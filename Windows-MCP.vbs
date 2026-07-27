 ' Windows-MCP Tray Launcher
 ' Double-click this file to start the server with a system tray icon.
 ' No console window will appear.
 '
 ' Configuration: change these values if needed.
 ' =============================================
 AUTH_KEY = "86882382"
 HOST     = "0.0.0.0"
 PORT     = "8000"
 TRANSPORT = "sse"
 ' =============================================
 
 Set objShell = CreateObject("WScript.Shell")
 Set objFSO   = CreateObject("Scripting.FileSystemObject")
 
 ' Locate this script's directory
 scriptDir = objFSO.GetParentFolderName(WScript.ScriptFullName)
 
 ' Try to find pythonw.exe
 pythonw = ""
 pythonwPaths = Array( _
     scriptDir & "\.venv\Scripts\pythonw.exe", _
     objShell.ExpandEnvironmentStrings("%LOCALAPPDATA%") & "\Programs\Python\Python313\pythonw.exe", _
     objShell.ExpandEnvironmentStrings("%LOCALAPPDATA%") & "\Programs\Python\Python312\pythonw.exe", _
     objShell.ExpandEnvironmentStrings("%LOCALAPPDATA%") & "\Programs\Python\Python311\pythonw.exe", _
     objShell.ExpandEnvironmentStrings("%LOCALAPPDATA%") & "\Microsoft\WindowsApps\pythonw.exe", _
     "C:\Python313\pythonw.exe", _
     "C:\Python312\pythonw.exe" _
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
     MsgBox "Cannot find pythonw.exe." & vbCrLf & vbCrLf & _
            "Please install Python 3.12+ and try again." & vbCrLf & _
            "Or edit this .vbs file to set the correct path.", _
            vbCritical, "Windows-MCP Error"
     WScript.Quit 1
 End If
 
 ' Build command
 cmd = """" & pythonw & """ -m windows_mcp serve --tray --transport " & TRANSPORT & _
       " --host " & HOST & " --port " & PORT & " --auth-key " & AUTH_KEY
 
 ' Run silently (window style 0 = hidden)
 objShell.Run cmd, 0, False
 
 Set objShell = Nothing
 Set objFSO   = Nothing
