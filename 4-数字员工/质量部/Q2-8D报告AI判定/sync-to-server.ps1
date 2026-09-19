# ================================================================
#  Q2 8D 报告 AI 判定 — 同步代码到长开服务器
#  用途：把本机 Q2 工程 + 平台底座推送到 192.168.100.51，并重启服务
#  使用：在【笔记本】普通 PowerShell 运行
#        powershell -ExecutionPolicy Bypass -File sync-to-server.ps1
#
#  SSH/scp 同步 + 重启轮询验证的通用逻辑复用 `5-平台底座/deploy-tools/ZhuopinDeploy.psm1`
#  （同 SC8/QD-B/FI2/SC2/命令中心共用，重启可靠性修复一处改、全部受益）。
#
#  ⚠️ 只同步 data/mock（samples.json，11 份合成样本）与 data/rules（陈忱 V3.2 判据搬运件，
#  sha256 用例守）；tests/、reports/（审计明细）、.env、data/golden/ 均不上服务器。
#  档 1 只有 mock 源；真实数据（QD-A 解析）留档 2，不在本脚本范围。
# ================================================================

$APP  = $PSScriptRoot                                   # 本 Q2 工程目录
$REPO = (Get-Item $APP).Parent.Parent.Parent.FullName   # 仓库根

Import-Module (Join-Path $REPO "5-平台底座\deploy-tools\ZhuopinDeploy.psm1") -Force

$SshAlias = "supplychain-server"
$Base     = "C:/q2"

Write-Host "`n== Q2 8D 报告 AI 判定 服务器同步 ==" -ForegroundColor Cyan

Sync-ZhuopinPlatformAndApp `
    -ServerBase $Base `
    -LocalPlatformDir (Join-Path $REPO "5-平台底座\zhuopin_platform") `
    -LocalAppDir $APP `
    -AppFiles @("pyproject.toml", "q2_8d_verdict", "scripts", "deploy-server.ps1", "smoke-server.ps1") `
    -AppLabel "Q2 工程"

Write-Host "[mock 数据 + 判据规则表] 单独推送 data/mock、data/rules（均为合成/搬运件，可入库）..." -ForegroundColor Yellow
$winBase = $Base.Replace('/', '\')
ssh $SshAlias "if not exist $winBase\app\data mkdir $winBase\app\data"
scp -r "$APP\data\mock" "${SshAlias}:${Base}/app/data/"
if ($LASTEXITCODE -ne 0) { Write-Warning "mock 数据推送失败，请检查 SSH/scp" }
scp -r "$APP\data\rules" "${SshAlias}:${Base}/app/data/"
if ($LASTEXITCODE -ne 0) { Write-Warning "判据规则表推送失败，请检查 SSH/scp" } else { Write-Host "      OK" -ForegroundColor Green }

Write-Host "重启服务（轮询确认端口释放+新进程存活）..." -ForegroundColor Yellow
$result = Restart-ZhuopinTask -TaskName "Q2WebServer" -CheckMode Port -Port 8098

if (-not $result.Ok) {
    Write-Warning "自动重启失败或未确认成功（详情见上方远程输出：OLD_STILL_BUSY=旧进程杀不掉／RESTART_FAILED_NO_INSTANCE=新进程没起来，多半是首次部署、任务还没建）。"
    Write-Warning "首次部署：ssh $SshAlias 后 cd C:\q2\app → powershell -ExecutionPolicy Bypass -File deploy-server.ps1"
} else {
    Write-Host "      服务已重启并确认新进程存活（见上方 NEW_PID/CREATED）" -ForegroundColor Green
}

Write-Host "`n同步完成。" -ForegroundColor Green
Write-Host "   首次部署：在 .51 跑一次 deploy-server.ps1（建 venv+注册任务+防火墙+借共享口令）" -ForegroundColor Yellow
Write-Host "   冒烟    ：在 .51 跑 smoke-server.ps1（三件套：ping／未登录 302／登录后 200 含 mock 标注）" -ForegroundColor Yellow
Write-Host "   服务地址：http://192.168.100.51:8098/quality/q2/" -ForegroundColor Cyan
