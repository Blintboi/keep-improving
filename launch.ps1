. "$PSScriptRoot\common.ps1"
$manifest = Read-GameTimeManifest $PSScriptRoot
$launchRoot = $PSScriptRoot
if (-not $manifest) {
    $installedRoot = Get-GameTimeDirectory
    $installedManifest = Read-GameTimeManifest $installedRoot
    if ($installedManifest) { $manifest = $installedManifest; $launchRoot = $installedRoot }
}
$profile = if ($manifest) { Join-Path $launchRoot 'data' } else { Join-Path (Get-GameTimeDirectory) 'data' }
$bundle = Get-GameTimeBundle $profile
if ($bundle) {
    Start-Process -FilePath (Join-Path $bundle.InstallDir 'GameTimeMonitor.exe') -ArgumentList @('--data-dir',('"' + $bundle.DataDir + '"')) -WindowStyle Hidden
    exit
}
$python = if ($manifest) { [PSCustomObject]@{ Pythonw = $manifest.Pythonw } } else { Get-GameTimePython }
$arguments = '-B "' + (Join-Path $launchRoot 'main.py') + '" --data-dir "' + (Join-Path $launchRoot 'data') + '"'
Start-Process -FilePath $python.Pythonw -ArgumentList $arguments -WorkingDirectory $launchRoot -WindowStyle Hidden
