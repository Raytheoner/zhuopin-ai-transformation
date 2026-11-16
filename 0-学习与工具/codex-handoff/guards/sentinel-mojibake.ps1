<#
.SYNOPSIS
  H3 · 乱码哨兵（PostToolUse，matcher Edit|Write）

.DESCRIPTION
  承接根 CLAUDE.md §5「🔴 乱码文件夹哨兵」——把「开工与收工各记得扫一次目录」这条**人守**，
  换成「写入当刻按字节判」这条**机制守**。

  历史违反 2 起：
    · 2026-07-04 11:42 QD-A —— UTF-8 写入损坏，路径与内容同现 U+FFFD（每个汉字变 2 个）
    · 2026-08-19 —— 两处 `D:\airead` 被写成含 BEL（U+0007）控制字符

  判据（spec: hooks-mojibake-sentinel）：
    · 本次新增内容 **或** 写入目标路径本身含 U+FFFD / 非白名单控制字符 ⇒ 命中
    · 白名单：制表符 U+0009、换行 U+000A、回车 U+000D
    · 判定范围限文本类目标（.md/.py/.ps1/.json/.yaml/.yml），二进制目标放行且不读内容
    · 代码围栏内 / 块引用 / 带 `乱码豁免：<理由>` 的行不判 —— 事故复盘要原样贴出坏字节
    · 反馈必须给出「行号 ＋ 行内偏移 ＋ 码点」，只说「发现乱码」不算合格输出

  🔴 fail-open：任何异常一律 exit 0，异常摘要进心跳。
#>

$ErrorActionPreference = 'Stop'
$SentinelName = 'H3-乱码哨兵'
$ExemptionMark = '乱码'
$RepoRoot = $PWD.Path
$Mode = 'warn'

try {
    . (Join-Path (Split-Path -Parent $PSCommandPath) 'hooks-common.ps1')

    $raw = Read-SentinelStdin
    $payload = ConvertTo-SentinelPayload -Raw $raw

    $RepoRoot = Get-SentinelRepoRoot -StartDir $(if ($payload.Cwd) { $payload.Cwd } else { $PWD.Path })
    $modeInfo = Get-SentinelMode -RepoRoot $RepoRoot
    $Mode = $modeInfo.Mode

    if (-not $payload.Ok) {
        Complete-Sentinel -RepoRoot $RepoRoot -Sentinel $SentinelName -Verdict 'undetermined' `
            -Tool $payload.ToolName -SessionId $payload.SessionId -Target $payload.TargetPath `
            -Mode $Mode -Note ('无法判定：' + $payload.Reason)
    }

    $target = $payload.TargetPath

    # ── 坏字符判据（一处定义，路径与内容共用）
    $badAt = {
        param([string]$s)
        $hits = New-Object System.Collections.ArrayList
        for ($i = 0; $i -lt $s.Length; $i++) {
            $c = [int][char]$s[$i]
            $bad = $false
            if ($c -eq 0xFFFD) { $bad = $true }
            elseif ($c -lt 0x20 -and $c -ne 0x09 -and $c -ne 0x0A -and $c -ne 0x0D) { $bad = $true }
            elseif ($c -eq 0x7F) { $bad = $true }
            if ($bad) { [void]$hits.Add(@{ Offset = ($i + 1); Code = $c }) }
        }
        return @($hits)
    }

    $findings = New-Object System.Collections.ArrayList

    # ── ① 写入目标路径本身（2026-07-04 事故形态＝路径与内容同现）
    #     🔴 路径不受围栏/豁免影响：一条含坏字节的路径没有任何合法用途
    foreach ($h in (& $badAt $target)) {
        [void]$findings.Add(@{
            Where = '写入目标路径'; Line = 0; Offset = $h.Offset; Code = $h.Code
            Excerpt = $target
        })
    }

    # ── ② 本次新增内容（仅文本类目标）
    $isText = Test-SentinelTextTarget -TargetPath $target
    if ($isText) {
        $fileText = Get-SentinelTargetText -TargetPath $target
        $fileExempt = Test-SentinelFileExemption -MarkName $ExemptionMark -FileText $fileText -Segments $payload.Segments

        if (-not $fileExempt) {
            foreach ($seg in $payload.Segments) {
                $resolved = Resolve-SentinelSegmentLines -SegmentText $seg.Text -FileText $fileText
                $skip = Get-SentinelLineContext -Lines $resolved.Lines -InFenceAtStart $resolved.InFenceAtStart -MarkName $ExemptionMark
                for ($i = 0; $i -lt $resolved.Lines.Count; $i++) {
                    if ($skip[$i]) { continue }
                    $ln = $resolved.Lines[$i]
                    foreach ($h in (& $badAt $ln.Text)) {
                        [void]$findings.Add(@{
                            Where   = $(if ($resolved.Located) { '文件行号' } else { ('片段内相对行号（{0}，未能在文件中唯一定位）' -f $seg.Label) })
                            Line    = $ln.No; Offset = $h.Offset; Code = $h.Code
                            Excerpt = $(if ($ln.Text.Length -gt 120) { $ln.Text.Substring(0, 120) + '…' } else { $ln.Text })
                        })
                    }
                }
            }
        }
    }

    if ($findings.Count -eq 0) {
        $note = if ($isText) { '' } else { ('二进制/非文本目标，未读取内容（扩展名 {0}）' -f [System.IO.Path]::GetExtension($target)) }
        Complete-Sentinel -RepoRoot $RepoRoot -Sentinel $SentinelName -Verdict 'pass' `
            -Tool $payload.ToolName -SessionId $payload.SessionId -Target $target -Mode $Mode -Note $note
    }

    # ── 反馈：行号 ＋ 行内偏移 ＋ 码点，缺一不可
    $sb = New-Object System.Text.StringBuilder
    [void]$sb.AppendLine(('🔴 {0}：本次写入引入了 {1} 处非预期字节（模式 {2}）' -f $SentinelName, $findings.Count, $Mode))
    [void]$sb.AppendLine(('   目标：{0}' -f $target))
    foreach ($f in $findings) {
        $cp = 'U+{0:X4}' -f $f.Code
        $nm = switch ($f.Code) { 0xFFFD { '替换字符（UTF-8 解码损坏的指纹）' } 0x0007 { 'BEL 响铃' } 0x007F { 'DEL' } default { '控制字符' } }
        if ($f.Line -eq 0) {
            [void]$sb.AppendLine(('   · {0} 第 {1} 个字符：{2} {3}｜{4}' -f $f.Where, $f.Offset, $cp, $nm, $f.Excerpt))
        } else {
            [void]$sb.AppendLine(('   · {0} 第 {1} 行、行内第 {2} 个字符：{3} {4}' -f $f.Where, $f.Line, $f.Offset, $cp, $nm))
            [void]$sb.AppendLine(('     ↳ {0}' -f $f.Excerpt))
        }
    }
    [void]$sb.AppendLine('   处置：① 用正确编码重写该处；② 若本处是事故复盘/规范文档需要原样保留坏字节，')
    [void]$sb.AppendLine('         把它放进代码围栏或块引用，或在该行写 `乱码豁免：<理由>`（🔴 必须带理由，只写标记不生效）。')

    Complete-Sentinel -RepoRoot $RepoRoot -Sentinel $SentinelName -Verdict 'violation' `
        -Tool $payload.ToolName -SessionId $payload.SessionId -Target $target -Mode $Mode `
        -Findings $findings.Count -Message $sb.ToString()

} catch {
    # 🔴 fail-open：放行可以，静默不行
    try {
        Write-SentinelHeartbeat -RepoRoot $RepoRoot -Sentinel $SentinelName -Verdict 'error' `
            -Mode $Mode -ErrorSummary $_.Exception.Message
    } catch { }
    try { [Console]::Error.WriteLine('⚠ ' + $SentinelName + ' 异常放行：' + $_.Exception.Message) } catch { }
    exit 0
}
