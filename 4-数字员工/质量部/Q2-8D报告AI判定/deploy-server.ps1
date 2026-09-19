# ================================================================
#  Q2 8D 报告 AI 判定 — 长开服务器首次部署（在【服务器 192.168.100.51】上以管理员运行）
#    cd C:\q2\app
#    powershell -ExecutionPolicy Bypass -File deploy-server.ps1
#
#  布局（由笔记本 sync-to-server.ps1 推送形成）：
#    C:\q2\zhuopin_platform\   平台底座包
#    C:\q2\app\                Q2 工程（本脚本所在）
#    C:\q2\.venv\              虚拟环境（本脚本创建）
#    C:\q2\.env                共享口令门禁 ZP_GATE_PASSWORD（值不入库、不打印）
#
#  端口 8098 —— 过渡期独立端口（队列 §一 #612，Shao Peishen 2026-09-19 答 1a：「比照 FI3 #615
#  走独立端口过渡形态先上功能」），与 design D7「不新起端口、走 .51:8090 网关反代」相反，
#  先例＝FI3 8097（#615）。网关收编（决策件线③）时本端口、本防火墙规则一并回收。本脚本不碰 8090。
#
#  红线：本页只读档 1 mock 汇总，不接 QD-A，不写回任何系统；首屏显著标注「mock 数据」——
#        并非真实 8D 评审结论；L2，退回决定永远由质量工程师签发。
#  判据正本：3-治理与合规/.51部署标准清单-服务侧与笔记本侧-2026-08-01.md §三 七类坑
#    ① 本文件带 UTF-8 BOM   ② 防火墙 RemoteAddress Any   ③ AtStartup + SYSTEM
#    ④ venv python 绝对路径烘焙进 start-q2.ps1   ⑤ RestartCount 3 / 1 分钟
#    ⑥ ZP_GATE_PASSWORD 复用同机 fi3 的值（服务器本地复制，值不出机、不回显）   ⑦ 凭据只在 .env
# ================================================================

$ErrorActionPreference = "Stop"

$APP       = $PSScriptRoot                        # C:\q2\app
$BASE      = Split-Path $APP -Parent              # C:\q2
$PLATFORM  = Join-Path $BASE "zhuopin_platform"
$VENV      = Join-Path $BASE ".venv"
$PORT      = 8098
$PREFIX    = "/quality/q2"
$TASK      = "Q2WebServer"
$WEBSCRIPT = Join-Path $APP "scripts\run_q2_web.py"
$SIBLING_ENV = "C:\fi3\.env"                      # 同机既有服务的 .env（FI3，今日刚部署），只借 ZP_GATE_PASSWORD 那一行

Import-Module (Join-Path $BASE "deploy-tools\ZhuopinDeploy.psm1") -Force

Write-Host "`n== Q2 8D 报告 AI 判定 — 服务器部署 ==" -ForegroundColor Cyan
Write-Host "   基目录  : $BASE"
Write-Host "   平台底座: $PLATFORM"
Write-Host "   Q2 工程: $APP"
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

# ── 3. editable 安装平台 + Q2（flask/waitress 随 Q2 pyproject 依赖装上）──
Write-Host "[3/7] 安装依赖（zhuopin_platform + Q2）..." -ForegroundColor Yellow
& $pipExe install --quiet -e $PLATFORM
& $pipExe install --quiet -e $APP
Write-Host "      完成" -ForegroundColor Green

# ── 4. 共享口令 .env（ZP_GATE_PASSWORD，#160；#612：复用、不新设）──
#  Set-ZhuopinGatePasswordEnv 只保证「有这一行」；行值为空时从同机 C:\fi3\.env 借同名行——
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

# ── 5. 防火墙放行 8098（内网 LAN 全网段 RemoteAddress Any，同既有六服务惯例；不得限 LocalSubnet）──
Write-Host "[5/7] 防火墙（入站 TCP $PORT，LAN 全网段）..." -ForegroundColor Yellow
Register-ZhuopinFirewallRule -RuleName "Q2-WebServer-$PORT" -Port $PORT

# ── 6. 启动包装脚本（venv python 绝对路径烘焙；对外绑定只在这里置 0.0.0.0，run_q2_web.py 默认值不改）──
Write-Host "[6/7] 生成 start-q2.ps1..." -ForegroundColor Yellow
$startPs1 = Join-Path $APP "start-q2.ps1"
$startContent = @"
# Q2 web service launcher (shared by scheduled task and manual start)
`$env:Q2_WEB_HOST = "0.0.0.0"
`$env:Q2_WEB_PORT = "$PORT"
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
    -WorkingDirectory $APP -Description "Q2 8D 报告 AI 判定 门户页（端口 $PORT，档 1 mock，过渡期独立端口 #612）"

Write-Host "启动服务..." -ForegroundColor Yellow
$healthy = Start-ZhuopinWebServiceAndCheckHealth -TaskName $TASK -Port $PORT -HealthPath "$PREFIX/api/ping"

Write-Host "`n部署完成。" -ForegroundColor Green
Write-Host "   服务地址 : http://192.168.100.51:$PORT$PREFIX/"         -ForegroundColor Cyan
Write-Host "   健康检查 : http://192.168.100.51:$PORT$PREFIX/api/ping" -ForegroundColor DarkGray
Write-Host "   冒烟     : powershell -ExecutionPolicy Bypass -File $APP\smoke-server.ps1" -ForegroundColor DarkGray
Write-Host "   重启服务 : schtasks /End /TN $TASK ; schtasks /Run /TN $TASK" -ForegroundColor DarkGray
Write-Host "   回滚     : schtasks /End /TN $TASK ; schtasks /Delete /TN $TASK /F ; Remove-NetFirewallRule -DisplayName Q2-WebServer-$PORT（不清 .env：ZP_GATE_PASSWORD 为六服务共享键）" -ForegroundColor DarkGray
Write-Host "   ⚠️ 档 1 mock 数据——并非真实 8D 评审结论，退回由质量工程师签发；过渡期独立端口，网关收编时回收" -ForegroundColor Yellow
if (-not $healthy) { exit 1 }
