<#
.SYNOPSIS
  H4 · 代词哨兵（PostToolUse，matcher Edit|Write）

.DESCRIPTION
  承接人员名录正本末「🔴 读到规则 ≠ 执行规则 —— 真正的落点是起草完成后扫一遍全文
  第三人称代词，逐个回名录核对」这条**人守**，换成写入当刻按名录逐个核对的**机制守**。

  历史违反 ≥6 次，其中 `财务部#14` 那次**信已发出、撤不回**。
  🔴 本文件刻意不写出任何一个具体人名 —— 写出来就等于造出了第二份名录（配套单测会锁死这一点）。

  判据（spec: hooks-pronoun-sentinel）：
    · 只在写入目标命中 `6-人才与组织/部门AI专员跟进/*.md` 时判
    · 名录**从 `6-人才与组织/人员名录-称谓与性别-正本.md` 读取**，🔴 脚本内零硬编码人名与性别
    · 判定限「同一段落内出现名录人名，且其后最近的第三人称代词与名录不符」这一形态
    · 同段落出现多个不同性别的名录人名 ⇒ 归属不明确 ⇒ 放行
    · 名录外人物（客户/OEM 对接人/其他部门同事）不触发
    · 块引用 / 代码围栏 / 带 `代词豁免：<理由>` 的行不判（历史记录不追改）
    · 名录缺失或解析出 0 人 ⇒ 放行，且明写「🔴 本类无法核验：<原因>」，
      🔴 MUST NOT 输出「未发现违规」—— 没有名录时它没有任何结论可用

  🔑 判据宁可漏报也不误报：一个每周误拦好几次的哨兵会被关掉，而关掉之后连漏报的
     那部分保护也一起没了。
#>

$ErrorActionPreference = 'Stop'
$SentinelName = 'H4-代词哨兵'
$ExemptionMark = '代词'
$RosterRelPath = '6-人才与组织/人员名录-称谓与性别-正本.md'
$LetterDirPattern = '6-人才与组织/部门AI专员跟进/'
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
    $normTarget = ($target -replace '\\', '/')

    # ── 作用域：只判跟进信
    if ($normTarget -notlike ('*' + $LetterDirPattern + '*') -or $normTarget -notlike '*.md') {
        Complete-Sentinel -RepoRoot $RepoRoot -Sentinel $SentinelName -Verdict 'pass' `
            -Tool $payload.ToolName -SessionId $payload.SessionId -Target $target -Mode $Mode `
            -Note '非跟进信目标，本哨兵不判'
    }

    # ── 名录（🔴 唯一数据源，脚本内零硬编码）
    $rosterPath = Join-Path $RepoRoot $RosterRelPath
    $rosterText = $null
    if (Test-Path -LiteralPath $rosterPath -PathType Leaf) {
        try { $rosterText = Get-Content -LiteralPath $rosterPath -Raw -Encoding UTF8 } catch { $rosterText = $null }
    }

    $unverifiableReason = ''
    if (-not $rosterText) {
        $unverifiableReason = ('名录正本读不到（{0}）' -f $rosterPath)
    }

    $roster = @{}   # 别名 → @{ Name; Gender }
    if (-not $unverifiableReason) {
        $byName = @{}
        # `姓名（男）` / `姓名（女，部门）` —— 姓名限 2~4 个汉字
        foreach ($m in [regex]::Matches($rosterText, '([一-龥]{2,4})（(男|女)')) {
            $n = $m.Groups[1].Value
            $g = $m.Groups[2].Value
            # 明显不是人名的词（名录正文里的说明性措辞）一律不收
            if ($n -match '名录|专员|部门|同事|全员|人员|以下|其中|如下') { continue }
            if ($byName.ContainsKey($n)) {
                if ($byName[$n] -ne $g) { $byName[$n] = '冲突' }
            } else {
                $byName[$n] = $g
            }
        }

        # 全名入表（性别冲突的丢弃 —— 名录自相矛盾时本哨兵没有结论可用）
        foreach ($n in $byName.Keys) {
            if ($byName[$n] -eq '冲突') { continue }
            $roster[$n] = @{ Name = $n; Gender = $byName[$n] }
        }

        # 名（去姓）别名：名录里那 7 个「会把语言直觉带偏」的名字在信里常单名出现。
        # 🔴 仍是从名录派生，不是硬编码；歧义（两人同名、或与某个全名撞车）一律不收。
        $shortMap = @{}
        foreach ($n in $roster.Keys) {
            if ($n.Length -lt 3) { continue }
            $s = $n.Substring(1)
            if ($roster.ContainsKey($s)) { continue }
            if ($shortMap.ContainsKey($s)) { $shortMap[$s] = $null } else { $shortMap[$s] = $roster[$n] }
        }
        foreach ($s in $shortMap.Keys) {
            if ($null -ne $shortMap[$s]) { $roster[$s] = $shortMap[$s] }
        }

        if ($roster.Count -eq 0) {
            $unverifiableReason = ('名录正本解析出 0 个人物（{0}）' -f $rosterPath)
        }
    }

    if ($unverifiableReason) {
        $msg = ('🔴 {0} 本类无法核验：{1}｜按 spec 放行，但本次判定不构成任何「没有问题」的结论。' -f $SentinelName, $unverifiableReason)
        Complete-Sentinel -RepoRoot $RepoRoot -Sentinel $SentinelName -Verdict 'unverifiable' `
            -Tool $payload.ToolName -SessionId $payload.SessionId -Target $target -Mode $Mode `
            -Note ('本类无法核验：' + $unverifiableReason) -Message $msg
    }

    # 别名按长度降序：同一位置优先匹配长名（全名胜过去姓的短名），避免短名把长名切碎
    $aliases = @($roster.Keys | Sort-Object -Property Length -Descending)

    $pronounOf = @{ '男' = '他'; '女' = '她' }

    $fileText = Get-SentinelTargetText -TargetPath $target
    $fileExempt = Test-SentinelFileExemption -MarkName $ExemptionMark -FileText $fileText -Segments $payload.Segments

    $findings = New-Object System.Collections.ArrayList

    if (-not $fileExempt) {
        foreach ($seg in $payload.Segments) {
            $resolved = Resolve-SentinelSegmentLines -SegmentText $seg.Text -FileText $fileText
            $skip = Get-SentinelLineContext -Lines $resolved.Lines -InFenceAtStart $resolved.InFenceAtStart -MarkName $ExemptionMark

            # ── 切段落：空行或「不判」行都是段落边界
            $para = New-Object System.Collections.ArrayList
            $flush = {
                if ($para.Count -eq 0) { return }

                # 拼接段落文本，同时记住每个字符属于哪一行
                $buf = New-Object System.Text.StringBuilder
                $lineOf = New-Object System.Collections.ArrayList
                foreach ($p in $para) {
                    foreach ($ch in [char[]]$p.Text) { [void]$buf.Append($ch); [void]$lineOf.Add($p.No) }
                    [void]$buf.Append(' '); [void]$lineOf.Add($p.No)
                }
                $text = $buf.ToString()

                # 段内所有名录人名出现位置（长名优先，不重叠）
                $hitsN = New-Object System.Collections.ArrayList
                $i = 0
                while ($i -lt $text.Length) {
                    $matched = $null
                    foreach ($a in $aliases) {
                        if (($i + $a.Length) -le $text.Length -and $text.Substring($i, $a.Length) -eq $a) { $matched = $a; break }
                    }
                    if ($matched) {
                        [void]$hitsN.Add(@{ Pos = $i; Alias = $matched; Info = $roster[$matched] })
                        $i += $matched.Length
                    } else { $i++ }
                }

                if ($hitsN.Count -eq 0) { $para.Clear(); return }

                # 🔴 同段出现多个不同性别的名录人名 ⇒ 归属不明确 ⇒ 整段放行
                $genders = @($hitsN | ForEach-Object { $_.Info.Gender } | Sort-Object -Unique)
                if ($genders.Count -ne 1) { $para.Clear(); return }

                $firstNamePos = ($hitsN | ForEach-Object { $_.Pos } | Measure-Object -Minimum).Minimum

                foreach ($pm in [regex]::Matches($text, '[他她]')) {
                    $pos = $pm.Index
                    if ($pos -lt $firstNamePos) { continue }               # 代词在人名之前 ⇒ 不是「其后最近」
                    $ch = $pm.Value
                    $next = if (($pos + 1) -lt $text.Length) { $text.Substring($pos + 1, 1) } else { '' }
                    $prev = if ($pos -gt 0) { $text.Substring($pos - 1, 1) } else { '' }
                    if ($next -eq '们') { continue }                        # 复数，归属不明确
                    if ($ch -eq '他' -and ($prev -eq '其' -or $prev -eq '吉' -or $next -eq '人')) { continue }  # 其他/吉他/他人

                    # 🔴 被引号单独括起来的代词是**词例引用**（在谈论这个字），不是在指代谁。
                    #    实测来源：真实跟进信里的「代词自检: … 全部写作「她」；「他」0 处」被误判 —— 而这句
                    #    恰恰是**做对了自检**的那句话。design 已预判此形态：「写称谓纪律时会举反例，
                    #    H4 若不认上下文，规则文档自己就违规」。
                    #    引号按码点写，不写字面量——单/双引号的字面量在 PowerShell 单引号串里
                    #    需要成对转义，写错了整脚本连解析都过不去（本班实测踩中一次）。
                    $openQuotes = [char[]]@(0x300C, 0x300E, 0x201C, 0x2018, 0x0022, 0x0027, 0x0060)
                    $closeQuotes = [char[]]@(0x300D, 0x300F, 0x201D, 0x2019, 0x0022, 0x0027, 0x0060)
                    if ($prev -and $next -and ($openQuotes -contains [char]$prev) -and ($closeQuotes -contains [char]$next)) { continue }

                    # 其前最近的那个名录人名
                    $owner = $null
                    foreach ($h in $hitsN) { if ($h.Pos -lt $pos) { $owner = $h } }
                    if (-not $owner) { continue }

                    $want = $pronounOf[$owner.Info.Gender]
                    if ($ch -ne $want) {
                        [void]$findings.Add(@{
                            Line    = $lineOf[$pos]
                            Located = $resolved.Located
                            Label   = $seg.Label
                            Person  = $owner.Info.Name
                            Alias   = $owner.Alias
                            Gender  = $owner.Info.Gender
                            Written = $ch
                            Correct = $want
                            Excerpt = $(
                                $s = [Math]::Max(0, $pos - 20); $len = [Math]::Min(45, $text.Length - $s)
                                $text.Substring($s, $len)
                            )
                        })
                    }
                }
                $para.Clear()
            }

            for ($i = 0; $i -lt $resolved.Lines.Count; $i++) {
                $ln = $resolved.Lines[$i]
                if ($skip[$i] -or -not ([string]$ln.Text).Trim()) { & $flush; continue }
                [void]$para.Add($ln)
            }
            & $flush
        }
    }

    if ($findings.Count -eq 0) {
        Complete-Sentinel -RepoRoot $RepoRoot -Sentinel $SentinelName -Verdict 'pass' `
            -Tool $payload.ToolName -SessionId $payload.SessionId -Target $target -Mode $Mode `
            -Note ('已按名录核对（{0} 个别名）' -f $roster.Count)
    }

    $sb = New-Object System.Text.StringBuilder
    [void]$sb.AppendLine(('🔴 {0}：本次写入的第三人称代词与人员名录正本不符，共 {1} 处（模式 {2}）' -f $SentinelName, $findings.Count, $Mode))
    [void]$sb.AppendLine(('   目标：{0}' -f $target))
    [void]$sb.AppendLine(('   名录：{0}' -f $RosterRelPath))
    foreach ($f in $findings) {
        $where = if ($f.Located) { '第 {0} 行' -f $f.Line } else { '片段内相对第 {0} 行（{1}，未能在文件中唯一定位）' -f $f.Line, $f.Label }
        [void]$sb.AppendLine(('   · {0}：{1}（名录记「{2}」）写成了「{3}」，应为「{4}」' -f $where, $f.Person, $f.Gender, $f.Written, $f.Correct))
        [void]$sb.AppendLine(('     ↳ …{0}…' -f $f.Excerpt))
    }
    [void]$sb.AppendLine('   处置：① 按名录改正；② 若本处是原样引用旧信/历史记录（不追改），')
    [void]$sb.AppendLine('         放进块引用或代码围栏，或在该行写 `代词豁免：<理由>`（🔴 必须带理由，只写标记不生效）。')

    Complete-Sentinel -RepoRoot $RepoRoot -Sentinel $SentinelName -Verdict 'violation' `
        -Tool $payload.ToolName -SessionId $payload.SessionId -Target $target -Mode $Mode `
        -Findings $findings.Count -Message $sb.ToString()

} catch {
    try {
        Write-SentinelHeartbeat -RepoRoot $RepoRoot -Sentinel $SentinelName -Verdict 'error' `
            -Mode $Mode -ErrorSummary $_.Exception.Message
    } catch { }
    try { [Console]::Error.WriteLine('⚠ ' + $SentinelName + ' 异常放行：' + $_.Exception.Message) } catch { }
    exit 0
}
