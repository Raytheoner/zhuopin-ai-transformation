# ================================================================
#  QD-B 立项审核门禁 — 长开服务器首次部署（在【服务器 192.168.100.51】上以管理员运行）
#    cd C:\qd-b\app
#    powershell -ExecutionPolicy Bypass -File deploy-server.ps1
#
#  布局（由笔记本 sync-to-server.ps1 推送形成）：
#    C:\qd-b\zhuopin_platform\   平台底座包
#    C:\qd-b\app\                QD-B 工程（本脚本所在）
#    C:\qd-b\.venv\              虚拟环境（本脚本创建）
#
#  端口 8093（避开保供看板 8091 / 命令中心 8092，可同机共存）。
#  红线：立项书上传件不入库、仅落 app/reports/（gitignore）；仅 LAN 访问（无登录鉴权）；
#        AI 不自动执行任何业务动作，报告页显著标注"试用版"。
# ================================================================

$ErrorActionPreference = "Stop"

$APP      = $PSScriptRoot                         # C:\qd-b\app
$BASE     = Split-Path $APP -Parent               # C:\qd-b
$PLATFORM = Join-Path $BASE "zhuopin_platform"
$VENV     = Join-Path $BASE ".venv"
$PORT     = 8093
$TASK     = "QdBWebServer"
$WEBSCRIPT = Join-Path $APP "scripts\run_qd_b_web.py"

Write-Host "`n== QD-B 立项审核门禁 — 服务器部署 ==" -ForegroundColor Cyan
Write-Host "   基目录  : $BASE"
Write-Host "   平台底座: $PLATFORM"
Write-Host "   QD-B 工程: $APP"
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

# ── 3. editable 安装平台 + QD-B（flask/waitress/openpyxl 随 QD-B 依赖装上）──
Write-Host "[3/7] 安装依赖（zhuopin_platform + QD-B）..." -ForegroundColor Yellow
& $pipExe install --quiet -e $PLATFORM
& $pipExe install --quiet -e $APP
Write-Host "      完成" -ForegroundColor Green

# ── 4. 规则注册表就位检查（sync-to-server.ps1 单独推送 data/rules/registry.json）──
Write-Host "[4/7] 检查规则注册表..." -ForegroundColor Yellow
$registryPath = Join-Path $APP "data\rules\registry.json"
if (-not (Test-Path $registryPath)) {
    Write-Warning "      未找到 $registryPath —— 请确认笔记本 sync-to-server.ps1 已推送 data/rules/registry.json"
} else {
    Write-Host "      已就位" -ForegroundColor Green
}

# ── 5. 防火墙放行 8093（内网 LAN 全网段，同保供看板/命令中心惯例）──
# 注意：不要限 LocalSubnet —— 组员笔记本常在不同网段(如 WLAN)，LocalSubnet 会挡掉。
Write-Host "[5/7] 防火墙（入站 TCP $PORT，LAN 全网段）..." -ForegroundColor Yellow
$ruleName = "QdB-WebServer-$PORT"
if (-not (Get-NetFirewallRule -DisplayName $ruleName -ErrorAction SilentlyContinue)) {
    New-NetFirewallRule -DisplayName $ruleName -Direction Inbound -Protocol TCP `
        -LocalPort $PORT -Action Allow | Out-Null
    Write-Host "      已放行 $PORT（LAN 全网段）" -ForegroundColor Green
} else {
    Set-NetFirewallRule -DisplayName $ruleName -RemoteAddress Any -Profile Any -Enabled True | Out-Null
    Write-Host "      规则已存在，已确保放行 LAN 全网段" -ForegroundColor Green
}

# ── 6. 启动包装脚本（PowerShell 对中文/UTF-8 路径友好）──
Write-Host "[6/7] 生成 start-qdb.ps1..." -ForegroundColor Yellow
$startPs1 = Join-Path $APP "start-qdb.ps1"
$startContent = @"
# QD-B web service launcher (shared by scheduled task and manual start)
`$env:QD_B_WEB_PORT = "$PORT"
& "$pyExe" "$WEBSCRIPT"
"@
Set-Content -Path $startPs1 -Value $startContent -Encoding UTF8
Write-Host "      已生成" -ForegroundColor Green

# ── 7. 计划任务（开机自启、SYSTEM、失败重启3次）+ 启动 + 健康检查 ──
Write-Host "[7/7] 注册计划任务 $TASK..." -ForegroundColor Yellow
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
    -Description "QD-B 立项审核门禁 Web 服务（端口 $PORT，试用版）" | Out-Null
Write-Host "      已注册" -ForegroundColor Green

Write-Host "启动服务..." -ForegroundColor Yellow
Get-NetTCPConnection -LocalPort $PORT -State Listen -ErrorAction SilentlyContinue |
    ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }
Start-ScheduledTask -TaskName $TASK
Start-Sleep -Seconds 6
$ProgressPreference = 'SilentlyContinue'   # 非交互会话(SSH exec)下 Invoke-WebRequest 进度条访问控制台句柄会报错，静默规避
try {
    $r = Invoke-WebRequest -Uri "http://127.0.0.1:$PORT/api/ping" -TimeoutSec 5 -UseBasicParsing
    Write-Host "      健康检查 OK：$($r.Content)" -ForegroundColor Green
} catch {
    Write-Host "      健康检查未过——排查：powershell -File `"$startPs1`"  看前台报错。" -ForegroundColor Red
}

Write-Host "`n部署完成。" -ForegroundColor Green
Write-Host "   服务地址 : http://192.168.100.51:$PORT/"        -ForegroundColor Cyan
Write-Host "   健康检查 : http://192.168.100.51:$PORT/api/ping" -ForegroundColor DarkGray
Write-Host "   重启服务 : schtasks /End /TN $TASK ; schtasks /Run /TN $TASK" -ForegroundColor DarkGray
Write-Host "   回滚     : schtasks /End /TN $TASK ; schtasks /Delete /TN $TASK /F" -ForegroundColor DarkGray
Write-Host "   ⚠️ 仅 LAN（无登录鉴权）；试用版·灰度，AI 预审建议非终局" -ForegroundColor Yellow
