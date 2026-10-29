#!/usr/bin/env python3
"""Shared Internet installer and installed-instance manager (Python 3.12).

Bootstrap preparation uses only the standard library. Application imports are
deferred until running inside the locked project environment.
"""

from __future__ import annotations

import argparse
from contextlib import contextmanager
import hashlib
from html.parser import HTMLParser
import json
import os
from pathlib import Path
import platform
import shlex
import shutil
import socket
import subprocess
import sys
import tarfile
import tempfile
import time
import urllib.parse
import urllib.request
import webbrowser
import zipfile

ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / ".artemis-install.json"
FRONTEND = ROOT / "apps/showcase_next"
OUT = FRONTEND / "out"
LOG = ROOT / "logs/install.log"
PYTHON = ROOT / (".venv/Scripts/python.exe" if os.name == "nt" else ".venv/bin/python")
BOOTSTRAP_VERSION = 1
NODE_VERSION = "22.22.3"  # Same version as the frontend CI build.
sys.path.insert(0, str(ROOT))


class InstallError(Exception):
    def __init__(self, code: int, message: str):
        super().__init__(message)
        self.code = code


def read_state() -> dict:
    try:
        state = json.loads(STATE.read_text(encoding="utf-8"))
        if state.get("schema") != 1 or state.get("source") != "jokerhung/android-automation-studio":
            raise ValueError
        if state.get("bootstrap_version", 1) != BOOTSTRAP_VERSION:
            raise ValueError("Unsupported bootstrap contract")
        directory = state.get("directory")
        if directory and Path(directory).resolve() != ROOT.resolve():
            raise ValueError("Installation moved; explicit recovery required")
        runtime_env = state.get("runtime_env", {})
        if not isinstance(runtime_env, dict) or any(
            key
            not in {
                "ARTEMIS_APP_DIR",
                "ANTIGRAVITY_APP_DIR",
                "ARTEMIS_USE_USER_DIR",
                "ARTEMIS_TRACES_DIR",
                "ARTEMIS_ARTEMIS_JSONC",
            }
            or not isinstance(value, str)
            for key, value in runtime_env.items()
        ):
            raise ValueError("Invalid runtime environment")
        if "port" in state and (type(state["port"]) is not int or not 1 <= state["port"] <= 65535):
            raise ValueError("Invalid port")
        if state.get("host", "0.0.0.0") not in {"0.0.0.0", "127.0.0.1"}:
            raise ValueError("Invalid bind")
        return state
    except (OSError, ValueError, AttributeError, TypeError) as exc:
        raise InstallError(3, f"Invalid installation metadata: {STATE}") from exc


def save_state(state: dict) -> None:
    temporary = STATE.with_suffix(".tmp")
    temporary.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
    temporary.replace(STATE)


def fingerprint(paths: list[Path]) -> str:
    digest = hashlib.sha256()
    for path in sorted(set(paths)):
        if path.is_file():
            digest.update(str(path.relative_to(ROOT)).encode())
            digest.update(path.read_bytes())
    return digest.hexdigest()


def frontend_fingerprint() -> str:
    paths = [
        FRONTEND / name
        for name in (
            "package.json",
            "package-lock.json",
            "next.config.ts",
            "postcss.config.mjs",
            "tsconfig.json",
        )
    ]
    for name in ("src", "public"):
        paths.extend((FRONTEND / name).rglob("*"))
    return fingerprint(paths)


def run(
    command: list[str],
    *,
    cwd: Path = ROOT,
    timeout: float = 1800,
    code: int = 5,
    preserve_code: bool = False,
) -> None:
    """Bounded command execution; keep raw dependency output out of user logs."""
    LOG.parent.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()
    # Child output can contain credentials from third-party tooling; capture only
    # with the terminal (no .env or child environment is copied into installer logs).
    with LOG.open("a", encoding="utf-8") as log:
        log.write(f"START {Path(command[0]).name}: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        log.flush()
        kwargs = (
            {"creationflags": subprocess.CREATE_NO_WINDOW}
            if os.name == "nt"
            else {"start_new_session": True}
        )
        with subprocess.Popen(command, cwd=cwd, stdin=subprocess.DEVNULL, **kwargs) as process:
            try:
                while True:
                    try:
                        result = process.wait(
                            timeout=min(10, max(0.1, timeout - (time.monotonic() - started)))
                        )
                        break
                    except subprocess.TimeoutExpired:
                        elapsed = time.monotonic() - started
                        print(f"[DANG] {Path(command[0]).name}: {elapsed:.0f}s", flush=True)
                        if elapsed >= timeout:
                            raise InstallError(
                                code, f"{Path(command[0]).name} timed out after {timeout:.0f}s"
                            ) from None
            except BaseException:
                # Terminate only the subprocess tree created by this invocation.
                if os.name == "nt":
                    subprocess.run(
                        ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        check=False,
                    )
                else:
                    import signal

                    os.killpg(process.pid, signal.SIGTERM)
                process.wait(timeout=10)
                raise
        log.write(f"EXIT {result}, elapsed {time.monotonic() - started:.1f}s\n")
    if result:
        raise InstallError(
            result if preserve_code and result in {2, 3, 4, 5, 6, 7, 8, 130} else code,
            f"{Path(command[0]).name} failed (exit {result}); review the command output above and retry",
        )


def download(url: str, destination: Path) -> None:
    """HTTPS downloads, bounded retries and total time per attempt."""
    for attempt in range(3):
        try:
            started = time.monotonic()
            with (
                urllib.request.urlopen(url, timeout=15) as response,
                destination.open("wb") as output,
            ):
                while chunk := response.read(1024 * 1024):
                    output.write(chunk)
                    if time.monotonic() - started > 600:
                        raise TimeoutError
            return
        except (OSError, TimeoutError) as exc:
            if attempt == 2:
                raise InstallError(4, f"Download failed: {url}") from exc
            time.sleep(2 * (attempt + 1))


def prepare_node() -> str:
    managed = ROOT / ".tools/node" / ("node.exe" if os.name == "nt" else "bin/node")
    for candidate in (str(managed), shutil.which("node")):
        if not candidate:
            continue
        try:
            result = subprocess.run(
                [candidate, "-p", "process.versions.node"],
                capture_output=True,
                text=True,
                timeout=10,
                check=True,
            )
            if tuple(int(n) for n in result.stdout.strip().split(".")) >= (22, 12, 0):
                directory = str(Path(candidate).parent)
                os.environ["PATH"] = directory + os.pathsep + os.environ.get("PATH", "")
                npm = shutil.which("npm.cmd" if os.name == "nt" else "npm")
                if npm:
                    return npm
        except (OSError, ValueError, subprocess.SubprocessError):
            pass
    system = {"Windows": "win", "Linux": "linux", "Darwin": "darwin"}[platform.system()]
    arch = "arm64" if platform.machine().lower() in {"arm64", "aarch64"} else "x64"
    stem = f"node-v{NODE_VERSION}-{system}-{arch}"
    filename = stem + (".zip" if os.name == "nt" else ".tar.gz")
    base = f"https://nodejs.org/dist/v{NODE_VERSION}"
    with tempfile.TemporaryDirectory(prefix="artemis-node-", dir=ROOT / ".tools") as temporary:
        temporary = Path(temporary)
        archive, sums = temporary / filename, temporary / "SHASUMS256.txt"
        download(f"{base}/{filename}", archive)
        download(f"{base}/SHASUMS256.txt", sums)
        expected = next(
            (
                line.split()[0]
                for line in sums.read_text().splitlines()
                if line.split()[-1] == filename
            ),
            None,
        )
        if not expected or hashlib.sha256(archive.read_bytes()).hexdigest() != expected:
            raise InstallError(4, "Node.js checksum mismatch")
        if os.name == "nt":
            with zipfile.ZipFile(archive) as bundle:
                bundle.extractall(temporary)
        else:
            with tarfile.open(archive) as bundle:
                bundle.extractall(temporary, filter="data")
        target = ROOT / ".tools/node"
        if target.exists():
            shutil.rmtree(target)
        shutil.move(str(temporary / stem), target)
    return prepare_node()


class Assets(HTMLParser):
    def __init__(self):
        super().__init__()
        self.urls: set[str] = set()

    def handle_starttag(self, tag, attrs):
        for key, value in attrs:
            if key in {"href", "src"} and value and value.startswith("/_next/"):
                self.urls.add(value)


def frontend_assets() -> list[str]:
    assets = Assets()
    try:
        for page in (OUT / "index.html", OUT / "settings/index.html"):
            text = page.read_text(encoding="utf-8")
            assets.feed(text)
            if "<html" not in text.lower() or "<script" not in text.lower():
                raise ValueError("Missing HTML/scripts")
        if not assets.urls:
            raise ValueError("No Next.js assets")
        for url in assets.urls:
            path = (
                OUT / urllib.parse.unquote(urllib.parse.urlsplit(url).path).lstrip("/")
            ).resolve()
            if (
                not path.is_relative_to(OUT.resolve())
                or not path.is_file()
                or not path.stat().st_size
            ):
                raise ValueError("Missing frontend asset")
    except (OSError, ValueError) as exc:
        raise InstallError(
            7, "Incomplete frontend export; rerun the installer to build Home, Settings and assets"
        ) from exc
    return sorted(assets.urls)


def dependencies_current(state: dict, signature: str) -> bool:
    if not PYTHON.is_file() or state.get("dependencies") != signature:
        return False
    probe = subprocess.run(
        [str(PYTHON), "-c", "import fastapi, uvicorn, psutil, cv2, artemis_client"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        timeout=30,
    )
    return probe.returncode == 0


def prepare(args, state: dict) -> int:
    # Persist only path/behavior overrides; never store API keys or full env.
    runtime_env = dict(state.get("runtime_env", {}))
    runtime_env.update(
        {
            key: value
            for key, value in os.environ.items()
            if key
            in {
                "ARTEMIS_APP_DIR",
                "ANTIGRAVITY_APP_DIR",
                "ARTEMIS_USE_USER_DIR",
                "ARTEMIS_TRACES_DIR",
                "ARTEMIS_ARTEMIS_JSONC",
            }
        }
    )
    state["runtime_env"] = runtime_env
    for key, value in runtime_env.items():
        os.environ[key] = value
    state.update(stage="preparing", directory=str(ROOT), bootstrap_version=BOOTSTRAP_VERSION)
    save_state(state)
    signature = fingerprint(
        [ROOT / "uv.lock", ROOT / "pyproject.toml", ROOT / "packages/artemis-client/pyproject.toml"]
    )
    current = dependencies_current(state, signature)
    build_current = state.get("frontend") == frontend_fingerprint()
    try:
        frontend_assets()
    except InstallError:
        build_current = False
    if not current or not build_current:
        # Do not mutate the environment/assets of any running installed server.
        if PYTHON.exists():
            probe = subprocess.run(
                [str(PYTHON), str(Path(__file__)), "_active"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=30,
            )
            if probe.returncode != 0:
                raise InstallError(
                    8,
                    "Stop the installed server explicitly before repairing dependencies or frontend assets",
                )
        if not current:
            print("[DANG] 3/6 Syncing locked Python dependencies", flush=True)
            run([args.uv, "sync", "--locked", "--python", "3.12", "--no-dev"])
            # OpenCV wheels need these libraries on a minimal Ubuntu image.
            if platform.system() == "Linux":
                cv = subprocess.run(
                    [str(PYTHON), "-c", "import cv2"], capture_output=True, text=True, timeout=30
                )
                if cv.returncode and any(
                    lib in cv.stderr for lib in ("libGL.so", "libglib", "libgthread")
                ):
                    sudo = [] if os.geteuid() == 0 else ["sudo", "-n"]
                    print("[CAN] OpenCV requires Ubuntu packages: libgl1 libglib2.0-0", flush=True)
                    run([*sudo, "apt-get", "update"])
                    run([*sudo, "apt-get", "install", "-y", "libgl1", "libglib2.0-0"])
            if not dependencies_current({"dependencies": signature}, signature):
                raise InstallError(
                    5,
                    "Python dependency import failed; on Ubuntu install libgl1 and libglib2.0-0, then retry",
                )
            state["dependencies"] = signature
            save_state(state)
        else:
            print("[GIU] 3/6 Python environment is current", flush=True)
        configure = [str(PYTHON), str(Path(__file__)), "_configure"]
        if args.port is not None:
            configure += ["--port", str(args.port)]
        for name in ("local_only", "non_interactive"):
            if getattr(args, name):
                configure.append("--" + name.replace("_", "-"))
        run(configure, timeout=60, code=6, preserve_code=True)
        state = read_state()
        if not build_current:
            print("[DANG] 5/6 Building frontend", flush=True)
            (ROOT / ".tools").mkdir(exist_ok=True)
            npm = prepare_node()
            # Never accept leftover output after a failed build.
            state.pop("frontend", None)
            save_state(state)
            run([npm, "ci", "--no-audit", "--no-fund"], cwd=FRONTEND, code=7)
            run([npm, "run", "build"], cwd=FRONTEND, timeout=1200, code=7)
            frontend_assets()
            state["frontend"] = frontend_fingerprint()
            save_state(state)
    else:
        print("[GIU] 3/6 Dependencies and 5/6 frontend are current", flush=True)
    command = [str(PYTHON), str(Path(__file__)), "_finish"]
    if args.port is not None:
        command += ["--port", str(args.port)]
    for name in ("local_only", "non_interactive", "open"):
        if getattr(args, name):
            command.append("--" + name.replace("_", "-"))
    return subprocess.call(command, cwd=ROOT, stdin=subprocess.DEVNULL)


def initialize_config() -> None:
    from artemis.config.paths import get_config_path, get_env_file
    from artemis.utils.file import load_jsonc
    from dotenv.parser import parse_stream

    env = get_env_file()
    env.parent.mkdir(parents=True, exist_ok=True)
    if not env.exists():
        template = ROOT / ".env.example"
        # Exclusive creation also preserves a file created concurrently by Settings.
        try:
            with env.open("x", encoding="utf-8") as output:
                if template.exists():
                    output.write(template.read_text(encoding="utf-8"))
            if os.name != "nt":
                env.chmod(0o600)
        except FileExistsError:
            pass
    with env.open(encoding="utf-8") as stream:
        if any(binding.error for binding in parse_stream(stream)):
            raise InstallError(6, f"Invalid dotenv syntax: {env}; fix the file and retry")
    override = os.environ.get("ARTEMIS_ARTEMIS_JSONC")
    if override and not Path(override).is_file():
        raise InstallError(
            6,
            f"Configuration override does not exist: {override}; create it or remove the override",
        )
    config = get_config_path("artemis.jsonc")
    try:
        with config.open(encoding="utf-8") as source:
            load_jsonc(source)
    except Exception as exc:
        raise InstallError(
            6, f"Invalid configuration: {config}; preserve the file and fix its syntax"
        ) from exc
    print(f"[OK] 4/6 Configuration preserved/initialized: {env}", flush=True)


def lifecycle(host: str, port: int):
    from artemis.runtime.tray_controller import ArtemisLifecycleAdapter

    return ArtemisLifecycleAdapter(host=host, port=port, poll_interval=1)


def port_available(port: int, host: str) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        try:
            listener.bind((host, port))
            return True
        except OSError:
            return False


def choose_port(args, state: dict, host: str) -> int:
    from artemis.runtime.tray_controller import DaemonPresence

    port = args.port if args.port is not None else state.get("port", 8009)
    presence = lifecycle(host, port).status().presence
    if presence is DaemonPresence.ARTEMIS or (
        presence is DaemonPresence.STOPPED and port_available(port, host)
    ):
        return port
    if args.port is not None or args.non_interactive:
        raise InstallError(8, f"Port {port} is occupied. Retry with --port N (PowerShell: -Port N)")
    suggestion = next(
        (n for n in range(port + 1, min(port + 101, 65536)) if port_available(n, host)), None
    )
    try:
        # Read the controlling terminal, never the piped installer script.
        terminal_name = "CON" if os.name == "nt" else "/dev/tty"
        with open(terminal_name, "r+") as terminal:
            if not terminal.isatty():
                raise OSError
            terminal.write(
                f"[CAN] Port {port} occupied. Enter available port [{suggestion}], or q to cancel: "
            )
            terminal.flush()
            answer = terminal.readline().strip()
    except OSError:
        raise InstallError(
            8, f"Port {port} occupied; no interactive terminal. Use --port N (PowerShell: -Port N)"
        ) from None
    if answer.lower() == "q":
        raise KeyboardInterrupt
    try:
        chosen = int(answer or str(suggestion))
        if 1 <= chosen <= 65535 and port_available(chosen, host):
            return chosen
    except ValueError:
        pass
    raise InstallError(8, "Invalid or occupied port. Retry with --port N (PowerShell: -Port N)")


def http_frontend_ready(port: int, assets: list[str], *, timeout: float = 2) -> bool:
    # Avoid HTTP_PROXY for loopback readiness, and compare complete bytes so the
    # backend's HTTP-200 'Not Built' page or HTML fallback cannot pass.
    client = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    for url, path in [
        ("/", OUT / "index.html"),
        ("/settings/", OUT / "settings/index.html"),
        (assets[0], OUT / urllib.parse.urlsplit(assets[0]).path.lstrip("/")),
    ]:
        try:
            with client.open(f"http://127.0.0.1:{port}{url}", timeout=timeout) as response:
                if (
                    response.status != 200
                    or hashlib.sha256(response.read()).digest()
                    != hashlib.sha256(path.read_bytes()).digest()
                ):
                    return False
        except (OSError, ValueError):
            return False
    return True


def wait_ready(adapter, port: int, assets: list[str], *, timeout: float = 120) -> None:
    from artemis.runtime.tray_controller import DaemonPresence

    deadline = time.monotonic() + timeout
    last_progress = 0.0
    while time.monotonic() < deadline:
        if adapter.status().presence is DaemonPresence.ARTEMIS and http_frontend_ready(
            port, assets, timeout=min(2, max(0.1, (deadline - time.monotonic()) / 3))
        ):
            return
        if time.monotonic() - last_progress >= 10:
            print(
                "[DANG] 6/6 Waiting for ARTEMIS identity, Home, Settings and asset HTTP checks",
                flush=True,
            )
            last_progress = time.monotonic()
        time.sleep(min(1, max(0, deadline - time.monotonic())))
    raise InstallError(
        8,
        f"Readiness timeout on port {port}; a daemon may still be starting. Use status/stop before retrying",
    )


def show_access(port: int, host: str) -> None:
    from artemis.runtime.daemon_client import daemon_log_path
    from artemis.runtime.network_urls import lan_addresses

    print("[OK] ARTEMIS HTTP and frontend verified. Background process; terminal can be closed.")
    print(f"http://localhost:{port}\nhttp://127.0.0.1:{port}")
    if host == "0.0.0.0":
        try:
            addresses = lan_addresses()
        except Exception:
            addresses = []
        for name, address, virtual in addresses:
            print(f"Interface: {name}" + (" [VPN/virtual; may not be LAN]" if virtual else ""))
            print(f"http://{address}:{port}")
        print(
            "[CAN] Addresses detected; access from another device has not been verified."
            if addresses
            else "[CAN] No usable LAN IPv4 found. Local access is available."
        )
    else:
        print("[GIU] Local-only bind; LAN access is disabled.")
    for tab in ("system", "models", "android"):
        print(f"http://localhost:{port}/settings/?tab={tab}")
    print(
        "Configure models and connect Android in Settings. Web access needs neither a key nor a device."
    )
    print(f"Directory: {ROOT}\nInstaller log: {LOG}\nServer log: {daemon_log_path(port)}")
    for action in ("start", "status", "stop", "restart"):
        command = [str(PYTHON), str(Path(__file__)), action]
        if os.name == "nt":
            rendered = "& " + " ".join("'" + value.replace("'", "''") + "'" for value in command)
        else:
            rendered = shlex.join(command)
        print(f"{action}: {rendered}")


def manage(args, state: dict) -> int:
    from artemis.runtime.background_runtime import ensure_background_runtime
    from artemis.runtime.server_lifecycle import read_server_info
    from artemis.runtime.tray_controller import DaemonPresence

    if args.action != "_finish":
        install_lock = ROOT.with_name(ROOT.name + ".install-lock")
        if os.name == "nt":
            try:
                # The bootstrap holds this file with FileShare.None. Merely
                # opening an existing lock detects it without creating files.
                if install_lock.exists():
                    with install_lock.open("rb"):
                        pass
            except PermissionError as exc:
                raise InstallError(
                    3, "Installer is running; retry management after it finishes"
                ) from exc
        elif install_lock.exists():
            raise InstallError(3, "Installer is running; retry management after it finishes")

    host = "127.0.0.1" if args.local_only else state.get("host", "0.0.0.0")
    port = (
        choose_port(args, state, host)
        if args.action == "_finish"
        else (args.port or state.get("port", 8009))
    )
    adapter = lifecycle(host, port)
    status = adapter.status()
    if args.action == "status":
        print(f"{status.presence.value}: port {port}")
        if status.presence is DaemonPresence.ARTEMIS:
            wait_ready(adapter, port, frontend_assets(), timeout=10)
            show_access(port, (read_server_info(port) or {}).get("host", "127.0.0.1"))
            return 0
        return 8
    if args.action in {"stop", "restart"}:
        if not adapter.stop(timeout=30):
            raise InstallError(
                8, "Verified daemon did not stop; no unrelated process was terminated"
            )
        if args.action == "stop":
            print(f"[OK] Stopped port {port}")
            return 0
        status = adapter.status()
    assets = frontend_assets()
    initialize_config()
    if status.presence is DaemonPresence.ARTEMIS:
        actual_host = (read_server_info(port) or {}).get("host", "127.0.0.1")
        if args.local_only and actual_host != "127.0.0.1":
            raise InstallError(
                8, "Running instance has LAN bind. Stop it explicitly before selecting --local-only"
            )
        host = actual_host
        print("[GIU] Reusing verified running ARTEMIS instance", flush=True)
    elif status.presence is not DaemonPresence.STOPPED:
        raise InstallError(8, f"Port {port} is occupied by an unverified process")
    else:
        print("[DANG] 6/6 Starting background ARTEMIS", flush=True)
        # The lifecycle waiter may see a listening socket before identity is
        # initialized. The bounded loop below performs the final verification.
        state.update(stage="starting", host=host, port=port)
        save_state(state)
        ensure_background_runtime(host=host, port=port, lifecycle=adapter, wait_timeout=0)
    wait_ready(adapter, port, assets)
    state.update(host=host, port=port, stage="ready", directory=str(ROOT))
    save_state(state)
    show_access(port, host)
    if args.open:
        try:
            if not webbrowser.open(f"http://localhost:{port}/settings/?tab=system"):
                print("[CAN] Could not open browser automatically; open the URL above.")
        except Exception:
            print("[CAN] Could not open browser automatically; open the URL above.")
    return 0


@contextmanager
def management_lock():
    """Serialize management calls; the outer bootstrap owns the install lock."""
    path = ROOT / ".artemis-manager.lock"
    with path.open("a+b") as handle:
        try:
            if os.name == "nt":
                import msvcrt

                handle.seek(0)
                handle.write(b"0")
                handle.flush()
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl

                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            raise InstallError(3, "Another installed-instance operation is running") from exc
        yield


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "action",
        choices=(
            "install",
            "_configure",
            "_finish",
            "_active",
            "start",
            "status",
            "stop",
            "restart",
        ),
    )
    parser.add_argument("--uv")
    parser.add_argument("--port", type=int)
    parser.add_argument("--local-only", action="store_true")
    parser.add_argument("--non-interactive", action="store_true")
    parser.add_argument("--open", action="store_true")
    args = parser.parse_args()
    if args.port is not None and not 1 <= args.port <= 65535:
        parser.error("--port must be 1..65535")
    os.chdir(ROOT)
    os.environ["ARTEMIS_FRONTEND"] = "next"
    try:
        state = read_state()
        if args.action != "install":
            for key, value in state.get("runtime_env", {}).items():
                if key in {
                    "ARTEMIS_APP_DIR",
                    "ANTIGRAVITY_APP_DIR",
                    "ARTEMIS_USE_USER_DIR",
                    "ARTEMIS_TRACES_DIR",
                    "ARTEMIS_ARTEMIS_JSONC",
                }:
                    os.environ.setdefault(key, value)
        if args.action == "_active":
            # Remain usable when an interrupted sync left application imports
            # incomplete. Treat uninspectable metadata conservatively.
            try:
                import psutil
            except ImportError:
                psutil = None
            directories = {ROOT}
            for key in ("ARTEMIS_APP_DIR", "ANTIGRAVITY_APP_DIR"):
                if os.environ.get(key):
                    directories.add(Path(os.environ[key]))
            if state.get("server_info_dir"):
                directories.add(Path(state["server_info_dir"]))
            for path in (
                p for directory in directories for p in directory.glob(".artemis_server*.json")
            ):
                try:
                    info = json.loads(path.read_text(encoding="utf-8"))
                    same_workspace = os.path.normcase(
                        str(info.get("workspace", info.get("cwd")))
                    ) == os.path.normcase(str(ROOT))
                    if same_workspace and (psutil is None or psutil.pid_exists(info["pid"])):
                        return 1
                except (OSError, ValueError, KeyError, TypeError):
                    # Unknown metadata must not authorize dependency mutation.
                    return 1
            return 0
        if args.action == "install":
            if not args.uv:
                raise InstallError(2, "Use install.sh or install.ps1 to prepare uv")
            return prepare(args, state)
        if args.action == "_configure":
            from artemis.config.paths import get_server_info_file

            initialize_config()
            host = "127.0.0.1" if args.local_only else state.get("host", "0.0.0.0")
            port = choose_port(args, state, host)
            state.update(host=host, port=port, server_info_dir=str(get_server_info_file().parent))
            save_state(state)
            return 0
        with management_lock():
            return manage(args, state)
    except KeyboardInterrupt:
        print(
            "[HUY] Installation cancelled. A previously started daemon may remain; use status/stop.",
            file=sys.stderr,
        )
        return 130
    except InstallError as exc:
        print(
            f"[LOI] {exc}\nCode: {exc.code}; installer log: {LOG}\nRetry the same installer command. Existing configuration was preserved.",
            file=sys.stderr,
        )
        return exc.code
    except Exception as exc:
        # Exception text from third-party config parsers can include secrets.
        print(
            f"[LOI] {type(exc).__name__} during {args.action}. Review configuration/tool availability and retry. Log: {LOG}",
            file=sys.stderr,
        )
        return 6 if args.action in {"_configure", "_finish"} else 5


if __name__ == "__main__":
    sys.exit(main())
