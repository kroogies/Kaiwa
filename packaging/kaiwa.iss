; Inno Setup script for Kaiwa — wraps the PyInstaller onedir output (dist\Kaiwa)
; into a per-user Windows installer. Version comes from the KAIWA_VERSION env var
; set by the CI workflow. Compile with: ISCC.exe packaging\kaiwa.iss  (from repo root)

#define MyAppName "Kaiwa"
#ifndef MyAppVersion
  #define MyAppVersion GetEnv("KAIWA_VERSION")
#endif
#if MyAppVersion == ""
  #define MyAppVersion "0.0.0-dev"
#endif
#define MyAppPublisher "kroogies"
#define MyAppExeName "Kaiwa.exe"

[Setup]
; This script lives in packaging/, but all its inputs (dist\, packaging\kaiwa.ico)
; are relative to the repo root — resolve relative paths from there.
SourceDir=..
AppId={{B1F9C2A4-3D5E-4F6A-8B7C-9D0E1F2A3B4C}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={localappdata}\Programs\Kaiwa
DisableProgramGroupPage=yes
; per-user install → no admin prompt (important: the app is unsigned)
PrivilegesRequired=lowest
OutputDir=dist_installer
OutputBaseFilename=Kaiwa-Setup
SetupIconFile=packaging\kaiwa.ico
Compression=lzma2
SolidCompression=yes
WizardStyle=modern

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional icons:"; Flags: unchecked

[Files]
Source: "dist\Kaiwa\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion

[Icons]
Name: "{autoprograms}\Kaiwa"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\Kaiwa"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch Kaiwa"; Flags: nowait postinstall skipifsilent
