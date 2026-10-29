"""Run the Internet Bash bootstrap with a local archive and fake toolchain.

Host installer tests; no Android device or device actions are used.
"""

import io
import os
from pathlib import Path
import shutil
import subprocess
import tarfile

import pytest

ROOT = Path(__file__).resolve().parents[3]
BASH = (
    shutil.which("bash")
    if os.name != "nt"
    else shutil.which("bash", path=r"C:\Program Files\Git\bin")
)
pytestmark = [pytest.mark.integration, pytest.mark.skipif(not BASH, reason="Bash unavailable")]


@pytest.fixture
def bootstrap(tmp_path):
    tools = tmp_path / "bin"
    tools.mkdir()
    archive = tmp_path / "source.tar.gz"
    entries = {
        name: "fixture"
        for name in (
            "install.sh",
            "install.ps1",
            ".env.example",
            "apps/admin_console/__init__.py",
            "apps/showcase_next/package.json",
            "apps/showcase_next/next.config.ts",
            "apps/showcase_next/src/app/page.tsx",
            "pyproject.toml",
            "uv.lock",
            "artemis/__init__.py",
            "apps/showcase_next/package-lock.json",
            "packages/artemis-client/pyproject.toml",
            "config/artemis.jsonc",
            "scripts/install_runtime.py",
        )
    }
    entries["scripts/install_runtime.py"] = "BOOTSTRAP_VERSION = 1\n"
    entries["scripts/bootstrap_common.sh"] = """bootstrap_uv() {
  ARTEMIS_UV="$1/fake-uv"
  printf '#!/usr/bin/env bash\nprintf "%%s\\n" "$*" >> "$ARTEMIS_TEST_CALLS"\nif [ "$1" = run ]; then exit "${ARTEMIS_TEST_EXIT:-0}"; fi\n' > "$ARTEMIS_UV"
  chmod +x "$ARTEMIS_UV"
}
"""
    with tarfile.open(archive, "w:gz") as bundle:
        for name, content in entries.items():
            data = content.encode()
            member = tarfile.TarInfo("snapshot/" + name)
            member.size = len(data)
            bundle.addfile(member, io.BytesIO(data))
    scripts = {
        "uname": '#!/bin/sh\nif [ "$1" = -s ]; then echo Darwin; else echo arm64; fi\n',
        "sw_vers": "#!/bin/sh\necho 14.7\n",
        "curl": '#!/bin/sh\nwhile [ "$#" -gt 0 ]; do if [ "$1" = -o ]; then cp "$ARTEMIS_TEST_ARCHIVE" "$2"; exit; fi; shift; done\nexit 4\n',
    }
    for name, content in scripts.items():
        path = tools / name
        path.write_text(content, newline="\n")
        path.chmod(0o755)
    destination = tmp_path / "Install path with spaces"
    env = dict(
        os.environ,
        PATH=str(tools) + os.pathsep + os.environ["PATH"],
        ARTEMIS_TEST_ARCHIVE=str(archive),
        ARTEMIS_TEST_CALLS=str(tmp_path / "calls"),
    )

    def execute(*args, code=0):
        env["ARTEMIS_TEST_EXIT"] = str(code)

        def bash_path(path):
            value = Path(path).as_posix()
            return "/" + value[0].lower() + value[2:] if os.name == "nt" else value

        return subprocess.run(
            [
                BASH,
                "-c",
                'export PATH="$1:$PATH"; shift; cat "$1" | bash -s -- "${@:2}"',
                "bootstrap-test",
                bash_path(tools),
                str(ROOT / "install.sh"),
                "--install-dir",
                bash_path(destination),
                *args,
            ],
            env=env,
            capture_output=True,
            text=True,
            timeout=30,
        )

    return execute, destination, tmp_path


def test_pipe_download_install_rerun_and_cleanup(bootstrap):
    execute, destination, root = bootstrap
    result = execute("--port", "8123", "--non-interactive")
    assert result.returncode == 0, result.stdout + result.stderr
    assert (destination / ".artemis-install.json").is_file()
    assert not Path(str(destination) + ".install-lock").exists()
    assert not list(root.glob(".artemis-stage.*"))
    assert "--port 8123 --non-interactive" in (root / "calls").read_text()
    (destination / ".env").write_text("PRESERVED=1")
    result = execute()
    assert result.returncode == 0, result.stdout + result.stderr
    assert "[GIU]" in result.stdout
    assert (destination / ".env").read_text() == "PRESERVED=1"


def test_unknown_destination_is_preserved(bootstrap):
    execute, destination, _ = bootstrap
    destination.mkdir()
    sentinel = destination / "important.txt"
    sentinel.write_text("keep")
    result = execute()
    assert result.returncode == 3
    assert sentinel.read_text() == "keep"
    assert not (destination / "pyproject.toml").exists()


def test_native_runtime_failure_code_is_not_swallowed(bootstrap):
    execute, destination, _ = bootstrap
    assert execute().returncode == 0
    result = execute(code=8)
    assert result.returncode == 8, result.stdout + result.stderr
    assert not Path(str(destination) + ".install-lock").exists()


def test_invalid_arguments_fail_before_download(bootstrap):
    execute, destination, _ = bootstrap
    assert execute("--port", "65536").returncode == 2
    assert execute("--unknown").returncode == 2
    assert not destination.exists()


def test_concurrent_installer_fails_without_touching_destination(bootstrap):
    execute, destination, _ = bootstrap
    lock = Path(str(destination) + ".install-lock")
    lock.mkdir()
    assert execute().returncode == 3
    assert not destination.exists()
    assert lock.is_dir()
