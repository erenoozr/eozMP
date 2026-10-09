@echo off
title Building eozMP
cd /d "%~dp0"
echo.
echo  ==============================================
echo     eozMP builder - turns musicplayer.py into eozMP.exe
echo  ==============================================
echo.

rem --- 1. Python must be installed (python.org, tick "Add Python to PATH")
where python >nul 2>nul
if errorlevel 1 (
    echo  Python was not found.
    echo  Install it from https://www.python.org/downloads/ and tick "Add Python to PATH",
    echo  then run this file again.
    pause
    exit /b 1
)

if not exist "musicplayer.py" (
    echo  musicplayer.py is not in this folder. Put build_exe.bat next to musicplayer.py.
    pause
    exit /b 1
)

rem --- 2. Install / update everything eozMP uses
echo  [1/3] Installing what eozMP needs (this can take a few minutes the first time)...
python -m pip install --upgrade pip
python -m pip install --upgrade PyQt6 mutagen numpy pyinstaller
rem Optional: lets eozMP use VLC (needed for the equalizer). Harmless if VLC isn't installed.
python -m pip install --upgrade python-vlc
if errorlevel 1 (
    echo  Something went wrong while installing. Check your internet connection and try again.
    pause
    exit /b 1
)

rem --- 3. Build the exe
echo.
echo  [2/3] Building eozMP.exe ...
if exist build rmdir /s /q build
if exist "eozMP.ico" (
    python -m PyInstaller --noconfirm --onefile --windowed --name eozMP --icon eozMP.ico musicplayer.py
) else (
    echo  (eozMP.ico not found - building without the icon)
    python -m PyInstaller --noconfirm --onefile --windowed --name eozMP musicplayer.py
)
if not exist "dist\eozMP.exe" (
    echo.
    echo  The build failed. Scroll up to see the error and send it to whoever helps you with eozMP.
    pause
    exit /b 1
)

rem --- 4. Put a copy on the Desktop
echo.
echo  [3/3] Copying eozMP.exe to your Desktop...
for /f "usebackq delims=" %%D in (`powershell -NoProfile -Command "[Environment]::GetFolderPath('Desktop')"`) do set "DESKTOP=%%D"
if defined DESKTOP (
    copy /y "dist\eozMP.exe" "%DESKTOP%\eozMP.exe" >nul
    echo  Done! eozMP.exe is on your Desktop (and in the "dist" folder here).
) else (
    echo  Done! eozMP.exe is in the "dist" folder here.
)
echo.
pause
