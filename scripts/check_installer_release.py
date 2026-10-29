#!/usr/bin/env python3
"""Check anonymous public installer downloads without installing or publishing.

Standard library only. Exit 0 means the selected files are reachable and match
this checkout (ignoring CRLF/LF); it is not clean-machine or LAN acceptance.
Exit 4 means publication/download verification failed, 2 means invalid options.
"""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
import re
import sys
import urllib.error
import urllib.parse
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
REQUIRED_FILES = (
    "install.sh",
    "install.ps1",
    "scripts/bootstrap_common.sh",
    "scripts/bootstrap_common.ps1",
    "scripts/install_runtime.py",
    "artemis/runtime/network_urls.py",
    "artemis/runtime/tray_controller.py",
    "artemis/runtime/daemon_client.py",
    "pyproject.toml",
    "uv.lock",
    "packages/artemis-client/pyproject.toml",
    "config/artemis.jsonc",
    "apps/showcase_next/package.json",
    "apps/showcase_next/package-lock.json",
)


@dataclass(frozen=True)
class Resource:
    label: str
    url: str
    local_path: Path | None = None


def resources(repo: str, ref: str, root: Path = ROOT) -> list[Resource]:
    encoded_ref = urllib.parse.quote(ref, safe="")
    raw = f"https://raw.githubusercontent.com/{repo}/{encoded_ref}"
    result = [Resource(name, f"{raw}/{name}", root / name) for name in REQUIRED_FILES]
    for archive_format in ("zip", "tar.gz"):
        result.append(
            Resource(
                f"source archive ({archive_format})",
                f"https://codeload.github.com/{repo}/{archive_format}/refs/heads/{encoded_ref}",
            )
        )
    return result


def check(resource: Resource, timeout: float = 15) -> tuple[bool, str]:
    method = "GET" if resource.local_path is not None else "HEAD"
    request = urllib.request.Request(
        resource.url, method=method, headers={"User-Agent": "Artemis-Public-Release-Check/1.0"}
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            if response.status != 200:
                return False, f"HTTP {response.status}"
            if resource.local_path is not None:
                # All selected resources are text; Windows checkout line endings
                # must not be mistaken for a different published implementation.
                local = resource.local_path.read_bytes().replace(b"\r\n", b"\n")
                published = response.read(len(local) + 1024 * 1024).replace(b"\r\n", b"\n")
                if published != local:
                    return False, "HTTP 200, content differs from this checkout"
                return True, "HTTP 200, checkout text matches"
            return True, "HTTP 200, archive reachable (HEAD only)"
    except urllib.error.HTTPError as exc:
        return False, f"HTTP {exc.code}"
    except (OSError, ValueError) as exc:
        # Avoid printing proxy credentials or arbitrary response/exception text.
        return False, f"download/local-read failed ({type(exc).__name__})"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", default="jokerhung/android-automation-studio")
    parser.add_argument("--ref", default="nextjs", help="Published branch")
    parser.add_argument("--timeout", type=float, default=15, help="Per-request timeout in seconds")
    args = parser.parse_args(argv)
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", args.repo):
        parser.error("--repo must be OWNER/REPOSITORY")
    if not args.ref or not 1 <= args.timeout <= 120:
        parser.error("--ref must be nonempty and --timeout must be 1..120")
    targets = resources(args.repo, args.ref)
    print(f"Public installer release check: {args.repo} @ {args.ref}", flush=True)
    with ThreadPoolExecutor(max_workers=6) as pool:
        results = list(pool.map(lambda resource: check(resource, args.timeout), targets))
    for target, (ok, detail) in zip(targets, results, strict=True):
        print(f"[{'OK' if ok else 'LOI'}] {target.label}: {detail}\n{target.url}")
    if not all(ok for ok, _ in results):
        print(
            "[LOI] Public release unavailable or inconsistent. A 404 may mean a missing "
            "repository/ref/file or lack of anonymous access. The release owner must "
            "publish the installer and source/helpers together, then rerun this check. "
            "This command does not publish or change repository access.",
            file=sys.stderr,
        )
        return 4
    print(
        "[OK] Download gate passed. Clean-machine installation and second-device LAN tests are still required."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
