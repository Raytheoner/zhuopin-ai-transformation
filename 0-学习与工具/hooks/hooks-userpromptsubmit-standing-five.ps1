<#
.SYNOPSIS
  UserPromptSubmit 钩子（队列 §一 #381⑸ⓑ，openspec 变更包 cc-hooks-p3）：每轮从根
  `CLAUDE.md` 正文按行内锚点抓取"常驻五条"（称呼纪律／禁推断性别／需你定夺格式／
  粘贴端标注／默认项两前提），拼成 ≤300 B 摘要注入上下文——对抗"会话中途丢规则"。

.DESCRIPTION
  判据正本＝队列 §一 #381⑸ⓑ 原文 ＋ design.md 决策点 6。

  🔴 **不在脚本内维护硬编码副本**：五条摘要文本 MUST 直接来自根 `CLAUDE.md` 当前
  正文，本脚本只做"找到那一行、截断、拼接"，正文改了下一轮自动反映新文本。

  🔴 **锚点机制，不做子串猜测**：五处目标行行尾各带 `<!-- UPS5:n -->`（n=1..5）
  HTML 注释标记（不影响 Markdown 渲染），脚本按该标记精确提取整行，**断言恰好
  命中 5 条**——命中数 ≠5 时仍必须放行（fail-open），但须把"预期 5、实得 N"这一
  差异写进注入内容与审计，不得静默按实得数量拼接而不报告（同 CLAUDE.md §5「工具
  静默回退」纪律：一处只读操作返回"太干净"的结果时，先怀疑是不是没读到该读的东西）。
#>

$ErrorActionPreference = 'Stop'
try { [Console]::OutputEncoding = [Text.UTF8Encoding]::new($false) } catch {}

. (Join-Path $PSScriptRoot 'hooks-common.ps1')

$HookName = 'userpromptsubmit-standing-five'
$script:PerLineByteCap = 80
$script:TotalByteCap = 300
$script:ExpectedAnchorCount = 5

function Write-HookMessage([string]$msg) {
    $payload = @{
        hookSpecificOutput = @{
            hookEventName     = 'UserPromptSubmit'
            additionalContext = $msg
        }
    }
    $payload | ConvertTo-Json -Depth 5 -Compress
}

function Limit-Utf8Bytes([string]$Text, [int]$MaxBytes) {
    <# 按 UTF-8 字节数截断，避免在多字节字符中途切断；超限时追加"…"（3 字节）。
       逐字符收缩是 O(n) 但 n 极小（单行文本），性能不是考量点，正确性优先。 #>
    $enc = [Text.Encoding]::UTF8
    if ($enc.GetByteCount($Text) -le $MaxBytes) { return $Text }
    $t = $Text
    $budget = $MaxBytes - 3
    if ($budget -lt 0) { $budget = 0 }
    while ($t.Length -gt 0 -and $enc.GetByteCount($t) -gt $budget) {
        $t = $t.Substring(0, $t.Length - 1)
    }
    return "$t…"
}

function Get-StandingFiveFromClaudeMd([string]$RepoRoot) {
    <#
      返回 @{ Ok=$bool; Lines=<string[]>; ExpectedVsActual=<string>; Error=<string> }。
      🔴 哈希表包裹返回值，不直接返回数组——PowerShell 恰好 1 元素的数组会被管道
      展平成标量，`Set-StrictMode` 下对展平后的标量取 `.Count` 会抛异常（ⓐ 建造期
      实测坐死的坑，见 hooks-sessionstart-context.ps1 同一处理法）。
    #>
    $result = @{ Ok = $false; Lines = @(); ExpectedVsActual = ''; Error = '' }
    $claudeMdPath = Join-Path $RepoRoot 'CLAUDE.md'
    if (-not (Test-Path -LiteralPath $claudeMdPath)) {
        $result.Error = "根 CLAUDE.md 不存在：$claudeMdPath"
        return $result
    }
    $text = Get-Content -LiteralPath $claudeMdPath -Raw -Encoding UTF8
    $lines = $text -split "`r?`n"

    $byIndex = @{}
    foreach ($ln in $lines) {
        $m = [regex]::Match($ln, '<!--\s*UPS5:(\d)\s*-->')
        if (-not $m.Success) { continue }
        $idx = [int]$m.Groups[1].Value
        $body = $ln.Substring(0, $m.Index).Trim()
        $body = $body -replace '^-\s*', ''   # 去掉行首 Markdown 列表前缀，纯文本更省字节
        if (-not $byIndex.ContainsKey($idx)) { $byIndex[$idx] = New-Object System.Collections.ArrayList }
        [void]$byIndex[$idx].Add($body)
    }

    $actualCount = @($byIndex.Keys).Count
    if ($actualCount -ne $script:ExpectedAnchorCount) {
        $result.ExpectedVsActual = "预期 $script:ExpectedAnchorCount、实得 $actualCount"
    }
    # 重复锚点（同一编号出现 >1 次）单独记一笔，不静默取第一个/最后一个了事。
    $dupIndexes = @($byIndex.Keys | Where-Object { $byIndex[$_].Count -gt 1 } | Sort-Object)
    if ($dupIndexes.Count -gt 0) {
        $dupNote = "重复编号：" + ($dupIndexes -join '、')
        $result.ExpectedVsActual = if ($result.ExpectedVsActual) { "$($result.ExpectedVsActual)；$dupNote" } else { $dupNote }
    }

    # 🔴 每条上限 80 字节是"单条不得超过"的硬顶；但 5 条各顶格拼起来会超过 300 字节
    # 总预算——若先各截 80 再整体截 300，超出部分会从**尾部**被砍掉，等价于"第 5 条
    # 整条消失不见"，比"5 条都稍短一点"更差（丢一条 ≠ 更省字节，是更丢信息）。
    # 改为：按实得条数把总预算（扣掉分隔符开销）均分，与 80 字节硬顶取较小值，
    # 让**每一条都在**、只是长短随条数自适应，不会有条目整条消失。
    $foundCount = @($byIndex.Keys).Count
    $perLineCap = $script:PerLineByteCap
    if ($foundCount -gt 0) {
        $separatorOverheadBytes = [Text.Encoding]::UTF8.GetByteCount(' ｜ ') * [Math]::Max(0, $foundCount - 1)
        $fairShare = [Math]::Floor(([double]($script:TotalByteCap - $separatorOverheadBytes)) / $foundCount)
        if ($fairShare -lt $perLineCap) { $perLineCap = [Math]::Max(1, [int]$fairShare) }
    }

    $ordered = New-Object System.Collections.ArrayList
    foreach ($i in 1..$script:ExpectedAnchorCount) {
        if ($byIndex.ContainsKey($i)) {
            [void]$ordered.Add((Limit-Utf8Bytes $byIndex[$i][0] $perLineCap))
        }
    }
    $result.Ok = $true
    $result.Lines = @($ordered)
    return $result
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
    $five = Get-StandingFiveFromClaudeMd -RepoRoot $repoRoot

    if (-not $five.Ok) {
        Write-HookMessage "常驻五条不可用：$($five.Error)"
        Add-HooksAuditLine -RepoRoot $repoRoot -Hook $HookName -Verdict 'error' `
            -SessionId $sessionId -Detail $five.Error
        exit 0
    }

    $lines = @($five.Lines)
    $body = ($lines -join ' ｜ ')
    $body = Limit-Utf8Bytes $body $script:TotalByteCap

    $prefix = '📌 常驻五条：'
    $msg = "$prefix$body"
    if ($five.ExpectedVsActual) {
        $msg = "⚠ 常驻五条锚点异常（$($five.ExpectedVsActual)）$msg"
    }

    Write-HookMessage $msg

    $verdict = if ($five.ExpectedVsActual) { 'undetermined' } else { 'pass' }
    Add-HooksAuditLine -RepoRoot $repoRoot -Hook $HookName -Verdict $verdict `
        -SessionId $sessionId -Detail "命中 $($lines.Count) 条｜$($five.ExpectedVsActual)"
    exit 0
} catch {
    Write-HookMessage "[常驻五条] ⚠ hooks-userpromptsubmit-standing-five 自身报错：$($_.Exception.Message)"
    try {
        Add-HooksAuditLine -RepoRoot (Get-SentinelRepoRoot) -Hook $HookName -Verdict 'error' `
            -Detail $_.Exception.Message
    } catch { }
    exit 0
}
