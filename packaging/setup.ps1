param(
    [string]$InstallDir = (Join-Path $env:LOCALAPPDATA 'Programs\GameTimeMonitor'),
    [string]$DataDir = (Join-Path ([Environment]::GetFolderPath('MyDocuments')) 'GameTimeMonitor\data'),
    [string]$StartupName = 'GameTimeMonitor',
    [string]$GamesRoot,
    [switch]$NoHubShortcut,
    [switch]$NoStart,
    [switch]$Quiet
)
$ErrorActionPreference = 'Stop'
$taskLog = Join-Path $env:TEMP 'GameTimeMonitor-setup.log'
$taskStage = Join-Path $env:TEMP ('GameTimeMonitor-stage-' + [guid]::NewGuid().ToString('N'))
function Get-PayloadHash([string]$Path) {
    $stream = [IO.File]::OpenRead($Path)
    $hasher = [Security.Cryptography.SHA256]::Create()
    try { return [BitConverter]::ToString($hasher.ComputeHash($stream)).Replace('-','') }
    finally { $hasher.Dispose(); $stream.Dispose() }
}
try {
    $InstallDir = [IO.Path]::GetFullPath($InstallDir).TrimEnd('\')
    $DataDir = [IO.Path]::GetFullPath($DataDir).TrimEnd('\')
    if ([IO.Path]::GetPathRoot($InstallDir).TrimEnd('\') -eq $InstallDir -or $InstallDir -eq $env:USERPROFILE -or
        $InstallDir -eq $env:LOCALAPPDATA -or $DataDir -eq $InstallDir -or $DataDir.StartsWith($InstallDir + '\', [StringComparison]::OrdinalIgnoreCase)) {
        throw 'Choose a dedicated application folder, separate from the data folder.'
    }
    $oldManifest = Join-Path $InstallDir 'bundle-install.json'
    if (Test-Path -LiteralPath $InstallDir) {
        if (-not (Test-Path -LiteralPath $oldManifest)) { throw 'The target folder already exists and is not owned by Game Time Monitor.' }
        $old = Get-Content -LiteralPath $oldManifest -Raw -Encoding UTF8 | ConvertFrom-Json
        if ($old.Marker -ne 'GameTimeMonitor.bundle.v1' -or [IO.Path]::GetFullPath($old.InstallDir) -ne $InstallDir) {
            throw 'Invalid installation marker. No files were replaced.'
        }
    }
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    $archive = [IO.Compression.ZipFile]::OpenRead((Join-Path $PSScriptRoot 'payload.zip'))
    try {
        foreach ($entry in $archive.Entries) {
            $destination = [IO.Path]::GetFullPath((Join-Path $taskStage $entry.FullName))
            if (-not $destination.StartsWith($taskStage + '\', [StringComparison]::OrdinalIgnoreCase)) { throw 'Unsafe archive entry.' }
        }
    } finally { $archive.Dispose() }
    Expand-Archive -LiteralPath (Join-Path $PSScriptRoot 'payload.zip') -DestinationPath $taskStage
    $payload = Get-Content -LiteralPath (Join-Path $taskStage 'payload-manifest.json') -Raw -Encoding UTF8 | ConvertFrom-Json
    foreach ($file in $payload.Files) {
        $path = [IO.Path]::GetFullPath((Join-Path $taskStage $file.Path))
        if (-not $path.StartsWith($taskStage + '\', [StringComparison]::OrdinalIgnoreCase) -or
            (Get-PayloadHash $path) -ne $file.SHA256) { throw 'Payload integrity check failed.' }
    }
    New-Item -ItemType Directory -Path $DataDir -Force | Out-Null
    # The new bundled runtime can stop both old Python installs and bundled ones.
    $stageExe = Join-Path $taskStage 'GameTimeMonitor.exe'
    $process = Start-Process -FilePath $stageExe -ArgumentList @('--stop-wait','20','--data-dir',('"' + $DataDir + '"')) -WindowStyle Hidden -Wait -PassThru
    if ($process.ExitCode -ne 0) { throw 'The running monitor could not be stopped. Close it from its tray menu and retry.' }
    $backup = Join-Path $DataDir ('backups\before-1.4.0-' + (Get-Date -Format 'yyyyMMdd-HHmmss'))
    New-Item -ItemType Directory -Path $backup -Force | Out-Null
    foreach ($name in @('usage.sqlite3','usage.sqlite3-wal','usage.sqlite3-shm','hub-state.json')) {
        $item = Join-Path $DataDir $name
        if (Test-Path -LiteralPath $item) { Copy-Item -LiteralPath $item -Destination $backup }
    }
    New-Item -ItemType Directory -Path $InstallDir -Force | Out-Null
    foreach ($file in $payload.Files) {
        $target = [IO.Path]::GetFullPath((Join-Path $InstallDir $file.Path))
        if (-not $target.StartsWith($InstallDir + '\', [StringComparison]::OrdinalIgnoreCase)) { throw 'Unsafe application path.' }
        $parent = [IO.Path]::GetDirectoryName($target)
        $check = $parent
        while ($check.Length -ge $InstallDir.Length) {
            if ((Test-Path -LiteralPath $check) -and ((Get-Item -LiteralPath $check).Attributes -band [IO.FileAttributes]::ReparsePoint)) { throw 'Application folder contains a directory junction.' }
            $check = [IO.Path]::GetDirectoryName($check)
            if (-not $check) { break }
        }
        New-Item -ItemType Directory -Path $parent -Force | Out-Null
        Copy-Item -LiteralPath (Join-Path $taskStage $file.Path) -Destination $target -Force
    }
    $exe = Join-Path $InstallDir 'GameTimeMonitor.exe'
    $report = Join-Path $taskStage 'configured.json'
    $arguments = @('--configure','--data-dir',('"' + $DataDir + '"'))
    if (-not (Test-Path -LiteralPath (Join-Path $DataDir 'usage.sqlite3'))) {
        if (-not $GamesRoot) { $GamesRoot = Join-Path ([Environment]::GetFolderPath('MyDocuments')) 'Gaming Hub' }
        $arguments += @('--enable-hub','--games-root',('"' + $GamesRoot + '"'))
    }
    $process = Start-Process -FilePath $exe -ArgumentList $arguments -WindowStyle Hidden -Wait -PassThru
    if ($process.ExitCode -ne 0) { throw 'Configuration failed. Your previous data backup was preserved.' }
    $process = Start-Process -FilePath $exe -ArgumentList @('--diagnose','--data-dir',('"' + $DataDir + '"'),'--report',('"' + $report + '"')) -WindowStyle Hidden -Wait -PassThru
    if ($process.ExitCode -ne 0 -or -not (Test-Path -LiteralPath $report)) { throw 'Installed application verification failed.' }
    $diagnostic = Get-Content -LiteralPath $report -Raw -Encoding UTF8 | ConvertFrom-Json
    $startup = '"' + $exe + '" --background --data-dir "' + $DataDir + '"'
    $runKey = 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Run'
    # New-Item -Force on an existing registry key clears its other values.
    # CreateSubKey opens it without replacing it; update only our own value.
    $runRegistry = [Microsoft.Win32.Registry]::CurrentUser.CreateSubKey('Software\Microsoft\Windows\CurrentVersion\Run')
    try { $runRegistry.SetValue($StartupName, $startup, [Microsoft.Win32.RegistryValueKind]::String) }
    finally { $runRegistry.Dispose() }
    $shell = New-Object -ComObject WScript.Shell
    $links = @()
    foreach ($directory in @([Environment]::GetFolderPath('Startup'),[Environment]::GetFolderPath('Programs'),[Environment]::GetFolderPath('Desktop'))) {
        $linkPath = Join-Path $directory ($StartupName + '.lnk')
        $link = $shell.CreateShortcut($linkPath)
        $link.TargetPath = $exe
        $link.Arguments = if ($directory -eq [Environment]::GetFolderPath('Startup')) { '--background --data-dir "' + $DataDir + '"' } else { '--data-dir "' + $DataDir + '"' }
        $link.WorkingDirectory = $InstallDir
        $link.Description = 'Game Time Monitor - GameTimeMonitor.bundle.v1'
        $link.IconLocation = $exe + ',0'
        $link.Save()
        $links += $linkPath
    }
    if ($diagnostic.hub_enabled -and -not $NoHubShortcut) {
        New-Item -ItemType Directory -Path $diagnostic.games_root -Force | Out-Null
        $hubLink = $shell.CreateShortcut((Join-Path ([Environment]::GetFolderPath('Desktop')) 'Gaming Hub.lnk'))
        $hubLink.TargetPath = $diagnostic.games_root
        $hubLink.Description = 'Game Time Monitor Gaming Hub'
        $hubLink.Save()
    }
    $uninstallKey = 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\' + $StartupName
    $uninstall = 'powershell.exe -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "' + (Join-Path $InstallDir 'uninstall-bundled.ps1') + '"'
    $manifest = [ordered]@{ Marker='GameTimeMonitor.bundle.v1'; Version=$payload.Version; InstallDir=$InstallDir; DataDir=$DataDir;
        StartupName=$StartupName; Startup=$startup; UninstallKey=$uninstallKey; Links=$links; Files=$payload.Files }
    $manifest | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath (Join-Path $InstallDir 'bundle-install.json') -Encoding UTF8
    New-Item -Path $uninstallKey -Force | Out-Null
    foreach ($pair in @{DisplayName='Game Time Monitor';DisplayVersion=$payload.Version;Publisher='Game Time Monitor contributors';InstallLocation=$InstallDir;
                        DisplayIcon=$exe;UninstallString=$uninstall;NoModify=1;NoRepair=1}.GetEnumerator()) {
        Set-ItemProperty -LiteralPath $uninstallKey -Name $pair.Key -Value $pair.Value
    }
    "Installed $($payload.Version) to $InstallDir. Data: $DataDir" | Set-Content -LiteralPath $taskLog -Encoding UTF8
    if (-not $NoStart) {
        Start-Process -FilePath $exe -ArgumentList @('--data-dir',('"' + $DataDir + '"')) -WindowStyle Hidden -WorkingDirectory $InstallDir
    }
    if (-not $Quiet) {
        Add-Type -AssemblyName PresentationFramework
        [System.Windows.MessageBox]::Show("Game Time Monitor is installed and starts with Windows.`n`nYour games and play history stay on this computer.`nUse the tray icon to open Settings or exit.",'Setup complete','OK','Information') | Out-Null
    }
} catch {
    $_ | Out-String | Set-Content -LiteralPath $taskLog -Encoding UTF8
    if (-not $Quiet) {
        Add-Type -AssemblyName PresentationFramework
        [System.Windows.MessageBox]::Show("Installation failed: $($_.Exception.Message)`n`nDetails: $taskLog",'Game Time Monitor setup','OK','Error') | Out-Null
    }
    exit 1
} finally {
    if ((Test-Path -LiteralPath $taskStage) -and [IO.Path]::GetFullPath($taskStage).StartsWith([IO.Path]::GetFullPath($env:TEMP) + '\', [StringComparison]::OrdinalIgnoreCase)) {
        Remove-Item -LiteralPath $taskStage -Recurse -Force
    }
}
