# Install ARTEMIS over the Internet

The installer downloads a complete source snapshot, prepares Python/uv and
Node/npm, initializes missing configuration, builds the static web interface,
starts a detached server, and checks its identity and HTTP responses before
printing access URLs. Git, WinGet, Homebrew, Python and Node are not prerequisites.

## Install

**Release status: incomplete publication (rechecked 2026-10-28).** Both raw
installers and the new bootstrap/runtime helpers still return HTTP 404. The
`nextjs` ZIP and tar.gz archives now return HTTP 200 to HEAD requests, but the
published `tray_controller.py` and `daemon_client.py` differ from this checkout.
The Internet commands below cannot start an installation until the release owner
publishes the complete implementation together. This is an open acceptance blocker.

From a source checkout, verify the public downloads without installing anything:

```bash
python scripts/check_installer_release.py
```

Use `.venv/Scripts/python.exe scripts/check_installer_release.py` on this Windows
workspace if Python is not on PATH. The command checks both entry points and
required helper/config/lock files against the checkout (normalizing CRLF/LF),
and checks ZIP and tar.gz archive availability with HEAD requests. It requires
no API keys or Git credentials, makes no changes, and returns `4` on a missing
or inconsistent release. A 404 can also mean the repository is not publicly
readable; do not assume changing the branch name fixes it.

After publication, run the **Installer contracts** workflow manually with
`verify_public` enabled. Passing this download gate does not replace clean-machine
installation or second-device LAN acceptance. Repository publication/access
changes are performed separately by the release owner.

These public commands require this revision's installer **and helpers** to be
published together on the `nextjs` branch. Local implementation alone does not
publish them.

Linux/macOS, from Bash:

```bash
set -o pipefail
curl -fsSL https://raw.githubusercontent.com/jokerhung/android-automation-studio/nextjs/install.sh | bash
```

Windows, from Windows PowerShell 5.1 or PowerShell 7:

```powershell
& ([scriptblock]::Create((Invoke-RestMethod -Uri 'https://raw.githubusercontent.com/jokerhung/android-automation-studio/nextjs/install.ps1')))
```

For local development, run `bash install.sh --help` or `./install.ps1 -Help`.
The bootstrap always installs an isolated downloaded snapshot; it does not adopt
or change a developer checkout.

## Target environments and prerequisites

| OS | Architecture | Shell |
| --- | --- | --- |
| Windows 11 | x64 | PowerShell 5.1 / 7 |
| Ubuntu 22.04 / 24.04 with glibc | x86_64 | Bash |
| macOS 14 / 15 | Intel x86_64 / Apple Silicon arm64 | System Bash 3.2 or later |

This is the implementation target matrix. Clean-machine acceptance on every row
and access from a second LAN device still require separate verification. Other
OS/architecture combinations are rejected before downloading source.

Bash needs `curl`, CA certificates, `tar`, `mktemp`, and `sha256sum` (Ubuntu) or
`shasum` (macOS). On minimal Ubuntu, prepare the download tools with
`sudo apt-get update` followed by
`sudo apt-get install -y curl ca-certificates tar`. Windows needs HTTPS downloads
and PowerShell's `Expand-Archive`. Internet access to GitHub/codeload,
nodejs.org, Python package indexes and uv's Python releases is required.

uv **0.12.13** is downloaded into `.tools/uv` and verified against its release
SHA-256 checksum. uv provisions **Python 3.12** and runs `uv sync --locked
--python 3.12 --no-dev`. An existing Node >=22.12 with npm is reused; otherwise
portable **Node 22.22.3** (matching frontend CI) is installed into `.tools/node`
and verified against Node's `SHASUMS256.txt`. The build uses `npm ci` and
`npm run build`, with no fallback that changes lockfiles.

On minimal Ubuntu, OpenCV may require `libgl1` and `libglib2.0-0`. The installer
attempts apt installation as root or with already authorized `sudo -n`. If that
is unavailable, install those packages with `sudo apt-get install -y libgl1
libglib2.0-0`, then rerun. It does not wait for a password through the script pipe.

ADB is required for Android tasks; scrcpy and FFmpeg support additional media
features. Missing device tools/API keys do not prevent opening the web interface.
Use **Settings → System & Environment** for the actual readiness report and
tool-specific setup guidance. This installer does not configure IDE MCP clients.

## Options

| Bash | PowerShell | Meaning |
| --- | --- | --- |
| `--install-dir PATH` | `-InstallDir PATH` | Installation directory |
| `--port N` | `-Port N` | Exact port, 1–65535 |
| `--local-only` | `-LocalOnly` | Listen on 127.0.0.1 |
| `--non-interactive` | `-NonInteractive` | Do not prompt for a replacement port |
| `--open` | `-Open` | Open Settings after HTTP verification |
| `--help` | `-Help` | Show usage |

For example, Bash with a custom port and local access only:

```bash
set -o pipefail
curl -fsSL https://raw.githubusercontent.com/jokerhung/android-automation-studio/nextjs/install.sh | bash -s -- --port 8123 --local-only --non-interactive
```

PowerShell:

```powershell
& ([scriptblock]::Create((Invoke-RestMethod -Uri 'https://raw.githubusercontent.com/jokerhung/android-automation-studio/nextjs/install.ps1'))) -Port 8123 -LocalOnly -NonInteractive
```

Default directories are `$HOME/.local/share/artemis` on Linux/macOS and
`%LOCALAPPDATA%\Programs\Artemis` on Windows. The initial port is **8009** and
the initial bind is **0.0.0.0**, enabling access from reachable LAN devices.
ARTEMIS has no user login: machines that can reach that port can access the
console. Choose local-only when LAN access is unnecessary. Firewall rules are
not changed; Host/Origin checks and local-only lifecycle APIs remain enforced.

## Access and initial setup

The installer prints `http://localhost:8009`, `http://127.0.0.1:8009` and each
usable interface's IPv4 URL, using the actual selected port. VPN/virtual
interfaces are labeled. Detecting an address is not proof that another device
can reach it. On a second device, use an address on the same Wi-Fi/Ethernet
network; check the host firewall and network isolation if it fails.

Open `/settings/?tab=system`, configure the model under `?tab=models`, and
connect Android under `?tab=android`. No key/device is needed just to browse.
Some management actions must be performed from a browser on the server computer;
Settings displays its local address when accessed over LAN.

## Rerun, start, status, stop and restart

Rerunning the same install command preserves source, `.env`, configuration and
data. It reuses the saved port and verified running server without restarting.
It skips dependency synchronization and frontend build when fingerprints and
artifacts are current. Broken dependencies/assets are repaired only after the
installed server has been stopped explicitly. It does not upgrade the source.
An unrelated nonempty destination is rejected.

The installer prints complete management commands using the installed Python,
including quoting for spaces. For default directories:

```bash
"$HOME/.local/share/artemis/.venv/bin/python" "$HOME/.local/share/artemis/scripts/install_runtime.py" status
"$HOME/.local/share/artemis/.venv/bin/python" "$HOME/.local/share/artemis/scripts/install_runtime.py" stop
"$HOME/.local/share/artemis/.venv/bin/python" "$HOME/.local/share/artemis/scripts/install_runtime.py" start
"$HOME/.local/share/artemis/.venv/bin/python" "$HOME/.local/share/artemis/scripts/install_runtime.py" restart
```

```powershell
& "$env:LOCALAPPDATA/Programs/Artemis/.venv/Scripts/python.exe" "$env:LOCALAPPDATA/Programs/Artemis/scripts/install_runtime.py" status
& "$env:LOCALAPPDATA/Programs/Artemis/.venv/Scripts/python.exe" "$env:LOCALAPPDATA/Programs/Artemis/scripts/install_runtime.py" stop
& "$env:LOCALAPPDATA/Programs/Artemis/.venv/Scripts/python.exe" "$env:LOCALAPPDATA/Programs/Artemis/scripts/install_runtime.py" start
& "$env:LOCALAPPDATA/Programs/Artemis/.venv/Scripts/python.exe" "$env:LOCALAPPDATA/Programs/Artemis/scripts/install_runtime.py" restart
```

Installed `start.sh` and `start.bat` also reuse this manager, without rebuilding.
The server keeps running after the terminal closes. Nothing is registered to
start automatically on OS login.

## Errors and recovery

| Exit code | Meaning / next step |
| --- | --- |
| 2 | Invalid arguments or unsupported environment; see help/matrix |
| 3 | Permissions, unknown destination or lock; select a writable install directory |
| 4 | Download/archive/checksum; check HTTPS/proxy access, rerun |
| 5 | Dependency setup; read command output, check OS libraries and retry |
| 6 | Configuration syntax; fix the named file without resetting saved values |
| 7 | Frontend install/build/artifact; fix build error and rerun |
| 8 | Port, daemon or HTTP checks; select another port or inspect status/server log |
| 130 | Cancellation when captured; use status/stop, then rerun |

Download attempts are bounded (up to three attempts, ten minutes per request).
Dependency commands have a 30-minute deadline, build 20 minutes, and final HTTP
readiness 120 seconds. Home, Settings and actual static bytes must match the
export; TCP liveness and HTTP 200 alone cannot pass.

Installer stage/exit records are in `logs/install.log`; command details also
appear in the terminal. The server log's actual path is printed after startup.
Do not post `.env` or lifecycle metadata containing the internal token.
After a readiness timeout a server may still be starting; inspect status and
stop it explicitly before changing configuration or retrying a repair.

Bash uses a sibling `<install-dir>.install-lock` directory. An uncatchable kill
may leave it behind: only remove that directory after confirming no installer
is running. Windows uses an exclusive file handle released by the OS on exit;
the zero-content lock file can remain. Temporary source staging is unique to
each attempt and cleaned on normal exit/cancellation.
