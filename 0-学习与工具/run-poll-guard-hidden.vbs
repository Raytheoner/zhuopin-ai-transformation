' 轮询守隐藏窗口启动器（队列 #575 甲／OP-0913-Q，批 B-0913_轮询守）。
' 范式同 run-commit-sweep-hidden.vbs（队列 #231）：计划任务 Action 直接 Execute=powershell/pwsh
' 每 15 分钟会闪一次控制台窗口，Settings.Hidden 对控制台窗口未必生效，故走已验证的
' WScript.Shell.Run SW_HIDE(0)。scriptDir 动态取自身所在目录，本文件不含机器专属绝对路径、可入库；
' 它拉起的 run-poll-guard.ps1 由 工具-注册轮询守计划任务.ps1 生成（绝对路径烘焙，已在 .gitignore）。
' 🔴 起 轮询守 一律 pwsh 7（巡检脚本本身要 pwsh；Windows PowerShell 5.1 跑不动）——pwsh 的绝对路径
' 也烘焙在 run-poll-guard.ps1 里，这里只负责用系统自带的 powershell.exe 把它以隐藏窗口拉起来
' （5.1 只是个跳板，真正的工作进程是包装脚本里那条 pwsh）。等待完成（True）以保持任务「运行中」语义。
Set objShell = CreateObject("WScript.Shell")
scriptDir = Left(WScript.ScriptFullName, Len(WScript.ScriptFullName) - Len(WScript.ScriptName))
cmd = "powershell.exe -NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File """ & scriptDir & "run-poll-guard.ps1"""
objShell.Run cmd, 0, True
