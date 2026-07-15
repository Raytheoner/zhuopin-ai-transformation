# ================================================================
#  企微智能机器人双向通道服务 — 同步代码到长开服务器（照搬 SC8 baoguan-web-service）
#  用途：把本机 wecom-aibot-service 工程 + 平台底座推送到 192.168.100.51，并重启服务
#  使用：在【笔记本】普通 PowerShell 运行
#        powershell -ExecutionPolicy Bypass -File sync-to-server.ps1
#  依赖：~/.ssh/config 中的 "supplychain-server" 别名（→192.168.100.51，密钥已配，
#        与 SC8/supplychain/SalesMarketing 共用同一台服务器同一别名）
#
#  与 SC8 sync-to-server.ps1 的关键差异：本服务无监听端口，"重启前清旧实例"
#  改用命令行匹配（wmic）而非按端口找 PID（design.md D1：纯出站服务）。
# ================================================================

$SSH_ALIAS = "supplychain-server"          # 复用已配好的 SSH 别名（→192.168.100.51）
$SERVER_BASE = "C:/wecom-aibot"            # 服务器基目录（正斜杠）
$TASK = "WecomAibotService"

$APP  = $PSScriptRoot                                   # 本工程目录
$REPO = (Get-Item $APP).Parent.Parent.FullName          # 仓库根
$PLATFORM = Join-Path $REPO "5-平台底座\zhuopin_platform"

Write-Host "`n== 企微智能机器人服务 服务器同步 ==" -ForegroundColor Cyan
Write-Host "   SSH 别名 : $SSH_ALIAS (192.168.100.51)"
Write-Host "   服务器   : $SERVER_BASE  (平台→/zhuopin_platform, 本服务→/app)"
Write-Host "   本机来源 : $APP`n"

# ── 1. 检查 scp ──
Write-Host "[1/5] 检查 SSH 工具..." -ForegroundColor Yellow
if (-not (Get-Command scp -ErrorAction SilentlyContinue)) {
    Write-Error "找不到 scp。请装 Windows OpenSSH 客户端：设置→应用→可选功能→OpenSSH 客户端"; exit 1
}
if (-not (Test-Path $PLATFORM)) { Write-Error "未找到平台底座：$PLATFORM"; exit 1 }
Write-Host "      ssh/scp 可用" -ForegroundColor Green

# ── 2. 确保服务器目录存在（Windows OpenSSH 默认 shell = cmd.exe）──
Write-Host "[2/5] 确保服务器目录..." -ForegroundColor Yellow
ssh $SSH_ALIAS "if not exist C:\wecom-aibot\app mkdir C:\wecom-aibot\app"
Write-Host "      OK" -ForegroundColor Green

# ── 3. 推送平台底座（落 C:/wecom-aibot/zhuopin_platform）──
Write-Host "[3/5] 推送平台底座..." -ForegroundColor Yellow
scp -r "$PLATFORM" "${SSH_ALIAS}:${SERVER_BASE}/"
if ($LASTEXITCODE -ne 0) { Write-Error "平台底座同步失败"; exit 1 }
Write-Host "      OK" -ForegroundColor Green

# ── 4. 推送本工程（只推运行所需：pyproject + aibot_service/ + scripts/ + 部署脚本；
#       不推 reports/(含审计明细/发送人姓名)、tests/、.venv）──
Write-Host "[4/5] 推送本工程..." -ForegroundColor Yellow
scp    "$APP\pyproject.toml"     "${SSH_ALIAS}:${SERVER_BASE}/app/"
scp -r "$APP\aibot_service"      "${SSH_ALIAS}:${SERVER_BASE}/app/"
scp -r "$APP\scripts"            "${SSH_ALIAS}:${SERVER_BASE}/app/"
scp    "$APP\deploy-server.ps1"  "${SSH_ALIAS}:${SERVER_BASE}/app/"
if ($LASTEXITCODE -ne 0) { Write-Warning "部分文件同步失败，请检查" }
Write-Host "      OK" -ForegroundColor Green

# ── 5. 重启服务 ──
# 无监听端口可按端口清旧实例（区别于 SC8），改用命令行匹配 kill 残留 python。
# 首次部署任务不存在 → 杀进程/重启均无害失败 → 提示去服务器跑 deploy-server.ps1。
Write-Host "[5/5] 重启服务（按命令行清旧实例，防孤儿残留）..." -ForegroundColor Yellow
ssh $SSH_ALIAS "schtasks /End /TN $TASK 2>nul & wmic process where `"CommandLine like '%run_aibot_service.py%'`" call terminate 2>nul" | Out-Null
ssh $SSH_ALIAS "timeout /t 2 /nobreak >nul & schtasks /Run /TN $TASK" | Out-Null
if ($LASTEXITCODE -ne 0) {
    Write-Warning "自动重启失败（多半是首次部署、任务还没建）。"
    Write-Warning "首次部署：RDP 登录 192.168.100.51 → 先把 .env 放到 C:\wecom-aibot\.env →"
    Write-Warning "          cd C:\wecom-aibot\app → powershell -ExecutionPolicy Bypass -File deploy-server.ps1"
} else {
    Write-Host "      服务已重启" -ForegroundColor Green
}

Write-Host "`n同步完成。" -ForegroundColor Green
Write-Host "   首次部署：服务器放好 C:\wecom-aibot\.env，再管理员跑一次 deploy-server.ps1（建 venv+注册任务）" -ForegroundColor Yellow
Write-Host "   查看状态：ssh $SSH_ALIAS `"schtasks /Query /TN $TASK`"" -ForegroundColor Cyan
