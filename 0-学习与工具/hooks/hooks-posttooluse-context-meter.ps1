<#
.SYNOPSIS
  PostToolUse 钩子（队列 §一 #582／#598，Token 优化 Phase 2B／P2）：只读 transcript
  尾部，取最近一条 assistant 消息的 usage（input + cache_creation + cache_read）＝
  当前上下文估算值；越过 150k 首次、此后每 +50k 各提醒一次（同档不重复），提醒文案
  写死转场动作。**另加一条独立维度**：单会话工具调用次数达 150 次时提醒一次（一次性，
  不随档位重复），提示看护会话逐轮自查请求数偏高、改用 `wait` 子命令阻塞轮询。两条
  维度各自独立判据、可同批合并进同一条 `additionalContext`；仅提醒不拦截，未触发任一
  条件静默无输出，任何异常静默放行、不拦工具。

.DESCRIPTION
  判据正本＝队列 §一 #582／#598 原文 ＋ `构建Token消耗优化-核验与路线图-2026-09-16.md`
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

  🔴 **工具调用计数与上下文档位是两条独立轴，不合并成一个数字**：档位管"这次对话
  攒了多少上下文"，计数管"这个会话来回调了多少次工具"——看护轮询场景里后者可能
  先于前者告警（每 15 秒自己查一次心跳，上下文没涨多少，但请求数已经很高）。
  两条轴各自维护自己的"已提醒"标记（`lastTier` vs `callCountNotified`），互不影响；
  同一次调用若两条都命中，合并进同一条 `additionalContext`（换行分隔），不拆两次
  hook 输出——宿主每次只读一份 `hookSpecificOutput`。**计数无衰减、不分档、只提醒
  一次**：它的作用是"提醒改用 wait 工具"，不是持续告警，改了之后没有再吵的必要。

.NOTES
  transcript 记录 schema（本机实测确认，字段名与 `message.usage.*` 路径）：
  `{"type":"assistant","sessionId":"...","message":{"usage":{"input_tokens":N,
  "cache_creation_input_tokens":N,"cache_read_input_tokens":N,...}}}`。

  🔴 **读取面盲区（队列 §一 `#639`）＋修法**：本钩子只在工具调用后触发——若某一轮
  回复不含工具调用（纯文本收尾）就直接进 Stop，那一轮 usage 永远不会被本钩子读到，
  状态文件的 `lastContext` 因此持续低估真实峰值。状态读写、档位换算、usage 解析
  已抽到 `hooks-context-meter-lib.ps1`，与新增的 Stop 读取面
  `hooks-stop-context-meter.ps1` 共用——两个读取面合起来覆盖"有工具调用"与
  "纯文本收尾"两种轮次，不留盲区；本钩子自身逻辑不变。
#>

$ErrorActionPreference = 'Stop'
try { [Console]::OutputEncoding = [Text.UTF8Encoding]::new($false) } catch {}

. (Join-Path $PSScriptRoot 'hooks-common.ps1')
. (Join-Path $PSScriptRoot 'hooks-context-meter-lib.ps1')

$HookName = 'posttooluse-context-meter'
$script:ThresholdStart = 150000
$script:ThresholdStep = 50000
$script:HardLine = 250000  # 09-16 他拍 1a：150k 软提醒／250k 硬线
$script:CallCountThreshold = 150  # #598：单会话工具调用数达此值提醒一次（一次性、不分档）

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

    # ---- 计数轴：与上下文档位轴各自独立，先算、先决定要不要提醒 ----
    $state = Read-ContextMeterState -RepoRoot $repoRoot -SessionId $sessionId
    $toolCalls = $state.ToolCalls + 1
    $countJustCrossed = ($state.ToolCalls -lt $script:CallCountThreshold) `
        -and ($toolCalls -ge $script:CallCountThreshold) -and (-not $state.CallCountNotified)
    $callCountNotified = $state.CallCountNotified -or $countJustCrossed

    $messages = New-Object System.Collections.Generic.List[string]
    if ($countJustCrossed) {
        $messages.Add(
            "本会话工具调用已达 $toolCalls 次，请求数偏高：若在逐轮自查心跳／summary／进程，" +
            "改用 ``0-学习与工具/工具-泳道看护等待.py wait --batch <批次>`` 一次阻塞轮询到事件，减少来回调用。"
        )
    }

    $usage = Get-LatestAssistantUsage -TranscriptPath $transcriptPath
    if (-not $usage.Ok) {
        Write-ContextMeterState -RepoRoot $repoRoot -SessionId $sessionId `
            -Tier $state.LastTier -Context $state.LastContext -ToolCalls $toolCalls -CallCountNotified $callCountNotified
        if ($messages.Count -gt 0) {
            Write-HookMessage ($messages -join "`n")
            Add-HooksAuditLine -RepoRoot $repoRoot -Hook $HookName -Verdict 'remind' `
                -Tool $toolName -SessionId $sessionId -Detail "调用计数达 $toolCalls 次；usage 不可用：$($usage.Error)"
        } else {
            Add-HooksAuditLine -RepoRoot $repoRoot -Hook $HookName -Verdict 'error' `
                -Tool $toolName -SessionId $sessionId -Detail $usage.Error
        }
        exit 0
    }

    $context = $usage.Context
    $tier = Get-ContextTier -Context $context -ThresholdStart $script:ThresholdStart -ThresholdStep $script:ThresholdStep
    $tierJustCrossed = $tier -gt $state.LastTier
    if ($tierJustCrossed) {
        $kDisplay = [math]::Round($context / 1000)
        if ($context -ge $script:HardLine) {
            $messages.Add(
                "当前上下文 ≈${kDisplay}k，已越 250k 硬线：立即收尾——commit 已有增量、写接力卡、交接后结束本会话；" +
                "无头泳道以 ``OPENER_PARTIAL: 上下文转场（≈${kDisplay}k）`` 收尾"
            )
        } else {
            $messages.Add(
                "当前上下文 ≈${kDisplay}k，已越 150k 软提醒线：先把当前里程碑做完（至少 commit 一个可验证增量）再收尾交接，" +
                "不要在零产出时停下；无头泳道交接时以 ``OPENER_PARTIAL: 上下文转场（≈${kDisplay}k）`` 收尾。此后大文件先 grep 定位再分段读、重输出交子代理；250k 为硬线，届时须立即收尾"
            )
        }
    }
    $tierToWrite = if ($tierJustCrossed) { $tier } else { $state.LastTier }

    Write-ContextMeterState -RepoRoot $repoRoot -SessionId $sessionId `
        -Tier $tierToWrite -Context $context -ToolCalls $toolCalls -CallCountNotified $callCountNotified

    if ($messages.Count -eq 0) {
        Add-HooksAuditLine -RepoRoot $repoRoot -Hook $HookName -Verdict 'pass' `
            -Tool $toolName -SessionId $sessionId -Detail "未越线，当前上下文约 $context，调用计数 $toolCalls"
        exit 0
    }

    Write-HookMessage ($messages -join "`n")
    Add-HooksAuditLine -RepoRoot $repoRoot -Hook $HookName -Verdict 'remind' `
        -Tool $toolName -SessionId $sessionId `
        -Detail "档位 $tier（越线=$tierJustCrossed）／调用计数 $toolCalls（越线=$countJustCrossed），当前上下文约 $context"
    exit 0
} catch {
    try {
        Add-HooksAuditLine -RepoRoot (Get-SentinelRepoRoot) -Hook $HookName -Verdict 'error' `
            -Detail $_.Exception.Message
    } catch { }
    exit 0
}
