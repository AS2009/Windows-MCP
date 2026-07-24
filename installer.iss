#define MyAppName "Windows-MCP"
#define MyAppVersion "0.8.2"
#define MyAppPublisher "AS2009"
#define MyAppURL "https://github.com/AS2009/Windows-MCP"
#define MyAppExeName "windows-mcp.exe"

[Setup]
AppId={{B8F4A3D2-7E6C-4A1B-9D5F-8C2E0A7B3D1F}
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

[Languages]
Name: "chinesesimp"; MessagesFile: "compiler:Languages\ChineseSimplified.isl"

[Tasks]
Name: "desktopicon"; Description: "创建桌面快捷方式"; GroupDescription: "附加快捷方式:"
Name: "startup"; Description: "开机自动启动服务"; GroupDescription: "启动选项:"

[Files]
Source: "dist\{#MyAppExeName}"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Comment: "配置并启动 Windows-MCP 服务"
Name: "{group}\卸载 Windows-MCP"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "运行配置向导"; Flags: nowait postinstall skipifsilent

[Registry]
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "Windows-MCP"; ValueData: """{app}\{#MyAppExeName}"" serve"; Flags: uninsdeletevalue; Tasks: startup

[UninstallRun]
Filename: "reg"; Parameters: "delete HKCU\Software\Microsoft\Windows\CurrentVersion\Run /v Windows-MCP /f"; Flags: runhidden

[Code]
procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssPostInstall then
  begin
    if not WizardIsTaskSelected('startup') then
    begin
      RegDeleteStringIncludingSubkeys(HKEY_CURRENT_USER,
        'Software\Microsoft\Windows\CurrentVersion\Run', 'Windows-MCP');
    end;
  end;
end;
