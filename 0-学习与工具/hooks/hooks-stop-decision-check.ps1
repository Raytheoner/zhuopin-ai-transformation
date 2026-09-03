<#
.SYNOPSIS
  Stop 钩子（队列 §一 #381⑸ⓓ，openspec 变更包 cc-hooks-p3）：读最后一条 assistant
  回复，若含「需你定夺／需你决策」小节却缺 `(a)`/`(b)` 选项标签，回退提示补全。

.DESCRIPTION
  判据正本＝队列 §一 #381⑸ⓓ 原文 ＋ design.md 决策点 2／5。

  🔴 **已知边界，本次知情接受（design.md 决策点 2）**：`#381`⑷评估 ⒞ 曾否决"本机
  Stop hook 作为主方案"（只覆盖 CC、覆盖不了 Cowork，半覆盖比没有更危险）；
  `#155`（2026-09-04）晚于该评估、重新拍板仍建。ⓓ 只覆盖 CC 侧，Cowork 侧仍靠
  根 `CLAUDE.md` 正文常驻五条兜底——两者互补，根文件对应判据正文不因此降指针。

  🔴 **只在"小节存在但格式不全"时拦，"完全没写"时放行**：根 `CLAUDE.md` §5 原文
  允许"无决策项时明写'本次无需你决策'"这一合法终态；对完全没有该小节的回复也
  拦截，会把合法终态变成过不去的死循环。

  🔴 **`stop_hook_active` 时必须直接放行**：该字段为真表示本次 Stop 是上一次
  Stop 钩子拦截后的重试——不重复判定，防止模型改不对格式时陷入无限重试。

.NOTES
  transcript 解析口径与 `专线opener模板库.md` §〇.15「CC 复命取件」既有约定一致：
  逐行 `ConvertFrom-Json`，取 `type=assistant` 的 `message.content[].text`，
  版本探测失败按行跳过（fail-loud 计数，不静默吞成"没有内容"）。
#>

$ErrorActionPreference = 'Stop'
try { [Console]::OutputEncoding = [Text.UTF8Encoding]::new($false) } catch {}

. (Join-Path $PSScriptRoot 'hooks-common.ps1')

$HookName = 'stop-decision-check'

#: 需你定夺／需你决策，但排除"本次无需你决策"这类合法否定句（负向后顾断言）。
$script:DecisionSectionRe = '(?<!无)需你(?:定夺|决策)'
$script:OptionLabelRe = '\(a\)|\(b\)'

function Get-LastAssistantText([string]$TranscriptPath) {
    <# 返回 @{ Ok=$bool; Text=$string; Error=$string; ParseErrors=$int }。#>
    $result = @{ Ok = $false; Text = ''; Error = ''; ParseErrors = 0 }
    if (-not $TranscriptPath -or -not (Test-Path -LiteralPath $TranscriptPath -PathType Leaf)) {
        $result.Error = "transcript 文件不存在：$TranscriptPath"
        return $result
    }
    $lastText = $null
    $parseErrors = 0
    try {
        $streamReader = [System.IO.StreamReader]::new($TranscriptPath, [Text.Encoding]::UTF8)
    } catch {
        $result.Error = "无法打开 transcript：$($_.Exception.Message)"
        return $result
    }
    try {
        while (-not $streamReader.EndOfStream) {
            $line = $streamReader.ReadLine()
            if (-not $line -or -not $line.Trim()) { continue }
            try {
                $obj = $line | ConvertFrom-Json
            } catch {
                $parseErrors++
                continue
            }
            $objProps = Get-JsonPropertyNames $obj
            if (-not ($objProps -contains 'type') -or [string]$obj.type -ne 'assistant') { continue }
            if (-not ($objProps -contains 'message')) { continue }
            $msgProps = Get-JsonPropertyNames $obj.message
            if (-not ($msgProps -contains 'content')) { continue }

            $textParts = New-Object System.Collections.ArrayList
            foreach ($block in @($obj.message.content)) {
                $blockProps = Get-JsonPropertyNames $block
                if (($blockProps -contains 'type') -and [string]$block.type -eq 'text' `
                        -and ($blockProps -contains 'text')) {
                    [void]$textParts.Add([string]$block.text)
                }
            }
            if ($textParts.Count -gt 0) {
                $lastText = ($textParts -join "`n")
            }
        }
    } finally {
        $streamReader.Dispose()
    }

    $result.ParseErrors = $parseErrors
    if ($null -eq $lastText) {
        $result.Error = "未找到任何 assistant 文本消息（解析失败行数：$parseErrors；" +
            "transcript 契约非公开、格式可能已变，需人工核查）"
        return $result
    }
    $result.Ok = $true
    $result.Text = $lastText
    return $result
}

try {
    $stdinRaw = Read-SentinelStdin
    if (-not $stdinRaw -or -not $stdinRaw.Trim()) { exit 0 }
    $json = $stdinRaw | ConvertFrom-Json
    $jsonProps = Get-JsonPropertyNames $json

    $sessionId = ''
    if ($jsonProps -contains 'session_id') { $sessionId = [string]$json.session_id }

    if (($jsonProps -contains 'stop_hook_active') -and $json.stop_hook_active) {
        Add-HooksAuditLine -RepoRoot (Get-SentinelRepoRoot) -Hook $HookName -Verdict 'pass' `
            -SessionId $sessionId -Detail 'stop_hook_active=true，防循环放行，不重复判定'
        exit 0
    }

    $transcriptPath = ''
    if ($jsonProps -contains 'transcript_path') { $transcriptPath = [string]$json.transcript_path }

    $repoRoot = Get-SentinelRepoRoot
    $lastMsg = Get-LastAssistantText -TranscriptPath $transcriptPath

    if (-not $lastMsg.Ok) {
        Add-HooksAuditLine -RepoRoot $repoRoot -Hook $HookName -Verdict 'error' `
            -SessionId $sessionId -Detail $lastMsg.Error
        exit 0
    }

    $text = $lastMsg.Text
    $sectionMatch = [regex]::Match($text, $script:DecisionSectionRe)
    if (-not $sectionMatch.Success) {
        # 完全未出现该字样——合法终态（可能是真的无决策项，也可能是"本次无需你
        # 决策"这类否定句），不拦截。
        Add-HooksAuditLine -RepoRoot $repoRoot -Hook $HookName -Verdict 'pass' `
            -SessionId $sessionId -Detail '末条回复无"需你定夺"字样，不适用本判据'
        exit 0
    }

    $rest = $text.Substring($sectionMatch.Index)
    $hasLabels = [regex]::IsMatch($rest, $script:OptionLabelRe)
    if ($hasLabels) {
        Add-HooksAuditLine -RepoRoot $repoRoot -Hook $HookName -Verdict 'pass' `
            -SessionId $sessionId -Detail '"需你定夺"小节含 (a)/(b) 选项标签，格式完整'
        exit 0
    }

    $msg = '✗ 「需你定夺」小节缺选项标签：末条回复出现"需你定夺／需你决策"字样，' +
        '但其后未找到 (a)/(b) 形态的选项标签。请补全为可直接作答的选择题（带字母标签、' +
        '写清代价、标默认项或明写"本项无默认"），或若确无决策项，删掉该字样并改写为' +
        '"本次无需你决策"（根 CLAUDE.md §5）。'
    Add-HooksAuditLine -RepoRoot $repoRoot -Hook $HookName -Verdict 'violation' `
        -SessionId $sessionId -Detail '"需你定夺"小节缺 (a)/(b) 选项标签'
    [Console]::Error.WriteLine($msg)
    exit 2
} catch {
    try {
        Add-HooksAuditLine -RepoRoot (Get-SentinelRepoRoot) -Hook $HookName -Verdict 'error' `
            -Detail $_.Exception.Message
    } catch { }
    exit 0
}
