# ================================================================
#  FI3 付款申请自动校验 — 长开服务器首次部署（在【服务器 192.168.100.51】上以管理员运行）
#    cd C:\fi3\app
#    powershell -ExecutionPolicy Bypass -File deploy-server.ps1
#
#  布局（由笔记本 sync-to-server.ps1 推送形成）：
#    C:\fi3\zhuopin_platform\   平台底座包
#    C:\fi3\app\                FI3 工程（本脚本所在）
#    C:\fi3\.venv\              虚拟环境（本脚本创建）
#    C:\fi3\.env                共享口令门禁 ZP_GATE_PASSWORD（值不入库、不打印）
#
#  端口 8097 —— 过渡期独立端口（队列 §一 #615，Shao Peishen 2026-09-18 答 a：「现在都是内网，
#  先上功能，认证完善以后慢慢上」），与 design D7「不新起端口、走 .51:8090 网关反代」相反，
#  先例＝SC2 8096。网关收编（决策件线③）时本端口、本防火墙规则一并回收。本脚本不碰 8090。
#
#  红线：本页只读档 1 mock 数据，不接 U9C，不写回 ERP；首屏显著标注「mock 数据」——
#        看形态、不看数字；AI 不碰钱，付款执行永远由人在 U9C／银企系统完成。
#  判据正本：3-治理与合规/.51部署标准清单-服务侧与笔记本侧-2026-08-01.md §三 七类坑
#    ① 本文件带 UTF-8 BOM   ② 防火墙 RemoteAddress Any   ③ AtStartup + SYSTEM
#    ④ venv python 绝对路径烘焙进 start-fi3.ps1   ⑤ RestartCount 3 / 1 分钟
#    ⑥ ZP_GATE_PASSWORD 复用同机 fi2 的值（服务器本地复制，值不出机、不回显）   ⑦ 凭据只在 .env
# ================================================================

$ErrorActionPreference = "Stop"

$APP       = $PSScriptRoot                        # C:\fi3\app
$BASE      = Split-Path $APP -Parent              # C:\fi3
$PLATFORM  = Join-Path $BASE "zhuopin_platform"
$VENV      = Join-Path $BASE ".venv"
$PORT      = 8097
$PREFIX    = "/finance/fi3"
$TASK      = "Fi3WebServer"
$WEBSCRIPT = Join-Path $APP "scripts\run_fi3_web.py"
$SIBLING_ENV = "C:\fi2\.env"                      # 同机既有服务的 .env，只借 ZP_GATE_PASSWORD 那一行

Import-Module (Join-Path $BASE "deploy-tools\ZhuopinDeploy.psm1") -Force

Write-Host "`n== FI3 付款申请自动校验 — 服务器部署 ==" -ForegroundColor Cyan
Write-Host "   基目录  : $BASE"
Write-Host "   平台底座: $PLATFORM"
Write-Host "   FI3 工程: $APP"
Write-Host "   端口    : $PORT（路由前缀 $PREFIX）`n"

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

# ── 3. editable 安装平台 + FI3（flask/waitress 随 FI3 pyproject 依赖装上）──
Write-Host "[3/7] 安装依赖（zhuopin_platform + FI3）..." -ForegroundColor Yellow
& $pipExe install --quiet -e $PLATFORM
& $pipExe install --quiet -e $APP
Write-Host "      完成" -ForegroundColor Green

# ── 4. 共享口令 .env（ZP_GATE_PASSWORD，#160；#615：复用、不新设）──
#  Set-ZhuopinGatePasswordEnv 只保证「有这一行」；行值为空时从同机 C:\fi2\.env 借同名行——
#  值只在服务器盘上从一个文件走到另一个文件，本脚本不打印、不回显、不写日志。
#  🔴 未配置门禁即静默 no-op（清单 §三⑥），故下面显式核对「非空」，不靠报错。
Write-Host "[4/7] 检查共享口令 .env..." -ForegroundColor Yellow
$envFile = Join-Path $BASE ".env"
Set-ZhuopinGatePasswordEnv -EnvFile $envFile
$gateNonEmpty = [bool]((Get-Content $envFile) -match '^\s*ZP_GATE_PASSWORD=\S')
if (-not $gateNonEmpty) {
    if (Test-Path $SIBLING_ENV) {
        $borrowed = (Get-Content $SIBLING_ENV) | Where-Object { $_ -match '^\s*ZP_GATE_PASSWORD=\S' } | Select-Object -First 1
        if ($borrowed) {
            $lines = (Get-Content $envFile) | Where-Object { $_ -notmatch '^\s*ZP_GATE_PASSWORD=' }
            Set-Content -Path $envFile -Value (($lines + $borrowed) -join "`n") -Encoding UTF8
            $gateNonEmpty = $true
            Write-Host "      ZP_GATE_PASSWORD 已从 $SIBLING_ENV 复用（值未回显）" -ForegroundColor Green
        }
    }
}
if ($gateNonEmpty) { Write-Host "      ZP_GATE_PASSWORD 非空（门禁将生效）" -ForegroundColor Green }
else { Write-Warning "      ZP_GATE_PASSWORD 为空：门禁静默 no-op！请在 $envFile 填与其余服务同值后重启任务。" }

# ── 5. 防火墙放行 8097（内网 LAN 全网段 RemoteAddress Any，同既有六服务惯例；不得限 LocalSubnet）──
Write-Host "[5/7] 防火墙（入站 TCP $PORT，LAN 全网段）..." -ForegroundColor Yellow
Register-ZhuopinFirewallRule -RuleName "Fi3-WebServer-$PORT" -Port $PORT

# ── 6. 启动包装脚本（venv python 绝对路径烘焙；对外绑定只在这里置 0.0.0.0，run_fi3_web.py 默认值不改）──
Write-Host "[6/7] 生成 start-fi3.ps1..." -ForegroundColor Yellow
$startPs1 = Join-Path $APP "start-fi3.ps1"
$startContent = @"
# FI3 web service launcher (shared by scheduled task and manual start)
`$env:FI3_WEB_HOST = "0.0.0.0"
`$env:FI3_WEB_PORT = "$PORT"
`$env:ZP_ENV_FILE  = "$envFile"
& "$pyExe" "$WEBSCRIPT"
"@
Set-Content -Path $startPs1 -Value $startContent -Encoding UTF8
Write-Host "      已生成" -ForegroundColor Green

# ── 7. 计划任务（开机自启 AtStartup、SYSTEM、失败重启 3 次/1 分钟）+ 启动 + 健康检查 ──
#  🔴 健康检查路径必须带路由前缀：本场景没有裸 /api/ping。
Write-Host "[7/7] 注册计划任务 $TASK..." -ForegroundColor Yellow
Register-ZhuopinScheduledTask -TaskName $TASK `
    -Execute "powershell.exe" -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$startPs1`"" `
    -WorkingDirectory $APP -Description "FI3 付款申请自动校验 门户页（端口 $PORT，档 1 mock，过渡期独立端口 #615）"

Write-Host "启动服务..." -ForegroundColor Yellow
$healthy = Start-ZhuopinWebServiceAndCheckHealth -TaskName $TASK -Port $PORT -HealthPath "$PREFIX/api/ping"

Write-Host "`n部署完成。" -ForegroundColor Green
Write-Host "   服务地址 : http://192.168.100.51:$PORT$PREFIX/"         -ForegroundColor Cyan
Write-Host "   健康检查 : http://192.168.100.51:$PORT$PREFIX/api/ping" -ForegroundColor DarkGray
Write-Host "   冒烟     : powershell -ExecutionPolicy Bypass -File $APP\smoke-server.ps1" -ForegroundColor DarkGray
Write-Host "   重启服务 : schtasks /End /TN $TASK ; schtasks /Run /TN $TASK" -ForegroundColor DarkGray
Write-Host "   回滚     : schtasks /End /TN $TASK ; schtasks /Delete /TN $TASK /F ; Remove-NetFirewallRule -DisplayName Fi3-WebServer-$PORT" -ForegroundColor DarkGray
Write-Host "   ⚠️ 档 1 mock 数据——看形态、不看数字；AI 不碰钱；过渡期独立端口，网关收编时回收" -ForegroundColor Yellow
if (-not $healthy) { exit 1 }
