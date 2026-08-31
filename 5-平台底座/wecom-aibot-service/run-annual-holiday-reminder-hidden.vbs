' 队列 #379：年度节假日日历更新提醒计划任务的隐藏窗口启动器。同
' `run-decision-reminder-hidden.vbs`/`run-hidden.vbs` 既有范式（队列 #231，
' 2026-08-04）——沿用 WScript.Shell.Run + Win32 SW_HIDE（0），避免每日固定
' 时点触发时弹出一闪而过的控制台窗口。scriptDir 动态取自身所在目录，本文件
' 不含任何机器专属绝对路径，可安全入库；等待完成（True）以保持任务"运行中"
' 状态语义与既有两份一致。
Set objShell = CreateObject("WScript.Shell")
scriptDir = Left(WScript.ScriptFullName, Len(WScript.ScriptFullName) - Len(WScript.ScriptName))
cmd = "powershell.exe -NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File """ & scriptDir & "run-annual-holiday-reminder-check.ps1"""
objShell.Run cmd, 0, True
