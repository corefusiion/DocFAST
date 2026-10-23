; Inno Setup script for DocFAST — per-user install, no admin rights needed.
#define AppVersion GetEnv("DOCFAST_VERSION")
#if AppVersion == ""
  #define AppVersion "1.1.0"
#endif

[Setup]
AppId={{8B2F3A1C-8E6F-4B9A-9F4B-E8B6F2D3C4F5}
AppName=DocFAST
AppVersion={#AppVersion}
AppPublisher=Gleisson Santos
AppPublisherURL=https://docfastbr.lovable.app/
AppSupportURL=https://docfastbr.lovable.app/
AppUpdatesURL=https://docfastbr.lovable.app/
DefaultDirName={localappdata}\Programs\DocFAST
DefaultGroupName=DocFAST
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir=..\dist
OutputBaseFilename=DocFAST-Setup
SetupIconFile=..\docfast\assets\docfast.ico
UninstallDisplayIcon={app}\DocFAST.exe
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
CloseApplications=yes
RestartApplications=no

[Tasks]
Name: "autostart"; Description: "Start DocFAST when I sign in to Windows"; Flags: checkedonce
Name: "contextmenu"; Description: "Add ""DocFAST"" to the right-click menu for files"; Flags: checkedonce
Name: "desktopicon"; Description: "Create a desktop shortcut"; Flags: unchecked

[Files]
Source: "..\dist\DocFAST\*"; DestDir: "{app}"; Flags: recursesubdirs ignoreversion

[Icons]
Name: "{autoprograms}\DocFAST"; Filename: "{app}\DocFAST.exe"
Name: "{autodesktop}\DocFAST"; Filename: "{app}\DocFAST.exe"; Tasks: desktopicon
Name: "{usersendto}\DocFAST"; Filename: "{app}\DocFAST.exe"

[Registry]
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "DocFAST"; ValueData: """{app}\DocFAST.exe"" --quiet"; Tasks: autostart; Flags: uninsdeletevalue
Root: HKCU; Subkey: "Software\Classes\*\shell\DocFAST"; ValueType: string; ValueName: "MUIVerb"; ValueData: "DocFAST…"; Tasks: contextmenu; Flags: uninsdeletekey
Root: HKCU; Subkey: "Software\Classes\*\shell\DocFAST"; ValueType: string; ValueName: "Icon"; ValueData: "{app}\DocFAST.exe"; Tasks: contextmenu
Root: HKCU; Subkey: "Software\Classes\*\shell\DocFAST"; ValueType: string; ValueName: "MultiSelectModel"; ValueData: "Player"; Tasks: contextmenu
Root: HKCU; Subkey: "Software\Classes\*\shell\DocFAST\command"; ValueType: string; ValueName: ""; ValueData: """{app}\DocFAST.exe"" ""%1"""; Tasks: contextmenu
Root: HKCU; Subkey: "Software\DocFAST"; Flags: uninsdeletekey

[Run]
Filename: "{app}\DocFAST.exe"; Description: "Launch DocFAST now"; Flags: nowait postinstall skipifsilent

[UninstallRun]
Filename: "{cmd}"; Parameters: "/C taskkill /F /IM DocFAST.exe"; Flags: runhidden; RunOnceId: "KillDocFAST"
