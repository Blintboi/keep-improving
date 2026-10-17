. "$PSScriptRoot\common.ps1"
$manifest = Read-GameTimeManifest $PSScriptRoot
$launchRoot = $PSScriptRoot
if (-not $manifest) {
    $installedRoot = Get-GameTimeDirectory
    $installedManifest = Read-GameTimeManifest $installedRoot
    if ($installedManifest) { $manifest = $installedManifest; $launchRoot = $installedRoot }
}
$python = if ($manifest) { [PSCustomObject]@{ Pythonw = $manifest.Pythonw } } else { Get-GameTimePython }
$arguments = '-B "' + (Join-Path $launchRoot 'main.py') + '" --data-dir "' + (Join-Path $launchRoot 'data') + '"'
Start-Process -FilePath $python.Pythonw -ArgumentList $arguments -WorkingDirectory $launchRoot -WindowStyle Hidden
