<#
.SYNOPSIS
  Stop 钩子（队列 §一 `#639`，泳道读取面切分）：补写 `hooks-posttooluse-context-meter.ps1`
  的读取盲区——某一轮回复若不含工具调用（纯文本收尾），PostToolUse 永远不会触发，
  那一轮的 usage 就不会被写进 `reports/context-meter/<sid>.json`。本钩子在 Stop 时机
  再读一次 transcript 最新一条 assistant usage，把 `lastContext`／`lastTier` 补齐。

.DESCRIPTION
  判据正本＝队列 §一 `#639` 原文：`工具-opener批处理执行v2.ps1` 据 `lastContext`
  判 150k／250k，实测同一条泳道闸读到 223,309 而 `工具-Token用量度量.py`（逐行扫描
  整份 transcript）算出 230,874，差 7,565；当日四条逐条比对闸均偏低。根因＝
  PostToolUse 这一个读取面只覆盖"有工具调用"的轮次，纯文本收尾轮次的 usage 从未
  被写入过。修法＝新增本钩子作为第二个读取面，两者共用
  `hooks-context-meter-lib.ps1` 的状态读写／档位换算／usage 解析函数——合起来覆盖
  全部轮次，不留盲区。

  🔴 **只补写状态，不提醒**：越线提醒本该在越线的那次 PostToolUse 上出现一次；
  Stop 时机会话已经在收尾，重复提醒没有意义，也会与 `hooks-stop-decision-check.ps1`
  的「需你定夺」格式判据混在同一条 stdout 里增加解析复杂度。本钩子恒不产出
  `additionalContext`，只落审计行与状态文件。

  🔴 **不因 `stop_hook_active` 跳过**：`hooks-stop-decision-check.ps1` 的防循环跳过
  是为了不重复"格式判定"（判定结果不会因重试而变）；本钩子做的是"读当前 transcript
  最新状态并记录"，重试轮次的 transcript 只会更长、usage 只会更新，照常读写无害，
  且补问轮次（v2.ps1 的 NO-SENTINEL 补问）攒的上下文也需要被计入峰值。

  🔴 **阈值 150000／250000 仍是既定政策值，本文件不引用、不判定越线**——只算档位
  存档，越线文案与硬线终止逻辑仍分别在 `hooks-posttooluse-context-meter.ps1` 与
  `工具-opener批处理执行v2.ps1` 里，不在本钩子重复。
#>

$ErrorActionPreference = 'Stop'
try { [Console]::OutputEncoding = [Text.UTF8Encoding]::new($false) } catch {}

. (Join-Path $PSScriptRoot 'hooks-common.ps1')
. (Join-Path $PSScriptRoot 'hooks-context-meter-lib.ps1')

$HookName = 'stop-context-meter'
$script:ThresholdStart = 150000
$script:ThresholdStep = 50000

try {
    $stdinRaw = Read-SentinelStdin
    if (-not $stdinRaw -or -not $stdinRaw.Trim()) { exit 0 }
    $json = $stdinRaw | ConvertFrom-Json
    $jsonProps = Get-JsonPropertyNames $json

    $sessionId = ''
    if ($jsonProps -contains 'session_id') { $sessionId = [string]$json.session_id }
    $transcriptPath = ''
    if ($jsonProps -contains 'transcript_path') { $transcriptPath = [string]$json.transcript_path }

    $repoRoot = Get-SentinelRepoRoot

    if (-not $sessionId -or -not $transcriptPath) {
        Add-HooksAuditLine -RepoRoot $repoRoot -Hook $HookName -Verdict 'undetermined' `
            -SessionId $sessionId -Detail 'stdin 缺 session_id 或 transcript_path'
        exit 0
    }

    $state = Read-ContextMeterState -RepoRoot $repoRoot -SessionId $sessionId
    $usage = Get-LatestAssistantUsage -TranscriptPath $transcriptPath
    if (-not $usage.Ok) {
        Add-HooksAuditLine -RepoRoot $repoRoot -Hook $HookName -Verdict 'error' `
            -SessionId $sessionId -Detail $usage.Error
        exit 0
    }

    $context = $usage.Context
    $tier = Get-ContextTier -Context $context -ThresholdStart $script:ThresholdStart -ThresholdStep $script:ThresholdStep
    $tierToWrite = if ($tier -gt $state.LastTier) { $tier } else { $state.LastTier }

    Write-ContextMeterState -RepoRoot $repoRoot -SessionId $sessionId `
        -Tier $tierToWrite -Context $context -ToolCalls $state.ToolCalls -CallCountNotified $state.CallCountNotified

    Add-HooksAuditLine -RepoRoot $repoRoot -Hook $HookName -Verdict 'pass' `
        -SessionId $sessionId -Detail "Stop 读取面补写：上下文约 $context（PostToolUse 此前记到 $($state.LastContext)，档位 $($state.LastTier) → $tierToWrite）"
    exit 0
} catch {
    try {
        Add-HooksAuditLine -RepoRoot (Get-SentinelRepoRoot) -Hook $HookName -Verdict 'error' `
            -Detail $_.Exception.Message
    } catch { }
    exit 0
}
