@echo off
title Building eozMP
cd /d "%~dp0"
echo.
echo  ==============================================
echo     eozMP builder - turns musicplayer.py into eozMP.exe
echo  ==============================================
echo.

rem --- 1. Python must be installed (python.org). The "py" launcher comes with it; "python" works
rem        when "Add Python to PATH" was ticked. (On some PCs "python" only opens the Microsoft Store.)
set "PY="
py -3 --version >nul 2>nul && set "PY=py -3"
if not defined PY python --version >nul 2>nul && set "PY=python"
if not defined PY (
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
%PY% -m pip install --upgrade pip
%PY% -m pip install --upgrade PyQt6 mutagen numpy pyinstaller segno
rem Optional: Windows media controls (lock screen, volume flyout, headset buttons)
%PY% -m pip install --upgrade winrt-runtime winrt-Windows.Foundation winrt-Windows.Foundation.Collections winrt-Windows.Media winrt-Windows.Media.Playback winrt-Windows.Storage winrt-Windows.Storage.Streams
rem Optional engines. mpv: gapless playback, ReplayGain, equalizer (needs libmpv-2.dll next to
rem eozMP.exe or picked in Settings). VLC: needs VLC installed. Both are harmless if missing.
%PY% -m pip install --upgrade mpv python-vlc
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
    %PY% -m PyInstaller --noconfirm --onefile --windowed --name eozMP --icon eozMP.ico --hidden-import mpv --hidden-import vlc --collect-all winrt musicplayer.py
) else (
    echo  (eozMP.ico not found - building without the icon)
    %PY% -m PyInstaller --noconfirm --onefile --windowed --name eozMP --hidden-import mpv --hidden-import vlc musicplayer.py
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
