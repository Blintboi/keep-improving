param(
    [string]$SdkPath = "$env:LOCALAPPDATA/Android/Sdk",
    [string]$JavaPath = $env:JAVA_HOME,
    [string]$PythonPath = "$PSScriptRoot/../build/venv-security/Scripts/python.exe",
    [string]$GradlePath = "$PSScriptRoot/gradlew.bat"
)
$ErrorActionPreference = 'Stop'
$repo = Split-Path $PSScriptRoot -Parent
$devRoot = Join-Path $env:LOCALAPPDATA 'KeepImprovingDev'
$projectLink = Join-Path $devRoot 'android-project'
New-Item -ItemType Directory -Force $devRoot | Out-Null
if (-not (Test-Path -LiteralPath $projectLink)) {
    New-Item -ItemType Junction -Path $projectLink -Target $PSScriptRoot | Out-Null
} elseif ([System.IO.Path]::GetFullPath([string]@((Get-Item -LiteralPath $projectLink).Target)[0]) -ne [System.IO.Path]::GetFullPath($PSScriptRoot)) {
    throw 'The Android build junction belongs to another checkout.'
}
if (-not (Test-Path "$JavaPath/bin/keytool.exe")) { throw 'Set -JavaPath to a JDK 21 installation.' }
if (-not (Test-Path "$SdkPath/platforms/android-36/android.jar")) { throw 'Android SDK platform 36 is required.' }
[System.IO.File]::WriteAllText("$PSScriptRoot/local.properties", "sdk.dir=$($SdkPath.Replace('\','/').Replace(':','\:'))`n", [System.Text.UTF8Encoding]::new($false))
$signing = Join-Path $env:LOCALAPPDATA 'KeepImprovingAndroidSigning'
New-Item -ItemType Directory -Force $signing | Out-Null
$credentialFile = Join-Path $signing 'credential.xml'
$keyFile = Join-Path $signing 'keep-improving.p12'
if (-not (Test-Path $credentialFile)) {
    if (Test-Path $keyFile) { throw 'Signing credential is missing. Preserve the existing key; restore its credential.' }
    $bytes = New-Object byte[] 32
    $generator = [System.Security.Cryptography.RandomNumberGenerator]::Create()
    try { $generator.GetBytes($bytes) } finally { $generator.Dispose() }
    $secret = ConvertTo-SecureString ([Convert]::ToBase64String($bytes)) -AsPlainText -Force
    [pscredential]::new('keepimproving', $secret) | Export-Clixml -LiteralPath $credentialFile
}
$credential = Import-Clixml -LiteralPath $credentialFile
$oldJava = $env:JAVA_HOME
$oldReadCache = $env:GRADLE_RO_DEP_CACHE
try {
    $env:JAVA_HOME = $JavaPath
    $env:GRADLE_RO_DEP_CACHE = Join-Path $env:USERPROFILE '.gradle/caches'
    $env:KI_ANDROID_KEYSTORE = $keyFile
    $env:KI_ANDROID_BUILD_ROOT = Join-Path $devRoot 'android-build'
    $env:KI_ANDROID_STORE_PASSWORD = $credential.GetNetworkCredential().Password
    if (-not (Test-Path $keyFile)) {
        & "$JavaPath/bin/keytool.exe" -genkeypair -keystore $keyFile -storetype PKCS12 -storepass:env KI_ANDROID_STORE_PASSWORD -keypass:env KI_ANDROID_STORE_PASSWORD -alias keepimproving -keyalg RSA -keysize 3072 -validity 10000 -dname 'CN=Keep Improving Android Local'
        if ($LASTEXITCODE -ne 0) { throw 'Signing key creation failed.' }
    }
    & $GradlePath -g "$devRoot/gradle" -p $projectLink --no-problems-report :app:testPreviewUnitTest :app:lintPreview :app:assemblePreview
    if ($LASTEXITCODE -ne 0) { throw 'Android checks/build failed.' }
    & $PythonPath "$PSScriptRoot/verify_interop.py" --build-dir "$env:KI_ANDROID_BUILD_ROOT/app"
    if ($LASTEXITCODE -ne 0) { throw 'Desktop interoperability check failed.' }
    $apk = "$env:KI_ANDROID_BUILD_ROOT/app/outputs/apk/preview/app-preview.apk"
    & "$SdkPath/build-tools/36.0.0/apksigner.bat" verify --verbose --print-certs $apk
    if ($LASTEXITCODE -ne 0) { throw 'APK signature verification failed.' }
    $output = Join-Path $repo 'dist/KeepImproving-Android-0.1.0.apk'
    New-Item -ItemType Directory -Force (Split-Path $output) | Out-Null
    Copy-Item -LiteralPath $apk -Destination $output -Force
    $hash = (Get-FileHash -LiteralPath $output -Algorithm SHA256).Hash.ToLowerInvariant()
    [System.IO.File]::WriteAllText("$output.sha256", "$hash  KeepImproving-Android-0.1.0.apk`n", [System.Text.UTF8Encoding]::new($false))
    Write-Output "Verified local APK: $output"
} finally {
    Remove-Item Env:KI_ANDROID_STORE_PASSWORD,Env:KI_ANDROID_KEYSTORE,Env:KI_ANDROID_BUILD_ROOT -ErrorAction SilentlyContinue
    $env:JAVA_HOME = $oldJava
    $env:GRADLE_RO_DEP_CACHE = $oldReadCache
}
