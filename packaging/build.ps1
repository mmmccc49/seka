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
$IExpressWorkDir = Join-Path $env:TEMP "ColorMarkStudioBuild"
$StageDir = Join-Path $IExpressWorkDir "stage"
$SetupExe = Join-Path $DistDir "ColorMarkStudio-Setup-$Version.exe"
$TempSetupExe = Join-Path $IExpressWorkDir "ColorMarkStudio-Setup-$Version.exe"
$PortableZip = Join-Path $DistDir "ColorMarkStudio-portable-$Version.zip"

if (-not (Test-Path $VenvPython)) {
    python -m venv (Join-Path $Root ".venv-build")
}

& $VenvPython -m pip install -r (Join-Path $Root "requirements.txt") pyinstaller

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
    --add-data "$Root\README.md;." `
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

$IExpress = (Get-Command iexpress.exe -ErrorAction SilentlyContinue).Source
if (-not $IExpress) {
    Write-Warning "IExpress was not found. Portable build is ready, but setup EXE was skipped."
    Write-Host "Portable executable: $AppExe"
    Write-Host "Portable zip:        $PortableZip"
    exit 0
}

if (Test-Path $IExpressWorkDir) {
    Remove-Item -LiteralPath $IExpressWorkDir -Recurse -Force
}
New-Item -ItemType Directory -Force -Path $StageDir | Out-Null
Copy-Item -LiteralPath $AppExe -Destination (Join-Path $StageDir "ColorMarkStudio.exe") -Force

$InstallPs1 = @'
$ErrorActionPreference = "Stop"

$AppName = "ColorMark Studio"
$ExeName = "ColorMarkStudio.exe"
$InstallDir = Join-Path $env:LOCALAPPDATA "Programs\ColorMark Studio"
$SourceExe = Join-Path $PSScriptRoot $ExeName

New-Item -ItemType Directory -Force -Path $InstallDir | Out-Null
Copy-Item -LiteralPath $SourceExe -Destination (Join-Path $InstallDir $ExeName) -Force

$Shell = New-Object -ComObject WScript.Shell
$Programs = [Environment]::GetFolderPath("Programs")
$StartMenuShortcut = Join-Path $Programs "$AppName.lnk"
$Shortcut = $Shell.CreateShortcut($StartMenuShortcut)
$Shortcut.TargetPath = Join-Path $InstallDir $ExeName
$Shortcut.WorkingDirectory = $InstallDir
$Shortcut.Description = "Desktop color picker and palette tool"
$Shortcut.Save()

$Desktop = [Environment]::GetFolderPath("DesktopDirectory")
$DesktopShortcut = Join-Path $Desktop "$AppName.lnk"
$Shortcut = $Shell.CreateShortcut($DesktopShortcut)
$Shortcut.TargetPath = Join-Path $InstallDir $ExeName
$Shortcut.WorkingDirectory = $InstallDir
$Shortcut.Description = "Desktop color picker and palette tool"
$Shortcut.Save()

Start-Process -FilePath (Join-Path $InstallDir $ExeName)
'@

$InstallCmd = @'
@echo off
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0install.ps1"
exit /b %ERRORLEVEL%
'@

Set-Content -LiteralPath (Join-Path $StageDir "install.ps1") -Value $InstallPs1 -Encoding UTF8
Set-Content -LiteralPath (Join-Path $StageDir "install.cmd") -Value $InstallCmd -Encoding ASCII

$SedPath = Join-Path $IExpressWorkDir "ColorMarkStudio.sed"
$Sed = @"
[Version]
Class=IEXPRESS
SEDVersion=3

[Options]
PackagePurpose=InstallApp
ShowInstallProgramWindow=0
HideExtractAnimation=1
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
FinishMessage=ColorMark Studio has been installed.
TargetName=$TempSetupExe
FriendlyName=ColorMark Studio Setup
AppLaunched=install.cmd
PostInstallCmd=<None>
AdminQuietInstCmd=install.cmd
UserQuietInstCmd=install.cmd
FILE0="ColorMarkStudio.exe"
FILE1="install.cmd"
FILE2="install.ps1"

[SourceFiles]
SourceFiles0=$StageDir\

[SourceFiles0]
%FILE0%=
%FILE1%=
%FILE2%=
"@

Set-Content -LiteralPath $SedPath -Value $Sed -Encoding ASCII
& $IExpress /N /Q $SedPath

if (-not (Test-Path $TempSetupExe)) {
    throw "IExpress did not create $TempSetupExe"
}

Copy-Item -LiteralPath $TempSetupExe -Destination $SetupExe -Force

Write-Host "Portable executable: $AppExe"
Write-Host "Portable zip:        $PortableZip"
Write-Host "Installer:           $SetupExe"
