<#
.SYNOPSIS
  项目级写入时刻哨兵 · 公共框架（openspec 变更包 project-hooks-write-time-sentinels）

.DESCRIPTION
  被 sentinel-*.ps1 以 dot-source 方式载入。承接 specs/hooks-common-framework/spec.md
  的五条 Requirement：

    ① 只对「解析出的写入目标 ＋ 本次新增内容」判定，禁止对原始命令串做正则；
    ② fail-open（try/catch → exit 0），且异常必须留痕，禁止静默失败；
    ③ 每一次运行（含放行、含异常）都落心跳，自证在岗；
    ④ 拦截留痕复用既有 audit-blocks 日志形态，不新造日志文件；
    ⑤ 行内留痕式逃生阀（`<哨兵名>豁免：<理由>`，无理由不生效）。

  🔴 本文件不做任何判定，只提供输入解析、上下文、留痕与退出。判据在各哨兵脚本里。

.NOTES
  设计依据 design.md 决策点 2：判定输入一律取 stdin JSON 里解析出的 file_path
  与本次写入引入的内容，绝不对 command 字段或整条命令串做路径正则——
  「正文里提到一个路径」不等于「写入了那个路径」。
#>

Set-StrictMode -Version Latest

# ─────────────────────────────────────────────────────────────────────────────
# 常量
# ─────────────────────────────────────────────────────────────────────────────

# 判定范围内的文本类扩展名（spec: hooks-mojibake-sentinel）。其余一律视为二进制，放行且不读内容。
$script:SentinelTextExtensions = @('.md', '.py', '.ps1', '.json', '.yaml', '.yml')

# 心跳文件名（单一定名文件，MUST NOT 按日期或会话分片 —— 见 design 决策点 1 «刻意不做的两件事»）
$script:SentinelHeartbeatRelPath = 'reports/hooks-heartbeat.json'

# 读目标文件用于「定位新增内容的绝对行号」与「上下文判定」的体量上限；超过即降级为相对行号。
$script:SentinelMaxFileBytes = 8MB


# ─────────────────────────────────────────────────────────────────────────────
# 时刻（🔴 一律显式标基准，见根 CLAUDE.md「时间戳必判 UTC vs Win 本地」）
# ─────────────────────────────────────────────────────────────────────────────

function Get-SentinelTimestamp {
    <# 返回带时区偏移的本机时刻，形如 2026-08-29T09:04:31.123+08:00 #>
    return (Get-Date).ToString('yyyy-MM-ddTHH:mm:ss.fffzzz')
}

function Get-SentinelTimestampBasis {
    $tz = [System.TimeZoneInfo]::Local
    $off = [System.TimeZoneInfo]::Local.GetUtcOffset([DateTime]::Now)
    $sign = if ($off.Ticks -lt 0) { '-' } else { '+' }
    return ('本机时区 {0}（UTC{1}{2:00}:{3:00}），非 UTC' -f $tz.Id, $sign, [Math]::Abs($off.Hours), [Math]::Abs($off.Minutes))
}


# ─────────────────────────────────────────────────────────────────────────────
# 仓库根
# ─────────────────────────────────────────────────────────────────────────────

function Get-SentinelRepoRoot {
    <#
      按 `git rev-parse --git-common-dir` 定位**主工作区**根 —— 与
      `0-学习与工具/工具-共享文档编辑锁.py` 的 REPO_ROOT 同一把尺子。

      🔴 为什么不用 cwd：CC 常在 linked worktree 里干活，若心跳随 cwd 落到各自
      worktree 的 reports/ 下，就会分裂成 N 份、每份都显得「很久没心跳」——
      «最近 N 天零心跳即告警» 会因此常年误报，等于把自证在岗这条准入条件废掉。
    #>
    param([string]$StartDir)

    # 单测夹具专用：把心跳与名录锚到一个临时目录，使「名录缺失」「坏心跳」等
    # 反例可在不动生产仓库的前提下构造。生产运行时该变量不存在。
    if ($env:ZHUOPIN_SENTINEL_REPO_ROOT -and (Test-Path -LiteralPath $env:ZHUOPIN_SENTINEL_REPO_ROOT)) {
        return (Resolve-Path -LiteralPath $env:ZHUOPIN_SENTINEL_REPO_ROOT).Path
    }

    if (-not $StartDir) { $StartDir = $PWD.Path }

    try {
        $common = & git -C $StartDir rev-parse --path-format=absolute --git-common-dir 2>$null
        if ($LASTEXITCODE -eq 0 -and $common) {
            $commonDir = ([string]$common).Trim()
            if ($commonDir) {
                $parent = Split-Path -Parent $commonDir
                if ($parent -and (Test-Path -LiteralPath $parent)) { return $parent }
            }
        }
    } catch { }

    # 兜底：本脚本位于 <repo>/0-学习与工具/hooks/ ⇒ 上溯两级即仓库根
    try {
        $here = Split-Path -Parent $PSCommandPath
        $guess = Split-Path -Parent (Split-Path -Parent $here)
        if ($guess -and (Test-Path -LiteralPath $guess)) { return $guess }
    } catch { }

    return $StartDir
}


# ─────────────────────────────────────────────────────────────────────────────
# 运行模式（warn ／ block）
# ─────────────────────────────────────────────────────────────────────────────

function Get-SentinelMode {
    <#
      上线形态由 `0-学习与工具/hooks/sentinels-mode.json` 决定：{"mode":"warn"|"block"}。

      🔴 判定逻辑与本开关无关 —— 命中就是命中，两种模式下都会写心跳与 audit 留痕；
      本开关只决定最后一步的退出码：
        warn  ⇒ exit 0（观察期，只计数不打断）
        block ⇒ exit 2（stderr 反馈给模型当场修复）

      文件缺失/坏 JSON/取值非法 ⇒ 一律回落 warn（更保守的那一侧），并把原因带进心跳。
    #>
    param([string]$RepoRoot)

    $result = [ordered]@{ Mode = 'warn'; Source = 'default'; Note = '' }
    # 回落原因必须跟着进心跳 —— 「以为在 block、其实在 warn」是一条不会报错的静默降级
    $script:SentinelModeNote = ''
    try {
        $p = Join-Path $RepoRoot '0-学习与工具/hooks/sentinels-mode.json'
        if (-not (Test-Path -LiteralPath $p)) {
            $result.Note = '模式文件不存在，回落 warn'
            return $result
        }
        $raw = Get-Content -LiteralPath $p -Raw -Encoding UTF8
        $obj = $raw | ConvertFrom-Json
        $m = [string]$obj.mode
        if ($m -eq 'block' -or $m -eq 'warn') {
            $result.Mode = $m
            $result.Source = $p
        } else {
            $result.Note = ('模式文件取值非法（{0}），回落 warn' -f $m)
        }
    } catch {
        $result.Note = ('模式文件读取失败（{0}），回落 warn' -f $_.Exception.Message)
    }
    $script:SentinelModeNote = $result.Note
    return $result
}


# ─────────────────────────────────────────────────────────────────────────────
# stdin JSON 解析
# ─────────────────────────────────────────────────────────────────────────────

function Read-SentinelStdin {
    <#
      以**严格 UTF-8** 读 stdin。

      🔴 为什么用 throwOnInvalidBytes=true：H3 判的就是 U+FFFD，而宽松解码器遇到
      非法字节**自己就会产出 U+FFFD** —— 那样哨兵会把自己的解码故障当成对方的乱码，
      是一条稳定造假的路径。严格解码让这种情形以异常现身，走「无法判定」而不是「有违规」。
    #>
    $stdin = [Console]::OpenStandardInput()
    $enc = New-Object System.Text.UTF8Encoding($false, $true)
    $reader = New-Object System.IO.StreamReader($stdin, $enc)
    try { return $reader.ReadToEnd() } finally { $reader.Dispose() }
}

function ConvertTo-SentinelPayload {
    <#
      从 hook 的 stdin JSON 解析出判定所需的一切。返回 hashtable：
        Ok           解析是否成功
        Reason       Ok=$false 时的原因（进心跳，禁止静默）
        ToolName     Edit / Write / MultiEdit / NotebookEdit / …
        SessionId
        Cwd
        TargetPath   本次写入目标（file_path / notebook_path），🔴 绝不从 command 猜
        Segments     本次写入引入的内容片段数组，每项 @{ Text=...; Label=... }

      🔴 MUST NOT 读 tool_input.command —— 那正是 design 决策点 2 判死的形态。
    #>
    param([string]$Raw)

    $out = [ordered]@{
        Ok = $false; Reason = ''; ToolName = ''; SessionId = ''; Cwd = ''
        TargetPath = ''; Segments = @()
    }

    if (-not $Raw -or -not $Raw.Trim()) {
        $out.Reason = 'stdin 为空'
        return $out
    }

    $json = $Raw | ConvertFrom-Json

    if ($json.PSObject.Properties.Name -contains 'tool_name') { $out.ToolName = [string]$json.tool_name }
    if ($json.PSObject.Properties.Name -contains 'session_id') { $out.SessionId = [string]$json.session_id }
    if ($json.PSObject.Properties.Name -contains 'cwd') { $out.Cwd = [string]$json.cwd }

    if (-not ($json.PSObject.Properties.Name -contains 'tool_input')) {
        $out.Reason = 'stdin JSON 无 tool_input'
        return $out
    }
    $ti = $json.tool_input
    $names = @($ti.PSObject.Properties.Name)

    if ($names -contains 'file_path' -and $ti.file_path) { $out.TargetPath = [string]$ti.file_path }
    elseif ($names -contains 'notebook_path' -and $ti.notebook_path) { $out.TargetPath = [string]$ti.notebook_path }

    if (-not $out.TargetPath) {
        $out.Reason = ('无法从 tool_input 解析出写入目标（tool_name={0}）' -f $out.ToolName)
        return $out
    }

    $segs = New-Object System.Collections.ArrayList
    if ($names -contains 'content' -and $null -ne $ti.content) {
        [void]$segs.Add(@{ Text = [string]$ti.content; Label = 'content' })
    }
    if ($names -contains 'new_string' -and $null -ne $ti.new_string) {
        [void]$segs.Add(@{ Text = [string]$ti.new_string; Label = 'new_string' })
    }
    if ($names -contains 'new_source' -and $null -ne $ti.new_source) {
        [void]$segs.Add(@{ Text = [string]$ti.new_source; Label = 'new_source' })
    }
    if ($names -contains 'edits' -and $ti.edits) {
        $i = 0
        foreach ($e in @($ti.edits)) {
            $i++
            if ($e.PSObject.Properties.Name -contains 'new_string' -and $null -ne $e.new_string) {
                [void]$segs.Add(@{ Text = [string]$e.new_string; Label = ('edits[{0}].new_string' -f $i) })
            }
        }
    }

    $out.Segments = @($segs)
    if ($out.Segments.Count -eq 0) {
        $out.Reason = ('目标已解析（{0}），但本次无可判定的新增内容' -f $out.TargetPath)
        return $out
    }

    $out.Ok = $true
    return $out
}


# ─────────────────────────────────────────────────────────────────────────────
# 目标文件读取与行号定位
# ─────────────────────────────────────────────────────────────────────────────

function Test-SentinelTextTarget {
    param([string]$TargetPath)
    $ext = [System.IO.Path]::GetExtension($TargetPath)
    if (-not $ext) { return $false }
    return $script:SentinelTextExtensions -contains $ext.ToLowerInvariant()
}

function Get-SentinelTargetText {
    <#
      读目标文件全文，**只用于两件事**：① 把本次新增内容定位到绝对行号；
      ② 判断插入点是否落在代码围栏内部（上下文）。

      🔴 绝不用它做违规判定 —— spec 明写「MUST NOT 扫描目标文件中本次未改动的既有内容」。
      本函数的两个用途都只会让判定**更宽松**（给出更准的行号、或额外放行），
      在任何情况下都不可能凭既有内容制造出一条违规。读失败 ⇒ 返回 $null，降级为相对行号。
    #>
    param([string]$TargetPath)
    try {
        if (-not (Test-Path -LiteralPath $TargetPath -PathType Leaf)) { return $null }
        $fi = Get-Item -LiteralPath $TargetPath
        if ($fi.Length -gt $script:SentinelMaxFileBytes) { return $null }
        return (Get-Content -LiteralPath $TargetPath -Raw -Encoding UTF8)
    } catch { return $null }
}

function Resolve-SentinelSegmentLines {
    <#
      把一个新增内容片段切成行，并尽力给出**文件里的绝对行号**。
      定位不到（新内容不在文件里、文件读不到、多处重复）⇒ Located=$false，行号退化为片段内相对行号，
      并在反馈里注明，绝不假装成绝对行号。

      返回 @{ Lines=@(@{ No=..; Text=..; }); Located=$bool; InFenceAtStart=$bool }
    #>
    param([string]$SegmentText, [string]$FileText)

    $lines = $SegmentText -split "`r?`n"
    $baseLine = 1
    $located = $false
    $inFence = $false

    if ($FileText) {
        # 🔴 定位前把两侧换行统一成 LF：工具侧传来的新增内容与磁盘上的文件常常
        #    一个是 LF、一个是 CRLF，直接 IndexOf 会一路找不到，于是行号全部退化
        #    成「片段内相对行号」——那是一种不报错、只是让反馈变难用的静默降级。
        #    统一后行数不变，行号计算完全等价。
        $ft = $FileText -replace "`r`n", "`n"
        $SegmentText = $SegmentText -replace "`r`n", "`n"
        $lines = $SegmentText -split "`n"
        $idx = $ft.IndexOf($SegmentText, [StringComparison]::Ordinal)
        if ($idx -ge 0) {
            $last = $ft.LastIndexOf($SegmentText, [StringComparison]::Ordinal)
            if ($idx -eq $last) {
                $FileText = $ft
                $located = $true
                $prefix = $FileText.Substring(0, $idx)
                $baseLine = ([regex]::Matches($prefix, "`n")).Count + 1
                # 前缀里的围栏开合状态 —— 只可能让判定更宽松（额外放行），不可能制造违规
                $fenceCount = 0
                foreach ($pl in ($prefix -split "`r?`n")) {
                    if ($pl -match '^\s*(```|~~~)') { $fenceCount++ }
                }
                $inFence = (($fenceCount % 2) -eq 1)
            }
        }
    }

    $result = New-Object System.Collections.ArrayList
    for ($i = 0; $i -lt $lines.Count; $i++) {
        [void]$result.Add(@{ No = ($baseLine + $i); Text = $lines[$i] })
    }
    return @{ Lines = @($result); Located = $located; InFenceAtStart = $inFence }
}


# ─────────────────────────────────────────────────────────────────────────────
# 上下文：代码围栏 ／ 块引用 ／ 逃生阀
# ─────────────────────────────────────────────────────────────────────────────

function Get-SentinelExemptionRegex {
    param([string]$MarkName)
    # `<哨兵名>豁免：<理由>` —— 🔴 理由必须非空，只有标记没有理由的不生效
    return ('{0}豁免\s*[：:]\s*\S' -f [regex]::Escape($MarkName))
}

function Test-SentinelFileExemption {
    <#
      文件级豁免：被检查文件内任意一处写有 `<哨兵名>豁免：<理由>` ⇒ 整份文件本次不判。

      为什么要有文件级：H3 的 spec 自身、事故复盘件、以及本纪律的说明文档，都必须**原样**
      保留当时那个坏字节／那个错代词，而它们往往被引用在正文（不在围栏内）。
      design 决策点 2 已写明：「一个连自己的规则文档都写不进去的哨兵，第一周就会被关掉。」
      豁免进 git、值周巡检看得见，且不新增任何写盘路径 —— 与框架 spec「行内留痕式」同一形态。
    #>
    param([string]$MarkName, [string]$FileText, [object]$Segments)

    $re = Get-SentinelExemptionRegex -MarkName $MarkName
    if ($FileText -and ($FileText -match $re)) { return $true }
    foreach ($s in @($Segments)) {
        if ($s.Text -and ($s.Text -match $re)) { return $true }
    }
    return $false
}

function Get-SentinelLineContext {
    <#
      逐行标注三类「不判」上下文：代码围栏内、块引用、行内豁免。
      入参 Lines 来自 Resolve-SentinelSegmentLines，InFenceAtStart 是片段起点处的围栏状态。
      返回与 Lines 等长的布尔数组：$true = 该行跳过判定。
    #>
    param([object]$Lines, [bool]$InFenceAtStart, [string]$MarkName)

    $re = Get-SentinelExemptionRegex -MarkName $MarkName
    $inFence = $InFenceAtStart
    $skip = New-Object System.Collections.ArrayList

    foreach ($ln in @($Lines)) {
        $t = [string]$ln.Text
        $isFenceMarker = ($t -match '^\s*(```|~~~)')
        $skipThis = $false

        if ($isFenceMarker) { $skipThis = $true }        # 围栏行本身不判
        elseif ($inFence) { $skipThis = $true }          # 围栏内不判
        elseif ($t -match '^\s*>') { $skipThis = $true } # 块引用不判（历史记录不追改）
        elseif ($t -match $re) { $skipThis = $true }     # 行内豁免（带理由）

        [void]$skip.Add($skipThis)
        if ($isFenceMarker) { $inFence = -not $inFence }
    }
    return @($skip)
}


# ─────────────────────────────────────────────────────────────────────────────
# 留痕：心跳 ＋ audit-blocks
# ─────────────────────────────────────────────────────────────────────────────

function Write-SentinelHeartbeat {
    <#
      单一定名文件、覆盖写、每一次运行都写（含放行、含异常）。
      🔴 MUST NOT 按日期或会话分片 —— 分片会造出无限增长的文件形态（#322 的坑）。

      同时维护一份很小的累计计数（runs.byVerdict），供 warn 观察期统计误报率；
      逐条事件在 audit 日志里，心跳只负责「它还在岗吗」。
    #>
    param(
        [string]$RepoRoot,
        [string]$Sentinel,
        [string]$Verdict,       # pass / violation / undetermined / unverifiable / error
        [string]$Tool = '',
        [string]$SessionId = '',
        [string]$Target = '',
        [string]$Mode = 'warn',
        [int]$Findings = 0,
        [string]$ErrorSummary = '',
        [string]$Note = ''
    )

    try {
        $modeNote = ''
        try { if ($script:SentinelModeNote) { $modeNote = $script:SentinelModeNote } } catch { }
        if ($modeNote) { $Note = ($Note + '｜模式：' + $modeNote).TrimStart([char]0xFF5C) }

        $dir = Join-Path $RepoRoot 'reports'
        if (-not (Test-Path -LiteralPath $dir)) { New-Item -ItemType Directory -Path $dir -Force | Out-Null }
        $path = Join-Path $RepoRoot $script:SentinelHeartbeatRelPath

        $counts = [ordered]@{}
        $total = 0
        if (Test-Path -LiteralPath $path) {
            try {
                $prev = (Get-Content -LiteralPath $path -Raw -Encoding UTF8) | ConvertFrom-Json
                if ($prev.PSObject.Properties.Name -contains 'runs') {
                    if ($prev.runs.PSObject.Properties.Name -contains 'total') { $total = [int]$prev.runs.total }
                    if ($prev.runs.PSObject.Properties.Name -contains 'byVerdict') {
                        foreach ($p in $prev.runs.byVerdict.PSObject.Properties) { $counts[$p.Name] = [int]$p.Value }
                    }
                }
            } catch {
                # 上一份心跳是坏 JSON：不静默 —— 计数从零重建，并把这件事写进本次 note
                $Note = ('（上一份心跳文件无法解析，累计计数已重建）' + $Note)
            }
        }
        $total++
        if ($counts.Contains($Verdict)) { $counts[$Verdict] = [int]$counts[$Verdict] + 1 } else { $counts[$Verdict] = 1 }

        $obj = [ordered]@{
            schemaVersion = 1
            lastRun       = (Get-SentinelTimestamp)
            lastRunBasis  = (Get-SentinelTimestampBasis)
            sentinel      = $Sentinel
            mode          = $Mode
            verdict       = $Verdict
            findings      = $Findings
            tool          = $Tool
            sessionId     = $SessionId
            target        = $Target
            error         = $ErrorSummary
            note          = $Note
            runs          = [ordered]@{ total = $total; byVerdict = $counts }
        }

        $tmp = "$path.tmp"
        $obj | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $tmp -Encoding UTF8
        Move-Item -LiteralPath $tmp -Destination $path -Force
    } catch {
        # 心跳都写不了也不能打断对方的写入 —— fail-open 是本框架的第一原则
    }
}

function Add-SentinelAuditRecord {
    <#
      复用既有 audit-blocks 日志形态（TSV 六列：时刻 / 事件 / 工具 / session_id / 目标 / 命中规则）。
      🔴 MUST NOT 新造任何日志文件形态。
      事件列：block（拦截）／warn（观察期命中但未拦）。
    #>
    param(
        [string]$Event, [string]$Tool, [string]$SessionId, [string]$Target, [string]$Rule
    )
    try {
        $home1 = $env:USERPROFILE
        if (-not $home1) { $home1 = $HOME }
        $dir = Join-Path $home1 '.claude'
        if (-not (Test-Path -LiteralPath $dir)) { return }
        $name = 'audit-blocks-{0}.log' -f (Get-Date -Format 'yyyyMMdd')
        $path = Join-Path $dir $name
        $flat = { param($s) (([string]$s) -replace "[`t`r`n]", ' ') }
        $line = @(
            (Get-SentinelTimestamp), $Event, (& $flat $Tool), (& $flat $SessionId), (& $flat $Target), (& $flat $Rule)
        ) -join "`t"
        Add-Content -LiteralPath $path -Value $line -Encoding UTF8
    } catch { }
}


# ─────────────────────────────────────────────────────────────────────────────
# 统一收口
# ─────────────────────────────────────────────────────────────────────────────

function Complete-Sentinel {
    <#
      所有哨兵的唯一出口。负责：写心跳 → （命中时）写 audit → 按模式决定退出码。

      Verdict 语义：
        pass          判过了，没有违规
        violation     命中判据
        undetermined  解析不出目标/新增内容 ⇒ 放行，但记为「无法判定」，禁止记成「没有违规」
        unverifiable  判据的数据源不可用（如名录正本缺失）⇒ 放行并明说「本类无法核验」
        error         异常 ⇒ 放行，异常摘要进心跳
    #>
    param(
        [string]$RepoRoot, [string]$Sentinel, [string]$Verdict,
        [string]$Tool = '', [string]$SessionId = '', [string]$Target = '',
        [string]$Mode = 'warn', [int]$Findings = 0,
        [string]$ErrorSummary = '', [string]$Note = '', [string]$Message = ''
    )

    Write-SentinelHeartbeat -RepoRoot $RepoRoot -Sentinel $Sentinel -Verdict $Verdict `
        -Tool $Tool -SessionId $SessionId -Target $Target -Mode $Mode `
        -Findings $Findings -ErrorSummary $ErrorSummary -Note $Note

    if ($Verdict -eq 'violation') {
        $ev = if ($Mode -eq 'block') { 'block' } else { 'warn' }
        Add-SentinelAuditRecord -Event $ev -Tool $Tool -SessionId $SessionId -Target $Target `
            -Rule ('{0}｜命中 {1} 处' -f $Sentinel, $Findings)
        if ($Message) { [Console]::Error.WriteLine($Message) }
        if ($Mode -eq 'block') { exit 2 }
        exit 0
    }

    if ($Message) { [Console]::Error.WriteLine($Message) }
    exit 0
}
