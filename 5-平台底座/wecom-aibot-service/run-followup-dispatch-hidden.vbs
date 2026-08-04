' 队列 #124 阶段二：ZhuopinFollowupDispatchDaily 计划任务的隐藏窗口启动器，
' 同 run-decision-reminder-hidden.vbs/run-hidden.vbs 既有范式（#231/#189
' 已在 ZhuopinAibotDevListener/ZhuopinDecisionReminderDaily 上验证过）——
' WScript.Shell.Run + Win32 SW_HIDE（0），避免 Execute=powershell.exe 每次
' 触发弹出一闪而过的控制台窗口。scriptDir 动态取自身所在目录，本文件不含
' 任何机器专属绝对路径，可安全入库；等待完成（True）以保持任务"运行中"
' 状态语义。
Set objShell = CreateObject("WScript.Shell")
scriptDir = Left(WScript.ScriptFullName, Len(WScript.ScriptFullName) - Len(WScript.ScriptName))
cmd = "powershell.exe -NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File """ & scriptDir & "run-followup-dispatch-check.ps1"""
objShell.Run cmd, 0, True
