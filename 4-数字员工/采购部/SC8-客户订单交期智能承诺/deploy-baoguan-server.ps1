# ============================================================
#  成品保供预警看板 — 内网长开服务器一键部署（照搬 supplychain deploy-intranet.ps1 套路）
#  适用：192.168.100.51（Windows，已装 Python 3.11+）
#  用法：把整个 AI-Tran 仓库放到 .51（git clone 或 SMB），然后在 .51 上
#        以【管理员】PowerShell 进入本 SC8 工程目录运行：
#          powershell -ExecutionPolicy Bypass -File deploy-baoguan-server.ps1
#
#  与 supplychain 差异：① editable 安装 zhuopin_platform + SC8 两个包；
#  ② 只起 1 个服务（8090），FO 走正式库外网 apiKey、无需本地 FO API 服务。
#  红线：含真实客户名 → 防火墙只放行 LocalSubnet；对客闸全程关；外网开放须先加鉴权（待办#10）。
# ============================================================

$ErrorActionPreference = "Stop"

# ── 路径推导 ────────────────────────────────────────────────
$SC8  = $PSScriptRoot                                   # 本 SC8 工程目录
$REPO = (Get-Item $SC8).Parent.Parent.Parent.FullName   # 仓库根（SC8→采购部→4-数字员工→repo）
$PLATFORM = Join-Path $REPO "5-平台底座\zhuopin_platform"
$VENV = Join-Path $SC8 ".venv"
$PORT = 8090
$TASK = "BaoguanWebServer"
$WEBSCRIPT = Join-Path $SC8 "scripts\run_baoguan_web.py"

Write-Host "`n== 成品保供预警看板 — 部署 ==" -ForegroundColor Cyan
Write-Host "   仓库根  : $REPO"
Write-Host "   SC8 工程: $SC8"
Write-Host "   平台底座: $PLATFORM"
Write-Host "   端口    : $PORT`n"

# ── Step 1: 检查 Python ─────────────────────────────────────
Write-Host "[1/8] 检查 Python..." -ForegroundColor Yellow
$py = Get-Command python -ErrorAction SilentlyContinue
if (-not $py) { Write-Error "未找到 Python。请装 Python 3.11+ 并勾选 Add to PATH。"; exit 1 }
Write-Host "      $(python --version 2>&1)" -ForegroundColor Green

# ── Step 2: 建虚拟环境 ──────────────────────────────────────
Write-Host "[2/8] 准备虚拟环境..." -ForegroundColor Yellow
if (-not (Test-Path $VENV)) { python -m venv $VENV; Write-Host "      已创建 $VENV" -ForegroundColor Green }
else { Write-Host "      已存在，跳过" -ForegroundColor Green }
$pipExe = Join-Path $VENV "Scripts\pip.exe"
$pyExe  = Join-Path $VENV "Scripts\python.exe"

# ── Step 3: editable 安装平台 + SC8（flask/waitress 随 SC8 依赖装上）──
Write-Host "[3/8] 安装依赖（zhuopin_platform + SC8）..." -ForegroundColor Yellow
& $pipExe install --quiet --upgrade pip
& $pipExe install --quiet -e $PLATFORM
& $pipExe install --quiet -e $SC8
Write-Host "      依赖安装完成" -ForegroundColor Green

# ── Step 4: 检查 .env（仓库根，凭据手工放、不入库）──────────────
Write-Host "[4/8] 检查 .env..." -ForegroundColor Yellow
$envFile = Join-Path $REPO ".env"
if (-not (Test-Path $envFile)) {
    Write-Host "      .env 不存在，生成模板（务必填真实凭据再启动）" -ForegroundColor DarkYellow
    $tpl = @"
# 成品保供预警看板 — 环境变量（凭据只在本文件，不入库）
SC8_DATA_SOURCE=real
U9C_DATA_SOURCE=real

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

# 真延期推送的保供运维群（缺省走 WECOM_WEBHOOK_URL）
WECOM_WEBHOOK_URL=
# SC8_BAOGUAN_OPS_WEBHOOK_URL=

# 可选：AI 草稿（无 key 自动降级模板）
# ANTHROPIC_API_KEY=

# 可选调参：定时刷新分钟(默认360=6h) / 端口(默认8090) / FO状态过滤(默认2=已审核, all=不过滤)
# SC8_BAOGUAN_REFRESH_MIN=360
# SC8_BAOGUAN_PORT=8090
# SC8_FO_STATUS=2
"@
    Set-Content -Path $envFile -Value $tpl -Encoding UTF8
    Write-Host "      模板已生成：$envFile —— 请填好凭据后再继续" -ForegroundColor Red
} else {
    Write-Host "      .env 已存在" -ForegroundColor Green
}

# ── Step 5: 防火墙放行 8090（仅 LocalSubnet，不开 Public）──────
Write-Host "[5/8] 配置防火墙（入站 TCP $PORT，限 LocalSubnet）..." -ForegroundColor Yellow
$ruleName = "Baoguan-WebServer-$PORT"
if (-not (Get-NetFirewallRule -DisplayName $ruleName -ErrorAction SilentlyContinue)) {
    New-NetFirewallRule -DisplayName $ruleName -Direction Inbound -Protocol TCP `
        -LocalPort $PORT -Action Allow -Profile Private,Domain -RemoteAddress LocalSubnet | Out-Null
    Write-Host "      已放行 $PORT（LocalSubnet）" -ForegroundColor Green
} else {
    Write-Host "      规则已存在，跳过" -ForegroundColor Green
}

# ── Step 6: 生成手动启动脚本（PowerShell，UTF-8 友好，避开中文路径 cmd 乱码）──
Write-Host "[6/8] 生成 start-baoguan.ps1..." -ForegroundColor Yellow
$startPs1 = Join-Path $SC8 "start-baoguan.ps1"
$startContent = @"
# 手动启动保供看板（前台）。常驻由计划任务 $TASK 负责。
`$env:SC8_DATA_SOURCE = "real"
& "$pyExe" "$WEBSCRIPT"
"@
Set-Content -Path $startPs1 -Value $startContent -Encoding UTF8
Write-Host "      start-baoguan.ps1 已生成" -ForegroundColor Green

# ── Step 7: 注册开机自启计划任务（SYSTEM、失败重启 3 次）──────
Write-Host "[7/8] 注册计划任务 $TASK（开机自启）..." -ForegroundColor Yellow
if (Get-ScheduledTask -TaskName $TASK -ErrorAction SilentlyContinue) {
    Write-Host "      已存在，先注销重建以更新路径" -ForegroundColor DarkYellow
    Unregister-ScheduledTask -TaskName $TASK -Confirm:$false
}
# 直接执行 venv 的 python.exe（-WorkingDirectory 设 SC8，避免 cmd 中文路径乱码）
$action = New-ScheduledTaskAction -Execute $pyExe -Argument "`"$WEBSCRIPT`"" -WorkingDirectory $SC8
$trigger = New-ScheduledTaskTrigger -AtStartup
$principal = New-ScheduledTaskPrincipal -UserId "SYSTEM" -LogonType ServiceAccount -RunLevel Highest
$settings = New-ScheduledTaskSettingsSet -ExecutionTimeLimit (New-TimeSpan -Hours 0) `
                -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1) -AllowStartIfOnBatteries
Register-ScheduledTask -TaskName $TASK -Action $action -Trigger $trigger `
    -Principal $principal -Settings $settings `
    -Description "成品保供预警看板 Web 服务（端口 $PORT，real）" | Out-Null
Write-Host "      计划任务 $TASK 已注册" -ForegroundColor Green

# ── Step 8: 立即启动 + 健康检查 ─────────────────────────────
Write-Host "[8/8] 启动服务..." -ForegroundColor Yellow
Start-ScheduledTask -TaskName $TASK
Start-Sleep -Seconds 6
try {
    $r = Invoke-WebRequest -Uri "http://127.0.0.1:$PORT/api/ping" -TimeoutSec 5 -UseBasicParsing
    Write-Host "      健康检查 OK：$($r.Content)" -ForegroundColor Green
} catch {
    Write-Host "      健康检查未通过——多半是 .env 凭据未填或 Python 报错。" -ForegroundColor Red
    Write-Host "      手动排查：在 SC8 目录运行  powershell -File start-baoguan.ps1  看报错。" -ForegroundColor DarkYellow
}

$ip = (Get-NetIPAddress -AddressFamily IPv4 | Where-Object { $_.IPAddress -like "192.168.*" } | Select-Object -First 1).IPAddress
Write-Host "`n部署完成。" -ForegroundColor Green
Write-Host "   看板地址 : http://${ip}:${PORT}/"            -ForegroundColor Cyan
Write-Host "   固定地址 : http://192.168.100.51:${PORT}/"    -ForegroundColor Cyan
Write-Host "   案例处置 : http://192.168.100.51:${PORT}/cases" -ForegroundColor Cyan
Write-Host "   健康检查 : http://192.168.100.51:${PORT}/api/ping" -ForegroundColor DarkGray
Write-Host "   重启服务 : schtasks /End /TN $TASK ; schtasks /Run /TN $TASK" -ForegroundColor DarkGray
Write-Host "   ⚠️ 仅 LAN 内部访问（无登录鉴权）；外网开放前须先加鉴权（待办#10，含真实客户名红线）" -ForegroundColor Yellow
