<#
.SYNOPSIS
  SessionStart 钩子（队列 §一 #381⑸ⓐ，openspec 变更包 cc-hooks-p3）：会话开场注入
  本机双标时刻、仓库连通性、与 origin/master 的双向提交计数、本线待领队列行摘要。

.DESCRIPTION
  判据正本＝队列 §一 #381⑸ⓐ 原文。**刻意独立于 `#398` 心跳钩子**（本会话内实测坐实
  `#398` 已在生产独立生效：`~/.claude/settings.json` 已注册 SessionStart 指向
  `health-check-staleness.ps1`）——合并已不产生"省一次注册"的收益（两者本就要分别
  登记到「项目」与「全局」两份不同的 settings.json），见 openspec 变更包 design.md
  决策点 1。

  🔴 刻意不跑 `git fetch`：SessionStart 钩子有超时（本项目既有钩子统一 10s），网络
  抓取耗时不可控且可能改变本地 refs 状态；`ahead`/`behind` 只读**本地已知的**
  `origin/master`，若显得"太干净"（0/0）不代表真的同步，只代表上次 fetch 之后没有
  新进展被看到——这本身也是本项目「工具静默回退」纪律要求显式声明的那类边界。

  待领队列行摘要是**尽力而为的启发式**，不是权威计数（权威判据在
  `工具-共享文档编辑锁.py::_count_mechanism_wip` 等专用工具里）：按行内最后一个
  `[S:...]` 标记取值，`open` 且其后 15 字符内不含 🛑 即计入；解析失败的行静默跳过
  （不是本钩子要守的判据，读不出来不算异常）。
#>

$ErrorActionPreference = 'Stop'
try { [Console]::OutputEncoding = [Text.UTF8Encoding]::new($false) } catch {}

. (Join-Path $PSScriptRoot 'hooks-common.ps1')

$HookName = 'sessionstart-context'

function Write-HookMessage([string]$msg) {
    $payload = @{
        systemMessage       = $msg
        hookSpecificOutput  = @{
            hookEventName     = 'SessionStart'
            additionalContext = $msg
        }
    }
    $payload | ConvertTo-Json -Depth 5 -Compress
}

function Get-QueueOpenSummary {
    <# 返回最多 5 条 "#编号 截断标题" 字符串；失败时返回 $null 并把原因写进 $script:QueueSummaryError。#>
    param([string]$RepoRoot)
    # 🔴 返回值刻意包一层对象，不直接返回数组或 $null——PowerShell 函数的 `return`/管道
    # 输出在"恰好 1 个元素"时会静默把数组"展平"成标量（本文件曾因此实际撞坑：
    # `Set-StrictMode -Version Latest`（hooks-common.ps1 已设）下对展平后的标量字符串
    # 取 `.Count` 直接抛异常，且只在"恰好 1 条待领行"这个具体输入下才会触发，
    # 平时测不出来）。哈希表的属性读取不经过管道，不受这条展平规则影响，从根上避免。
    $result = [ordered]@{ Ok = $false; Error = ''; Rows = @() }
    try {
        $queuePath = Join-Path $RepoRoot '1-转型规划/0-全景路线图/跨桌任务队列-机制环境.md'
        if (-not (Test-Path -LiteralPath $queuePath)) {
            $result.Error = "队列文件不存在：$queuePath"
            return $result
        }
        $lines = Get-Content -LiteralPath $queuePath -Encoding UTF8
        $inSectionOne = $false
        $rows = New-Object System.Collections.ArrayList
        foreach ($ln in $lines) {
            if ($ln -match '^##\s*一、') { $inSectionOne = $true; continue }
            if ($inSectionOne -and $ln -match '^##\s*二、') { break }
            if (-not $inSectionOne) { continue }
            if ($ln -notmatch '^\s*\|\s*(\d+)\s*\|') { continue }
            [void]$rows.Add($ln)
        }
        if ($rows.Count -eq 0) {
            $result.Error = '§一 区间未解析到任何行（结构可能已变，钩子未跟上）'
            return $result
        }
        $picked = New-Object System.Collections.ArrayList
        foreach ($row in $rows) {
            if ($picked.Count -ge 5) { break }
            $statusMatches = [regex]::Matches($row, '\[S:(\w+)\]')
            if ($statusMatches.Count -eq 0) { continue }
            $last = $statusMatches[$statusMatches.Count - 1]
            if ($last.Groups[1].Value -ne 'open') { continue }
            $tailStart = $last.Index + $last.Length
            $tailLen = [Math]::Min(15, $row.Length - $tailStart)
            $tail = if ($tailLen -gt 0) { $row.Substring($tailStart, $tailLen) } else { '' }
            if ($tail -match '🛑') { continue }
            $numMatch = [regex]::Match($row, '^\s*\|\s*(\d+)\s*\|')
            $num = if ($numMatch.Success) { $numMatch.Groups[1].Value } else { '?' }
            $cols = $row -split '\|'
            $preview = if ($cols.Count -ge 3) { $cols[2].Trim() } else { '' }
            $preview = $preview -replace '\*{1,2}', '' -replace '🔴', '' -replace '━+', ''
            $preview = $preview.Trim()
            if ($preview.Length -gt 60) { $preview = $preview.Substring(0, 60) + '…' }
            [void]$picked.Add("#$num $preview")
        }
        $result.Ok = $true
        $result.Rows = @($picked)
        return $result
    } catch {
        $result.Error = "解析异常：$($_.Exception.Message)"
        return $result
    }
}

try {
    $stdinRaw = Read-SentinelStdin
    $sessionId = ''
    if ($stdinRaw -and $stdinRaw.Trim()) {
        try {
            $stdinJson = $stdinRaw | ConvertFrom-Json
            if ((Get-JsonPropertyNames $stdinJson) -contains 'session_id') {
                $sessionId = [string]$stdinJson.session_id
            }
        } catch { }
    }

    $repoRoot = Get-SentinelRepoRoot

    # ── 双标时刻 ──────────────────────────────────────────────────────────
    $localNow = Get-Date
    $utcNow = $localNow.ToUniversalTime()
    $timeLine = "🕐 {0} 本地 / {1} UTC" -f `
        $localNow.ToString('yyyy-MM-dd HH:mm:ss'), $utcNow.ToString('yyyy-MM-dd HH:mm:ss')

    # ── 仓库连通性 ────────────────────────────────────────────────────────
    $fsckOk = $true
    try {
        $fsckOut = & git -C $repoRoot fsck --connectivity-only 2>&1
        if ($LASTEXITCODE -ne 0) {
            $fsckOk = $false
            $fsckLine = "🔴 git fsck 退出码 $LASTEXITCODE：" + (($fsckOut | Select-Object -First 5) -join '; ')
        } elseif ($fsckOut) {
            $fsckLine = "⚠ git fsck 有输出（前 5 行）：" + (($fsckOut | Select-Object -First 5) -join '; ')
        } else {
            $fsckLine = '✓ 仓库连通性正常（git fsck --connectivity-only 无输出）'
        }
    } catch {
        $fsckOk = $false
        $fsckLine = "仓库健康信息不可用：$($_.Exception.Message)"
    }

    # ── 与 origin/master 双向计数（🔴 不 fetch，只读本地已知的 origin/master）──
    try {
        $ahead = (& git -C $repoRoot rev-list --count 'origin/master..master' 2>$null).Trim()
        $behind = (& git -C $repoRoot rev-list --count 'master..origin/master' 2>$null).Trim()
        if ($ahead -match '^\d+$' -and $behind -match '^\d+$') {
            $aheadBehindLine = "↕ ahead=$ahead behind=$behind（相对本地已知的 origin/master，未 fetch）"
        } else {
            $aheadBehindLine = '↕ ahead/behind 不可用（无法解析 origin/master，可能无网络历史或非常规分支状态）'
        }
    } catch {
        $aheadBehindLine = "↕ ahead/behind 不可用：$($_.Exception.Message)"
    }

    # ── 待领队列行摘要 ────────────────────────────────────────────────────
    $queueResult = Get-QueueOpenSummary -RepoRoot $repoRoot
    $queueRows = @($queueResult.Rows)   # 🔴 防御性再包一层 @()：即便万一 .Rows 也被展平，这里补救
    if (-not $queueResult.Ok) {
        $queueBlock = "📋 待领队列摘要不可用：$($queueResult.Error)"
    } elseif ($queueRows.Count -eq 0) {
        $queueBlock = '📋 §一当前无 [S:open] 且非 🛑 的待领行（或全部已超前 5 条截断范围外）'
    } else {
        $queueBlock = "📋 §一 待领行摘要（前 $($queueRows.Count) 条，非权威计数）：`n  " +
            ($queueRows -join "`n  ")
    }

    $msg = @($timeLine, $fsckLine, $aheadBehindLine, $queueBlock) -join "`n"
    Write-HookMessage $msg

    $verdict = if ($fsckOk) { 'pass' } else { 'violation' }
    Add-HooksAuditLine -RepoRoot $repoRoot -Hook $HookName -Verdict $verdict `
        -SessionId $sessionId -Detail $fsckLine
    exit 0
} catch {
    $errMsg = "[会话开场] ⚠ hooks-sessionstart-context 自身报错：$($_.Exception.Message)"
    Write-HookMessage $errMsg
    try {
        Add-HooksAuditLine -RepoRoot (Get-SentinelRepoRoot) -Hook $HookName -Verdict 'error' `
            -Detail $_.Exception.Message
    } catch { }
    exit 0
}
