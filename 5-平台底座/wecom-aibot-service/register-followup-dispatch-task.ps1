# ================================================================
#  register-followup-dispatch-task.ps1
#  用途：把 scripts/dispatch_followup_letters.py 注册为每日定时任务
#  （队列 #124 阶段二，design.md D2）——工作日 09:30 扫描跟进信 README，
#  发送「发送状态」严格等于 `🆕 待发` 且未被 `🔒人工发送`/D7 机器判据
#  跳过的行；判定逻辑见 aibot_service/dispatch.py，本脚本只登记计划任务。
#
#  Action 指向 `ops/wecom-service-home`（本服务的长驻 worktree，与
#  ZhuopinAibotDevListener/ZhuopinDecisionReminderDaily 同一个 checkout）——
#  同 register-decision-reminder-task.ps1 惯例：本脚本只读 README+发一批
#  消息，不修改任何 git 仓库内容，且它 import 的 `aibot_service` 包与所需
#  `.env` 凭据本就长驻在这个 worktree。
#
#  触发时刻 09:30（design.md D2/Open Questions，2026-08-04 Shao Peishen
#  审 design 时由默认建议 17:30 改定）：17:30 发出的信落在专员下班后，
#  抢出的半天没有兑现，且若发错整晚无人在场补救；09:30 慢半天但专员
#  在岗、误发有一整天可挽回。与决策提醒（08:30）间隔 1 小时、与拆件巡逻
#  首班（9:00）间隔 30 分钟，避免同批触发相互干扰。
#
#  运行身份：当前账户 + LogonType Interactive（同 ZhuopinDecisionReminderDaily
#  既有教训——LogonType S4U 在本机注册**新**任务会报 Access denied，S4U
#  需要"以批处理作业登录"权限，赋予该权限本身要求管理员权限）。代价：
#  触发时用户需已登录本机（笔记本工作日常态，可接受）。
#
#  Action 直接用 wscript.exe + run-followup-dispatch-hidden.vbs（同
#  ZhuopinDecisionReminderDaily/ZhuopinAibotDevListener 既有范式，非事后
#  补丁）——不弹出一闪而过的控制台窗口。
#
#  用法（本机管理员或当前用户 PowerShell，在 ops/wecom-service-home 目录下
#        执行一次；重复执行幂等——会先注销旧任务再重建）：
#    powershell -ExecutionPolicy Bypass -File "5-平台底座\wecom-aibot-service\register-followup-dispatch-task.ps1"
#
#  验证：
#    Start-ScheduledTask -TaskName ZhuopinFollowupDispatchDaily
#    Get-ScheduledTaskInfo -TaskName ZhuopinFollowupDispatchDaily
#    (Get-ScheduledTask -TaskName ZhuopinFollowupDispatchDaily).Actions[0].Execute   # 应为 wscript.exe
#
#  回滚：
#    schtasks /End /TN ZhuopinFollowupDispatchDaily
#    schtasks /Delete /TN ZhuopinFollowupDispatchDaily /F
# ================================================================
$ErrorActionPreference = "Stop"

$REPO         = "C:\Users\Paul Shao\OneDrive\Projects\企业AI转型\.claude\worktrees\wecom-service-home"
$MAIN_WORKSPACE_QUEUE = "C:\Users\Paul Shao\OneDrive\Projects\企业AI转型\1-转型规划\0-全景路线图\跨桌任务队列.md"
$SERVICE_DIR  = Join-Path $REPO "5-平台底座\wecom-aibot-service"
$DISPATCH_SCRIPT = Join-Path $SERVICE_DIR "scripts\dispatch_followup_letters.py"
$WRAPPER      = Join-Path $SERVICE_DIR "run-followup-dispatch-check.ps1"
$VBS_LAUNCHER = Join-Path $SERVICE_DIR "run-followup-dispatch-hidden.vbs"
$TASK         = "ZhuopinFollowupDispatchDaily"
$DAILY_TIME   = "09:30"

Write-Host "`n== 注册每日跟进信自动发信计划任务（队列 #124 阶段二）==" -ForegroundColor Cyan
Write-Host "   服务常驻 worktree: $REPO"
Write-Host "   发信脚本: $DISPATCH_SCRIPT"
Write-Host "   周期    : 工作日每天 $DAILY_TIME`n"

if (-not (Test-Path $DISPATCH_SCRIPT)) {
    Write-Error "未找到 $DISPATCH_SCRIPT —— 请确认 ops/wecom-service-home 已同步到含本脚本的 commit。"
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

Write-Host "[2/3] 生成 run-followup-dispatch-check.ps1..." -ForegroundColor Yellow
$wrapperContent = @"
# 每日跟进信自动发信启动包装（由 register-followup-dispatch-task.ps1
# 生成，勿手改——重跑注册脚本会覆盖此文件）。绝对路径烘焙进来，不依赖
# 计划任务触发时的运行时 PATH（同落库 sweep/decision_reminder 惯例）。
#
# WECOM_AIBOT_QUEUE_PATH 显式指向主工作区队列文件（同 decision_reminder
# 既有教训）：dispatch_followup_letters.py 默认按自身 __file__ 反推仓库根，
# 若不显式指定，在本 ops/wecom-service-home worktree 里跑会读到**这个
# worktree 自己的 README/队列副本**（需手动同步、可能滞后）而非主工作区
# 实时内容，审计也会写进这个 worktree 自己的 reports/，与其余脚本分裂
# （正是队列 #126 修复过的同类问题）。显式设置后，resolve_repo_root 会
# 以这个路径为锚点动态解析出主工作区根，README/队列内容与审计落点都
# 对齐到唯一权威位置。
`$env:WECOM_AIBOT_QUEUE_PATH = "$MAIN_WORKSPACE_QUEUE"
& "$pyExe" "$DISPATCH_SCRIPT"
exit `$LASTEXITCODE
"@
Set-Content -Path $WRAPPER -Value $wrapperContent -Encoding UTF8
Write-Host "      已生成 $WRAPPER" -ForegroundColor Green

Write-Host "[3/3] 注册计划任务 $TASK..." -ForegroundColor Yellow
if (Get-ScheduledTask -TaskName $TASK -ErrorAction SilentlyContinue) {
    Unregister-ScheduledTask -TaskName $TASK -Confirm:$false
}
# 队列 #231 同款范式：Execute=wscript.exe 拉起隐藏窗口的 VBS 启动器，不
# 直接 Execute=powershell.exe（避免每次触发弹出一闪而过的控制台窗口）。
$action = New-ScheduledTaskAction -Execute "wscript.exe" -Argument "`"$VBS_LAUNCHER`"" -WorkingDirectory $REPO
$trigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Monday,Tuesday,Wednesday,Thursday,Friday -At $DAILY_TIME

$principal = New-ScheduledTaskPrincipal -UserId $currentUser -LogonType Interactive
# 同 ZhuopinDecisionReminderDaily 既有教训（#199）：缺 -StartWhenAvailable
# 时，错过的每日 09:30 触发不会在机器后续开机/唤醒后补跑——design.md D2/D3
# "不承诺准点、只承诺下次开机即处理"的可靠性模型正是靠这一项落地。
$settings  = New-ScheduledTaskSettingsSet -ExecutionTimeLimit (New-TimeSpan -Minutes 10) `
    -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries

Register-ScheduledTask -TaskName $TASK `
    -Action $action -Trigger $trigger `
    -Principal $principal -Settings $settings `
    -Description ("队列 #124 阶段二：工作日 09:30 扫描跟进信 README 并发送已批准（`🆕 待发`）" +
                  "且未被硬截止/漏标判据跳过的行，详见 aibot_service/dispatch.py") `
    | Out-Null
Write-Host "      已注册（工作日每天 $DAILY_TIME）" -ForegroundColor Green

Write-Host "`n注册完成。" -ForegroundColor Green
Write-Host "   立即手动跑一次（验证）: Start-ScheduledTask -TaskName $TASK" -ForegroundColor DarkGray
Write-Host "   查看上次运行结果      : Get-ScheduledTaskInfo -TaskName $TASK" -ForegroundColor DarkGray
Write-Host "   复核启动方式          : (Get-ScheduledTask -TaskName $TASK).Actions[0].Execute" -ForegroundColor DarkGray
Write-Host "   回滚                  : schtasks /End /TN $TASK ; schtasks /Delete /TN $TASK /F" -ForegroundColor DarkGray
