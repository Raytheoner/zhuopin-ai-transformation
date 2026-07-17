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
# ================================================================

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

    Write-Host "[1/4] 检查 SSH 工具..." -ForegroundColor Yellow
    if (-not (Get-Command scp -ErrorAction SilentlyContinue)) {
        throw "找不到 scp。请装 Windows OpenSSH 客户端：设置→应用→可选功能→OpenSSH 客户端"
    }
    if (-not (Test-Path $LocalPlatformDir)) { throw "未找到平台底座：$LocalPlatformDir" }
    Write-Host "      ssh/scp 可用" -ForegroundColor Green

    Write-Host "[2/4] 确保服务器目录..." -ForegroundColor Yellow
    $winBase = $ServerBase.Replace('/', '\')
    ssh $SshAlias "if not exist $winBase\app mkdir $winBase\app"
    Write-Host "      OK" -ForegroundColor Green

    Write-Host "[3/4] 推送平台底座..." -ForegroundColor Yellow
    scp -r "$LocalPlatformDir" "${SshAlias}:${ServerBase}/"
    if ($LASTEXITCODE -ne 0) { throw "平台底座同步失败" }
    Write-Host "      OK" -ForegroundColor Green

    Write-Host "[4/4] 推送 $AppLabel..." -ForegroundColor Yellow
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

Export-ModuleMember -Function Sync-ZhuopinPlatformAndApp, Restart-ZhuopinTask
