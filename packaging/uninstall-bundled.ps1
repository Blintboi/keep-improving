param([switch]$Quiet)
$ErrorActionPreference = 'Stop'
function Get-PayloadHash([string]$Path) {
    $stream = [IO.File]::OpenRead($Path)
    $hasher = [Security.Cryptography.SHA256]::Create()
    try { return [BitConverter]::ToString($hasher.ComputeHash($stream)).Replace('-','') }
    finally { $hasher.Dispose(); $stream.Dispose() }
}
try {
    $root = [IO.Path]::GetFullPath($PSScriptRoot).TrimEnd('\')
    $marker = Join-Path $root 'bundle-install.json'
    $manifest = Get-Content -LiteralPath $marker -Raw -Encoding UTF8 | ConvertFrom-Json
    if ($manifest.Marker -ne 'GameTimeMonitor.bundle.v1' -or [IO.Path]::GetFullPath($manifest.InstallDir) -ne $root -or
        $root -eq [IO.Path]::GetPathRoot($root).TrimEnd('\')) { throw 'Invalid installation marker; nothing was removed.' }
    if (-not $Quiet) {
        Add-Type -AssemblyName PresentationFramework
        $answer = [System.Windows.MessageBox]::Show('Remove Keep Improving and its Windows startup entries? Games, settings and history will be kept.','Uninstall Keep Improving','YesNo','Question')
        if ($answer -ne 'Yes') { exit 0 }
    }
    $exe = Join-Path $root 'GameTimeMonitor.exe'
    $process = Start-Process -FilePath $exe -ArgumentList @('--stop-wait','20','--data-dir',('"' + $manifest.DataDir + '"')) -WindowStyle Hidden -Wait -PassThru
    if ($process.ExitCode -ne 0) { throw 'The monitor could not be stopped. Exit it from the tray menu first.' }
    $runKey = 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Run'
    $property = (Get-ItemProperty -LiteralPath $runKey -ErrorAction SilentlyContinue).PSObject.Properties[$manifest.StartupName]
    $value = if ($property) { $property.Value } else { $null }
    if ($value -eq $manifest.Startup) { Remove-ItemProperty -LiteralPath $runKey -Name $manifest.StartupName }
    $shell = New-Object -ComObject WScript.Shell
    foreach ($linkPath in $manifest.Links) {
        if (Test-Path -LiteralPath $linkPath) {
            $link = $shell.CreateShortcut($linkPath)
            if ($link.TargetPath -eq $exe -and $link.Description -eq 'Game Time Monitor - GameTimeMonitor.bundle.v1') {
                Remove-Item -LiteralPath $linkPath -Force
            }
        }
    }
    $key = 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\' + $manifest.StartupName
    if ((Get-ItemPropertyValue -LiteralPath $key -Name InstallLocation -ErrorAction SilentlyContinue) -eq $root) {
        Remove-Item -LiteralPath $key -Recurse
    }
    foreach ($file in $manifest.Files) {
        $target = [IO.Path]::GetFullPath((Join-Path $root $file.Path))
        if (-not $target.StartsWith($root + '\', [StringComparison]::OrdinalIgnoreCase)) { throw 'Unsafe manifest path.' }
        $check = $target
        while ($check -and $check.Length -ge $root.Length) {
            if ((Test-Path -LiteralPath $check) -and ((Get-Item -LiteralPath $check).Attributes -band [IO.FileAttributes]::ReparsePoint)) { throw 'Unexpected directory junction; files were preserved.' }
            $check = [IO.Path]::GetDirectoryName($check)
        }
        if ((Test-Path -LiteralPath $target -PathType Leaf) -and (Get-PayloadHash $target) -eq $file.SHA256) {
            Remove-Item -LiteralPath $target -Force
        }
    }
    Remove-Item -LiteralPath $marker -Force
    # Only remove empty owned application directories. No recursive data deletion.
    Get-ChildItem -LiteralPath $root -Directory -Recurse | Sort-Object { $_.FullName.Length } -Descending | ForEach-Object {
        if (-not (Get-ChildItem -LiteralPath $_.FullName -Force | Select-Object -First 1)) { Remove-Item -LiteralPath $_.FullName }
    }
    if (-not (Get-ChildItem -LiteralPath $root -Force | Select-Object -First 1)) { Remove-Item -LiteralPath $root }
    if (-not $Quiet) { [System.Windows.MessageBox]::Show('Keep Improving was removed. Your games and data were kept.','Uninstall complete') | Out-Null }
} catch {
    if (-not $Quiet) {
        Add-Type -AssemblyName PresentationFramework
        [System.Windows.MessageBox]::Show($_.Exception.Message,'Uninstall failed','OK','Error') | Out-Null
    }
    exit 1
}
