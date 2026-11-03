; Inno Setup script for Bubu & Dudu: Picnic Adventure
; Build: ISCC.exe installer.iss  (after PyInstaller has produced dist\BubuDudu)

#define MyAppName "Bubu & Dudu: Picnic Adventure"
; folder/shortcut-safe name (no ":" allowed in file names)
#define MyAppShortName "Bubu & Dudu"
#define MyAppExeName "BubuDudu.exe"
#define MyAppVersion "1.0"

[Setup]
AppId={{7B3C2E9A-5D14-4F6B-9C1A-BUBUDUDU2026}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher=Ivan
DefaultDirName={autopf}\BubuDudu
DefaultGroupName={#MyAppShortName}
DisableProgramGroupPage=yes
OutputDir=installer
OutputBaseFilename=BubuDudu-Setup
SetupIconFile=assets\icon.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
Source: "dist\BubuDudu\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppShortName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppShortName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent
