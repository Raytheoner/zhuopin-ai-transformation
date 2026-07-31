# ================================================================
#  register-decision-reminder-task.ps1
#  用途：把 scripts/decision_reminder_check.py 注册为每日定时任务（队列 #172
#  ②"每日超期汇总"）——扫队列 §四 已过截止项 + §一 P0/P1 待领超期行，按
#  1/3/7 天递减升级私信 Shao Peishen；判定纯函数见
#  aibot_service/decision_reminder.py，不做任何主观新增，只登记本机计划任务。
#
#  Action 指向 `ops/wecom-service-home`（本服务的长驻 worktree，与
#  ZhuopinAibotDevListener 同一个 checkout）——与落库 sweep 那份注册脚本
#  惯例不同：sweep 直接改写主工作区队列文件，必须固定指主工作区；本脚本
#  只读队列文件+独立发一条消息，不修改任何 git 仓库内容，且它 import 的
#  `aibot_service` 包与所需 `.env` 凭据本就长驻在这个 worktree（同该服务
#  其余组件一致），选这里比选主工作区更贴合实际依赖，也不违反"勿指临时
#  建造 worktree"的精神——`ops/` 前缀的服务常驻 worktree 本就是稳定路径，
#  不会被 `git worktree remove` 掉（同 #49/§5"长驻服务类 worktree"惯例）。
#  本脚本内部通过 `resolve_repo_root` 动态解析队列文件真实所属仓库根，
#  与从哪个 checkout 触发无关。
#
#  运行身份沿用落库 sweep 那次的 #96 教训：SYSTEM 账户对 OneDrive 个人版
#  路径无 ACL 访问权限会静默零执行——用当前账户 + LogonType S4U。
#
#  用法（本机管理员或当前用户 PowerShell，在 ops/wecom-service-home 目录下
#        执行一次；重复执行幂等——会先注销旧任务再重建）：
#    powershell -ExecutionPolicy Bypass -File "5-平台底座\wecom-aibot-service\register-decision-reminder-task.ps1"
#
#  验证：
#    Start-ScheduledTask -TaskName ZhuopinDecisionReminderDaily
#    Get-ScheduledTaskInfo -TaskName ZhuopinDecisionReminderDaily
#
#  回滚：
#    schtasks /End /TN ZhuopinDecisionReminderDaily
#    schtasks /Delete /TN ZhuopinDecisionReminderDaily /F
# ================================================================
$ErrorActionPreference = "Stop"

$REPO         = "C:\Users\Paul Shao\OneDrive\Projects\企业AI转型\.claude\worktrees\wecom-service-home"
$SERVICE_DIR  = Join-Path $REPO "5-平台底座\wecom-aibot-service"
$CHECK_SCRIPT = Join-Path $SERVICE_DIR "scripts\decision_reminder_check.py"
$WRAPPER      = Join-Path $SERVICE_DIR "run-decision-reminder-check.ps1"
$TASK         = "ZhuopinDecisionReminderDaily"
$DAILY_TIME   = "08:30"

Write-Host "`n== 注册需 Shao Peishen 决策项每日超期汇总计划任务 ==" -ForegroundColor Cyan
Write-Host "   服务常驻 worktree: $REPO"
Write-Host "   检查脚本: $CHECK_SCRIPT"
Write-Host "   周期    : 每天 $DAILY_TIME`n"

if (-not (Test-Path $CHECK_SCRIPT)) {
    Write-Error "未找到 $CHECK_SCRIPT —— 请确认 ops/wecom-service-home 已同步到含本脚本的 commit。"
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

Write-Host "[2/3] 生成 run-decision-reminder-check.ps1..." -ForegroundColor Yellow
$wrapperContent = @"
# 需 Shao Peishen 决策项每日超期汇总启动包装（由 register-decision-reminder-task.ps1
# 生成，勿手改——重跑注册脚本会覆盖此文件）。绝对路径烘焙进来，不依赖计划
# 任务触发时的运行时 PATH（同落库 sweep 惯例，见 #79 教训）。
& "$pyExe" "$CHECK_SCRIPT"
exit `$LASTEXITCODE
"@
Set-Content -Path $WRAPPER -Value $wrapperContent -Encoding UTF8
Write-Host "      已生成 $WRAPPER" -ForegroundColor Green

Write-Host "[3/3] 注册计划任务 $TASK..." -ForegroundColor Yellow
if (Get-ScheduledTask -TaskName $TASK -ErrorAction SilentlyContinue) {
    Unregister-ScheduledTask -TaskName $TASK -Confirm:$false
}
$psArgs = "-NoProfile -ExecutionPolicy Bypass -File `"$WRAPPER`""
$action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument $psArgs -WorkingDirectory $REPO
$trigger = New-ScheduledTaskTrigger -Daily -At $DAILY_TIME

$principal = New-ScheduledTaskPrincipal -UserId $currentUser -LogonType S4U
$settings  = New-ScheduledTaskSettingsSet -ExecutionTimeLimit (New-TimeSpan -Minutes 10) `
    -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries

Register-ScheduledTask -TaskName $TASK `
    -Action $action -Trigger $trigger `
    -Principal $principal -Settings $settings `
    -Description ("队列 #172：每日扫 §四 已过截止项 + §一 P0/P1 待领超期行，" +
                  "按 1/3/7 天递减升级私信 Shao Peishen，详见 aibot_service/decision_reminder.py") `
    | Out-Null
Write-Host "      已注册（每天 $DAILY_TIME）" -ForegroundColor Green

Write-Host "`n注册完成。" -ForegroundColor Green
Write-Host "   立即手动跑一次（验证）: Start-ScheduledTask -TaskName $TASK" -ForegroundColor DarkGray
Write-Host "   查看上次运行结果      : Get-ScheduledTaskInfo -TaskName $TASK" -ForegroundColor DarkGray
Write-Host "   回滚                  : schtasks /End /TN $TASK ; schtasks /Delete /TN $TASK /F" -ForegroundColor DarkGray
