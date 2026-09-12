#Requires -Version 5.1
<#
.SYNOPSIS
    常驻执行体 worktree 对齐与重启验活（队列 §一 #338 子项 B，OP-0823-G）。

.DESCRIPTION
    把 `§四 #68`（2026-08-19 实操）踩出来的三个坑固化成流程。

    🔴 **本脚本是「重启」那一半的唯一实现，人与机器都走它**（#338 改版明写
    「勿另写一套」）。两级分工是：
      · **ff 由 sweep 每轮自动做** —— 落后是持续过程（约 70 提交/天），
        一次性动作治不了它，无论触发人是谁；
      · **重启按需** —— 只在本轮 ff 真的动了常驻服务代码路径时才需要，
        判据复用 #87 ⑶⑷ 那套白名单；且缺省走人工确认（开关
        `CARRIER_AUTO_RESTART_ENABLED` 默认 OFF，首月只 ff、攒够样本再放开）。
    ⇒ **日常最常用的是 `-RestartOnly`**：ff 已由 sweep 做掉，人工要补的
    只是重启验活那一步。

    🔴 本脚本存在的理由，是一件比"落后了"更要紧的事：
    `#68` 已于 2026-08-19 完整对齐过一次（五项验收全过），**四天后又落后了
    305 个提交**。⇒ 问题从来不是"那次没做好"，是"**对齐是一次性动作，而落后
    是持续过程**"。检测由 sweep 每轮做；本脚本负责让"检测到之后怎么办"不再
    依赖某个人是否读到过队列里那段叙述。

    九关（任一关不过即停，退出码见 .NOTES）：
      1 身份校验    —— `.git` 条目 ＋ 注册项；**不看 `git -C` 的输出**
      2 可 ff 校验  —— 不满足即停，绝不 revert／挑拣；**落后为 0 时再判一道
                       进程新鲜度**（2b，见下），否则本关在断口上报绿
      3 固化备份    —— 未跟踪 ＋ ignored 全量复制到**仓库外**
      4 停服        —— 整条进程链，**先父后子**，复查零残留
      5 ff          —— `merge --ff-only`，校验落后归零
      6 启动        —— **只启「停服前在跑的」**，绝不计划外触发一次性日任务
      7 验重启      —— 比对进程链 CreationTime **真的变了**
      8 验活        —— 心跳时间戳**真的刷新**（不是看服务在不在）
      9 摘要

    🔴 **2b 进程新鲜度（队列 §一 #570，OP-0913-G）**：第 2 关原来只算落后数
    `rev-list --count <targetHead>..master`，为 0 即报「已对齐，无需处置」
    ——**它只看 git、不看进程**。2026-09-12 实证：`#312` 的代码 18:22–18:44
    ff 进 master，常驻进程却起于前一天 21:22，**跑了 21 小时旧判据**，而
    `-DryRun` 照报「已对齐（落后 0）」；同日又一例：listener 起于 13:10:20Z，
    `#556` 修复 13:11:10Z 落 master，**晚 50 秒**，工具照报绿。两把尺子量的
    不是一件事，读数好看反而掩盖断口。
    ⇒ 落后为 0 时，再把**常驻进程 `CreationDate`** 与**代码落库时刻**比一次：
      · 代码落库时刻 ＝ max(`git log -1 --format=%cI <targetHead>` 的提交时刻，
        该 worktree `HEAD` 最近一次 reflog 移动时刻)。取后者是因为提交时刻
        只是下界——进程若起于「提交之后、ff 之前」，按提交时刻会误判新鲜。
      · 任一常驻进程早于代码落库时刻 ⇒ 判**「代码已对齐、执行体过期」**。
    ⚠️ **判过期之后怎么办，不一刀切**（#570 末句约束）：
      · `-DryRun`             ⇒ 只报告，退出码 **18**（不再是 0——量具不得报绿）；
      · 实跑且 `.env` 里 `CARRIER_AUTO_RESTART_ENABLED` 为 ON
                             ⇒ 走既有 `-RestartOnly` 路径（停服→启动→验重启→验活）；
      · 实跑且开关 OFF／缺失  ⇒ 只告警，退出码 18，打印处置命令；人工确认后
                             自己带 `-RestartOnly` 再跑一次。
    开关与 sweep `_carrier_auto_restart_enabled` 同一把、同一解析规则（读不到
    即 OFF，fail-safe）——**不新造第二套开关**。

.PARAMETER WorktreeName
    执行体 worktree 目录名，如 `wecom-service-home`。

.PARAMETER RepoRoot
    仓库根；默认由 `git rev-parse --git-common-dir` 解出主工作区（而非本脚本
    所在的那份 checkout —— 本脚本可能正躺在某个 worktree 副本里）。

.PARAMETER BackupDir
    备份目录，**必须在仓库之外**；默认 `$env:TEMP\carrier-realign-<时间戳>`。

.PARAMETER RestartOnly
    只重启验活，跳过 ff 相关的三关（可 ff 校验／固化备份／ff）。**这是 #338
    改版后的常规用法。**

.PARAMETER DryRun
    干跑：只跑判定并打印将要做什么，不停服、不 ff、不启动。🔴 判到「执行体
    过期」时退出码为 18 而非 0（见 2b）。

.EXAMPLE
    powershell -NoProfile -File "0-学习与工具\工具-执行体对齐重启.ps1" -WorktreeName wecom-service-home -DryRun

.EXAMPLE
    powershell -NoProfile -File "0-学习与工具\工具-执行体对齐重启.ps1" -WorktreeName wecom-service-home -RestartOnly

.NOTES
    退出码（🔴 由本脚本自身 `exit` 给出，调用方读 `$LASTEXITCODE`）：
      0 全关通过 ／ 10 身份 ／ 11 不可 ff ／ 12 备份 ／ 13 停服残留
      14 ff 失败 ／ 15 重启未生效 ／ 16 验活失败 ／ 17 无可重启的常驻任务
      18 执行体过期（代码已对齐但常驻进程早于代码落库时刻；仅报告、未重启）
      20 参数或环境错误

    🔴 **绝不要**用 `cmd /c ... & echo %ERRORLEVEL%` 之类取本脚本的退出码：
    `%ERRORLEVEL%` 在 cmd **解析期**就被展开，读到的是命令还没跑时的值
    （OP-0819-F 实测读到 0、真值是 2）。同族第一形态是管道——报的是 `tail`
    的码。两者都表现为"拿到一个看起来很正常的 0"。
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$WorktreeName,
    [string]$RepoRoot,
    [string]$BackupDir,
    [switch]$RestartOnly,
    [switch]$DryRun
)

$ErrorActionPreference = 'Stop'
$script:Summary = New-Object System.Collections.ArrayList

function Write-Gate {
    param([string]$Gate, [string]$Verdict, [string]$Detail)
    $line = "[{0}] {1} —— {2}" -f $Verdict, $Gate, $Detail
    Write-Host $line
    [void]$script:Summary.Add($line)
}

function Stop-WithCode {
    param([int]$Code, [string]$Reason)
    Write-Host ''
    Write-Host '================ 摘要 ================'
    $script:Summary | ForEach-Object { Write-Host $_ }
    Write-Host "结论：$Reason"
    Write-Host "退出码：$Code"
    exit $Code
}

function Invoke-Git {
    <# 统一带 core.quotepath=false：本项目路径几乎全是中文，不关掉的话
       status/diff 的路径会被转成八进制转义串。 #>
    param([string[]]$GitArgs, [string]$Cwd)
    $out = & git -c core.quotepath=false -C $Cwd @GitArgs 2>&1
    return [pscustomobject]@{ Code = $LASTEXITCODE; Text = ($out -join "`n") }
}

# ─────────────────────────── 前置：解出仓库根 ───────────────────────────
if (-not $RepoRoot) {
    try {
        $common = & git -C $PSScriptRoot rev-parse --path-format=absolute --git-common-dir 2>$null
        if ($LASTEXITCODE -ne 0 -or -not $common) { throw '无法解析 --git-common-dir' }
        $RepoRoot = Split-Path -Parent ($common -join '')
    } catch {
        Write-Gate '前置' '✗' "解析仓库根失败：$_"
        Stop-WithCode 20 '仓库根未解出，未做任何改动'
    }
}
$RepoRoot = (Resolve-Path -LiteralPath $RepoRoot).Path
$WorktreePath = Join-Path (Join-Path $RepoRoot '.claude\worktrees') $WorktreeName

Write-Host "仓库根　　：$RepoRoot"
Write-Host "目标执行体：$WorktreePath"
$modeText = if ($DryRun) { '干跑（不做任何改动）' } elseif ($RestartOnly) { '实跑 · 只重启验活（跳过 ff 三关）' } else { '实跑 · 对齐＋重启' }
Write-Host ("模式　　　：{0}" -f $modeText)
Write-Host ''

# ─────────────────────── 第 1 关：身份校验 ───────────────────────
# 🔴 判 worktree 身份**只认两件事**：目录内 `.git` 条目存在 ＋ 在
# `git worktree list --porcelain` 注册项内。**不看 `git -C <目录>` 的输出**
# ——#98 实测：对非注册目录跑 `git -C`，git 会静默向上找到主工作区的 `.git`
# 并返回**主工作区**的状态（当时返回"分支=master／落后 0／脏 0"，照抄就会
# 把一个该清的空壳记成"干净、无需处理"）。
if (-not (Test-Path -LiteralPath $WorktreePath)) {
    Write-Gate '1 身份校验' '✗' "目录不存在：$WorktreePath"
    Stop-WithCode 10 '目标不存在，未做任何改动'
}
if (-not (Test-Path -LiteralPath (Join-Path $WorktreePath '.git'))) {
    Write-Gate '1 身份校验' '✗' '目录内无 .git 条目（物理空壳）'
    Stop-WithCode 10 '非有效 worktree，未做任何改动'
}
$porcelain = Invoke-Git @('worktree', 'list', '--porcelain') $RepoRoot
if ($porcelain.Code -ne 0) {
    Write-Gate '1 身份校验' '✗' "worktree list 失败：$($porcelain.Text)"
    Stop-WithCode 10 '注册项读取失败，未做任何改动'
}
$normTarget = $WorktreePath.Replace('\', '/').TrimEnd('/')
$registered = $false
$targetHead = $null
$lines = $porcelain.Text -split "`n"
for ($i = 0; $i -lt $lines.Count; $i++) {
    if ($lines[$i] -like 'worktree *') {
        $p = $lines[$i].Substring(9).Trim().Replace('\', '/').TrimEnd('/')
        if ($p -ieq $normTarget) {
            $registered = $true
            if ($i + 1 -lt $lines.Count -and $lines[$i + 1] -like 'HEAD *') {
                $targetHead = $lines[$i + 1].Substring(5).Trim()
            }
        }
    }
}
if (-not $registered) {
    Write-Gate '1 身份校验' '✗' '不在 git worktree 注册项内'
    Stop-WithCode 10 '非注册 worktree，未做任何改动'
}
if (-not $targetHead -or $targetHead -match '^0+$') {
    Write-Gate '1 身份校验' '✗' "HEAD 无效（$targetHead）"
    Stop-WithCode 10 'HEAD 无效，未做任何改动'
}
Write-Gate '1 身份校验' '✓' "注册项命中，HEAD=$($targetHead.Substring(0,7))"

# ─────────────────────── 公用：找常驻进程链 ───────────────────────
function Get-CarrierProcesses {
    param([string]$NormPath)
    # ⚠️ #68 假警报教训：过滤字符串会**命中执行这条查询的进程自己**（当时
    # 看到"第二个 run_aibot_service 进程"，查明是自己的命令行自匹配）。故
    # 显式排除本进程及其父链。
    $selfChain = @()
    $cur = $PID
    for ($i = 0; $i -lt 8 -and $cur; $i++) {
        $selfChain += $cur
        $p = Get-CimInstance Win32_Process -Filter "ProcessId = $cur" -ErrorAction SilentlyContinue
        if (-not $p) { break }
        $cur = $p.ParentProcessId
    }
    Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
        Where-Object {
            $_.CommandLine -and
            ($_.CommandLine.Replace('\', '/').ToLower().Contains(($NormPath + '/').ToLower())) -and
            ($selfChain -notcontains $_.ProcessId)
        }
}

# ─────────────────────── 公用：2b 进程新鲜度的两个读数 ───────────────────────
function Get-CodeLandedTime {
    <# 代码落库时刻 ＝ max(HEAD 提交时刻, worktree HEAD 最近一次 reflog 移动时刻)。
       返回 [pscustomobject]{ Landed, CommitAt, ReflogAt, Basis }；两者都取不到
       返回 $null（调用方按「无法判定」处理，不得当新鲜）。#>
    param([string]$Head, [string]$Wt, [string]$Root)
    $commitAt = $null; $reflogAt = $null
    $c = Invoke-Git @('log', '-1', '--format=%cI', $Head) $Root
    if ($c.Code -eq 0 -and $c.Text.Trim()) {
        try { $commitAt = [DateTimeOffset]::Parse($c.Text.Trim(), [cultureinfo]::InvariantCulture) } catch { }
    }
    # reflog 时刻：`%gd` 配 `--date=iso-strict` 形如 `HEAD@{2026-09-13T07:19:00+08:00}`。
    $r = Invoke-Git @('log', '-g', '-1', '--date=iso-strict', '--format=%gd', 'HEAD') $Wt
    if ($r.Code -eq 0 -and $r.Text -match '\{([^}]+)\}') {
        try { $reflogAt = [DateTimeOffset]::Parse($Matches[1], [cultureinfo]::InvariantCulture) } catch { }
    }
    if (-not $commitAt -and -not $reflogAt) { return $null }
    $landed = $commitAt; $basis = '提交时刻'
    if ($reflogAt -and (-not $commitAt -or $reflogAt -gt $commitAt)) { $landed = $reflogAt; $basis = 'reflog 移动时刻' }
    return [pscustomobject]@{ Landed = $landed; CommitAt = $commitAt; ReflogAt = $reflogAt; Basis = $basis }
}

function Test-CarrierAutoRestartEnabled {
    <# 与 sweep `_carrier_auto_restart_enabled` 同一把开关、同一解析：仓库根
       `.env` 里 `CARRIER_AUTO_RESTART_ENABLED=<1|true|yes|on>`；读不到、读错、
       值不认识一律 OFF。 #>
    param([string]$Root)
    $envPath = Join-Path $Root '.env'
    if (-not (Test-Path -LiteralPath $envPath)) { return $false }
    try { $lines = Get-Content -LiteralPath $envPath -Encoding UTF8 -ErrorAction Stop } catch { return $false }
    foreach ($l in $lines) {
        $t = $l.Trim()
        if ($t.StartsWith('CARRIER_AUTO_RESTART_ENABLED=')) {
            $v = $t.Substring('CARRIER_AUTO_RESTART_ENABLED='.Length).Trim().Trim('"').Trim("'").ToLower()
            return @('1', 'true', 'yes', 'on') -contains $v
        }
    }
    return $false
}

# ─────────────────────── 第 2 关：可 ff 校验 ───────────────────────
# 不满足即停。**绝不 revert、绝不挑拣提交**——#68 的原话是"未在生产载体上
# 造出第三种代码状态"。
$behindN = -1
$StaleCarrier = $false        # 2b 判「代码已对齐、执行体过期」时置真
$StaleDetail = ''
if ($RestartOnly) {
    Write-Gate '2 可 ff 校验' 'i' '已跳过（-RestartOnly：ff 由 sweep 每轮负责，本次只重启验活）'
}
if (-not $RestartOnly) {
$ancestor = Invoke-Git @('merge-base', '--is-ancestor', $targetHead, 'master') $RepoRoot
$ahead = Invoke-Git @('rev-list', '--count', "master..$targetHead") $RepoRoot
$behind = Invoke-Git @('rev-list', '--count', "$targetHead..master") $RepoRoot
$behindN = if ($behind.Code -eq 0) { [int]$behind.Text.Trim() } else { -1 }
$aheadN = if ($ahead.Code -eq 0) { [int]$ahead.Text.Trim() } else { -1 }
if ($ancestor.Code -ne 0 -or $aheadN -ne 0) {
    Write-Gate '2 可 ff 校验' '✗' "非纯 ff（是否祖先=$($ancestor.Code -eq 0)，ahead=$aheadN）"
    Stop-WithCode 11 '不可 ff，已停手；不做 revert／挑拣，未做任何改动'
}
Write-Gate '2 可 ff 校验' '✓' "可纯 ff：落后 $behindN 个提交，ahead=0"

if ($behindN -eq 0) {
    # ── 2b 进程新鲜度（#570）：落后 0 只说明 git 对齐了，**不说明进程跟上了**。
    $landed = Get-CodeLandedTime $targetHead $WorktreePath $RepoRoot
    $procs = @(Get-CarrierProcesses $normTarget)
    if (-not $landed) {
        # 代码落库时刻取不到 ⇒ 无法判定；按「不得报绿」处理，但也没有依据去重启。
        Write-Gate '2b 进程新鲜度' '✗' '代码落库时刻取不到（git log／reflog 均失败），无法判定新鲜度——不报「已对齐」'
        Stop-WithCode 20 '落后 0 但新鲜度无法判定，未做任何改动'
    }
    $landedShown = "{0}Z（{1} 本地，取 {2}）" -f $landed.Landed.ToUniversalTime().ToString('yyyy-MM-dd HH:mm:ss'), $landed.Landed.ToLocalTime().ToString('HH:mm:ss'), $landed.Basis
    if ($procs.Count -eq 0) {
        Write-Gate '2b 进程新鲜度' 'i' "落后 0，且当前**没有**指向本执行体的进程在跑（无从比对；代码落库于 $landedShown）——若该执行体本应常驻，那是「没起来」而非「过期」，本脚本不代为启动"
        Write-Gate '总体' '✓' '已对齐（落后 0），无在跑进程，无需处置'
        Stop-WithCode 0 '已对齐，未做任何改动'
    }
    $staleProcs = @()
    foreach ($p in $procs) {
        $created = [DateTimeOffset]$p.CreationDate
        $mark = if ($created -lt $landed.Landed) { '过期' } else { '新鲜' }
        Write-Host ("      在跑：{0} pid={1} 起于 {2}Z（{3} 本地）⇒ {4}" -f $p.Name, $p.ProcessId, $created.ToUniversalTime().ToString('yyyy-MM-dd HH:mm:ss'), $created.ToLocalTime().ToString('HH:mm:ss'), $mark)
        if ($created -lt $landed.Landed) { $staleProcs += $p }
    }
    if ($staleProcs.Count -eq 0) {
        Write-Gate '2b 进程新鲜度' '✓' "$($procs.Count) 个在跑进程均晚于代码落库时刻 $landedShown"
        Write-Gate '总体' '✓' '已对齐（落后 0，执行体新鲜），无需处置'
        Stop-WithCode 0 '已对齐且执行体新鲜，未做任何改动'
    }
    $oldest = ($staleProcs | ForEach-Object { [DateTimeOffset]$_.CreationDate } | Sort-Object | Select-Object -First 1)
    $lag = $landed.Landed - $oldest
    $lagShown = if ($lag.TotalMinutes -ge 1) { '{0:N0} 分钟' -f $lag.TotalMinutes } else { '{0:N0} 秒' -f $lag.TotalSeconds }
    $StaleDetail = "代码已对齐（落后 0），但 {0}/{1} 个在跑进程早于代码落库时刻 {2}，最老进程比代码老 {3} ⇒ 执行体过期，跑的是旧代码" -f $staleProcs.Count, $procs.Count, $landedShown, $lagShown
    Write-Gate '2b 进程新鲜度' '✗' $StaleDetail
    $StaleCarrier = $true
}
}
# 从这里起，「只重启验活」有两个来源：调用方显式 `-RestartOnly`，或 2b 判过期。
$SkipFf = $RestartOnly -or $StaleCarrier

# 找出指向本执行体的计划任务（与 sweep 侧同一判据：Action 路径落在该
# worktree 之下）。
$tasks = @()
try {
    foreach ($t in Get-ScheduledTask) {
        foreach ($a in $t.Actions) {
            $blob = ("{0} {1}" -f [string]$a.Execute, [string]$a.Arguments).Replace('\', '/')
            if ($blob.ToLower().Contains(($normTarget + '/').ToLower())) { $tasks += $t.TaskName; break }
        }
    }
} catch {
    Write-Gate '前置' '✗' "计划任务查询失败：$_"
    Stop-WithCode 20 '执行体关联任务未取到，未做任何改动'
}
$tasks = @($tasks | Select-Object -Unique)
# 🔴 **第 4 个坑（2026-08-24 首次实跑当场撞到，#68 未记）**：这三个关联任务
# 里只有 `ZhuopinAibotDevListener` 是常驻的，另两个是**每日一次性任务**。
# 初版把它们一并 `Start-ScheduledTask`，等于**在计划外把日任务跑了一遍**
# ——本次实测它们没发出任何东西（`dispatch_batch_summary` 的 sent=0），
# **但那是运气不是设计**：这一族脚本普遍是「报告上次以来的新增项并记下
# 已见」，计划外跑一遍有可能**把新增项消耗掉却不通知任何人**。
# ⇒ 判据：**只重启「停服前确实在跑」的任务**，其余显式跳过并说明。
$runningBefore = @()
foreach ($name in $tasks) {
    try {
        if ((Get-ScheduledTask -TaskName $name).State -eq 'Running') { $runningBefore += $name }
    } catch { }
}
if ($tasks.Count -eq 0) {
    Write-Gate '前置' 'i' $(if ($SkipFf) { '未找到指向本执行体的计划任务——无可停服/重启的任务（进程链仍按命令行匹配处理）' } else { '未找到指向本执行体的计划任务——本次只做 ff，不涉停服/重启/验活' })
} else {
    Write-Gate '前置' 'i' ("关联计划任务 {0} 个：{1}" -f $tasks.Count, ($tasks -join '、'))
}

if ($DryRun) {
    $plan = if ($SkipFf) {
        "将执行：停 $($tasks.Count) 个任务并杀进程链 → 只重启其中在跑的 $($runningBefore.Count) 个（$($runningBefore -join '、')）→ 验重启 → 验活（跳过 ff 三关）"
    } else {
        "将执行：备份 → 停 $($tasks.Count) 个任务并杀进程链 → ff（$behindN 个提交）→ 只重启其中在跑的 $($runningBefore.Count) 个（$($runningBefore -join '、')）→ 验重启 → 验活"
    }
    Write-Gate '干跑' 'i' $plan
    if ($StaleCarrier) {
        # 🔴 量具不得报绿：干跑判到过期，退出码给 18，不给 0。
        Stop-WithCode 18 ("干跑结束，未做任何改动；但执行体过期——处置：本脚本 -WorktreeName {0} -RestartOnly（人工确认后跑）" -f $WorktreeName)
    }
    Stop-WithCode 0 '干跑结束，未做任何改动'
}

# ─────────── 2b 判过期后的分流：什么条件下自动重启、什么条件下只告警 ───────────
# #570 末句：重启在跑的生产服务属 ⏭️／🟡，**不得一刀切自动**。判据只有一条、
# 且复用既有的：`.env` 的 `CARRIER_AUTO_RESTART_ENABLED`（与 sweep 同一把开关）。
#   · ON  ⇒ 继续往下，走既有 -RestartOnly 路径（第 4/6/7/8 关），成功只留痕；
#   · OFF ⇒ 只告警（退出码 18）并打印处置命令，由人带 -RestartOnly 再跑。
if ($StaleCarrier -and -not (Test-CarrierAutoRestartEnabled $RepoRoot)) {
    Write-Gate '2b 分流' 'i' ("自动重启开关 CARRIER_AUTO_RESTART_ENABLED＝OFF（缺省，读不到即 OFF）⇒ 只告警不重启；处置：本脚本 -WorktreeName {0} -RestartOnly" -f $WorktreeName)
    Stop-WithCode 18 '执行体过期（代码已对齐、进程早于代码落库时刻），自动重启关着，已停手、未做任何改动'
}
if ($StaleCarrier) {
    Write-Gate '2b 分流' 'i' '自动重启开关＝ON ⇒ 按既有 -RestartOnly 路径重启验活（跳过备份／ff）'
}

# ─────────────────────── 第 3 关：固化备份 ───────────────────────
# #267 真实事故：两份签字审计报告落在某 worktree 的 `reports/`（gitignore
# 命中），被判"干净可删"后随 `worktree remove` **真实丢失**。故 ff 之前
# 一律先把未跟踪 ＋ ignored 内容固化到**仓库外**。
if ($SkipFf) {
    Write-Gate '3 固化备份' 'i' $(if ($RestartOnly) { '已跳过（-RestartOnly：本次不 ff，工作区内容不会被覆盖）' } else { '已跳过（2b 判过期、落后 0：本次不 ff，工作区内容不会被覆盖）' })
}
if (-not $SkipFf) {
if (-not $BackupDir) {
    $stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
    $BackupDir = Join-Path $env:TEMP "carrier-realign-$WorktreeName-$stamp"
}
if ($BackupDir.Replace('\', '/').ToLower().StartsWith($RepoRoot.Replace('\', '/').ToLower())) {
    Write-Gate '3 固化备份' '✗' "备份目录落在仓库内：$BackupDir"
    Stop-WithCode 12 '备份目录必须在仓库之外，未做任何改动'
}
try {
    $st = Invoke-Git @('status', '--porcelain=v1', '--untracked-files=all', '--ignored=matching') $WorktreePath
    if ($st.Code -ne 0) { throw "status 失败：$($st.Text)" }
    $rels = @()
    foreach ($l in ($st.Text -split "`n")) {
        if ($l -match '^(\?\?|!!) (.+)$') { $rels += $Matches[2].Trim().Trim('"') }
    }
    New-Item -ItemType Directory -Path $BackupDir -Force | Out-Null
    foreach ($rel in $rels) {
        $src = Join-Path $WorktreePath ($rel -replace '/', '\')
        if (-not (Test-Path -LiteralPath $src)) { continue }
        $dst = Join-Path $BackupDir ($rel -replace '/', '\')
        $dstParent = Split-Path -Parent $dst
        if ($dstParent) { New-Item -ItemType Directory -Path $dstParent -Force | Out-Null }
        Copy-Item -LiteralPath $src -Destination $dst -Recurse -Force
    }
    Write-Gate '3 固化备份' '✓' ("{0} 项已备份到 {1}" -f $rels.Count, $BackupDir)
    foreach ($rel in $rels) { Write-Host "      · $rel" }
} catch {
    Write-Gate '3 固化备份' '✗' "$_"
    Stop-WithCode 12 '备份失败，已停手，未执行 ff'
}
}

# ─────────────────────── 第 4 关：停服（整条进程链） ───────────────────────
# 🔴 **坑⑴**（#68 当场复现）：`Stop-ScheduledTask` **只杀 wscript**，遗留
# powershell 与 python 子进程。**父进程带自愈，先杀子会被立刻拉起** ⇒ 必须
# 先杀父再杀子，且复查零残留后才继续。
# （`Get-CarrierProcesses` 定义已上移到第 2 关之前——2b 进程新鲜度也要用它，
#  且 PowerShell 脚本里函数须先定义后调用。）

foreach ($name in $tasks) {
    try { Stop-ScheduledTask -TaskName $name -ErrorAction Stop } catch { }
}
Start-Sleep -Seconds 2

$before = @(Get-CarrierProcesses $normTarget)
$beforeInfo = $before | ForEach-Object {
    [pscustomobject]@{ Pid = $_.ProcessId; Name = $_.Name; Created = $_.CreationDate }
}
foreach ($p in $beforeInfo) { Write-Host ("      停服前存活：{0} pid={1} 起于 {2}" -f $p.Name, $p.Pid, $p.Created) }

# 先父后子：按"是不是别人的父"排序——父在前。
$byPid = @{}
foreach ($p in $before) { $byPid[[int]$p.ProcessId] = $p }
function Get-Depth {
    param($Proc, $Map)
    $d = 0; $cur = [int]$Proc.ParentProcessId
    while ($Map.ContainsKey($cur) -and $d -lt 16) { $d++; $cur = [int]$Map[$cur].ParentProcessId }
    return $d
}
$ordered = $before | Sort-Object { Get-Depth $_ $byPid }   # 深度小 = 更靠父端 = 先杀
foreach ($p in $ordered) {
    try {
        Stop-Process -Id $p.ProcessId -Force -ErrorAction Stop
        Write-Host ("      已终止：{0} pid={1}" -f $p.Name, $p.ProcessId)
    } catch {
        Write-Host ("      终止失败（可能已随父进程退出）：pid={0}：{1}" -f $p.ProcessId, $_)
    }
}
Start-Sleep -Seconds 3
$residue = @(Get-CarrierProcesses $normTarget)
if ($residue.Count -gt 0) {
    foreach ($p in $residue) { Write-Host ("      残留：{0} pid={1}" -f $p.Name, $p.ProcessId) }
    Write-Gate '4 停服' '✗' "复查仍有 $($residue.Count) 个残留进程"
    Stop-WithCode 13 ("停服未清干净，已停手；未执行 ff（备份已在 $BackupDir）")
}
Write-Gate '4 停服' '✓' "整条进程链已清零（停服前 $($before.Count) 个，先父后子，复查零残留）"

# ─────────────────────── 第 5 关：ff ───────────────────────
if ($SkipFf) {
    Write-Gate '5 ff' 'i' $(if ($RestartOnly) { '已跳过（-RestartOnly）' } else { '已跳过（2b 判过期、落后 0，无需 ff）' })
}
if (-not $SkipFf) {
$merge = Invoke-Git @('merge', '--ff-only', 'master') $WorktreePath
if ($merge.Code -ne 0) {
    Write-Gate '5 ff' '✗' "merge --ff-only 失败：$($merge.Text)"
    Stop-WithCode 14 'ff 失败；服务仍处停止状态，须人工处置'
}
$behindAfter = Invoke-Git @('rev-list', '--count', 'HEAD..master') $WorktreePath
$behindAfterN = if ($behindAfter.Code -eq 0) { [int]$behindAfter.Text.Trim() } else { -1 }
if ($behindAfterN -ne 0) {
    Write-Gate '5 ff' '✗' "ff 后仍落后 $behindAfterN 个提交"
    Stop-WithCode 14 'ff 未达成对齐；服务仍处停止状态，须人工处置'
}
Write-Gate '5 ff' '✓' "已 ff 对齐（$behindN → 0）"
}

# ─────────────────────── 第 6 关：启动 ───────────────────────
$startAt = (Get-Date).ToUniversalTime()
foreach ($name in $tasks) {
    if ($runningBefore -notcontains $name) {
        Write-Host ("      跳过启动：{0}（停服前未在运行；一次性任务不做计划外触发）" -f $name)
        continue
    }
    try { Start-ScheduledTask -TaskName $name -ErrorAction Stop } catch {
        Write-Host ("      启动失败：{0}：{1}" -f $name, $_)
    }
}
if ($runningBefore.Count -eq 0) {
    Write-Gate '6 启动' '✗' '停服前没有任何关联任务处于运行状态——**没有可重启的常驻任务**；若本意是把一个已停的服务拉起来，那是「启动」不是「重启」，请人工确认后手动 Start-ScheduledTask'
    Stop-WithCode 17 '无可重启的常驻任务，已停手（未计划外触发任何一次性任务）'
}
Write-Gate '6 启动' 'i' ("已发起启动 {0}/{1} 个任务（只重启停服前在跑的：{2}；发起时刻 {3}Z）" -f $runningBefore.Count, $tasks.Count, ($runningBefore -join '、'), $startAt.ToString('HH:mm:ss'))

# ─────────────────────── 第 7 关：验重启 ───────────────────────
# 🔴 **坑⑵**：不能只信"已重启"的打印，须比对进程链 CreationTime **真的变了**。
$after = @()
for ($i = 0; $i -lt 20; $i++) {
    Start-Sleep -Seconds 3
    $after = @(Get-CarrierProcesses $normTarget)
    if ($after.Count -gt 0) { break }
}
if ($after.Count -eq 0) {
    Write-Gate '7 验重启' '✗' '启动后未见任何关联进程'
    Stop-WithCode 15 '重启未生效（无进程），须人工处置'
}
$stale = @($after | Where-Object { $_.CreationDate.ToUniversalTime() -lt $startAt })
foreach ($p in $after) {
    Write-Host ("      启动后：{0} pid={1} 起于 {2}" -f $p.Name, $p.ProcessId, $p.CreationDate)
}
if ($stale.Count -gt 0) {
    Write-Gate '7 验重启' '✗' "有 $($stale.Count) 个进程 CreationTime 早于启动发起时刻（未真正重启）"
    Stop-WithCode 15 '重启未生效（CreationTime 未刷新），须人工处置'
}
Write-Gate '7 验重启' '✓' "$($after.Count) 个进程 CreationTime 均晚于启动发起时刻"

# ─────────────────────── 第 8 关：验活（心跳） ───────────────────────
# 🔴 **坑⑶**：不是看服务在不在，是看心跳**真的刷新**。
# ⚠️ `alive_at` 是 **UTC**（实测 `14:28:13Z` ＝ 22:28:13 本地）；本机时区
# UTC+8，比对前必须统一基准（根 CLAUDE.md §5 硬规则）。
$svcDir = Join-Path $WorktreePath '5-平台底座\wecom-aibot-service'
$hbPath = Join-Path $svcDir 'reports\aibot_liveness.json'
if (-not (Test-Path -LiteralPath $svcDir)) {
    Write-Gate '8 验活' 'i' '该执行体不含 wecom-aibot-service，本关**不适用**（如实登记，不计为通过）'
} else {
    $fresh = $false
    $hbShown = '（未读到）'
    for ($i = 0; $i -lt 40; $i++) {
        Start-Sleep -Seconds 3
        if (-not (Test-Path -LiteralPath $hbPath)) { continue }
        try {
            $hb = Get-Content -LiteralPath $hbPath -Raw -Encoding UTF8 | ConvertFrom-Json
            $aliveUtc = ([datetime]$hb.alive_at).ToUniversalTime()
            $hbShown = "{0}Z（{1} 本地）" -f $aliveUtc.ToString('HH:mm:ss'), $aliveUtc.ToLocalTime().ToString('HH:mm:ss')
            if ($aliveUtc -gt $startAt) { $fresh = $true; break }
        } catch { }
    }
    if (-not $fresh) {
        Write-Gate '8 验活' '✗' "心跳未刷新（读到 $hbShown，启动发起于 $($startAt.ToString('HH:mm:ss'))Z）"
        Stop-WithCode 16 '验活失败：心跳未刷新（残留旧戳不算通过），须人工处置'
    }
    Write-Gate '8 验活' '✓' "心跳已刷新至 $hbShown，晚于启动发起时刻"
}

# ─────────────────────── 第 9 关：摘要 ───────────────────────
if ($RestartOnly) { Write-Gate '9 摘要' '✓' '只重启验活模式，未 ff、未备份' }
elseif ($StaleCarrier) { Write-Gate '9 摘要' '✓' '2b 判过期后自动重启（开关 ON），未 ff、未备份' }
else { Write-Gate '9 摘要' '✓' "备份在 $BackupDir" }
Stop-WithCode 0 $(if ($RestartOnly) { '各关通过：已重启并验活' } elseif ($StaleCarrier) { '各关通过：执行体过期已自动重启并验活' } else { '九关全过：已对齐并重启验活' })
