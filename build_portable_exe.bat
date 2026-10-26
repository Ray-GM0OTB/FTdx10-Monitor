@echo off
setlocal
title Building FTDX10 Monitor.exe
cd /d "%~dp0"
if /i not "%~1"=="inner" (
  echo Building FTDX10 Monitor.exe - this takes a few minutes, please wait...
  echo The full log is written to build_log.txt
  call "%~f0" inner > "%~dp0build_log.txt" 2>&1
  type "%~dp0build_log.txt"
  echo.
  pause
  exit /b
)

rem ---- find Python 3
set "PY="
where py >nul 2>nul && set "PY=py -3"
if not defined PY where python >nul 2>nul && set "PY=python"
if not defined PY (
  echo Python 3 was not found. Install it from https://www.python.org/downloads/ and run this again.
  echo RESULT: FAILED
  exit /b 1
)
echo Using: %PY%
%PY% --version

echo.
echo === Installing build tools (PyInstaller, pyserial, sounddevice) ===
%PY% -m pip install --disable-pip-version-check --upgrade pyinstaller pyserial sounddevice
if errorlevel 1 (
  %PY% -m pip install --user --disable-pip-version-check --upgrade pyinstaller pyserial sounddevice
  if errorlevel 1 ( echo pip failed - are you online? & echo RESULT: FAILED & exit /b 1 )
)

echo.
echo === Building one-file FTDX10 Monitor.exe ===
%PY% -m PyInstaller --noconfirm --clean --onefile --windowed ^
  --name "FTDX10 Monitor" ^
  --icon "%~dp0ftdx10.ico" ^
  --add-data "%~dp0ftdx10.ico;." ^
  --add-data "%~dp0ftdx10.png;." ^
  --hidden-import serial.tools.list_ports ^
  --collect-all _sounddevice_data ^
  --exclude-module numpy ^
  --distpath "%~dp0dist" --workpath "%~dp0build" --specpath "%~dp0build" ^
  "%~dp0FTDX10_Monitor.py"
if not exist "%~dp0dist\FTDX10 Monitor.exe" ( echo BUILD FAILED - see the messages above. & echo RESULT: FAILED & exit /b 1 )

rem ---- put the exe in its own folder; it keeps its settings, memories and QSO log next to itself
if not exist "%~dp0FTDX10 Monitor" mkdir "%~dp0FTDX10 Monitor"
copy /y "%~dp0dist\FTDX10 Monitor.exe" "%~dp0FTDX10 Monitor\" >nul
if errorlevel 1 ( echo Could not replace FTDX10 Monitor.exe - is it still running? Close it and run this again. & echo RESULT: FAILED & exit /b 1 )
rem ---- bring over settings, memories and log from an installed copy
for %%D in ("%LOCALAPPDATA%\FTDX10 Monitor" "%LOCALAPPDATA%\Programs\FTDX10 Monitor") do (
  for %%F in (ftdx10_settings.json ftdx10_qso_log.json) do (
    if not exist "%~dp0FTDX10 Monitor\%%F" if exist "%%~D\%%F" copy "%%~D\%%F" "%~dp0FTDX10 Monitor\" >nul && echo Copied your existing %%F from %%~D
  )
)

echo.
echo === DONE ===
echo   %~dp0FTDX10 Monitor\FTDX10 Monitor.exe
echo RESULT: OK
