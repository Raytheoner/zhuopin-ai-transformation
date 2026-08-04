' 队列 #231（2026-08-04，环境保障线取证）：ZhuopinCommitSweep 计划任务的
' Action 此前直接 Execute=powershell.exe，每小时触发时会弹出一闪而过的
' 控制台窗口（Shao Peishen 反馈"屏幕一闪不知做了啥"）。单把
' Settings.Hidden=$true 打开是否足以消除该窗口未经实测——Hidden 主要影响
' 任务在任务计划程序 UI 里是否可见，对控制台窗口未必生效，故不赌，直接
' 沿用本项目已验证过的范式：改用 WScript.Shell.Run 的 Win32 SW_HIDE（0）
' 拉起（同 5-平台底座/wecom-aibot-service/run-hidden.vbs，2026-07-19 已在
' ZhuopinAibotDevListener 上验证过）。scriptDir 动态取自身所在目录，本文件
' 不含任何机器专属绝对路径，可安全入库；等待完成（True）以保持任务"运行
' 中"状态语义与此前一致。
Set objShell = CreateObject("WScript.Shell")
scriptDir = Left(WScript.ScriptFullName, Len(WScript.ScriptFullName) - Len(WScript.ScriptName))
cmd = "powershell.exe -NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File """ & scriptDir & "run-commit-sweep.ps1"""
objShell.Run cmd, 0, True
