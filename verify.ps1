param([string]$InstallDir)
. "$PSScriptRoot\common.ps1"
if (-not $InstallDir) { $InstallDir = $PSScriptRoot }
$bundle = Get-GameTimeBundle (Join-Path $InstallDir 'data')
if ($bundle) {
    if ((Get-GameTimeStartupValue $bundle.StartupName) -ne $bundle.Startup) { throw 'Bundled startup entry does not match.' }
    $report = Join-Path $env:TEMP ('GameTimeMonitor-diagnose-' + [guid]::NewGuid().ToString('N') + '.json')
    $process = Start-Process -FilePath (Join-Path $bundle.InstallDir 'GameTimeMonitor.exe') -ArgumentList @('--diagnose','--data-dir',('"' + $bundle.DataDir + '"'),'--report',('"' + $report + '"')) -WindowStyle Hidden -Wait -PassThru
    if ($process.ExitCode -ne 0 -or -not (Test-Path -LiteralPath $report)) { throw 'Bundled runtime diagnosis failed.' }
    Get-Content -LiteralPath $report
    Remove-Item -LiteralPath $report
    Write-Host 'Verified bundled runtime, profile and automatic startup.'
    return
}
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
