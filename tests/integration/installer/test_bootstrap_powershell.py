"""Exercise the PowerShell scriptblock bootstrap with local download fixtures."""

import os
from pathlib import Path
import shutil
import subprocess
import zipfile

import pytest

ROOT = Path(__file__).resolve().parents[3]
SHELLS = [name for name in ("powershell", "pwsh") if shutil.which(name)]
pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(os.name != "nt" or not SHELLS, reason="Windows PowerShell required"),
]


@pytest.fixture
def bootstrap_ps(tmp_path):
    archive = tmp_path / "source.zip"
    helper = """function Initialize-BootstrapUv([string]$Root, [string]$Temporary) {
        return (Join-Path $Root 'fake-uv.cmd')
    }
"""
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
    entries["scripts/bootstrap_common.ps1"] = helper
    entries["fake-uv.cmd"] = (
        '@echo off\r\necho %*>>"%ARTEMIS_TEST_CALLS%"\r\nif "%1"=="run" exit /b %ARTEMIS_TEST_EXIT%\r\nexit /b 0\r\n'
    )
    with zipfile.ZipFile(archive, "w") as bundle:
        for name, content in entries.items():
            bundle.writestr("snapshot/" + name, content)
    harness = tmp_path / "harness.ps1"
    harness.write_text(
        """$ErrorActionPreference = 'Stop'
function Invoke-WebRequest {
    param($UseBasicParsing, $Uri, $OutFile, $TimeoutSec)
    Copy-Item -LiteralPath $env:ARTEMIS_TEST_ARCHIVE -Destination $OutFile
}
# Simulate the supported OS gate so Windows 10 development hosts can exercise
# the Windows 11 installer behavior. The production gate itself is unchanged.
$env:OS = 'Windows_NT'
$env:PROCESSOR_ARCHITECTURE = 'AMD64'
$source = (Get-Content -LiteralPath $env:ARTEMIS_TEST_SOURCE -Raw).Replace('-lt 22000', '-lt 0')
try {
    & ([scriptblock]::Create($source)) -InstallDir $env:ARTEMIS_TEST_DEST -Port 8123 -NonInteractive
} catch {
    # Scriptblocks throw without closing the caller's interactive shell. A host
    # running -File can explicitly map the preserved installer code to its exit.
    if ($LASTEXITCODE -in @(2, 3, 4, 5, 6, 7, 8, 130)) { exit $LASTEXITCODE }
    throw
}
""",
        encoding="ascii",
    )
    # Use a proper switch signature for the mocked web command.
    harness.write_text(
        harness.read_text().replace("param($UseBasicParsing,", "param([switch]$UseBasicParsing,"),
        encoding="ascii",
    )
    destination = tmp_path / "Install path with spaces"
    env = dict(
        os.environ,
        ARTEMIS_TEST_SOURCE=str(ROOT / "install.ps1"),
        ARTEMIS_TEST_ARCHIVE=str(archive),
        ARTEMIS_TEST_CALLS=str(tmp_path / "calls"),
        ARTEMIS_TEST_DEST=str(destination),
        ARTEMIS_TEST_EXIT="0",
    )

    def execute(shell, code=0):
        env["ARTEMIS_TEST_EXIT"] = str(code)
        return subprocess.run(
            [shell, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(harness)],
            env=env,
            capture_output=True,
            text=True,
            timeout=30,
        )

    return execute, destination, tmp_path


@pytest.mark.parametrize("shell", SHELLS or ["powershell"])
def test_scriptblock_install_rerun_native_exit_and_preservation(bootstrap_ps, shell):
    execute, destination, root = bootstrap_ps
    result = execute(shell)
    assert result.returncode == 0, result.stdout + result.stderr
    assert (destination / ".artemis-install.json").exists()
    assert "--port 8123 --non-interactive" in (root / "calls").read_text()
    env = destination / ".env"
    env.write_text("PRESERVED=1")
    assert execute(shell).returncode == 0
    assert env.read_text() == "PRESERVED=1"
    result = execute(shell, code=8)
    assert result.returncode == 8, result.stdout + result.stderr
    assert env.read_text() == "PRESERVED=1"
    assert not list(root.glob(".artemis-stage-*"))
