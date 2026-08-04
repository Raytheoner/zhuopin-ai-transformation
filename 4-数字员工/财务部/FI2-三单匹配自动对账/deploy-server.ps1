# ================================================================
#  FI2 三单匹配自动对账 — 长开服务器首次部署（在【服务器 192.168.100.51】上以管理员运行）
#    cd C:\fi2\app
#    powershell -ExecutionPolicy Bypass -File deploy-server.ps1
#
#  布局（由笔记本 sync-to-server.ps1 推送形成）：
#    C:\fi2\zhuopin_platform\   平台底座包
#    C:\fi2\app\                FI2 工程（本脚本所在）
#    C:\fi2\.venv\              虚拟环境（本脚本创建）
#
#  端口 8094（避开保供看板 8091 / 命令中心 8092 / QD-B 8093，可同机共存）。
#  红线：只读取数，不写回 ERP；仅 LAN 访问（无登录鉴权）；AI 结论恒为"建议/预警"，
#        报告页显著标注"试用版"，未过账、结案在财务人员。
# ================================================================

$ErrorActionPreference = "Stop"

$APP      = $PSScriptRoot                         # C:\fi2\app
$BASE     = Split-Path $APP -Parent               # C:\fi2
$PLATFORM = Join-Path $BASE "zhuopin_platform"
$VENV     = Join-Path $BASE ".venv"
$PORT     = 8094
$TASK     = "Fi2WebServer"
$WEBSCRIPT = Join-Path $APP "scripts\run_fi2_web.py"

Import-Module (Join-Path $BASE "deploy-tools\ZhuopinDeploy.psm1") -Force

Write-Host "`n== FI2 三单匹配自动对账 — 服务器部署 ==" -ForegroundColor Cyan
Write-Host "   基目录  : $BASE"
Write-Host "   平台底座: $PLATFORM"
Write-Host "   FI2 工程: $APP"
Write-Host "   端口    : $PORT`n"

if (-not (Test-Path $PLATFORM)) { Write-Error "未找到 $PLATFORM —— 请先在笔记本跑 sync-to-server.ps1 推送代码。"; exit 1 }

# ── 1. Python ──
Write-Host "[1/6] 检查 Python..." -ForegroundColor Yellow
if (-not (Get-Command python -ErrorAction SilentlyContinue)) { Write-Error "未找到 Python，请装 3.11+ 并 Add to PATH。"; exit 1 }
Write-Host "      $(python --version 2>&1)" -ForegroundColor Green

# ── 2. venv ──
Write-Host "[2/6] 虚拟环境..." -ForegroundColor Yellow
if (-not (Test-Path $VENV)) { python -m venv $VENV; Write-Host "      已创建 $VENV" -ForegroundColor Green }
else { Write-Host "      已存在，跳过" -ForegroundColor Green }
$pipExe = Join-Path $VENV "Scripts\pip.exe"
$pyExe  = Join-Path $VENV "Scripts\python.exe"

# ── 3. editable 安装平台 + FI2（flask/waitress/pydantic 随 FI2 依赖装上）──
Write-Host "[3/6] 安装依赖（zhuopin_platform + FI2）..." -ForegroundColor Yellow
& $pipExe install --quiet -e $PLATFORM
& $pipExe install --quiet -e $APP
Write-Host "      完成" -ForegroundColor Green

# ── 4. 访问口令 .env（ZP_GATE_PASSWORD，四服务共享，临时止血，跨桌任务队列 #10）──
Write-Host "[4/7] 检查访问口令 .env..." -ForegroundColor Yellow
$envFile = Join-Path $BASE ".env"
Set-ZhuopinGatePasswordEnv -EnvFile $envFile

# ── 5. 防火墙放行 8094（内网 LAN 全网段，同保供看板/命令中心/QD-B 惯例）──
Write-Host "[5/7] 防火墙（入站 TCP $PORT，LAN 全网段）..." -ForegroundColor Yellow
Register-ZhuopinFirewallRule -RuleName "Fi2-WebServer-$PORT" -Port $PORT

# ── 5. 启动包装脚本（PowerShell 对中文/UTF-8 路径友好）──
Write-Host "[6/7] 生成 start-fi2.ps1..." -ForegroundColor Yellow
$startPs1 = Join-Path $APP "start-fi2.ps1"
$startContent = @"
# FI2 web service launcher (shared by scheduled task and manual start)
`$env:FI2_WEB_PORT = "$PORT"
& "$pyExe" "$WEBSCRIPT"
"@
Set-Content -Path $startPs1 -Value $startContent -Encoding UTF8
Write-Host "      已生成" -ForegroundColor Green

# ── 6. 计划任务（开机自启、SYSTEM、失败重启3次）+ 启动 + 健康检查 ──
Write-Host "[7/7] 注册计划任务 $TASK..." -ForegroundColor Yellow
Register-ZhuopinScheduledTask -TaskName $TASK `
    -Execute "powershell.exe" -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$startPs1`"" `
    -WorkingDirectory $APP -Description "FI2 三单匹配自动对账 Web 服务（端口 $PORT，试用版）"

Write-Host "启动服务..." -ForegroundColor Yellow
Start-ZhuopinWebServiceAndCheckHealth -TaskName $TASK -Port $PORT | Out-Null

Write-Host "`n部署完成。" -ForegroundColor Green
Write-Host "   服务地址 : http://192.168.100.51:$PORT/"        -ForegroundColor Cyan
Write-Host "   健康检查 : http://192.168.100.51:$PORT/api/ping" -ForegroundColor DarkGray
Write-Host "   重启服务 : schtasks /End /TN $TASK ; schtasks /Run /TN $TASK" -ForegroundColor DarkGray
Write-Host "   回滚     : schtasks /End /TN $TASK ; schtasks /Delete /TN $TASK /F" -ForegroundColor DarkGray
Write-Host "   ⚠️ 仅 LAN（无登录鉴权）；试用版·灰度，AI 建议/预警非终局，只读不写回 ERP" -ForegroundColor Yellow
