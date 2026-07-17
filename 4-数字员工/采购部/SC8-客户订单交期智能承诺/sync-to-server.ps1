# ================================================================
#  成品保供预警看板 — 同步代码到长开服务器
#  用途：把本机 SC8 工程 + 平台底座推送到 192.168.100.51，并重启服务
#  使用：在【笔记本】普通 PowerShell 运行
#        powershell -ExecutionPolicy Bypass -File sync-to-server.ps1
#
#  2026-07-16 瘦身：SSH/scp 同步 + 重启轮询验证的通用逻辑已收拢进共享模块
#  `5-平台底座/deploy-tools/ZhuopinDeploy.psm1`（同一份重启可靠性修复现在
#  所有场景共用，改一处、全部受益，不再各自维护一份容易漂移的完整脚本）。
# ================================================================

$SC8  = $PSScriptRoot                                   # 本 SC8 工程目录
$REPO = (Get-Item $SC8).Parent.Parent.Parent.FullName   # 仓库根

Import-Module (Join-Path $REPO "5-平台底座\deploy-tools\ZhuopinDeploy.psm1") -Force

Write-Host "`n== 保供看板 服务器同步 ==" -ForegroundColor Cyan

Sync-ZhuopinPlatformAndApp `
    -ServerBase "C:/baoguan" `
    -LocalPlatformDir (Join-Path $REPO "5-平台底座\zhuopin_platform") `
    -LocalAppDir $SC8 `
    -AppFiles @("pyproject.toml", "sc8", "scripts", "deploy-server.ps1") `
    -AppLabel "SC8 工程"

Write-Host "[5/5] 重启服务（轮询确认端口释放+新进程存活）..." -ForegroundColor Yellow
$result = Restart-ZhuopinTask -TaskName "BaoguanWebServer" -CheckMode Port -Port 8091

if (-not $result.Ok) {
    Write-Warning "自动重启失败或未确认成功（详情见上方远程输出：OLD_STILL_BUSY=旧进程杀不掉／RESTART_FAILED_NO_INSTANCE=新进程没起来，多半是首次部署、任务还没建）。"
    Write-Warning "首次部署：RDP 登录 192.168.100.51 → 先把 .env 放到 C:\baoguan\.env →"
    Write-Warning "          cd C:\baoguan\app → powershell -ExecutionPolicy Bypass -File deploy-server.ps1"
} else {
    Write-Host "      服务已重启并确认新进程存活（见上方 NEW_PID/CREATED）" -ForegroundColor Green
}

Write-Host "`n同步完成。" -ForegroundColor Green
Write-Host "   首次部署：服务器放好 C:\baoguan\.env，再管理员跑一次 deploy-server.ps1（建 venv+注册任务）" -ForegroundColor Yellow
Write-Host "   看板地址：http://192.168.100.51:8091/" -ForegroundColor Cyan
Write-Host "   案例处置：http://192.168.100.51:8091/cases" -ForegroundColor Cyan
