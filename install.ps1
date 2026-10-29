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
$previousErrorPreference = $ErrorActionPreference
if ($Help) {
    Write-Host 'Usage: install.ps1 [-InstallDir PATH] [-Port 1..65535] [-LocalOnly] [-NonInteractive] [-Open]'
    Write-Host 'Default: %LOCALAPPDATA%\Programs\Artemis, port 8009, LAN bind, background process.'
    return
}
if ($Port -and ($Port -notmatch '^\d{1,5}$' -or [int]$Port -lt 1 -or [int]$Port -gt 65535)) {
    $global:LASTEXITCODE = 2
    if ($PSCommandPath) { exit 2 }
    throw 'Port must be 1..65535 (code 2).'
}
if ([string]::IsNullOrWhiteSpace($InstallDir)) {
    $global:LASTEXITCODE = 2
    if ($PSCommandPath) { exit 2 }
    throw 'InstallDir cannot be empty (code 2).'
}
$previousTls = [Net.ServicePointManager]::SecurityProtocol
$previousPythonUtf8 = $env:PYTHONUTF8
$previousFrontend = $env:ARTEMIS_FRONTEND
$installerCode = 2
$lockHandle = $null
$stage = $null
$ErrorActionPreference = 'Stop'
try {
    $machineArch = if ($env:PROCESSOR_ARCHITEW6432) { $env:PROCESSOR_ARCHITEW6432 } else { $env:PROCESSOR_ARCHITECTURE }
    if ($env:OS -ne 'Windows_NT' -or $machineArch -ne 'AMD64' -or [Environment]::OSVersion.Version.Build -lt 22000) {
        throw 'Supported Windows environment: Windows 11 x64.'
    }
    [Net.ServicePointManager]::SecurityProtocol = [Net.ServicePointManager]::SecurityProtocol -bor [Net.SecurityProtocolType]::Tls12
    $installerCode = 3
    $InstallDir = [IO.Path]::GetFullPath($InstallDir).TrimEnd('\')
    $parent = Split-Path -Parent $InstallDir
    if (-not $parent) { throw 'Cannot install into a filesystem root.' }
    if ((Test-Path -LiteralPath $InstallDir) -and ((Get-Item -LiteralPath $InstallDir -Force).Attributes -band [IO.FileAttributes]::ReparsePoint)) { throw 'Destination cannot be a link.' }
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
        Add-Type -AssemblyName System.IO.Compression.FileSystem
        $zip = [IO.Compression.ZipFile]::OpenRead("$stage/source.zip")
        try {
            $archiveRoot = $null
            foreach ($entry in $zip.Entries) {
                $name = $entry.FullName
                if ($name -match '(^/|\\|:|(^|/)\.\.?(/|$))' -or -not $name) { throw 'Unsafe archive path.' }
                $top = ($name -split '/')[0]
                if (-not $archiveRoot) { $archiveRoot = $top }
                if ($top -ne $archiveRoot) { throw 'Multiple archive roots.' }
                $kind = ($entry.ExternalAttributes -shr 16) -band 0xF000
                if ($kind -notin @(0, 0x8000, 0x4000) -or ($entry.ExternalAttributes -band 0x400)) { throw 'Archive links/special files are not allowed.' }
            }
            if (-not $archiveRoot) { throw 'Empty archive.' }
        } finally { $zip.Dispose() }
        $archiveSha = (Get-FileHash -LiteralPath "$stage/source.zip" -Algorithm SHA256).Hash.ToLowerInvariant()
        Write-Host "Archive SHA-256: $archiveSha"
        Expand-Archive -LiteralPath "$stage/source.zip" -DestinationPath "$stage/source"
        $source = @(Get-ChildItem -LiteralPath "$stage/source" -Directory)
        if ($source.Count -ne 1) { throw 'Invalid source archive.' }
        $sourceRoot = $source[0].FullName
        foreach ($required in @('install.sh', 'install.ps1', '.env.example', 'pyproject.toml', 'uv.lock', 'artemis', 'apps/admin_console', 'apps/showcase_next/package.json', 'apps/showcase_next/package-lock.json', 'apps/showcase_next/next.config.ts', 'apps/showcase_next/src', 'packages/artemis-client/pyproject.toml', 'config/artemis.jsonc', 'scripts/install_runtime.py', 'scripts/bootstrap_common.ps1')) {
            if (-not (Test-Path -LiteralPath (Join-Path $sourceRoot $required))) { throw "Incomplete archive: $required" }
        }
        if (-not (Select-String -LiteralPath "$sourceRoot/scripts/install_runtime.py" -Pattern '^BOOTSTRAP_VERSION = 1$' -Quiet)) { throw 'Incompatible snapshot bootstrap contract.' }
        @{schema=1; source='jokerhung/android-automation-studio'; ref='nextjs'; bootstrap_version=1; archive_sha256=$archiveSha; archive_url='https://codeload.github.com/jokerhung/android-automation-studio/zip/refs/heads/nextjs'; stage='source_ready'} | ConvertTo-Json | Set-Content -LiteralPath "$sourceRoot/.artemis-install.json" -Encoding ASCII
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
        $pythonDownload = Start-Process -FilePath $uvPath -ArgumentList @('python', 'install', '3.12') -WindowStyle Hidden -PassThru
        $null = $pythonDownload.Handle
        if (-not $pythonDownload.WaitForExit(1800000)) {
            & taskkill /PID $pythonDownload.Id /T /F | Out-Null
            throw 'Managed Python download timed out (1800 seconds).'
        }
        if ($pythonDownload.ExitCode -ne 0) { throw 'Managed Python 3.12 installation failed.' }
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
    $env:PYTHONUTF8 = $previousPythonUtf8
    $env:ARTEMIS_FRONTEND = $previousFrontend
    [Net.ServicePointManager]::SecurityProtocol = $previousTls
    $ErrorActionPreference = $previousErrorPreference
    if ($stage) {
        # Only remove the unique staging directory created under the checked parent.
        $resolvedStage = [IO.Path]::GetFullPath($stage)
        if ((Split-Path -Parent $resolvedStage) -eq $parent -and (Split-Path -Leaf $resolvedStage) -like '.artemis-stage-*') {
            Remove-Item -LiteralPath $resolvedStage -Recurse -Force -ErrorAction SilentlyContinue
        }
    }
}
if ($installerCode -ne 0) {
    if ($PSCommandPath) { exit $installerCode }
    $global:LASTEXITCODE = $installerCode
    throw "ARTEMIS installation failed (code $installerCode)."
}
