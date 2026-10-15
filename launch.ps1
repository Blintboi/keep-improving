. "$PSScriptRoot\common.ps1"
$manifest = Read-GameTimeManifest $PSScriptRoot
$python = if ($manifest) { [PSCustomObject]@{ Pythonw = $manifest.Pythonw } } else { Get-GameTimePython }
$arguments = '-B "' + (Join-Path $PSScriptRoot 'main.py') + '" --data-dir "' + (Join-Path $PSScriptRoot 'data') + '"'
Start-Process -FilePath $python.Pythonw -ArgumentList $arguments -WorkingDirectory $PSScriptRoot -WindowStyle Hidden
