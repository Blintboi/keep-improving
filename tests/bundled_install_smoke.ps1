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
    & (Join-Path $app '_internal\gametime\rtss_bridge.exe') --self-test
    $report.rtss_bridge_verified = $LASTEXITCODE -eq 0
    $diag = Join-Path $taskRoot 'diagnose.json'
    $process = Start-Process -FilePath $exe -ArgumentList @('--diagnose','--data-dir',('"' + $data + '"'),'--report',('"' + $diag + '"')) -WindowStyle Hidden -Wait -PassThru
    $first = Get-Content -LiteralPath $diag -Raw -Encoding UTF8 | ConvertFrom-Json
    $installedVersion = (Get-Content -LiteralPath (Join-Path $app 'bundle-install.json') -Raw -Encoding UTF8 | ConvertFrom-Json).Version
    $report.runtime_version_matches_payload = $first.version -eq $installedVersion
    $report.runtime_file_version_matches_payload = (Get-Item -LiteralPath $exe).VersionInfo.ProductVersion -eq $installedVersion
    $report.fresh_update_checks_enabled = $first.check_updates -eq $true
    $report.runtime_and_profile_verified = $process.ExitCode -eq 0 -and $first.data -eq $data -and $first.games_root -eq $games -and $first.hub_enabled -and $first.language -eq 'en'
    $report.fresh_overlay_is_opt_in = -not $first.overlay_enabled -and $first.overlay_replace_warning -and $first.limit_popup_enabled
    $report.fresh_rtss_is_opt_in = $first.overlay_rtss_auto -eq $false
    $report.fresh_overlay_risk_consent_is_empty = $first.overlay_risk_consent_count -eq 0
    $report.fresh_minimize_risk_consent_is_empty = $first.minimize_risk_consent_count -eq 0
    $report.fresh_countdown_size_is_compatible = $first.overlay_font_size -eq 25
    $report.fresh_personalization_defaults_are_compatible = $first.overlay_color_normal -eq '#ffffff' -and $first.overlay_color_warning -eq '#ff5c65' -and $first.custom_message_count -eq 0
    $report.fresh_sound_schedule_and_game_defaults_are_compatible = $first.notification_sound -eq 'default' -and -not $first.weekend_enabled -and $first.game_countdown_count -eq 0
    $report.fresh_weekly_schedule_defaults_are_compatible = $first.scheduled_day_count -eq 0
    $report.fresh_restriction_is_opt_in = -not $first.restriction_enabled -and $first.restriction_seconds -eq 7500
    $report.fresh_bedtime_is_opt_in = -not $first.bedtime_enabled -and -not $first.bedtime_minimize -and $first.bedtime_warning_minute -eq 1435 -and $first.bedtime_minute -eq 0 -and $first.bedtime_resume_minute -eq 360
    $report.fresh_bedtime_budget_is_opt_in = $first.bedtime_caps_budget -eq $false
    $report.fresh_budget_resets_at_midnight = $first.budget_reset_minute -eq 0
    $report.fresh_per_game_limits_are_empty = $first.game_limit_count -eq 0
    $report.bedtime_handover_script_bundled = Test-Path -LiteralPath (Join-Path $app '_internal\gametime\bedtime_legacy.ps1')
    $hubIcon = Join-Path $data 'assets\gaming-hub.ico'
    $report.hub_icon_installed = (Test-Path -LiteralPath $hubIcon) -and (Get-FileHash -LiteralPath $hubIcon).Hash -eq (Get-FileHash -LiteralPath (Join-Path $app '_internal\gametime\app.ico')).Hash
    $shell = New-Object -ComObject WScript.Shell
    $hubPath = Join-Path $desktop 'Gaming Hub.lnk'
    $hubLink = $shell.CreateShortcut($hubPath)
    $report.desktop_hub_opens_integrated_app = $hubLink.TargetPath -eq $exe -and $hubLink.Arguments -eq ('--hub --data-dir "' + $data + '"') -and $hubLink.IconLocation -eq ($hubIcon + ',0')
    $report.single_shared_desktop_icon = @(Get-ChildItem -LiteralPath $desktop -Filter '*.lnk').Count -eq 1
    # Diagnostics alone never imports Qt. Exercise the actual frozen GUI too.
    # Automated profiles never contact the public update service.
    'import json,sqlite3,sys; d=sqlite3.connect(sys.argv[1]); c=json.loads(d.execute("SELECT value FROM settings WHERE key=?",("config",)).fetchone()[0]); c["check_updates"]=False; d.execute("UPDATE settings SET value=? WHERE key=?",(json.dumps(c),"config")); d.commit()' | & $PythonPath -B - (Join-Path $data 'usage.sqlite3')
    if ($LASTEXITCODE -ne 0) { throw 'Could not isolate updater network access.' }
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
    'import json,sqlite3,sys; d=sqlite3.connect(sys.argv[1]); c=json.loads(d.execute("SELECT value FROM settings WHERE key=?",("config",)).fetchone()[0]); c.update(bedtime_enabled=True,bedtime_minimize=True,bedtime_minute=30,restriction_enabled=True,restriction_seconds=7500,overlay_enabled=True,overlay_replace_warning=True,limit_popup_enabled=False,overlay_opacity=0.55,overlay_font_size=48,overlay_color_normal="#12ab34",overlay_color_warning="#bc56ef",notification_messages={"warning":"Fixture: {remaining} min left","bedtime":"Sleep well"},overlay_x=0.2,overlay_y=0.8,overlay_screen="missing-fixture-monitor",overlay_rtss_auto=False,overlay_rtss_paths=[r"C:\Fixture\game.exe"]); d.execute("UPDATE settings SET value=? WHERE key=?",(json.dumps(c),"config")); d.commit()' | & $PythonPath -B - (Join-Path $data 'usage.sqlite3')
    if ($LASTEXITCODE -ne 0) { throw 'Overlay fixture settings failed.' }
    @'
import json,sqlite3,sys
from gametime.statistics_sync import local_group
d=sqlite3.connect(sys.argv[1]); code='1'*32; day='2026-01-01'
c=json.loads(d.execute("SELECT value FROM settings WHERE key='config'").fetchone()[0])
c.update(bedtime_caps_budget=True,notification_sound='silent',notification_sound_path=r'C:\Fixture\saved.wav',weekend_enabled=True,weekend_schedule={'limit_seconds':10800,'warning_seconds':9000,'bedtime_minute':60,'bedtime_resume_minute':480},game_overlays={'test:hidden':{'overlay_enabled':False,'overlay_font_size':36,'overlay_x':0.1,'overlay_y':0.9,'overlay_color_normal':'#aabbcc','overlay_color_warning':'#dd5566'}})
c.update(daily_schedules={'1':{'limit_seconds':13200,'warning_seconds':12000,'bedtime_minute':90}})
c.update(game_limits={'test:hidden':1800})
c.update(statistics_sync_group=code,statistics_sync_enabled=False,statistics_device_name='Fixture Desktop')
d.execute("UPDATE settings SET value=? WHERE key='config'",(json.dumps(c),))
d.execute('INSERT INTO statistics_devices VALUES (?,?,?,?,?)',(code,'a'*32,'Other fixture PC',99,day))
d.execute('INSERT INTO statistics_remote VALUES (?,?,?,?,?,?,?)',(code,'a'*32,day,'steam:42','Example','Steam',120))
d.execute('INSERT INTO settings VALUES (?,?)',('statistics_snapshot:'+code,json.dumps({'revision':99,'digest':'fixture'})))
d.execute('INSERT INTO settings VALUES (?,?)',('launcher_clients',json.dumps({'version':1,'clients':[]})))
d.execute('INSERT INTO settings VALUES (?,?)',('statistics_device_alias:'+local_group(code)+':'+'a'*32,'Fixture Laptop'))
d.commit(); d.close()
'@ | & $PythonPath -B - (Join-Path $data 'usage.sqlite3')
    if ($LASTEXITCODE -ne 0) { throw 'Legacy credential fixture failed.' }
    $trackingStart = 'import sqlite3,sys; d=sqlite3.connect(sys.argv[1]); print(d.execute("SELECT value FROM settings WHERE key=?",("tracking_started_on",)).fetchone()[0])' | & $PythonPath -B - (Join-Path $data 'usage.sqlite3')
    $runKey = 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Run'
    $report.startup_registered = (Get-ItemPropertyValue -LiteralPath $runKey -Name $name) -like ('"' + $exe + '" --background*')
    $report.foreign_startup_preserved_on_install = (Get-ItemProperty -LiteralPath $runKey).PSObject.Properties[$sentinelName].Value -eq $sentinelValue
    $report.installed_apps_registered = Test-Path -LiteralPath ('HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\' + $name)
    $programLink = Join-Path ([Environment]::GetFolderPath('Programs')) ($name + '.lnk')
    $report.start_menu_registered = Test-Path -LiteralPath $programLink
    'unrelated file' | Set-Content -LiteralPath (Join-Path $app 'user-note.txt')
    'save data' | Set-Content -LiteralPath (Join-Path $data 'keep.txt')
    'import sqlite3,sys; from datetime import date; d=sqlite3.connect(sys.argv[1]); d.execute("INSERT INTO game_preferences VALUES (?,?)",("test:hidden",1)); d.execute("INSERT INTO overrides VALUES (?,?)",("test:hidden",0)); d.execute("INSERT INTO usage VALUES (?,?,?)",(date.today().isoformat(),"test:hidden",123)); d.commit()' | & $PythonPath -B - (Join-Path $data 'usage.sqlite3')
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
    # Reproduce a resident helper still mapping an identical runtime DLL.
    $lockedRuntime = Join-Path $app '_internal\VCRUNTIME140_1.dll'
    $runtimeHash = (Get-FileHash -LiteralPath $lockedRuntime).Hash
    $runtimeLock = [IO.File]::Open($lockedRuntime,[IO.FileMode]::Open,[IO.FileAccess]::Read,[IO.FileShare]::Read)
    try {
        & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $setup -InstallDir $app -DataDir $data -GamesRoot $games -DesktopDir $desktop -StartupName $name -Quiet -NoStart
        if ($LASTEXITCODE -ne 0) { throw 'Upgrade failed with an unchanged locked runtime DLL.' }
        $report.locked_unchanged_runtime_preserved = (Get-FileHash -LiteralPath $lockedRuntime).Hash -eq $runtimeHash
    } finally { $runtimeLock.Dispose() }
    # Run the actual frozen startup migration, with cloud sync disabled.
    $securityGui=Start-Process -FilePath $exe -ArgumentList @('--background','--data-dir',('"'+$data+'"')) -WindowStyle Hidden -PassThru
    try {
        Start-Sleep -Seconds 2
        $stop=Start-Process -FilePath $exe -ArgumentList @('--stop-wait','20','--data-dir',('"'+$data+'"')) -WindowStyle Hidden -Wait -PassThru
        if ($stop.ExitCode -ne 0 -or -not $securityGui.WaitForExit(10000)) { throw 'Frozen credential migration did not stop safely.' }
    } finally { if (-not $securityGui.HasExited) { Stop-Process -Id $securityGui.Id -Force } }
    $credentialCheck=@'
import json,sqlite3,sys
from pathlib import Path
from gametime.secrets import PREFIX,unprotect
from gametime.statistics_sync import local_group
p=Path(sys.argv[1]); d=sqlite3.connect(p); code='1'*32
c=json.loads(d.execute("SELECT value FROM settings WHERE key='config'").fetchone()[0])
print(c['statistics_sync_group'].startswith(PREFIX) and unprotect(c['statistics_sync_group'])==code and not c['statistics_sync_enabled'])
print(d.execute('SELECT name,revision FROM statistics_devices WHERE group_id=?',(local_group(code),)).fetchone()==('Other fixture PC',99) and d.execute('SELECT seconds FROM statistics_remote WHERE group_id=?',(local_group(code),)).fetchone()==(120.0,))
d.close()
'@ | & $PythonPath -B - (Join-Path $data 'usage.sqlite3')
    $report.windows_credential_protected_on_upgrade=$credentialCheck[0] -eq 'True'
    $report.cached_statistics_migrated_on_upgrade=$credentialCheck[1] -eq 'True'
    $process = Start-Process -FilePath $exe -ArgumentList @('--diagnose','--data-dir',('"' + $data + '"'),'--report',('"' + $diag + '"')) -WindowStyle Hidden -Wait -PassThru
    $report.obsolete_owned_file_removed = -not (Test-Path -LiteralPath $obsoleteOwned)
    $report.modified_obsolete_file_preserved = (Get-Content -LiteralPath $obsoleteEdited) -eq 'user modified document'
    $report.language_preserved_on_upgrade = (Get-Content -LiteralPath $diag -Raw -Encoding UTF8 | ConvertFrom-Json).language -eq 'hu'
    $overlayConfig = 'import json,sqlite3,sys; d=sqlite3.connect(sys.argv[1]); c=json.loads(d.execute("SELECT value FROM settings WHERE key=?",("config",)).fetchone()[0]); print(c["restriction_enabled"] and c["restriction_seconds"]==7500 and c["overlay_enabled"] and c["overlay_replace_warning"] and not c["limit_popup_enabled"] and c["overlay_opacity"]==0.55 and c["overlay_font_size"]==48 and c["overlay_x"]==0.2 and c["overlay_y"]==0.8 and c["overlay_screen"]=="missing-fixture-monitor")' | & $PythonPath -B - (Join-Path $data 'usage.sqlite3')
    $report.overlay_and_restriction_preferences_preserved_on_upgrade = $overlayConfig -eq 'True'
    $personalConfig = 'import json,sqlite3,sys; d=sqlite3.connect(sys.argv[1]); c=json.loads(d.execute("SELECT value FROM settings WHERE key=?",("config",)).fetchone()[0]); print(c["overlay_color_normal"]=="#12ab34" and c["overlay_color_warning"]=="#bc56ef" and c["notification_messages"]=={"warning":"Fixture: {remaining} min left","bedtime":"Sleep well"})' | & $PythonPath -B - (Join-Path $data 'usage.sqlite3')
    $report.personal_messages_and_countdown_colors_preserved_on_upgrade = $personalConfig -eq 'True'
    $customConfig = 'import json,sqlite3,sys; d=sqlite3.connect(sys.argv[1]); c=json.loads(d.execute("SELECT value FROM settings WHERE key=?",("config",)).fetchone()[0]); print(c["notification_sound"]=="silent" and c["notification_sound_path"]==r"C:\Fixture\saved.wav" and c["weekend_enabled"] and c["weekend_schedule"]=={"limit_seconds":10800,"warning_seconds":9000,"bedtime_minute":60,"bedtime_resume_minute":480} and c["game_overlays"]=={"test:hidden":{"overlay_enabled":False,"overlay_font_size":36,"overlay_x":0.1,"overlay_y":0.9,"overlay_color_normal":"#aabbcc","overlay_color_warning":"#dd5566"}})' | & $PythonPath -B - (Join-Path $data 'usage.sqlite3')
    $report.sound_weekend_and_game_preferences_preserved_on_upgrade = $customConfig -eq 'True'
    $dailyConfig = 'import json,sqlite3,sys; d=sqlite3.connect(sys.argv[1]); c=json.loads(d.execute("SELECT value FROM settings WHERE key=?",("config",)).fetchone()[0]); print(c["daily_schedules"]=={"1":{"limit_seconds":13200,"warning_seconds":12000,"bedtime_minute":90}})' | & $PythonPath -B - (Join-Path $data 'usage.sqlite3')
    $report.weekly_day_preferences_preserved_on_upgrade = $dailyConfig -eq 'True'
    $gameCaps = 'import json,sqlite3,sys; d=sqlite3.connect(sys.argv[1]); c=json.loads(d.execute("SELECT value FROM settings WHERE key=?",("config",)).fetchone()[0]); print(c["game_limits"]=={"test:hidden":1800})' | & $PythonPath -B - (Join-Path $data 'usage.sqlite3')
    $report.per_game_limits_preserved_on_upgrade = $gameCaps -eq 'True'

    $report.bedtime_preferences_preserved_on_upgrade = (Get-Content -LiteralPath $diag -Raw -Encoding UTF8 | ConvertFrom-Json).bedtime_minute -eq 30 -and (Get-Content -LiteralPath $diag -Raw -Encoding UTF8 | ConvertFrom-Json).bedtime_minimize
    $report.bedtime_budget_preference_preserved_on_upgrade = (Get-Content -LiteralPath $diag -Raw -Encoding UTF8 | ConvertFrom-Json).bedtime_caps_budget -eq $true
    $report.update_check_preference_preserved_on_upgrade = (Get-Content -LiteralPath $diag -Raw -Encoding UTF8 | ConvertFrom-Json).check_updates -eq $false
    $rtssConfig = 'import json,sqlite3,sys; d=sqlite3.connect(sys.argv[1]); c=json.loads(d.execute("SELECT value FROM settings WHERE key=?",("config",)).fetchone()[0]); print(c["overlay_rtss_auto"] is False and c["overlay_rtss_paths"]==[r"C:\Fixture\game.exe"])' | & $PythonPath -B - (Join-Path $data 'usage.sqlite3')
    $report.rtss_selection_preserved_on_upgrade = $rtssConfig -eq 'True'
    $trackingStartAfter = 'import sqlite3,sys; d=sqlite3.connect(sys.argv[1]); print(d.execute("SELECT value FROM settings WHERE key=?",("tracking_started_on",)).fetchone()[0])' | & $PythonPath -B - (Join-Path $data 'usage.sqlite3')
    $report.tracking_start_preserved_on_upgrade = $trackingStartAfter -eq $trackingStart
    $upgradedHub = $shell.CreateShortcut($hubPath)
    $report.old_desktop_entries_consolidated = -not (Test-Path -LiteralPath $legacyDesktop) -and $upgradedHub.TargetPath -eq $exe -and $upgradedHub.Arguments.StartsWith('--hub ')
    $report.foreign_desktop_file_preserved = (Get-Content -LiteralPath $foreign) -eq 'preserve'
    $value = 'import sqlite3,sys; d=sqlite3.connect(sys.argv[1]); print(d.execute("SELECT hidden FROM game_preferences WHERE game_id=?",("test:hidden",)).fetchone()[0]); print(d.execute("SELECT seconds FROM usage WHERE game_id=?",("test:hidden",)).fetchone()[0])' | & $PythonPath -B - (Join-Path $data 'usage.sqlite3')
    $report.upgrade_preserves_hidden_and_history = $value[0] -eq '1' -and [double]$value[1] -eq 123
    $excluded = 'import sqlite3,sys; d=sqlite3.connect(sys.argv[1]); print(d.execute("SELECT enabled FROM overrides WHERE game_id=?",("test:hidden",)).fetchone()==(0,))' | & $PythonPath -B - (Join-Path $data 'usage.sqlite3')
    $report.upgrade_preserves_per_game_exclusions = $LASTEXITCODE -eq 0 -and $excluded -eq 'True'
    $clients = 'import json,sqlite3,sys; d=sqlite3.connect(sys.argv[1]); print(json.loads(d.execute("SELECT value FROM settings WHERE key=?",("launcher_clients",)).fetchone()[0])=={"version":1,"clients":[]})' | & $PythonPath -B - (Join-Path $data 'usage.sqlite3')
    $report.upgrade_preserves_remembered_launchers = $LASTEXITCODE -eq 0 -and $clients -eq 'True'
    $computerName = 'import json,sqlite3,sys; d=sqlite3.connect(sys.argv[1]); print(json.loads(d.execute("SELECT value FROM settings WHERE key=?",("config",)).fetchone()[0])["statistics_device_name"]=="Fixture Desktop")' | & $PythonPath -B - (Join-Path $data 'usage.sqlite3')
    $report.upgrade_preserves_computer_name = $LASTEXITCODE -eq 0 -and $computerName -eq 'True'
    $deviceAlias = 'import sqlite3,sys; from gametime.statistics_sync import local_group; d=sqlite3.connect(sys.argv[1]); print(d.execute("SELECT value FROM settings WHERE key=?",("statistics_device_alias:"+local_group("1"*32)+":"+"a"*32,)).fetchone()==("Fixture Laptop",))' | & $PythonPath -B - (Join-Path $data 'usage.sqlite3')
    $report.upgrade_preserves_linked_computer_name = $LASTEXITCODE -eq 0 -and $deviceAlias -eq 'True'
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
