; Per-user installer. It never downloads or installs the GPU runtime or models.
#ifndef AppVersion
  #define AppVersion "0.1.0a1"
#endif
#ifndef SourceDir
  #define SourceDir "..\dist\ArtegraEnhancer"
#endif
#ifndef OutputDir
  #define OutputDir "..\dist"
#endif
[Setup]
AppId={{2B6628CA-E890-46BF-A894-E5D1E004707F}
AppName=Artegra Enhancer
AppVersion={#AppVersion}
AppPublisher=Studio Artegra
DefaultDirName={localappdata}\Programs\ArtegraEnhancer
DefaultGroupName=Artegra Enhancer
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir={#OutputDir}
OutputBaseFilename=ArtegraEnhancer-{#AppVersion}-Setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
UninstallDisplayIcon={app}\ArtegraEnhancer.exe
CloseApplications=yes
RestartApplications=no
[Tasks]
Name: desktopicon; Description: "Create a desktop shortcut"; GroupDescription: "Shortcuts:"; Flags: unchecked
[Files]
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
[Icons]
Name: "{group}\Artegra Enhancer"; Filename: "{app}\ArtegraEnhancer.exe"
Name: "{autodesktop}\Artegra Enhancer"; Filename: "{app}\ArtegraEnhancer.exe"; Tasks: desktopicon
Name: "{group}\Uninstall Artegra Enhancer"; Filename: "{uninstallexe}"
[Run]
Filename: "{app}\ArtegraEnhancer.exe"; Description: "Open Artegra Enhancer"; Flags: nowait postinstall skipifsilent unchecked
