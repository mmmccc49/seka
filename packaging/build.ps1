param(
    [string]$Version = "1.0.0",
    [switch]$SkipInstaller
)

$ErrorActionPreference = "Stop"

$Root = Resolve-Path (Join-Path $PSScriptRoot "..")
$VenvPython = Join-Path $Root ".venv-build\Scripts\python.exe"
$VenvPyInstaller = Join-Path $Root ".venv-build\Scripts\pyinstaller.exe"
$DistDir = Join-Path $Root "dist"
$BuildDir = Join-Path $Root "build"
$PortableZip = Join-Path $DistDir "ColorMarkStudio-portable-$Version.zip"
$SetupExe = Join-Path $DistDir "ColorMarkStudio-Setup-$Version.exe"
$IconPath = Join-Path $Root "assets\app_icon.ico"

if (-not (Test-Path $VenvPython)) {
    python -m venv (Join-Path $Root ".venv-build")
}

& $VenvPython -m pip install -r (Join-Path $Root "requirements.txt") pyinstaller pywin32

$env:QT_QPA_PLATFORM = "offscreen"
& $VenvPython (Join-Path $Root "packaging\make_icon.py")
Remove-Item Env:\QT_QPA_PLATFORM -ErrorAction SilentlyContinue

if (Test-Path $DistDir) {
    Remove-Item -LiteralPath $DistDir -Recurse -Force
}
if (Test-Path $BuildDir) {
    Remove-Item -LiteralPath $BuildDir -Recurse -Force
}

& $VenvPyInstaller `
    --noconfirm `
    --clean `
    --onefile `
    --windowed `
    --name "ColorMarkStudio" `
    --icon "$IconPath" `
    --add-data "$Root\README.md;." `
    --add-data "$Root\assets;assets" `
    (Join-Path $Root "main.py")

$AppExe = Join-Path $DistDir "ColorMarkStudio.exe"
if (-not (Test-Path $AppExe)) {
    throw "PyInstaller did not create $AppExe"
}

Compress-Archive -Path $AppExe, (Join-Path $Root "README.md") -DestinationPath $PortableZip -Force

if ($SkipInstaller) {
    Write-Host "Portable executable: $AppExe"
    Write-Host "Portable zip:        $PortableZip"
    exit 0
}

& $VenvPyInstaller `
    --noconfirm `
    --clean `
    --onefile `
    --windowed `
    --name "ColorMarkStudio-Setup-$Version" `
    --icon "$IconPath" `
    --add-binary "$AppExe;." `
    --add-data "$Root\README.md;." `
    --add-data "$IconPath;." `
    (Join-Path $Root "packaging\installer_main.py")

if (-not (Test-Path $SetupExe)) {
    throw "PyInstaller did not create $SetupExe"
}

Write-Host "Portable executable: $AppExe"
Write-Host "Portable zip:        $PortableZip"
Write-Host "Installer:           $SetupExe"
