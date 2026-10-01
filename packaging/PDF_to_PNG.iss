; Rebuild with Inno Setup 6.3+ from this file.
#include "version.iss"
#define AppName "PDF LoveR"
#define AppExeName AppBaseName + ".exe"

[Setup]
AppId={{743E935A-23DA-4E3B-A5A2-8A2D6F11FEC8}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
DefaultDirName={localappdata}\Programs\PDF LoveR
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
OutputDir=..\dist\{#AppBaseName}
OutputBaseFilename={#AppBaseName}_Setup
SetupIconFile=..\assets\pdf_to_png.ico
UninstallDisplayIcon={app}\{#AppExeName}
WizardStyle=modern
Compression=lzma2
SolidCompression=yes
CloseApplications=yes
RestartApplications=no
VersionInfoVersion={#AppFileVersion}
VersionInfoDescription=PDF LoveR Setup
VersionInfoProductName=PDF LoveR
VersionInfoProductVersion={#AppVersion}

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Shortcuts:"; Flags: unchecked

[Files]
Source: "..\build-release-dist\{#AppBaseName}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs; Excludes: "preview.png"

[Icons]
Name: "{autoprograms}\{#AppName}"; Filename: "{app}\{#AppExeName}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExeName}"; Description: "Open PDF LoveR"; Flags: nowait postinstall skipifsilent

; Uninstall removes only files installed by this package. Converted images and
; other files created by the user are not listed in [UninstallDelete].
