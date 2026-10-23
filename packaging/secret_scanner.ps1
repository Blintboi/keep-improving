# Pinned upstream scanner, verified before extracting or running executable code.
function Get-GameTimeSecretScanner([string]$CacheDir) {
    $ErrorActionPreference = 'Stop'
    New-Item -ItemType Directory -Path $CacheDir -Force | Out-Null
    $archive = Join-Path $CacheDir 'gitleaks_8.30.1_windows_x64.zip'
    $expected = 'd29144deff3a68aa93ced33dddf84b7fdc26070add4aa0f4513094c8332afc4e'
    if (-not (Test-Path -LiteralPath $archive)) {
        Invoke-WebRequest -UseBasicParsing -Uri 'https://github.com/gitleaks/gitleaks/releases/download/v8.30.1/gitleaks_8.30.1_windows_x64.zip' -OutFile $archive
    }
    if ((Get-FileHash -LiteralPath $archive -Algorithm SHA256).Hash.ToLowerInvariant() -ne $expected) {
        throw 'Secret scanner integrity check failed.'
    }
    # Re-extract from verified bytes so a modified cached EXE cannot bypass checks.
    Expand-Archive -LiteralPath $archive -DestinationPath (Join-Path $CacheDir 'verified') -Force
    return Join-Path $CacheDir 'verified\gitleaks.exe'
}
