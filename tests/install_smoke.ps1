param([Parameter(Mandatory=$true)][string]$ReportPath, [string]$PythonPath)
$ErrorActionPreference = 'Stop'
$sourcePath = Split-Path -Parent $PSScriptRoot
. (Join-Path $sourcePath 'common.ps1')
$testBasePath = Join-Path ([IO.Path]::GetTempPath()) ('GameTime-install-test-' + [Guid]::NewGuid().ToString('N'))
$testInstallPath = Join-Path $testBasePath 'Install with spaces'
$testGamesPath = Join-Path $testBasePath 'Games fixture'
$testStartupName = 'GameTimeMonitor.Test.' + [Guid]::NewGuid().ToString('N')
$runKey = 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Run'
$report = [ordered]@{ IsolatedInstallDirectory = $testInstallPath }
try {
    & (Join-Path $sourcePath 'install.ps1') -PythonPath $PythonPath -InstallDir $testInstallPath -GamesRoot $testGamesPath -StartupName $testStartupName -EnableHub -NoStart
    $report.FirstInstall = Test-Path -LiteralPath (Join-Path $testInstallPath 'install.json')
    $manifest = Read-GameTimeManifest $testInstallPath
    $probePath = Join-Path $testBasePath 'seed.py'
    @'
import pathlib, sys
sys.path.insert(0, sys.argv[1])
from gametime.store import Store
store = Store(pathlib.Path(sys.argv[1]) / 'data' / 'usage.sqlite3')
store.add_usage({('2000-01-01', 'test:fixture'): 123.0})
store.set_rule(r'C:\Fixture\chess.exe', None)
store.close()
'@ | Set-Content -LiteralPath $probePath -Encoding UTF8
    & $manifest.Python -B $probePath $testInstallPath
    if ($LASTEXITCODE -ne 0) { throw 'Database seed failed.' }
    & (Join-Path $sourcePath 'install.ps1') -PythonPath $PythonPath -InstallDir $testInstallPath -GamesRoot $testGamesPath -StartupName $testStartupName -NoStart
    $report.RepeatedInstall = $true
    $probeVerifyPath = Join-Path $testBasePath 'check.py'
    @'
import pathlib, sys
sys.path.insert(0, sys.argv[1])
from gametime.store import Store
from gametime.model import norm
store = Store(pathlib.Path(sys.argv[1]) / 'data' / 'usage.sqlite3')
assert store.totals('2000-01-01') == {'test:fixture': 123.0}
assert norm(r'C:\Fixture\chess.exe') in store.rules()
assert store.rules()[norm(r'C:\Fixture\chess.exe')] is None
assert store.settings().hub_enabled is True
store.close()
'@ | Set-Content -LiteralPath $probeVerifyPath -Encoding UTF8
    & $manifest.Python -B $probeVerifyPath $testInstallPath
    if ($LASTEXITCODE -ne 0) { throw 'Reinstall did not preserve time and exceptions.' }
    $report.TimeAndExceptionsSurviveReinstall = $true
    $report.HubEnabledSurvivesReinstall = $true
    $report.AutostartMatches = (Get-GameTimeStartupValue $testStartupName) -eq $manifest.StartupCommand
    $report.StartupFolderShortcutCreated = Test-Path -LiteralPath $manifest.StartupShortcut
    $argsText = '-B "' + (Join-Path $testInstallPath 'main.py') + '" --background --data-dir "' + (Join-Path $testInstallPath 'data') + '"'
    $process = Start-Process -FilePath $manifest.Pythonw -ArgumentList $argsText -PassThru -WindowStyle Hidden
    Start-Sleep -Seconds 4
    $process.Refresh()
    $report.BackgroundStarted = -not $process.HasExited
    $cpuBefore = $process.TotalProcessorTime.TotalSeconds
    $measureStart = [DateTime]::UtcNow
    Start-Sleep -Seconds 6
    $process.Refresh()
    $report.CpuPercentOneCore = [Math]::Round(100 * ($process.TotalProcessorTime.TotalSeconds - $cpuBefore) / ([DateTime]::UtcNow - $measureStart).TotalSeconds, 3)
    $report.WorkingSetMiB = [Math]::Round($process.WorkingSet64 / 1MB, 1)
    $hubStatePath = Join-Path $testInstallPath 'data\hub-state.json'
    $hubDeadline = [DateTime]::UtcNow.AddSeconds(45)
    while (-not (Test-Path -LiteralPath $hubStatePath -PathType Leaf) -and [DateTime]::UtcNow -lt $hubDeadline) {
        Start-Sleep -Milliseconds 200
    }
    if (-not (Test-Path -LiteralPath $hubStatePath -PathType Leaf)) { throw 'Enabled Gaming Hub did not synchronize.' }
    $hubState = Get-Content -LiteralPath $hubStatePath -Raw -Encoding UTF8 | ConvertFrom-Json
    $report.HubCreatedAfterBackgroundStart = $hubState.marker -eq 'GameTimeHub.v1'
    & (Join-Path $testInstallPath 'verify.ps1') -InstallDir $testInstallPath
    $report.VerifyWhileRunning = $true
    $report.DiagnosticDidNotOpenUi = -not (Test-Path -LiteralPath (Join-Path $testInstallPath 'data\show.request'))
    $duplicate = Start-Process -FilePath $manifest.Pythonw -ArgumentList $argsText -PassThru -WindowStyle Hidden
    if (-not $duplicate.WaitForExit(10000)) { throw 'Duplicate background launch did not exit.' }
    $report.DuplicateBackgroundDidNotOpenUi = -not (Test-Path -LiteralPath (Join-Path $testInstallPath 'data\show.request'))
    # The uninstaller must preserve unrelated user files as well as the database.
    'unrelated sentinel' | Set-Content -LiteralPath (Join-Path $testInstallPath 'user-sentinel.txt')
    & (Join-Path $sourcePath 'uninstall.ps1') -InstallDir $testInstallPath
    $process.WaitForExit(10000) | Out-Null
    $report.GracefulBackgroundStop = $process.HasExited
    $report.AutostartRemoved = -not (Get-GameTimeStartupValue $testStartupName)
    $report.StartupFolderShortcutRemoved = -not (Test-Path -LiteralPath $manifest.StartupShortcut)
    $report.DatabasePreserved = Test-Path -LiteralPath (Join-Path $testInstallPath 'data\usage.sqlite3')
    $report.UserFilesPreserved = Test-Path -LiteralPath (Join-Path $testInstallPath 'user-sentinel.txt')
    $report.OwnedCodeRemoved = -not (Test-Path -LiteralPath (Join-Path $testInstallPath 'main.py'))
    & (Join-Path $sourcePath 'uninstall.ps1') -InstallDir $testInstallPath
    $report.IdempotentUninstall = $true
} finally {
    if (Test-Path -LiteralPath (Join-Path $testInstallPath 'main.py') -PathType Leaf) {
        & (Join-Path $sourcePath 'uninstall.ps1') -InstallDir $testInstallPath
    }
    if (Get-GameTimeStartupValue $testStartupName) {
        Remove-ItemProperty -LiteralPath $runKey -Name $testStartupName
    }
    $reportDirectory = Split-Path -Parent ([IO.Path]::GetFullPath($ReportPath))
    [IO.Directory]::CreateDirectory($reportDirectory) | Out-Null
    $report | ConvertTo-Json | Set-Content -LiteralPath $ReportPath -Encoding UTF8
}
$report | ConvertTo-Json
if (@($report.Values | Where-Object { $_ -is [bool] -and -not $_ }).Count) { throw 'Install test assertion failed.' }
