# ================================================================
#  工具-注册轮询守计划任务.ps1
#  用途：把 工具-轮询守.ps1 注册为 Windows 计划任务 ZhuopinPollGuard（每 15 分钟一轮），
#        作为 Cowork 桌面端 `poll-opener-batch` 定时任务的替代品。
#        承接队列 §一 `#575` 甲（`OP-0913-Q`，批 `B-0913_轮询守`）。
#
#  🔴 本脚本只**建**替代品，不停用、不改动现有 Cowork 桌面端任务——那在 Shao Peishen 本机、归他手动
#     （看护件 §二）。两者短期并存是安全的：探针有「已报」状态文件，谁先跑谁推、后跑者得 [NO-SIGNAL]；
#     巡检本身幂等（登记册销行／worktree remove 二次跑无事可做）。并存期间的代价只是两份留痕，
#     待他确认本任务的留痕连续若干轮正常后，再手动停 Cowork 那条。
#
#  沿用 工具-注册落库sweep计划任务.ps1 的全部范式（成因原文在那里，此处只留指针）：
#    · 当前账户 + LogonType Interactive（#648 用户批准：仅账户已登录时运行；S4U Session 0 的 Codex sandbox 管道超时）；
#    · Action 指主工作区稳定路径，绝不指 .codex\worktrees\<name>（#49/#79）；
#    · 绝对路径烘焙进生成的包装脚本 run-poll-guard.ps1（S4U 触发时 PATH ≠ 交互式登录 shell；
#      python 是用户级安装、codex.exe 在 ~\.local\bin、pwsh 在 WindowsApps——三个都不在 SYSTEM/S4U 默认 PATH）；
#    · Execute=wscript.exe + run-poll-guard-hidden.vbs 拉起隐藏窗口（#231：每 15 分钟闪一次控制台窗口不可接受）；
#    · 提权自检守卫（#412 M1）：S4U 任务的 Register/Unregister 需 SeTcbPrivilege，非提权跑＝「以为刷新了、其实没刷新」。
#  🔴 起 轮询守 一律用 pwsh 7（看护件顶部：巡检脚本本身就要 `pwsh -NoProfile -File`，Windows PowerShell 5.1 跑不动它）。
#  🔴 解析出的 pwsh/python/git/codex/node 一律过 Assert-RealExecutable（OP-0913-S 缺陷一，批 B-0913_轮询守实机三修）：
#     0 字节／ReparsePoint 的应用执行别名 ⇒ 报错退出、不生成包装、不注册。-PwshExe 等五个参数只为单测指向桩而设。
#
#  用法（本机管理员 PowerShell，在主工作区目录下执行一次；幂等——先注销旧任务再重建）：
#    pwsh -NoProfile -ExecutionPolicy Bypass -File "0-学习与工具\工具-注册轮询守计划任务.ps1"
#    pwsh -NoProfile -ExecutionPolicy Bypass -File "0-学习与工具\工具-注册轮询守计划任务.ps1" -IntervalMinutes 15
#    pwsh -NoProfile -ExecutionPolicy Bypass -File "0-学习与工具\工具-注册轮询守计划任务.ps1" -Unregister   # 回滚
#    pwsh -NoProfile -ExecutionPolicy Bypass -File "0-学习与工具\工具-注册轮询守计划任务.ps1" -WhatIf       # 只打印、不注册（不要求提权）
#
#  验证（「空跑也写日志」标准，同 sweep）：Start-ScheduledTask 后 reports\poll-guard\poll-guard-<今天>.jsonl 必须多一行；
#        没多一行＝任务没有真正执行，回查 Principal/权限，不能只看 LastTaskResult=0：
#    Start-ScheduledTask -TaskName ZhuopinPollGuard
#    Get-ScheduledTaskInfo -TaskName ZhuopinPollGuard
#    Get-Content "C:\Dev\zhuopin-ai\reports\poll-guard\poll-guard-$(Get-Date -Format yyyyMMdd).jsonl" -Tail 3
# ================================================================
[CmdletBinding()]
param(
    [string]$Repo = 'C:\Dev\zhuopin-ai',   # 只为 -WhatIf 在泳道 worktree 里自测而设；生产一律主工作区
    [int]$IntervalMinutes = 15,
    [string]$Model = '',        # 传给 轮询守 -Model（留空＝codex CLI 默认）
    # 下列五个只为单测指向桩／伪造件而设（配合 -WhatIf），留空＝自动解析；生产一律留空
    [string]$PwshExe = '',
    [string]$PythonExe = '',
    [string]$GitExe = '',
    [string]$CodexExe = '',
    [string]$NodeExe = '',
    [switch]$ConsumerEnabled,
    [switch]$Unregister,
    [switch]$WhatIf
)
$ErrorActionPreference = "Stop"

$REPO         = $Repo
$GUARD_SCRIPT = Join-Path $REPO "0-学习与工具\工具-轮询守.ps1"
$WRAPPER      = Join-Path $REPO "0-学习与工具\run-poll-guard.ps1"
$VBS_LAUNCHER = Join-Path $REPO "0-学习与工具\run-poll-guard-hidden.vbs"
$TASK         = "ZhuopinPollGuard"

# ── 提权自检守卫（#412 M1；-WhatIf 只打印不动任务，免提权） ──
$__isAdmin = ([Security.Principal.WindowsPrincipal] `
    [Security.Principal.WindowsIdentity]::GetCurrent()
).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $__isAdmin -and -not $WhatIf) {
    Write-Error ("本脚本要注册/修改计划任务，需要管理员 PowerShell。" +
        "当前会话非提权，已在改动任何任务之前退出——请在管理员 PowerShell 里重跑本脚本（或加 -WhatIf 只看不动）。")
    exit 1
}
if (-not $WhatIf) { Write-Host "[守卫] 提权自检通过（管理员 PowerShell）。" -ForegroundColor DarkGray }

if ($Unregister) {
    if ($WhatIf) { Write-Host "[WhatIf] 将注销计划任务 $TASK"; exit 0 }
    if (Get-ScheduledTask -TaskName $TASK -ErrorAction SilentlyContinue) {
        Unregister-ScheduledTask -TaskName $TASK -Confirm:$false
        Write-Host "已注销 $TASK。" -ForegroundColor Green
    } else { Write-Host "$TASK 本就不存在，无事可做。" }
    exit 0
}

Write-Host "`n== 注册轮询守计划任务 ==" -ForegroundColor Cyan
Write-Host "   主工作区 : $REPO"
Write-Host "   守卫脚本 : $GUARD_SCRIPT"
Write-Host "   周期     : 开机启动 + 此后每 $IntervalMinutes 分钟一次`n"

foreach ($p in @($GUARD_SCRIPT, $VBS_LAUNCHER)) {
    if (-not (Test-Path $p)) { Write-Error "未找到 $p —— 请确认主工作区已同步到含本文件的 commit。"; exit 1 }
}
if (-not $WhatIf -and -not (Test-Path (Join-Path $REPO ".git") -PathType Container)) {   # -WhatIf 允许在泳道 worktree 里自测
    Write-Error "$REPO\.git 不是目录（当前路径可能是某个 linked worktree，而非主工作区）——已中止。"; exit 1
}

# ── 1. 解析绝对路径 + 运行身份 ──
Write-Host "[1/3] 解析 pwsh / python / git / codex 绝对路径 + 运行身份..." -ForegroundColor Yellow
function Assert-RealExecutable {
    <# 🔴 fail-loud 校验（OP-0913-S 缺陷一，批 B-0913_轮询守实机三修）：解析出的可执行文件若 Length -eq 0 或带 ReparsePoint
       属性 ⇒ 它是 App Execution Alias（%LOCALAPPDATA%\Microsoft\WindowsApps\*.exe 那种 0 字节重解析点），不是真二进制。
       S4U 无交互式登录上下文、解析不了该别名：第一轮实机验收 wscript 1 秒返回 0（手跑 94.8 s）——整条链路根本没起来，
       而对照组 ZhuopinCommitSweep（同 Principal）一直跑得好，只因它调的是 …\Python314\python.exe 这个真实二进制。
       校验不过 ⇒ 报错退出、不生成包装、不注册。只把解析换个写法而不加校验＝换台机器再踩一遍。 #>
    param([Parameter(Mandatory)][string]$Name, [Parameter(Mandatory)][string]$Path)
    $fi = Get-Item -LiteralPath $Path -Force -ErrorAction SilentlyContinue
    if (-not $fi -or $fi.PSIsContainer) {
        Write-Error "$Name 解析到 $Path，但它不存在或不是文件——已中止，不生成包装、不注册。"; exit 1
    }
    $isReparse = (($fi.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0)
    if ($fi.Length -eq 0 -or $isReparse) {
        Write-Error ("$Name 解析到 $Path（Length=$($fi.Length)，Attributes=$($fi.Attributes)）——这是 0 字节／ReparsePoint 的应用执行别名，" +
            "不是可执行文件，S4U 计划任务解析不了它（缺陷一）。已中止，不生成包装、不注册。" +
            "请改用真身路径重跑（如 -${Name}Exe `"<真实 .exe 全路径>`"），或把真身目录放到 PATH 里 WindowsApps 之前。")
        exit 1
    }
}
function Resolve-Exe([string]$name, [string]$override = '') {
    if ($override) { $src = $override }
    else {
        $c = Get-Command $name -ErrorAction SilentlyContinue
        if (-not $c) { Write-Error "未找到 $name，请确认已安装并加入当前用户 PATH。"; exit 1 }
        $src = $c.Source
    }
    Assert-RealExecutable -Name $name -Path $src
    return $src
}
# 🔴 pwsh：本机是 Store 安装，Get-Command 常解析到 %LOCALAPPDATA%\Microsoft\WindowsApps\pwsh.exe 这个别名（上文校验会拒掉），
#    真身在 C:\Program Files\WindowsApps\Microsoft.PowerShell_<版本>_…\pwsh.exe。本脚本本就要求在 pwsh 7 下跑，
#    当前进程的 Path 就是真身（实测返回的正是该路径），优先取它。代价：版本号烘进路径，Store 升级一次就失效——
#    包装脚本起手先校验 pwsh 存在，不存在则留痕＋exit 9（配合 VBS 退出码透传，任务面板会红），届时重跑本脚本即可
#    （注册动作本就归人）。此前「优先用别名、升级不变」的取舍正是缺陷一的根因，已撤。
if (-not $PwshExe -and $PSVersionTable.PSEdition -eq 'Core') {
    $selfPath = (Get-Process -Id $PID).Path
    if ($selfPath -and (Split-Path $selfPath -Leaf) -ieq 'pwsh.exe') { $PwshExe = $selfPath }
}
$pwshExe   = Resolve-Exe pwsh   $PwshExe
$pyExe     = Resolve-Exe python $PythonExe
$gitExe    = Resolve-Exe git    $GitExe
if (-not $CodexExe) {
    $runtimeFile = Join-Path $REPO '.codex/runtime.local.json'
    if (Test-Path -LiteralPath $runtimeFile) { $CodexExe = (Get-Content -LiteralPath $runtimeFile -Raw | ConvertFrom-Json).codex_executable }
}
$codexExe = Resolve-Exe codex $CodexExe
$gitDir    = Split-Path $gitExe -Parent
$nodeDir   = ''
$nodeSrc   = $NodeExe
if (-not $nodeSrc) { $nodeCmd = Get-Command node -ErrorAction SilentlyContinue; if ($nodeCmd) { $nodeSrc = $nodeCmd.Source } }
if ($nodeSrc) { Assert-RealExecutable -Name node -Path $nodeSrc; $nodeDir = Split-Path $nodeSrc -Parent }
$currentUser = (whoami).Trim()
Write-Host "      pwsh    : $pwshExe" -ForegroundColor Green
Write-Host "      python  : $pyExe" -ForegroundColor Green
Write-Host "      git     : $gitDir" -ForegroundColor Green
Write-Host "      codex  : $codexExe" -ForegroundColor Green
Write-Host "      node    : $(if ($nodeDir) { $nodeDir } else { '（未找到，codex.exe 为原生二进制时不需要）' })" -ForegroundColor Green
Write-Host "      运行身份: $currentUser" -ForegroundColor Green

# ── 2. 生成启动包装脚本（绝对路径烘焙；本文件在 .gitignore 里，机器专属） ──
Write-Host "[2/3] 生成 run-poll-guard.ps1..." -ForegroundColor Yellow
$consumerArg = if ($ConsumerEnabled) { ' -ConsumerEnabled' } else { '' }
$modelArg = if ($Model) { " -Model `"$Model`"" } else { '' }
$pathPrefix = "$gitDir;" + $(if ($nodeDir) { "$nodeDir;" } else { '' }) + (Split-Path $codexExe -Parent) + ";" + (Split-Path $pyExe -Parent)
$wrapperContent = @"
# 轮询守启动包装（由 工具-注册轮询守计划任务.ps1 生成，勿手改——重跑注册脚本会覆盖此文件；已在 .gitignore）。
# S4U 触发时的 PATH 未必等同交互式登录 shell，此处把 git/node/codex/python 的绝对目录显式烘焙进来。
`$env:PATH = "$pathPrefix;`$env:PATH"
# 每次启动按本机runtime解析，升级不永久烘焙版本路径；配置缺失即停止。
`$runtimeFile = Join-Path "$REPO" '.codex/runtime.local.json'
if (-not (Test-Path -LiteralPath `$runtimeFile)) { exit 9 }
`$runtime = Get-Content -LiteralPath `$runtimeFile -Raw | ConvertFrom-Json
`$env:ZHUOPIN_CODEX_EXECUTABLE = `$runtime.codex_executable
if (-not (Test-Path -LiteralPath `$env:ZHUOPIN_CODEX_EXECUTABLE)) { exit 9 }

# 🔴 pwsh 真身路径含 Store 版本号，升级后会消失（OP-0913-S 缺陷一的取舍）：不存在就留一行痕＋exit 9，别静默返回 0。
if (-not (Test-Path -LiteralPath "$pwshExe" -PathType Leaf)) {
    `$d = "$REPO\reports\poll-guard"; New-Item -ItemType Directory -Force -Path `$d | Out-Null
    `$ts = Get-Date
    Add-Content -Path (Join-Path `$d ("poll-guard-" + `$ts.ToString('yyyyMMdd') + ".jsonl")) -Encoding UTF8 -Value ('{"ts":"' + `$ts.ToString('o') + '","round":"' + `$ts.ToString('yyyyMMdd-HHmmss') + '","wrapper_error":"pwsh 不存在（Store 升级后路径失效？请重跑 工具-注册轮询守计划任务.ps1）：' + "$pwshExe".Replace('\', '\\') + '","woke":false,"total_ms":0}')
    exit 9
}
& "$pwshExe" -NoProfile -NonInteractive -ExecutionPolicy Bypass -File "$GUARD_SCRIPT" -Repo "$REPO" -PythonExe "$pyExe" -PwshExe "$pwshExe"$modelArg$consumerArg
`$rc = `$LASTEXITCODE
# 🔴 #575：原生命令**压根没启动**时 `$LASTEXITCODE 为 `$null，exit `$null 就是 exit 0——
#    VBS 那一层刚补上的退出码透传被这一层吃掉。实测：09-14～09-16 一天 ~96 轮里
#    只有 2 轮真跑，其余轮轮 1 秒、LastTaskResult=0、零留痕，面板上全是「成功」。
#    取不到退出码即当失败：写一行痕并 exit 8。**只会报成功的守卫等于没有守卫。**
if (`$null -eq `$rc) {
    `$d = "$REPO\reports\poll-guard"; New-Item -ItemType Directory -Force -Path `$d | Out-Null
    `$ts = Get-Date
    Add-Content -Path (Join-Path `$d ("poll-guard-" + `$ts.ToString('yyyyMMdd') + ".jsonl")) -Encoding UTF8 -Value ('{"ts":"' + `$ts.ToString('o') + '","round":"wrapper-nostart","skipped":"pwsh-not-started","woke":false,"total_ms":0}')
    exit 8
}
exit `$rc
"@
if ($WhatIf) {
    Write-Host "[WhatIf] 将写入 $WRAPPER：" -ForegroundColor DarkGray
    Write-Host $wrapperContent
} else {
    Set-Content -Path $WRAPPER -Value $wrapperContent -Encoding utf8BOM   # 跳板是 powershell 5.1，无 BOM 会把中文注释按 ANSI 读
    Write-Host "      已生成 $WRAPPER" -ForegroundColor Green
}

# ── 3. 注册计划任务（当前账户 Interactive + AtStartup + 每 N 分钟；上一轮未完则忽略新实例） ──
Write-Host "[3/3] 注册计划任务 $TASK..." -ForegroundColor Yellow
$action = New-ScheduledTaskAction -Execute "wscript.exe" -Argument "`"$VBS_LAUNCHER`"" -WorkingDirectory $REPO
$triggerStartup = New-ScheduledTaskTrigger -AtStartup
# [TimeSpan]::MaxValue 会被任务计划程序服务拒绝（sweep 注册脚本 2026-07-24 实测），改 10 年＝本项目尺度的「永久」。
$triggerRepeat = New-ScheduledTaskTrigger -Once -At (Get-Date) `
    -RepetitionInterval (New-TimeSpan -Minutes $IntervalMinutes) `
    -RepetitionDuration (New-TimeSpan -Days 3650)
$principal = New-ScheduledTaskPrincipal -UserId $currentUser -LogonType Interactive
# ExecutionTimeLimit 40 分钟 ＝ 探针 2 + 巡检 15 + 模型 20 三个上限之和再留余量；MultipleInstances IgnoreNew 与
# 脚本内的 Global\ZhuopinPollGuard 互斥体双保险（前者省一次进程起动，后者管手工与任务并发）。
$settings = New-ScheduledTaskSettingsSet -ExecutionTimeLimit (New-TimeSpan -Minutes 40) `
    -MultipleInstances IgnoreNew -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable
$description = ("轮询守（队列 #575 甲／OP-0913-Q）：每 $IntervalMinutes 分钟跑 无头棒收工探针 ＋ 待合分支巡检，" +
                "只在有信号时才唤 codex exec；每轮无条件留一行痕到 reports\poll-guard\。替代 Cowork 桌面端 poll-opener-batch。")

if ($WhatIf) {
    Write-Host "[WhatIf] 将注册 $TASK：Execute=wscript.exe `"$VBS_LAUNCHER`"；触发＝开机 + 每 $IntervalMinutes 分钟；身份＝$currentUser/Interactive（仅已登录时运行）；上限 40 分钟；IgnoreNew。"
    exit 0
}
if (Get-ScheduledTask -TaskName $TASK -ErrorAction SilentlyContinue) {
    Unregister-ScheduledTask -TaskName $TASK -Confirm:$false   # 重建以更新路径
}
Register-ScheduledTask -TaskName $TASK `
    -Action $action -Trigger @($triggerStartup, $triggerRepeat) `
    -Principal $principal -Settings $settings -Description $description | Out-Null
Write-Host "      已注册（开机启动 + 此后每 $IntervalMinutes 分钟一次）" -ForegroundColor Green

Write-Host "`n注册完成。" -ForegroundColor Green
Write-Host "   立即手动跑一次（验证）: Start-ScheduledTask -TaskName $TASK" -ForegroundColor DarkGray
Write-Host "   查看上次运行结果      : Get-ScheduledTaskInfo -TaskName $TASK" -ForegroundColor DarkGray
Write-Host "   留痕（每轮一行）      : $REPO\reports\poll-guard\poll-guard-<yyyyMMdd>.jsonl" -ForegroundColor DarkGray
Write-Host "   回滚                  : pwsh -File `"$PSCommandPath`" -Unregister" -ForegroundColor DarkGray
