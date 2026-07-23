# ================================================================
#  QD-B 立项审核门禁 — 同步代码到长开服务器
#  用途：把本机 QD-B 工程 + 平台底座推送到 192.168.100.51，并重启服务
#  使用：在【笔记本】普通 PowerShell 运行
#        powershell -ExecutionPolicy Bypass -File sync-to-server.ps1
#
#  SSH/scp 同步 + 重启轮询验证的通用逻辑复用 `5-平台底座/deploy-tools/ZhuopinDeploy.psm1`
#  （同 SC8/命令中心/企微机器人共用，重启可靠性修复一处改、全部受益）。
#
#  ⚠️ 规则注册表 `data/rules/registry.json` 单独推送（不用 AppFiles 整目录同步 data/，
#  避免带上 `data/golden/` 下的真实黄金样本——那些是本机 LAN 测试用件，红线要求不出本机）。
# ================================================================

$APP  = $PSScriptRoot                                   # 本 QD-B 工程目录
$REPO = (Get-Item $APP).Parent.Parent.Parent.FullName   # 仓库根

Import-Module (Join-Path $REPO "5-平台底座\deploy-tools\ZhuopinDeploy.psm1") -Force

$SshAlias = "supplychain-server"
$Base     = "C:/qd-b"

Write-Host "`n== QD-B 立项审核门禁 服务器同步 ==" -ForegroundColor Cyan

Sync-ZhuopinPlatformAndApp `
    -ServerBase $Base `
    -LocalPlatformDir (Join-Path $REPO "5-平台底座\zhuopin_platform") `
    -LocalAppDir $APP `
    -AppFiles @("pyproject.toml", "qd_b_gate", "scripts", "deploy-server.ps1") `
    -AppLabel "QD-B 工程"

Write-Host "[规则注册表] 单独推送 data/rules/registry.json..." -ForegroundColor Yellow
$winBase = $Base.Replace('/', '\')
ssh $SshAlias "if not exist $winBase\app\data\rules mkdir $winBase\app\data\rules"
scp "$APP\data\rules\registry.json" "${SshAlias}:${Base}/app/data/rules/registry.json"
if ($LASTEXITCODE -ne 0) { Write-Warning "规则注册表推送失败，请检查 SSH/scp" } else { Write-Host "      OK" -ForegroundColor Green }

Write-Host "重启服务（轮询确认端口释放+新进程存活）..." -ForegroundColor Yellow
$result = Restart-ZhuopinTask -TaskName "QdBWebServer" -CheckMode Port -Port 8093

if (-not $result.Ok) {
    Write-Warning "自动重启失败或未确认成功（详情见上方远程输出：OLD_STILL_BUSY=旧进程杀不掉／RESTART_FAILED_NO_INSTANCE=新进程没起来，多半是首次部署、任务还没建）。"
    Write-Warning "首次部署：RDP 登录 192.168.100.51 → cd C:\qd-b\app → powershell -ExecutionPolicy Bypass -File deploy-server.ps1"
} else {
    Write-Host "      服务已重启并确认新进程存活（见上方 NEW_PID/CREATED）" -ForegroundColor Green
}

Write-Host "`n同步完成。" -ForegroundColor Green
Write-Host "   首次部署：管理员登录 .51 跑一次 deploy-server.ps1（建 venv+注册任务+防火墙）" -ForegroundColor Yellow
Write-Host "   服务地址：http://192.168.100.51:8093/" -ForegroundColor Cyan
