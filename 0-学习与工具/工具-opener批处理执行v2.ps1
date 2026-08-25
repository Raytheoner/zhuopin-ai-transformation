# 工具-opener批处理执行v2.ps1 —— 泳道并行版（v2.0，2026-08-25）
# 相对 v1 的唯一结构变化：opener 按「▶ 泳道：<名>」分组——泳道间并行（各起一个后台 Job）、泳道内严格串行。
# 并行判据沿用矩阵纪律：同泳道＝触碰区/资源相斥（SRM 限流、同文件、同信链），跨泳道＝实测零重叠。
# 用法（一行）：
#   powershell -ExecutionPolicy Bypass -File "0-学习与工具\工具-opener批处理执行v2.ps1" -Plan "1-转型规划\0-全景路线图\建造波次-2026-08-25-泳道版.md" -FullAuto -Yes
# 参数同 v1：-Plan / -Only / -DryRun / -FullAuto / -Yes / -Model；新增 -MaxParallel（默认 3）、-StaggerSec（泳道错峰启动间隔，默认 90，降编辑锁碰撞）
# 判成败双指标不变：claude 退出码 ＋ OPENER_DONE/OPENER_PARTIAL 哨兵；FAIL/NO-SENTINEL 只停本泳道，其余泳道继续。
# 日志：reports/opener-batch/<时间戳>/<泳道>-<编号>.log；结束在同目录写 summary.txt。
param(
    [string]$Plan = '',
    [string[]]$Only = @(),
    [switch]$DryRun,
    [switch]$FullAuto,
    [switch]$Yes,
    [string]$Model = '',
    [int]$MaxParallel = 3,
    [int]$StaggerSec = 90
)

$ErrorActionPreference = 'Stop'
$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot
$Utf8NoBom = New-Object System.Text.UTF8Encoding $false
$global:OutputEncoding = $Utf8NoBom
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$claudeCmd = Get-Command claude -ErrorAction SilentlyContinue
if (-not $claudeCmd) { Write-Host '✗ 找不到 claude CLI。' -ForegroundColor Red; exit 10 }
if ([string]::IsNullOrWhiteSpace($Plan)) { Write-Host '✗ 请用 -Plan 指定波次计划文件。' -ForegroundColor Red; exit 11 }
if (-not (Test-Path $Plan)) { $Plan = Join-Path $RepoRoot $Plan }
if (-not (Test-Path $Plan)) { Write-Host "✗ 计划文件不存在：$Plan" -ForegroundColor Red; exit 11 }

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
if ($openers.Count -eq 0) { Write-Host '✗ 未解析到任何 opener。' -ForegroundColor Red; exit 12 }
$openers = $openers | Sort-Object { [int]($_.Id.Substring(1)) }
if ($Only.Count -gt 0) { $openers = $openers | Where-Object { $Only -contains $_.Id } }
if ($openers.Count -eq 0) { Write-Host '✗ -Only 过滤后为空。' -ForegroundColor Red; exit 12 }

$laneNames = @()
foreach ($op in $openers) { if ($laneNames -notcontains $op.Lane) { $laneNames += $op.Lane } }
Write-Host ('计划：' + $Plan)
Write-Host ('泳道 ' + $laneNames.Count + ' 条（并行上限 ' + $MaxParallel + '，错峰 ' + $StaggerSec + 's）：')
foreach ($ln in $laneNames) {
    $ids = ($openers | Where-Object { $_.Lane -eq $ln } | ForEach-Object { $_.Id }) -join '→'
    Write-Host ('  ◆ ' + $ln + ' ：' + $ids + '（泳道内串行）')
}
Write-Host ('权限模式：' + $(if ($FullAuto) { 'dangerously-skip-permissions（全自动）' } else { 'acceptEdits' }))
if ($DryRun) { exit 0 }
if (-not $Yes) { $ans = Read-Host '开跑？(y/N)'; if ($ans -ne 'y' -and $ans -ne 'Y') { exit 0 } }

$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$logDir = Join-Path $RepoRoot ('reports\opener-batch\' + $stamp)
New-Item -ItemType Directory -Path $logDir -Force | Out-Null

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
        $claudeArgs = @('-p', '--output-format', 'text')
        if ($fullAuto) { $claudeArgs += '--dangerously-skip-permissions' } else { $claudeArgs += @('--permission-mode', 'acceptEdits') }
        if ($model) { $claudeArgs += @('--model', $model) }
        ('[lane:' + $laneName + '] ' + $op.Id + ' ' + $op.Title + ' | start=' + $t0.ToString('s')) | Out-File -FilePath $log -Encoding utf8
        Get-Content -Raw -Encoding UTF8 $tmp | & claude @claudeArgs 2>&1 | Out-File -FilePath $log -Append -Encoding utf8
        $code = $LASTEXITCODE
        $t1 = Get-Date
        $tail = Get-Content $log -Encoding UTF8 -Tail 40
        $done = [bool]($tail | Where-Object { $_ -match '^OPENER_DONE\s*$' })
        $partial = [bool]($tail | Where-Object { $_ -match '^OPENER_PARTIAL' })
        $status = if ($code -eq 0 -and $done) { 'OK' } elseif ($code -eq 0 -and $partial) { 'PARTIAL' } elseif ($code -eq 0) { 'NO-SENTINEL' } else { 'FAIL(' + $code + ')' }
        $results += [pscustomobject]@{ Lane = $laneName; Id = $op.Id; Status = $status; Minutes = [math]::Round(($t1 - $t0).TotalMinutes, 1); Log = $log }
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
$all | Format-Table Lane, Id, Status, Minutes -AutoSize | Out-String | Write-Host
$all | Format-Table Lane, Id, Status, Minutes -AutoSize | Out-String | Out-File -FilePath (Join-Path $logDir 'summary.txt') -Encoding utf8
Write-Host ('日志目录：' + $logDir)
$failed = @($all | Where-Object { $_.Status -like 'FAIL*' -or $_.Status -eq 'NO-SENTINEL' })
if ($failed.Count -gt 0) {
    Write-Host ('✗ ' + $failed.Count + ' 项失败/无哨兵（只停了所在泳道）。续跑：-Only ' + (($failed | ForEach-Object { $_.Id }) -join ',') + ' 加其泳道内后续编号。') -ForegroundColor Red
    exit 1
}
exit 0
