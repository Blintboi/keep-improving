param([string]$PythonPath, [string]$GamesRoot, [string]$InstallDir,
      [string]$StartupName = 'GameTimeMonitor', [switch]$NoStart)
. "$PSScriptRoot\common.ps1"
if (-not $InstallDir) { $InstallDir = Get-GameTimeDirectory }
$InstallDir = [IO.Path]::GetFullPath($InstallDir)
if ($InstallDir -eq [IO.Path]::GetPathRoot($InstallDir) -or $InstallDir.Contains('"')) {
    throw 'Choose a dedicated installation directory.'
}
if ($StartupName -notmatch '^GameTimeMonitor([.][A-Za-z0-9_-]+)*$') { throw 'Invalid startup value name.' }
$python = Get-GameTimePython $PythonPath
if (-not $GamesRoot) {
    $answer = Read-Host 'Games folder [C:\Games] (Enter accepts the default)'
    $GamesRoot = if ($answer.Trim()) { $answer.Trim() } else { 'C:\Games' }
}
if (-not [IO.Path]::IsPathRooted($GamesRoot)) { throw 'Games folder must be an absolute path.' }
$GamesRoot = [IO.Path]::GetFullPath($GamesRoot)
if ($GamesRoot -eq [IO.Path]::GetPathRoot($GamesRoot) -or $GamesRoot.Contains('"')) {
    throw 'Games folder must be a dedicated directory, not a drive root.'
}
$old = Read-GameTimeManifest $InstallDir
if ((Test-Path -LiteralPath $InstallDir) -and -not $old) {
    $other = @(Get-ChildItem -LiteralPath $InstallDir -Force | Where-Object Name -ne 'data')
    if ($other.Count) { throw 'The destination contains files from another application. Choose a separate directory.' }
}
$runKey = 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Run'
$commandLine = '"' + $python.Pythonw + '" -B "' + (Join-Path $InstallDir 'main.py') + '" --background --data-dir "' + (Join-Path $InstallDir 'data') + '"'
$existing = Get-GameTimeStartupValue $StartupName
if ($existing -and $existing -ne $commandLine -and (-not $old -or $existing -ne $old.StartupCommand)) {
    throw 'This startup entry belongs to a different installation; it was not changed.'
}
if ($old) {
    & $python.Python -B (Join-Path $InstallDir 'main.py') --data-dir (Join-Path $InstallDir 'data') --stop-wait 12
    if ($LASTEXITCODE -ne 0) { throw 'The running monitor could not be stopped.' }
}
[IO.Directory]::CreateDirectory($InstallDir) | Out-Null
foreach ($name in Get-GameTimeFiles) {
    $source = Join-Path $PSScriptRoot $name
    $target = Join-Path $InstallDir $name
    [IO.Directory]::CreateDirectory((Split-Path -Parent $target)) | Out-Null
    if ([IO.Path]::GetFullPath($source) -ne [IO.Path]::GetFullPath($target)) {
        Copy-Item -LiteralPath $source -Destination $target -Force
    }
}
$manifest = [ordered]@{ Marker = 'GameTimeMonitor.v1'; InstallDir = $InstallDir; Python = $python.Python;
    Pythonw = $python.Pythonw; StartupName = $StartupName; StartupCommand = $commandLine }
$manifest | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $InstallDir 'install.json') -Encoding UTF8
& $python.Python -B (Join-Path $InstallDir 'main.py') --data-dir (Join-Path $InstallDir 'data') --configure --games-root $GamesRoot --scan-once
if ($LASTEXITCODE -ne 0) { throw 'Initial configuration or discovery failed; automatic startup was not enabled.' }
if (-not (Test-Path -LiteralPath $runKey)) { New-Item -Path $runKey -Force | Out-Null }
New-ItemProperty -LiteralPath $runKey -Name $StartupName -PropertyType String -Value $commandLine -Force | Out-Null
if ($old -and $old.StartupName -ne $StartupName) {
    $oldCommand = Get-GameTimeStartupValue $old.StartupName
    if ($oldCommand -eq $old.StartupCommand) { Remove-ItemProperty -LiteralPath $runKey -Name $old.StartupName }
}
& (Join-Path $InstallDir 'verify.ps1') -InstallDir $InstallDir
Write-Host "Installed: $InstallDir"
Write-Host "Games folder: $GamesRoot"
Write-Host 'Open Inditas.cmd. Use the Popup proba button to test the notification.'
if (-not $NoStart) {
    $arguments = '-B "' + (Join-Path $InstallDir 'main.py') + '" --data-dir "' + (Join-Path $InstallDir 'data') + '"'
    Start-Process -FilePath $python.Pythonw -ArgumentList $arguments -WorkingDirectory $InstallDir -WindowStyle Hidden
}
