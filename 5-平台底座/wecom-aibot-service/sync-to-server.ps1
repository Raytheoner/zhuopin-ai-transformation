# ================================================================
#  企微智能机器人双向通道服务 — 同步代码到长开服务器
#  用途：把本机 wecom-aibot-service 工程 + 平台底座推送到 192.168.100.51，并重启服务
#  使用：在【笔记本】普通 PowerShell 运行
#        powershell -ExecutionPolicy Bypass -File sync-to-server.ps1
#
#  ⚠️ 本服务 .51 正式发布是独立后续动作（见 CLAUDE.md §6 范围澄清，Paul 2026-07-13
#  拍板），本脚本目前不在常规使用——保留、瘦身，供日后 Paul 拍板发布时直接用。
#
#  2026-07-16 瘦身：SSH/scp 同步 + 重启轮询验证的通用逻辑已收拢进共享模块
#  `5-平台底座/deploy-tools/ZhuopinDeploy.psm1`（与 SC8 共用同一份重启可靠性
#  修复——本服务此前一直没跟上 SC8 那次修复，这次瘦身顺带补齐，不再各自维护
#  一份容易漂移的完整脚本）。
#
#  与 SC8 的关键差异：本服务无监听端口，"重启前清旧实例"用命令行匹配（区别于
#  SC8 按端口找 PID），走 ZhuopinDeploy 模块的 -CheckMode ProcessMatch。
# ================================================================

$APP  = $PSScriptRoot                                   # 本工程目录
$REPO = (Get-Item $APP).Parent.Parent.FullName          # 仓库根

Import-Module (Join-Path $REPO "5-平台底座\deploy-tools\ZhuopinDeploy.psm1") -Force

Write-Host "`n== 企微智能机器人服务 服务器同步 ==" -ForegroundColor Cyan

Sync-ZhuopinPlatformAndApp `
    -ServerBase "C:/wecom-aibot" `
    -LocalPlatformDir (Join-Path $REPO "5-平台底座\zhuopin_platform") `
    -LocalAppDir $APP `
    -AppFiles @("pyproject.toml", "aibot_service", "scripts", "deploy-server.ps1") `
    -AppLabel "本服务"

Write-Host "[5/5] 重启服务（按命令行清旧实例，轮询确认真正重启）..." -ForegroundColor Yellow
$result = Restart-ZhuopinTask -TaskName "WecomAibotService" -CheckMode ProcessMatch -ProcessMatchPattern "run_aibot_service.py"

if (-not $result.Ok) {
    Write-Warning "自动重启失败或未确认成功（详情见上方远程输出：OLD_STILL_BUSY=旧进程杀不掉／RESTART_FAILED_NO_INSTANCE=新进程没起来，多半是首次部署、任务还没建）。"
    Write-Warning "首次部署：RDP 登录 192.168.100.51 → 先把 .env 放到 C:\wecom-aibot\.env →"
    Write-Warning "          cd C:\wecom-aibot\app → powershell -ExecutionPolicy Bypass -File deploy-server.ps1"
} else {
    Write-Host "      服务已重启并确认新进程存活（见上方 NEW_PID/CREATED）" -ForegroundColor Green
}

Write-Host "`n同步完成。" -ForegroundColor Green
Write-Host "   首次部署：服务器放好 C:\wecom-aibot\.env，再管理员跑一次 deploy-server.ps1（建 venv+注册任务）" -ForegroundColor Yellow
Write-Host "   查看状态：ssh supplychain-server `"schtasks /Query /TN WecomAibotService`"" -ForegroundColor Cyan
