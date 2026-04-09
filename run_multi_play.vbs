Option Explicit

Dim shell, fso, scriptDir, mainPy, localVbs, localBat, envPythonw, envPython, envDir, condaRoot, condaBat, cmd
Set shell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")

scriptDir = fso.GetParentFolderName(WScript.ScriptFullName)
mainPy = fso.BuildPath(fso.BuildPath(scriptDir, "app"), "main.py")
localVbs = fso.BuildPath(scriptDir, "run_multi_play_local.vbs")
localBat = fso.BuildPath(scriptDir, "run_multi_play_local.bat")
envPythonw = fso.BuildPath(fso.GetParentFolderName(scriptDir), "pythonw.exe")
envPython = fso.BuildPath(fso.GetParentFolderName(scriptDir), "python.exe")
envDir = fso.GetParentFolderName(envPython)
condaRoot = fso.GetParentFolderName(fso.GetParentFolderName(envDir))
condaBat = fso.BuildPath(fso.BuildPath(condaRoot, "condabin"), "conda.bat")

If Not fso.FileExists(mainPy) Then
  MsgBox "app\main.py not found:" & vbCrLf & mainPy, vbExclamation, "Multi-Play"
  WScript.Quit 1
End If

shell.CurrentDirectory = scriptDir

If fso.FileExists(localVbs) Then
  shell.Run """" & localVbs & """", 0, False
  WScript.Quit 0
End If

If fso.FileExists(condaBat) And fso.FileExists(envPython) Then
  If fso.FileExists(envPythonw) Then
    cmd = "cmd.exe /d /c " & Q(Q(condaBat) & " activate " & Q(envDir) & " && " & Q(envPythonw) & " " & Q(mainPy))
    shell.Run cmd, 0, False
    WScript.Quit 0
  End If
  cmd = "cmd.exe /d /c " & Q(Q(condaBat) & " activate " & Q(envDir) & " && " & Q(envPython) & " " & Q(mainPy))
  shell.Run cmd, 0, False
  WScript.Quit 0
End If

If fso.FileExists(localBat) Then
  shell.Run "cmd.exe /c """ & localBat & """", 0, False
  WScript.Quit 0
End If

If fso.FileExists(envPythonw) Then
  cmd = Q(envPythonw) & " " & Q(mainPy)
  shell.Run cmd, 0, False
  WScript.Quit 0
End If

If fso.FileExists(envPython) Then
  cmd = Q(envPython) & " " & Q(mainPy)
  shell.Run cmd, 0, False
  WScript.Quit 0
End If

MsgBox "No launcher or Python executable was found." & vbCrLf & _
       "Run install\install_windows.ps1 first, or create run_multi_play_local.bat.", _
       vbExclamation, "Multi-Play"
WScript.Quit 1

Function Q(value)
  Q = """" & value & """"
End Function
