# ============================================================
#  企微智能机器人双向通道服务 — 长开服务器部署（照搬 SC8 baoguan-web-service 套路）
#
#  ⚠️ 现状（2026-08-04 核实，队列 #167）：本脚本对应 D1（2026-07-11）"部署到 .51"
#  的原定计划，但服务实际常驻改为 Paul 的 Windows 笔记本（计划任务
#  `ZhuopinAibotDevListener`，走 `ops/wecom-service-home` worktree 本地的
#  `start-aibot-service-dev.ps1`，未纳入版本控制），本脚本目前不在生产链路上
#  ——同一处理原则见姊妹脚本 `sync-to-server.ps1` 头部说明。**保留、不删**：
#  供日后 Paul 拍板把本服务正式发布到 .51 时直接用（同 #96 部署标准清单口径）。
#  本次补齐 UTF-8 BOM，避免届时在 .51 内建 Windows PowerShell 5.1 上执行时
#  因无 BOM 被按系统 ANSI 误读中文而语法报错（同 2026-07-21 命令中心已踩坑）。
#
#  在【服务器 192.168.100.51】上以管理员运行（首次部署 / 依赖变更时）：
#    cd C:\wecom-aibot\app
#    powershell -ExecutionPolicy Bypass -File deploy-server.ps1
#
#  布局（由笔记本 sync-to-server.ps1 推送形成）：
#    C:\wecom-aibot\zhuopin_platform\   平台底座包
#    C:\wecom-aibot\app\                本工程（本脚本所在）
#    C:\wecom-aibot\.env                凭据（手工放，不入库）—— 与 5-平台底座/.env 同层级约定
#
#  与 SC8 baoguan-web-service（8091）的关键差异（design.md D1）：
#    本服务是**纯出站 WebSocket 客户端**（wss://openws.work.weixin.qq.com），
#    不监听任何端口，不需要开任何入站防火墙规则。
#
#  单连接看门狗（design.md D2 第一道防线）：
#    计划任务设 -MultipleInstances IgnoreNew——若任务已在运行，不再启动新实例，
#    从源头避免 .51 上同时出现两个进程互踢同一 BotID 的长连接。
#
#  三级重启退避（design.md D2 第三道防线）：
#    Windows 计划任务的 RestartCount/RestartInterval 只支持单一固定间隔，无法
#    表达"1分钟→5分钟→15分钟"三级退避——改为 start-aibot-service.ps1 包装脚本
#    自行实现三级退避循环，计划任务只需在开机时启动这一个包装脚本一次。
# ============================================================

$ErrorActionPreference = "Stop"

$APP      = $PSScriptRoot                         # C:\wecom-aibot\app
$BASE     = Split-Path $APP -Parent               # C:\wecom-aibot
$PLATFORM = Join-Path $BASE "zhuopin_platform"
$VENV     = Join-Path $BASE ".venv"
$TASK     = "WecomAibotService"
$RUNSCRIPT = Join-Path $APP "scripts\run_aibot_service.py"
$ALERTSCRIPT = Join-Path $APP "scripts\alert_webhook.py"

Import-Module (Join-Path $BASE "deploy-tools\ZhuopinDeploy.psm1") -Force

Write-Host "`n== 企微智能机器人双向通道服务 — 服务器部署 ==" -ForegroundColor Cyan
Write-Host "   基目录  : $BASE"
Write-Host "   平台底座: $PLATFORM"
Write-Host "   本工程  : $APP`n"

if (-not (Test-Path $PLATFORM)) { Write-Error "未找到 $PLATFORM —— 请先在笔记本跑 sync-to-server.ps1 推送代码。"; exit 1 }

# ── 1. Python ──
Write-Host "[1/7] 检查 Python..." -ForegroundColor Yellow
if (-not (Get-Command python -ErrorAction SilentlyContinue)) { Write-Error "未找到 Python，请装 3.11+ 并 Add to PATH。"; exit 1 }
Write-Host "      $(python --version 2>&1)" -ForegroundColor Green

# ── 2. venv ──
Write-Host "[2/7] 虚拟环境..." -ForegroundColor Yellow
if (-not (Test-Path $VENV)) { python -m venv $VENV; Write-Host "      已创建 $VENV" -ForegroundColor Green }
else { Write-Host "      已存在，跳过" -ForegroundColor Green }
$pipExe = Join-Path $VENV "Scripts\pip.exe"
$pyExe  = Join-Path $VENV "Scripts\python.exe"

# ── 3. editable 安装平台（含 [aibot] extra）+ 本工程 ──
Write-Host "[3/7] 安装依赖（zhuopin_platform[aibot] + wecom-aibot-service）..." -ForegroundColor Yellow
& $pipExe install --quiet -e "$PLATFORM[aibot]"
& $pipExe install --quiet -e $APP
Write-Host "      完成" -ForegroundColor Green

# ── 4. .env（基目录，凭据手工放；两套凭据并存）──
Write-Host "[4/7] 检查 .env..." -ForegroundColor Yellow
$envFile = Join-Path $BASE ".env"
if (-not (Test-Path $envFile)) {
    Write-Host "      .env 不存在，生成模板（填好真实凭据再启动）" -ForegroundColor DarkYellow
    $tpl = @"
# 企微智能机器人双向通道服务 — 环境变量（凭据只在本文件，不入库）

# 智能机器人长连接凭据（企微后台"智能机器人"→长连接模式获取，队列 §四#10）
WECOM_AIBOT_BOTID=
WECOM_AIBOT_SECRET=

# 既有 webhook 群机器人凭据（并存不改，仅供 alert_webhook.py 自身故障告警用）
WECOM_WEBHOOK_URL=

# 可选：覆盖默认路径（默认按仓库相对结构推导，通常不需要改）
# WECOM_AIBOT_EXTERNAL_DOCS_ROOT=
# WECOM_AIBOT_QUEUE_PATH=
# WECOM_AIBOT_AUDIT_PATH=
"@
    Set-Content -Path $envFile -Value $tpl -Encoding UTF8
    Write-Host "      模板已生成：$envFile —— 填好凭据后重跑本脚本或重启任务" -ForegroundColor Red
} else {
    Write-Host "      .env 已存在" -ForegroundColor Green
}
if (Test-Path $envFile) {
    $botLine = Get-Content $envFile | Where-Object { $_ -match '^\s*WECOM_AIBOT_BOTID=' }
    $botVal = if ($botLine) { ($botLine -split '=', 2)[1].Trim().Trim('"').Trim("'") } else { "" }
    if (-not $botVal) {
        Write-Host "      ⚠️ .env 里 WECOM_AIBOT_BOTID 为空/缺失 —— 服务启动会 fail-loud 报凭据缺失。" -ForegroundColor Red
        Write-Host "         需 Paul 完成队列 §四#10 前置动作（企微后台建智能机器人取 BotID/Secret）后回填。" -ForegroundColor Red
    }
}

# ── 5. 生成三级退避包装脚本（PowerShell 对中文/UTF-8 路径友好）──
Write-Host "[5/7] 生成 start-aibot-service.ps1（三级重启退避 1min/5min/15min）..." -ForegroundColor Yellow
$startPs1 = Join-Path $APP "start-aibot-service.ps1"
$startContent = @"
# Wecom Aibot service launcher — 三级重启退避（design.md D2 第三道防线）
# 计划任务只在开机时启动这一个脚本一次；退避循环由本脚本自行管理。
`$ErrorActionPreference = "Continue"
`$tiers = @(60, 300, 900)  # 秒：1分钟 / 5分钟 / 15分钟
`$attempt = 0
while (`$true) {
    Write-Host "[`$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] 启动企微智能机器人服务（第 `$(`$attempt + 1) 次）..."
    & "$pyExe" "$RUNSCRIPT"
    `$exitCode = `$LASTEXITCODE
    Write-Host "[`$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] 服务退出（exit=`$exitCode）"
    if (`$attempt -ge `$tiers.Length) {
        Write-Host "三级重启退避已耗尽，停止重启并告警。" -ForegroundColor Red
        & "$pyExe" "$ALERTSCRIPT" "企微智能机器人服务连续 `$(`$tiers.Length) 次崩溃退出（最近 exit=`$exitCode），已停止自动重启，请人工核查 .51 上的进程与 .env 凭据。"
        break
    }
    `$delay = `$tiers[`$attempt]
    Write-Host "第 `$(`$attempt + 1) 级退避：等待 `$delay 秒后重启..."
    Start-Sleep -Seconds `$delay
    `$attempt++
}
"@
Set-Content -Path $startPs1 -Value $startContent -Encoding UTF8
Write-Host "      已生成" -ForegroundColor Green

# ── 6. 计划任务（开机自启、SYSTEM、单实例、无入站端口）──
Write-Host "[6/7] 注册计划任务 $TASK..." -ForegroundColor Yellow
# RestartCount=0：本服务自行实现三级退避（start-aibot-service.ps1 的 while 循环），
# 不用计划任务原生的单级重启，避免两套重启机制互相打架。
Register-ZhuopinScheduledTask -TaskName $TASK `
    -Execute "powershell.exe" -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$startPs1`"" `
    -WorkingDirectory $APP -RestartCount 0 -MultipleInstancesIgnoreNew `
    -Description "企微智能机器人双向通道服务（纯出站 WS 客户端，无入站端口）"
Write-Host "      已注册（-MultipleInstances IgnoreNew，防双实例互踢）" -ForegroundColor Green

# ── 7. 启动 + 健康检查（无 HTTP 端口，改看进程是否存活 + 日志/审计文件是否更新）──
Write-Host "[7/7] 启动服务..." -ForegroundColor Yellow
Start-ScheduledTask -TaskName $TASK
Start-Sleep -Seconds 5
$state = (Get-ScheduledTask -TaskName $TASK).State
Write-Host "      计划任务状态：$state" -ForegroundColor $(if ($state -eq "Running") { "Green" } else { "Red" })
$auditPath = Join-Path $APP "reports\wecom_aibot_audit.jsonl"
Write-Host "      审计文件（服务正常收发后会持续追加）：$auditPath" -ForegroundColor DarkGray

Write-Host "`n部署完成。" -ForegroundColor Green
Write-Host "   查看状态 : Get-ScheduledTask -TaskName $TASK | Get-ScheduledTaskInfo" -ForegroundColor DarkGray
Write-Host "   重启服务 : schtasks /End /TN $TASK ; schtasks /Run /TN $TASK" -ForegroundColor DarkGray
Write-Host "   ⚠️ 纯出站服务，无需公网/LAN 入站开放；.env 凭据未填时会在启动瞬间 fail-loud 退出（预期行为）" -ForegroundColor Yellow
