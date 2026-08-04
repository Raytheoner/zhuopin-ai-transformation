' 队列 #231（2026-08-04，环境保障线取证）：ZhuopinDecisionReminderDaily 计划
' 任务的 Action 此前直接 Execute=powershell.exe，每日 08:30 触发时会弹出
' 一闪而过的控制台窗口（Shao Peishen 反馈"屏幕一闪不知做了啥"）。同
' `0-学习与工具/run-commit-sweep-hidden.vbs` 一样，沿用本项目已验证过的
' WScript.Shell.Run + Win32 SW_HIDE（0）范式（同源见 run-hidden.vbs，
' 2026-07-19 已在 ZhuopinAibotDevListener 上验证）。scriptDir 动态取自身
' 所在目录，本文件不含任何机器专属绝对路径，可安全入库；等待完成（True）
' 以保持任务"运行中"状态语义与此前一致。
Set objShell = CreateObject("WScript.Shell")
scriptDir = Left(WScript.ScriptFullName, Len(WScript.ScriptFullName) - Len(WScript.ScriptName))
cmd = "powershell.exe -NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File """ & scriptDir & "run-decision-reminder-check.ps1"""
objShell.Run cmd, 0, True
