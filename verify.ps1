param([string]$InstallDir)
. "$PSScriptRoot\common.ps1"
if (-not $InstallDir) { $InstallDir = $PSScriptRoot }
$manifest = Read-GameTimeManifest $InstallDir
if (-not $manifest) { throw 'Installation marker is missing. Run Telepites.cmd first.' }
foreach ($file in Get-GameTimeFiles) {
    if (-not (Test-Path -LiteralPath (Join-Path $InstallDir $file) -PathType Leaf)) { throw "Missing file: $file" }
}
$value = Get-GameTimeStartupValue $manifest.StartupName
if ($value -ne $manifest.StartupCommand) { throw 'Automatic startup does not match this installation.' }
if ($manifest.PSObject.Properties['StartupShortcut']) {
    if (-not (Test-Path -LiteralPath $manifest.StartupShortcut)) { throw 'Startup folder shortcut is missing.' }
    $shell = New-Object -ComObject WScript.Shell
    $link = $shell.CreateShortcut($manifest.StartupShortcut)
    if (('"' + $link.TargetPath + '" ' + $link.Arguments) -cne $manifest.StartupCommand) {
        throw 'Startup shortcut does not match this installation.'
    }
}
& $manifest.Python -B (Join-Path $InstallDir 'main.py') --data-dir (Join-Path $InstallDir 'data') --diagnose
if ($LASTEXITCODE -ne 0) { throw 'Diagnostic command failed.' }
Write-Host 'Verified: Python, app files, SQLite and per-user automatic startup.'
