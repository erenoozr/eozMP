@echo off
title Building the eozMP installer
cd /d "%~dp0"
echo.
echo  ==============================================
echo     eozMP installer builder - makes installer\Output\eozMP-Setup-x.y.exe
echo  ==============================================
echo.

where python >nul 2>nul
if errorlevel 1 (
    echo  Python was not found. Install it from https://www.python.org/downloads/
    echo  and tick "Add Python to PATH", then run this file again.
    pause
    exit /b 1
)

rem --- find Inno Setup (free: https://jrsoftware.org/isdl.php or "winget install JRSoftware.InnoSetup")
set "ISCC=%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe"
if not exist "%ISCC%" set "ISCC=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
if not exist "%ISCC%" (
    echo  Inno Setup 6 was not found. Install it with:  winget install JRSoftware.InnoSetup
    pause
    exit /b 1
)

echo  [1/3] Installing what eozMP needs...
python -m pip install --upgrade PyQt6 mutagen numpy pyinstaller python-vlc segno winrt-runtime winrt-Windows.Foundation winrt-Windows.Foundation.Collections winrt-Windows.Media winrt-Windows.Media.Playback winrt-Windows.Storage winrt-Windows.Storage.Streams
if errorlevel 1 (
    echo  Installing failed. Check your internet connection and try again.
    pause
    exit /b 1
)

echo.
echo  [2/3] Building eozMP.exe ...
if exist build rmdir /s /q build
python -m PyInstaller --noconfirm --onefile --windowed --name eozMP --icon eozMP.ico --collect-all winrt musicplayer.py
if not exist "dist\eozMP.exe" (
    echo  The build failed. Scroll up to see the error.
    pause
    exit /b 1
)

rem --- slskd is put inside the installer; download it once
if not exist "installer\vendor\slskd\slskd.exe" (
    echo  Downloading slskd 0.26.1 ...
    powershell -NoProfile -Command "$ErrorActionPreference='Stop'; New-Item -ItemType Directory -Force installer\vendor | Out-Null; Invoke-WebRequest 'https://github.com/slskd/slskd/releases/download/0.26.1/slskd-0.26.1-win-x64.zip' -OutFile installer\vendor\slskd.zip; Expand-Archive -Force installer\vendor\slskd.zip installer\vendor\slskd; Remove-Item installer\vendor\slskd.zip"
    if not exist "installer\vendor\slskd\slskd.exe" (
        echo  Couldn't download slskd. Check your internet connection and try again.
        pause
        exit /b 1
    )
)

rem --- fpcalc (Chromaprint) identifies songs by their sound for "Fix tags"
if not exist "installer\vendor\fpcalc\fpcalc.exe" (
    echo  Downloading fpcalc 1.6.1 ...
    powershell -NoProfile -Command "$ErrorActionPreference='Stop'; Invoke-WebRequest 'https://github.com/acoustid/chromaprint/releases/download/v1.6.1/chromaprint-fpcalc-1.6.1-windows-x86_64.zip' -OutFile installer\vendor\fp.zip; Expand-Archive -Force installer\vendor\fp.zip installer\vendor\fp; New-Item -ItemType Directory -Force installer\vendor\fpcalc | Out-Null; Get-ChildItem -Recurse installer\vendor\fp -Filter fpcalc.exe | Copy-Item -Destination installer\vendor\fpcalc; Remove-Item -Recurse installer\vendor\fp, installer\vendor\fp.zip"
)

echo.
echo  [3/3] Building the installer...
"%ISCC%" /Q "installer\eozMP.iss"
if errorlevel 1 (
    echo  The installer build failed. Scroll up to see the error.
    pause
    exit /b 1
)
echo.
echo  Done! The installer is in the installer\Output folder.
explorer "installer\Output"
pause
