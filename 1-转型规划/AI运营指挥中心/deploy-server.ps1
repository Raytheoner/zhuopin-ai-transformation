# ================================================================
#  AI 运营指挥中心 · 服务器首次部署（在 192.168.100.51 上以【管理员】PowerShell 跑一次）
#  作用：注册计划任务 CommandCenterWeb —— 登录即启动 serve.py、异常自动重启、可常驻。
#        （对齐 BaoguanWebServer / ZhuopinAibotDevListener 惯例）
#  前置：C:\command-center\ 下已有 index.html + serve.py（由笔记本 sync-to-server.ps1 推送）。
#  之后日常更新只需在笔记本跑 sync-to-server.ps1（推文件 + 重启），无需再跑本脚本。
# ================================================================
param(
  [string]$Base       = "C:\command-center",
  [string]$PythonExe  = "python",          # python 不在 PATH 时改绝对路径，或复用 C:\baoguan\.venv\Scripts\python.exe
  [int]$Port          = 8092,
  [string]$TaskName   = "CommandCenterWeb"
)
$ErrorActionPreference = "Stop"

if (-not (Test-Path "$Base\serve.py"))   { throw "缺 $Base\serve.py —— 先在笔记本跑 sync-to-server.ps1 推送" }
if (-not (Test-Path "$Base\index.html")) { throw "缺 $Base\index.html（命令中心页面）" }

Write-Host "注册计划任务 $TaskName（端口 $Port，登录启动 + 失败重启）..." -ForegroundColor Yellow
$action   = New-ScheduledTaskAction  -Execute $PythonExe -Argument "`"$Base\serve.py`" $Port" -WorkingDirectory $Base
$trigger  = New-ScheduledTaskTrigger -AtLogOn
$settings = New-ScheduledTaskSettingsSet -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1) `
                                         -MultipleInstances IgnoreNew -StartWhenAvailable -AllowStartIfOnBatteries
Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -Settings $settings -Force -RunLevel Highest | Out-Null
schtasks /Run /TN $TaskName | Out-Null
Start-Sleep -Seconds 2

Write-Host "冒烟自检..." -ForegroundColor Yellow
try {
  $code = (Invoke-WebRequest "http://127.0.0.1:$Port/" -UseBasicParsing -TimeoutSec 6).StatusCode
  Write-Host "  首页 HTTP $code" -ForegroundColor Green
} catch { Write-Warning "  本机冒烟失败：$_（检查 python 是否在 PATH / 端口 $Port 是否被占）" }

Write-Host "`n完成。命令中心地址：http://192.168.100.51:$Port/" -ForegroundColor Cyan
Write-Host "回滚：schtasks /End /TN $TaskName（停服务）；schtasks /Delete /TN $TaskName /F（注销任务）" -ForegroundColor DarkGray
