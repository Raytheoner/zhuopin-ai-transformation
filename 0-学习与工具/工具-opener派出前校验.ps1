# 工具-opener派出前校验.ps1 —— opener 批处理器（v1 串行版／v2 泳道版）共用的「派出前查队列态」helper
# （openspec 包 `opener-batch-archive-precheck`，队列 §一 #397／#561，design 决策点 1/2/3 已由 Shao Peishen
#   2026-09-12 签认 (a)/(a)/(a)；apply 泳道 OP-0912-Z）。
#
# 治的病：无头批派 opener 时不查那条队列行是不是已经做完了，于是重复派出、白跑一轮（实证：2026-08-24 run
#   20260824-165657 的 A4 对应 §一 #368，该行两天前已销号、当天已迁归档，仍被照常派出，烧掉 4.2 分钟一整个 session）。
# 🔴 底线＝fail-open：判不准时**照常派出**（白跑一次，有人在读那个 session），**绝不误跳过**（漏做且无人在场）。
#
# 用法（两个 runner 在「解析完成、-Only 过滤之后、任何派出/分组动作之前」dot-source 并调用一次）：
#   . (Join-Path $PSScriptRoot '工具-opener派出前校验.ps1')
#   $openers = Set-OpenerDispatchDecision -Openers $openers -RepoRoot $RepoRoot [-Force]
# 出参：同一数组，每个元素补 Skip([bool])／SkipReason([string])／QueueRows([int[]])／PrecheckNote([string])。
#
# 判据本体只有一份、在 Python：`工具-队列查询.py --row N --section 一 --include-archive --format json`——本文件只做
#   ① 从 opener 标题抽行号（决策点 2：先剥 `§四 #N(x)` 与 `§二 …`，再取「队列/§一 #N[／#M…]」；多行号取**合取**）；
#   ② 调 Python、只读 JSON 的 `done`（不解析中文文案、不依赖退出码——取证四：该工具「未找到」也曾 exit 0）；
#   ③ 映射四态：live-open ⇒ 派出／live-done ⇒ 跳过／archived ⇒ 跳过／unresolved ⇒ 派出＋告警；
#   ④ Python 起不来、超时、JSON 解析失败 ⇒ 派出＋告警（绝不 fail-closed）。
# 🔴 不在 PowerShell 里重写表格解析（决策点 3 否掉 (c)：PS 侧没有反引号游程屏蔽，含反引号路径的行会切错格，#314）。
# 🔴 不缓存查询结果（决策点 4 (a)）：每个 opener 各查一次，不落任何新文件。

Set-StrictMode -Off

# 抽行号：返回 [int[]]（可能为空）。
#   `【CC】#353 apply：…——队列 #353／§四 #108(a)`  → 353（§四 #108 先被剥掉）
#   `【CC】#397 批处理…（#396 治本）——队列 #397／#396` → 397, 396（标题开头那个裸 #397 不带锚点、不算）
#   `【Cowork】…——协议〇.8／§四 #44`               → （空）
function Get-OpenerQueueRowIds {
    param([string]$Title)
    if ([string]::IsNullOrWhiteSpace($Title)) { return @() }
    $t = $Title
    $t = [regex]::Replace($t, '§四\s*#\d+(?:\([a-z]\))?', '')
    $t = [regex]::Replace($t, '§二[^／/]*', '')
    $ids = New-Object System.Collections.Generic.List[int]
    # 锚点后允许一串 `#N`，以 ／ / 、 , ， 或空白分隔（`队列 #397／#396`）。
    foreach ($m in [regex]::Matches($t, '(?:队列|§一)\s*((?:#\d+\s*[／/、,，]?\s*)+)')) {
        foreach ($n in [regex]::Matches($m.Groups[1].Value, '#(\d+)')) {
            $v = [int]$n.Groups[1].Value
            if (-not $ids.Contains($v)) { $ids.Add($v) }
        }
    }
    return @($ids.ToArray())
}

# 调 Python 查一行。返回 pscustomobject：Ok（调用与解析是否成功）／Row／Done／Reason／Carrier／File／Line／Error。
# Ok=$false 的一律由调用方按 fail-open 处理。
function Invoke-QueueRowLookup {
    param([string]$RepoRoot, [int]$Row, [int]$TimeoutSec = 60)
    $script = Join-Path $RepoRoot '0-学习与工具\工具-队列查询.py'
    $res = [pscustomobject]@{ Ok = $false; Row = $Row; Done = $false; Reason = ''; Carrier = ''; File = ''; Line = $null; Error = '' }
    if (-not (Test-Path $script)) { $res.Error = "查询工具不存在：$script"; return $res }
    $py = Get-Command python -ErrorAction SilentlyContinue
    if (-not $py) { $res.Error = '找不到 python（不在 PATH）'; return $res }
    try {
        $psi = New-Object System.Diagnostics.ProcessStartInfo
        $psi.FileName = $py.Source
        $psi.Arguments = '"' + $script + '" --row ' + $Row + ' --section 一 --include-archive --format json'
        $psi.WorkingDirectory = $RepoRoot
        $psi.UseShellExecute = $false
        $psi.RedirectStandardOutput = $true
        $psi.RedirectStandardError = $true
        $psi.StandardOutputEncoding = [System.Text.Encoding]::UTF8
        $psi.StandardErrorEncoding = [System.Text.Encoding]::UTF8
        $psi.EnvironmentVariables['PYTHONIOENCODING'] = 'utf-8'
        $proc = [System.Diagnostics.Process]::Start($psi)
        $stdoutTask = $proc.StandardOutput.ReadToEndAsync()
        $stderrTask = $proc.StandardError.ReadToEndAsync()
        if (-not $proc.WaitForExit([int]($TimeoutSec * 1000))) {
            try { $proc.Kill() } catch { }
            $res.Error = "查询超时（>$TimeoutSec s）"
            return $res
        }
        $stdout = $stdoutTask.Result
        $stderr = $stderrTask.Result
        # JSON 只认 stdout 里以 `{` 开头的那一行（前面可能有 hook/告警文本）。
        $jsonLine = ($stdout -split "`r?`n" | Where-Object { $_.TrimStart().StartsWith('{') } | Select-Object -Last 1)
        if (-not $jsonLine) {
            $res.Error = '查询未输出 JSON（exit=' + $proc.ExitCode + '）：' + (($stdout + ' ' + $stderr).Trim() -replace '\s+', ' ')
            return $res
        }
        $obj = $jsonLine | ConvertFrom-Json
        if ($null -eq $obj -or $null -eq $obj.PSObject.Properties['done']) { $res.Error = 'JSON 缺 done 字段：' + $jsonLine; return $res }
        $res.Ok = $true
        $res.Done = [bool]$obj.done
        $res.Reason = [string]$obj.reason
        $res.Carrier = [string]$obj.carrier
        $res.File = if ($obj.file) { [string]$obj.file } else { '' }
        $res.Line = $obj.line
        if ($obj.error) { $res.Error = [string]$obj.error }
        return $res
    } catch {
        $res.Error = '调用/解析失败：' + $_.Exception.Message
        return $res
    }
}

# 主入口：给每个 opener 打 Skip/SkipReason。-Force ⇒ 全部不跳、日志留痕。
function Set-OpenerDispatchDecision {
    param(
        [Parameter(Mandatory = $true)][AllowEmptyCollection()][object[]]$Openers,
        [Parameter(Mandatory = $true)][string]$RepoRoot,
        [switch]$Force,
        [switch]$Quiet
    )
    $out = @()
    foreach ($op in $Openers) {
        $ids = @(Get-OpenerQueueRowIds -Title $op.Title)
        $skip = $false; $reason = ''; $note = ''
        if ($Force) {
            $reason = '[Force] 归档校验已被绕过'
            $note = $reason
        } elseif ($ids.Count -eq 0) {
            # 无行号标题＝正常形态（如 A2 的 `协议〇.8／§四 #44`）——告警文案与「写了行号但查不到」区分。
            $note = 'no-row-ref（标题无 §一 行号引用，照常派出）'
        } else {
            $parts = @(); $allDone = $true; $anyFail = $false
            foreach ($id in $ids) {
                $r = Invoke-QueueRowLookup -RepoRoot $RepoRoot -Row $id
                if (-not $r.Ok) {
                    $anyFail = $true; $allDone = $false
                    $parts += ('#' + $id + ' precheck-failed（' + $r.Error + '）')
                    continue
                }
                $where = if ($r.File) { (Split-Path -Leaf $r.File) + $(if ($null -ne $r.Line) { ':' + $r.Line } else { '' }) } else { '' }
                if ($r.Done) {
                    $parts += ('#' + $id + ' ' + $r.Reason + $(if ($where) { '@' + $where } else { '' }))
                } else {
                    $allDone = $false
                    $parts += ('#' + $id + ' ' + $r.Reason + $(if ($where) { '@' + $where } elseif ($r.Reason -eq 'unresolved') { '（live 与归档均未命中，照常派出）' } else { '' }) + $(if ($r.Error) { '（' + $r.Error + '）' } else { '' }))
                }
            }
            $note = ($parts -join '；')
            if ($allDone -and -not $anyFail) { $skip = $true; $reason = $note }
        }
        foreach ($pair in @(@('Skip', $skip), @('SkipReason', $reason), @('QueueRows', $ids), @('PrecheckNote', $note))) {
            $op | Add-Member -NotePropertyName $pair[0] -NotePropertyValue $pair[1] -Force
        }
        if (-not $Quiet) {
            if ($skip) {
                Write-Host ('  ⏭ SKIPPED ' + $op.Id + ' ｜ ' + $reason) -ForegroundColor Yellow
            } elseif ($Force) {
                Write-Host ('  ' + $reason + ' ' + $op.Id) -ForegroundColor DarkYellow
            } elseif ($note -match 'precheck-failed|unresolved|no-row-ref') {
                Write-Host ('  ⚠ 派出前校验告警 ' + $op.Id + ' ｜ ' + $note + ' ⇒ 照常派出') -ForegroundColor Yellow
            }
        }
        $out += $op
    }
    # 直接输出数组元素（不用 `,$out` 包一层——那样调用方 @() 拿到的是「一个元素＝整个数组」，Where-Object 全部误判）；调用方以 @(...) 收。
    return $out
}
