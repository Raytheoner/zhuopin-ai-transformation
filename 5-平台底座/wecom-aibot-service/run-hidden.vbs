' 2026-07-19: PowerShell -WindowStyle Hidden 对本任务不可靠（Start-ScheduledTask
' 手动触发时曾出现可见窗口，原因未完全查清，疑与 Start-Transcript / 交互式
' LogonType 组合有关）。改用 WScript.Shell.Run 的 Win32 SW_HIDE（0）——这是
' 业界公认更可靠的"计划任务真正隐藏窗口"方法，不依赖 PowerShell 自身的
' 窗口样式提示。等待完成（True）以保持任务"运行中"状态语义与此前一致。
Set objShell = CreateObject("WScript.Shell")
scriptDir = Left(WScript.ScriptFullName, Len(WScript.ScriptFullName) - Len(WScript.ScriptName))
cmd = "powershell.exe -NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File """ & scriptDir & "start-aibot-service-dev.ps1"""
objShell.Run cmd, 0, True
