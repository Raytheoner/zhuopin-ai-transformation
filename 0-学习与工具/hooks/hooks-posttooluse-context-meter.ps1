<#
.SYNOPSIS
  PostToolUse 钩子（队列 §一 #582，Token 优化 Phase 2B）：只读 transcript 尾部，
  取最近一条 assistant 消息的 usage（input + cache_creation + cache_read）＝当前
  上下文估算值；越过 150k 首次、此后每 +50k 各提醒一次（同档不重复），提醒文案
  写死转场动作。未越线静默无输出，任何异常静默放行、不拦工具。

.DESCRIPTION
  判据正本＝队列 §一 #582 原文 ＋ `构建Token消耗优化-核验与路线图-2026-09-16.md`
  Phase 2B。

  🔴 **只读尾部，不全量解析 transcript**：用 `Get-Content -Tail N` 从文件末尾按行
  倒序取一小段窗口，在窗口内找最近一条 `type=assistant` 记录；找不到才把窗口翻倍
  重试（有限次数封顶），绝不对整份 transcript 做全量 `Get-Content -Raw`。这是
  `hooks-stop-decision-check.ps1`（全量 StreamReader 顺读）与本钩子的关键差异——
  那份钩子早于本次性能指标（p95 < 300ms）立项，不作为本钩子的参照写法。

  🔴 **提醒判据 ＝ 门槛分档，不是"是否越线"这一个布尔**：`Get-ContextTier` 把
  上下文换算成档位（<150k ＝ 0 档，[150k,200k) ＝ 1 档，[200k,250k) ＝ 2 档……），
  状态文件只记"已提醒到的最高档"；本次档位 > 已记档位才提醒并推进状态，否则静默。
  这样"同档不重复"与"跨档必提醒"是同一条比较，不需要分别写两条判据。

.NOTES
  transcript 记录 schema（本机实测确认，字段名与 `message.usage.*` 路径）：
  `{"type":"assistant","sessionId":"...","message":{"usage":{"input_tokens":N,
  "cache_creation_input_tokens":N,"cache_read_input_tokens":N,...}}}`。
#>

$ErrorActionPreference = 'Stop'
try { [Console]::OutputEncoding = [Text.UTF8Encoding]::new($false) } catch {}

. (Join-Path $PSScriptRoot 'hooks-common.ps1')

$HookName = 'posttooluse-context-meter'
$script:ThresholdStart = 150000
$script:ThresholdStep = 50000
$script:HardLine = 250000  # 09-16 他拍 1a：150k 软提醒／250k 硬线
# 窗口倍增序列：先按小窗口试（覆盖绝大多数一轮一次工具调用的常态），找不到再翻倍——
# 封顶 20000 行，避免一份"连续几万行都没有 assistant 记录"的畸形 transcript 把钩子拖垮。
$script:TailWindowSizes = @(200, 2000, 20000)


function Get-ContextMeterStateDir([string]$RepoRoot) {
    Join-Path $RepoRoot 'reports/context-meter'
}

function Get-ContextMeterStatePath([string]$RepoRoot, [string]$SessionId) {
    # session_id 正常形态是 GUID，仍做一次白名单清洗防越权路径拼接。
    $safe = ($SessionId -replace '[^A-Za-z0-9_-]', '_')
    if (-not $safe) { $safe = 'unknown' }
    Join-Path (Get-ContextMeterStateDir $RepoRoot) "$safe.json"
}

function Read-ContextMeterState([string]$RepoRoot, [string]$SessionId) {
    $path = Get-ContextMeterStatePath -RepoRoot $RepoRoot -SessionId $SessionId
    $result = @{ LastTier = 0 }
    if (-not (Test-Path -LiteralPath $path)) { return $result }
    try {
        $obj = (Get-Content -LiteralPath $path -Raw -Encoding UTF8) | ConvertFrom-Json
        if ((Get-JsonPropertyNames $obj) -contains 'lastTier') { $result.LastTier = [int]$obj.lastTier }
    } catch {
        # 状态文件损坏 ⇒ 当作从未提醒过（更保守的一侧：宁可多提醒一次，也不能因为
        # 一份坏 JSON 就此再也不提醒）。
    }
    return $result
}

function Write-ContextMeterState([string]$RepoRoot, [string]$SessionId, [int]$Tier, [long]$Context) {
    try {
        $dir = Get-ContextMeterStateDir $RepoRoot
        if (-not (Test-Path -LiteralPath $dir)) { New-Item -ItemType Directory -Path $dir -Force | Out-Null }
        $path = Get-ContextMeterStatePath -RepoRoot $RepoRoot -SessionId $SessionId
        $obj = [ordered]@{
            lastTier    = $Tier
            lastContext = $Context
            lastTs      = (Get-SentinelTimestamp)
        }
        $tmp = "$path.tmp"
        $obj | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath $tmp -Encoding UTF8
        Move-Item -LiteralPath $tmp -Destination $path -Force
    } catch {
        # 状态写不了也不能打断宿主钩子——fail-open 是本框架第一原则。
    }
}

function Get-ContextTier([long]$Context) {
    if ($Context -lt $script:ThresholdStart) { return 0 }
    return ([int][math]::Floor(($Context - $script:ThresholdStart) / $script:ThresholdStep)) + 1
}

function Get-LatestAssistantUsage([string]$TranscriptPath) {
    <# 返回 @{ Ok=$bool; Context=[long]; Error=$string }。只读尾部窗口，找到即停。 #>
    $result = @{ Ok = $false; Context = 0L; Error = '' }
    if (-not $TranscriptPath -or -not (Test-Path -LiteralPath $TranscriptPath -PathType Leaf)) {
        $result.Error = "transcript 文件不存在：$TranscriptPath"
        return $result
    }

    foreach ($tailN in $script:TailWindowSizes) {
        $lines = @(Get-Content -LiteralPath $TranscriptPath -Tail $tailN -Encoding UTF8 -ErrorAction Stop)
        for ($i = $lines.Count - 1; $i -ge 0; $i--) {
            $line = $lines[$i]
            if (-not $line -or -not $line.Trim()) { continue }
            try {
                $obj = $line | ConvertFrom-Json
            } catch {
                continue
            }
            $objProps = Get-JsonPropertyNames $obj
            if (-not ($objProps -contains 'type') -or [string]$obj.type -ne 'assistant') { continue }
            if (-not ($objProps -contains 'message')) { continue }
            $msgProps = Get-JsonPropertyNames $obj.message
            if (-not ($msgProps -contains 'usage')) { continue }
            $usageProps = Get-JsonPropertyNames $obj.message.usage
            if (-not ($usageProps -contains 'input_tokens') `
                    -or -not ($usageProps -contains 'cache_creation_input_tokens') `
                    -or -not ($usageProps -contains 'cache_read_input_tokens')) { continue }

            $ctx = [long]$obj.message.usage.input_tokens `
                + [long]$obj.message.usage.cache_creation_input_tokens `
                + [long]$obj.message.usage.cache_read_input_tokens
            $result.Ok = $true
            $result.Context = $ctx
            return $result
        }
        # 若这个窗口已经等于全文件行数（文件比窗口还短）却仍没找到，再放大窗口也没用。
        if ($lines.Count -lt $tailN) { break }
    }

    $result.Error = 'transcript 尾部窗口内未找到含 usage 的 assistant 记录（已放宽至最大窗口）'
    return $result
}

function Write-HookMessage([string]$msg) {
    $payload = @{
        hookSpecificOutput = @{
            hookEventName     = 'PostToolUse'
            additionalContext = $msg
        }
    }
    $payload | ConvertTo-Json -Depth 5 -Compress
}

try {
    $stdinRaw = Read-SentinelStdin
    if (-not $stdinRaw -or -not $stdinRaw.Trim()) { exit 0 }
    $json = $stdinRaw | ConvertFrom-Json
    $jsonProps = Get-JsonPropertyNames $json

    $sessionId = ''
    if ($jsonProps -contains 'session_id') { $sessionId = [string]$json.session_id }
    $toolName = ''
    if ($jsonProps -contains 'tool_name') { $toolName = [string]$json.tool_name }
    $transcriptPath = ''
    if ($jsonProps -contains 'transcript_path') { $transcriptPath = [string]$json.transcript_path }

    $repoRoot = Get-SentinelRepoRoot

    if (-not $sessionId -or -not $transcriptPath) {
        Add-HooksAuditLine -RepoRoot $repoRoot -Hook $HookName -Verdict 'undetermined' `
            -Tool $toolName -SessionId $sessionId -Detail 'stdin 缺 session_id 或 transcript_path'
        exit 0
    }

    $usage = Get-LatestAssistantUsage -TranscriptPath $transcriptPath
    if (-not $usage.Ok) {
        Add-HooksAuditLine -RepoRoot $repoRoot -Hook $HookName -Verdict 'error' `
            -Tool $toolName -SessionId $sessionId -Detail $usage.Error
        exit 0
    }

    $context = $usage.Context
    $tier = Get-ContextTier -Context $context
    if ($tier -eq 0) {
        Add-HooksAuditLine -RepoRoot $repoRoot -Hook $HookName -Verdict 'pass' `
            -Tool $toolName -SessionId $sessionId -Detail "未越线，当前上下文约 $context"
        exit 0
    }

    $state = Read-ContextMeterState -RepoRoot $repoRoot -SessionId $sessionId
    if ($tier -le $state.LastTier) {
        Add-HooksAuditLine -RepoRoot $repoRoot -Hook $HookName -Verdict 'pass' `
            -Tool $toolName -SessionId $sessionId -Detail "档位 $tier 已提醒过（当前上下文约 $context），本次不重复"
        exit 0
    }

    Write-ContextMeterState -RepoRoot $repoRoot -SessionId $sessionId -Tier $tier -Context $context

    $kDisplay = [math]::Round($context / 1000)
    if ($context -ge $script:HardLine) {
        $msg = "当前上下文 ≈${kDisplay}k，已越 250k 硬线：立即收尾——commit 已有增量、写接力卡、交接后结束本会话；" +
               "无头泳道以 ``OPENER_PARTIAL: 上下文转场（≈${kDisplay}k）`` 收尾"
    } else {
        $msg = "当前上下文 ≈${kDisplay}k，已越 150k 软提醒线：先把当前里程碑做完（至少 commit 一个可验证增量）再收尾交接，" +
               "不要在零产出时停下；无头泳道交接时以 ``OPENER_PARTIAL: 上下文转场（≈${kDisplay}k）`` 收尾。此后大文件先 grep 定位再分段读、重输出交子代理；250k 为硬线，届时须立即收尾"
    }
    Write-HookMessage $msg

    Add-HooksAuditLine -RepoRoot $repoRoot -Hook $HookName -Verdict 'remind' `
        -Tool $toolName -SessionId $sessionId -Detail "档位 $tier 首次越线，当前上下文约 $context"
    exit 0
} catch {
    try {
        Add-HooksAuditLine -RepoRoot (Get-SentinelRepoRoot) -Hook $HookName -Verdict 'error' `
            -Detail $_.Exception.Message
    } catch { }
    exit 0
}
