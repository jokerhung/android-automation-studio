# Internet bootstrap for Windows PowerShell 5.1 and PowerShell 7. ASCII only.
[CmdletBinding()]
param(
    [string]$InstallDir = "$env:LOCALAPPDATA\Programs\Artemis",
    [string]$Port,
    [switch]$LocalOnly,
    [switch]$NonInteractive,
    [switch]$Open,
    [switch]$Help
)
$ErrorActionPreference = 'Stop'
if ($Help) {
    Write-Host 'Usage: install.ps1 [-InstallDir PATH] [-Port 1..65535] [-LocalOnly] [-NonInteractive] [-Open]'
    Write-Host 'Default: %LOCALAPPDATA%\Programs\Artemis, port 8009, LAN bind, background process.'
    return
}
if ($Port -and ($Port -notmatch '^\d{1,5}$' -or [int]$Port -lt 1 -or [int]$Port -gt 65535)) {
    Write-Error 'Port must be 1..65535.' -ErrorAction Continue
    exit 2
}
if ([string]::IsNullOrWhiteSpace($InstallDir)) { exit 2 }
$installerCode = 2
$lockHandle = $null
$stage = $null
try {
    $machineArch = if ($env:PROCESSOR_ARCHITEW6432) { $env:PROCESSOR_ARCHITEW6432 } else { $env:PROCESSOR_ARCHITECTURE }
    if ($env:OS -ne 'Windows_NT' -or $machineArch -ne 'AMD64' -or [Environment]::OSVersion.Version.Build -lt 22000) {
        throw 'Supported Windows environment: Windows 11 x64.'
    }
    [Net.ServicePointManager]::SecurityProtocol = [Net.ServicePointManager]::SecurityProtocol -bor [Net.SecurityProtocolType]::Tls12
    $installerCode = 3
    $InstallDir = [IO.Path]::GetFullPath($InstallDir).TrimEnd('\')
    $parent = Split-Path -Parent $InstallDir
    New-Item -ItemType Directory -Force -Path $parent | Out-Null
    # FileShare.None provides an OS lock released automatically on interruption.
    $lockHandle = [IO.File]::Open("$InstallDir.install-lock", 'OpenOrCreate', 'ReadWrite', 'None')
    Write-Host '[OK] 1/6 Environment: Windows/x64'
    Write-Host 'Source: jokerhung/android-automation-studio @ nextjs'
    Write-Host "Directory: $InstallDir"
    $stage = Join-Path $parent ('.artemis-stage-' + [guid]::NewGuid().ToString('N'))
    New-Item -ItemType Directory -Path $stage | Out-Null
    if ((Test-Path -LiteralPath "$InstallDir/.artemis-install.json") -and (Test-Path -LiteralPath "$InstallDir/scripts/install_runtime.py")) {
        Write-Host '[GIU] 2/6 Keeping existing source and configuration'
    } else {
        if ((Test-Path -LiteralPath $InstallDir) -and ((-not (Test-Path -LiteralPath $InstallDir -PathType Container)) -or @(Get-ChildItem -LiteralPath $InstallDir -Force).Count -gt 0)) {
            throw 'Destination is not a recognized installation. Choose -InstallDir PATH.'
        }
        $installerCode = 4
        Write-Host '[DANG] 2/6 Downloading source snapshot'
        # This function is self-contained: source helpers do not exist yet.
        function Get-BootstrapFile([string]$Uri, [string]$Destination) {
            for ($attempt = 1; $attempt -le 3; $attempt++) {
                try {
                    Invoke-WebRequest -UseBasicParsing -Uri $Uri -OutFile $Destination -TimeoutSec 600
                    return
                } catch {
                    if ($attempt -eq 3) { throw }
                    Start-Sleep -Seconds (2 * $attempt)
                }
            }
        }
        Get-BootstrapFile 'https://codeload.github.com/jokerhung/android-automation-studio/zip/refs/heads/nextjs' "$stage/source.zip"
        Expand-Archive -LiteralPath "$stage/source.zip" -DestinationPath "$stage/source"
        $source = @(Get-ChildItem -LiteralPath "$stage/source" -Directory)
        if ($source.Count -ne 1) { throw 'Invalid source archive.' }
        $sourceRoot = $source[0].FullName
        foreach ($required in @('pyproject.toml', 'uv.lock', 'artemis', 'apps/showcase_next/package-lock.json', 'packages/artemis-client', 'config/artemis.jsonc', 'scripts/install_runtime.py', 'scripts/bootstrap_common.ps1')) {
            if (-not (Test-Path -LiteralPath (Join-Path $sourceRoot $required))) { throw "Incomplete archive: $required" }
        }
        '{"schema":1,"source":"jokerhung/android-automation-studio","ref":"nextjs","stage":"source"}' | Set-Content -LiteralPath "$sourceRoot/.artemis-install.json" -Encoding ASCII
        if (Test-Path -LiteralPath $InstallDir) { Remove-Item -LiteralPath $InstallDir }
        Move-Item -LiteralPath $sourceRoot -Destination $InstallDir
    }
    $installerCode = 4
    . "$InstallDir/scripts/bootstrap_common.ps1"
    $uvPath = Initialize-BootstrapUv -Root $InstallDir -Temporary $stage
    $installerCode = 5
    $env:PYTHONUTF8 = '1'
    $env:ARTEMIS_FRONTEND = 'next'
    Push-Location -LiteralPath $InstallDir
    try {
        & $uvPath python install 3.12
        if ($LASTEXITCODE -ne 0) { throw 'Managed Python 3.12 installation failed.' }
        $runtimeArgs = @('install', '--uv', $uvPath)
        if ($Port) { $runtimeArgs += @('--port', $Port) }
        if ($LocalOnly) { $runtimeArgs += '--local-only' }
        if ($NonInteractive) { $runtimeArgs += '--non-interactive' }
        if ($Open) { $runtimeArgs += '--open' }
        & $uvPath run --no-project --python 3.12 python scripts/install_runtime.py @runtimeArgs
        $installerCode = $LASTEXITCODE
        if ($installerCode -ne 0) { throw "Runtime installer failed (code $installerCode)." }
    } finally { Pop-Location }
} catch {
    Write-Host "[LOI] Installation stopped (code $installerCode): $($_.Exception.Message)"
    Write-Host "Existing servers were not stopped. Retry the same command. Log when available: $InstallDir/logs/install.log"
} finally {
    if ($lockHandle) { $lockHandle.Dispose() }
    if ($stage) {
        # Only remove the unique staging directory created under the checked parent.
        $resolvedStage = [IO.Path]::GetFullPath($stage)
        if ((Split-Path -Parent $resolvedStage) -eq $parent -and (Split-Path -Leaf $resolvedStage) -like '.artemis-stage-*') {
            Remove-Item -LiteralPath $resolvedStage -Recurse -Force -ErrorAction SilentlyContinue
        }
    }
}
if ($installerCode -ne 0) { exit $installerCode }
