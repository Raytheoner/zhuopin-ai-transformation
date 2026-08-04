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
#  运行身份：当前账户 + LogonType Interactive（2026-07-31 实测教训——落库
#  sweep 那份脚本用的 `LogonType S4U` 在本机注册**新**任务时报
#  `Register-ScheduledTask : Access is denied`（S4U 需要"以批处理作业登录"
#  权限，赋予该权限的动作本身要求管理员权限，即便任务运行期不需要；已
#  分别单独验证 S4U 失败/Interactive 成功，隔离出是登录类型而非其他配置
#  项导致）；`ZhuopinAibotDevListener` 本身也是 `LogonType=InteractiveToken`
#  非 S4U，属本项目已有先例。代价：Interactive 要求触发时用户已登录本机
#  （笔记本工作日常态，可接受）；若未来需要"未登录也能跑"，须由 Paul 或
#  管理员账户手动重跑本脚本改用 S4U/Password 登录类型。
#
#  队列 #231（2026-08-04，环境保障线取证）：Action 此前直接 Execute=powershell.exe，
#          每天 08:30 触发都会弹出一闪而过的控制台窗口（Shao Peishen 反馈"屏幕
#          一闪不知做了啥"）。本项目已有验证过的根治范式（同账户下的
#          ZhuopinAibotDevListener，见 run-hidden.vbs）：改用
#          "wscript.exe + WScript.Shell.Run SW_HIDE(0)"，Action 改为
#          Execute=wscript.exe，Argument 指向新增的
#          run-decision-reminder-hidden.vbs（committed、无机器专属路径，动态
#          解析自身所在目录），由它拉起本脚本原生成的
#          run-decision-reminder-check.ps1（内容不变）。⚠️ 两处未实测，如实
#          标注：①单把 Settings.Hidden=$true 是否足以消除控制台窗口未验证过
#          （对本任务同样不赌，直接走 VBS）；②本次只改了 Action 定义、未在
#          真实机器上重新 Register-ScheduledTask 验证——收工不触碰 .51 与
#          常驻服务，改后需 Shao Peishen/CC 后续（待 ops/wecom-service-home
#          同步到含本次改动的提交后）重跑本脚本一次才会在生产任务上生效。
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
$MAIN_WORKSPACE_QUEUE = "C:\Users\Paul Shao\OneDrive\Projects\企业AI转型\1-转型规划\0-全景路线图\跨桌任务队列.md"
$SERVICE_DIR  = Join-Path $REPO "5-平台底座\wecom-aibot-service"
$CHECK_SCRIPT = Join-Path $SERVICE_DIR "scripts\decision_reminder_check.py"
$WRAPPER      = Join-Path $SERVICE_DIR "run-decision-reminder-check.ps1"
$VBS_LAUNCHER = Join-Path $SERVICE_DIR "run-decision-reminder-hidden.vbs"
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
if (-not (Test-Path $VBS_LAUNCHER)) {
    Write-Error "未找到 $VBS_LAUNCHER —— 请确认 ops/wecom-service-home 已同步到含本文件的 commit（队列 #231）。"
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
#
# WECOM_AIBOT_QUEUE_PATH 显式指向主工作区队列文件（2026-07-31 实测教训）：
# decision_reminder_check.py 默认按自身 __file__ 反推仓库根，若不显式指定，
# 在本 ops/wecom-service-home worktree 里跑会读到**这个 worktree 自己的
# 队列文件副本**（需手动同步、可能滞后）而非主工作区实时内容，审计也会
# 写进这个 worktree 自己的 reports/，与 push_followup_letter.py 等脚本写
# 主工作区那份分裂成两份（正是队列 #126 修复过的同类问题，本脚本若不显式
# 指定队列锚点就会重犯）。显式设置后，`resolve_repo_root` 会以这个路径为
# 锚点动态解析出主工作区根，队列内容与审计落点都对齐到唯一权威位置。
`$env:WECOM_AIBOT_QUEUE_PATH = "$MAIN_WORKSPACE_QUEUE"
& "$pyExe" "$CHECK_SCRIPT"
exit `$LASTEXITCODE
"@
Set-Content -Path $WRAPPER -Value $wrapperContent -Encoding UTF8
Write-Host "      已生成 $WRAPPER" -ForegroundColor Green

Write-Host "[3/3] 注册计划任务 $TASK..." -ForegroundColor Yellow
if (Get-ScheduledTask -TaskName $TASK -ErrorAction SilentlyContinue) {
    Unregister-ScheduledTask -TaskName $TASK -Confirm:$false
}
# 队列 #231：Execute 改为 wscript.exe 拉起隐藏窗口的 VBS 启动器（同
# ZhuopinAibotDevListener 既有范式），不再直接 Execute=powershell.exe——见
# 文件头部说明。VBS 内部仍会拉起上面这份 $WRAPPER（内容不变）。
$action = New-ScheduledTaskAction -Execute "wscript.exe" -Argument "`"$VBS_LAUNCHER`"" -WorkingDirectory $REPO
$trigger = New-ScheduledTaskTrigger -Daily -At $DAILY_TIME

$principal = New-ScheduledTaskPrincipal -UserId $currentUser -LogonType Interactive
# 队列 #199：此前缺 -StartWhenAvailable——ZhuopinCommitSweep/ZhuopinAibotDevListener
# 均已带此项（#189），本任务是同日稍晚新建、注册脚本没带上，属"靠照抄
# 上一个传承"漏项（#96 清单要防的形态）。缺此项时错过的每日 08:30 触发
# 不会在机器后续开机/唤醒后补跑，#192-A 的第二道兜底 flush 恰好挂在本任务
# 上，唯一被需要的场景（周末/清晨未开机）下会一并失效。
$settings  = New-ScheduledTaskSettingsSet -ExecutionTimeLimit (New-TimeSpan -Minutes 10) `
    -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries

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
