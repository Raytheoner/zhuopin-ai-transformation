# ================================================================
#  AI 运营指挥中心 · 服务器首次部署（在 192.168.100.51 上以【管理员】PowerShell 跑一次）
#  作用：注册计划任务 CommandCenterWeb —— 开机启动 serve.py、异常自动重启、可常驻。
#        （对齐 BaoguanWebServer / QdBWebServer 惯例：SYSTEM + AtStartup，见下方 2026-07-23 修复说明）
#  前置：C:\command-center\ 下已有 index.html + serve.py（由笔记本 sync-to-server.ps1 推送）。
#  之后日常更新只需在笔记本跑 sync-to-server.ps1（推文件 + 重启），无需再跑本脚本。
#
#  2026-07-23 可靠性修复：原用 AtLogOn 触发器 + 默认交互式登录（InteractiveToken）注册，
#  依赖 Administrator 保持"活跃"RDP 会话。QD-B 极简版发布收口时，对本任务做一次常规重启
#  （`schtasks /End` + `/Run`）触发了真实故障——Administrator 会话彼时处于"已断开"
#  （断开连接≠已注销，原进程能在断开会话里继续跑，但 Task Scheduler 无法向断开的交互式
#  会话里启动*新*进程，`schtasks /Run` 报错 0x80070002，服务中断至下次有人真登录 RDP）。
#  改为 SYSTEM + AtStartup（同 BaoguanWebServer/QdBWebServer），不依赖任何交互式会话，
#  `schtasks /End`+`/Run` 常规重启从此可靠。
#
#  同批修复第二处：SYSTEM 账户只认机器级 PATH（`C:\Windows\system32` 等），不含
#  Administrator 用户级 PATH（python.exe 装在 `C:\Users\Administrator\AppData\Local\
#  Programs\Python\Python314\`）——若仍传裸命令 "python"，SYSTEM 触发时 0x80070002
#  「找不到文件」。改为注册前用 `Get-Command` 解析出绝对路径并**烘焙进任务定义**，
#  之后 SYSTEM 触发不再依赖任何账户的 PATH。
# ================================================================
param(
  [string]$Base       = "C:\command-center",
  [string]$PythonExe  = "python",          # 裸命令名/绝对路径均可，下面会解析成绝对路径再注册
  [int]$Port          = 8092,
  [string]$TaskName   = "CommandCenterWeb"
)
$ErrorActionPreference = "Stop"

if (-not (Test-Path "$Base\serve.py"))   { throw "缺 $Base\serve.py —— 先在笔记本跑 sync-to-server.ps1 推送" }
if (-not (Test-Path "$Base\index.html")) { throw "缺 $Base\index.html（命令中心页面）" }

# 访问口令 .env（ZP_GATE_PASSWORD，四服务共享，临时止血，跨桌任务队列 #10）
Write-Host "检查访问口令 .env..." -ForegroundColor Yellow
$envFile = Join-Path $Base ".env"
if (-not (Test-Path $envFile)) {
    Set-Content -Path $envFile -Value "# 四服务共享访问口令门禁（临时止血,跨桌任务队列#10）——8091/8092/8093/8094 四份.env须填同一个值`nZP_GATE_PASSWORD=`n" -Encoding UTF8
    Write-Host "  已生成 $envFile（ZP_GATE_PASSWORD 待填，四服务须用同一个值）" -ForegroundColor DarkYellow
} else {
    $hasGate = (Get-Content $envFile) -match '^\s*ZP_GATE_PASSWORD='
    if (-not $hasGate) {
        Add-Content -Path $envFile -Value "`n# 四服务共享访问口令门禁（临时止血,跨桌任务队列#10）——四份.env须填同一个值`nZP_GATE_PASSWORD=`n"
        Write-Host "  已在既有 .env 追加 ZP_GATE_PASSWORD（待填，四服务须同一个值）" -ForegroundColor DarkYellow
    } else {
        Write-Host "  .env 已含 ZP_GATE_PASSWORD" -ForegroundColor Green
    }
}

# 解析绝对路径（本脚本以管理员交互式跑，"python" 在此处能正确解析；SYSTEM 触发时不会再重新解析）
$resolvedPython = (Get-Command $PythonExe -ErrorAction SilentlyContinue).Source
if (-not $resolvedPython) { throw "找不到 Python 可执行文件：$PythonExe（装 3.11+ 并 Add to PATH，或直接传绝对路径）" }
Write-Host "Python 解析为：$resolvedPython" -ForegroundColor DarkGray

Write-Host "注册计划任务 $TaskName（端口 $Port，开机启动 + 失败重启，SYSTEM 账户不依赖交互式会话）..." -ForegroundColor Yellow
if (Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue) {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false   # 重建以切换到 SYSTEM+AtStartup
}
$action    = New-ScheduledTaskAction  -Execute $resolvedPython -Argument "`"$Base\serve.py`" $Port" -WorkingDirectory $Base
$trigger   = New-ScheduledTaskTrigger -AtStartup
$principal = New-ScheduledTaskPrincipal -UserId "SYSTEM" -LogonType ServiceAccount -RunLevel Highest
$settings  = New-ScheduledTaskSettingsSet -ExecutionTimeLimit (New-TimeSpan -Hours 0) `
                 -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1) `
                 -MultipleInstances IgnoreNew -StartWhenAvailable -AllowStartIfOnBatteries
Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger `
    -Principal $principal -Settings $settings -Description "AI 运营指挥中心 Web 服务（端口 $Port）" | Out-Null

# 防火墙放行（内网 LAN 全网段，与 Baoguan-WebServer-8091 一致）——
# 不限 LocalSubnet：组员笔记本常在不同网段（如 WLAN），LocalSubnet 会挡掉跨网段访问。
Write-Host "防火墙（入站 TCP $Port，LAN 全网段）..." -ForegroundColor Yellow
$ruleName = "CommandCenter-WebServer-$Port"
if (-not (Get-NetFirewallRule -DisplayName $ruleName -ErrorAction SilentlyContinue)) {
    New-NetFirewallRule -DisplayName $ruleName -Direction Inbound -Protocol TCP `
        -LocalPort $Port -Action Allow | Out-Null
    Write-Host "  已放行 $Port（LAN 全网段）" -ForegroundColor Green
} else {
    Set-NetFirewallRule -DisplayName $ruleName -RemoteAddress Any -Profile Any -Enabled True | Out-Null
    Write-Host "  规则已存在，已确保放行 LAN 全网段" -ForegroundColor Green
}

schtasks /Run /TN $TaskName | Out-Null
Start-Sleep -Seconds 2

Write-Host "冒烟自检..." -ForegroundColor Yellow
$ProgressPreference = 'SilentlyContinue'   # 非交互会话（如 SSH exec）下 Invoke-WebRequest 进度条访问控制台句柄会报 0x5，静默进度条规避
try {
  $code = (Invoke-WebRequest "http://127.0.0.1:$Port/" -UseBasicParsing -TimeoutSec 6).StatusCode
  Write-Host "  首页 HTTP $code" -ForegroundColor Green
} catch { Write-Warning "  本机冒烟失败：$_（检查 python 是否在 PATH / 端口 $Port 是否被占）" }

Write-Host "`n完成。命令中心地址：http://192.168.100.51:$Port/" -ForegroundColor Cyan
Write-Host "回滚：schtasks /End /TN $TaskName（停服务）；schtasks /Delete /TN $TaskName /F（注销任务）" -ForegroundColor DarkGray
