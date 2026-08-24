# ================================================================
#  SC2 采购周报自动生成 — 长开服务器首次部署（在【服务器 192.168.100.51】上以管理员运行）
#    cd C:\sc2\app
#    powershell -ExecutionPolicy Bypass -File deploy-server.ps1
#
#  布局（由笔记本 sync-to-server.ps1 推送形成，**扁平、非 monorepo**）：
#    C:\sc2\zhuopin_platform\   平台底座包
#    C:\sc2\app\                SC2 工程（本脚本所在）
#    C:\sc2\.venv\              虚拟环境（本脚本创建）
#  ⚠️ 这套扁平布局正是队列 #345 那颗地雷的触发条件——run_sc2.py 顶部的 #300 引导
#     必须能在找不到 `5-平台底座/` 标记时回退，否则服务进程秒退而计划任务仍报 0。
#
#  端口 8096。⚠️ **不是 design 审 ④(a) 原定的 8095**——8095 已被 ZhuopinRecruitAgent
#  占用（2026-08-18 部署当日实测），Shao Peishen 同日改判 8096。
#  ⚠️ 这是对「新场景一律不新起端口对外」硬约束的**显式豁免**，注销条件＝统一门户
#     网关落地后收编至 /procurement/sc2 路由。详见场景 CLAUDE.md「部署状态」段。
#
#  红线：周报生成物与审计只落 app/reports/（gitignore）；仅 LAN 访问（共享口令门禁）；
#        **不自动执行任何业务动作**（只生成与推送一份报表）。
#  🔴 2026-08-25 起「确认发布」不再是推送前置（队列 §四 #89，Shao Peishen 2026-08-22
#     拍板 (a)：周五 20:00 自动生成并自动推群；连带定性「SC2 周报不属 IATF 需签认输出」
#     亦已拍板）。页面上的签认按钮保留，记录的是**事后复核**。
# ================================================================

$ErrorActionPreference = "Stop"

$APP      = $PSScriptRoot                         # C:\sc2\app
$BASE     = Split-Path $APP -Parent               # C:\sc2
$PLATFORM = Join-Path $BASE "zhuopin_platform"
$VENV     = Join-Path $BASE ".venv"
$PORT     = 8096
$TASK     = "Sc2WebServer"
$PUSHTASK = "Sc2WeeklyAutoPush"        # 周五 20:00 自动生成并推群（队列 §四 #89）
$PREFIX   = "/procurement/sc2"
$WEBSCRIPT = Join-Path $APP "run_sc2.py"

Import-Module (Join-Path $BASE "deploy-tools\ZhuopinDeploy.psm1") -Force

Write-Host "`n== SC2 采购周报自动生成 — 服务器部署 ==" -ForegroundColor Cyan
Write-Host "   基目录  : $BASE"
Write-Host "   平台底座: $PLATFORM"
Write-Host "   SC2 工程: $APP"
Write-Host "   端口    : $PORT   路由前缀: $PREFIX`n"

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

# ── 3. editable 安装平台 + SC2（flask/waitress 随 SC2 依赖装上）──
Write-Host "[3/7] 安装依赖（zhuopin_platform + SC2）..." -ForegroundColor Yellow
& $pipExe install --quiet -e $PLATFORM
& $pipExe install --quiet -e $APP
Write-Host "      完成" -ForegroundColor Green

# ── 4. 凭据 .env ──
#  SC2 真实模式需要 ERP（ZpConnector）凭据 STOCK_API_BASE / STOCK_API_KEY，
#  以及四服务共享的 ZP_GATE_PASSWORD。🔴 凭据只进 .env，不入库、不打印值。
Write-Host "[4/7] 检查凭据 .env..." -ForegroundColor Yellow
$envFile = Join-Path $BASE ".env"
Set-ZhuopinGatePasswordEnv -EnvFile $envFile
$envText = if (Test-Path $envFile) { Get-Content $envFile } else { @() }
foreach ($k in @("STOCK_API_BASE", "STOCK_API_KEY")) {
    if (-not ($envText -match "^\s*$k=\S")) {
        Write-Warning "      $envFile 缺少 $k —— 真实模式取数会失败。可照抄 C:\fi2\.env 同名键。"
    } else {
        Write-Host "      $k 已就位" -ForegroundColor Green
    }
}

# ── 5. 防火墙放行 8096 ──
#  🔴 只在 .51 本机冒烟 200 是假象，不补入站规则外部会超时（根 CLAUDE.md 坑 5）。
Write-Host "[5/7] 防火墙（入站 TCP $PORT，LAN 全网段）..." -ForegroundColor Yellow
Register-ZhuopinFirewallRule -RuleName "Sc2-WebServer-$PORT" -Port $PORT

# ── 6. 启动包装脚本 ──
Write-Host "[6/7] 生成 start-sc2.ps1..." -ForegroundColor Yellow
$startPs1 = Join-Path $APP "start-sc2.ps1"
$startContent = @"
# SC2 weekly report service launcher (shared by scheduled task and manual start)
& "$pyExe" "$WEBSCRIPT" serve --mode real --port $PORT
"@
Set-Content -Path $startPs1 -Value $startContent -Encoding UTF8
Write-Host "      已生成" -ForegroundColor Green

# ── 7. 计划任务（开机自启、SYSTEM、失败重启3次）+ 启动 + 健康检查 ──
#  🔴 健康检查路径必须带路由前缀：本场景没有裸 /api/ping。
Write-Host "[7/8] 注册计划任务 $TASK..." -ForegroundColor Yellow
Register-ZhuopinScheduledTask -TaskName $TASK `
    -Execute "powershell.exe" -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$startPs1`"" `
    -WorkingDirectory $APP -Description "SC2 采购周报自动生成 Web 服务（端口 $PORT，试用版）"

Write-Host "启动服务..." -ForegroundColor Yellow
Start-ZhuopinWebServiceAndCheckHealth -TaskName $TASK -Port $PORT -HealthPath "$PREFIX/api/ping" | Out-Null

# ── 8. 周五 20:00 自动生成并推群（队列 §四 #89，Shao Peishen 2026-08-22 拍板 (a)）──
#  姚祖怡原话：「周五晚 8 点自动给出本周的，出来后挂到页面上，同步推到群里」。
#  🔴 确认发布前置已按该拍板取消；连带定性「SC2 周报不属 IATF 需签认输出」亦已拍板。
#
#  ⚠️ 这个任务**独立于 Web 服务进程**：它是一次性跑完就退的 CLI，不是常驻服务。
#     故 -ExecutionTimeLimitHours 2（真实全量取数实测约 2 分 20 秒，2 小时是宽松上限）
#     ＋ -MultipleInstancesIgnoreNew —— 两者必须一起给：只给后者而不限时，一次挂死
#     就会把此后每周的触发全部静默 IgnoreNew 掉，表现为「任务还在、再也没跑过」。
Write-Host "[8/8] 注册周报自动推送任务 $PUSHTASK（每周五 20:00）..." -ForegroundColor Yellow
$pushPs1 = Join-Path $APP "autopush-sc2.ps1"
$pushContent = @"
# SC2 weekly report auto-generate + push to WeCom group (Fri 20:00)
& "$pyExe" "$WEBSCRIPT" autopush --mode real
"@
Set-Content -Path $pushPs1 -Value $pushContent -Encoding UTF8

Register-ZhuopinScheduledTask -TaskName $PUSHTASK `
    -Execute "powershell.exe" -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$pushPs1`"" `
    -WorkingDirectory $APP `
    -Description "SC2 采购周报：每周五 20:00 自动生成并推送采购部群（队列 #89）" `
    -Trigger (New-ScheduledTaskTrigger -Weekly -DaysOfWeek Friday -At "20:00") `
    -ExecutionTimeLimitHours 2 -MultipleInstancesIgnoreNew -StartWhenAvailable

Write-Host "`n部署完成。" -ForegroundColor Green
Write-Host "   服务地址 : http://192.168.100.51:$PORT$PREFIX/"        -ForegroundColor Cyan
Write-Host "   健康检查 : http://192.168.100.51:$PORT$PREFIX/api/ping" -ForegroundColor DarkGray
Write-Host "   全量重算 : POST http://192.168.100.51:$PORT$PREFIX/api/refresh （真实模式约 2 分 20 秒）" -ForegroundColor DarkGray
Write-Host "   重启服务 : schtasks /End /TN $TASK ; schtasks /Run /TN $TASK" -ForegroundColor DarkGray
Write-Host "   自动推送 : $PUSHTASK 每周五 20:00（手工试跑：schtasks /Run /TN $PUSHTASK）" -ForegroundColor DarkGray
Write-Host "   回滚     : schtasks /End /TN $TASK ; schtasks /Delete /TN $TASK /F ; schtasks /Delete /TN $PUSHTASK /F ; 防火墙规则 Sc2-WebServer-$PORT 可留" -ForegroundColor DarkGray
Write-Host "   ⚠️ 仅 LAN（共享口令门禁）；周五 20:00 自动生成并推群，确认发布前置已按 #89 取消" -ForegroundColor Yellow
Write-Host "   ⚠️ 推送经 outbox 落盘、由笔记本侧中继代发 —— 中继未上线前消息只会积压，不会送达" -ForegroundColor Yellow
