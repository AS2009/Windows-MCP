#define MyAppName "Windows-MCP"
#define MyAppVersion "0.8.6"
#define MyAppPublisher "AS2009"
#define MyAppURL "https://github.com/AS2009/Windows-MCP"
#define MyAppExeName "windows-mcp.exe"

[Setup]
AppId={{B8F4A3D2-7E6C-4A1B-9D5F-8C2E0A7B3D1F}}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
AllowNoIcons=yes
OutputDir=dist
OutputBaseFilename=Windows-MCP-Setup-{#MyAppVersion}
Compression=lzma
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest

[Tasks]
Name: "desktopicon"; Description: "Create desktop shortcut"; GroupDescription: "Additional shortcuts:"
Name: "startup"; Description: "Auto-start server at login"; GroupDescription: "Startup options:"

[Files]
Source: "dist\{#MyAppExeName}"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Comment: "Configure and start Windows-MCP service"
Name: "{group}\Uninstall Windows-MCP"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch configuration wizard"; Flags: nowait postinstall skipifsilent

[Registry]
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "Windows-MCP"; ValueData: """{app}\{#MyAppExeName}"" serve --tray"; Flags: uninsdeletevalue; Tasks: startup

[UninstallRun]
Filename: "reg"; Parameters: "delete HKCU\Software\Microsoft\Windows\CurrentVersion\Run /v Windows-MCP /f"; Flags: runhidden
