# ================================================================
#  AI 运营指挥中心 · 同步到 .51 + 重启（在【笔记本】普通 PowerShell 运行）
#      powershell -ExecutionPolicy Bypass -File sync-to-server.ps1
#
#  首次部署顺序：
#    1) 笔记本跑本脚本（推 index.html + serve.py + deploy-server.ps1 到 C:\command-center）
#    2) RDP 登录 192.168.100.51 → 管理员 PowerShell → cd C:\command-center →
#       powershell -ExecutionPolicy Bypass -File deploy-server.ps1   （注册计划任务，仅首次）
#    3) 之后日常更新只跑本脚本即可（推文件 + 自动重启，无需再跑 deploy-server.ps1）
#
#  依赖：~/.ssh/config 的 supplychain-server 别名（→192.168.100.51）；Windows OpenSSH 客户端。
#  端口 8092 / 目录 C:/command-center / 任务 CommandCenterWeb —— 与保供看板(8091/C:\baoguan)完全隔离。
# ================================================================
$CC   = $PSScriptRoot
$REPO = (Get-Item $CC).Parent.Parent.FullName          # 仓库根（AI运营指挥中心 在 1-转型规划 下 → 上两级）
Import-Module (Join-Path $REPO "5-平台底座\deploy-tools\ZhuopinDeploy.psm1") -Force

$SshAlias = "supplychain-server"
$Base     = "C:/command-center"
$winBase  = $Base.Replace('/', '\')

# 取最新一份命令中心页面（框架原型-*.html，取修改时间最新的一个）
$page = Get-ChildItem $CC -Filter "AI运营指挥中心-框架原型-*.html" | Sort-Object LastWriteTime -Descending | Select-Object -First 1
if (-not $page) { throw "未找到 AI运营指挥中心-框架原型-*.html" }

Write-Host "`n== AI 运营指挥中心 服务器同步 ==" -ForegroundColor Cyan
Write-Host "   源页面 : $($page.Name)  →  $Base/index.html" -ForegroundColor DarkGray

ssh $SshAlias "if not exist $winBase\data mkdir $winBase\data"
scp "$($page.FullName)"        "${SshAlias}:${Base}/index.html"
scp "$CC\serve.py"             "${SshAlias}:${Base}/serve.py"
scp "$CC\deploy-server.ps1"    "${SshAlias}:${Base}/deploy-server.ps1"
if ($LASTEXITCODE -ne 0) { Write-Warning "部分文件同步失败，请检查 SSH/scp" }

# deploy-server.ps1 在服务器上 Import-Module 复用注册/健康检查函数，需先推送该模块自身
# （本脚本不走 Sync-ZhuopinPlatformAndApp，故需单独调用，其余四服务经该函数自动推送）
Publish-ZhuopinDeployToolsModule -SshAlias $SshAlias -ServerBase $Base

# 销售JSON由.51同机refresh_sales.py在完整取数与脱敏后发布。
# 整站发布保留服务器最后有效销售快照，避免用笔记本旧数据覆盖日同步结果。
# 首次销售数据初始化也须走获批的销售刷新验收，不从仓库历史JSON补造新数据。
Write-Host "   保留服务器销售快照；销售更新由独立获批的同机入口执行。" -ForegroundColor Yellow

Write-Host "重启服务（轮询确认端口释放 + 新进程存活）..." -ForegroundColor Yellow
$r = Restart-ZhuopinTask -TaskName "CommandCenterWeb" -CheckMode Port -Port 8092
if (-not $r.Ok) {
    Write-Warning "重启未确认成功（多半首次部署、任务未建）——请按脚本顶部步骤 2 到 .51 上跑一次 deploy-server.ps1。"
} else {
    Write-Host "   服务已重启（见上方 NEW_PID/CREATED）" -ForegroundColor Green
}
Write-Host "`n命令中心地址：http://192.168.100.51:8092/" -ForegroundColor Cyan
