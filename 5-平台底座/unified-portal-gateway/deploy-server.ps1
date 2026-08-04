# ================================================================
#  统一门户网关 — 长开服务器首次部署（在【服务器 192.168.100.51】上以管理员运行）
#    cd C:\portal-gateway\app
#    powershell -ExecutionPolicy Bypass -File deploy-server.ps1
#
#  布局（由笔记本 sync-to-server.ps1 推送形成）：
#    C:\portal-gateway\zhuopin_platform\   平台底座包
#    C:\portal-gateway\app\                网关工程（本脚本所在）
#    C:\portal-gateway\.venv\              虚拟环境（本脚本创建）
#
#  端口 8090（决策件门户新增的唯一对外入口，避开保供看板8091/命令中心8092/
#  QD-B 8093/FI2 8094，可同机共存）。
#
#  ⚠️ 必须在 .env 配置 PORTAL_GATEWAY_SESSION_SECRET（会话签名密钥，未配置
#  网关拒绝启动，见 webapp.py::_resolve_session_secret）。本次试点阶段
#  PORTAL_GATEWAY_MOCK_LOGIN=1（企微 OAuth 凭据未到位，见队列 #240），
#  真实凭据到位后须显式移除该开关。
# ================================================================

$ErrorActionPreference = "Stop"

$APP      = $PSScriptRoot                         # C:\portal-gateway\app
$BASE     = Split-Path $APP -Parent               # C:\portal-gateway
$PLATFORM = Join-Path $BASE "zhuopin_platform"
$VENV     = Join-Path $BASE ".venv"
$PORT     = 8090
$TASK     = "UnifiedPortalGateway"
$WEBSCRIPT = Join-Path $APP "scripts\run_gateway.py"

Import-Module (Join-Path $BASE "deploy-tools\ZhuopinDeploy.psm1") -Force

Write-Host "`n== 统一门户网关 — 服务器部署 ==" -ForegroundColor Cyan
Write-Host "   基目录  : $BASE"
Write-Host "   平台底座: $PLATFORM"
Write-Host "   网关工程: $APP"
Write-Host "   端口    : $PORT`n"

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

# ── 3. editable 安装平台 + 网关（flask/waitress/requests/pyyaml 随依赖装上）──
Write-Host "[3/7] 安装依赖（zhuopin_platform + 网关）..." -ForegroundColor Yellow
& $pipExe install --quiet -e $PLATFORM
& $pipExe install --quiet -e $APP
Write-Host "      完成" -ForegroundColor Green

# ── 4. .env 检查（会话密钥为必需项，不同于 ZP_GATE_PASSWORD 可选） ──
Write-Host "[4/7] 检查 .env（PORTAL_GATEWAY_SESSION_SECRET 必需）..." -ForegroundColor Yellow
$envFile = Join-Path $BASE ".env"
if (-not (Test-Path $envFile)) {
    Write-Warning "      未找到 $envFile —— 网关启动会因缺 PORTAL_GATEWAY_SESSION_SECRET 直接拒绝（fail loud，非 fail open）"
} else {
    $hasSecret = (Get-Content $envFile) -match '^\s*PORTAL_GATEWAY_SESSION_SECRET=\S'
    if (-not $hasSecret) { Write-Warning "      .env 存在但未填 PORTAL_GATEWAY_SESSION_SECRET —— 网关会拒绝启动" }
    else { Write-Host "      已配置" -ForegroundColor Green }
}

# ── 5. 防火墙放行 8090（内网 LAN 全网段，同其余三服务惯例）──
Write-Host "[5/7] 防火墙（入站 TCP $PORT，LAN 全网段）..." -ForegroundColor Yellow
Register-ZhuopinFirewallRule -RuleName "UnifiedPortalGateway-$PORT" -Port $PORT

# ── 6. 启动包装脚本 ──
Write-Host "[6/7] 生成 start-portal-gateway.ps1..." -ForegroundColor Yellow
$startPs1 = Join-Path $APP "start-portal-gateway.ps1"
$startContent = @"
# Unified portal gateway launcher (shared by scheduled task and manual start)
`$env:PORTAL_GATEWAY_PORT = "$PORT"
& "$pyExe" "$WEBSCRIPT"
"@
Set-Content -Path $startPs1 -Value $startContent -Encoding UTF8
Write-Host "      已生成" -ForegroundColor Green

# ── 7. 计划任务（开机自启、SYSTEM、失败重启3次）+ 启动 + 健康检查 ──
Write-Host "[7/7] 注册计划任务 $TASK..." -ForegroundColor Yellow
Register-ZhuopinScheduledTask -TaskName $TASK `
    -Execute "powershell.exe" -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$startPs1`"" `
    -WorkingDirectory $APP -Description "统一门户网关（端口 $PORT，试点：门户首页→8092）"

Write-Host "启动服务..." -ForegroundColor Yellow
Start-ZhuopinWebServiceAndCheckHealth -TaskName $TASK -Port $PORT | Out-Null

Write-Host "`n部署完成。" -ForegroundColor Green
Write-Host "   服务地址 : http://192.168.100.51:$PORT/"        -ForegroundColor Cyan
Write-Host "   健康检查 : http://192.168.100.51:$PORT/api/ping" -ForegroundColor DarkGray
Write-Host "   重启服务 : schtasks /End /TN $TASK ; schtasks /Run /TN $TASK" -ForegroundColor DarkGray
Write-Host "   回滚     : schtasks /End /TN $TASK ; schtasks /Delete /TN $TASK /F" -ForegroundColor DarkGray
Write-Host "   ⚠️ 8092 原端口仍保留直连（应急通道，不对外宣传）；网关是新增入口，不影响既有四服务" -ForegroundColor Yellow
Write-Host "   ⚠️ 本次为试点部署：企微 OAuth 凭据未到位，暂用 mock 登录打通链路，真实凭据到位后须移除 PORTAL_GATEWAY_MOCK_LOGIN" -ForegroundColor Yellow
