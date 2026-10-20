Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Get-GameTimeDirectory {
    [IO.Path]::Combine([Environment]::GetFolderPath('MyDocuments'), 'GameTimeMonitor')
}

function Get-GameTimeStartupValue([string]$Name) {
    $key = [Microsoft.Win32.Registry]::CurrentUser.OpenSubKey('Software\Microsoft\Windows\CurrentVersion\Run')
    try {
        if ($null -eq $key) { return $null }
        return $key.GetValue($Name, $null, [Microsoft.Win32.RegistryValueOptions]::DoNotExpandEnvironmentNames)
    } finally {
        if ($null -ne $key) { $key.Dispose() }
    }
}

function Get-GameTimeStartupLink([string]$Name) {
    Join-Path ([Environment]::GetFolderPath('Startup')) ($Name + '.lnk')
}

function Set-GameTimeStartupLink([string]$Name, [string]$Pythonw, [string]$Arguments, [string]$Directory) {
    $path = Get-GameTimeStartupLink $Name
    $shell = New-Object -ComObject WScript.Shell
    $link = $shell.CreateShortcut($path)
    if ((Test-Path -LiteralPath $path) -and $link.Description -ne 'GameTimeMonitor.v1 startup') {
        throw 'An unrelated startup shortcut was preserved.'
    }
    $link.TargetPath = $Pythonw
    $link.Arguments = $Arguments
    $link.WorkingDirectory = $Directory
    $link.Description = 'GameTimeMonitor.v1 startup'
    $link.WindowStyle = 7
    $link.Save()
    $check = $shell.CreateShortcut($path)
    if ($check.TargetPath -ine $Pythonw -or $check.Arguments -cne $Arguments) {
        throw 'Startup shortcut readback failed.'
    }
    return $path
}

function Get-GameTimePython([string]$PythonPath) {
    $probe = 'import sys,sqlite3,pathlib; from PySide6.QtWidgets import QApplication; from cryptography.hazmat.primitives.ciphers.aead import AESGCM; assert sys.version_info >= (3,10); print(pathlib.Path(sys.executable).resolve())'
    $candidates = @()
    if ($PythonPath) {
        $candidates += [PSCustomObject]@{ Path = (Resolve-Path -LiteralPath $PythonPath).Path; Args = @() }
    } else {
        foreach ($name in @('py.exe','python.exe')) {
            $command = Get-Command $name -ErrorAction SilentlyContinue
            if ($command) {
                $prefix = @()
                if ($name -eq 'py.exe') { $prefix = @('-3') }
                $candidates += [PSCustomObject]@{ Path = $command.Source; Args = $prefix }
            }
        }
    }
    foreach ($candidate in $candidates) {
        $arguments = @($candidate.Args) + @('-c', $probe)
        try {
            $result = & $candidate.Path @arguments 2>&1
            if ($LASTEXITCODE -ne 0) { continue }
            $resolved = [string]($result | Select-Object -Last 1)
            $pythonw = Join-Path (Split-Path -Parent $resolved) 'pythonw.exe'
            if (Test-Path -LiteralPath $pythonw -PathType Leaf) {
                return [PSCustomObject]@{ Python = $resolved; Pythonw = $pythonw }
            }
        } catch { continue }
    }
    throw 'Python 3.10+ with PySide6 is required. Run python -m pip install -r requirements-runtime.txt, or use the standalone Setup. Pass -PythonPath to select a prepared environment.'
}

function Build-GameTimeRTSSBridge([string]$SourceRoot) {
    $source = Join-Path $SourceRoot 'gametime\rtss_bridge.cs'
    $output = Join-Path $SourceRoot 'gametime\rtss_bridge.exe'
    $hashPath = $output + '.sha256'
    $hasher = [Security.Cryptography.SHA256]::Create()
    try { $sourceHash = [BitConverter]::ToString($hasher.ComputeHash([IO.File]::ReadAllBytes($source))).Replace('-','') }
    finally { $hasher.Dispose() }
    if ((Test-Path -LiteralPath $output) -and (Test-Path -LiteralPath $hashPath) -and
        (Get-Content -LiteralPath $hashPath -Raw).Trim() -eq $sourceHash) { return }
    $compiler = Join-Path $env:WINDIR 'Microsoft.NET\Framework64\v4.0.30319\csc.exe'
    if (-not (Test-Path -LiteralPath $compiler)) { throw 'The Windows .NET Framework 4 compiler is required to build the optional RTSS bridge.' }
    & $compiler /nologo /unsafe /optimize+ /platform:anycpu /target:exe /r:System.Web.Extensions.dll (('/out:' + $output)) $source
    if ($LASTEXITCODE -ne 0) { throw 'RTSS bridge compilation failed.' }
    $sourceHash | Set-Content -LiteralPath $hashPath -Encoding ascii
}

function Get-GameTimeFiles {
    @('SECURITY.md','requirements-runtime.lock')
    @('gametime\statistics_auth.py','gametime\qt_account.py')
    @('gametime\artwork.py','gametime\clients.py','gametime\overlay.py','gametime\rtss.py','gametime\rtss_bridge.cs','gametime\rtss_bridge.exe','gametime\rtss_bridge.exe.sha256','requirements-runtime.txt','gametime\controller.py','gametime\qt_ui.py','gametime\qt_widgets.py','gametime\qt_statistics.py','gametime\icons\chevron.svg','gametime\icons\check.svg','main.py','gametime\__init__.py','gametime\model.py','gametime\discovery.py',
      'gametime\store.py','gametime\secrets.py','gametime\tracker.py','gametime\service.py','gametime\win32.py','gametime\i18n.py','gametime\statistics.py','gametime\statistics_ui.py',
      'gametime\ui.py','gametime\statistics_sync.py','gametime\statistics_cloud.py','gametime\launch.py','gametime\removal.py','gametime\ubisoft.py','gametime\riot.py','gametime\minecraft.py','gametime\hub.py','gametime\hub_links.ps1','gametime\app.ico','gametime\app.png','common.ps1','install.ps1','uninstall.ps1','launch.ps1','verify.ps1',
      'Telepites.cmd','Eltavolitas.cmd','Inditas.cmd','Ellenorzes.cmd','README.md','README.hu.md','TESTING.md','ARCHITECTURE.md','THIRD-PARTY-NOTICES.md','TESZTELES.md','TESZTEREDMENYEK.txt')
}

function Read-GameTimeManifest([string]$Directory) {
    $file = Join-Path $Directory 'install.json'
    if (-not (Test-Path -LiteralPath $file -PathType Leaf)) { return $null }
    $manifest = Get-Content -LiteralPath $file -Raw -Encoding UTF8 | ConvertFrom-Json
    if ($manifest.Marker -ne 'GameTimeMonitor.v1' -or
        [IO.Path]::GetFullPath($manifest.InstallDir) -ne [IO.Path]::GetFullPath($Directory)) {
        throw 'Installation marker is invalid; nothing was changed.'
    }
    return $manifest
}

function Get-GameTimeBundle([string]$DataDir) {
    $entry = Get-ItemProperty -LiteralPath 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\GameTimeMonitor' -ErrorAction SilentlyContinue
    if (-not $entry -or -not $entry.PSObject.Properties['InstallLocation']) { return $null }
    $root = $entry.InstallLocation
    $path = Join-Path $root 'bundle-install.json'
    if (-not (Test-Path -LiteralPath $path)) { return $null }
    $bundle = Get-Content -LiteralPath $path -Raw -Encoding UTF8 | ConvertFrom-Json
    if ($bundle.Marker -eq 'GameTimeMonitor.bundle.v1' -and [IO.Path]::GetFullPath($bundle.InstallDir) -eq [IO.Path]::GetFullPath($root) -and
        [IO.Path]::GetFullPath($bundle.DataDir) -eq [IO.Path]::GetFullPath($DataDir)) { return $bundle }
    return $null
}
