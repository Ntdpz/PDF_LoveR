; Rebuild with Inno Setup 6.3+ from this file.
#define AppName "PDF to PNG"
#define AppVersion "1.0.0"
#define AppExeName "PDF_to_PNG_Modern.exe"

[Setup]
AppId={{743E935A-23DA-4E3B-A5A2-8A2D6F11FEC8}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
DefaultDirName={localappdata}\Programs\PDF to PNG
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
OutputDir=..\dist\Release
OutputBaseFilename=PDF_to_PNG_Setup_1.0.0
SetupIconFile=..\assets\pdf_to_png.ico
UninstallDisplayIcon={app}\{#AppExeName}
WizardStyle=modern
Compression=lzma2
SolidCompression=yes
CloseApplications=yes
RestartApplications=no
VersionInfoVersion=1.0.0.0
VersionInfoDescription=PDF to PNG Setup
VersionInfoProductName=PDF to PNG
VersionInfoProductVersion=1.0.0

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Shortcuts:"; Flags: unchecked

[Files]
Source: "..\build-release-dist\PDF_to_PNG_Modern\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs; Excludes: "preview.png"
Source: "README_Distribution.txt"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\{#AppName}"; Filename: "{app}\{#AppExeName}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExeName}"; Description: "Open PDF to PNG"; Flags: nowait postinstall skipifsilent

; Uninstall removes only files installed by this package. Converted images and
; other files created by the user are not listed in [UninstallDelete].
