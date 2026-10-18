param(
    [string]$PythonPath = 'python.exe',
    [string]$OutputDir = (Join-Path $PSScriptRoot '..\dist'),
    [string]$BuildDir = (Join-Path $PSScriptRoot '..\build'),
    [switch]$SkipFreeze,
    [switch]$FreezeOnly
)
$ErrorActionPreference = 'Stop'
$repo = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$OutputDir = [IO.Path]::GetFullPath($OutputDir)
$BuildDir = [IO.Path]::GetFullPath($BuildDir)
New-Item -ItemType Directory -Path $OutputDir,$BuildDir -Force | Out-Null
$version = (& $PythonPath -B -c "import sys; sys.path.insert(0,sys.argv[1]); from gametime import __version__; print(__version__)" $repo).Trim()
if (-not $SkipFreeze) {
    # Build tools must not resolve Qt dependencies from unrelated programs on PATH.
    $pythonQuery = 'import sys,json; print(json.dumps({"executable":sys.executable,"base":sys.base_prefix}))'
    $pythonInfo = ($pythonQuery | & $PythonPath -) | ConvertFrom-Json
    $PythonPath = $pythonInfo.executable
    $savedBuildPath = $env:PATH
    try {
        $env:PATH = @((Split-Path -Parent $PythonPath), $pythonInfo.base, (Join-Path $pythonInfo.base 'DLLs'),
                      (Join-Path $env:WINDIR 'System32'), $env:WINDIR, (Join-Path $env:WINDIR 'System32\WindowsPowerShell\v1.0')) -join ';'
        & $PythonPath -B -m PyInstaller --noconfirm --clean --onedir --windowed --name GameTimeMonitor --icon (Join-Path $repo 'gametime\app.ico') --add-data ((Join-Path $repo 'gametime\app.ico') + ':gametime') --add-data ((Join-Path $repo 'gametime\hub_links.ps1') + ':gametime') --add-data ((Join-Path $repo 'gametime\icons') + ':gametime/icons') --distpath (Join-Path $BuildDir 'frozen') --workpath (Join-Path $BuildDir 'pyinstaller') --specpath $BuildDir (Join-Path $repo 'main.py')
        if ($LASTEXITCODE -ne 0) { throw 'PyInstaller build failed.' }
    } finally { $env:PATH = $savedBuildPath }

}
$bundle = Join-Path $BuildDir 'frozen\GameTimeMonitor'
if (Test-Path -LiteralPath (Join-Path $bundle '_internal\icuuc.dll')) { throw 'Unexpected app-local ICU: Qt on Windows 11 must use the Windows ICU runtime.' }
if ($FreezeOnly) { Write-Output $bundle; return }
Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'uninstall-bundled.ps1') -Destination $bundle
foreach ($name in @('README.md','README.hu.md','TESTING.md','ARCHITECTURE.md','THIRD-PARTY-NOTICES.md')) {
    Copy-Item -LiteralPath (Join-Path $repo $name) -Destination $bundle
}
$licenseDir = Join-Path $bundle 'licenses'
New-Item -ItemType Directory -Path $licenseDir -Force | Out-Null
$pythonBase = (& $PythonPath -c 'import sys; print(sys.base_prefix)').Trim()
Copy-Item -LiteralPath (Join-Path $pythonBase 'LICENSE.txt') -Destination (Join-Path $licenseDir 'Python-LICENSE.txt')
Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'licenses\Qt') -Destination $licenseDir -Recurse -Force
$licenseQuery = 'import importlib.metadata as m; print(m.distribution("pyinstaller").locate_file("pyinstaller-6.22.0.dist-info/licenses/COPYING.txt"))'
$pyinstallerLicense = ($licenseQuery | & $PythonPath -).Trim()
if (-not (Test-Path -LiteralPath $pyinstallerLicense)) { throw 'PyInstaller license was not found.' }
Copy-Item -LiteralPath $pyinstallerLicense -Destination (Join-Path $licenseDir 'PyInstaller-COPYING.txt')
$files = @(Get-ChildItem -LiteralPath $bundle -Recurse -File | Where-Object { $_.Name -ne 'payload-manifest.json' } | ForEach-Object {
    [ordered]@{ Path=$_.FullName.Substring($bundle.Length + 1); SHA256=(Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash }
})
[ordered]@{Version=$version;Files=$files} | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath (Join-Path $bundle 'payload-manifest.json') -Encoding UTF8
$package = Join-Path $BuildDir 'package'
New-Item -ItemType Directory -Path $package -Force | Out-Null
$payloadZip = Join-Path $package 'payload.zip'
if (Test-Path -LiteralPath $payloadZip) { Remove-Item -LiteralPath $payloadZip }
Add-Type -AssemblyName System.IO.Compression.FileSystem
[IO.Compression.ZipFile]::CreateFromDirectory($bundle, $payloadZip, [IO.Compression.CompressionLevel]::Optimal, $false)
Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'setup.ps1'),(Join-Path $PSScriptRoot 'setup.cmd') -Destination $package -Force
$setup = Join-Path $OutputDir ('GameTimeMonitor-' + $version + '-Setup.exe')
# IExpress silently fails with some long source/output paths. Build its small
# cabinet in a short temporary folder, then copy the result to the requested path.
$cabRoot = Join-Path $env:TEMP ('gtm-cab-' + [guid]::NewGuid().ToString('N').Substring(0,8))
New-Item -ItemType Directory -Path $cabRoot -Force | Out-Null
Copy-Item -LiteralPath $payloadZip,(Join-Path $package 'setup.ps1'),(Join-Path $package 'setup.cmd') -Destination $cabRoot
$cabExe = Join-Path $cabRoot 'Setup.exe'
$sed = Join-Path $cabRoot 'installer.sed'
@"
[Version]
Class=IEXPRESS
SEDVersion=3
[Options]
PackagePurpose=InstallApp
ShowInstallProgramWindow=0
HideExtractAnimation=0
UseLongFileName=1
InsideCompressed=0
CAB_FixedSize=0
CAB_ResvCodeSigning=0
RebootMode=N
InstallPrompt=%InstallPrompt%
DisplayLicense=%DisplayLicense%
FinishMessage=%FinishMessage%
TargetName=%TargetName%
FriendlyName=%FriendlyName%
AppLaunched=%AppLaunched%
PostInstallCmd=%PostInstallCmd%
AdminQuietInstCmd=%AdminQuietInstCmd%
UserQuietInstCmd=%UserQuietInstCmd%
SourceFiles=SourceFiles
[Strings]
InstallPrompt=
DisplayLicense=
FinishMessage=
TargetName=$cabExe
FriendlyName=Game Time Monitor $version Setup
AppLaunched=cmd.exe /d /c setup.cmd
PostInstallCmd=<None>
AdminQuietInstCmd=cmd.exe /d /c setup.cmd -Quiet
UserQuietInstCmd=cmd.exe /d /c setup.cmd -Quiet
FILE0="payload.zip"
FILE1="setup.ps1"
FILE2="setup.cmd"
[SourceFiles]
SourceFiles0=$cabRoot\
[SourceFiles0]
%FILE0%=
%FILE1%=
%FILE2%=
"@ | Set-Content -LiteralPath $sed -Encoding ASCII
try {
    # This legacy tool rejects a quoted SED argument. A relative filename avoids
    # both that parser bug and spaces in a Windows user profile path.
    $builder = Start-Process -FilePath (Join-Path $env:WINDIR 'System32\iexpress.exe') -ArgumentList @('/N','/Q','installer.sed') -WindowStyle Hidden -WorkingDirectory $cabRoot -PassThru -Wait
    if ($builder.ExitCode -ne 0 -or -not (Test-Path -LiteralPath $cabExe)) {
        Copy-Item -LiteralPath $sed -Destination (Join-Path $BuildDir 'failed-installer.sed') -Force
        throw "IExpress installer build failed (exit $($builder.ExitCode)). See failed-installer.sed in the build directory."
    }
    Copy-Item -LiteralPath $cabExe -Destination $setup -Force
} finally {
    if ([IO.Path]::GetFullPath($cabRoot).StartsWith([IO.Path]::GetFullPath($env:TEMP) + '\', [StringComparison]::OrdinalIgnoreCase)) {
        Remove-Item -LiteralPath $cabRoot -Recurse -Force
    }
}
$iconScript = 'import sys; from PyInstaller.utils.win32.icon import CopyIcons_FromIco; CopyIcons_FromIco(sys.argv[1], [sys.argv[2]])'
$iconScript | & $PythonPath - $setup (Join-Path $repo 'gametime\app.ico')
if ($LASTEXITCODE -ne 0) { throw 'Installer icon update failed.' }
$hash = (Get-FileHash -LiteralPath $setup -Algorithm SHA256).Hash.ToLowerInvariant()
($hash + '  ' + [IO.Path]::GetFileName($setup)) | Set-Content -LiteralPath ($setup + '.sha256') -Encoding ASCII
Write-Output $setup
