# 工具-opener批处理执行v2.ps1 —— 泳道并行版（v2.0，2026-08-25；v2.1，2026-09-10 队列 §一 `#549`：--resume 接管 ＋ -Detach；v2.2，2026-09-10 队列 §一 `#550`：NO-SENTINEL 补问一次；v2.3，2026-09-12 队列 §一 `#397`／`#561`：派出前查队列态，已完成的行 SKIPPED 不派）
# 相对 v1 的唯一结构变化：opener 按「▶ 泳道：<名>」分组——泳道间并行（各起一个后台 Job）、泳道内严格串行。
# 并行判据沿用矩阵纪律：同泳道＝触碰区/资源相斥（SRM 限流、同文件、同信链），跨泳道＝实测零重叠。
# 用法（一行）：
#   powershell -ExecutionPolicy Bypass -File "0-学习与工具\工具-opener批处理执行v2.ps1" -Plan "1-转型规划\0-全景路线图\建造波次-2026-08-25-泳道版.md" -FullAuto -Yes
# 参数同 v1：-Plan / -Only / -DryRun / -FullAuto / -Yes / -Model / -Force；新增 -MaxParallel（默认 3）、-StaggerSec（泳道错峰启动间隔，默认 90，降编辑锁碰撞）、-SentinelRetryTimeoutSec（v2.2，NO-SENTINEL 补问超时秒数，默认 180）
# 判成败双指标不变：claude 退出码 ＋ OPENER_DONE/OPENER_PARTIAL 哨兵；FAIL/NO-SENTINEL 只停本泳道，其余泳道继续。
# 日志：reports/opener-batch/<时间戳>/<泳道>-<编号>.log；结束在同目录写 summary.txt。
#
# v2.1（队列 §一 `#549` ⑴⑵，承接 `#522` ⑷⑸，2026-09-10）：
#   ⑴ --resume 接管：每条 opener 起 claude 前先生成 session id（GUID），以 `--session-id <id>` 传入，
#      并写进该泳道日志**首行**（`session=<id>`）与 summary.txt 的 Session 列 ⇒ 棒停了可用
#      `claude --resume <id>` 接管，不必人工粘贴互动重跑（`#443` 清扫棒因此只能人工跑，是唯一一次必须切 tab 的）。
#   ⑵ -Detach：先建日志目录、再用 Start-Process 把本脚本自身后台起一份（子进程带 -LogDir 指向同一目录），
#      **立即**把日志目录路径打到 stdout 并退出 0，供 Cowork 调用而不占 PowerShell 通道。
#      🔴 子进程退出码不再丢：子进程结束时把退出码写进 <日志目录>\exit.txt（并在 summary.txt 末行 `EXIT=<code>`），
#      launcher.json 记 pid／起跑时刻／计划文件。此前调用方自己用 Start-Process 包一层拿不到退出码，正是本项要消灭的。
#   -LogDir：内部参数（-Detach 子进程用），也可由调用方显式指定日志目录；未给则按时间戳新建。
#
# v2.2（队列 §一 `#550` 重定向棒 `OP-0910-S`，2026-09-10）：哨兵从「注入」改到「强制」
#   立行实证：2026-09-10 四条泳道活全做了却判 NO-SENTINEL——哨兵要求一直由下面前言 ⑤ 注入，
#   是 agent 拿到了没照做（544 把哨兵包在反引号里；507/529 被 claude 自身 600s 后台任务上限掐断在收尾前）。
#   正文里再写一句拦不住 ⇒ 本版在判出 NO-SENTINEL 时**用 `claude --resume <sid>` 补问一次**，
#   prompt 极窄（只要一行哨兵），拿到即按 OK/PARTIAL 记、Sentinel 列标「补问」（🔴 与首轮自觉输出分开计数，
#   summary 末尾 SENTINEL_FIRST/RETRY/NONE 三个数才是真实遵守率）；仍无 ⇒ 仍判 NO-SENTINEL 并停本泳道。
#   🔴 补问自身也是一次 claude 调用、会挂死：每条 opener **只补问一次、不循环**，超时 -SentinelRetryTimeoutSec
#   （默认 180s，明显短于正常泳道）到即 taskkill /T 整棵进程树并判 NO-SENTINEL，不吞。
#   退出码 ≠ 0 的 FAIL 不补问（那是进程层失败，不是遵守问题）。
#
# v2.3（openspec `opener-batch-archive-precheck`，design 决策点 1/2/3 Shao Peishen 2026-09-12 签认 (a)，apply 泳道 OP-0912-Z）：
#   解析完成、-Only 过滤之后、**泳道分组之前** dot-source `工具-opener派出前校验.ps1`，按每个 opener 标题引用的 §一 行号
#   （`队列 #N[／#M]`，多行号取合取）调 `工具-队列查询.py --include-archive --format json` 判四态：live 未 done ⇒ 派；
#   live [S:done] ⇒ SKIPPED（live-done）；已迁归档 ⇒ SKIPPED（archived，不读归档行状态列）；查不到／校验自身失败 ⇒ 告警＋照派（fail-open）。
#   🔴 SKIPPED 在分组前从泳道成员滤除——不起 claude、不产生哨兵、不进 NO-SENTINEL 判定、不停泳道；整泳道被跳空 ⇒ 不 Start-Job、不占并发额、不等 -StaggerSec。
#   SKIPPED 作为第一等状态进汇总表／summary.txt／summary.json（含行号与理由），不影响退出码。-Force ⇒ 全部照派、日志留痕 [Force]。
#
# v2.4（队列 §一 `#584` ⑶b，2026-09-16 `OP-0916-N` 续四，承接 `#584⑵'`/`#584⑶a`）：
#   每条 opener 处理完（claude 进程已退出、子会话理应已按自己【设置】行「worktree：☑（<名>，
#   收工自删」）的纪律清干净）后，本脚本从该 opener 正文抠出它自建的 worktree 名，若那个
#   worktree（及其 `reports/`）还在——说明子会话崩溃/超时/漏做，此前的产出会随 opener骨架.md
#   ⑶a 之前的做法一起随 worktree 被删而无声丢失——就把残留 `reports/` 整棵拷回主工作区
#   `reports/_from-worktree/<泳道>/`，日志留痕（非致命：拷贝失败只记警告，不改变该条判成败）。
#
# v2.5（队列 §一 `#567`，2026-09-20 `OP-0920-D`）：`-Detach` 起跑路径在 PS 5.1 下必炸——
#   ⑴ 子进程 shell 此前继承调用方自己的 `(Get-Process -Id $PID).Path`，调用方若是 5.1 就把
#      5.1 传下去；改为显式优先 `pwsh`、回退 `powershell.exe`，与调用方用什么 shell 起本脚本无关。
#   ⑵ `Start-Job -WorkingDirectory` 是 PS7 专有参数，PS 5.1 直接崩 `NamedParameterNotFound`
#      （既有 `-Detach` 那一支、也有本脚本被直接用 PS 5.1 起时的泳道 `Start-Job` 那一支）；
#      按 `$PSVersionTable.PSVersion.Major` 分支，5.1 改把 `$RepoRoot` 当参数传给 `$laneBlock`，
#      block 首行 `Set-Location` 兜住原参数要解决的「显式定 cwd」语义（否则 `--resume`／补问
#      接管会「No conversation found」）。
#   ⑶ 崩溃发生在参数绑定期，早于任何 `Exit-WithCode` 调用 ⇒ `exit.txt` 此前根本不落盘，调用方
#      只能读 stderr 才知道失败。新增脚本级 `trap`：兜住任何未被捕获的终止性异常，落一个专属
#      退出码（20）并写 `exit.txt`／`launcher-crash.log` 后退出，不改变既有正常退出点的行为。
param(
    [string]$Plan = '',
    [string[]]$Only = @(),
    [switch]$DryRun,
    [switch]$FullAuto,
    [switch]$Yes,
    [string]$Model = 'sonnet',
    [int]$MaxParallel = 3,
    [int]$StaggerSec = 90,
    [switch]$Detach,
    [string]$LogDir = '',
    [int]$SentinelRetryTimeoutSec = 180,
    [switch]$Force
)

$ErrorActionPreference = 'Stop'
$RepoRoot = Split-Path -Parent $PSScriptRoot
# 队列 #600 实测补缺（2026-09-17）：相对 -LogDir 须在切目录前按调用方 cwd 定成绝对路径——泳道 Job 会 Push-Location
# 进 worktree，相对路径随之漂进 worktree，Out-File 找不到目录、泳道在起 claude 前就崩（实测 op0917a 实撞）。
if ($LogDir -and -not [System.IO.Path]::IsPathRooted($LogDir)) { $LogDir = [System.IO.Path]::GetFullPath((Join-Path (Get-Location).Path $LogDir)) }
Set-Location $RepoRoot
$Utf8NoBom = New-Object System.Text.UTF8Encoding $false
$global:OutputEncoding = $Utf8NoBom
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

# -File 方式传 `-Only A1,A2` 到达时是单个字符串，这里统一按逗号拆开（-Detach 子进程走的就是 -File）。
$Only = @($Only | ForEach-Object { $_ -split ',' } | ForEach-Object { $_.Trim() } | Where-Object { $_ })

# 退出码落盘：只要日志目录已定，任何退出点都把 code 写进 exit.txt（-Detach 调用方读它，不猜）。
function Exit-WithCode([int]$code) {
    if ($LogDir) {
        New-Item -ItemType Directory -Path $LogDir -Force | Out-Null
        [System.IO.File]::WriteAllText((Join-Path $LogDir 'exit.txt'), "$code`r`n", $Utf8NoBom)
    }
    exit $code
}

# 队列 #567 并入项 ⑵：`Start-Job -WorkingDirectory` 在 PS 5.1 下崩（`NamedParameterNotFound`）——
# 崩的是参数绑定期的终止性异常，早于任何 `Exit-WithCode` 调用，此前 `exit.txt` 因此根本没生成，
# 调用方只能读 stderr 才知道失败。`trap` 兜住脚本主体里任何未被捕获的终止性异常，落盘一个专属
# 退出码（20）后立即退出——不改变既有的正常 `Exit-WithCode` 调用点，只补「崩溃也落哨兵」这一条路径。
trap {
    $crashMsg = '✗ 未捕获异常：' + $_.Exception.Message + "`r`n" + $_.ScriptStackTrace
    Write-Host $crashMsg -ForegroundColor Red
    if ($LogDir) {
        try {
            New-Item -ItemType Directory -Path $LogDir -Force | Out-Null
            $crashMsg | Out-File -FilePath (Join-Path $LogDir 'launcher-crash.log') -Encoding utf8 -Append
        } catch {}
    }
    Exit-WithCode 20
}

$claudeCmd = Get-Command claude -ErrorAction SilentlyContinue
if (-not $claudeCmd) { Write-Host '✗ 找不到 claude CLI。' -ForegroundColor Red; Exit-WithCode 10 }
if ([string]::IsNullOrWhiteSpace($Plan)) { Write-Host '✗ 请用 -Plan 指定波次计划文件。' -ForegroundColor Red; Exit-WithCode 11 }
if (-not (Test-Path $Plan)) { $Plan = Join-Path $RepoRoot $Plan }
if (-not (Test-Path $Plan)) { Write-Host "✗ 计划文件不存在：$Plan" -ForegroundColor Red; Exit-WithCode 11 }
$Plan = (Resolve-Path $Plan).Path

# ---------- -Detach：后台起自己，立即返回日志目录 ----------
if ($Detach) {
    if (-not $LogDir) { $LogDir = Join-Path $RepoRoot ('reports\opener-batch\' + (Get-Date -Format 'yyyyMMdd-HHmmss')) }
    New-Item -ItemType Directory -Path $LogDir -Force | Out-Null
    $childArgs = @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', $PSCommandPath,
                   '-Plan', $Plan, '-Yes', '-LogDir', $LogDir,
                   '-MaxParallel', $MaxParallel, '-StaggerSec', $StaggerSec,
                   '-SentinelRetryTimeoutSec', $SentinelRetryTimeoutSec)
    if ($FullAuto) { $childArgs += '-FullAuto' }
    if ($DryRun) { $childArgs += '-DryRun' }
    if ($Force) { $childArgs += '-Force' }
    if ($Model) { $childArgs += @('-Model', $Model) }
    if ($Only.Count -gt 0) { $childArgs += @('-Only', ($Only -join ',')) }
    # 队列 #567 ①：子进程 shell 此前继承「谁调用了本脚本」（`(Get-Process -Id $PID).Path`）——
    # 若调用方本身在 PS 5.1（`powershell.exe`）下起本脚本，子进程也落进 5.1，撞见下面
    # `Start-Job -WorkingDirectory`（PS7 专有参数）当场 `NamedParameterNotFound`。改为显式
    # 优先 `pwsh`、回退 `powershell.exe`（系统自带、Start-Process 靠 PATH 即可解析），
    # 不再看调用方自己是用什么 shell 起的。
    $pwshCmd = Get-Command pwsh -ErrorAction SilentlyContinue
    $shell = if ($pwshCmd) { $pwshCmd.Source } else { 'powershell.exe' }
    $proc = Start-Process -FilePath $shell -ArgumentList $childArgs -WorkingDirectory $RepoRoot -PassThru -WindowStyle Hidden `
        -RedirectStandardOutput (Join-Path $LogDir 'launcher-stdout.log') -RedirectStandardError (Join-Path $LogDir 'launcher-stderr.log')
    $launcher = [ordered]@{ pid = $proc.Id; shell = $shell; plan = $Plan; log_dir = $LogDir
                            started_at_utc = (Get-Date).ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ssZ')
                            exit_file = (Join-Path $LogDir 'exit.txt'); summary = (Join-Path $LogDir 'summary.txt') }
    [System.IO.File]::WriteAllText((Join-Path $LogDir 'launcher.json'), ($launcher | ConvertTo-Json), $Utf8NoBom)
    Write-Host ('✓ 已后台起（pid ' + $proc.Id + '）。日志目录：' + $LogDir)
    Write-Host ('  退出码看 ' + (Join-Path $LogDir 'exit.txt') + '；各泳道 session id 看 summary.txt 的 Session 列或各 .log 首行。')
    Write-Output $LogDir
    exit 0
}

# ---------- 解析：### A<N> 标题 → ▶ 泳道 → 代码块 ----------
$lines = [System.IO.File]::ReadAllLines($Plan, $Utf8NoBom)
$fence = [char]0x60 + [char]0x60 + [char]0x60
# 队列 #581 合入前补缺 ⑴：每条 opener【设置】行可带「模型：sonnet｜opus」——同一口径
# 由 `工具-opener生成.py::_settings_line` 落笔（`｜ 模型：<值>`），本正则只按值本身
# 匹配（不锚定前缀「｜」），故手写 opener（无本字段）与生成器产出（有本字段）都解得出。
$modelFieldRe = '模型[：:]\s*([^\s｜\|]+)'
$validModels = @('sonnet', 'opus')
$openers = @()
for ($i = 0; $i -lt $lines.Count; $i++) {
    if ($lines[$i] -match '^###\s+(A\d+)\s*·?\s*(.*)$') {
        $id = $Matches[1]; $title = $Matches[2].Trim(); $paste = ''; $lane = '默认'
        $body = New-Object System.Collections.Generic.List[string]
        $j = $i + 1
        while ($j -lt $lines.Count -and -not ($lines[$j] -match '^###?\s')) {
            if ($lines[$j] -match '粘贴端：\s*(CC|Cowork)') { $paste = $Matches[1] }
            if ($lines[$j] -match '泳道：\s*(\S+)') { $lane = $Matches[1] }
            if ($lines[$j].StartsWith($fence)) {
                $j++
                while ($j -lt $lines.Count -and -not $lines[$j].StartsWith($fence)) { $body.Add($lines[$j]); $j++ }
                break
            }
            $j++
        }
        if ($body.Count -gt 0) {
            # 缺省＝批级 `-Model`；显式合法值覆盖；非法值不在此处报错——留到 laneBlock
            # 判 FAIL 并点名（判成败与报告落在同一处，不在解析期就中断整批解析）。
            $modelRaw = $null
            foreach ($bl in $body) { if ($bl -match $modelFieldRe) { $modelRaw = $Matches[1]; break } }
            if ([string]::IsNullOrEmpty($modelRaw)) {
                $resolvedModel = $Model; $modelInvalid = $false
            } elseif ($validModels -contains $modelRaw) {
                $resolvedModel = $modelRaw; $modelInvalid = $false
            } else {
                $resolvedModel = $null; $modelInvalid = $true
            }
            $openers += [pscustomobject]@{
                Id = $id; Title = $title; Paste = $paste; Lane = $lane; Text = ($body -join "`r`n")
                Model = $resolvedModel; ModelRaw = $modelRaw; ModelInvalid = $modelInvalid
            }
        }
    }
}
if ($openers.Count -eq 0) { Write-Host '✗ 未解析到任何 opener。' -ForegroundColor Red; Exit-WithCode 12 }
$openers = $openers | Sort-Object { [int]($_.Id.Substring(1)) }
if ($Only.Count -gt 0) { $openers = $openers | Where-Object { $Only -contains $_.Id } }
if ($openers.Count -eq 0) { Write-Host '✗ -Only 过滤后为空。' -ForegroundColor Red; Exit-WithCode 12 }

# ---------- v2.3 派出前查队列态（挂点：解析后、-Only 过滤后、泳道分组前；判据只有 Python 一份） ----------
$precheckHelper = Join-Path $PSScriptRoot '工具-opener派出前校验.ps1'
Write-Host ('计划：' + $Plan)
if (Test-Path $precheckHelper) {
    . $precheckHelper
    Write-Host '派出前查队列态（live [S:done]／已迁归档 ⇒ SKIPPED；查不到 ⇒ 照常派出）：'
    $openers = @(Set-OpenerDispatchDecision -Openers @($openers) -RepoRoot $RepoRoot -Force:$Force)
} else {
    # 校验自身不可用 ⇒ fail-open：全部照常派出＋告警（spec「校验自身失败时 fail-open」），绝不因此停批。
    Write-Host ('⚠ 派出前校验 helper 不存在（' + $precheckHelper + '）⇒ 跳过校验、全部照常派出（fail-open）') -ForegroundColor Yellow
    $openers = @($openers | ForEach-Object { $_ | Add-Member -NotePropertyName Skip -NotePropertyValue $false -Force -PassThru | Add-Member -NotePropertyName SkipReason -NotePropertyValue '' -Force -PassThru })
}
$skippedOps = @($openers | Where-Object { $_.Skip })
$openers = @($openers | Where-Object { -not $_.Skip })
if ($skippedOps.Count -gt 0) { Write-Host ('⏭ SKIPPED ' + $skippedOps.Count + ' 个（不起 session、不占泳道）：' + (($skippedOps | ForEach-Object { $_.Id + '［' + $_.SkipReason + '］' }) -join '；')) -ForegroundColor Yellow }

$laneNames = @()
foreach ($op in $openers) { if ($laneNames -notcontains $op.Lane) { $laneNames += $op.Lane } }
Write-Host ('泳道 ' + $laneNames.Count + ' 条（并行上限 ' + $MaxParallel + '，错峰 ' + $StaggerSec + 's）：' + $(if ($laneNames.Count -eq 0) { '（全部 opener 已 SKIPPED，无泳道可起）' } else { '' }))
foreach ($ln in $laneNames) {
    $ids = ($openers | Where-Object { $_.Lane -eq $ln } | ForEach-Object { $_.Id }) -join '→'
    Write-Host ('  ◆ ' + $ln + ' ：' + $ids + '（泳道内串行）')
}
Write-Host ('权限模式：' + $(if ($FullAuto) { 'dangerously-skip-permissions（全自动）' } else { 'acceptEdits' }))
if ($DryRun) { Exit-WithCode 0 }
if (-not $Yes) { $ans = Read-Host '开跑？(y/N)'; if ($ans -ne 'y' -and $ans -ne 'Y') { Exit-WithCode 0 } }

if (-not $LogDir) { $LogDir = Join-Path $RepoRoot ('reports\opener-batch\' + (Get-Date -Format 'yyyyMMdd-HHmmss')) }
New-Item -ItemType Directory -Path $LogDir -Force | Out-Null
$logDir = $LogDir
# v2.4 `#571`⑶：launcher.json 是起跑时刻的正本，此前只有 -Detach 那一支写它 ⇒ `-LogDir` 显式指定的语义名批
# （20260912-portal197／20260913-收口三泳道…）没有正本，收工探针只能退目录 mtime。这里补齐：非 Detach 也写，
# 已有（Detach 父进程先写了）就不覆盖——父进程那份带子进程 pid，更准。
if (-not (Test-Path (Join-Path $logDir 'launcher.json'))) {
    $launcher = [ordered]@{ pid = $PID; shell = (Get-Process -Id $PID).Path; plan = $Plan; log_dir = $logDir
                            started_at_utc = (Get-Date).ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ssZ')
                            exit_file = (Join-Path $logDir 'exit.txt'); summary = (Join-Path $logDir 'summary.txt') }
    [System.IO.File]::WriteAllText((Join-Path $logDir 'launcher.json'), ($launcher | ConvertTo-Json), $Utf8NoBom)
}

$header = @(
    '【无头批处理引导（v2 泳道版）】本 session 由脚本无头启动。五条硬规则：',
    '① 无人在场：凡需 Shao Peishen 拍板/批准/签认的点，登记后停在该点——跟进信最多到「⏳ 待你审」绝不发送；判据/口径/阈值类绝不默认生效；对外真实消息（真人/真群冒烟）一律留步登记、不发。',
    '② 本机当前 off-LAN：凡需 .51 部署、SRM/U9C 真实库访问的步骤，代码与单测照做，该步骤如实登记「LAN 留步」后继续或收工——不得假装闭合，也不得因此判整件失败。aibot 通道走公网可用，不属 LAN 依赖。',
    '③ 若 mcp__ccd_session_mgmt__set_session_title 等工具不存在，跳过继续。',
    '④ 收工必做：回写队列行＋登记 §二 批次（编辑锁纪律照旧）；写后反查。',
    '⑤ 全部完成输出顶格一行 OPENER_DONE；有留步/未尽项改输出 OPENER_PARTIAL: 加一句原因。',
    '────────── 以下为 opener 正文 ──────────'
) -join "`r`n"

# v2.2 `#550`：补问 prompt——极窄，只要一行；点名「顶格、不加反引号」是因为 544 泳道把哨兵写成 `OPENER_DONE`（带反引号）才没命中。
$sentinelRetryPrompt = @(
    '你上一轮没有按收工协议输出哨兵行。**现在只输出一行**，顶格、不加反引号、不加粗、不要解释、不要复述、不要再调用任何工具：',
    '全部完成输出 OPENER_DONE；有留步/未尽项输出 OPENER_PARTIAL: <一句原因>。'
) -join "`r`n"

# 每个泳道一个 Job：泳道内严格串行，FAIL/NO-SENTINEL 停本泳道
$laneBlock = {
    param($laneName, $items, $logDir, $header, $fullAuto, $retryPrompt, $retryTimeoutSec, $claudeExe, $repoRootForJob)
    $Utf8NoBom = New-Object System.Text.UTF8Encoding $false
    $global:OutputEncoding = $Utf8NoBom
    $results = @()
    # Start-Job 起的是独立 runspace，外层脚本作用域的 `$RepoRoot` 变量在此不可见（同 ⑶b 段
    # 既有注释「本脚本…走的是脚本物理落盘位置的仓库根」同一坑）。PS7 下调用方已传 `-WorkingDirectory
    # $RepoRoot`，`Get-Location` 本就落在主仓；PS 5.1 没有该参数（队列 #567 并入项 ⑵：撞见即
    # `NamedParameterNotFound`），改由调用方把 `$RepoRoot` 显式当参数传进来、这里 `Set-Location`
    # 兜住同一语义（`#549` 要解决的「不显式定 cwd，`--resume`／补问接管会 No conversation found」）。
    # 两个版本都过一遍这一步：PS7 下 `Set-Location` 到与 `-WorkingDirectory` 相同的目录、纯冗余不冲突。
    if ($repoRootForJob) { Set-Location $repoRootForJob }
    $repoRootInJob = (Get-Location).Path
    foreach ($op in $items) {
        $log = Join-Path $logDir ($laneName + '-' + $op.Id + '.log')
        # 队列 #581 合入前补缺 ⑴：opener【设置】行模型字段非法值 ⇒ 判 FAIL、不起 claude（不消耗一个 session）。
        if ($op.ModelInvalid) {
            ('[lane:' + $laneName + '] ' + $op.Id + ' ' + $op.Title + ' | 模型字段非法值 ' + $op.ModelRaw + '（须 sonnet｜opus 之一，见 opener【设置】行「模型：」）⇒ 判 FAIL，未起 claude') | Out-File -FilePath $log -Encoding utf8
            $results += [pscustomobject]@{ Lane = $laneName; Id = $op.Id; Status = 'FAIL(model)'; Sentinel = '—'; Minutes = 0; Session = ''; Model = $op.ModelRaw; Log = $log }
            break
        }

        # 队列 #600 ⑴⑵：脚本层强制建隔离 worktree——不再依赖泳道自觉「自己 cd 进去」。
        # 【设置】行「worktree：☑（<名>，...」声明时，起 claude 前先在本仓 `git worktree add`
        # （分支取「分支：」字段里首个反引号包裹的 `claude/...`；分支已存在 ⇒ 检出，否则从 master
        # 新建）；建失败、或声明 ☑ 却解析不出 worktree 名／分支名 ⇒ 判 FAIL、不起 claude；
        # worktree 已在（续棒复用同名 worktree）⇒ 跳过建、直接复用，不重建。
        $wtDeclared = $op.Text -match 'worktree[：:]\s*☑'
        $laneWorktreePath = $null
        $wtNote = $null  # 队列 #600 合入前补缺：worktree 提示延后到 session 首行之后写，守「日志首行＝session」契约（#549）
        if ($wtDeclared) {
            $wtMatch = [regex]::Match($op.Text, 'worktree[：:]\s*☑\s*[（(]\s*([^，,）)]+)')
            if (-not $wtMatch.Success -or [string]::IsNullOrWhiteSpace($wtMatch.Groups[1].Value)) {
                ('[lane:' + $laneName + '] ' + $op.Id + ' ' + $op.Title + ' | 【设置】声明 worktree（☑）但解析不出名字 ⇒ 判 FAIL，未起 claude') | Out-File -FilePath $log -Encoding utf8
                $results += [pscustomobject]@{ Lane = $laneName; Id = $op.Id; Status = 'FAIL(worktree-name)'; Sentinel = '—'; Minutes = 0; Session = ''; Model = $op.Model; Log = $log }
                break
            }
            $wtName = $wtMatch.Groups[1].Value.Trim()
            $laneWorktreePath = Join-Path $repoRootInJob ('.claude\worktrees\' + $wtName)
            $branchFieldMatch = [regex]::Match($op.Text, '分支[：:]\s*([^｜|]+)')
            $branchName = $null
            if ($branchFieldMatch.Success) {
                $bm = [regex]::Match($branchFieldMatch.Groups[1].Value, ([char]0x60) + '(claude/[^' + ([char]0x60) + ']+)' + ([char]0x60))
                if ($bm.Success) { $branchName = $bm.Groups[1].Value.Trim() }
            }
            if (-not $branchName) {
                ('[lane:' + $laneName + '] ' + $op.Id + ' ' + $op.Title + ' | worktree 已声明但「分支：」字段解不出反引号包裹的 claude/ 分支名 ⇒ 判 FAIL，未起 claude') | Out-File -FilePath $log -Encoding utf8
                $results += [pscustomobject]@{ Lane = $laneName; Id = $op.Id; Status = 'FAIL(branch-name)'; Sentinel = '—'; Minutes = 0; Session = ''; Model = $op.Model; Log = $log }
                break
            }
            if (-not (Test-Path -LiteralPath $laneWorktreePath)) {
                & git -C $repoRootInJob rev-parse --verify --quiet ('refs/heads/' + $branchName) *> $null
                $branchExists = ($LASTEXITCODE -eq 0)
                if ($branchExists) {
                    $wtAddOut = & git -C $repoRootInJob worktree add $laneWorktreePath $branchName 2>&1
                } else {
                    $wtAddOut = & git -C $repoRootInJob worktree add -b $branchName $laneWorktreePath master 2>&1
                }
                if ($LASTEXITCODE -ne 0) {
                    ('[lane:' + $laneName + '] ' + $op.Id + ' ' + $op.Title + ' | git worktree add 失败（分支=' + $branchName + '，path=' + $laneWorktreePath + '）⇒ 判 FAIL，未起 claude' + "`r`n" + ($wtAddOut -join "`r`n")) | Out-File -FilePath $log -Encoding utf8
                    $results += [pscustomobject]@{ Lane = $laneName; Id = $op.Id; Status = 'FAIL(worktree-build)'; Sentinel = '—'; Minutes = 0; Session = ''; Model = $op.Model; Log = $log }
                    break
                }
                $wtNote = ('[lane:' + $laneName + '] ' + $op.Id + ' worktree 已建：' + $laneWorktreePath + '（分支 ' + $branchName + $(if ($branchExists) { '，既有分支检出' } else { '，新建自 master' }) + '）')
            } else {
                $wtNote = ('[lane:' + $laneName + '] ' + $op.Id + ' worktree 已存在（复用）：' + $laneWorktreePath)
            }
        }

        # 队列 #600 ⑷：收工核验（第三道闸）——起 claude 前先拍一张主工作区 git 状态快照，供
        # 本条 opener 跑完后比对是否有非白名单脏文件泄漏进主工作区。不论是否声明 worktree 都跑
        # 这一闸：#596/#599 两条实证泄漏正是「opener 未声明 worktree」——第一/二道闸管不到的情形。
        $preLeakSnapshot = @(& git -C $repoRootInJob -c core.quotepath=false status --porcelain)

        $tmp = Join-Path $logDir ($laneName + '-' + $op.Id + '.opener.txt')
        [System.IO.File]::WriteAllText($tmp, $header + "`r`n" + $op.Text, $Utf8NoBom)
        $t0 = Get-Date
        # v2.1 ⑴：session id 由本脚本先定、再交给 claude（--session-id），首行即落盘——
        # 不等 claude 输出再去抓（text 输出格式根本不带 session id），棒停了也接得上。
        $sid = [guid]::NewGuid().ToString()
        $claudeArgs = @('-p', '--output-format', 'text', '--session-id', $sid)
        if ($fullAuto) { $claudeArgs += '--dangerously-skip-permissions' } else { $claudeArgs += @('--permission-mode', 'acceptEdits') }
        # 队列 #581 合入前补缺 ⑴：模型由 opener【设置】行自带（解析期已按批级 `-Model` 兜底），
        # 不再读批级泳道共享的形参——每条 opener 可各自覆盖。
        if ($op.Model) { $claudeArgs += @('--model', $op.Model) }
        ('[lane:' + $laneName + '] ' + $op.Id + ' ' + $op.Title + ' | model=' + $op.Model + ' | session=' + $sid + ' | resume: claude --resume ' + $sid + ' | start=' + $t0.ToString('s')) | Out-File -FilePath $log -Append -Encoding utf8
        if ($wtNote) { $wtNote | Out-File -FilePath $log -Append -Encoding utf8 }
        # 队列 #600 ⑵：claude 子进程的 cwd 与环境标记——worktree 已声明时 cwd 切进该 worktree
        # （Push/Pop-Location；管道调用的子进程 cwd 随宿主 runspace 的 Get-Location 走，
        # 下面的补问 Start-Process 也用同一 `(Get-Location).Path` 取 -WorkingDirectory，故无需
        # 额外改那处），并设 `ZHUOPIN_LANE_WORKTREE`／`ZHUOPIN_MAIN_REPO` 供两道 hooks 写入闸判定
        # （`#600⑶`，6c68fd3）；未声明 worktree 时两个变量都清空，行为与此前完全一致。
        if ($wtDeclared) { Push-Location -LiteralPath $laneWorktreePath }
        try {
            if ($wtDeclared) {
                $env:ZHUOPIN_LANE_WORKTREE = $laneWorktreePath
                $env:ZHUOPIN_MAIN_REPO = $repoRootInJob
            } else {
                Remove-Item Env:\ZHUOPIN_LANE_WORKTREE -ErrorAction SilentlyContinue
                Remove-Item Env:\ZHUOPIN_MAIN_REPO -ErrorAction SilentlyContinue
            }
            Get-Content -Raw -Encoding UTF8 $tmp | & claude @claudeArgs 2>&1 | Out-File -FilePath $log -Append -Encoding utf8
            $code = $LASTEXITCODE
            $t1 = Get-Date
            # 哨兵扫全文（原为 -Tail 40）：2026-08-25 实测 A21/A25 的哨兵落在第 2 行，
            # 只因日志短于 40 行才侥幸命中；日志一长即误判 NO-SENTINEL 并误停整条泳道。
            $tail = Get-Content $log -Encoding UTF8
            $done = [bool]($tail | Where-Object { $_ -match '^OPENER_DONE\s*$' })
            $partial = [bool]($tail | Where-Object { $_ -match '^OPENER_PARTIAL' })
            $status = if ($code -eq 0 -and $done) { 'OK' } elseif ($code -eq 0 -and $partial) { 'PARTIAL' } elseif ($code -eq 0) { 'NO-SENTINEL' } else { 'FAIL(' + $code + ')' }
            # Sentinel 列：首轮＝agent 自觉输出；补问＝靠下面 --resume 追问才拿到；无＝两轮都没有；—＝FAIL（进程层失败，不谈哨兵）。
            $sentinelBy = if ($done -or $partial) { '首轮' } elseif ($code -eq 0) { '无' } else { '—' }
            # >>> #550 补问 begin（变异检验时整段注释掉，NO-SENTINEL 须回来）
            if ($status -eq 'NO-SENTINEL') {
                $retryPromptFile = Join-Path $logDir ($laneName + '-' + $op.Id + '.retry-prompt.txt')
                $retryLog = Join-Path $logDir ($laneName + '-' + $op.Id + '.retry.log')
                $retryErr = Join-Path $logDir ($laneName + '-' + $op.Id + '.retry.err')
                [System.IO.File]::WriteAllText($retryPromptFile, $retryPrompt, $Utf8NoBom)
                $retryArgs = @('-p', '--output-format', 'text', '--resume', $sid)
                if ($fullAuto) { $retryArgs += '--dangerously-skip-permissions' } else { $retryArgs += @('--permission-mode', 'acceptEdits') }
                if ($op.Model) { $retryArgs += @('--model', $op.Model) }
                $tr0 = Get-Date
                ('[lane:' + $laneName + '] ' + $op.Id + ' NO-SENTINEL ⇒ 补问一次：claude ' + ($retryArgs -join ' ') + ' | timeout=' + $retryTimeoutSec + 's | start=' + $tr0.ToString('s')) | Out-File -FilePath $log -Append -Encoding utf8
                $retryOutcome = 'timeout'
                try {
                    # Start-Process 而非管道：管道版没有超时；-PassThru 拿到 pid 才能到点整树 taskkill（claude 会再起 node 子进程）。
                    $proc = Start-Process -FilePath $claudeExe -ArgumentList $retryArgs -WorkingDirectory (Get-Location).Path -PassThru -NoNewWindow `
                        -RedirectStandardInput $retryPromptFile -RedirectStandardOutput $retryLog -RedirectStandardError $retryErr
                    if ($proc.WaitForExit([int]($retryTimeoutSec * 1000))) {
                        $retryOutcome = 'exit=' + $proc.ExitCode
                    } else {
                        & taskkill /PID $proc.Id /T /F 2>&1 | Out-Null
                        $retryOutcome = 'timeout(' + $retryTimeoutSec + 's, killed)'
                    }
                } catch {
                    $retryOutcome = 'error: ' + $_.Exception.Message
                }
                $tr1 = Get-Date
                $retryText = if (Test-Path $retryLog) { Get-Content $retryLog -Encoding UTF8 } else { @() }
                $rDone = [bool]($retryText | Where-Object { $_ -match '^OPENER_DONE\s*$' })
                $rPartial = [bool]($retryText | Where-Object { $_ -match '^OPENER_PARTIAL' })
                if ($rDone) { $status = 'OK'; $sentinelBy = '补问' } elseif ($rPartial) { $status = 'PARTIAL'; $sentinelBy = '补问' }
                ('[lane:' + $laneName + '] ' + $op.Id + ' 补问结果：' + $retryOutcome + ' | sentinel=' + $sentinelBy + ' | status=' + $status + ' | ' + [math]::Round(($tr1 - $tr0).TotalSeconds, 1) + 's | 补问输出见 ' + $retryLog) | Out-File -FilePath $log -Append -Encoding utf8
                $t1 = Get-Date
            }
            # <<< #550 补问 end
        } finally {
            if ($wtDeclared) { Pop-Location }
            Remove-Item Env:\ZHUOPIN_LANE_WORKTREE -ErrorAction SilentlyContinue
            Remove-Item Env:\ZHUOPIN_MAIN_REPO -ErrorAction SilentlyContinue
        }
        # ⑶b（队列 #584 续四）：收工阶段兜底扫描——按【设置】行「worktree：☑（<名>，」抠出
        # 这条 opener 自建的 worktree 名；子会话应已按自己的纪律「收工自删」，但崩溃/超时/
        # 遗忘会漏拷 reports/ 产出，删除前这里补一刀，把残留 reports/（gitignore、worktree
        # 天生没有历史内容，能扫到的都是本次新产出）捞回主工作区 reports/_from-worktree/<泳道>/。
        # 子会话已经删干净 ⇒ Test-Path 为假、本步骤无害跳过，不影响 $status 判定、不写进 break 条件。
        try {
            $wtMatch = [regex]::Match($op.Text, 'worktree[：:]\s*☑\s*[（(]\s*([^，,）)]+)')
            if ($wtMatch.Success) {
                $wtName = $wtMatch.Groups[1].Value.Trim()
                $wtReports = Join-Path (Get-Location).Path ('.claude\worktrees\' + $wtName + '\reports')
                if (Test-Path -LiteralPath $wtReports) {
                    $destDir = Join-Path (Get-Location).Path ('reports\_from-worktree\' + $laneName)
                    New-Item -ItemType Directory -Path $destDir -Force | Out-Null
                    $recovered = 0
                    Get-ChildItem -LiteralPath $wtReports -Recurse -File | ForEach-Object {
                        $rel = $_.FullName.Substring($wtReports.Length).TrimStart('\', '/')
                        $destPath = Join-Path $destDir $rel
                        $destParent = Split-Path $destPath -Parent
                        if (-not (Test-Path -LiteralPath $destParent)) { New-Item -ItemType Directory -Path $destParent -Force | Out-Null }
                        Copy-Item -LiteralPath $_.FullName -Destination $destPath -Force
                        $recovered++
                    }
                    ('[lane:' + $laneName + '] ' + $op.Id + ' worktree 残留回收：' + $wtReports + '（' + $recovered + ' 个文件）→ ' + $destDir) | Out-File -FilePath $log -Append -Encoding utf8
                }
            }
        } catch {
            ('[lane:' + $laneName + '] ' + $op.Id + ' worktree 残留回收失败（非致命，不影响本条判定）：' + $_.Exception.Message) | Out-File -FilePath $log -Append -Encoding utf8
        }
        # 队列 #600 ⑷：收工核验——比对起跑前快照，主工作区新增非白名单脏文件⇒本条判 FAIL、
        # git diff／未跟踪文件原文存补丁到日志目录、日志醒目告警；**不自动撤回**（人工核实
        # 后再决定去留，机制化此前 596/599 两条靠手工 `git diff` 留证的做法，实证见
        # reports/opener-batch/20260916-204736/596-main-leak.patch／599-main-leak.patch）。
        # 🔴 队列 #611 方案 D（2026-09-19）：白名单一次补齐三类——协议〇要求泳道收工必写的
        # `ff-patrol-<yyyyMMdd>.jsonl`＋两份队列物理文件＋`队列行日志/#<N>.md`（K2 外置件）；
        # 判据正本＝本段，`工具-main-leak回放.py` 现取本块、不留第二份硬编码副本。
        $postLeakSnapshot = @(& git -C $repoRootInJob -c core.quotepath=false status --porcelain)
        $newLeakLines = @($postLeakSnapshot | Where-Object { $preLeakSnapshot -notcontains $_ })
        $leakLines = @($newLeakLines | Where-Object {
            $lp = $_.Substring(3)
            if ($lp -match '^"(.*)"$') { $lp = $lp.Substring(1, $lp.Length - 2) }
            if ($lp -match ' -> ') { $lp = ($lp -split ' -> ')[-1] }
            -not (
                $lp -eq 'reports' -or $lp -like 'reports/*' -or
                $lp -eq '1-转型规划/0-全景路线图/合入登记/pending-ff.jsonl' -or
                $lp -like '1-转型规划/0-全景路线图/合入登记/ff-patrol-*.jsonl' -or
                $lp -eq '1-转型规划/0-全景路线图/跨桌任务队列-机制环境.md' -or
                $lp -eq '1-转型规划/0-全景路线图/跨桌任务队列-业务场景.md' -or
                $lp -like '1-转型规划/0-全景路线图/队列行日志/#*.md'
            )
        })
        # 队列 #611 归属判定（2026-09-19 OP-0919-Q，Shao Peishen 答 `1a`）：白名单过滤剩下的
        # 候选，还须证明「该泳道 worktree 实际触碰过」才算它的泄漏——看护者（或任何其它并行
        # 进程）同时段直接写主仓的文件，天然不落在这个集合里，不再被误记成本泳道账。
        # 🔴 判据只认「该泳道自己的分支相对 fork 点新增了什么」＋「worktree 若还在、它自己的
        # 实时 git status」的并集，**不看 git author／不按时间窗切**——`1a` 明确否决了方案
        # `b`（看护者与泳道同身份同时段，两者切不干净，见 `#611` 行内原文）。用分支提交历史
        # 而非只信 worktree 实时状态：泳道常见「收工自删」在先（见上⑶b 段），worktree 目录
        # 届时可能已不在，但分支的提交对象仍在共享 `.git` 里、天然扛得住这个时序。
        # 未声明 worktree（`$wtDeclared` 为假）时没有隔离基线可比，维持改动前的判法：非白名单
        # 一律计入，不因本条新增而放宽。
        if ($wtDeclared -and $leakLines.Count -gt 0) {
            $branchTouched = @{}
            if ($branchName) {
                try {
                    $forkPoint = (& git -C $repoRootInJob merge-base master $branchName 2>$null | Select-Object -First 1)
                    if ($LASTEXITCODE -eq 0 -and $forkPoint) {
                        foreach ($f in (& git -C $repoRootInJob diff --name-only $forkPoint.Trim() $branchName 2>$null)) {
                            if ($f) { $branchTouched[$f] = $true }
                        }
                    }
                } catch { }
            }
            if ($laneWorktreePath -and (Test-Path -LiteralPath $laneWorktreePath)) {
                foreach ($wl in (& git -C $laneWorktreePath -c core.quotepath=false status --porcelain 2>$null)) {
                    if (-not $wl) { continue }
                    $wp = $wl.Substring(3)
                    if ($wp -match '^"(.*)"$') { $wp = $wp.Substring(1, $wp.Length - 2) }
                    if ($wp -match ' -> ') { $wp = ($wp -split ' -> ')[-1] }
                    $branchTouched[$wp] = $true
                }
            }
            $leakLines = @($leakLines | Where-Object {
                $lp = $_.Substring(3)
                if ($lp -match '^"(.*)"$') { $lp = $lp.Substring(1, $lp.Length - 2) }
                if ($lp -match ' -> ') { $lp = ($lp -split ' -> ')[-1] }
                $branchTouched.ContainsKey($lp)
            })
        }
        if ($leakLines.Count -gt 0) {
            $patchPath = Join-Path $logDir ($laneName + '-' + $op.Id + '-main-leak.patch')
            $patchLines = @('# 队列 #600 ⑷ 收工核验：主工作区新增非白名单脏文件，未自动撤回，人工核实后再决定去留', '')
            foreach ($ll in $leakLines) {
                $lp = $ll.Substring(3)
                if ($lp -match '^"(.*)"$') { $lp = $lp.Substring(1, $lp.Length - 2) }
                if ($lp -match ' -> ') { $lp = ($lp -split ' -> ')[-1] }
                if ($ll -match '^\?\?') {
                    $patchLines += ('----- 未跟踪新文件：' + $lp + ' -----')
                    $fullP = Join-Path $repoRootInJob $lp
                    if (Test-Path -LiteralPath $fullP -PathType Leaf) {
                        $patchLines += (Get-Content -LiteralPath $fullP -Raw -Encoding UTF8)
                    }
                } else {
                    $patchLines += ('----- 已跟踪文件改动：' + $lp + ' -----')
                    $patchLines += (& git -C $repoRootInJob diff -- $lp)
                }
            }
            $patchLines -join "`r`n" | Out-File -FilePath $patchPath -Encoding utf8
            $alertMsg = '🔴🔴🔴 [lane:' + $laneName + '] ' + $op.Id + ' 收工核验：主工作区新增非白名单脏文件（第三道闸拦截）⇒ 本条判 FAIL，补丁已存 ' + $patchPath + '，不自动撤回，须人工核实：' + "`r`n" + ($leakLines -join "`r`n")
            $alertMsg | Out-File -FilePath $log -Append -Encoding utf8
            Write-Warning $alertMsg
            $status = 'FAIL(main-leak)'
        }
        $results += [pscustomobject]@{ Lane = $laneName; Id = $op.Id; Status = $status; Sentinel = $sentinelBy; Minutes = [math]::Round(($t1 - $t0).TotalMinutes, 1); Session = $sid; Model = $op.Model; Log = $log }
        if ($status -like 'FAIL*' -or $status -eq 'NO-SENTINEL') { break }
    }
    $results
}

$lanes = @()
foreach ($ln in $laneNames) { $lanes += ,@($ln, @($openers | Where-Object { $_.Lane -eq $ln })) }

$jobs = @{}
$queue = New-Object System.Collections.Queue
foreach ($l in $lanes) { $queue.Enqueue($l) }
$started = 0
while ($queue.Count -gt 0 -or ($jobs.Values | Where-Object { $_.State -eq 'Running' })) {
    while ($queue.Count -gt 0 -and (($jobs.Values | Where-Object { $_.State -eq 'Running' }).Count) -lt $MaxParallel) {
        $l = $queue.Dequeue()
        if ($started -gt 0 -and $StaggerSec -gt 0) { Start-Sleep -Seconds $StaggerSec }
        Write-Host ('━━ 泳道「' + $l[0] + '」启动 ' + (Get-Date -Format 'HH:mm:ss') + '（' + (($l[1] | ForEach-Object { $_.Id }) -join '→') + '）')
        # v2.2 `#550` 顺手实证：泳道 Job 不继承父进程 Set-Location——2026-09-10 四条泳道的 session 全落在
        # `C:\Users\Paul Shao\OneDrive\文档`（Cowork 调用方的 cwd），而 claude 按 cwd 归档 session、`--resume` 也按 cwd 找
        # ⇒ 不显式给 -WorkingDirectory，补问与人工接管都会「No conversation found」。
        # 同批实证：`[bool]$FullAuto` 在参数位是字符串 "[bool]False"（非空 ⇒ 恒真）⇒ 此前 -FullAuto 给不给都 skip-permissions；加括号才是布尔。
        # 队列 #567 并入项 ⑵：`Start-Job -WorkingDirectory` 是 PS7 专有参数，PS 5.1 下当场
        # `NamedParameterNotFound`。PS7 保留原样；PS 5.1 改把 `$RepoRoot` 当普通参数传给
        # `$laneBlock`，block 首行 `Set-Location` 兜住同一「显式定 cwd」语义。
        if ($PSVersionTable.PSVersion.Major -ge 7) {
            $jobs[$l[0]] = Start-Job -WorkingDirectory $RepoRoot -ScriptBlock $laneBlock -ArgumentList $l[0], $l[1], $logDir, $header, ([bool]$FullAuto), $sentinelRetryPrompt, $SentinelRetryTimeoutSec, $claudeCmd.Source, $RepoRoot
        } else {
            $jobs[$l[0]] = Start-Job -ScriptBlock $laneBlock -ArgumentList $l[0], $l[1], $logDir, $header, ([bool]$FullAuto), $sentinelRetryPrompt, $SentinelRetryTimeoutSec, $claudeCmd.Source, $RepoRoot
        }
        $started++
    }
    Start-Sleep -Seconds 20
}

$all = @()
foreach ($k in $jobs.Keys) { $all += Receive-Job -Job $jobs[$k]; Remove-Job -Job $jobs[$k] -Force }
# v2.3：SKIPPED 作为第一等状态并入汇总（Sentinel='—'：未起 session、不谈哨兵；Log 列放跳过理由含行号与命中载体）。
# 队列 #581 合入前补缺 ⑵：Model 列同样带（跳过的也报其本来会用的模型，'—' 表示解析期已判非法）。
foreach ($so in $skippedOps) {
    $skipModel = if ($so.ModelInvalid) { '—' } else { $so.Model }
    $all += [pscustomobject]@{ Lane = $so.Lane; Id = $so.Id; Status = 'SKIPPED'; Sentinel = '—'; Minutes = 0; Session = ''; Model = $skipModel; Log = $so.SkipReason }
}
$all = $all | Sort-Object Lane, { [int]($_.Id.Substring(1)) }
Write-Host ''
Write-Host '━━━━━━ 泳道批处理汇总 ━━━━━━'
$all | Format-Table Lane, Id, Status, Model, Sentinel, Minutes, Session -AutoSize | Out-String -Width 300 | Write-Host
$failed = @($all | Where-Object { $_.Status -like 'FAIL*' -or $_.Status -eq 'NO-SENTINEL' })
$exitCode = if ($failed.Count -gt 0) { 1 } else { 0 }
$summaryText = ($all | Format-Table Lane, Id, Status, Model, Sentinel, Minutes, Session -AutoSize | Out-String -Width 300)
# v2.2 `#550`：哨兵来源三个计数分开落盘——「活干完了却 NO-SENTINEL」应归零，而 RETRY 那个数才是真实遵守率，不得混进 OK 里看不见。
$sentinelFirst = @($all | Where-Object { $_.Sentinel -eq '首轮' }).Count
$sentinelRetry = @($all | Where-Object { $_.Sentinel -eq '补问' }).Count
$sentinelNone = @($all | Where-Object { $_.Sentinel -eq '无' }).Count
$summaryText += "`r`nSENTINEL_FIRST=" + $sentinelFirst + "`r`nSENTINEL_RETRY=" + $sentinelRetry + "`r`nSENTINEL_NONE=" + $sentinelNone
# v2.3：跳过必留痕——summary.txt 逐条写 [skipped] <编号> | <行号 理由@载体:行>，人可直接复核判定。
$skippedRows = @($all | Where-Object { $_.Status -eq 'SKIPPED' })
$summaryText += "`r`nSKIPPED=" + $skippedRows.Count
foreach ($sr in $skippedRows) { $summaryText += "`r`n[skipped] " + $sr.Id + ' | ' + $sr.Log }
if ($sentinelRetry -gt 0) { Write-Host ('⚠ ' + $sentinelRetry + ' 项哨兵靠补问才拿到（首轮未自觉输出）——遵守率看 SENTINEL_FIRST/RETRY，不看 OK 数。') -ForegroundColor Yellow }
# v2.1 ⑵：退出码随 summary 落盘（末行 EXIT=<code>）——-Detach 调用方读文件即得，不必持有子进程句柄。
$summaryText += "`r`nEXIT=" + $exitCode + "`r`n"
[System.IO.File]::WriteAllText((Join-Path $logDir 'summary.txt'), $summaryText, $Utf8NoBom)
# 机读副本：Cowork 取件不必解析表格文本。
# 队列 #567 实测顺手补：`ConvertTo-Json -AsArray` 是 PS7 专有参数，PS 5.1 下同样 `NamedParameterNotFound`
# ——`-AsArray` 本是为了在只有一行时也保证输出是 JSON 数组（无它，1 行会被解包成裸对象）。改手工拼数组
# 括号，两个版本都不依赖该参数、行为一致。
$summaryRows = @($all | Select-Object Lane, Id, Status, Model, Sentinel, Minutes, Session, Log)
$summaryJson = if ($summaryRows.Count -eq 0) { '[]' } else {
    '[' + (($summaryRows | ForEach-Object { $_ | ConvertTo-Json -Compress }) -join ',') + ']'
}
[System.IO.File]::WriteAllText((Join-Path $logDir 'summary.json'), $summaryJson, $Utf8NoBom)
Write-Host ('日志目录：' + $logDir)
if ($failed.Count -gt 0) {
    Write-Host ('✗ ' + $failed.Count + ' 项失败/无哨兵（只停了所在泳道）。续跑：-Only ' + (($failed | ForEach-Object { $_.Id }) -join ',') + ' 加其泳道内后续编号；或 claude --resume <Session> 接管。') -ForegroundColor Red
}
Exit-WithCode $exitCode
