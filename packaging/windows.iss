; Compile with Inno Setup 6.3+ after building packaging/Alder.spec.
#ifndef AppVersion
  #error AppVersion must be supplied by scripts/build_windows.py
#endif
#define AppName "Alder"
#ifndef Edition
  #define Edition "GUI"
#endif
#ifndef BundleDir
  #define BundleDir "..\dist\Alder"
#endif

[Setup]
AppId={{7841FB2F-67E9-4B35-9023-794282893420}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion} ({#Edition})
DefaultDirName={localappdata}\Programs\Alder
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0.17763
OutputDir=..\dist\release
OutputBaseFilename=Alder-{#AppVersion}-Windows-x64-{#Edition}-Setup
SetupIconFile=..\src\alder\assets\alder.ico
UninstallDisplayIcon={app}\Alder.exe
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
CloseApplications=yes
RestartApplications=no

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Shortcuts:"; Flags: unchecked

[InstallDelete]
; Editions share one application; calculation caches/jobs live outside this folder.
Type: filesandordirs; Name: "{app}\mlip-offline"

[Files]
Source: "{#BundleDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\Alder.exe"; WorkingDir: "{app}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\Alder.exe"; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
Filename: "{app}\Alder.exe"; Parameters: "--setup"; StatusMsg: "Setting up models and calculation hardware..."; Flags: waituntilterminated skipifsilent
Filename: "{app}\Alder.exe"; Description: "Open {#AppName}"; Flags: nowait postinstall skipifsilent
