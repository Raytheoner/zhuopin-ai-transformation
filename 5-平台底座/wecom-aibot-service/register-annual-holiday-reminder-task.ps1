# ================================================================
#  register-annual-holiday-reminder-task.ps1
#  用途：把 scripts/annual_holiday_reminder.py 注册为**每日**定时任务（队列
#  #379）。任务本身每天触发，但脚本内部按本地日期判断"今天是不是 9 月 1
#  日"，只有到了那天才真的发送——**刻意不用 Windows 原生"每年一次"触发
#  器**：队列 #379 行内原话「一年后才第一次跑的定时任务，到时候多半是坏
#  的、且没人会知道它坏了」——每日触发使任务本身的"还活着"这件事每天都能
#  被验证（心跳写进 reports/annual_holiday_reminder_state.json 的
#  last_checked_at），不必等到明年 9 月才能发现它坏没坏。
#
#  Action 指向 `ops/wecom-service-home`（本服务的长驻 worktree），与
#  register-decision-reminder-task.ps1 同一惯例——脚本 import 的
#  `aibot_service` 包与 `.env` 凭据长驻在这个 worktree，且它是稳定路径，
#  不会被"僵尸 worktree 清理"误伤（同 #49/§5"长驻服务类 worktree"惯例）。
#
#  运行身份：LogonType Interactive（同 ZhuopinDecisionReminderDaily/
#  ZhuopinAibotDevListener 既有先例）。🔴 **2026-08-31 实测更正**：
#  register-decision-reminder-task.ps1 顶部注释称"S4U 需要管理员权限、
#  Interactive 不需要"，但其守卫代码对**任意**注册（不论 logon type）
#  一律要求管理员——本次在同一台机器上对 LogonType=Interactive 单独做了
#  一次可逆探针（注册一个空动作任务、立即注销），**未提权也注册成功**，
#  故本脚本不设管理员门槛，按实测结果为准（同根 CLAUDE.md「判据本身也
#  需要被质疑一次」）；若未来在别的机器上遇到 Access denied，请改用
#  管理员 PowerShell 重跑。
#
#  用法（在仓库根或任意目录下执行一次；重复执行幂等——会先注销旧任务再
#        重建）：
#    powershell -ExecutionPolicy Bypass -File "5-平台底座\wecom-aibot-service\register-annual-holiday-reminder-task.ps1"
#
#  验证：
#    Start-ScheduledTask -TaskName ZhuopinAnnualHolidayReminderDaily
#    Get-ScheduledTaskInfo -TaskName ZhuopinAnnualHolidayReminderDaily
#
#  回滚：
#    schtasks /End /TN ZhuopinAnnualHolidayReminderDaily
#    schtasks /Delete /TN ZhuopinAnnualHolidayReminderDaily /F
# ================================================================
param(
    # 同 register-decision-reminder-task.ps1 惯例：只重生成 wrapper、跳过
    # 注销+重注册，用于"wrapper 内容坏了但任务定义没问题"的修复场景。
    [switch] $SkipTaskRegistration
)
$ErrorActionPreference = "Stop"

# 孤立 CR 断言器（队列 #355）——与另两份注册脚本共用同一份，不各自复制。
. (Join-Path $PSScriptRoot "assert-no-orphan-cr.ps1")

$REPO         = "C:\Dev\zhuopin-ai\.claude\worktrees\wecom-service-home"
$MAIN_WORKSPACE_QUEUE = "C:\Dev\zhuopin-ai\1-转型规划\0-全景路线图\跨桌任务队列-机制环境.md"
$SERVICE_DIR  = Join-Path $REPO "5-平台底座\wecom-aibot-service"
$CHECK_SCRIPT = Join-Path $SERVICE_DIR "scripts\annual_holiday_reminder.py"
$WRAPPER      = Join-Path $SERVICE_DIR "run-annual-holiday-reminder-check.ps1"
$VBS_LAUNCHER = Join-Path $SERVICE_DIR "run-annual-holiday-reminder-hidden.vbs"
$TASK         = "ZhuopinAnnualHolidayReminderDaily"
$DAILY_TIME   = "08:35"

Write-Host "`n== 注册队列 #379 年度节假日日历提醒计划任务（每日触发、内部按日期门控）==" -ForegroundColor Cyan
Write-Host "   服务常驻 worktree: $REPO"
Write-Host "   检查脚本: $CHECK_SCRIPT"
Write-Host "   周期    : 每天 $DAILY_TIME（只在 9 月 1 日实际发送）`n"

if (-not (Test-Path $CHECK_SCRIPT)) {
    Write-Error "未找到 $CHECK_SCRIPT —— 请确认 ops/wecom-service-home 已同步到含本脚本的 commit。"
    exit 1
}
if (-not (Test-Path $VBS_LAUNCHER)) {
    Write-Error "未找到 $VBS_LAUNCHER —— 请确认 ops/wecom-service-home 已同步到含本文件的 commit。"
    exit 1
}
$gitMarker = Join-Path $REPO ".git"
if (-not (Test-Path $gitMarker)) {
    Write-Error "$gitMarker 不存在（$REPO 可能已不是有效的 git worktree）——已中止。"
    exit 1
}

Write-Host "[1/3] 解析 python 绝对路径 + 计划任务运行身份..." -ForegroundColor Yellow
$pyCmd = Get-Command python -ErrorAction SilentlyContinue
if (-not $pyCmd) { Write-Error "未找到 python，请确认已安装并加入当前用户 PATH。"; exit 1 }
$pyExe = $pyCmd.Source
$currentUser = (whoami).Trim()
Write-Host "      python  : $pyExe" -ForegroundColor Green
Write-Host "      运行身份: $currentUser" -ForegroundColor Green

Write-Host "[2/3] 生成 run-annual-holiday-reminder-check.ps1..." -ForegroundColor Yellow
# 🔴 单引号 here-string（队列 #355 教训）：零转义零插值，三个真实值改由
# 下方占位符 .Replace() 显式代入。不得改回双引号 here-string。
$wrapperTemplate = @'
# 队列 #379 年度节假日日历提醒启动包装（由 register-annual-holiday-reminder-task.ps1
# 生成，勿手改——重跑注册脚本会覆盖此文件）。绝对路径烘焙进来，不依赖计划
# 任务触发时的运行时 PATH（同落库 sweep/decision_reminder 惯例）。
$env:WECOM_AIBOT_QUEUE_PATH = "__MAIN_WORKSPACE_QUEUE__"
& "__PY_EXE__" "__CHECK_SCRIPT__"
exit $LASTEXITCODE
'@
$wrapperContent = $wrapperTemplate.Replace('__MAIN_WORKSPACE_QUEUE__', $MAIN_WORKSPACE_QUEUE)
$wrapperContent = $wrapperContent.Replace('__PY_EXE__', $pyExe)
$wrapperContent = $wrapperContent.Replace('__CHECK_SCRIPT__', $CHECK_SCRIPT)

Assert-NoOrphanCR -Text $wrapperContent -Label "run-annual-holiday-reminder-check.ps1 模板（写盘前）"
Set-Content -Path $WRAPPER -Value $wrapperContent -Encoding UTF8
Assert-NoOrphanCR -Path $WRAPPER -Label "已写盘的 run-annual-holiday-reminder-check.ps1"
Write-Host "      已生成 $WRAPPER（孤立 CR 自检通过）" -ForegroundColor Green

if ($SkipTaskRegistration) {
    Write-Host "[3/3] 已按 -SkipTaskRegistration 跳过计划任务注册。" -ForegroundColor Yellow
    Write-Host "      $TASK 的既有定义保持不变；本次只重生成了 wrapper。" -ForegroundColor DarkGray
    Write-Host "`n完成（仅重生成 wrapper）。" -ForegroundColor Green
    exit 0
}

Write-Host "[3/3] 注册计划任务 $TASK..." -ForegroundColor Yellow
if (Get-ScheduledTask -TaskName $TASK -ErrorAction SilentlyContinue) {
    Unregister-ScheduledTask -TaskName $TASK -Confirm:$false
}
$action = New-ScheduledTaskAction -Execute "wscript.exe" -Argument "`"$VBS_LAUNCHER`"" -WorkingDirectory $REPO
$trigger = New-ScheduledTaskTrigger -Daily -At $DAILY_TIME

$principal = New-ScheduledTaskPrincipal -UserId $currentUser -LogonType Interactive
$settings  = New-ScheduledTaskSettingsSet -ExecutionTimeLimit (New-TimeSpan -Minutes 10) `
    -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries

Register-ScheduledTask -TaskName $TASK `
    -Action $action -Trigger $trigger `
    -Principal $principal -Settings $settings `
    -Description ("队列 #379：每天检查一次，仅在 9 月 1 日向李姣龙发送次年节假日" +
                  "日历更新提醒（含存活自证心跳），详见 scripts/annual_holiday_reminder.py") `
    | Out-Null
Write-Host "      已注册（每天 $DAILY_TIME）" -ForegroundColor Green

Write-Host "`n注册完成。" -ForegroundColor Green
Write-Host "   立即手动跑一次（验证，今天非 9-1 只会刷心跳）: Start-ScheduledTask -TaskName $TASK" -ForegroundColor DarkGray
Write-Host "   查看上次运行结果      : Get-ScheduledTaskInfo -TaskName $TASK" -ForegroundColor DarkGray
Write-Host "   回滚                  : schtasks /End /TN $TASK ; schtasks /Delete /TN $TASK /F" -ForegroundColor DarkGray
