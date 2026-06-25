# ============================================================
#  成品保供预警看板 — 长开服务器部署（照搬 supplychain/SalesMarketing 套路）
#  在【服务器 192.168.100.51】上以管理员运行（首次部署 / 依赖变更时）：
#    cd C:\baoguan\app
#    powershell -ExecutionPolicy Bypass -File deploy-server.ps1
#
#  布局（由笔记本 sync-to-server.ps1 推送形成）：
#    C:\baoguan\zhuopin_platform\   平台底座包
#    C:\baoguan\app\                SC8 工程（本脚本所在）
#    C:\baoguan\.env                凭据（手工放，不入库）
#
#  端口 8091（避开 supplychain 8080 / SalesMarketing 8090，可同机共存）。
#  红线：含真实客户名 → 防火墙只放行 LocalSubnet；对客闸全程关；外网开放须先加鉴权(待办#10)。
# ============================================================

$ErrorActionPreference = "Stop"

$APP      = $PSScriptRoot                         # C:\baoguan\app
$BASE     = Split-Path $APP -Parent               # C:\baoguan
$PLATFORM = Join-Path $BASE "zhuopin_platform"
$VENV     = Join-Path $BASE ".venv"
$PORT     = 8091
$TASK     = "BaoguanWebServer"
$WEBSCRIPT = Join-Path $APP "scripts\run_baoguan_web.py"

Write-Host "`n== 成品保供预警看板 — 服务器部署 ==" -ForegroundColor Cyan
Write-Host "   基目录  : $BASE"
Write-Host "   平台底座: $PLATFORM"
Write-Host "   SC8 工程: $APP"
Write-Host "   端口    : $PORT`n"

if (-not (Test-Path $PLATFORM)) { Write-Error "未找到 $PLATFORM —— 请先在笔记本跑 sync-to-server.ps1 推送代码。"; exit 1 }

# ── 1. Python ──
Write-Host "[1/8] 检查 Python..." -ForegroundColor Yellow
if (-not (Get-Command python -ErrorAction SilentlyContinue)) { Write-Error "未找到 Python，请装 3.11+ 并 Add to PATH。"; exit 1 }
Write-Host "      $(python --version 2>&1)" -ForegroundColor Green

# ── 2. venv ──
Write-Host "[2/8] 虚拟环境..." -ForegroundColor Yellow
if (-not (Test-Path $VENV)) { python -m venv $VENV; Write-Host "      已创建 $VENV" -ForegroundColor Green }
else { Write-Host "      已存在，跳过" -ForegroundColor Green }
$pipExe = Join-Path $VENV "Scripts\pip.exe"
$pyExe  = Join-Path $VENV "Scripts\python.exe"

# ── 3. editable 安装平台 + SC8（flask/waitress 随 SC8 依赖装上）──
Write-Host "[3/8] 安装依赖（zhuopin_platform + SC8）..." -ForegroundColor Yellow
& $pipExe install --quiet --upgrade pip
& $pipExe install --quiet -e $PLATFORM
& $pipExe install --quiet -e $APP
Write-Host "      完成" -ForegroundColor Green

# ── 4. .env（基目录，凭据手工放）──
Write-Host "[4/8] 检查 .env..." -ForegroundColor Yellow
$envFile = Join-Path $BASE ".env"
if (-not (Test-Path $envFile)) {
    Write-Host "      .env 不存在，生成模板（填好真实凭据再启动）" -ForegroundColor DarkYellow
    $tpl = @"
# 成品保供预警看板 — 环境变量（凭据只在本文件，不入库）
SC8_DATA_SOURCE=real
U9C_DATA_SOURCE=real
SC8_BAOGUAN_PORT=$PORT

# FO 预测订单（正式库外网 apiKey）
FO_API_BASE=https://erp.equalitytec.com:4443
FORECAST_API_KEY=
# U9C BOM（OAuth2）
U9C_API_BASE=https://erp.equalitytec.com:4443
U9C_CLIENT_ID=
U9C_CLIENT_SECRET=
U9C_ORG_CODE=Z
# 携客云 SRM 承诺
XKY_API_BASE=https://openapi.xiekeyun.com
XKY_OWNER_COMPANY_CODE=
XKY_APP_KEY=
XKY_APP_SECRET=
XKY_ERP_CODE=
# 真延期推送的保供运维群
WECOM_WEBHOOK_URL=
# 可选：AI 草稿 key（无则模板降级） / 定时刷新分钟(默认360=6h) / FO状态(默认2,all=不过滤)
# ANTHROPIC_API_KEY=
# SC8_BAOGUAN_REFRESH_MIN=360
# SC8_FO_STATUS=2
"@
    Set-Content -Path $envFile -Value $tpl -Encoding UTF8
    Write-Host "      模板已生成：$envFile —— 填好凭据后重跑本脚本或重启任务" -ForegroundColor Red
} else {
    Write-Host "      .env 已存在" -ForegroundColor Green
}

# ── 5. 防火墙放行 8091（仅 LocalSubnet）──
Write-Host "[5/8] 防火墙（入站 TCP $PORT，限 LocalSubnet）..." -ForegroundColor Yellow
$ruleName = "Baoguan-WebServer-$PORT"
if (-not (Get-NetFirewallRule -DisplayName $ruleName -ErrorAction SilentlyContinue)) {
    New-NetFirewallRule -DisplayName $ruleName -Direction Inbound -Protocol TCP `
        -LocalPort $PORT -Action Allow -Profile Private,Domain -RemoteAddress LocalSubnet | Out-Null
    Write-Host "      已放行 $PORT" -ForegroundColor Green
} else { Write-Host "      规则已存在" -ForegroundColor Green }

# ── 6. 启动包装脚本（设 real + 端口，PowerShell 对中文/UTF-8 路径友好）──
Write-Host "[6/8] 生成 start-baoguan.ps1..." -ForegroundColor Yellow
$startPs1 = Join-Path $APP "start-baoguan.ps1"
$startContent = @"
# 保供看板启动包装（计划任务与手动启动共用）
`$env:SC8_DATA_SOURCE = "real"
`$env:SC8_BAOGUAN_PORT = "$PORT"
& "$pyExe" "$WEBSCRIPT"
"@
Set-Content -Path $startPs1 -Value $startContent -Encoding UTF8
Write-Host "      已生成" -ForegroundColor Green

# ── 7. 计划任务（开机自启、SYSTEM、失败重启3次）──
Write-Host "[7/8] 注册计划任务 $TASK..." -ForegroundColor Yellow
if (Get-ScheduledTask -TaskName $TASK -ErrorAction SilentlyContinue) {
    Unregister-ScheduledTask -TaskName $TASK -Confirm:$false   # 重建以更新路径
}
$psArgs = "-NoProfile -ExecutionPolicy Bypass -File `"$startPs1`""
$action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument $psArgs -WorkingDirectory $APP
$trigger = New-ScheduledTaskTrigger -AtStartup
$principal = New-ScheduledTaskPrincipal -UserId "SYSTEM" -LogonType ServiceAccount -RunLevel Highest
$settings = New-ScheduledTaskSettingsSet -ExecutionTimeLimit (New-TimeSpan -Hours 0) `
                -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1) -AllowStartIfOnBatteries
Register-ScheduledTask -TaskName $TASK -Action $action -Trigger $trigger `
    -Principal $principal -Settings $settings `
    -Description "成品保供预警看板 Web 服务（端口 $PORT，real）" | Out-Null
Write-Host "      已注册" -ForegroundColor Green

# ── 8. 启动 + 健康检查 ──
Write-Host "[8/8] 启动服务..." -ForegroundColor Yellow
Start-ScheduledTask -TaskName $TASK
Start-Sleep -Seconds 6
try {
    $r = Invoke-WebRequest -Uri "http://127.0.0.1:$PORT/api/ping" -TimeoutSec 5 -UseBasicParsing
    Write-Host "      健康检查 OK：$($r.Content)" -ForegroundColor Green
} catch {
    Write-Host "      健康检查未过——多半 .env 凭据未填或 Python 报错。" -ForegroundColor Red
    Write-Host "      排查：powershell -File `"$startPs1`"  看前台报错。" -ForegroundColor DarkYellow
}

Write-Host "`n部署完成。" -ForegroundColor Green
Write-Host "   看板地址 : http://192.168.100.51:$PORT/"        -ForegroundColor Cyan
Write-Host "   案例处置 : http://192.168.100.51:$PORT/cases"   -ForegroundColor Cyan
Write-Host "   健康检查 : http://192.168.100.51:$PORT/api/ping" -ForegroundColor DarkGray
Write-Host "   重启服务 : schtasks /End /TN $TASK ; schtasks /Run /TN $TASK" -ForegroundColor DarkGray
Write-Host "   ⚠️ 仅 LAN（无登录鉴权）；外网开放前须先加鉴权（待办#10，真实客户名红线）" -ForegroundColor Yellow
