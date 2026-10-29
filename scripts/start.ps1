# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

[CmdletBinding()]
param(
    [ValidateRange(1, 65535)]
    [int]$Port = 8009,
    [switch]$NoOpen = $false,
    [switch]$Daemon = $false,
    [switch]$Stop = $false,
    [ValidateSet("next")]
    [string]$Frontend = $(if ([string]::IsNullOrWhiteSpace($env:ARTEMIS_FRONTEND)) { "next" } else { $env:ARTEMIS_FRONTEND.Trim().ToLowerInvariant() })
)

if ($Daemon -and $Stop) {
    Write-Host "   [ERROR] -Daemon and -Stop are mutually exclusive." -ForegroundColor Red
    exit 1
}

$ErrorActionPreference = "Continue"
if ($Frontend -notin @("next")) { throw "ARTEMIS_FRONTEND must be 'next' (Angular has been removed) (got: $Frontend)." }
$env:ARTEMIS_FRONTEND = $Frontend
$FrontendApp = "showcase_next"
$FrontendLabel = "Next.js"
$NodeRequirement = ">= 20.9.0"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

# Ensure modern TLS protocols are enabled for downloads (GitHub releases, nodejs.org, Google repositories)
try {
    [System.Net.ServicePointManager]::SecurityProtocol = [System.Net.ServicePointManager]::SecurityProtocol -bor [System.Net.SecurityProtocolType]::Tls12
} catch {}

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
$RootDir = Split-Path -Parent $ScriptDir
Set-Location $RootDir

# Installed instances use the saved host/port and never rebuild on start/stop.
if (Test-Path -LiteralPath "$RootDir/.artemis-install.json") {
    $installedAction = if ($Stop) { 'stop' } else { 'start' }
    $installedArgs = @($installedAction)
    if ($PSBoundParameters.ContainsKey('Port')) { $installedArgs += @('--port', "$Port") }
    if (-not $NoOpen -and -not $Stop) { $installedArgs += '--open' }
    & "$RootDir/.venv/Scripts/python.exe" "$RootDir/scripts/install_runtime.py" @installedArgs
    exit $LASTEXITCODE
}

Write-Host "======================================================" -ForegroundColor Cyan
Write-Host "       Artemis Autonomous Mobile Agent UI           " -ForegroundColor Cyan
Write-Host "======================================================" -ForegroundColor Cyan
Write-Host ""

function Update-EnvironmentPath {
    $standardDirs = @(
        "$env:LOCALAPPDATA\Microsoft\WinGet\Links",
        "$env:LOCALAPPDATA\Programs\node",
        "$env:USERPROFILE\.local\share\node",
        "$env:LOCALAPPDATA\Programs\scrcpy",
        "$env:USERPROFILE\.local\share\scrcpy",
        "$env:LOCALAPPDATA\Programs\platform-tools",
        "$env:USERPROFILE\.local\share\platform-tools",
        "$env:LOCALAPPDATA\Programs\uv",
        "$env:LOCALAPPDATA\uv",
        "$env:APPDATA\uv",
        "$env:USERPROFILE\.cargo\bin",
        "$env:USERPROFILE\.local\bin",
        "$env:USERPROFILE\scoop\shims",
        "C:\ProgramData\chocolatey\bin",
        "$env:LOCALAPPDATA\Android\Sdk\platform-tools",
        "$env:LOCALAPPDATA\Android\android-sdk\platform-tools",
        "$env:ProgramFiles\Android\platform-tools",
        "${env:ProgramFiles(x86)}\Android\android-sdk\platform-tools",
        "$env:ProgramFiles\nodejs",
        "${env:ProgramFiles(x86)}\nodejs",
        "$env:APPDATA\npm"
    )
    if ($env:CARGO_HOME) { $standardDirs = @("$env:CARGO_HOME\bin") + $standardDirs }
    if ($env:ANDROID_HOME) { $standardDirs += "$env:ANDROID_HOME\platform-tools" }
    if ($env:ANDROID_SDK_ROOT) { $standardDirs += "$env:ANDROID_SDK_ROOT\platform-tools" }
    if ($env:NVM_SYMLINK) { $standardDirs = @($env:NVM_SYMLINK) + $standardDirs }
    if ($env:NVM_HOME) { $standardDirs = @($env:NVM_HOME) + $standardDirs }

    $regPath = [Environment]::GetEnvironmentVariable("Path", "User") + ";" + [Environment]::GetEnvironmentVariable("Path", "Machine")
    $currentPaths = ($env:PATH -split ";") + ($regPath -split ";") + $standardDirs | Where-Object { [string]::IsNullOrWhiteSpace($_) -eq $false -and (Test-Path $_) } | Select-Object -Unique
    $env:PATH = $currentPaths -join ";"

    # Ensure user-space portable tools take absolute priority over system-level outdated versions
    $portableNode = "$env:LOCALAPPDATA\Programs\node"
    if (Test-Path "$portableNode\node.exe") {
        $env:PATH = "$portableNode;$env:PATH"
    }
    $portableScrcpy = "$env:LOCALAPPDATA\Programs\scrcpy"
    if (Test-Path "$portableScrcpy\scrcpy.exe") {
        $env:PATH = "$portableScrcpy;$env:PATH"
    }
    $portablePt = "$env:LOCALAPPDATA\Programs\platform-tools"
    if (Test-Path "$portablePt\adb.exe") {
        $env:PATH = "$portablePt;$env:PATH"
    }
}

function Start-LocalAdbServer {
    if (Test-CommandExists "adb") {
        try {
            $origSocket = $env:ADB_SERVER_SOCKET
            Remove-Item Env:\ADB_SERVER_SOCKET -ErrorAction SilentlyContinue
            & adb start-server 2>$null | Out-Null
            if ($origSocket) { $env:ADB_SERVER_SOCKET = $origSocket }
        } catch {}
    }
}

function Test-CommandExists {
    param([string]$Command)
    $res = Get-Command $Command -ErrorAction SilentlyContinue
    return ($null -ne $res)
}

function Invoke-DownloadFile {
    param(
        [Parameter(Mandatory=$true)][string]$Uri,
        [Parameter(Mandatory=$true)][string]$OutFile,
        [int]$TimeoutSec = 45
    )
    if (Test-Path $OutFile) {
        Remove-Item -Path $OutFile -Force -ErrorAction SilentlyContinue
    }

    # 1. Try Windows built-in curl.exe first (available in Win 10 1803+ and Win 11)
    if (Test-CommandExists "curl.exe") {
        try {
            & curl.exe -f -sSL --connect-timeout 5 --max-time $TimeoutSec "$Uri" -o "$OutFile" 2>$null
            if ($LASTEXITCODE -eq 0 -and (Test-Path $OutFile) -and ((Get-Item $OutFile).Length -gt 0)) {
                return $true
            }
        } catch {}
        if (Test-Path $OutFile) {
            Remove-Item -Path $OutFile -Force -ErrorAction SilentlyContinue
        }
    }

    # 2. Fallback to Invoke-WebRequest (suppressing progress bar to eliminate PowerShell buffer hangs)
    try {
        $prevProgress = $ProgressPreference
        $ProgressPreference = 'SilentlyContinue'
        Invoke-WebRequest -Uri $Uri -OutFile $OutFile -TimeoutSec $TimeoutSec -UseBasicParsing -ErrorAction Stop
        $ProgressPreference = $prevProgress
        if ((Test-Path $OutFile) -and ((Get-Item $OutFile).Length -gt 0)) {
            return $true
        }
    } catch {
        $ProgressPreference = $prevProgress
    }

    if (Test-Path $OutFile) {
        Remove-Item -Path $OutFile -Force -ErrorAction SilentlyContinue
    }
    return $false
}

function Install-PortablePlatformTools {
    $ptDir = "$env:LOCALAPPDATA\Programs\platform-tools"
    if (Test-Path "$ptDir\adb.exe") {
        $env:PATH = "$ptDir;$env:PATH"
        return $true
    }
    Write-Host "   [INFO] Installing Android platform-tools (adb) in user space..." -ForegroundColor Cyan
    try {
        $zipPath = "$env:TEMP\platform-tools-windows.zip"
        if (Invoke-DownloadFile -Uri "https://dl.google.com/android/repository/platform-tools-latest-windows.zip" -OutFile $zipPath -TimeoutSec 60) {
            New-Item -ItemType Directory -Path "$env:LOCALAPPDATA\Programs" -Force | Out-Null
            Expand-Archive -Path $zipPath -DestinationPath "$env:LOCALAPPDATA\Programs" -Force
            Remove-Item $zipPath -Force -ErrorAction SilentlyContinue
            if (Test-Path "$ptDir\adb.exe") {
                $env:PATH = "$ptDir;$env:PATH"
                Write-Host "   [OK] adb installed in user space." -ForegroundColor Green
                return $true
            }
        }
    } catch {
        Write-Host "   [WARN] Failed to install portable platform-tools: $_" -ForegroundColor DarkYellow
    }
    return $false
}

function Install-PortableScrcpy {
    $scrcpyDir = "$env:LOCALAPPDATA\Programs\scrcpy"
    if (Test-Path "$scrcpyDir\scrcpy.exe") {
        $env:PATH = "$scrcpyDir;$env:PATH"
        return $true
    }
    # Check if nested from an earlier run and heal
    $nested = Get-ChildItem -Path $scrcpyDir -Directory -Filter "scrcpy*" -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($nested -and (Test-Path "$($nested.FullName)\scrcpy.exe")) {
        Copy-Item -Path "$($nested.FullName)\*" -Destination $scrcpyDir -Recurse -Force
        Remove-Item -Path $nested.FullName -Recurse -Force -ErrorAction SilentlyContinue
        if (Test-Path "$scrcpyDir\scrcpy.exe") {
            $env:PATH = "$scrcpyDir;$env:PATH"
            return $true
        }
    }

    Write-Host "   [INFO] Installing portable scrcpy in user space..." -ForegroundColor Cyan
    try {
        $zipPath = "$env:TEMP\scrcpy-win64.zip"
        if (Invoke-DownloadFile -Uri "https://github.com/Genymobile/scrcpy/releases/download/v4.1/scrcpy-win64-v4.1.zip" -OutFile $zipPath -TimeoutSec 60) {
            $extractDir = "$env:TEMP\scrcpy_extract"
            if (Test-Path $extractDir) { Remove-Item $extractDir -Recurse -Force -ErrorAction SilentlyContinue }
            New-Item -ItemType Directory -Path $extractDir -Force | Out-Null
            Expand-Archive -Path $zipPath -DestinationPath $extractDir -Force
            $extractedFolder = Get-ChildItem -Path $extractDir -Directory | Select-Object -First 1
            if ($extractedFolder) {
                if (-not (Test-Path $scrcpyDir)) {
                    New-Item -ItemType Directory -Path $scrcpyDir -Force | Out-Null
                }
                Copy-Item -Path "$($extractedFolder.FullName)\*" -Destination $scrcpyDir -Recurse -Force
            }
            Remove-Item $zipPath -Force -ErrorAction SilentlyContinue
            Remove-Item $extractDir -Recurse -Force -ErrorAction SilentlyContinue
            if (Test-Path "$scrcpyDir\scrcpy.exe") {
                $env:PATH = "$scrcpyDir;$env:PATH"
                Write-Host "   [OK] Portable scrcpy installed in user space." -ForegroundColor Green
                return $true
            }
        }
    } catch {
        Write-Host "   [WARN] Failed to install portable scrcpy: $_" -ForegroundColor DarkYellow
    }
    return $false
}

function Test-NodeCompatible {
    if (-not (Test-CommandExists "node") -or (-not (Test-CommandExists "npm") -and -not (Test-CommandExists "npm.cmd"))) { return $false }
    try {
        $version = [version]((& node -v 2>$null).ToString().Trim().TrimStart('v'))
        return $version -ge [version]"20.9.0"
    } catch { return $false }
    return $false
}

function Install-PortableNode {
    $nodeDir = "$env:LOCALAPPDATA\Programs\node"
    if (Test-Path "$nodeDir\node.exe") {
        $env:PATH = "$nodeDir;$env:PATH"
        if (Test-NodeCompatible) {
            return $true
        }
    }
    # Check if nested from an earlier run and heal
    $nested = Get-ChildItem -Path $nodeDir -Directory -Filter "node-*" -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($nested -and (Test-Path "$($nested.FullName)\node.exe")) {
        Copy-Item -Path "$($nested.FullName)\*" -Destination $nodeDir -Recurse -Force
        Remove-Item -Path $nested.FullName -Recurse -Force -ErrorAction SilentlyContinue
        if (Test-Path "$nodeDir\node.exe") {
            $env:PATH = "$nodeDir;$env:PATH"
            if (Test-NodeCompatible) {
                return $true
            }
        }
    }

    Write-Host "   [INFO] Installing portable Node.js LTS (v22.23.2) in user space..." -ForegroundColor Cyan
    try {
        $nodeVer = "v22.23.2"
        $arch = if ([System.Environment]::Is64BitOperatingSystem) {
            if ($env:PROCESSOR_ARCHITECTURE -match "ARM64") { "arm64" } else { "x64" }
        } else { "x64" }
        $zipPath = "$env:TEMP\node-$nodeVer-win-$arch.zip"
        if (Invoke-DownloadFile -Uri "https://nodejs.org/dist/$nodeVer/node-$nodeVer-win-$arch.zip" -OutFile $zipPath -TimeoutSec 60) {
            $extractDir = "$env:TEMP\node_extract"
            if (Test-Path $extractDir) { Remove-Item $extractDir -Recurse -Force -ErrorAction SilentlyContinue }
            New-Item -ItemType Directory -Path $extractDir -Force | Out-Null
            Expand-Archive -Path $zipPath -DestinationPath $extractDir -Force
            $extractedFolder = Get-ChildItem -Path $extractDir -Directory | Select-Object -First 1
            if ($extractedFolder) {
                if (-not (Test-Path $nodeDir)) {
                    New-Item -ItemType Directory -Path $nodeDir -Force | Out-Null
                }
                Copy-Item -Path "$($extractedFolder.FullName)\*" -Destination $nodeDir -Recurse -Force
            }
            Remove-Item $zipPath -Force -ErrorAction SilentlyContinue
            Remove-Item $extractDir -Recurse -Force -ErrorAction SilentlyContinue
            if (Test-Path "$nodeDir\node.exe") {
                $env:PATH = "$nodeDir;$env:PATH"
                Write-Host "   [OK] Portable Node.js $nodeVer installed in user space." -ForegroundColor Green
                return $true
            }
        }
    } catch {
        Write-Host "   [WARN] Failed to install portable Node.js: $_" -ForegroundColor DarkYellow
    }
    return $false
}

# 1. Refresh PATH with standard toolchain paths
Update-EnvironmentPath

# 2. Check or install uv
if (-not (Test-CommandExists "uv")) {
    Write-Host "   [INFO] uv not found. Installing Astral uv..." -ForegroundColor Yellow
    try {
        Invoke-Expression (Invoke-RestMethod -Uri "https://astral.sh/uv/install.ps1")
    } catch {
        powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
    }
    Update-EnvironmentPath
}

if (-not (Test-CommandExists "uv")) {
    Write-Host "   [ERROR] Astral 'uv' package manager could not be installed or found in PATH." -ForegroundColor Red
    Write-Host "   Please install uv manually from https://astral.sh/ or run:" -ForegroundColor Yellow
    Write-Host "      powershell -c ""irm https://astral.sh/uv/install.ps1 | iex""" -ForegroundColor Cyan
    exit 1
}

# -Stop: just shut down the verified Artemis daemon on -Port and exit, no
# toolchain checks, no dependency sync, no frontend build.
if ($Stop) {
    Write-Host "   [INFO] Stopping Artemis server on port $Port..." -ForegroundColor Yellow
    uv run python -m artemis stop --port $Port
    exit $LASTEXITCODE
}

# 3. Check and try installing missing system toolchains (ADB, FFmpeg, scrcpy)
$missingCore = @()
if (-not (Test-CommandExists "adb")) { $missingCore += "adb" }
if (-not (Test-CommandExists "ffmpeg")) { $missingCore += "ffmpeg" }
if (-not (Test-CommandExists "scrcpy")) { $missingCore += "scrcpy" }

if ($missingCore.Count -gt 0) {
    $useWinGet = $false
    if (Test-CommandExists "winget") {
        if ([Console]::IsInputRedirected -eq $false) {
            Write-Host "   [INFO] Missing components detected: $($missingCore -join ', ')." -ForegroundColor Cyan
            $ans = Read-Host "      Install system packages via WinGet? [Y/n]"
            if ($ans -eq "" -or $ans -match "^[Yy]") {
                $useWinGet = $true
            }
        } else {
            $useWinGet = $true
        }
    }

    if ($useWinGet) {
        Write-Host "   [INFO] Auto-installing missing components ($($missingCore -join ', '))..." -ForegroundColor DarkYellow
        if ($missingCore -contains "adb") {
            winget install --id Google.PlatformTools -e --accept-source-agreements --accept-package-agreements --silent 2>$null | Out-Null
        }
        if ($missingCore -contains "ffmpeg") {
            winget install --id Gyan.FFmpeg -e --accept-source-agreements --accept-package-agreements --silent 2>$null | Out-Null
        }
        if ($missingCore -contains "scrcpy") {
            winget install --id Genymobile.scrcpy -e --accept-source-agreements --accept-package-agreements --silent 2>$null | Out-Null
        }
        Update-EnvironmentPath
    }

    # Zero-admin user-space fallback for adb and scrcpy if still missing
    if (-not (Test-CommandExists "adb")) {
        Install-PortablePlatformTools
    }
    if (-not (Test-CommandExists "scrcpy")) {
        Install-PortableScrcpy
    }
}

# Ensure local ADB daemon is warm & listening so probes do not hit 'Connection refused'
Start-LocalAdbServer

# 4. Check or initialize .env
if (-not (Test-Path ".env")) {
    if (Test-Path ".env.example") {
        Copy-Item ".env.example" ".env"
        Write-Host "   [OK] Initialized .env configuration file." -ForegroundColor Green
    } else {
        New-Item -ItemType File -Path ".env" | Out-Null
    }
}

# 5. Synchronize dependencies
Write-Host "   [INFO] Synchronizing Python runtime and project dependencies..." -ForegroundColor Cyan
uv sync --locked --quiet

# Build the selected frontend when its artifact is missing or stale
Write-Host "`nChecking selected frontend build ($FrontendLabel)..." -ForegroundColor Yellow
$FrontendDir = Join-Path $RootDir "apps\$FrontendApp"
$FrontendCandidates = @((Join-Path $FrontendDir "out\index.html"))
$InputRoots = @("src", "public")
$InputFiles = @("package.json", "package-lock.json", "next.config.ts", "postcss.config.mjs", "tsconfig.json")
$ExistingFrontendIndex = $FrontendCandidates | Where-Object { Test-Path $_ } | Select-Object -First 1
$FrontendBuildRequired = -not $ExistingFrontendIndex
if ($ExistingFrontendIndex) {
    $BuiltAt = (Get-Item $ExistingFrontendIndex).LastWriteTimeUtc
    $FrontendInputs = foreach ($relative in $InputRoots) { $path = Join-Path $FrontendDir $relative; if (Test-Path $path) { Get-ChildItem $path -Recurse -File -ErrorAction SilentlyContinue } }
    $FrontendInputs += foreach ($relative in $InputFiles) { $path = Join-Path $FrontendDir $relative; if (Test-Path $path) { Get-Item $path } }
    $FrontendBuildRequired = $null -ne ($FrontendInputs | Where-Object { $_.LastWriteTimeUtc -gt $BuiltAt } | Select-Object -First 1)
}
if ($FrontendBuildRequired) {
    if (-not (Test-NodeCompatible) -and (Test-CommandExists "nvm")) { & nvm use 22 | Out-Null; Update-EnvironmentPath }
    if (-not (Test-NodeCompatible)) { Install-PortableNode | Out-Null; Update-EnvironmentPath }
    if (-not (Test-NodeCompatible)) { Write-Error "Cannot build ${FrontendLabel}: Node.js $NodeRequirement and npm are required."; exit 1 }
    $npmExec = if (Test-CommandExists "npm.cmd") { "npm.cmd" } else { "npm" }
    Push-Location $FrontendDir
    try {
        Write-Host "   [INFO] Installing $FrontendLabel dependencies..." -ForegroundColor Cyan
        if (Test-Path "package-lock.json") { & $npmExec ci --no-audit --no-fund } else { & $npmExec install --no-audit --no-fund }
        if ($LASTEXITCODE -ne 0) { throw "npm dependency install failed with exit code $LASTEXITCODE" }
        Write-Host "   [INFO] Building $FrontendLabel frontend application..." -ForegroundColor Cyan
        & $npmExec run build
        if ($LASTEXITCODE -ne 0) { throw "$FrontendLabel build failed with exit code $LASTEXITCODE" }
    } catch {
        Write-Error "$FrontendLabel frontend build failed; the previous artifact, if any, was not removed. $_"
        exit 1
    } finally { Pop-Location }
    $BuiltFrontendIndex = $FrontendCandidates | Where-Object { Test-Path $_ } | Select-Object -First 1
    if (-not $BuiltFrontendIndex) { Write-Error "$FrontendLabel build completed but expected artifact was not found: $($FrontendCandidates -join ', ')"; exit 1 }
    Write-Host "   [OK] $FrontendLabel frontend compiled successfully." -ForegroundColor Green
} else { Write-Host "   [OK] Selected $FrontendLabel frontend artifact is current." -ForegroundColor Green }

# 7. Optionally configure MCP for detected AI IDEs
Write-Host ""
Write-Host "   [INFO] Would you like to configure ARTEMIS MCP & testing rules for your AI IDEs?" -ForegroundColor Cyan
Write-Host "      (Supported: Antigravity, Cursor, Claude Code/Desktop, Codex, OpenClaw, Windsurf)"
$installMcp = "Y"
if ([Console]::IsInputRedirected -eq $false) {
    $response = Read-Host "      Install MCP configuration & rules now? [Y/n]"
    if ($response -ne "") {
        $installMcp = $response
    }
} else {
    $installMcp = "N"
}

if ($installMcp -match "^[Yy]") {
    Write-Host "   Installing MCP server configuration & testing rules..." -ForegroundColor Cyan
    uv run python -m artemis mcp --install all
    if ($LASTEXITCODE -eq 0) {
        Write-Host "   [OK] MCP configuration and rules installed successfully." -ForegroundColor Green
        Write-Host "   [TIP] You can update or re-install anytime with: uv run artemis mcp --install all" -ForegroundColor Cyan
    } else {
        Write-Host "   [WARN] MCP installation failed. Review the error above and retry with: uv run artemis mcp --install all" -ForegroundColor Yellow
    }
} else {
    Write-Host "   [SKIP] You can install MCP anytime later with: uv run artemis mcp --install all" -ForegroundColor Yellow
}
Write-Host ""

# 8. Launch unified Showcase UI & open browser (or detach as a background daemon)
# Ensure local ADB daemon is warm & listening
Start-LocalAdbServer

# Launch via `python -m artemis` (not the `artemis.exe` console-script shim) so the
# long-running server never locks .venv\Scripts\artemis.exe against `uv sync` reinstalls.
if ($Daemon) {
    Write-Host "   [INFO] Launching Artemis Showcase UI & Admin Console as a background daemon..." -ForegroundColor Green
    $daemonArgs = @("-m", "artemis", "restart", "--port", "$Port", "--daemon")
    $daemonArgs += if ($NoOpen) { "--no-open" } else { "--open" }
    # Launch the venv's pythonw.exe directly (not `python.exe`, and not
    # through `uv run`). Two layers were tried and both still leaked a
    # visible console on this launch chain:
    #   - `uv run python -m artemis restart --daemon`: `uv` re-execs the
    #     Python process through its own child launcher, which opens a
    #     fresh console for it regardless of `uv`'s own window state.
    #   - venv's `python.exe` directly: on a uv-managed venv, that is a thin
    #     stub that re-execs the real base CPython interpreter, and that
    #     redirect does not propagate CREATE_NO_WINDOW either.
    # `pythonw.exe` (the windowless/GUI-subsystem build) does not have this
    # problem at any layer, because there is no console subsystem to ever
    # attach one to, in the stub or in the base interpreter it re-execs.
    # uv sync already ran earlier in this script, so the venv is current.
    $venvPythonW = Join-Path $RootDir ".venv\Scripts\pythonw.exe"
    if (-not (Test-Path $venvPythonW)) {
        Write-Host "   [ERROR] venv pythonw.exe not found at $venvPythonW. Run 'uv sync' first." -ForegroundColor Red
        exit 1
    }
    # This CLI call only verifies the port and spawns the actual detached
    # daemon (apps.admin_console.server, itself already CREATE_NO_WINDOW),
    # then exits. Its exit code is not reliable under pythonw.exe (Rich/Typer
    # console output can fail with no console attached), so success is
    # judged solely by polling the port below, not by $LASTEXITCODE here.
    Start-Process -FilePath $venvPythonW -ArgumentList $daemonArgs -WindowStyle Hidden -WorkingDirectory $RootDir
    $daemonUp = $false
    for ($i = 0; $i -lt 60; $i++) {
        Start-Sleep -Milliseconds 1000
        $test = Test-NetConnection -ComputerName "127.0.0.1" -Port $Port -InformationLevel Quiet -WarningAction SilentlyContinue
        if ($test) { $daemonUp = $true; break }
    }
    if ($daemonUp) {
        $LASTEXITCODE = 0
        Write-Host "   [OK] Artemis server is running in the background." -ForegroundColor Green
        Write-Host "   Web UI: http://localhost:$Port" -ForegroundColor Cyan
        Write-Host "   Check status anytime with: uv run python -m artemis status --port $Port" -ForegroundColor Cyan
        Write-Host "   Stop it with: .\start.bat -Stop -Port $Port" -ForegroundColor Cyan
    } else {
        $LASTEXITCODE = 1
        Write-Host "   [ERROR] Background daemon did not come up on port $Port within 60s." -ForegroundColor Red
        Write-Host "   Check logs under: $env:LOCALAPPDATA\Artemis\logs\daemon-$Port.log" -ForegroundColor Yellow
    }
} else {
    Write-Host "   [INFO] Launching Artemis Showcase UI & Admin Console..." -ForegroundColor Green
    if ($NoOpen) {
        uv run python -m artemis ui --port $Port --no-open
    } else {
        uv run python -m artemis ui --port $Port --open
    }
}

if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}
