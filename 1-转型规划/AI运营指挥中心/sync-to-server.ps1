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

# —— 销售域实时数据（队列 #53，走脱敏管道 sync_sales_data.py，勿直接 scp 原始 JSON）——
#   sync_sales_data.py：读 SalesMarketing/crm_data/dashboard_data.json → 脱敏高危线索联系方式
#   （Paul 2026-07-20 拍板：泓钦对齐前一律脱敏）→ 写本地 data/sales_dashboard_data.json；
#   再把【已脱敏】文件推到 .51 同源 data/。⚠️ 切勿直接 scp 原始 dashboard_data.json（会带出未脱敏 PII）。
#   日常刷新节奏：挂到 SalesMarketing 的「销售易数据同步」(每天 8:00) 之后，再跑本脚本即可。
Write-Host "刷新销售域数据（脱敏管道 sync_sales_data.py）..." -ForegroundColor Yellow
python "$CC\sync_sales_data.py"
if (($LASTEXITCODE -eq 0) -and (Test-Path "$CC\data\sales_dashboard_data.json")) {
    scp "$CC\data\sales_dashboard_data.json" "${SshAlias}:${Base}/data/sales_dashboard_data.json"
    Write-Host "   销售数据（已脱敏）已推送" -ForegroundColor Green
} else {
    Write-Warning "   sync_sales_data.py 未成功产出 data\sales_dashboard_data.json（源 SalesMarketing 数据可能未同步）——跳过销售数据推送，销售域将回落 2026-06-25 快照。"
}

Write-Host "重启服务（轮询确认端口释放 + 新进程存活）..." -ForegroundColor Yellow
$r = Restart-ZhuopinTask -TaskName "CommandCenterWeb" -CheckMode Port -Port 8092
if (-not $r.Ok) {
    Write-Warning "重启未确认成功（多半首次部署、任务未建）——请按脚本顶部步骤 2 到 .51 上跑一次 deploy-server.ps1。"
} else {
    Write-Host "   服务已重启（见上方 NEW_PID/CREATED）" -ForegroundColor Green
}
Write-Host "`n命令中心地址：http://192.168.100.51:8092/" -ForegroundColor Cyan
