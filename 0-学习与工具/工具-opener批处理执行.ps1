# 工具-opener批处理执行.ps1 —— 把《本周计划》A 节的 N 个 opener 塌缩成一次粘贴（v1，2026-08-24）
# 用法（在本机 PowerShell / Windows Terminal 里，一行）：
#   powershell -ExecutionPolicy Bypass -File "0-学习与工具\工具-opener批处理执行.ps1" -Plan "1-转型规划\0-全景路线图\本周计划-2026-08-24.md" -FullAuto -Yes
# 参数：
#   -Plan       周计划 md（仓库根相对或绝对路径；缺省取 1-转型规划/0-全景路线图/ 下按文件名最新的《本周计划-*.md》）
#   -Only       只跑指定 opener，如 -Only A1,A3（缺省全跑，按编号升序＝计划内既定次序）
#   -DryRun     只解析并列出将要执行的 opener，不执行
#   -FullAuto   传 --dangerously-skip-permissions 给 claude（无人值守可跑完 CC 建造类；不加则默认 acceptEdits，
#               Bash/git 类调用会因无人批准而失败——Cowork 纯 .md 类 opener 可用默认模式）
#   -Yes        跳过开跑前确认
#   -Resume     出错停下后续跑：等价于 -Only <失败项及其后全部>
# 设计要点（对齐项目纪律）：
#   ① 串行执行——天然避开编辑锁并发撞车；每个 opener 独立日志 reports/opener-batch/<日期>/<编号>.log
#   ② 双指标判成败：claude 退出码 ＋ 日志中 OPENER_DONE 哨兵串（防「返回 0 但没干活」的静默回退）
#   ③ 无头引导头：明告 session 无人在场——凡需 Shao Peishen 拍板/批准的点一律登记后停在该点；
#      跟进信只到「⏳ 待你审」绝不发送；判据/口径类绝不默认生效（这两道业务闸不受 -FullAuto 影响）
#   ④ 本脚本自身不改队列、不 commit——各 opener session 按其纪律回写队列/登记 §二 批次，落库交 sweep
param(
    [string]$Plan = '',
    [string[]]$Only = @(),
    [switch]$DryRun,
    [switch]$FullAuto,
    [switch]$Yes,
    [string]$Model = ''
)

$ErrorActionPreference = 'Stop'
$RepoRoot = Split-Path -Parent $PSScriptRoot   # 本脚本位于 0-学习与工具\ 下，上一级即仓库根
Set-Location $RepoRoot

# ---------- 编码（中文管道进出 claude 必须 UTF-8） ----------
$Utf8NoBom = New-Object System.Text.UTF8Encoding $false
$global:OutputEncoding = $Utf8NoBom
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

# ---------- 前提核验 ----------
$claudeCmd = Get-Command claude -ErrorAction SilentlyContinue
if (-not $claudeCmd) { Write-Host '✗ 找不到 claude CLI（不在 PATH）。请先安装 Claude Code。' -ForegroundColor Red; exit 10 }

if ([string]::IsNullOrWhiteSpace($Plan)) {
    $cand = Get-ChildItem (Join-Path $RepoRoot '1-转型规划\0-全景路线图') -Filter '本周计划-*.md' |
        Sort-Object Name -Descending | Select-Object -First 1
    if (-not $cand) { Write-Host '✗ 未找到任何《本周计划-*.md》，请用 -Plan 指定。' -ForegroundColor Red; exit 11 }
    $Plan = $cand.FullName
}
if (-not (Test-Path $Plan)) { $Plan = Join-Path $RepoRoot $Plan }
if (-not (Test-Path $Plan)) { Write-Host "✗ 计划文件不存在：$Plan" -ForegroundColor Red; exit 11 }

# ---------- 解析计划：### A<N> 标题 → 下一个 fenced 代码块 ＝ opener ----------
$lines = [System.IO.File]::ReadAllLines($Plan, $Utf8NoBom)
$fence = [char]0x60 + [char]0x60 + [char]0x60   # ``` （避免脚本源码里出现裸三连反引号）
$openers = @()
for ($i = 0; $i -lt $lines.Count; $i++) {
    if ($lines[$i] -match '^###\s+(A\d+)\s*·?\s*(.*)$') {
        $id = $Matches[1]; $title = $Matches[2].Trim()
        $paste = ''
        $body = New-Object System.Collections.Generic.List[string]
        $j = $i + 1
        while ($j -lt $lines.Count -and -not ($lines[$j] -match '^###?\s')) {
            if ($lines[$j] -match '粘贴端：\s*(CC|Cowork)') { $paste = $Matches[1] }
            if ($lines[$j].StartsWith($fence)) {
                $j++
                while ($j -lt $lines.Count -and -not $lines[$j].StartsWith($fence)) { $body.Add($lines[$j]); $j++ }
                break
            }
            $j++
        }
        if ($body.Count -gt 0) {
            $openers += [pscustomobject]@{ Id = $id; Title = $title; Paste = $paste; Text = ($body -join "`r`n") }
        }
    }
}
if ($openers.Count -eq 0) { Write-Host "✗ 计划文件里没解析到任何『### A<N> ＋ 代码块』形态的 opener：$Plan" -ForegroundColor Red; exit 12 }
$openers = $openers | Sort-Object { [int]($_.Id.Substring(1)) }
if ($Only.Count -gt 0) { $openers = $openers | Where-Object { $Only -contains $_.Id } }
if ($openers.Count -eq 0) { Write-Host '✗ -Only 过滤后为空。' -ForegroundColor Red; exit 12 }

Write-Host ('计划：' + $Plan)
Write-Host ('将按序执行 ' + $openers.Count + ' 个 opener：' + (($openers | ForEach-Object { $_.Id + '(' + $_.Paste + ')' }) -join ' → '))
Write-Host ('权限模式：' + $(if ($FullAuto) { 'dangerously-skip-permissions（全自动）' } else { 'acceptEdits（默认；CC 建造类可能停在命令授权）' }))
if ($DryRun) { $openers | ForEach-Object { Write-Host ('  ' + $_.Id + ' | ' + $_.Paste + ' | ' + $_.Title) }; exit 0 }
if (-not $Yes) {
    $ans = Read-Host '开跑？(y/N)'
    if ($ans -ne 'y' -and $ans -ne 'Y') { Write-Host '已取消。'; exit 0 }
}

# ---------- 执行 ----------
$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$logDir = Join-Path $RepoRoot ('reports\opener-batch\' + $stamp)
New-Item -ItemType Directory -Path $logDir -Force | Out-Null

$header = @(
    '【无头批处理引导（工具-opener批处理执行.ps1 v1）】本 session 由脚本无头启动，等价于人工把下方 opener 粘入对应环境。四条硬规则：',
    '① 无人在场：凡需要 Shao Peishen 拍板/批准/签认的点，一律登记（队列或 README）后停在该点——跟进信最多推进到「⏳ 待你审」、绝不发送；判据/口径/阈值类绝不默认生效。',
    '② 若 mcp__ccd_session_mgmt__set_session_title 等工具不存在，跳过该步继续，不视为失败。',
    '③ 收工必做：按 opener 要求回写队列行＋登记 §二 批次（编辑锁纪律照旧，acquire 与写盘分两步查退出码）；写后反查落盘。',
    '④ 全部完成后，最后单独输出一行（顶格、无其它字符）：OPENER_DONE；若有任何未完成项，改为输出一行 OPENER_PARTIAL: 加一句原因。',
    '────────── 以下为 opener 正文 ──────────'
) -join "`r`n"

$results = @()
$failedAt = ''
foreach ($op in $openers) {
    $log = Join-Path $logDir ($op.Id + '.log')
    $tmp = Join-Path $logDir ($op.Id + '.opener.txt')
    [System.IO.File]::WriteAllText($tmp, $header + "`r`n" + $op.Text, $Utf8NoBom)
    $t0 = Get-Date
    Write-Host ''
    Write-Host ('━━ ' + $op.Id + '（' + $op.Paste + '）开跑 ' + $t0.ToString('HH:mm:ss') + ' ｜ 日志：' + $log)
    $claudeArgs = @('-p', '--output-format', 'text')
    if ($FullAuto) { $claudeArgs += '--dangerously-skip-permissions' } else { $claudeArgs += @('--permission-mode', 'acceptEdits') }
    if ($Model) { $claudeArgs += @('--model', $Model) }
    ('[batch] ' + $op.Id + ' ' + $op.Title + ' | paste=' + $op.Paste + ' | start=' + $t0.ToString('s')) | Out-File -FilePath $log -Encoding utf8
    Get-Content -Raw -Encoding UTF8 $tmp | & claude @claudeArgs 2>&1 | Tee-Object -FilePath $log -Append
    $code = $LASTEXITCODE
    $t1 = Get-Date
    $tail = Get-Content $log -Encoding UTF8 -Tail 40
    $done = [bool]($tail | Where-Object { $_ -match '^OPENER_DONE\s*$' })
    $partial = [bool]($tail | Where-Object { $_ -match '^OPENER_PARTIAL' })
    $status = if ($code -eq 0 -and $done) { 'OK' } elseif ($code -eq 0 -and $partial) { 'PARTIAL' } elseif ($code -eq 0) { 'NO-SENTINEL' } else { 'FAIL(' + $code + ')' }
    $mins = [math]::Round(($t1 - $t0).TotalMinutes, 1)
    $results += [pscustomobject]@{ Id = $op.Id; Paste = $op.Paste; Status = $status; Minutes = $mins; Log = $log }
    Write-Host ('━━ ' + $op.Id + ' 结束：' + $status + '（' + $mins + ' 分钟）')
    if ($status -like 'FAIL*' -or $status -eq 'NO-SENTINEL') {
        $failedAt = $op.Id
        Write-Host ('✗ 在 ' + $op.Id + ' 停下（fail-loud，不带病续跑）。修复后续跑：加参数 -Only ' + (($openers | Where-Object { [int]($_.Id.Substring(1)) -ge [int]($op.Id.Substring(1)) } | ForEach-Object { $_.Id }) -join ',')) -ForegroundColor Red
        break
    }
}

Write-Host ''
Write-Host '━━━━━━ 批处理汇总 ━━━━━━'
$results | Format-Table Id, Paste, Status, Minutes -AutoSize | Out-String | Write-Host
Write-Host ('日志目录：' + $logDir)
Write-Host '跑完后请核对：① 各 opener 的队列行回写与 §二 批次（sweep 每小时自动落库）；② 跟进信仍停在「⏳ 待你审」等你批准；③ NO-SENTINEL 表示退出码 0 但未见 OPENER_DONE——按「工具静默回退」纪律人工读该日志再下结论。'
if ($failedAt) { exit 1 } else { exit 0 }
