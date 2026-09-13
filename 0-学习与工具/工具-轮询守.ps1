# 轮询守 —— 把 `poll-opener-batch` 定时任务从「每 15 分钟起一个完整模型会话」降级成
# 「纯脚本先跑两条命令，只在有信号时才唤 `claude -p`；每轮无条件留一行可计数痕」。
#
# 承接：队列 §一 `#575` 甲（Shao Peishen 2026-09-13 答「甲→乙」）；派出线 Cowork 环境总线 `OP-0913-E`，
#       批 `B-0913_轮询守`；看护件 `1-转型规划/0-全景路线图/看护件-【CC】轮询守信号才唤模型-2026-09-13.md`。
#
# 🔴 两个病，一起治（成因原文在看护件 §一，此处只留判别句）：
#   病一：九成以上是空耗——连续 7 次触发 0 次实际动作，而每次触发都是一个完整模型会话；
#         `工具-待合分支巡检.ps1` 自注「白名单候选常年几十条、每轮都不命中」，它早知道自己在空转。
#   病二：跑没跑过查不到——Cowork 桌面端任务不落任何可计数痕迹；探针 `last_run` 只在有通知时才更新，
#         不是运行计数器。**一个不留运行痕迹的守卫，你无法区分「它一直在跑且没事」和「它早就死了」。**
#
# 🔴 信号判据写死、不许模型参与判定（看护件 §二）——**两条命令各自以它们自己的 stdout 标记为准，不另造一套**：
#   ① 探针 `工具-无头棒收工探针.py --via-scheduled-task`：stdout 顶层标记全部 ∈ `$ProbeQuietMarkers`（＝`[NO-SIGNAL]`）才算无信号。
#      `[BASELINE]`／`[SIGNAL]`／任何别的标记 ⇒ 信号（`[BASELINE]` 一生只出现一次，多唤一次比漏掉便宜）。
#   ② 巡检 `工具-待合分支巡检.ps1`：stdout 顶层标记全部 ∈ `$PatrolQuietMarkers` 才算无动作。
#      看护件把这一侧简写成「非 `[NO-ACTION]`」；巡检真身在登记册为空时打的是 `[NO-PENDING]`（同一件事的另一种字面，
#      `poll-opener-batch.SKILL.md` 第 2 件把两者并列为空跑），动作〇／动作二各有自己的 `[WL-NO-ACTION]`／`[WL-OFF]`／
#      `[WT-NO-ACTION]`。**照字面只认 `[NO-ACTION]` 会让登记册为空的每一轮都唤模型——那正是病一本身**，故无动作集合＝
#      这五个字面；`[MERGED]`／`[WAITING]`／`[PENDING-SWEPT]`／`[WL-*]` 其余／`[WT-REMOVED]`／`[WT-BLOCKED]`／`[WT-SKIP]`／
#      `[WT-NONE]`／`[DRY]`／任何未见过的标记 ⇒ 信号（未知即信号＝fail-open 出声，同探针自身取向）。
#   ③ 🔴 命令非零退出／超时／stdout 一个顶层标记都没有 ⇒ 一律视为信号、唤模型并把 stderr 带进去。**不静默吞。**
#      （同日实证：`git blame` 取龄 32.9 s 超 30 s 上限而降级放行——静默失效的活例。）
#   任一侧有信号 ⇒ 唤模型一次；两侧都无 ⇒ 本轮到此结束，只留痕。
#
# 🔴 留痕（病二的解）：每轮**无条件**在 `<Repo>/reports/poll-guard/poll-guard-<yyyyMMdd>.jsonl` 追加一行——
#   时刻／两条命令退出码与耗时／各自判定与顶层标记／是否唤模型／模型退出码与耗时／本轮总耗时。
#   `reports/` 被 `.gitignore` 整棵忽略（`**/reports/`），**本文件不入库、只用于计数**——它不是 ff 正本，
#   与 `1-转型规划/0-全景路线图/合入登记/` 无关、也不许混进去。唤模型或命令异常的轮次另存全文捕获到
#   `reports/poll-guard/rounds/<轮次号>/`（probe.out／probe.err／patrol.out／patrol.err／prompt.txt／claude.out／claude.err）。
#
# 🔴 唤模型的方式：把 `poll-opener-batch.SKILL.md` 章程原文＋两条命令本轮的 stdout/stderr 一并喂给 `claude -p`（stdin），
#   并明写「两条命令已跑过、不要重跑」——探针跑过一次已把信号标为「已报」并推了企微，重跑只会得到 `[NO-SIGNAL]`；
#   巡检跑过一次已执行合入／销行／清理，重跑是双次副作用。工具白名单只给只读（`Read`／`Glob`／`Grep`／`Bash(git log:*)`），
#   章程本就只许它做只读核查。模型回复落在本轮捕获目录的 `claude.out`。
#
# 🔴 本脚本只**调用**探针与巡检，不改它们一个字节；不碰 `工具-opener批处理执行v2.ps1`／`工具-落库sweep.py`／合入链路三脚本；
#   不停用、不改动现有 Cowork 桌面端任务（那在他本机、归他手动）。注册计划任务见 `工具-注册轮询守计划任务.ps1`。
#
# 用法：pwsh -NoProfile -File 工具-轮询守.ps1 [-DryRun] [-Repo <仓库根>] [-LogDir <留痕目录>] [-Model <模型>]
#   -DryRun：零副作用干跑——探针加 `--peek`（不标已报、不推企微）、巡检加 `-DryRun`（不合入不删）、不唤模型；
#            仍按同一判据打出「本轮本会不会唤模型」并留痕（行内 `dry_run=true`）。
#   `-ProbeScript`／`-PatrolScript`／`-ClaudeExe`／`-SkillDoc`／`-PythonExe`／`-PwshExe` 只为单测指向桩而设，默认值即生产值。
#
# 退出码：0＝本轮走完（不论有无信号、模型退出码如何——模型结果在留痕行与 claude.out 里）；
#         2＝本脚本自身异常（写不了留痕目录等）；3＝上一轮仍在跑（互斥体占用，本轮跳过，跳过也留一行痕）。
param(
    [string]$Repo = 'C:\Dev\zhuopin-ai',
    [string]$LogDir = '',
    [string]$ProbeScript = '',
    [string]$PatrolScript = '',
    [string]$SkillDoc = '',
    [string]$PythonExe = 'python',
    [string]$PwshExe = 'pwsh',
    [string]$ClaudeExe = '',
    [string]$Model = '',
    [int]$ProbeTimeoutSec = 120,
    [int]$PatrolTimeoutSec = 900,
    [int]$ClaudeTimeoutSec = 1200,
    [switch]$DryRun
)
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

# ── 判据常量（🔴 改这两个集合＝改口径判据，属 🟡 档，须 Shao Peishen 答复；单测锁定它们的字面） ──
$ProbeQuietMarkers  = @('NO-SIGNAL')
$PatrolQuietMarkers = @('WL-NO-ACTION', 'WL-OFF', 'NO-PENDING', 'NO-ACTION', 'WT-NO-ACTION')
$MarkerRegex        = '^\[([A-Z][A-Z0-9-]*)\]'   # 顶层标记＝行首 `[大写-数字]`；`[lane:…]`／`[S:…]` 之类小写的不算

$LogDirNote = '本文件不入库、只用于计数（reports/ 被 .gitignore 整棵忽略；不是 ff 正本，与 合入登记/ 无关）'

if (-not $LogDir)       { $LogDir       = Join-Path $Repo 'reports\poll-guard' }
if (-not $ProbeScript)  { $ProbeScript  = Join-Path $Repo '0-学习与工具\工具-无头棒收工探针.py' }
if (-not $PatrolScript) { $PatrolScript = Join-Path $Repo '0-学习与工具\工具-待合分支巡检.ps1' }
if (-not $SkillDoc)     { $SkillDoc     = Join-Path $Repo '0-学习与工具\定时任务源码\poll-opener-batch.SKILL.md' }

$roundStart = Get-Date
$roundId    = $roundStart.ToString('yyyyMMdd-HHmmss')
$dayFile    = Join-Path $LogDir ("poll-guard-" + $roundStart.ToString('yyyyMMdd') + ".jsonl")
$roundDir   = Join-Path (Join-Path $LogDir 'rounds') $roundId

try { New-Item -ItemType Directory -Force -Path $LogDir | Out-Null }
catch { Write-Host "[GUARD-ERROR] 建不了留痕目录 $LogDir：$($_.Exception.Message)"; exit 2 }

function Write-Trace {
    <# 每轮无条件追加一行 JSONL（病二的解）。写完回读最后一行核对 round 字段——只有动作没有手段的验证＝没有验证。 #>
    param([Parameter(Mandatory)][System.Collections.IDictionary]$Row)
    $Row['note'] = $LogDirNote
    $json = ($Row | ConvertTo-Json -Compress -Depth 6)
    Add-Content -Path $dayFile -Value $json -Encoding UTF8
    $last = Get-Content -Path $dayFile -Encoding UTF8 -Tail 1
    if (-not ($last -like ('*"round":"' + $Row['round'] + '"*'))) {
        Write-Host "[GUARD-ERROR] 留痕回读不符：$dayFile 末行不含 round=$($Row['round'])"
        return $false
    }
    return $true
}

# ── 互斥：上一轮（多半是巡检在 rebase/ff/回归）还没跑完时，本轮不叠加、但仍留一行痕 ──
$mutex = New-Object System.Threading.Mutex($false, 'Global\ZhuopinPollGuard')
$gotMutex = $false
try { $gotMutex = $mutex.WaitOne(0) } catch [System.Threading.AbandonedMutexException] { $gotMutex = $true }
if (-not $gotMutex) {
    $null = Write-Trace @{
        ts = $roundStart.ToString('o'); round = $roundId; dry_run = [bool]$DryRun; skipped = 'overlap'
        woke = $false; total_ms = 0
    }
    Write-Host "[GUARD-SKIP] 上一轮仍在跑（互斥体 Global\ZhuopinPollGuard 占用），本轮跳过；已留痕 $dayFile"
    exit 3
}

function Invoke-Captured {
    <# 起子进程、捕获 stdout/stderr 到文件、限时；超时整树 taskkill 并记 exit=-1（timeout）。
       返回 @{ exit; ms; out; err; timeout }。🔴 非零退出／超时由调用方判成信号，这里只如实记录。 #>
    param(
        [Parameter(Mandatory)][string]$Exe,
        [Parameter(Mandatory)][string[]]$ArgList,
        [Parameter(Mandatory)][string]$Tag,
        [Parameter(Mandatory)][int]$TimeoutSec,
        [string]$StdinFile = ''
    )
    $tmpDir = Join-Path $LogDir '_tmp'
    New-Item -ItemType Directory -Force -Path $tmpDir | Out-Null
    $outF = Join-Path $tmpDir "$roundId-$Tag.out"
    $errF = Join-Path $tmpDir "$roundId-$Tag.err"
    $sw = [System.Diagnostics.Stopwatch]::StartNew()
    # 🔴 Start-Process 不给含空格的参数自动加引号（2026-09-13 实测：`Bash(git log:*)` 被拆成两个参数），这里统一补上
    $quoted = @($ArgList | ForEach-Object { if ($_ -match '\s' -and $_ -notmatch '^".*"$') { '"' + $_ + '"' } else { $_ } })
    $sp = @{
        FilePath = $Exe; ArgumentList = $quoted; WorkingDirectory = $Repo; PassThru = $true; NoNewWindow = $true
        RedirectStandardOutput = $outF; RedirectStandardError = $errF
    }
    if ($StdinFile) { $sp['RedirectStandardInput'] = $StdinFile }
    $timedOut = $false
    try {
        $proc = Start-Process @sp
        if (-not $proc.WaitForExit($TimeoutSec * 1000)) {
            $timedOut = $true
            & taskkill /PID $proc.Id /T /F 2>&1 | Out-Null
            Start-Sleep -Milliseconds 300
        }
        $code = if ($timedOut) { -1 } else { $proc.ExitCode }
    } catch {
        # 起不来（可执行文件不存在等）——同样不吞：exit=-2 ＋ 把异常文本当 stderr
        $code = -2
        Set-Content -Path $errF -Value ("[GUARD] 起进程失败：" + $_.Exception.Message) -Encoding UTF8
        if (-not (Test-Path $outF)) { Set-Content -Path $outF -Value '' -Encoding UTF8 }
    }
    $sw.Stop()
    $out = if (Test-Path $outF) { Get-Content -Raw -Encoding UTF8 $outF } else { '' }
    $err = if (Test-Path $errF) { Get-Content -Raw -Encoding UTF8 $errF } else { '' }
    if ($timedOut) { $err = "[GUARD] 超时 ${TimeoutSec}s，已整树 taskkill。`n" + $err }
    Remove-Item -Force -ErrorAction SilentlyContinue $outF, $errF
    return @{ exit = [int]$code; ms = [int]$sw.ElapsedMilliseconds; out = [string]$out; err = [string]$err; timeout = $timedOut }
}

function Get-TopMarkers {
    param([string]$Text)
    $found = @()
    foreach ($line in ($Text -split "`r?`n")) {
        if ($line -match $MarkerRegex) { $found += $Matches[1] }
    }
    return @($found)
}

function Get-CommandVerdict {
    <# 判据 ①②③ 的机械实现。返回 @{ signal=bool; verdict=string; markers=string[] }。
       verdict 字面：quiet ｜ exit:<code> ｜ timeout ｜ no-marker ｜ markers:<非静默标记逗号连接> #>
    param([hashtable]$Run, [string[]]$QuietSet)
    $markers = Get-TopMarkers -Text $Run.out
    if ($Run.timeout)     { return @{ signal = $true; verdict = 'timeout';            markers = $markers } }
    if ($Run.exit -ne 0)  { return @{ signal = $true; verdict = ('exit:' + $Run.exit); markers = $markers } }
    if ($markers.Count -eq 0) { return @{ signal = $true; verdict = 'no-marker';      markers = $markers } }
    $loud = @($markers | Where-Object { $QuietSet -notcontains $_ } | Select-Object -Unique)
    if ($loud.Count -gt 0) { return @{ signal = $true; verdict = ('markers:' + ($loud -join ',')); markers = $markers } }
    return @{ signal = $false; verdict = 'quiet'; markers = $markers }
}

$row = [ordered]@{
    ts = $roundStart.ToString('o'); round = $roundId; dry_run = [bool]$DryRun
}
$capture = $null
try {
    # ── 第 1 件：无头棒收工探针（🔴 `--via-scheduled-task` 不能漏、`--no-notify` 绝不用——章程原话） ──
    $env:PYTHONUTF8 = '1'; $env:PYTHONIOENCODING = 'utf-8'
    $probeArgs = @($ProbeScript, '--via-scheduled-task')
    if ($DryRun) { $probeArgs += '--peek' }
    $probe = Invoke-Captured -Exe $PythonExe -ArgList $probeArgs -Tag 'probe' -TimeoutSec $ProbeTimeoutSec
    $pj = Get-CommandVerdict -Run $probe -QuietSet $ProbeQuietMarkers

    # ── 第 2 件：待合分支巡检（只调用，不改；`-DryRun` 只在干跑时透传） ──
    $patrolArgs = @('-NoProfile', '-NonInteractive', '-File', $PatrolScript)
    if ($DryRun) { $patrolArgs += '-DryRun' }
    $patrol = Invoke-Captured -Exe $PwshExe -ArgList $patrolArgs -Tag 'patrol' -TimeoutSec $PatrolTimeoutSec
    $tj = Get-CommandVerdict -Run $patrol -QuietSet $PatrolQuietMarkers

    $wake = ($pj.signal -or $tj.signal)
    $row['probe']  = @{ exit = $probe.exit;  ms = $probe.ms;  verdict = $pj.verdict; markers = @($pj.markers) }
    $row['patrol'] = @{ exit = $patrol.exit; ms = $patrol.ms; verdict = $tj.verdict; markers = @($tj.markers) }
    $row['signal'] = $wake
    $row['woke']   = $false
    $row['claude'] = @{ exit = $null; ms = 0 }

    if ($wake -or $probe.exit -ne 0 -or $patrol.exit -ne 0) {
        # 有信号或有异常的轮次才存全文捕获（安静轮只留标记，免得 15 分钟一份 10 KB 巡检回显把盘撑满）
        New-Item -ItemType Directory -Force -Path $roundDir | Out-Null
        Set-Content -Path (Join-Path $roundDir 'probe.out')  -Value $probe.out  -Encoding UTF8
        Set-Content -Path (Join-Path $roundDir 'probe.err')  -Value $probe.err  -Encoding UTF8
        Set-Content -Path (Join-Path $roundDir 'patrol.out') -Value $patrol.out -Encoding UTF8
        Set-Content -Path (Join-Path $roundDir 'patrol.err') -Value $patrol.err -Encoding UTF8
        $capture = $roundDir
        $row['capture'] = $capture
    }

    if ($wake -and -not $DryRun) {
        # ── 唤模型（一次）：章程原文 ＋ 两条命令本轮实际输出，stdin 喂给 claude -p ──
        if (-not $ClaudeExe) {
            $cc = Get-Command claude -ErrorAction SilentlyContinue
            if ($cc) { $ClaudeExe = $cc.Source }
        }
        $skillText = if (Test-Path $SkillDoc) { Get-Content -Raw -Encoding UTF8 $SkillDoc } else { "（章程文件不存在：$SkillDoc）" }
        $prompt = @"
[轮询守唤模型 · $($roundStart.ToString('yyyy-MM-dd HH:mm:ss'))] 本轮由 工具-轮询守.ps1 按写死判据判定有信号：探针＝$($pj.verdict)；巡检＝$($tj.verdict)。
🔴 两条命令本轮已由脚本跑过，stdout／stderr 原样附在下面。**不要重跑探针**（它已把信号标为「已报」并推送企微，重跑只会得到 [NO-SIGNAL]）；**不要重跑巡检**（它已执行过合入／销行／清理动作，重跑＝双次副作用）。
按下方章程的「按输出分支」处理；章程里「运行第 1 件／第 2 件命令」两步视为已完成，只做章程允许的只读核查（读 summary.txt、git log -1）。
命令非零退出／超时／无标记的，按章程「探针自身异常」「脚本非零退出」分支处理：原样贴出 stderr 末几行，说明需人工核，**不要自行修脚本、不要重试**。
回复写清：① 每件的判定一句；② 非 OK 泳道清单（若探针 [SIGNAL]）；③ 新 master 短号（若巡检 [MERGED]）；④ 非零退出／超时的原因原文。本回复只落在留痕目录的 claude.out，无人会追问——不要提问、不要等待答复。

=== 章程原文（$SkillDoc）===
$skillText

=== 第 1 件 · 探针 stdout（exit=$($probe.exit)，$($probe.ms) ms，判定 $($pj.verdict)）===
$($probe.out)
=== 第 1 件 · 探针 stderr ===
$($probe.err)
=== 第 2 件 · 巡检 stdout（exit=$($patrol.exit)，$($patrol.ms) ms，判定 $($tj.verdict)）===
$($patrol.out)
=== 第 2 件 · 巡检 stderr ===
$($patrol.err)
"@
        $promptFile = Join-Path $roundDir 'prompt.txt'
        Set-Content -Path $promptFile -Value $prompt -Encoding UTF8
        # 🔴 `--allowedTools` 按逗号**和空格**切分，`Bash(git log:*)` 不能与别的规则合成一个逗号串，须各自成参（含空格者由 Invoke-Captured 加引号）
        $claudeArgs = @('-p', '--output-format', 'text', '--allowedTools', 'Read', 'Glob', 'Grep', 'Bash(git log:*)')
        if ($Model) { $claudeArgs += @('--model', $Model) }
        if (-not $ClaudeExe) {
            $claude = @{ exit = -2; ms = 0; out = ''; err = '[GUARD] 找不到 claude CLI（Get-Command claude 为空，且未传 -ClaudeExe）'; timeout = $false }
        } elseif ($ClaudeExe -like '*.ps1') {
            # 单测桩：.ps1 经 pwsh 起，参数原样透传
            $claude = Invoke-Captured -Exe $PwshExe -ArgList (@('-NoProfile', '-NonInteractive', '-File', $ClaudeExe) + $claudeArgs) -Tag 'claude' -TimeoutSec $ClaudeTimeoutSec -StdinFile $promptFile
        } else {
            $claude = Invoke-Captured -Exe $ClaudeExe -ArgList $claudeArgs -Tag 'claude' -TimeoutSec $ClaudeTimeoutSec -StdinFile $promptFile
        }
        Set-Content -Path (Join-Path $roundDir 'claude.out') -Value $claude.out -Encoding UTF8
        Set-Content -Path (Join-Path $roundDir 'claude.err') -Value $claude.err -Encoding UTF8
        $row['woke']   = $true
        $row['claude'] = @{ exit = $claude.exit; ms = $claude.ms; timeout = $claude.timeout }
    }
} catch {
    # 本脚本自身异常也不吞：记进留痕行再退出 2
    $row['guard_error'] = $_.Exception.Message
    $row['total_ms'] = [int]((Get-Date) - $roundStart).TotalMilliseconds
    $null = Write-Trace -Row $row
    Write-Host "[GUARD-ERROR] $($_.Exception.Message)；已留痕 $dayFile"
    $mutex.ReleaseMutex() | Out-Null
    exit 2
}

$row['total_ms'] = [int]((Get-Date) - $roundStart).TotalMilliseconds
$ok = Write-Trace -Row $row
$mutex.ReleaseMutex() | Out-Null

$summary = "[GUARD] round=$roundId dry_run=$([bool]$DryRun) probe=$($pj.verdict)(exit $($probe.exit),$($probe.ms)ms) patrol=$($tj.verdict)(exit $($patrol.exit),$($patrol.ms)ms) signal=$wake woke=$($row['woke'])"
if ($row['woke']) { $summary += " claude_exit=$($row['claude'].exit) claude_ms=$($row['claude'].ms)" }
$summary += " total_ms=$($row['total_ms']) trace=$dayFile"
if ($capture) { $summary += " capture=$capture" }
Write-Host $summary
if (-not $ok) { exit 2 }
exit 0
