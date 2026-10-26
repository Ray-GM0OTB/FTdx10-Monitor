@echo off
rem ============================================================
rem  FTDX10 Monitor - builds the Windows installer
rem  Put this file, FTDX10_Monitor.py and FTDX10_Monitor_installer.iss in one
rem  folder (plus ftdx10.ico / ftdx10.png if you have them),
rem  then double-click this file.
rem  Result: installer\FTDX10_Monitor_Setup_2.3.exe
rem ============================================================
setlocal
cd /d "%~dp0"

where py >nul 2>nul && (set PY=py) || (set PY=python)
%PY% --version >nul 2>nul || (
  echo Python was not found. Install it from https://www.python.org/downloads/ and tick "Add to PATH".
  pause & exit /b 1
)

echo.
echo [1/3] Installing build packages ...
%PY% -m pip install --upgrade pyinstaller pyserial sounddevice || goto :fail

echo.
echo [2/3] Building the program ...
set EXTRA=
if exist ftdx10.ico set EXTRA=%EXTRA% --icon ftdx10.ico --add-data "ftdx10.ico;."
if exist ftdx10.png set EXTRA=%EXTRA% --add-data "ftdx10.png;."
%PY% -m PyInstaller --noconfirm --clean --windowed --onedir --name "FTDX10 Monitor" ^
  --hidden-import sounddevice --hidden-import serial.tools.list_ports %EXTRA% FTDX10_Monitor.py || goto :fail

echo.
echo [3/3] Building the installer ...
set ISCC=
for %%P in ("%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" "%ProgramFiles%\Inno Setup 6\ISCC.exe" "%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe") do if exist %%P set ISCC=%%P
if not defined ISCC (
  echo Inno Setup not found - installing it with winget ...
  winget install --id JRSoftware.InnoSetup -e --accept-package-agreements --accept-source-agreements
  for %%P in ("%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" "%ProgramFiles%\Inno Setup 6\ISCC.exe" "%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe") do if exist %%P set ISCC=%%P
)
if not defined ISCC (
  echo Could not find Inno Setup. Install it from https://jrsoftware.org/isdl.php and run this again.
  echo The program itself is ready in: dist\FTDX10 Monitor\
  pause & exit /b 1
)
%ISCC% FTDX10_Monitor_installer.iss || goto :fail

echo.
echo Done. Installer: %CD%\installer\FTDX10_Monitor_Setup_2.3.exe
explorer installer
pause
exit /b 0

:fail
echo.
echo Build failed - see the messages above.
pause
exit /b 1
