# ================================================================
#  工具-注册不入库件备份任务.ps1
#  用途：把 工具-不入库件备份同步.ps1 注册为每周一次的 Windows 计划任务。
#        队列 §一 #412（M1 · T4）产出。
#
#  🔴 M1 内**不跑本脚本**（派单件硬约束：本件零迁移动作）。它随 M2 一起做——
#     因为在迁移完成前，仓库根还在 OneDrive 里，注册出来的任务会烘焙旧路径。
#
#  用法（管理员 PowerShell，迁移完成后在**新仓库根**下执行一次）：
#    powershell -File "C:\Dev\zhuopin-ai\0-学习与工具\工具-注册不入库件备份任务.ps1"
#
#  回滚：
#    schtasks /Delete /TN ZhuopinNonRepoBackupWeekly /F
# ================================================================
[CmdletBinding()]
param(
    # 仓库根。默认取本脚本上一级（本脚本住在 <仓库根>\0-学习与工具\ 下）。
    [string] $RepoRoot,
    [string] $BackupRoot = "$env:USERPROFILE\OneDrive\Backups\企业AI转型-不入库件",
    # 每周几、几点。默认周日 22:00（低流量时段，且早于周一 10:00 值周巡检）。
    [string] $DayOfWeek = "Sunday",
    [string] $AtTime = "22:00"
)

$ErrorActionPreference = "Stop"

# ── 提权自检守卫（同三个既有注册脚本，队列 #412 · M1）─────────────────────
#  S4U 计划任务的 Register/Unregister 一律需要 SeTcbPrivilege。非提权跑下去
#  不会「报错停住」，而是留下一个看起来没报错、实际一个都没注册的状态。
$__isAdmin = ([Security.Principal.WindowsPrincipal] `
    [Security.Principal.WindowsIdentity]::GetCurrent()
).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $__isAdmin) {
    Write-Error ("本脚本要注册计划任务，需要管理员 PowerShell。" +
        "当前会话非提权，已在改动任何任务之前退出——请在管理员 PowerShell 里重跑本脚本。")
    exit 1
}

if (-not $RepoRoot) { $RepoRoot = Split-Path (Split-Path $PSCommandPath -Parent) -Parent }
$SYNC_SCRIPT = Join-Path $RepoRoot "0-学习与工具\工具-不入库件备份同步.ps1"
$TASK = "ZhuopinNonRepoBackupWeekly"

Write-Host "`n== 注册不入库件每周备份任务 ==" -ForegroundColor Cyan
Write-Host "   仓库根   : $RepoRoot"
Write-Host "   同步脚本 : $SYNC_SCRIPT"
Write-Host "   备份到   : $BackupRoot"
Write-Host "   周期     : 每周 $DayOfWeek $AtTime`n"

if (-not (Test-Path -LiteralPath $SYNC_SCRIPT)) {
    Write-Error "未找到 $SYNC_SCRIPT —— 请确认在仓库根下执行本脚本。"
    exit 1
}
# 🔴 迁移前误跑的防呆：仓库根若还在 OneDrive 里，注册出来的任务会烘焙旧路径。
if ($RepoRoot -match '(?i)OneDrive') {
    Write-Error "仓库根 $RepoRoot 仍在 OneDrive 内——本任务须在迁移完成后、在新仓库根下注册，否则烘焙的是旧路径。"
    exit 1
}

# 绝对路径烘焙进 Action，不依赖触发时的运行时 PATH（同落库 sweep 惯例，#79 教训）。
$psExe = (Get-Command powershell.exe).Source
$action = New-ScheduledTaskAction -Execute $psExe `
    -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$SYNC_SCRIPT`" -RepoRoot `"$RepoRoot`" -BackupRoot `"$BackupRoot`"" `
    -WorkingDirectory $RepoRoot

$trigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek $DayOfWeek -At $AtTime

# 运行身份：当前账户 + S4U（不落密码、不要求保持登录会话）。
# 不用 SYSTEM —— 备份落点在用户的 OneDrive 目录下，SYSTEM 对其无 ACL 访问权限
# （#96 坑：会静默权限被拒、零执行零日志）。
$currentUser = (whoami).Trim()
$principal = New-ScheduledTaskPrincipal -UserId $currentUser -LogonType S4U -RunLevel Limited

$settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -ExecutionTimeLimit (New-TimeSpan -Hours 2)

if (Get-ScheduledTask -TaskName $TASK -ErrorAction SilentlyContinue) {
    Write-Host "[1/2] 已存在同名任务，先注销以更新路径..." -ForegroundColor Yellow
    Unregister-ScheduledTask -TaskName $TASK -Confirm:$false
}

Write-Host "[2/2] 注册 $TASK ..." -ForegroundColor Yellow
Register-ScheduledTask -TaskName $TASK `
    -Action $action -Trigger $trigger -Principal $principal -Settings $settings `
    -Description "每周把仓库内不入 git 的件（.env / 7-外部文档 / 各处 reports）增量同步到 OneDrive 备份目录。队列 #412 · M1·T4。" | Out-Null

# 🔴 回读确认——「注册没报错」不等于「路径是新的」。
$t = Get-ScheduledTask -TaskName $TASK
foreach ($a in $t.Actions) {
    Write-Host "`n   回读 Execute : $($a.Execute)" -ForegroundColor Green
    Write-Host "   回读 Args    : $($a.Arguments)" -ForegroundColor Green
    Write-Host "   回读 WD      : $($a.WorkingDirectory)" -ForegroundColor Green
    if ($a.Arguments -match '(?i)OneDrive\\Projects') {
        Write-Error "回读发现 Action 里仍含旧仓库路径——注册结果不可用。"
        exit 1
    }
}
Write-Host "`n   ✅ 已注册。首次请手动跑一次并核对文件数：" -ForegroundColor Cyan
Write-Host "      Start-ScheduledTask -TaskName $TASK" -ForegroundColor Cyan
