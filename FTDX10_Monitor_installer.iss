; Inno Setup script for FTDX10 Monitor (built by build_installer.bat)
#define AppName "FTDX10 Monitor"
#define AppVersion "2.3"
#define AppPublisher "GM0OTB"
#define AppExe "FTDX10 Monitor.exe"

[Setup]
AppId={{9D2F41C3-0010-4F6B-A1E2-0A0B0CF7D100}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher={#AppPublisher}
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
DisableDirPage=no
OutputDir=installer
OutputBaseFilename=FTDX10_Monitor_Setup_{#AppVersion}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64
PrivilegesRequiredOverridesAllowed=dialog
UninstallDisplayIcon={app}\{#AppExe}
#if FileExists("ftdx10.ico")
SetupIconFile=ftdx10.ico
#endif

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; GroupDescription: "Shortcuts:"

[Files]
Source: "dist\FTDX10 Monitor\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExe}"
Name: "{group}\Uninstall {#AppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExe}"; Description: "Start {#AppName} now"; Flags: nowait postinstall skipifsilent
