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
    $probe = 'import sys,tkinter,sqlite3,pathlib; assert sys.version_info >= (3,9); tkinter.Tcl(); print(pathlib.Path(sys.executable).resolve())'
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
    throw 'Python 3.9+ with Tkinter and SQLite is required. Install it from python.org, or pass -PythonPath C:\path\python.exe. No pip packages are required.'
}

function Get-GameTimeFiles {
    @('main.py','gametime\__init__.py','gametime\model.py','gametime\discovery.py',
      'gametime\store.py','gametime\tracker.py','gametime\service.py','gametime\win32.py',
      'gametime\ui.py','gametime\ubisoft.py','gametime\riot.py','gametime\minecraft.py','gametime\hub.py','gametime\hub_links.ps1','gametime\app.ico','common.ps1','install.ps1','uninstall.ps1','launch.ps1','verify.ps1',
      'Telepites.cmd','Eltavolitas.cmd','Inditas.cmd','Ellenorzes.cmd','README.md','TESZTELES.md','TESZTEREDMENYEK.txt')
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
