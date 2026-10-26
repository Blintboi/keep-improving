param(
    [string]$InstallDir = (Join-Path $env:LOCALAPPDATA 'Programs\GameTimeMonitor'),
    [string]$DataDir = (Join-Path ([Environment]::GetFolderPath('MyDocuments')) 'GameTimeMonitor\data'),
    [string]$StartupName = 'GameTimeMonitor',
    [string]$GamesRoot,
    [string]$DesktopDir = ([Environment]::GetFolderPath('Desktop')),
    [switch]$NoHubShortcut,
    [switch]$NoDesktopShortcut,
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
    $backup = Join-Path $DataDir ('backups\before-' + $payload.Version + '-' + (Get-Date -Format 'yyyyMMdd-HHmmss'))
    New-Item -ItemType Directory -Path $backup -Force | Out-Null
    foreach ($name in @('usage.sqlite3','usage.sqlite3-wal','usage.sqlite3-shm','hub-state.json')) {
        $item = Join-Path $DataDir $name
        if (Test-Path -LiteralPath $item) { Copy-Item -LiteralPath $item -Destination $backup }
    }
    New-Item -ItemType Directory -Path $InstallDir -Force | Out-Null
    # Retire only unchanged obsolete files recorded by the previous installer.
    # This also removes old runtime DLLs that would shadow a new runtime.
    $newPaths = New-Object 'System.Collections.Generic.HashSet[string]' ([StringComparer]::OrdinalIgnoreCase)
    foreach ($file in $payload.Files) { [void]$newPaths.Add($file.Path) }
    if ($old) {
        foreach ($prior in $old.Files) {
            if ($newPaths.Contains($prior.Path)) { continue }
            $obsolete = [IO.Path]::GetFullPath((Join-Path $InstallDir $prior.Path))
            if (-not $obsolete.StartsWith($InstallDir + '\', [StringComparison]::OrdinalIgnoreCase)) { throw 'Unsafe previous application path.' }
            $check = $obsolete
            while ($check.Length -ge $InstallDir.Length) {
                if ((Test-Path -LiteralPath $check) -and ((Get-Item -LiteralPath $check).Attributes -band [IO.FileAttributes]::ReparsePoint)) { throw 'Obsolete application path contains a reparse point.' }
                $check = [IO.Path]::GetDirectoryName($check)
                if (-not $check) { break }
            }
            if (Test-Path -LiteralPath $obsolete -PathType Leaf) {
                if ((Get-PayloadHash $obsolete) -eq $prior.SHA256) {
                    $retained = [IO.Path]::GetFullPath((Join-Path (Join-Path $backup 'obsolete-program-files') $prior.Path))
                    if (-not $retained.StartsWith($backup + '\', [StringComparison]::OrdinalIgnoreCase)) { throw 'Unsafe obsolete-file backup path.' }
                    [IO.Directory]::CreateDirectory([IO.Path]::GetDirectoryName($retained)) | Out-Null
                    Copy-Item -LiteralPath $obsolete -Destination $retained
                    Remove-Item -LiteralPath $obsolete
                } elseif ([IO.Path]::GetExtension($obsolete) -in @('.dll','.pyd','.exe')) {
                    throw 'An obsolete runtime file was modified and was preserved. Use a separate install folder or restore the original file before upgrading.'
                }
            }
        }
    }
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
        if (Test-Path -LiteralPath $target) {
            if ((Get-Item -LiteralPath $target).Attributes -band [IO.FileAttributes]::ReparsePoint) { throw 'Application file is a reparse point.' }
            # RTSS and other resident helpers can still map an unchanged runtime
            # DLL after the monitor exits. Verify and retain identical files.
            if ((Get-PayloadHash $target) -eq $file.SHA256) { continue }
        }
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
    foreach ($directory in @([Environment]::GetFolderPath('Startup'),[Environment]::GetFolderPath('Programs'))) {
        $shortcutName = if ($directory -eq [Environment]::GetFolderPath('Programs')) { 'Keep Improving' } else { $StartupName }
        $linkPath = Join-Path $directory ($shortcutName + '.lnk')
        $oldProgramLink = Join-Path $directory ($StartupName + '.lnk')
        if ($linkPath -ne $oldProgramLink -and (Test-Path -LiteralPath $oldProgramLink)) {
            $priorProgramLink = $shell.CreateShortcut($oldProgramLink)
            if ($priorProgramLink.TargetPath -eq $exe -and $priorProgramLink.Description -eq 'Game Time Monitor - GameTimeMonitor.bundle.v1') {
                Copy-Item -LiteralPath $oldProgramLink -Destination (Join-Path $backup 'previous-start-menu.lnk')
                Remove-Item -LiteralPath $oldProgramLink
            }
        }
        if (Test-Path -LiteralPath $linkPath) {
            $priorLink = $shell.CreateShortcut($linkPath)
            if ($priorLink.TargetPath -ne $exe -or $priorLink.Description -ne 'Game Time Monitor - GameTimeMonitor.bundle.v1') {
                $linkPath = Join-Path $directory ('Keep Improving - ' + $StartupName + '.lnk')
                if (Test-Path -LiteralPath $linkPath) {
                    $alternate = $shell.CreateShortcut($linkPath)
                    if ($alternate.TargetPath -ne $exe -or $alternate.Description -ne 'Game Time Monitor - GameTimeMonitor.bundle.v1') { throw 'Unrelated shortcut was preserved.' }
                }
            }
        }
        $link = $shell.CreateShortcut($linkPath)
        $link.TargetPath = $exe
        $link.Arguments = if ($directory -eq [Environment]::GetFolderPath('Startup')) { '--background --data-dir "' + $DataDir + '"' } else { '--data-dir "' + $DataDir + '"' }
        $link.WorkingDirectory = $InstallDir
        $link.Description = 'Game Time Monitor - GameTimeMonitor.bundle.v1'
        $link.IconLocation = $exe + ',0'
        $link.Save()
        $links += $linkPath
    }
    $hubAssets = Join-Path $DataDir 'assets'
    New-Item -ItemType Directory -Path $hubAssets -Force | Out-Null
    $hubIcon = Join-Path $hubAssets 'keep-improving.ico'
    Copy-Item -LiteralPath (Join-Path $InstallDir '_internal\gametime\app.ico') -Destination $hubIcon -Force
    if (-not $NoDesktopShortcut) {
        $DesktopDir = [IO.Path]::GetFullPath($DesktopDir)
        New-Item -ItemType Directory -Path $DesktopDir -Force | Out-Null
        $legacyDesktop = Join-Path $DesktopDir ($StartupName + '.lnk')
        if (Test-Path -LiteralPath $legacyDesktop) {
            $legacyLink = $shell.CreateShortcut($legacyDesktop)
            if ($legacyLink.TargetPath -eq $exe -and $legacyLink.Description -eq 'Game Time Monitor - GameTimeMonitor.bundle.v1') {
                Copy-Item -LiteralPath $legacyDesktop -Destination (Join-Path $backup 'previous-monitor-desktop.lnk')
                Remove-Item -LiteralPath $legacyDesktop
            }
        }
        if (-not $NoHubShortcut) {
            $legacyHubPath = Join-Path $DesktopDir 'Gaming Hub.lnk'
            if (Test-Path -LiteralPath $legacyHubPath) {
                $legacyHub = $shell.CreateShortcut($legacyHubPath)
                if ($legacyHub.Description -eq 'Game Time Monitor Gaming Hub' -or
                    ($legacyHub.TargetPath -eq $exe -and $legacyHub.Description -eq 'Game Time Monitor - GameTimeMonitor.bundle.v1')) {
                    Copy-Item -LiteralPath $legacyHubPath -Destination (Join-Path $backup 'previous-hub-desktop.lnk')
                    Remove-Item -LiteralPath $legacyHubPath
                }
            }
            $hubPath = Join-Path $DesktopDir 'Keep Improving.lnk'
            if (Test-Path -LiteralPath $hubPath) {
                $previousHub = $shell.CreateShortcut($hubPath)
                if ($previousHub.Description -eq 'Game Time Monitor Gaming Hub' -or
                    ($previousHub.TargetPath -eq $exe -and $previousHub.Description -eq 'Game Time Monitor - GameTimeMonitor.bundle.v1')) {
                    Copy-Item -LiteralPath $hubPath -Destination (Join-Path $backup 'previous-hub-desktop.lnk')
                } else {
                    $hubPath = Join-Path $DesktopDir ($StartupName + ' Hub.lnk')
                    if (Test-Path -LiteralPath $hubPath) {
                        $alternate = $shell.CreateShortcut($hubPath)
                        if ($alternate.TargetPath -ne $exe -or $alternate.Description -ne 'Game Time Monitor - GameTimeMonitor.bundle.v1') {
                            throw 'Unrelated Gaming Hub desktop shortcuts were preserved.'
                        }
                    }
                }
            }
            $hubLink = $shell.CreateShortcut($hubPath)
            $hubLink.TargetPath = $exe
            $hubLink.Arguments = '--hub --data-dir "' + $DataDir + '"'
            $hubLink.WorkingDirectory = $InstallDir
            $hubLink.Description = 'Game Time Monitor - GameTimeMonitor.bundle.v1'
            $hubLink.IconLocation = $hubIcon + ',0'
            $hubLink.Save()
            $links += $hubPath
        }
    }
    $uninstallKey = 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\' + $StartupName
    $uninstall = 'powershell.exe -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "' + (Join-Path $InstallDir 'uninstall-bundled.ps1') + '"'
    $manifest = [ordered]@{ Marker='GameTimeMonitor.bundle.v1'; Version=$payload.Version; InstallDir=$InstallDir; DataDir=$DataDir;
        StartupName=$StartupName; Startup=$startup; UninstallKey=$uninstallKey; Links=$links; Files=$payload.Files }
    $manifest | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath (Join-Path $InstallDir 'bundle-install.json') -Encoding UTF8
    New-Item -Path $uninstallKey -Force | Out-Null
    foreach ($pair in @{DisplayName='Keep Improving';DisplayVersion=$payload.Version;Publisher='Keep Improving contributors';InstallLocation=$InstallDir;
                        DisplayIcon=$exe;UninstallString=$uninstall;NoModify=1;NoRepair=1}.GetEnumerator()) {
        Set-ItemProperty -LiteralPath $uninstallKey -Name $pair.Key -Value $pair.Value
    }
    "Installed $($payload.Version) to $InstallDir. Data: $DataDir" | Set-Content -LiteralPath $taskLog -Encoding UTF8
    if (-not $NoStart) {
        Start-Process -FilePath $exe -ArgumentList @('--data-dir',('"' + $DataDir + '"')) -WindowStyle Hidden -WorkingDirectory $InstallDir
    }
    if (-not $Quiet) {
        Add-Type -AssemblyName PresentationFramework
        [System.Windows.MessageBox]::Show("Keep Improving is installed and starts with Windows.`n`nYour history and settings stay on this computer.`nUse the tray icon to open Settings or exit.",'Setup complete','OK','Information') | Out-Null
    }
} catch {
    $_ | Out-String | Set-Content -LiteralPath $taskLog -Encoding UTF8
    if (-not $Quiet) {
        Add-Type -AssemblyName PresentationFramework
        [System.Windows.MessageBox]::Show("Installation failed: $($_.Exception.Message)`n`nDetails: $taskLog",'Keep Improving setup','OK','Error') | Out-Null
    }
    exit 1
} finally {
    if ((Test-Path -LiteralPath $taskStage) -and [IO.Path]::GetFullPath($taskStage).StartsWith([IO.Path]::GetFullPath($env:TEMP) + '\', [StringComparison]::OrdinalIgnoreCase)) {
        Remove-Item -LiteralPath $taskStage -Recurse -Force
    }
}
