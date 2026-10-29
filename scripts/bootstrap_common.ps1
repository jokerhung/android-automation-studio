function Initialize-BootstrapUv([string]$Root, [string]$Temporary) {
    $version = '0.12.13'
    $uvPath = Join-Path $Root '.tools/uv/uv.exe'
    if (Test-Path -LiteralPath $uvPath) {
        $reportedVersion = & $uvPath --version
        if ($LASTEXITCODE -eq 0 -and $reportedVersion -match ('^uv ' + [regex]::Escape($version) + '(\s|$)')) { return $uvPath }
    }
    Write-Host "[DANG] 3/6 Preparing uv $version and managed Python 3.12"
    $file = 'uv-x86_64-pc-windows-msvc.zip'
    $base = "https://github.com/astral-sh/uv/releases/download/$version"
    # Local helper also works when this module is used outside the root bootstrap.
    foreach ($name in @($file, "$file.sha256")) {
        for ($attempt = 1; $attempt -le 3; $attempt++) {
            try {
                Invoke-WebRequest -UseBasicParsing -Uri "$base/$name" -OutFile "$Temporary/$name" -TimeoutSec 600
                break
            } catch {
                if ($attempt -eq 3) { throw }
                Start-Sleep -Seconds (2 * $attempt)
            }
        }
    }
    $expected = ((Get-Content -LiteralPath "$Temporary/$file.sha256" -Raw).Trim() -split '\s+')[0]
    $actual = (Get-FileHash -LiteralPath "$Temporary/$file" -Algorithm SHA256).Hash
    if ($actual -ne $expected) { throw 'uv checksum mismatch.' }
    Expand-Archive -LiteralPath "$Temporary/$file" -DestinationPath "$Temporary/uv"
    $binary = @(Get-ChildItem -LiteralPath "$Temporary/uv" -Recurse -Filter uv.exe)[0]
    if (-not $binary) { throw 'uv archive has no uv.exe.' }
    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $uvPath) | Out-Null
    Copy-Item -LiteralPath $binary.FullName -Destination $uvPath
    return $uvPath
}
