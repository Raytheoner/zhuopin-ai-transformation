# ================================================================
#  统一门户网关 — 同步代码到长开服务器
#  用途：把本机网关工程 + 平台底座推送到 192.168.100.51，并重启服务
#  使用：在【笔记本】普通 PowerShell 运行
#        powershell -ExecutionPolicy Bypass -File sync-to-server.ps1
#
#  SSH/scp 同步 + 重启轮询验证的通用逻辑复用 `5-平台底座/deploy-tools/ZhuopinDeploy.psm1`
#  （同 SC8/QD-B/FI2/命令中心/企微机器人共用，重启可靠性修复一处改、全部受益）。
# ================================================================

$APP  = $PSScriptRoot                                   # 本网关工程目录（5-平台底座/unified-portal-gateway）
$REPO = (Get-Item $APP).Parent.Parent.FullName          # 仓库根

Import-Module (Join-Path $REPO "5-平台底座\deploy-tools\ZhuopinDeploy.psm1") -Force

$SshAlias = "supplychain-server"
$Base     = "C:/portal-gateway"

Write-Host "`n== 统一门户网关 服务器同步 ==" -ForegroundColor Cyan

Sync-ZhuopinPlatformAndApp `
    -ServerBase $Base `
    -LocalPlatformDir (Join-Path $REPO "5-平台底座\zhuopin_platform") `
    -LocalAppDir $APP `
    -AppFiles @("pyproject.toml", "portal_gateway", "scripts", "deploy-server.ps1") `
    -AppLabel "网关工程"

Write-Host "重启服务（轮询确认端口释放+新进程存活）..." -ForegroundColor Yellow
$result = Restart-ZhuopinTask -TaskName "UnifiedPortalGateway" -CheckMode Port -Port 8090

if (-not $result.Ok) {
    Write-Warning "自动重启失败或未确认成功（详情见上方远程输出：OLD_STILL_BUSY=旧进程杀不掉／RESTART_FAILED_NO_INSTANCE=新进程没起来，多半是首次部署、任务还没建）。"
    Write-Warning "首次部署：RDP 登录 192.168.100.51 → cd C:\portal-gateway\app → powershell -ExecutionPolicy Bypass -File deploy-server.ps1"
} else {
    Write-Host "      服务已重启并确认新进程存活（见上方 NEW_PID/CREATED）" -ForegroundColor Green
}

Write-Host "`n同步完成。" -ForegroundColor Green
Write-Host "   首次部署：管理员登录 .51 跑一次 deploy-server.ps1（建 venv+注册任务+防火墙+.env 提示）" -ForegroundColor Yellow
Write-Host "   服务地址：http://192.168.100.51:8090/" -ForegroundColor Cyan
