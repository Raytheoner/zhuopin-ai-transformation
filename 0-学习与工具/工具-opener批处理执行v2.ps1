# 工具-opener批处理执行v2.ps1 —— 泳道并行版（v2.0，2026-08-25；v2.1，2026-09-10 队列 §一 `#549`：--resume 接管 ＋ -Detach）
# 相对 v1 的唯一结构变化：opener 按「▶ 泳道：<名>」分组——泳道间并行（各起一个后台 Job）、泳道内严格串行。
# 并行判据沿用矩阵纪律：同泳道＝触碰区/资源相斥（SRM 限流、同文件、同信链），跨泳道＝实测零重叠。
# 用法（一行）：
#   powershell -ExecutionPolicy Bypass -File "0-学习与工具\工具-opener批处理执行v2.ps1" -Plan "1-转型规划\0-全景路线图\建造波次-2026-08-25-泳道版.md" -FullAuto -Yes
# 参数同 v1：-Plan / -Only / -DryRun / -FullAuto / -Yes / -Model；新增 -MaxParallel（默认 3）、-StaggerSec（泳道错峰启动间隔，默认 90，降编辑锁碰撞）
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
param(
    [string]$Plan = '',
    [string[]]$Only = @(),
    [switch]$DryRun,
    [switch]$FullAuto,
    [switch]$Yes,
    [string]$Model = '',
    [int]$MaxParallel = 3,
    [int]$StaggerSec = 90,
    [switch]$Detach,
    [string]$LogDir = ''
)

$ErrorActionPreference = 'Stop'
$RepoRoot = Split-Path -Parent $PSScriptRoot
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
                   '-MaxParallel', $MaxParallel, '-StaggerSec', $StaggerSec)
    if ($FullAuto) { $childArgs += '-FullAuto' }
    if ($DryRun) { $childArgs += '-DryRun' }
    if ($Model) { $childArgs += @('-Model', $Model) }
    if ($Only.Count -gt 0) { $childArgs += @('-Only', ($Only -join ',')) }
    $shell = (Get-Process -Id $PID).Path
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
            $openers += [pscustomobject]@{ Id = $id; Title = $title; Paste = $paste; Lane = $lane; Text = ($body -join "`r`n") }
        }
    }
}
if ($openers.Count -eq 0) { Write-Host '✗ 未解析到任何 opener。' -ForegroundColor Red; Exit-WithCode 12 }
$openers = $openers | Sort-Object { [int]($_.Id.Substring(1)) }
if ($Only.Count -gt 0) { $openers = $openers | Where-Object { $Only -contains $_.Id } }
if ($openers.Count -eq 0) { Write-Host '✗ -Only 过滤后为空。' -ForegroundColor Red; Exit-WithCode 12 }

$laneNames = @()
foreach ($op in $openers) { if ($laneNames -notcontains $op.Lane) { $laneNames += $op.Lane } }
Write-Host ('计划：' + $Plan)
Write-Host ('泳道 ' + $laneNames.Count + ' 条（并行上限 ' + $MaxParallel + '，错峰 ' + $StaggerSec + 's）：')
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

$header = @(
    '【无头批处理引导（v2 泳道版）】本 session 由脚本无头启动。五条硬规则：',
    '① 无人在场：凡需 Shao Peishen 拍板/批准/签认的点，登记后停在该点——跟进信最多到「⏳ 待你审」绝不发送；判据/口径/阈值类绝不默认生效；对外真实消息（真人/真群冒烟）一律留步登记、不发。',
    '② 本机当前 off-LAN：凡需 .51 部署、SRM/U9C 真实库访问的步骤，代码与单测照做，该步骤如实登记「LAN 留步」后继续或收工——不得假装闭合，也不得因此判整件失败。aibot 通道走公网可用，不属 LAN 依赖。',
    '③ 若 mcp__ccd_session_mgmt__set_session_title 等工具不存在，跳过继续。',
    '④ 收工必做：回写队列行＋登记 §二 批次（编辑锁纪律照旧）；写后反查。',
    '⑤ 全部完成输出顶格一行 OPENER_DONE；有留步/未尽项改输出 OPENER_PARTIAL: 加一句原因。',
    '────────── 以下为 opener 正文 ──────────'
) -join "`r`n"

# 每个泳道一个 Job：泳道内严格串行，FAIL/NO-SENTINEL 停本泳道
$laneBlock = {
    param($laneName, $items, $logDir, $header, $fullAuto, $model)
    $Utf8NoBom = New-Object System.Text.UTF8Encoding $false
    $global:OutputEncoding = $Utf8NoBom
    $results = @()
    foreach ($op in $items) {
        $log = Join-Path $logDir ($laneName + '-' + $op.Id + '.log')
        $tmp = Join-Path $logDir ($laneName + '-' + $op.Id + '.opener.txt')
        [System.IO.File]::WriteAllText($tmp, $header + "`r`n" + $op.Text, $Utf8NoBom)
        $t0 = Get-Date
        # v2.1 ⑴：session id 由本脚本先定、再交给 claude（--session-id），首行即落盘——
        # 不等 claude 输出再去抓（text 输出格式根本不带 session id），棒停了也接得上。
        $sid = [guid]::NewGuid().ToString()
        $claudeArgs = @('-p', '--output-format', 'text', '--session-id', $sid)
        if ($fullAuto) { $claudeArgs += '--dangerously-skip-permissions' } else { $claudeArgs += @('--permission-mode', 'acceptEdits') }
        if ($model) { $claudeArgs += @('--model', $model) }
        ('[lane:' + $laneName + '] ' + $op.Id + ' ' + $op.Title + ' | session=' + $sid + ' | resume: claude --resume ' + $sid + ' | start=' + $t0.ToString('s')) | Out-File -FilePath $log -Encoding utf8
        Get-Content -Raw -Encoding UTF8 $tmp | & claude @claudeArgs 2>&1 | Out-File -FilePath $log -Append -Encoding utf8
        $code = $LASTEXITCODE
        $t1 = Get-Date
        # 哨兵扫全文（原为 -Tail 40）：2026-08-25 实测 A21/A25 的哨兵落在第 2 行，
        # 只因日志短于 40 行才侥幸命中；日志一长即误判 NO-SENTINEL 并误停整条泳道。
        $tail = Get-Content $log -Encoding UTF8
        $done = [bool]($tail | Where-Object { $_ -match '^OPENER_DONE\s*$' })
        $partial = [bool]($tail | Where-Object { $_ -match '^OPENER_PARTIAL' })
        $status = if ($code -eq 0 -and $done) { 'OK' } elseif ($code -eq 0 -and $partial) { 'PARTIAL' } elseif ($code -eq 0) { 'NO-SENTINEL' } else { 'FAIL(' + $code + ')' }
        $results += [pscustomobject]@{ Lane = $laneName; Id = $op.Id; Status = $status; Minutes = [math]::Round(($t1 - $t0).TotalMinutes, 1); Session = $sid; Log = $log }
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
        $jobs[$l[0]] = Start-Job -ScriptBlock $laneBlock -ArgumentList $l[0], $l[1], $logDir, $header, [bool]$FullAuto, $Model
        $started++
    }
    Start-Sleep -Seconds 20
}

$all = @()
foreach ($k in $jobs.Keys) { $all += Receive-Job -Job $jobs[$k]; Remove-Job -Job $jobs[$k] -Force }
$all = $all | Sort-Object Lane, { [int]($_.Id.Substring(1)) }
Write-Host ''
Write-Host '━━━━━━ 泳道批处理汇总 ━━━━━━'
$all | Format-Table Lane, Id, Status, Minutes, Session -AutoSize | Out-String -Width 300 | Write-Host
$failed = @($all | Where-Object { $_.Status -like 'FAIL*' -or $_.Status -eq 'NO-SENTINEL' })
$exitCode = if ($failed.Count -gt 0) { 1 } else { 0 }
$summaryText = ($all | Format-Table Lane, Id, Status, Minutes, Session -AutoSize | Out-String -Width 300)
# v2.1 ⑵：退出码随 summary 落盘（末行 EXIT=<code>）——-Detach 调用方读文件即得，不必持有子进程句柄。
$summaryText += "`r`nEXIT=" + $exitCode + "`r`n"
[System.IO.File]::WriteAllText((Join-Path $logDir 'summary.txt'), $summaryText, $Utf8NoBom)
# 机读副本：Cowork 取件不必解析表格文本。
[System.IO.File]::WriteAllText((Join-Path $logDir 'summary.json'), (@($all | Select-Object Lane, Id, Status, Minutes, Session, Log) | ConvertTo-Json -AsArray), $Utf8NoBom)
Write-Host ('日志目录：' + $logDir)
if ($failed.Count -gt 0) {
    Write-Host ('✗ ' + $failed.Count + ' 项失败/无哨兵（只停了所在泳道）。续跑：-Only ' + (($failed | ForEach-Object { $_.Id }) -join ',') + ' 加其泳道内后续编号；或 claude --resume <Session> 接管。') -ForegroundColor Red
}
Exit-WithCode $exitCode
