# ================================================================
#  register-decision-reminder-task.ps1
#  用途：把 scripts/decision_reminder_check.py 注册为每日定时任务（队列 #172
#  ②"每日超期汇总"）——扫队列 §四 已过截止项 + §一 P0/P1 待领超期行，按
#  1/3/7 天递减升级私信 Shao Peishen；判定纯函数见
#  aibot_service/decision_reminder.py，不做任何主观新增，只登记本机计划任务。
#
#  Action 指向主工作区稳定路径（同 工具-注册落库sweep计划任务.ps1 惯例，
#  #49 教训：勿指向任何 .claude\worktrees\<name> 建造 worktree，防止该
#  worktree 完工后 `git worktree remove` 掉导致任务失效）；本脚本内部通过
#  `resolve_repo_root` 动态解析真实仓库根，理论上从哪个 checkout 跑都行，
#  但注册时仍固定选主工作区，图的是"路径不会消失"这个稳定性保证，而非
#  解析能力本身的必要性。
#
#  运行身份沿用落库 sweep 那次的 #96 教训：SYSTEM 账户对 OneDrive 个人版
#  路径无 ACL 访问权限会静默零执行——用当前账户 + LogonType S4U。
#
#  用法（本机管理员或当前用户 PowerShell，在主工作区目录下执行一次；
#        重复执行幂等——会先注销旧任务再重建）：
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

$REPO         = "C:\Users\Paul Shao\OneDrive\Projects\企业AI转型"
$SERVICE_DIR  = Join-Path $REPO "5-平台底座\wecom-aibot-service"
$CHECK_SCRIPT = Join-Path $SERVICE_DIR "scripts\decision_reminder_check.py"
$WRAPPER      = Join-Path $SERVICE_DIR "run-decision-reminder-check.ps1"
$TASK         = "ZhuopinDecisionReminderDaily"
$DAILY_TIME   = "08:30"

Write-Host "`n== 注册需 Shao Peishen 决策项每日超期汇总计划任务 ==" -ForegroundColor Cyan
Write-Host "   主工作区: $REPO"
Write-Host "   检查脚本: $CHECK_SCRIPT"
Write-Host "   周期    : 每天 $DAILY_TIME`n"

if (-not (Test-Path $CHECK_SCRIPT)) {
    Write-Error "未找到 $CHECK_SCRIPT —— 请确认在主工作区（非 worktree）执行本脚本。"
    exit 1
}
$gitMarker = Join-Path $REPO ".git"
if (-not (Test-Path $gitMarker -PathType Container)) {
    Write-Error "$gitMarker 不是目录（当前路径可能是某个 linked worktree，而非主工作区）——已中止。"
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
