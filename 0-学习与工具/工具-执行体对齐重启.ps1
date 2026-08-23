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
      2 可 ff 校验  —— 不满足即停，绝不 revert／挑拣
      3 固化备份    —— 未跟踪 ＋ ignored 全量复制到**仓库外**
      4 停服        —— 整条进程链，**先父后子**，复查零残留
      5 ff          —— `merge --ff-only`，校验落后归零
      6 启动        —— **只启「停服前在跑的」**，绝不计划外触发一次性日任务
      7 验重启      —— 比对进程链 CreationTime **真的变了**
      8 验活        —— 心跳时间戳**真的刷新**（不是看服务在不在）
      9 摘要

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
    干跑：只跑判定并打印将要做什么，不停服、不 ff、不启动。

.EXAMPLE
    powershell -NoProfile -File "0-学习与工具\工具-执行体对齐重启.ps1" -WorktreeName wecom-service-home -DryRun

.EXAMPLE
    powershell -NoProfile -File "0-学习与工具\工具-执行体对齐重启.ps1" -WorktreeName wecom-service-home -RestartOnly

.NOTES
    退出码（🔴 由本脚本自身 `exit` 给出，调用方读 `$LASTEXITCODE`）：
      0 全关通过 ／ 10 身份 ／ 11 不可 ff ／ 12 备份 ／ 13 停服残留
      14 ff 失败 ／ 15 重启未生效 ／ 16 验活失败 ／ 17 无可重启的常驻任务
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

# ─────────────────────── 第 2 关：可 ff 校验 ───────────────────────
# 不满足即停。**绝不 revert、绝不挑拣提交**——#68 的原话是"未在生产载体上
# 造出第三种代码状态"。
$behindN = -1
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
    Write-Gate '总体' '✓' '已对齐（落后 0），无需处置'
    Stop-WithCode 0 '已对齐，未做任何改动'
}
}

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
    Write-Gate '前置' 'i' '未找到指向本执行体的计划任务——本次只做 ff，不涉停服/重启/验活'
} else {
    Write-Gate '前置' 'i' ("关联计划任务 {0} 个：{1}" -f $tasks.Count, ($tasks -join '、'))
}

if ($DryRun) {
    $plan = if ($RestartOnly) {
        "将执行：停 $($tasks.Count) 个任务并杀进程链 → 只重启其中在跑的 $($runningBefore.Count) 个（$($runningBefore -join '、')）→ 验重启 → 验活（跳过 ff 三关）"
    } else {
        "将执行：备份 → 停 $($tasks.Count) 个任务并杀进程链 → ff（$behindN 个提交）→ 只重启其中在跑的 $($runningBefore.Count) 个（$($runningBefore -join '、')）→ 验重启 → 验活"
    }
    Write-Gate '干跑' 'i' $plan
    Stop-WithCode 0 '干跑结束，未做任何改动'
}

# ─────────────────────── 第 3 关：固化备份 ───────────────────────
# #267 真实事故：两份签字审计报告落在某 worktree 的 `reports/`（gitignore
# 命中），被判"干净可删"后随 `worktree remove` **真实丢失**。故 ff 之前
# 一律先把未跟踪 ＋ ignored 内容固化到**仓库外**。
if ($RestartOnly) {
    Write-Gate '3 固化备份' 'i' '已跳过（-RestartOnly：本次不 ff，工作区内容不会被覆盖）'
}
if (-not $RestartOnly) {
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
if ($RestartOnly) {
    Write-Gate '5 ff' 'i' '已跳过（-RestartOnly）'
}
if (-not $RestartOnly) {
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
else { Write-Gate '9 摘要' '✓' "备份在 $BackupDir" }
Stop-WithCode 0 $(if ($RestartOnly) { '各关通过：已重启并验活' } else { '九关全过：已对齐并重启验活' })
