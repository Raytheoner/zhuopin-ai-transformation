<#
.SYNOPSIS
  上下文闸计量共享库（队列 §一 `#639`，泳道读取面切分）：状态读写、档位换算、
  transcript usage 解析——`hooks-posttooluse-context-meter.ps1` 与
  `hooks-stop-context-meter.ps1` 两个读取面共用同一套逻辑，被 dot-source 载入。

.DESCRIPTION
  抽出原因：PostToolUse 只在工具调用后触发，若某一轮回复不含工具调用（纯文本
  收尾）就直接进 Stop，那一轮的 usage 永远不会被 PostToolUse 写进
  `reports/context-meter/<sid>.json` 的 `lastContext`——`工具-opener批处理执行v2.ps1`
  轮询与收尾"最后一探"读到的都是这个被漏写的旧值，闸因此持续低估实际峰值
  （实测差值与四条逐条比对见队列 `#639`）。修法＝新增 Stop 读取面
  `hooks-stop-context-meter.ps1`，与 PostToolUse 共用本文件的状态读写函数：
  两个读取面合起来覆盖"有工具调用"与"纯文本收尾"两种轮次，不留盲区。

  🔴 本文件不含阈值判定与提醒文案——180k/250k 等政策值、越线提醒的措辞仍各自
  留在调用方脚本里（Stop 读取面只补写状态，不重复提醒，提醒本就该在越线的
  那次 PostToolUse 上出现一次，Stop 时机上提醒无意义——会话已经在收尾）。
#>

Set-StrictMode -Version Latest

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
    $result = @{ LastTier = 0; LastContext = 0L; ToolCalls = 0; CallCountNotified = $false }
    if (-not (Test-Path -LiteralPath $path)) { return $result }
    try {
        $obj = (Get-Content -LiteralPath $path -Raw -Encoding UTF8) | ConvertFrom-Json
        $props = Get-JsonPropertyNames $obj
        if ($props -contains 'lastTier') { $result.LastTier = [int]$obj.lastTier }
        if ($props -contains 'lastContext') { $result.LastContext = [long]$obj.lastContext }
        if ($props -contains 'toolCalls') { $result.ToolCalls = [int]$obj.toolCalls }
        if ($props -contains 'callCountNotified') { $result.CallCountNotified = [bool]$obj.callCountNotified }
    } catch {
        # 状态文件损坏 ⇒ 当作从未提醒过（更保守的一侧：宁可多提醒一次，也不能因为
        # 一份坏 JSON 就此再也不提醒）。
    }
    return $result
}

function Write-ContextMeterState(
    [string]$RepoRoot, [string]$SessionId, [int]$Tier, [long]$Context,
    [int]$ToolCalls, [bool]$CallCountNotified
) {
    try {
        $dir = Get-ContextMeterStateDir $RepoRoot
        if (-not (Test-Path -LiteralPath $dir)) { New-Item -ItemType Directory -Path $dir -Force | Out-Null }
        $path = Get-ContextMeterStatePath -RepoRoot $RepoRoot -SessionId $SessionId
        $obj = [ordered]@{
            lastTier          = $Tier
            lastContext       = $Context
            lastTs            = (Get-SentinelTimestamp)
            toolCalls         = $ToolCalls
            callCountNotified = $CallCountNotified
        }
        $tmp = "$path.tmp"
        $obj | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath $tmp -Encoding UTF8
        Move-Item -LiteralPath $tmp -Destination $path -Force
    } catch {
        # 状态写不了也不能打断宿主钩子——fail-open 是本框架第一原则。
    }
}

function Get-ContextTier([long]$Context, [long]$ThresholdStart = 150000, [long]$ThresholdStep = 50000) {
    if ($Context -lt $ThresholdStart) { return 0 }
    return ([int][math]::Floor(($Context - $ThresholdStart) / $ThresholdStep)) + 1
}

function Get-LatestAssistantUsage([string]$TranscriptPath, [int[]]$TailWindowSizes = @(200, 2000, 20000)) {
    <# 返回 @{ Ok=$bool; Context=[long]; Error=$string }。只读尾部窗口，找到即停。#>
    $result = @{ Ok = $false; Context = 0L; Error = '' }
    if (-not $TranscriptPath -or -not (Test-Path -LiteralPath $TranscriptPath -PathType Leaf)) {
        $result.Error = "transcript 文件不存在：$TranscriptPath"
        return $result
    }

    foreach ($tailN in $TailWindowSizes) {
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
