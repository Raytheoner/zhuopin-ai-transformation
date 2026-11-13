<#
.SYNOPSIS
  PreToolUse 钩子（队列 §一 `#639` 改判后新增，2026-09-21 `Win-0921-A`）：拦住
  **本会话内完全重复的只读调用**与**同一文件的碎步 Edit**——重复调用不产生任何
  新信息，但每一次的结果都永久进上下文、并在之后每一轮被重读一遍。

.DESCRIPTION
  立行判据＝实测，不是推测。2026-09-20／09-21 两天 25 条会话按 `requestId` 去重后：
    · `cache_read/工具调用` 从 19 次调用时的 60,972 涨到 130 次时的 161,652（贵 2.5 倍）；
    · 完全相同的 (工具,目标) 重复调用占 18–47%（`d8a76b23` 50/105＝47%、
      `d5346e25` 39/130＝30%）；
    · Read 里 40–80% 是重读同一个文件（20/25、15/25、9/16、6/15）；
    · 最贵两条泳道改 5 个文件各用了 31／26 次 Edit（6.2／5.2 次一个文件）。
  按曲线算，去掉重复即可让 `d5346e25` 从 21.0M 降到约 12.5M（−41%）、
  `d8a76b23` 从 17.4M 降到约 5.8M（−67%），且**不切分会话、不改业务代码**。

  🔴 判据只认「目标未变」：Read／Grep 只有在目标文件的 mtime＋size 与上次记录
  **完全一致**时才拒——文件真的变了（自己刚 Edit 过、或泳道并发改了）一律放行，
  不误拦。
  🔴 Bash **只计数、不拦**：命令幂等性没有可靠判据，误拒代价高于收益；本版把
  重复命令记进 audit，作为下一版的立行数据。
  🔴 fail-open：本钩子自身任何异常一律 `exit 0`，不拦主流程（与既有 PreToolUse
  钩子同口径）。
  🔴 逃生阀＝环境变量 `ZHUOPIN_DEDUP_GUARD=off` ⇒ 全放行但照旧计数。A/B 验收的
  Run A 用它取「现状」基线，Run B 不设——**同一份钩子、同一件活，唯一变量是这个
  环境变量**，不存在「装/不装钩子」带来的混淆项。
#>

$ErrorActionPreference = 'Stop'
try { [Console]::OutputEncoding = [Text.UTF8Encoding]::new($false) } catch {}

. (Join-Path $PSScriptRoot 'hooks-common.ps1')

$HookName = 'pretooluse-dedup-guard'

# 同一文件允许的 Edit 次数：第 N+1 次即拒，要求改走一次 MultiEdit。
$EditMaxPerFile = 2

function Get-DedupStatePath {
    param([string]$RepoRoot, [string]$SessionId)
    $dir = Join-Path $RepoRoot 'reports/dedup-guard'
    if (-not (Test-Path -LiteralPath $dir)) { New-Item -ItemType Directory -Force -Path $dir | Out-Null }
    $sid = if ($SessionId) { $SessionId } else { 'unknown-session' }
    $sid = ($sid -replace '[^A-Za-z0-9\-_]', '_')
    return (Join-Path $dir "$sid.json")
}

function Read-DedupState {
    param([string]$Path)
    if (-not (Test-Path -LiteralPath $Path)) { return @{} }
    try {
        $raw = Get-Content -LiteralPath $Path -Raw -Encoding UTF8
        if (-not $raw -or -not $raw.Trim()) { return @{} }
        $obj = $raw | ConvertFrom-Json
        $h = @{}
        foreach ($p in (Get-JsonPropertyNames $obj)) { $h[$p] = $obj.$p }
        return $h
    } catch { return @{} }
}

function Write-DedupState {
    param([string]$Path, [hashtable]$State)
    try {
        $json = $State | ConvertTo-Json -Depth 5 -Compress
        [System.IO.File]::WriteAllText($Path, $json, (New-Object System.Text.UTF8Encoding $false))
    } catch {}
}

function Get-TargetStamp {
    param([string]$Path)
    try {
        if (-not $Path) { return '' }
        $fi = Get-Item -LiteralPath $Path -ErrorAction Stop
        if ($fi.PSIsContainer) { return 'dir' }
        return ('{0}:{1}' -f $fi.LastWriteTimeUtc.Ticks, $fi.Length)
    } catch { return '' }
}

try {
    $stdinRaw = Read-SentinelStdin
    if (-not $stdinRaw -or -not $stdinRaw.Trim()) { exit 0 }
    $json = $stdinRaw | ConvertFrom-Json
    $jsonProps = Get-JsonPropertyNames $json

    $toolName = ''
    if ($jsonProps -contains 'tool_name') { $toolName = [string]$json.tool_name }
    $sessionId = ''
    if ($jsonProps -contains 'session_id') { $sessionId = [string]$json.session_id }
    if ($toolName -notin @('Read', 'Grep', 'Edit', 'Bash')) { exit 0 }

    $repoRoot = Get-SentinelRepoRoot
    $tiProps = Get-JsonPropertyNames $json.tool_input

    $target = ''
    $key = ''
    switch ($toolName) {
        'Read'  { if ($tiProps -contains 'file_path') { $target = [string]$json.tool_input.file_path }; $key = "Read|$target" }
        'Edit'  { if ($tiProps -contains 'file_path') { $target = [string]$json.tool_input.file_path }; $key = "Edit|$target" }
        'Grep'  {
            $pat = ''; $pth = ''
            if ($tiProps -contains 'pattern') { $pat = [string]$json.tool_input.pattern }
            if ($tiProps -contains 'path')    { $pth = [string]$json.tool_input.path }
            $target = $pth; $key = "Grep|$pat|$pth"
        }
        'Bash'  {
            $cmd = ''
            if ($tiProps -contains 'command') { $cmd = ([string]$json.tool_input.command) -replace '\s+', ' ' }
            $key = "Bash|$($cmd.Trim())"
        }
    }
    if (-not $key -or $key -match '^\w+\|$') { exit 0 }

    $statePath = Get-DedupStatePath -RepoRoot $repoRoot -SessionId $sessionId
    $state = Read-DedupState -Path $statePath
    $stamp = Get-TargetStamp -Path $target

    $prev = $null
    if ($state.ContainsKey($key)) { $prev = $state[$key] }
    $prevCount = 0; $prevStamp = ''
    if ($prev) {
        try { $prevCount = [int]$prev.count } catch { $prevCount = 0 }
        try { $prevStamp = [string]$prev.stamp } catch { $prevStamp = '' }
    }

    $off = ($env:ZHUOPIN_DEDUP_GUARD -eq 'off')
    $verdict = 'pass'
    $block = $false
    $msg = ''

    if ($prevCount -ge 1) {
        switch ($toolName) {
            'Read' {
                if ($stamp -and $stamp -eq $prevStamp) {
                    $block = $true
                    $msg = "✗ 重复读门禁：`"$target`" 本会话已读过 $prevCount 次，且文件自那次起**一字未变**（mtime＋size 相同）。" +
                        "它的内容仍在你的上下文里——**回看，不要重读**。确需只看某一段，改用 Grep／`sed -n` 定位后只读 ±40 行。" +
                        "（实测：重复调用占泳道工具调用的 18–47%，每次结果都永久进上下文并在之后每轮被重读；队列 §一 `#639`）"
                }
            }
            'Grep' {
                if ($stamp -and $stamp -eq $prevStamp) {
                    $block = $true
                    $msg = "✗ 重复检索门禁：同一 pattern 与同一 path 本会话已检索过 $prevCount 次，且目标自那次起未变。" +
                        "结果仍在上下文里，回看即可。（队列 §一 `#639`）"
                }
            }
            'Edit' {
                if ($prevCount -ge $EditMaxPerFile) {
                    $block = $true
                    $msg = "✗ 碎步改门禁：`"$target`" 本会话已 Edit $prevCount 次（上限 $EditMaxPerFile）。" +
                        "把**剩下所有改动一次性**走 MultiEdit（或一次 Write 全量重写），不要继续一处一处改。" +
                        "（实测：最贵两条泳道各用 31／26 次 Edit 只改了 5 个文件，6.2／5.2 次一个文件；队列 §一 `#639`）"
                }
            }
            'Bash' {
                # 本版只计数、不拦（命令幂等性无可靠判据）。
                $verdict = 'dup-observed'
            }
        }
    }

    $state[$key] = @{ count = ($prevCount + 1); stamp = $stamp; tool = $toolName }
    Write-DedupState -Path $statePath -State $state

    if ($block -and $off) {
        Add-HooksAuditLine -RepoRoot $repoRoot -Hook $HookName -Verdict 'dup-observed-escape' `
            -Tool $toolName -SessionId $sessionId -Detail "逃生阀 ZHUOPIN_DEDUP_GUARD=off 放行：$key（第 $($prevCount + 1) 次）"
        exit 0
    }
    if ($block) {
        Add-HooksAuditLine -RepoRoot $repoRoot -Hook $HookName -Verdict 'violation' `
            -Tool $toolName -SessionId $sessionId -Detail "$key（第 $($prevCount + 1) 次，目标未变）"
        [Console]::Error.WriteLine($msg)
        exit 2
    }
    Add-HooksAuditLine -RepoRoot $repoRoot -Hook $HookName -Verdict $verdict `
        -Tool $toolName -SessionId $sessionId -Detail "$key（第 $($prevCount + 1) 次）"
    exit 0
} catch {
    # fail-open：钩子自身炸了不许拦主流程
    exit 0
}
