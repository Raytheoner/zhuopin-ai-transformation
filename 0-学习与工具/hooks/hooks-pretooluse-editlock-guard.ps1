<#
.SYNOPSIS
  PreToolUse 钩子（队列 §一 #381⑸ⓒ，openspec 变更包 cc-hooks-p3）：`Edit`/`Write`/
  `MultiEdit` 目标命中两份队列真身或两张接力卡、且无有效编辑锁时，拒绝本次调用。

.DESCRIPTION
  判据正本＝队列 §一 #381⑸ⓒ 原文 ＋ design.md 决策点 3。

  🔴 只判"锁文件当前是否存在有效（未陈旧）记录"，不判"是不是我持的"——`PreToolUse`
  钩子进程与本次 `acquire` CLI 调用是两个独立进程，无共享状态，无法可靠核对
  `--who` 身份；这仍能拦住协议〇.7 历史事故的主要形态（完全忘记 acquire、直接
  改队列文件），"A 持锁、B 也直接改"这种绕锁场景由既有的幽灵副本检测另行兜底。

  🔴 锁文件路径与 `工具-共享文档编辑锁.py` 用**同一把尺子**：两份队列真身（及其
  指针文件）共用锚定在机制环境队列文件的一把锁（`QUEUE_LOCK_ANCHOR`）；两张
  接力卡各自独立持锁（`_is_queue_system_target` 判定它们不属于"队列系统本体"）。
  这里不 import Python 模块（避免钩子依赖 Python 运行时），改为在 PowerShell 侧
  复刻同一份路径判定——两处判据分叉是本项目明确要防的形态，故本文件的判定表
  MUST 与 `工具-共享文档编辑锁.py::_is_queue_system_target`／`STALE_MINUTES`
  保持逐字同步，改动任一处需同改。
#>

$ErrorActionPreference = 'Stop'
try { [Console]::OutputEncoding = [Text.UTF8Encoding]::new($false) } catch {}

. (Join-Path $PSScriptRoot 'hooks-common.ps1')

$HookName = 'pretooluse-editlock-guard'

#: 🔴 须与 `工具-共享文档编辑锁.py::STALE_MINUTES` 保持同步（现值 30）。
$script:StaleMinutes = 30

#: 队列系统本体三个等价路径（含旧指针文件），共用锚定在机制环境文件的一把锁。
$script:QueueSystemPaths = @(
    '1-转型规划/0-全景路线图/跨桌任务队列-机制环境.md'
    '1-转型规划/0-全景路线图/跨桌任务队列-业务场景.md'
    '1-转型规划/0-全景路线图/跨桌任务队列.md'
)
$script:QueueLockAnchor = '1-转型规划/0-全景路线图/跨桌任务队列-机制环境.md'

#: 两张接力卡，各自独立持锁（不共享 `QueueLockAnchor`）。
$script:RelayCardPaths = @(
    '1-转型规划/0-全景路线图/session接力-Phase1收口.md'
    '1-转型规划/0-全景路线图/session接力-业务总线.md'
)

function Resolve-RepoRelative([string]$RepoRoot, [string]$Candidate) {
    try {
        if ([System.IO.Path]::IsPathRooted($Candidate)) {
            return [System.IO.Path]::GetFullPath($Candidate)
        }
        return [System.IO.Path]::GetFullPath((Join-Path $RepoRoot $Candidate))
    } catch { return $null }
}

function Get-LockPathForTarget([string]$RepoRoot, [string]$TargetPath) {
    <# 返回 @{ Protected=$bool; LockPath=<绝对路径或$null> }。 #>
    $targetFull = Resolve-RepoRelative $RepoRoot $TargetPath
    if (-not $targetFull) { return @{ Protected = $false; LockPath = $null } }

    foreach ($rel in $script:QueueSystemPaths) {
        $full = Resolve-RepoRelative $RepoRoot $rel
        if ($full -and $targetFull -eq $full) {
            $anchorFull = Resolve-RepoRelative $RepoRoot $script:QueueLockAnchor
            return @{ Protected = $true; LockPath = "$anchorFull.editlock" }
        }
    }
    foreach ($rel in $script:RelayCardPaths) {
        $full = Resolve-RepoRelative $RepoRoot $rel
        if ($full -and $targetFull -eq $full) {
            return @{ Protected = $true; LockPath = "$targetFull.editlock" }
        }
    }
    return @{ Protected = $false; LockPath = $null }
}

function Test-ValidLock([string]$LockPath) {
    <# 返回 @{ Valid=$bool; Reason=<string> }。任何解析失败均 Valid=$false 且说明原因
       （对宿主而言"判不了"与"确实无锁"处置相同——均要求先 acquire，不因判不了而放行，
       这是本判据的门禁语义所要求的保守方向）。#>
    if (-not (Test-Path -LiteralPath $LockPath -PathType Leaf)) {
        return @{ Valid = $false; Reason = '锁文件不存在' }
    }
    try {
        $raw = Get-Content -LiteralPath $LockPath -Raw -Encoding UTF8
        $obj = $raw | ConvertFrom-Json
        # 🔴 须与 `工具-共享文档编辑锁.py::_read_lock` 同一判据：release 是"改写为
        # released 标记、不删除文件"，held_since 仍是**原 acquire 时刻**、不会更新——
        # 若不检查这个字段，刚被合法 release 掉的锁会被误判为"仍在有效期内"。
        $objProps = Get-JsonPropertyNames $obj
        if ($objProps -contains 'released' -and $obj.released) {
            return @{ Valid = $false; Reason = '锁已被 release（released 标记）' }
        }
        if (-not ($objProps -contains 'held_since') -or -not $obj.held_since) {
            return @{ Valid = $false; Reason = '锁文件缺 held_since 字段' }
        }
        $heldSince = [datetime]::Parse($obj.held_since, $null,
            [System.Globalization.DateTimeStyles]::RoundtripKind)
        $ageMinutes = ((Get-Date).ToUniversalTime() - $heldSince.ToUniversalTime()).TotalMinutes
        if ($ageMinutes -ge $script:StaleMinutes) {
            return @{ Valid = $false; Reason = ("锁已陈旧（{0:N0} 分钟前持锁，超过 {1} 分钟阈值）" -f $ageMinutes, $script:StaleMinutes) }
        }
        return @{ Valid = $true; Reason = ("有效（{0}，{1:N0} 分钟前持锁）" -f $obj.who, $ageMinutes) }
    } catch {
        return @{ Valid = $false; Reason = "锁文件解析失败：$($_.Exception.Message)" }
    }
}

try {
    $stdinRaw = Read-SentinelStdin
    if (-not $stdinRaw -or -not $stdinRaw.Trim()) { exit 0 }
    $json = $stdinRaw | ConvertFrom-Json

    $jsonProps = Get-JsonPropertyNames $json
    $toolName = ''
    if ($jsonProps -contains 'tool_name') { $toolName = [string]$json.tool_name }
    $sessionId = ''
    if ($jsonProps -contains 'session_id') { $sessionId = [string]$json.session_id }

    if ($toolName -notin @('Edit', 'Write', 'MultiEdit')) {
        # matcher 已在 settings.json 层过滤，理论不会走到这里；防御性放行，不留痕
        # （非本判据管辖的工具，留痕反而混淆"本判据到底看了多少次"这个信号）。
        exit 0
    }

    $targetPath = ''
    $tiProps = Get-JsonPropertyNames $json.tool_input
    if ($tiProps -contains 'file_path') {
        $targetPath = [string]$json.tool_input.file_path
    } elseif ($tiProps -contains 'notebook_path') {
        $targetPath = [string]$json.tool_input.notebook_path
    }

    $repoRoot = Get-SentinelRepoRoot

    if (-not $targetPath) {
        Add-HooksAuditLine -RepoRoot $repoRoot -Hook $HookName -Verdict 'undetermined' `
            -Tool $toolName -SessionId $sessionId -Detail '无法从 tool_input 解析出写入目标'
        exit 0
    }

    $info = Get-LockPathForTarget -RepoRoot $repoRoot -TargetPath $targetPath
    if (-not $info.Protected) {
        Add-HooksAuditLine -RepoRoot $repoRoot -Hook $HookName -Verdict 'pass' `
            -Tool $toolName -SessionId $sessionId -Detail "非受保护目标：$targetPath"
        exit 0
    }

    $lockCheck = Test-ValidLock -LockPath $info.LockPath
    if ($lockCheck.Valid) {
        Add-HooksAuditLine -RepoRoot $repoRoot -Hook $HookName -Verdict 'pass' `
            -Tool $toolName -SessionId $sessionId -Detail "有效锁：$($lockCheck.Reason)｜目标：$targetPath"
        exit 0
    }

    $msg = "✗ 编辑锁门禁：目标 `"$targetPath`" 受保护（队列真身/接力卡），但未检测到有效编辑锁" +
        "（$($lockCheck.Reason)）。请先执行：`n" +
        "  python 0-学习与工具/工具-共享文档编辑锁.py acquire --who ""<身份>"" --note ""<原因>""`n" +
        "acquire 成功后立即重试本次编辑；改完请立刻 release（协议〇.7）。"
    Add-HooksAuditLine -RepoRoot $repoRoot -Hook $HookName -Verdict 'violation' `
        -Tool $toolName -SessionId $sessionId -Detail "$targetPath ｜ $($lockCheck.Reason)"
    [Console]::Error.WriteLine($msg)
    exit 2
} catch {
    try {
        Add-HooksAuditLine -RepoRoot (Get-SentinelRepoRoot) -Hook $HookName -Verdict 'error' `
            -Detail $_.Exception.Message
    } catch { }
    exit 0
}
