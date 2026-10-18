param([Parameter(Mandatory=$true)][string]$PackageDir,
      [Parameter(Mandatory=$true)][string]$ReportPath,
      [string]$PythonPath='python.exe')
$ErrorActionPreference = 'Stop'
$taskRoot = Join-Path $env:TEMP ('GameTimeMonitor-bundle-test-' + [guid]::NewGuid().ToString('N'))
$app = Join-Path $taskRoot 'App with spaces'
$data = Join-Path $taskRoot 'Profile with spaces'
$games = Join-Path $taskRoot 'Games with spaces'
$desktop = Join-Path $taskRoot 'Desktop fixture'
$name = 'GameTimeMonitor-Test-' + [guid]::NewGuid().ToString('N')
$report = [ordered]@{}
$runKey = 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Run'
$sentinelName = $name + '-Foreign'
$sentinelValue = '"C:\NonexistentFixture\NotExecuted.exe" --preserve'
$startupRegistry = [Microsoft.Win32.Registry]::CurrentUser.CreateSubKey('Software\Microsoft\Windows\CurrentVersion\Run')
$originalStartup = @{}
foreach ($originalName in $startupRegistry.GetValueNames()) {
    $originalStartup[$originalName] = @{Value=$startupRegistry.GetValue($originalName,$null,[Microsoft.Win32.RegistryValueOptions]::DoNotExpandEnvironmentNames);Kind=$startupRegistry.GetValueKind($originalName)}
}
$startupRegistry.SetValue($sentinelName, $sentinelValue)
$startupRegistry.Dispose()
New-Item -ItemType Directory -Path $taskRoot -Force | Out-Null
try {
    $setup = Join-Path ([IO.Path]::GetFullPath($PackageDir)) 'setup.ps1'
    & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $setup -InstallDir $app -DataDir $data -GamesRoot $games -DesktopDir $desktop -StartupName $name -Quiet -NoStart
    if ($LASTEXITCODE -ne 0) { throw 'Fresh install failed.' }
    $exe = Join-Path $app 'GameTimeMonitor.exe'
    $report.bundled_runtime_installed = Test-Path -LiteralPath $exe
    $diag = Join-Path $taskRoot 'diagnose.json'
    $process = Start-Process -FilePath $exe -ArgumentList @('--diagnose','--data-dir',('"' + $data + '"'),'--report',('"' + $diag + '"')) -WindowStyle Hidden -Wait -PassThru
    $first = Get-Content -LiteralPath $diag -Raw -Encoding UTF8 | ConvertFrom-Json
    $report.runtime_and_profile_verified = $process.ExitCode -eq 0 -and $first.data -eq $data -and $first.games_root -eq $games -and $first.hub_enabled -and $first.language -eq 'en'
    $hubIcon = Join-Path $data 'assets\gaming-hub.ico'
    $report.hub_icon_installed = (Test-Path -LiteralPath $hubIcon) -and (Get-FileHash -LiteralPath $hubIcon).Hash -eq (Get-FileHash -LiteralPath (Join-Path $app '_internal\gametime\app.ico')).Hash
    $shell = New-Object -ComObject WScript.Shell
    $hubPath = Join-Path $desktop 'Gaming Hub.lnk'
    $hubLink = $shell.CreateShortcut($hubPath)
    $report.desktop_hub_opens_integrated_app = $hubLink.TargetPath -eq $exe -and $hubLink.Arguments -eq ('--hub --data-dir "' + $data + '"') -and $hubLink.IconLocation -eq ($hubIcon + ',0')
    $report.single_shared_desktop_icon = @(Get-ChildItem -LiteralPath $desktop -Filter '*.lnk').Count -eq 1
    # Diagnostics alone never imports Qt. Exercise the actual frozen GUI too.
    $gui = Start-Process -FilePath $exe -ArgumentList @('--background','--data-dir',('"' + $data + '"')) -WindowStyle Hidden -PassThru
    try {
        Start-Sleep -Seconds 2
        if ($gui.HasExited) { throw 'Frozen Qt resident did not start.' }
        $hubRequest = Start-Process -FilePath $exe -ArgumentList @('--hub','--data-dir',('"' + $data + '"')) -WindowStyle Hidden -PassThru
        if (-not $hubRequest.WaitForExit(10000)) { throw 'Hub request did not return.' }
        $guiDeadline = [DateTime]::UtcNow.AddSeconds(20)
        do {
            Start-Sleep -Milliseconds 200
            $gui.Refresh()
            if ($gui.HasExited) { throw 'Frozen Qt interface exited before opening.' }
            $guiVisible = $gui.MainWindowTitle -eq 'Gaming Hub'
        } until ($guiVisible -or [DateTime]::UtcNow -ge $guiDeadline)
        if (-not $guiVisible) { throw 'Frozen Qt interface did not become visible; inspect its monitor.log.' }
        $report.qt_window_opens_from_background = $true
        $report.qt_hub_request_reuses_resident = $hubRequest.HasExited -and -not $gui.HasExited
        $stop = Start-Process -FilePath $exe -ArgumentList @('--stop-wait','20','--data-dir',('"' + $data + '"')) -WindowStyle Hidden -Wait -PassThru
        $report.qt_resident_stops_gracefully = $stop.ExitCode -eq 0 -and $gui.WaitForExit(10000)
    } finally {
        if (-not $gui.HasExited) { Stop-Process -Id $gui.Id -Force }
    }
    $process = Start-Process -FilePath $exe -ArgumentList @('--configure','--language','hu','--data-dir',('"' + $data + '"')) -WindowStyle Hidden -Wait -PassThru
    if ($process.ExitCode -ne 0) { throw 'Language selection failed.' }
    $trackingStart = 'import sqlite3,sys; d=sqlite3.connect(sys.argv[1]); print(d.execute("SELECT value FROM settings WHERE key=?",("tracking_started_on",)).fetchone()[0])' | & $PythonPath -B - (Join-Path $data 'usage.sqlite3')
    $runKey = 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Run'
    $report.startup_registered = (Get-ItemPropertyValue -LiteralPath $runKey -Name $name) -like ('"' + $exe + '" --background*')
    $report.foreign_startup_preserved_on_install = (Get-ItemProperty -LiteralPath $runKey).PSObject.Properties[$sentinelName].Value -eq $sentinelValue
    $report.installed_apps_registered = Test-Path -LiteralPath ('HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\' + $name)
    $programLink = Join-Path ([Environment]::GetFolderPath('Programs')) ($name + '.lnk')
    $report.start_menu_registered = Test-Path -LiteralPath $programLink
    'unrelated file' | Set-Content -LiteralPath (Join-Path $app 'user-note.txt')
    'save data' | Set-Content -LiteralPath (Join-Path $data 'keep.txt')
    'import sqlite3,sys; from datetime import date; d=sqlite3.connect(sys.argv[1]); d.execute("INSERT INTO game_preferences VALUES (?,?)",("test:hidden",1)); d.execute("INSERT INTO usage VALUES (?,?,?)",(date.today().isoformat(),"test:hidden",123)); d.commit()' | & $PythonPath -B - (Join-Path $data 'usage.sqlite3')
    if ($LASTEXITCODE -ne 0) { throw 'Fixture write failed.' }
    $obsoleteOwned = Join-Path $app 'obsolete-owned.bin'
    $obsoleteEdited = Join-Path $app 'obsolete-edited.txt'
    'old runtime' | Set-Content -LiteralPath $obsoleteOwned
    'original document' | Set-Content -LiteralPath $obsoleteEdited
    $oldPayload = Get-Content -LiteralPath (Join-Path $app 'bundle-install.json') -Raw -Encoding UTF8 | ConvertFrom-Json
    foreach ($oldFile in @($obsoleteOwned,$obsoleteEdited)) {
        $oldPayload.Files += [PSCustomObject]@{Path=[IO.Path]::GetFileName($oldFile);SHA256=(Get-FileHash -LiteralPath $oldFile).Hash}
    }
    $oldPayload | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath (Join-Path $app 'bundle-install.json') -Encoding UTF8
    'user modified document' | Set-Content -LiteralPath $obsoleteEdited
    # Reproduce the old separate monitor icon and old Hub-folder shortcut.
    $legacyDesktop = Join-Path $desktop ($name + '.lnk')
    $oldMonitor = $shell.CreateShortcut($legacyDesktop)
    $oldMonitor.TargetPath = $exe; $oldMonitor.Description = 'Game Time Monitor - GameTimeMonitor.bundle.v1'; $oldMonitor.Save()
    $oldHub = $shell.CreateShortcut($hubPath)
    $oldHub.TargetPath = $games; $oldHub.Arguments = ''; $oldHub.Description = 'Game Time Monitor Gaming Hub'; $oldHub.Save()
    $foreign = Join-Path $desktop 'unrelated.txt'
    'preserve' | Set-Content -LiteralPath $foreign
    & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $setup -InstallDir $app -DataDir $data -GamesRoot $games -DesktopDir $desktop -StartupName $name -Quiet -NoStart
    if ($LASTEXITCODE -ne 0) { throw 'Upgrade failed.' }
    $process = Start-Process -FilePath $exe -ArgumentList @('--diagnose','--data-dir',('"' + $data + '"'),'--report',('"' + $diag + '"')) -WindowStyle Hidden -Wait -PassThru
    $report.obsolete_owned_file_removed = -not (Test-Path -LiteralPath $obsoleteOwned)
    $report.modified_obsolete_file_preserved = (Get-Content -LiteralPath $obsoleteEdited) -eq 'user modified document'
    $report.language_preserved_on_upgrade = (Get-Content -LiteralPath $diag -Raw -Encoding UTF8 | ConvertFrom-Json).language -eq 'hu'
    $trackingStartAfter = 'import sqlite3,sys; d=sqlite3.connect(sys.argv[1]); print(d.execute("SELECT value FROM settings WHERE key=?",("tracking_started_on",)).fetchone()[0])' | & $PythonPath -B - (Join-Path $data 'usage.sqlite3')
    $report.tracking_start_preserved_on_upgrade = $trackingStartAfter -eq $trackingStart
    $upgradedHub = $shell.CreateShortcut($hubPath)
    $report.old_desktop_entries_consolidated = -not (Test-Path -LiteralPath $legacyDesktop) -and $upgradedHub.TargetPath -eq $exe -and $upgradedHub.Arguments.StartsWith('--hub ')
    $report.foreign_desktop_file_preserved = (Get-Content -LiteralPath $foreign) -eq 'preserve'
    $value = 'import sqlite3,sys; d=sqlite3.connect(sys.argv[1]); print(d.execute("SELECT hidden FROM game_preferences WHERE game_id=?",("test:hidden",)).fetchone()[0]); print(d.execute("SELECT seconds FROM usage WHERE game_id=?",("test:hidden",)).fetchone()[0])' | & $PythonPath -B - (Join-Path $data 'usage.sqlite3')
    $report.upgrade_preserves_hidden_and_history = $value[0] -eq '1' -and [double]$value[1] -eq 123
    $report.backup_created = @(Get-ChildItem -LiteralPath (Join-Path $data 'backups') -Filter 'before-*' -Directory).Count -gt 0
    $report.foreign_startup_preserved_on_upgrade = (Get-ItemProperty -LiteralPath $runKey).PSObject.Properties[$sentinelName].Value -eq $sentinelValue
    $validManifestText = Get-Content -LiteralPath (Join-Path $app 'bundle-install.json') -Raw -Encoding UTF8
    $outsideFile = Join-Path $taskRoot 'escape-sentinel.txt'
    'outside sentinel' | Set-Content -LiteralPath $outsideFile
    $unsafeManifest = $validManifestText | ConvertFrom-Json
    $unsafeManifest.Files += [PSCustomObject]@{Path='..\escape-sentinel.txt';SHA256=(Get-FileHash -LiteralPath $outsideFile).Hash}
    $unsafeManifest | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath (Join-Path $app 'bundle-install.json') -Encoding UTF8
    try {
        & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $setup -InstallDir $app -DataDir $data -GamesRoot $games -DesktopDir $desktop -StartupName $name -Quiet -NoStart
        $report.unsafe_obsolete_path_rejected = $LASTEXITCODE -ne 0
        $report.outside_file_preserved = (Get-Content -LiteralPath $outsideFile) -eq 'outside sentinel'
    } finally { $validManifestText | Set-Content -LiteralPath (Join-Path $app 'bundle-install.json') -Encoding UTF8 }
    & powershell.exe -NoProfile -ExecutionPolicy Bypass -File (Join-Path $app 'uninstall-bundled.ps1') -Quiet
    if ($LASTEXITCODE -ne 0) { throw 'Uninstall failed.' }
    $report.program_removed = -not (Test-Path -LiteralPath $exe)
    $report.startup_removed = -not (Get-ItemProperty -LiteralPath $runKey).PSObject.Properties[$name]
    $report.foreign_startup_preserved_on_uninstall = (Get-ItemProperty -LiteralPath $runKey).PSObject.Properties[$sentinelName].Value -eq $sentinelValue
    $report.apps_and_shortcut_removed = -not (Test-Path -LiteralPath $programLink) -and -not (Test-Path -LiteralPath ('HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\' + $name))
    $report.data_and_foreign_files_preserved = (Test-Path -LiteralPath (Join-Path $data 'usage.sqlite3')) -and (Test-Path -LiteralPath (Join-Path $data 'keep.txt')) -and (Test-Path -LiteralPath (Join-Path $app 'user-note.txt'))
    $report.hub_icon_kept_after_monitor_uninstall = Test-Path -LiteralPath $hubIcon
    $report.integrated_app_shortcut_removed_on_uninstall = -not (Test-Path -LiteralPath $hubPath) -and (Test-Path -LiteralPath $foreign)
    if (@($report.Values | Where-Object { $_ -ne $true }).Count) { throw 'One or more bundle checks failed.' }
} catch {
    $report.error = $_ | Out-String
} finally {
    $startupRegistry = [Microsoft.Win32.Registry]::CurrentUser.OpenSubKey('Software\Microsoft\Windows\CurrentVersion\Run', $true)
    try {
        $startupRegistry.DeleteValue($sentinelName, $false)
        foreach ($originalName in $originalStartup.Keys) {
            # A failed regression test must still recover any erased real values.
            if ($null -eq $startupRegistry.GetValue($originalName,$null)) {
                $startupRegistry.SetValue($originalName,$originalStartup[$originalName].Value,$originalStartup[$originalName].Kind)
            }
        }
    } finally { $startupRegistry.Dispose() }
    $ReportPath = [IO.Path]::GetFullPath($ReportPath)
    New-Item -ItemType Directory -Path ([IO.Path]::GetDirectoryName($ReportPath)) -Force | Out-Null
    $report | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath $ReportPath -Encoding UTF8
    # Keep an error's isolated files for diagnosis; no real games were touched.
    if (-not $report.error -and [IO.Path]::GetFullPath($taskRoot).StartsWith([IO.Path]::GetFullPath($env:TEMP) + '\', [StringComparison]::OrdinalIgnoreCase)) {
        Remove-Item -LiteralPath $taskRoot -Recurse -Force
    }
}
if ($report.error) { throw $report.error }
