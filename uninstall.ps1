param([string]$InstallDir)
. "$PSScriptRoot\common.ps1"
if (-not $InstallDir) {
    $InstallDir = if (Test-Path -LiteralPath (Join-Path $PSScriptRoot 'install.json')) { $PSScriptRoot } else { Get-GameTimeDirectory }
}
$InstallDir = [IO.Path]::GetFullPath($InstallDir)
$bundle = Get-GameTimeBundle (Join-Path $InstallDir 'data')
if ($bundle) {
    & powershell.exe -NoProfile -ExecutionPolicy Bypass -File (Join-Path $bundle.InstallDir 'uninstall-bundled.ps1')
    if ($LASTEXITCODE -ne 0) { throw 'Bundled application removal failed.' }
    return
}
$manifest = Read-GameTimeManifest $InstallDir
if (-not $manifest) { Write-Host 'No owned installation found. Nothing was removed.'; return }
& $manifest.Python -B (Join-Path $InstallDir 'main.py') --data-dir (Join-Path $InstallDir 'data') --stop-wait 12
if ($LASTEXITCODE -ne 0) { throw 'Exit the monitor using its tray menu, then run uninstall again.' }
$runKey = 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Run'
$current = Get-GameTimeStartupValue $manifest.StartupName
if ($current -eq $manifest.StartupCommand) {
    Remove-ItemProperty -LiteralPath $runKey -Name $manifest.StartupName
} elseif ($current) {
    throw 'The startup entry was changed by another application; it was preserved.'
}
# Fixed file list only. No recursive deletion, games and usage data are preserved.
if ($manifest.PSObject.Properties['StartupShortcut'] -and (Test-Path -LiteralPath $manifest.StartupShortcut)) {
    $shell = New-Object -ComObject WScript.Shell
    $link = $shell.CreateShortcut($manifest.StartupShortcut)
    if ($link.Description -eq 'GameTimeMonitor.v1 startup' -and
        ('"' + $link.TargetPath + '" ' + $link.Arguments) -ceq $manifest.StartupCommand) {
        Remove-Item -LiteralPath $manifest.StartupShortcut
    } else { throw 'A changed startup shortcut was preserved.' }
}
foreach ($name in Get-GameTimeFiles) {
    $target = [IO.Path]::GetFullPath((Join-Path $InstallDir $name))
    if (-not $target.StartsWith($InstallDir.TrimEnd('\') + '\', [StringComparison]::OrdinalIgnoreCase)) {
        throw 'An owned file resolved outside the installation directory.'
    }
    if (Test-Path -LiteralPath $target -PathType Leaf) { Remove-Item -LiteralPath $target -Force }
}
Remove-Item -LiteralPath (Join-Path $InstallDir 'install.json') -Force
Write-Host 'Monitor removed. Automatic startup disabled. Data remains in:'
Write-Host (Join-Path $InstallDir 'data')
