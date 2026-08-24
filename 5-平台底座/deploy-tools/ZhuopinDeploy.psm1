# ================================================================
#  卓品智能 AI 转型项目 · 通用部署到长开服务器工具（2026-07-16 建）
#
#  背景：SC8 保供看板与企微机器人服务各自维护一份手工复制的
#  sync-to-server.ps1，2026-07-15 SC8 那份修了一次重启可靠性 bug
#  （固定等 2 秒 → 轮询确认端口释放/新进程存活），但企微机器人那份
#  没同步到（复制粘贴出来的代码天然不会自动同步）。本模块把两边共用
#  的 SSH/scp 同步 + 重启轮询验证逻辑收拢到一处：以后新场景要部署到
#  服务器，写几行调用本模块的薄封装脚本即可，可靠性修复只需改一处、
#  所有场景自动受益。
#
#  用法（场景侧 sync-to-server.ps1 参考 SC8/aibot-service 两个薄封装范例）：
#    $APP  = $PSScriptRoot
#    $REPO = ... # 按本工程相对仓库根的层级自行推导（各场景目录深度不同）
#    Import-Module (Join-Path $REPO "5-平台底座\deploy-tools\ZhuopinDeploy.psm1") -Force
#    Sync-ZhuopinPlatformAndApp -ServerBase "C:/xxx" -LocalPlatformDir ... -LocalAppDir $APP -AppFiles @(...)
#    $r = Restart-ZhuopinTask -TaskName "XxxService" -CheckMode Port -Port 1234
#    # 或无监听端口的纯出站服务：-CheckMode ProcessMatch -ProcessMatchPattern "run_xxx.py"
#
#  依赖：~/.ssh/config 中的 "supplychain-server" 别名（→192.168.100.51，密钥已配，
#        与 SC8/wecom-aibot-service/supplychain/SalesMarketing 共用同一台服务器同一别名）。
#
#  2026-08-04（队列 #96 CC 半边）：`.51` 侧五份 deploy-server.ps1 此前各自维护一份
#  130-175 行的完整脚本（Python 检查/venv/防火墙/计划任务注册/健康检查靠"照抄上
#  一个"传承，四类坑各自独立踩），本次把可安全共享的部分收拢进本模块——deploy-
#  server.ps1 运行在服务器上，故 `Sync-ZhuopinPlatformAndApp` 新增一步把本模块
#  文件自身也推送到 `$ServerBase/deploy-tools/`，deploy-server.ps1 才能在服务器
#  本地 `Import-Module` 到它（不推送则服务器上根本没有这个文件）。
# ================================================================

$script:ModuleFilePath = $PSCommandPath   # 模块自身路径（供 Publish-ZhuopinDeployToolsModule 推送到服务器用）

function Publish-ZhuopinDeployToolsModule {
    <#
    .SYNOPSIS
      把本模块文件自身推送到服务器 `$ServerBase/deploy-tools/ZhuopinDeploy.psm1`，
      使运行在服务器上的 deploy-server.ps1 能 Import-Module 到同一套函数
      （笔记本侧 sync-to-server.ps1 已在本机 Import-Module，无需再推一份给自己）。
    #>
    param(
        [string]$SshAlias = "supplychain-server",
        [Parameter(Mandatory)][string]$ServerBase
    )
    $winToolsDir = "$ServerBase/deploy-tools".Replace('/', '\')
    ssh $SshAlias "if not exist $winToolsDir mkdir $winToolsDir"
    scp "$script:ModuleFilePath" "${SshAlias}:${ServerBase}/deploy-tools/ZhuopinDeploy.psm1"
    if ($LASTEXITCODE -ne 0) { Write-Warning "部署工具模块推送失败，deploy-server.ps1 在服务器上可能无法 Import-Module" }
}

function Set-ZhuopinGatePasswordEnv {
    <#
    .SYNOPSIS
      幂等写入/追加 `ZP_GATE_PASSWORD` 占位行（四服务共享访问口令门禁，临时止血，
      跨桌任务队列 #10/#160）。已存在则不覆盖已填的值；不存在则生成/追加占位行。
    .PARAMETER EnvFile
      目标 .env 文件绝对路径（各场景各自的 $BASE\.env）。
    #>
    param([Parameter(Mandatory)][string]$EnvFile)
    $comment = "# 四服务共享访问口令门禁（临时止血,跨桌任务队列#10）——8091/8092/8093/8094 四份.env须填同一个值"
    if (-not (Test-Path $EnvFile)) {
        Set-Content -Path $EnvFile -Value "$comment`nZP_GATE_PASSWORD=`n" -Encoding UTF8
        Write-Host "      已生成 $EnvFile（ZP_GATE_PASSWORD 待填，四服务须用同一个值）" -ForegroundColor DarkYellow
    } else {
        $hasGate = (Get-Content $EnvFile) -match '^\s*ZP_GATE_PASSWORD='
        if (-not $hasGate) {
            Add-Content -Path $EnvFile -Value "`n$comment`nZP_GATE_PASSWORD=`n"
            Write-Host "      已在既有 .env 追加 ZP_GATE_PASSWORD（待填，四服务须同一个值）" -ForegroundColor DarkYellow
        } else {
            Write-Host "      .env 已含 ZP_GATE_PASSWORD" -ForegroundColor Green
        }
    }
}

function Register-ZhuopinFirewallRule {
    <#
    .SYNOPSIS
      幂等注册/确保入站防火墙规则放行 LAN 全网段。不限 LocalSubnet——组员笔记本
      常在不同网段（如 WLAN），LocalSubnet 会挡掉跨网段访问；红线针对的是"公网
      开放"，内网 LAN 全网段是这些看板的统一档。
    #>
    param(
        [Parameter(Mandatory)][string]$RuleName,
        [Parameter(Mandatory)][int]$Port
    )
    if (-not (Get-NetFirewallRule -DisplayName $RuleName -ErrorAction SilentlyContinue)) {
        New-NetFirewallRule -DisplayName $RuleName -Direction Inbound -Protocol TCP `
            -LocalPort $Port -Action Allow | Out-Null
        Write-Host "      已放行 $Port（LAN 全网段）" -ForegroundColor Green
    } else {
        Set-NetFirewallRule -DisplayName $RuleName -RemoteAddress Any -Profile Any -Enabled True | Out-Null
        Write-Host "      规则已存在，已确保放行 LAN 全网段" -ForegroundColor Green
    }
}

function Register-ZhuopinScheduledTask {
    <#
    .SYNOPSIS
      幂等注册开机自启计划任务（SYSTEM + AtStartup + RunLevel Highest）——已知四类坑
      收拢于此：① Execute 必须是绝对路径（SYSTEM 账户只认机器级 PATH，不含任何
      用户级 PATH，裸命令名会 0x80070002 找不到文件，调用方须自行 Get-Command 解析
      好再传入，同命令中心 2026-07-23 踩坑记录）；② AllowStartIfOnBatteries（笔记本
      场景需要，服务器场景无影响，统一加不额外增加风险）；③ RestartCount=0 时不设
      重启参数（供 wecom-aibot-service 这类自行实现多级退避、不用计划任务原生单级
      重启的服务）；④ MultipleInstancesIgnoreNew（纯出站单连接服务防双实例互踢）。
    .PARAMETER Execute
      可执行文件绝对路径（不传裸命令名，见上）。
    .PARAMETER RestartCount
      失败重启次数，0=不设（默认 3，1 分钟间隔）。
    .PARAMETER Trigger
      触发器对象。**缺省 AtStartup**（长开服务），传入即用传入的那个（如 SC2 周报
      每周五 20:00 的 `New-ScheduledTaskTrigger -Weekly -DaysOfWeek Friday -At 20:00`）。
      🔴 **刻意做成可选参数而不是另写一个注册函数**：上面那四类坑（SYSTEM 只认机器级
      PATH／电池／重启参数／防双实例）对定时任务同样成立，复制一份逻辑就等于把它们
      重踩一遍——而那正是本模块存在的理由。**缺省值未变，既有调用方行为一行不改。**
    #>
    param(
        [Parameter(Mandatory)][string]$TaskName,
        [Parameter(Mandatory)][string]$Execute,
        [string]$Argument = "",
        [Parameter(Mandatory)][string]$WorkingDirectory,
        [Parameter(Mandatory)][string]$Description,
        [int]$RestartCount = 3,
        [switch]$MultipleInstancesIgnoreNew,
        [switch]$StartWhenAvailable,
        $Trigger = $null,
        [int]$ExecutionTimeLimitHours = 0
    )
    if (Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue) {
        Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false   # 重建以更新路径/设置
    }
    $action = New-ScheduledTaskAction -Execute $Execute -Argument $Argument -WorkingDirectory $WorkingDirectory
    $trigger = if ($null -ne $Trigger) { $Trigger } else { New-ScheduledTaskTrigger -AtStartup }
    $principal = New-ScheduledTaskPrincipal -UserId "SYSTEM" -LogonType ServiceAccount -RunLevel Highest
    # ExecutionTimeLimit 0 ＝ 不限时（长开服务必须如此，否则会被计划任务掐掉）。
    # 🔴 定时任务应传一个有限值：与 -MultipleInstancesIgnoreNew 合用时，一次挂死的
    # 运行会把此后每一次触发都静默 IgnoreNew 掉 —— 表现为「任务还在、再也没跑过」。
    $settingsArgs = @{
        ExecutionTimeLimit = (New-TimeSpan -Hours $ExecutionTimeLimitHours)
        AllowStartIfOnBatteries = $true
    }
    if ($RestartCount -gt 0) {
        $settingsArgs["RestartCount"] = $RestartCount
        $settingsArgs["RestartInterval"] = (New-TimeSpan -Minutes 1)
    }
    if ($MultipleInstancesIgnoreNew) { $settingsArgs["MultipleInstances"] = "IgnoreNew" }
    if ($StartWhenAvailable) { $settingsArgs["StartWhenAvailable"] = $true }
    $settings = New-ScheduledTaskSettingsSet @settingsArgs
    Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger `
        -Principal $principal -Settings $settings -Description $Description | Out-Null
    Write-Host "      已注册 $TaskName" -ForegroundColor Green
}

function Start-ZhuopinWebServiceAndCheckHealth {
    <#
    .SYNOPSIS
      Web 服务专用收尾：清理占用端口的旧实例（防重部署时孤儿进程残留）→ 启动计划
      任务 → 等待 → GET 健康检查端点。非 Web/无监听端口的服务（如
      wecom-aibot-service）不适用，改用本模块既有 `Restart-ZhuopinTask`（-CheckMode
      ProcessMatch）。本函数在**服务器本地**运行（deploy-server.ps1 语境），与
      `Restart-ZhuopinTask`（笔记本侧经 SSH 远程操作）是同一模式在两侧的对应实现。
    #>
    param(
        [Parameter(Mandatory)][string]$TaskName,
        [Parameter(Mandatory)][int]$Port,
        [int]$WaitSeconds = 6,
        [string]$HealthPath = "/api/ping"
    )
    Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue |
        ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }
    Start-ScheduledTask -TaskName $TaskName
    Start-Sleep -Seconds $WaitSeconds
    $ProgressPreference = 'SilentlyContinue'   # 非交互会话(SSH exec)下 Invoke-WebRequest 进度条访问控制台句柄会报错，静默规避
    try {
        $r = Invoke-WebRequest -Uri "http://127.0.0.1:$Port$HealthPath" -TimeoutSec 5 -UseBasicParsing
        Write-Host "      健康检查 OK：$($r.Content)" -ForegroundColor Green
        return $true
    } catch {
        Write-Host "      健康检查未过——多半 .env 凭据未填或 Python 报错，排查：直接前台跑启动脚本看报错。" -ForegroundColor Red
        return $false
    }
}

function Sync-ZhuopinPlatformAndApp {
    <#
    .SYNOPSIS
      推送平台底座 + 场景工程到服务器（不含重启，重启另调 Restart-ZhuopinTask）。
    .PARAMETER ServerBase
      服务器基目录，正斜杠，如 "C:/baoguan"。平台底座落 $ServerBase/zhuopin_platform，
      场景工程落 $ServerBase/app。
    .PARAMETER AppFiles
      要推送进 $ServerBase/app/ 的文件/目录清单（相对 LocalAppDir 的路径），
      如 @("pyproject.toml","sc8","scripts","deploy-server.ps1")。
      刻意白名单而非整目录同步：避免带上 reports/（含真实客户名/审计明细）、
      tests/、.venv 等不该上服务器的内容。
    #>
    param(
        [string]$SshAlias = "supplychain-server",
        [Parameter(Mandatory)][string]$ServerBase,
        [Parameter(Mandatory)][string]$LocalPlatformDir,
        [Parameter(Mandatory)][string]$LocalAppDir,
        [Parameter(Mandatory)][string[]]$AppFiles,
        [string]$AppLabel = "本工程"
    )

    Write-Host "   SSH 别名 : $SshAlias (192.168.100.51)"
    Write-Host "   服务器   : $ServerBase  (平台→/zhuopin_platform, $AppLabel→/app)"
    Write-Host "   本机来源 : $LocalAppDir`n"

    Write-Host "[1/5] 检查 SSH 工具..." -ForegroundColor Yellow
    if (-not (Get-Command scp -ErrorAction SilentlyContinue)) {
        throw "找不到 scp。请装 Windows OpenSSH 客户端：设置→应用→可选功能→OpenSSH 客户端"
    }
    if (-not (Test-Path $LocalPlatformDir)) { throw "未找到平台底座：$LocalPlatformDir" }
    Write-Host "      ssh/scp 可用" -ForegroundColor Green

    Write-Host "[2/5] 确保服务器目录..." -ForegroundColor Yellow
    $winBase = $ServerBase.Replace('/', '\')
    ssh $SshAlias "if not exist $winBase\app mkdir $winBase\app"
    Write-Host "      OK" -ForegroundColor Green

    Write-Host "[3/5] 推送平台底座..." -ForegroundColor Yellow
    scp -r "$LocalPlatformDir" "${SshAlias}:${ServerBase}/"
    if ($LASTEXITCODE -ne 0) { throw "平台底座同步失败" }
    Write-Host "      OK" -ForegroundColor Green

    Write-Host "[4/5] 推送 $AppLabel..." -ForegroundColor Yellow
    foreach ($f in $AppFiles) {
        $src = Join-Path $LocalAppDir $f
        if (Test-Path $src -PathType Container) {
            scp -r "$src" "${SshAlias}:${ServerBase}/app/"
        } else {
            scp "$src" "${SshAlias}:${ServerBase}/app/"
        }
    }
    if ($LASTEXITCODE -ne 0) { Write-Warning "部分文件同步失败，请检查" }
    Write-Host "      OK" -ForegroundColor Green

    Write-Host "[5/5] 推送部署工具模块（deploy-server.ps1 在服务器上复用同一套注册/健康检查函数）..." -ForegroundColor Yellow
    Publish-ZhuopinDeployToolsModule -SshAlias $SshAlias -ServerBase $ServerBase
    Write-Host "      OK" -ForegroundColor Green
}

function Restart-ZhuopinTask {
    <#
    .SYNOPSIS
      重启服务器上的计划任务，轮询确认旧实例真正退出、新实例真正起来
      （2026-07-15 SC8 那次可靠性修复的通用化版本——不再赌固定等待秒数）。
    .PARAMETER CheckMode
      Port：按监听端口找实例（web 服务类，需 -Port）。
      ProcessMatch：按 python.exe 命令行子串找实例（纯出站/无监听端口的服务，需 -ProcessMatchPattern）。
    .OUTPUTS
      Hashtable { Ok = [bool]; Output = 远程脚本逐行输出 }。Ok=$false 时多半是首次
      部署、计划任务还没建，调用方应提示走 deploy-server.ps1。
    #>
    param(
        [string]$SshAlias = "supplychain-server",
        [Parameter(Mandatory)][string]$TaskName,
        [Parameter(Mandatory)][ValidateSet("Port", "ProcessMatch")][string]$CheckMode,
        [int]$Port = 0,
        [string]$ProcessMatchPattern = "",
        [int]$TimeoutSeconds = 15
    )
    if ($CheckMode -eq "Port" -and $Port -le 0) { throw "CheckMode=Port 需要 -Port" }
    if ($CheckMode -eq "ProcessMatch" -and -not $ProcessMatchPattern) { throw "CheckMode=ProcessMatch 需要 -ProcessMatchPattern" }

    $restartScript = @"
`$task = '$TaskName'
`$checkMode = '$CheckMode'
`$port = $Port
`$pattern = '$ProcessMatchPattern'
`$timeoutSec = $TimeoutSeconds

function Get-TargetPids {
    if (`$checkMode -eq 'Port') {
        Get-NetTCPConnection -LocalPort `$port -State Listen -ErrorAction SilentlyContinue |
            Select-Object -ExpandProperty OwningProcess -Unique
    } else {
        Get-CimInstance Win32_Process -Filter "Name='python.exe'" -ErrorAction SilentlyContinue |
            Where-Object { `$_.CommandLine -like "*`$pattern*" } |
            Select-Object -ExpandProperty ProcessId
    }
}

schtasks /End /TN `$task 2>`$null | Out-Null
`$deadline = (Get-Date).AddSeconds(`$timeoutSec)
while ((Get-Date) -lt `$deadline) {
    `$pids = Get-TargetPids
    if (-not `$pids) { break }
    foreach (`$p in `$pids) { Stop-Process -Id `$p -Force -ErrorAction SilentlyContinue }
    Start-Sleep -Milliseconds 500
}
`$remaining = Get-TargetPids
if (`$remaining) { Write-Output "OLD_STILL_BUSY:`$(`$remaining -join ',')"; exit 1 }
Write-Output "OLD_CLEAR"
schtasks /Run /TN `$task | Out-Null
`$deadline2 = (Get-Date).AddSeconds(`$timeoutSec)
`$newPid = `$null
while ((Get-Date) -lt `$deadline2) {
    `$pids = Get-TargetPids
    if (`$pids) { `$newPid = `$pids | Select-Object -First 1; break }
    Start-Sleep -Milliseconds 500
}
if (-not `$newPid) { Write-Output "RESTART_FAILED_NO_INSTANCE"; exit 1 }
`$proc = Get-Process -Id `$newPid -ErrorAction SilentlyContinue
Write-Output "NEW_PID=`$newPid CREATED=`$(`$proc.StartTime.ToString('yyyy-MM-dd HH:mm:ss'))"
"@

    $encoded = [Convert]::ToBase64String([System.Text.Encoding]::Unicode.GetBytes($restartScript))
    $remoteOutput = ssh $SshAlias "powershell -NoProfile -NonInteractive -EncodedCommand $encoded"
    $restartOk = ($LASTEXITCODE -eq 0)
    if ($remoteOutput) { $remoteOutput | ForEach-Object { Write-Host "      $_" -ForegroundColor DarkGray } }
    return @{ Ok = $restartOk; Output = $remoteOutput }
}

Export-ModuleMember -Function Sync-ZhuopinPlatformAndApp, Restart-ZhuopinTask, `
    Publish-ZhuopinDeployToolsModule, Set-ZhuopinGatePasswordEnv, Register-ZhuopinFirewallRule, `
    Register-ZhuopinScheduledTask, Start-ZhuopinWebServiceAndCheckHealth
