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

<#
.SYNOPSIS
    Force-rebuild the Next.js Showcase UI and restart the unified Artemis
    API + GUI server (apps/admin_console/server.py, one FastAPI/uvicorn
    process that serves both the REST API and the static GUI export).

.DESCRIPTION
    Unlike start.ps1 (which only rebuilds the frontend when its sources are
    newer than the last build), this script always rebuilds: `npm ci`/`install`
    then `npm run build` under apps/showcase_next, producing a fresh
    apps/showcase_next/out/ static export.

    It then (re)starts the server through Artemis's own identity-verified
    lifecycle commands (never by killing a PID directly):
      - Foreground (default): `artemis ui --restart` — stops any verified
        instance on -Port, then runs attached to this console (Ctrl+C stops it).
      - -Daemon: `artemis restart --daemon` — stops any verified instance,
        then launches a new one detached in the background. Use -Stop later
        to shut it down.

    -Stop skips the rebuild entirely and just calls `artemis stop` to shut
    down the verified daemon on -Port.

.PARAMETER Port
    Port the unified server binds to. Defaults to 8009 (matches start.ps1).

.PARAMETER Daemon
    Rebuild, then start the server detached in the background instead of
    attached to this console. Mutually exclusive with -Stop.

.PARAMETER Stop
    Skip the rebuild and stop the running server on -Port. Mutually
    exclusive with -Daemon.

.PARAMETER NoOpen
    Skip auto-opening the default browser once the server is ready. Ignored
    with -Stop.

.EXAMPLE
    .\scripts\rebuild.ps1
    Rebuild the GUI and run the server in this console (foreground).

.EXAMPLE
    .\scripts\rebuild.ps1 -Daemon
    Rebuild the GUI and run the server detached in the background.

.EXAMPLE
    .\scripts\rebuild.ps1 -Stop
    Stop the background (or foreground) server on the default port, no rebuild.
#>

[CmdletBinding()]
param(
    [ValidateRange(1, 65535)]
    [int]$Port = 8009,
    [switch]$Daemon = $false,
    [switch]$Stop = $false,
    [switch]$NoOpen = $false
)

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

if ($Daemon -and $Stop) {
    Write-Host "   [ERROR] -Daemon and -Stop are mutually exclusive." -ForegroundColor Red
    exit 1
}

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
$RootDir = Split-Path -Parent $ScriptDir
Set-Location $RootDir

$FrontendApp = "showcase_next"
$FrontendLabel = "Next.js"
$FrontendDir = Join-Path $RootDir "apps\$FrontendApp"

function Test-CommandExists {
    param([string]$Command)
    return $null -ne (Get-Command $Command -ErrorAction SilentlyContinue)
}

function Test-NodeCompatible {
    if (-not (Test-CommandExists "node")) { return $false }
    if (-not (Test-CommandExists "npm") -and -not (Test-CommandExists "npm.cmd")) { return $false }
    try {
        $version = [version]((& node -v 2>$null).ToString().Trim().TrimStart('v'))
        return $version -ge [version]"20.9.0"
    } catch {
        return $false
    }
}

if (-not (Test-CommandExists "uv")) {
    Write-Host "   [ERROR] 'uv' was not found in PATH. Run start.bat once first, or install uv from https://astral.sh/." -ForegroundColor Red
    exit 1
}

# --- Stop-only path: no rebuild, just shut down the verified daemon. -------
if ($Stop) {
    Write-Host "======================================================" -ForegroundColor Cyan
    Write-Host "   Artemis - Stop (API + GUI)                         " -ForegroundColor Cyan
    Write-Host "======================================================" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "   [INFO] Stopping Artemis server on port $Port..." -ForegroundColor Yellow
    uv run python -m artemis stop --port $Port
    exit $LASTEXITCODE
}

Write-Host "======================================================" -ForegroundColor Cyan
Write-Host "   Artemis - Rebuild & Restart (API + GUI)             " -ForegroundColor Cyan
Write-Host "======================================================" -ForegroundColor Cyan
Write-Host ""

if (-not (Test-NodeCompatible)) {
    Write-Host "   [ERROR] Node.js >= 20.9.0 and npm are required to rebuild $FrontendLabel." -ForegroundColor Red
    Write-Host "   Run start.bat once to auto-provision a portable Node.js, then retry." -ForegroundColor Yellow
    exit 1
}

$npmExec = if (Test-CommandExists "npm.cmd") { "npm.cmd" } else { "npm" }

# 1. Always rebuild the frontend, regardless of staleness.
Write-Host "`n[1/2] Rebuilding $FrontendLabel Showcase UI..." -ForegroundColor Yellow
Push-Location $FrontendDir
try {
    Write-Host "   [INFO] Installing $FrontendLabel dependencies..." -ForegroundColor Cyan
    if (Test-Path "package-lock.json") {
        & $npmExec ci --no-audit --no-fund
    } else {
        & $npmExec install --no-audit --no-fund
    }
    if ($LASTEXITCODE -ne 0) { throw "npm dependency install failed with exit code $LASTEXITCODE" }

    Write-Host "   [INFO] Building $FrontendLabel frontend application..." -ForegroundColor Cyan
    & $npmExec run build
    if ($LASTEXITCODE -ne 0) { throw "$FrontendLabel build failed with exit code $LASTEXITCODE" }
} catch {
    Write-Error "$FrontendLabel frontend rebuild failed: $_"
    exit 1
} finally {
    Pop-Location
}

$BuiltIndex = Join-Path $FrontendDir "out\index.html"
if (-not (Test-Path $BuiltIndex)) {
    Write-Error "$FrontendLabel build completed but expected artifact was not found: $BuiltIndex"
    exit 1
}
Write-Host "   [OK] $FrontendLabel frontend rebuilt successfully." -ForegroundColor Green

# 2. (Re)start the unified API + GUI server through Artemis's own
#    identity-verified lifecycle commands (never by killing a PID directly).
if ($Daemon) {
    Write-Host "`n[2/2] Restarting Artemis API + GUI server on port $Port (background daemon)..." -ForegroundColor Yellow
    if ($NoOpen) {
        uv run python -m artemis restart --port $Port --daemon --no-open
    } else {
        uv run python -m artemis restart --port $Port --daemon --open
    }
} else {
    Write-Host "`n[2/2] Restarting Artemis API + GUI server on port $Port (foreground)..." -ForegroundColor Yellow
    if ($NoOpen) {
        uv run python -m artemis ui --port $Port --restart --no-open
    } else {
        uv run python -m artemis ui --port $Port --restart --open
    }
}

if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}
