# ================================================================
#  FI2 三单匹配自动对账 — 同步代码到长开服务器
#  用途：把本机 FI2 工程 + 平台底座推送到 192.168.100.51，并重启服务
#  使用：在【笔记本】普通 PowerShell 运行
#        powershell -ExecutionPolicy Bypass -File sync-to-server.ps1
#
#  SSH/scp 同步 + 重启轮询验证的通用逻辑复用 `5-平台底座/deploy-tools/ZhuopinDeploy.psm1`
#  （同 SC8/QD-B/命令中心/企微机器人共用，重启可靠性修复一处改、全部受益）。
#
#  ⚠️ 只同步 data/mock（纯合成演示数据，无真实供应商/金额，供 Web 表单"mock 演示"选项
#  使用）；data/golden（黄金基准）与真实快照（data/real_*，财务红色数据）均不上生产服务器。
#  生产使用走 data_source=u9c（真实直读）或 data_source=csv（财务专员在服务器本机自行
#  准备的快照目录，如 dump_u9c_snapshot.py 产出 + 人工誊录 invoice.csv，round-1 已验证路径）。
# ================================================================

$APP  = $PSScriptRoot                                   # 本 FI2 工程目录
$REPO = (Get-Item $APP).Parent.Parent.Parent.FullName   # 仓库根

Import-Module (Join-Path $REPO "5-平台底座\deploy-tools\ZhuopinDeploy.psm1") -Force

$SshAlias = "supplychain-server"
$Base     = "C:/fi2"

Write-Host "`n== FI2 三单匹配自动对账 服务器同步 ==" -ForegroundColor Cyan

Sync-ZhuopinPlatformAndApp `
    -ServerBase $Base `
    -LocalPlatformDir (Join-Path $REPO "5-平台底座\zhuopin_platform") `
    -LocalAppDir $APP `
    -AppFiles @("pyproject.toml", "fi2", "scripts", "deploy-server.ps1", "register-tax-export-scan-task.ps1") `
    -AppLabel "FI2 工程"

Write-Host "[mock 演示数据] 单独推送 data/mock/（纯合成，不含真实数据）..." -ForegroundColor Yellow
$winBase = $Base.Replace('/', '\')
ssh $SshAlias "if not exist $winBase\app\data mkdir $winBase\app\data"
scp -r "$APP\data\mock" "${SshAlias}:${Base}/app/data/"
if ($LASTEXITCODE -ne 0) { Write-Warning "mock 演示数据推送失败，请检查 SSH/scp" } else { Write-Host "      OK" -ForegroundColor Green }

Write-Host "重启服务（轮询确认端口释放+新进程存活）..." -ForegroundColor Yellow
$result = Restart-ZhuopinTask -TaskName "Fi2WebServer" -CheckMode Port -Port 8094

if (-not $result.Ok) {
    Write-Warning "自动重启失败或未确认成功（详情见上方远程输出：OLD_STILL_BUSY=旧进程杀不掉／RESTART_FAILED_NO_INSTANCE=新进程没起来，多半是首次部署、任务还没建）。"
    Write-Warning "首次部署：RDP 登录 192.168.100.51 → cd C:\fi2\app → powershell -ExecutionPolicy Bypass -File deploy-server.ps1"
} else {
    Write-Host "      服务已重启并确认新进程存活（见上方 NEW_PID/CREATED）" -ForegroundColor Green
}

Write-Host "`n同步完成。" -ForegroundColor Green
Write-Host "   首次部署：管理员登录 .51 跑一次 deploy-server.ps1（建 venv+注册任务+防火墙）" -ForegroundColor Yellow
Write-Host "   服务地址：http://192.168.100.51:8094/" -ForegroundColor Cyan
