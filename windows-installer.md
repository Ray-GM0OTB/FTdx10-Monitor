# Windows builds

Two ways to run FTDX10 Monitor without Python, both built from `FTDX10_Monitor.py`:

| Build | Script | Result | Settings kept in |
| --- | --- | --- | --- |
| **Installer** | `build_installer.bat` | `installer\FTDX10_Monitor_Setup_1.7.exe`: installs to Program Files with Start-menu entry and uninstaller | `%LOCALAPPDATA%\FTDX10 Monitor` |
| **Portable** | `build_portable_exe.bat` | `FTDX10 Monitor\FTDX10 Monitor.exe`: one file, run from any folder or USB stick | Next to the `.exe` |

## Building the installer

1. Put `FTDX10_Monitor.py`, `build_installer.bat`, `FTDX10_Monitor_installer.iss`, `ftdx10.ico` and `ftdx10.png` in one folder (this repository's folder works).
2. Double-click `build_installer.bat`. It:
   1. installs PyInstaller, pyserial and sounddevice with pip;
   2. builds the program into `dist\FTDX10 Monitor\`;
   3. builds the setup with [Inno Setup 6](https://jrsoftware.org/isinfo.php), installing it with winget first if needed.
3. Explorer opens the `installer` folder with the setup `.exe`.

Run the setup on any Windows PC. Installing over an older version keeps the settings.

## Building the portable exe

Double-click `build_portable_exe.bat`. It installs the build tools, builds one `FTDX10 Monitor.exe` and puts it in a `FTDX10 Monitor` folder, copying in settings and the QSO log from an installed copy if there is one. Everything it prints is also saved in `build_log.txt`.

## New versions

When `FTDX10_Monitor.py` changes version, also change `AppVersion` in `FTDX10_Monitor_installer.iss` and the file name in `build_installer.bat`.

## If a build stops

| Step | Cause |
| --- | --- |
| Installing build tools | Python not on PATH: reinstall Python and tick **Add to PATH**; or no internet |
| Building the program | Antivirus blocking PyInstaller: allow the folder; or the old `.exe` is still running |
| Building the installer | Inno Setup missing and winget unavailable: install it from [jrsoftware.org](https://jrsoftware.org/isdl.php) |
