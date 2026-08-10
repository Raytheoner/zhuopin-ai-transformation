# ================================================================
#  register-tax-export-scan-task.ps1
#  用途：把 scripts/scan_tax_export_scheduled.py 注册为每日定时任务（队列 #82
#  第2层"定时扫描+失败告警"）——扫 D:\airead 新增税务导出文件、摄取入
#  data/tax_export/（内容哈希幂等，与手动 CLI scripts/ingest_tax_export.py
#  共享同一 out-dir/ledger，谁先跑到都一样、互不冲突）。文件级摄取失败
#  （sheet 名/必需列不符、整份文件解析不出——今天 #82 sheet 名事故正是这一类）
#  经既有群 webhook 逃生通道告警 Shao Peishen；行级诊断（ap_no_zero_match 等，
#  真实数据约 89% 属预期噪声）不告警，见 fi2/tax_export_scan.py 模块 docstring。
#
#  运行位置：在【服务器 192.168.100.51】C:\fi2\app 本地以管理员运行
#  （与 deploy-server.ps1 同语境，非在笔记本/worktree 上跑）——摄取目标
#  D:\airead 与产出目录 C:\fi2\app\data\tax_export 均为 .51 本地路径。
#
#    cd C:\fi2\app
#    powershell -ExecutionPolicy Bypass -File register-tax-export-scan-task.ps1
#
#  前置：deploy-server.ps1 已跑过（venv 已建）；.env 已配置 U9C_*/STOCK_API_*
#  （复用 Fi2WebServer 既有凭据，见场景 CLAUDE.md D19 部署段）；如需告警生效，
#  另需 .env 配置 WECOM_WEBHOOK_URL（未配置时静默跳过告警，不阻断扫描本身，
#  见 fi2/tax_export_scan.py `_try_alert` 既有降级方式）。
#
#  运行身份：SYSTEM + ServiceAccount 登录（同 Fi2WebServer 既有先例——SYSTEM
#  只认机器级 PATH，故下方 Execute 用 venv 内 python.exe 绝对路径，不传裸命令名，
#  同 ZhuopinDeploy.psm1::Register-ZhuopinScheduledTask 头部注释①既有教训）。
#
#  调度时点：每天 10:30（她 08-06 定的投放执行口径是"工作日上午 10 点前"，
#  留 30 分钟缓冲；内容哈希幂等，周末/节假日空跑无副作用，故用简单的 -Daily
#  而非按周几过滤，同 ZhuopinDecisionReminderDaily/ZhuopinCommitSweep 既有惯例）。
#
#  验证：
#    Start-ScheduledTask -TaskName Fi2TaxExportDailyScan
#    Get-ScheduledTaskInfo -TaskName Fi2TaxExportDailyScan
#
#  回滚：
#    schtasks /End /TN Fi2TaxExportDailyScan
#    schtasks /Delete /TN Fi2TaxExportDailyScan /F
# ================================================================
$ErrorActionPreference = "Stop"

$APP         = $PSScriptRoot                                     # C:\fi2\app
$BASE        = Split-Path $APP -Parent                           # C:\fi2
$VENV        = Join-Path $BASE ".venv"
$PY          = Join-Path $VENV "Scripts\python.exe"
$SCAN_SCRIPT = Join-Path $APP "scripts\scan_tax_export_scheduled.py"
$EXPORT_DIR  = "D:\airead"
$OUT_DIR     = Join-Path $APP "data\tax_export"
$TASK        = "Fi2TaxExportDailyScan"
$DAILY_TIME  = "10:30"

Write-Host "`n== 注册 FI2 税务导出定时扫描计划任务（队列 #82 第2层） ==" -ForegroundColor Cyan
Write-Host "   扫描脚本: $SCAN_SCRIPT"
Write-Host "   摄取目录: $EXPORT_DIR -> $OUT_DIR"
Write-Host "   周期    : 每天 $DAILY_TIME`n"

if (-not (Test-Path $PY)) {
    Write-Error "未找到 $PY —— 请先在 $APP 跑一次 deploy-server.ps1 完成 venv 安装。"
    exit 1
}
if (-not (Test-Path $SCAN_SCRIPT)) {
    Write-Error "未找到 $SCAN_SCRIPT —— 请确认已用 sync-to-server.ps1 同步含本文件的最新代码。"
    exit 1
}

Write-Host "[1/2] 生成计划任务参数..." -ForegroundColor Yellow
$argument = "`"$SCAN_SCRIPT`" --export-dir `"$EXPORT_DIR`" --out-dir `"$OUT_DIR`""
Write-Host "      $PY $argument" -ForegroundColor DarkGray

Write-Host "[2/2] 注册计划任务 $TASK..." -ForegroundColor Yellow
if (Get-ScheduledTask -TaskName $TASK -ErrorAction SilentlyContinue) {
    Unregister-ScheduledTask -TaskName $TASK -Confirm:$false   # 重建以更新路径/设置
}
$action = New-ScheduledTaskAction -Execute $PY -Argument $argument -WorkingDirectory $APP
$trigger = New-ScheduledTaskTrigger -Daily -At $DAILY_TIME
$principal = New-ScheduledTaskPrincipal -UserId "SYSTEM" -LogonType ServiceAccount -RunLevel Highest
$settings = New-ScheduledTaskSettingsSet -ExecutionTimeLimit (New-TimeSpan -Minutes 15) `
    -StartWhenAvailable -AllowStartIfOnBatteries `
    -RestartCount 2 -RestartInterval (New-TimeSpan -Minutes 5)

Register-ScheduledTask -TaskName $TASK `
    -Action $action -Trigger $trigger `
    -Principal $principal -Settings $settings `
    -Description ("队列 #82 第2层：每日扫 D:\airead 新增税务导出文件并摄取入 " +
                  "data\tax_export，文件级失败经群 webhook 告警 Shao Peishen") `
    | Out-Null
Write-Host "      已注册（每天 $DAILY_TIME）" -ForegroundColor Green

Write-Host "`n注册完成。" -ForegroundColor Green
Write-Host "   立即手动跑一次（验证）: Start-ScheduledTask -TaskName $TASK" -ForegroundColor DarkGray
Write-Host "   查看上次运行结果      : Get-ScheduledTaskInfo -TaskName $TASK" -ForegroundColor DarkGray
Write-Host "   回滚                  : schtasks /End /TN $TASK ; schtasks /Delete /TN $TASK /F" -ForegroundColor DarkGray
