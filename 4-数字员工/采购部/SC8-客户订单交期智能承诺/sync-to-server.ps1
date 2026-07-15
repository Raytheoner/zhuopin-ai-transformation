# ================================================================
#  成品保供预警看板 — 同步代码到长开服务器（照搬 supplychain/SalesMarketing）
#  用途：把本机 SC8 工程 + 平台底座推送到 192.168.100.51，并重启服务
#  使用：在【笔记本】普通 PowerShell 运行
#        powershell -ExecutionPolicy Bypass -File sync-to-server.ps1
#  依赖：~/.ssh/config 中的 "supplychain-server" 别名（→192.168.100.51，密钥已配）
# ================================================================

$SSH_ALIAS = "supplychain-server"          # 复用已配好的 SSH 别名（→192.168.100.51）
$SERVER_BASE = "C:/baoguan"                # 服务器基目录（正斜杠）
$TASK = "BaoguanWebServer"
$PORT = 8091

$SC8  = $PSScriptRoot                                   # 本 SC8 工程目录
$REPO = (Get-Item $SC8).Parent.Parent.Parent.FullName   # 仓库根
$PLATFORM = Join-Path $REPO "5-平台底座\zhuopin_platform"

Write-Host "`n== 保供看板 服务器同步 ==" -ForegroundColor Cyan
Write-Host "   SSH 别名 : $SSH_ALIAS (192.168.100.51)"
Write-Host "   服务器   : $SERVER_BASE  (平台→/zhuopin_platform, SC8→/app)"
Write-Host "   本机来源 : $SC8`n"

# ── 1. 检查 scp ──
Write-Host "[1/5] 检查 SSH 工具..." -ForegroundColor Yellow
if (-not (Get-Command scp -ErrorAction SilentlyContinue)) {
    Write-Error "找不到 scp。请装 Windows OpenSSH 客户端：设置→应用→可选功能→OpenSSH 客户端"; exit 1
}
if (-not (Test-Path $PLATFORM)) { Write-Error "未找到平台底座：$PLATFORM"; exit 1 }
Write-Host "      ssh/scp 可用" -ForegroundColor Green

# ── 2. 确保服务器目录存在（Windows OpenSSH 默认 shell = cmd.exe）──
Write-Host "[2/5] 确保服务器目录..." -ForegroundColor Yellow
ssh $SSH_ALIAS "if not exist C:\baoguan\app mkdir C:\baoguan\app"
Write-Host "      OK" -ForegroundColor Green

# ── 3. 推送平台底座（落 C:/baoguan/zhuopin_platform）──
Write-Host "[3/5] 推送平台底座..." -ForegroundColor Yellow
scp -r "$PLATFORM" "${SSH_ALIAS}:${SERVER_BASE}/"
if ($LASTEXITCODE -ne 0) { Write-Error "平台底座同步失败"; exit 1 }
Write-Host "      OK" -ForegroundColor Green

# ── 4. 推送 SC8 工程（只推运行所需：pyproject + sc8/ + scripts/ + 部署脚本；
#       不推 reports/(含真实客户名)、tests/、.venv）──
Write-Host "[4/5] 推送 SC8 工程..." -ForegroundColor Yellow
scp    "$SC8\pyproject.toml"     "${SSH_ALIAS}:${SERVER_BASE}/app/"
scp -r "$SC8\sc8"                "${SSH_ALIAS}:${SERVER_BASE}/app/"
scp -r "$SC8\scripts"            "${SSH_ALIAS}:${SERVER_BASE}/app/"
scp    "$SC8\deploy-server.ps1"  "${SSH_ALIAS}:${SERVER_BASE}/app/"
if ($LASTEXITCODE -ne 0) { Write-Warning "部分文件同步失败，请检查" }
Write-Host "      OK" -ForegroundColor Green

# ── 5. 重启服务（轮询确认端口真正释放 + 新进程真正起来，不再赌固定 2 秒）──
# 07-15 修复背景：原版 schtasks /End + 按端口 taskkill 两次观察到不一致——2026-07-14 首次
# 部署时 taskkill 未真正杀掉旧进程（需手动介入），同日晚些又正常生效，时序原因未深挖。
# 固定 `timeout /t 2` 赌"2 秒内一定死透"不可靠；改走远程 PowerShell 主动轮询：
# Stop-Process 循环确认端口释放 → schtasks /Run → 循环确认新监听进程出现并回传其 PID/
# 启动时间，而不是打印"服务已重启"就当真（这正是 2026-07-14 那次事故的教训）。
# 首次部署任务不存在 → /End 无害失败、/Run 后等不到监听 → 按原逻辑提示跑 deploy-server.ps1。
Write-Host "[5/5] 重启服务（轮询确认端口释放+新进程存活）..." -ForegroundColor Yellow

$restartScript = @"
`$port = $PORT
`$task = '$TASK'
function Get-PortPids(`$p) {
    Get-NetTCPConnection -LocalPort `$p -State Listen -ErrorAction SilentlyContinue |
        Select-Object -ExpandProperty OwningProcess -Unique
}
schtasks /End /TN `$task 2>`$null | Out-Null
`$deadline = (Get-Date).AddSeconds(15)
while ((Get-Date) -lt `$deadline) {
    `$pids = Get-PortPids `$port
    if (-not `$pids) { break }
    foreach (`$p in `$pids) { Stop-Process -Id `$p -Force -ErrorAction SilentlyContinue }
    Start-Sleep -Milliseconds 500
}
`$remaining = Get-PortPids `$port
if (`$remaining) { Write-Output "PORT_STILL_BUSY:`$(`$remaining -join ',')"; exit 1 }
Write-Output "PORT_CLEAR"
schtasks /Run /TN `$task | Out-Null
`$deadline2 = (Get-Date).AddSeconds(15)
`$newPid = `$null
while ((Get-Date) -lt `$deadline2) {
    `$pids = Get-PortPids `$port
    if (`$pids) { `$newPid = `$pids | Select-Object -First 1; break }
    Start-Sleep -Milliseconds 500
}
if (-not `$newPid) { Write-Output "RESTART_FAILED_NO_LISTENER"; exit 1 }
`$proc = Get-Process -Id `$newPid -ErrorAction SilentlyContinue
Write-Output "NEW_PID=`$newPid CREATED=`$(`$proc.StartTime.ToString('yyyy-MM-dd HH:mm:ss'))"
"@

$encoded = [Convert]::ToBase64String([System.Text.Encoding]::Unicode.GetBytes($restartScript))
$remoteOutput = ssh $SSH_ALIAS "powershell -NoProfile -NonInteractive -EncodedCommand $encoded"
$restartOk = ($LASTEXITCODE -eq 0)

if ($remoteOutput) { $remoteOutput | ForEach-Object { Write-Host "      $_" -ForegroundColor DarkGray } }

if (-not $restartOk) {
    Write-Warning "自动重启失败或未确认成功（详情见上方远程输出：PORT_STILL_BUSY=旧进程杀不掉／RESTART_FAILED_NO_LISTENER=新进程没起来，多半是首次部署、任务还没建）。"
    Write-Warning "首次部署：RDP 登录 192.168.100.51 → 先把 .env 放到 C:\baoguan\.env →"
    Write-Warning "          cd C:\baoguan\app → powershell -ExecutionPolicy Bypass -File deploy-server.ps1"
} else {
    Write-Host "      服务已重启并确认新进程存活（见上方 NEW_PID/CREATED）" -ForegroundColor Green
}

Write-Host "`n同步完成。" -ForegroundColor Green
Write-Host "   首次部署：服务器放好 C:\baoguan\.env，再管理员跑一次 deploy-server.ps1（建 venv+注册任务）" -ForegroundColor Yellow
Write-Host "   看板地址：http://192.168.100.51:8091/" -ForegroundColor Cyan
Write-Host "   案例处置：http://192.168.100.51:8091/cases" -ForegroundColor Cyan
