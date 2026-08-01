' Windows-MCP Tray Launcher
' Double-click this file to start the server with a system tray icon.
' No console window will appear.
'
' All server settings (host / port / transport / auth key) are read from
' ~/.windows-mcp/config.toml — nothing is hardcoded here.

Set objShell = CreateObject("WScript.Shell")
Set objFSO   = CreateObject("Scripting.FileSystemObject")

' Locate this script's directory
scriptDir = objFSO.GetParentFolderName(WScript.ScriptFullName)

' 1) Prefer the bundled windows-mcp.exe next to this script (installed layout)
exePath = scriptDir & "\windows-mcp.exe"
If objFSO.FileExists(exePath) Then
    ' The EXE reads ~/.windows-mcp/config.toml; warn early if it is missing.
    configPath = objShell.ExpandEnvironmentStrings("%USERPROFILE%") & "\.windows-mcp\config.toml"
    If Not objFSO.FileExists(configPath) Then
        MsgBox "未找到配置文件:" & vbCrLf & vbCrLf & configPath & vbCrLf & vbCrLf & _
               "请先运行 windows-mcp.exe 打开配置向导生成配置。", _
               vbExclamation, "Windows-MCP"
    End If
    cmd = """" & exePath & """ serve --tray"
    objShell.Run cmd, 0, False
    WScript.Quit 0
End If

' 2) Fallback: find pythonw.exe and run `pythonw -m windows_mcp serve --tray`
pythonw = ""
pythonwPaths = Array( _
    scriptDir & "\.venv\Scripts\pythonw.exe", _
    objShell.ExpandEnvironmentStrings("%LOCALAPPDATA%") & "\Programs\Python\Python313\pythonw.exe", _
    objShell.ExpandEnvironmentStrings("%LOCALAPPDATA%") & "\Programs\Python\Python312\pythonw.exe", _
    objShell.ExpandEnvironmentStrings("%LOCALAPPDATA%") & "\Programs\Python\Python311\pythonw.exe", _
    objShell.ExpandEnvironmentStrings("%LOCALAPPDATA%") & "\Programs\Python\Python310\pythonw.exe", _
    objShell.ExpandEnvironmentStrings("%LOCALAPPDATA%") & "\Microsoft\WindowsApps\pythonw.exe", _
    "C:\Python313\pythonw.exe", _
    "C:\Python312\pythonw.exe", _
    "C:\Python311\pythonw.exe", _
    "C:\Python310\pythonw.exe" _
)

For Each p In pythonwPaths
    If objFSO.FileExists(p) Then
        pythonw = p
        Exit For
    End If
Next

' Try "where pythonw" as fallback
If pythonw = "" Then
    On Error Resume Next
    Set objExec = objShell.Exec("where pythonw")
    pythonw = Trim(objExec.StdOut.ReadLine())
    On Error Goto 0
End If

If pythonw = "" Or Not objFSO.FileExists(pythonw) Then
    MsgBox "Cannot find pythonw.exe or windows-mcp.exe." & vbCrLf & vbCrLf & _
           "Please install Windows-MCP first (run the installer, or install" & vbCrLf & _
           "Python 3.10+ and run: pip install windows-mcp)." & vbCrLf & _
           "Or edit this .vbs file to set the correct path.", _
           vbCritical, "Windows-MCP Error"
    WScript.Quit 1
End If

' Run silently (window style 0 = hidden)
cmd = """" & pythonw & """ -m windows_mcp serve --tray"
objShell.Run cmd, 0, False

Set objShell = Nothing
Set objFSO   = Nothing
