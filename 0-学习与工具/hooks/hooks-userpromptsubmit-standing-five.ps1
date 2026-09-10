<#
.SYNOPSIS
  UserPromptSubmit 钩子（队列 §一 #381⑸ⓑ，openspec 变更包 cc-hooks-p3）：每轮从根
  `CLAUDE.md` 正文按行内锚点抓取"常驻纪律"若干条（称呼纪律／禁推断性别／需你定夺
  格式／粘贴端标注／默认项两前提／代执行优先…），拼成 ≤300 B 摘要注入上下文——
  对抗"会话中途丢规则"。

.DESCRIPTION
  判据正本＝队列 §一 #381⑸ⓑ 原文 ＋ design.md 决策点 6；**条目数判据**已按队列
  §一 #537（2026-09-10）改判，见下。

  🔴 **不在脚本内维护硬编码副本**：摘要文本 MUST 直接来自根 `CLAUDE.md` 当前正文，
  本脚本只做"找到那一行、截断、拼接"，正文改了下一轮自动反映新文本。

  🔴 **锚点机制，不做子串猜测**：目标行行尾各带 `<!-- UPS5:n -->`（n 从 1 起递增）
  HTML 注释标记（不影响 Markdown 渲染），脚本按该标记精确提取整行。

  🔴 **不断言"恰好 N 条"，改断言"锚点集自身自洽"（队列 §一 #537，2026-09-10）**：
  原实现把条目数写死成 5，2026-09-09 往 §5 合法新增第 6 条常驻纪律（`UPS5:6`）后，
  **每一轮 UserPromptSubmit 都打"预期 5、实得 6"**，并让一条单测长期常红——常红会
  掩盖真红。把 5 改成 6 只是把同一颗定时炸弹往后推一格（同族＝ §一 #535 夹具硬编码
  日期跨零点转红）：**任何"写死的数量／日期"都会在下一次变化时自动转红。**
  ⇒ 改判为按**实际锚点集**判三件事，与总条数无关：
    ① **缺号**——命中编号集 MUST 是 1..max 的连续整数，缺哪个报哪个；
    ② **重复**——同一编号出现 >1 次即报；
    ③ **非法编号**——编号 <1（如 `UPS5:0`）即报。
  三者皆无 ⇒ 判 pass，合法增删条目**不再产生噪声**。任一命中仍必须放行
  （fail-open），但须把差异写进注入内容与审计，不得静默按实得数量拼接而不报告
  （同 CLAUDE.md §5「工具静默回退」纪律：一处只读操作返回"太干净"的结果时，先怀疑
  是不是没读到该读的东西）。**一个锚点都没命中同样是异常**——那正是"太干净"的形态。
#>

$ErrorActionPreference = 'Stop'
try { [Console]::OutputEncoding = [Text.UTF8Encoding]::new($false) } catch {}

. (Join-Path $PSScriptRoot 'hooks-common.ps1')

$HookName = 'userpromptsubmit-standing-five'
$script:PerLineByteCap = 80
$script:TotalByteCap = 300
# 🔴 这里**故意没有** `ExpectedAnchorCount` —— 条目数由根 CLAUDE.md 的锚点集自己决定，
#    脚本只校验该集合自洽（连续／不重复／编号合法）。判据见文件头 .DESCRIPTION。
$script:AnchorRegex = '<!--\s*UPS5:(\d+)\s*-->'   # `\d+` 而非 `\d`：编号到两位数也不静默漏读

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

function Get-StandingAnchorsFromClaudeMd([string]$RepoRoot) {
    <#
      返回 @{ Ok=$bool; Lines=<string[]>; Anomaly=<string>; Error=<string> }。
      `Anomaly` 为空串 ＝ 锚点集自洽（连续、不重复、编号合法）；非空 ＝ 须在注入内容
      与审计里可见的差异描述。**不再有"预期 N"这一硬编码判据**（队列 §一 #537）。

      🔴 哈希表包裹返回值，不直接返回数组——PowerShell 恰好 1 元素的数组会被管道
      展平成标量，`Set-StrictMode` 下对展平后的标量取 `.Count` 会抛异常（ⓐ 建造期
      实测坐死的坑，见 hooks-sessionstart-context.ps1 同一处理法）。
    #>
    $result = @{ Ok = $false; Lines = @(); Anomaly = ''; Error = '' }
    $claudeMdPath = Join-Path $RepoRoot 'CLAUDE.md'
    if (-not (Test-Path -LiteralPath $claudeMdPath)) {
        $result.Error = "根 CLAUDE.md 不存在：$claudeMdPath"
        return $result
    }
    $text = Get-Content -LiteralPath $claudeMdPath -Raw -Encoding UTF8
    $lines = $text -split "`r?`n"

    $byIndex = @{}
    foreach ($ln in $lines) {
        $m = [regex]::Match($ln, $script:AnchorRegex)
        if (-not $m.Success) { continue }
        $idx = [int]$m.Groups[1].Value
        $body = $ln.Substring(0, $m.Index).Trim()
        $body = $body -replace '^-\s*', ''   # 去掉行首 Markdown 列表前缀，纯文本更省字节
        if (-not $byIndex.ContainsKey($idx)) { $byIndex[$idx] = New-Object System.Collections.ArrayList }
        [void]$byIndex[$idx].Add($body)
    }

    # ── 锚点集自洽性校验（三族，与总条数无关；判据见文件头 .DESCRIPTION） ──────────
    $indexes = @($byIndex.Keys | Sort-Object)
    $notes = New-Object System.Collections.ArrayList

    if ($indexes.Count -eq 0) {
        # 一条都没命中＝典型的"结果太干净"，比缺一条更该报，不得当"正好 0 条、自洽"放过。
        [void]$notes.Add('未命中任何 UPS5:n 锚点')
    }
    else {
        # ① 非法编号：编号从 1 起，`UPS5:0`／负数一律报（regex 只放 \d+，故只可能是 0）。
        $illegal = @($indexes | Where-Object { $_ -lt 1 })
        if ($illegal.Count -gt 0) { [void]$notes.Add('非法编号：' + ($illegal -join '、')) }

        # ② 缺号：合法编号 MUST 构成 1..max 的连续整数集；缺哪个报哪个。
        #    这是"合法新增/删除条目不报警、真漏一条才报警"的关键——只看连续性，不看总数。
        $legal = @($indexes | Where-Object { $_ -ge 1 })
        if ($legal.Count -gt 0) {
            $maxIdx = $legal[-1]
            $missing = @(1..$maxIdx | Where-Object { -not $byIndex.ContainsKey($_) })
            if ($missing.Count -gt 0) {
                [void]$notes.Add("缺号：" + ($missing -join '、') + "（实得 $($legal.Count) 条·最大编号 $maxIdx）")
            }
        }

        # ③ 重复锚点（同一编号出现 >1 次）单独记一笔，不静默取第一个/最后一个了事。
        $dupIndexes = @($byIndex.Keys | Where-Object { $byIndex[$_].Count -gt 1 } | Sort-Object)
        if ($dupIndexes.Count -gt 0) { [void]$notes.Add('重复编号：' + ($dupIndexes -join '、')) }
    }
    if ($notes.Count -gt 0) { $result.Anomaly = ($notes -join '；') }

    # 🔴 每条上限 80 字节是"单条不得超过"的硬顶；但各条顶格拼起来会超过 300 字节
    # 总预算——若先各截 80 再整体截 300，超出部分会从**尾部**被砍掉，等价于"最后一条
    # 整条消失不见"，比"每条都稍短一点"更差（丢一条 ≠ 更省字节，是更丢信息）。
    # 改为：按实得条数把总预算（扣掉分隔符开销）均分，与 80 字节硬顶取较小值，
    # 让**每一条都在**、只是长短随条数自适应，不会有条目整条消失。
    $foundCount = $indexes.Count
    $perLineCap = $script:PerLineByteCap
    if ($foundCount -gt 0) {
        $separatorOverheadBytes = [Text.Encoding]::UTF8.GetByteCount(' ｜ ') * [Math]::Max(0, $foundCount - 1)
        $fairShare = [Math]::Floor(([double]($script:TotalByteCap - $separatorOverheadBytes)) / $foundCount)
        if ($fairShare -lt $perLineCap) { $perLineCap = [Math]::Max(1, [int]$fairShare) }
    }

    # 🔴 按**实得编号升序**输出，不按 1..N 固定区间遍历——旧写法会把编号 >N 的条目
    #    整条丢掉（正是 2026-09-09 新增 `UPS5:6` 后第 6 条从未被注入过的成因）。
    $ordered = New-Object System.Collections.ArrayList
    foreach ($i in $indexes) {
        [void]$ordered.Add((Limit-Utf8Bytes $byIndex[$i][0] $perLineCap))
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
    $standing = Get-StandingAnchorsFromClaudeMd -RepoRoot $repoRoot

    if (-not $standing.Ok) {
        Write-HookMessage "常驻纪律不可用：$($standing.Error)"
        Add-HooksAuditLine -RepoRoot $repoRoot -Hook $HookName -Verdict 'error' `
            -SessionId $sessionId -Detail $standing.Error
        exit 0
    }

    $lines = @($standing.Lines)
    $body = ($lines -join ' ｜ ')
    $body = Limit-Utf8Bytes $body $script:TotalByteCap

    # 🔴 前缀里的条数也随实得数走，不写死"五条"——否则展示层本身会说谎（显示 6 条却
    #    自称"常驻五条"），属同一族"硬编码数量下一次变化即失真"。
    $prefix = "📌 常驻纪律 $($lines.Count) 条："
    $msg = "$prefix$body"
    if ($standing.Anomaly) {
        $msg = "⚠ 常驻纪律锚点异常（$($standing.Anomaly)）$msg"
    }

    Write-HookMessage $msg

    $verdict = if ($standing.Anomaly) { 'undetermined' } else { 'pass' }
    Add-HooksAuditLine -RepoRoot $repoRoot -Hook $HookName -Verdict $verdict `
        -SessionId $sessionId -Detail "命中 $($lines.Count) 条｜$($standing.Anomaly)"
    exit 0
} catch {
    Write-HookMessage "[常驻纪律] ⚠ hooks-userpromptsubmit-standing-five 自身报错：$($_.Exception.Message)"
    try {
        Add-HooksAuditLine -RepoRoot (Get-SentinelRepoRoot) -Hook $HookName -Verdict 'error' `
            -Detail $_.Exception.Message
    } catch { }
    exit 0
}
