<#
.SYNOPSIS
  PreToolUse 钩子（队列 §一 #381⑸ⓗ2，K3 口径）：`Read`/`Grep`/`Bash` 目标
  命中两份队列真身或队列归档件时拒绝本次调用，提示改用查询工具。

.DESCRIPTION
  判据正本＝队列 §一 #381⑸ⓗ2 原文 ＋
  `1-转型规划/0-全景路线图/跨桌任务队列瘦身-方案-2026-09-04.md` §二 K3 ＋
  `.claude/rules/队列与落库.md`「读侧禁通读」。

  两份队列真身单行可达 78 KB——`Read` 全文或对其 `Grep` 一次命中就把整行
  原文灌进上下文（实测 ≈3 万 tokens／行）。本钩子只做"挡在门口"这一件
  事，合法读法（判行状态 `--row`、扫池 `--digest`、核触碰区
  `--digest --grep`）一律指向 `工具-队列查询.py`。

  🔴 **`Read`／`Grep` 只判"结构化目标字段是否精确命中"（`file_path`／
  `path`），不对内容或命令串做正则**——同 `hooks-common.ps1` 决策点 2
  既有立场（写侧哨兵"判定输入一律取 stdin JSON 里解析出的 file_path，
  绝不对 command 字段做路径正则"）：这两个工具本就有结构化路径字段，
  不需要猜。`Grep` 未传 `path`（默认从 cwd 搜索）时本钩子不拦——那是
  "没有目标字段可判"，不是"判了不命中"，同源头治理立场，不用目录归属
  之类的模糊启发式去猜它可能扫到什么（见 `Test-ProtectedQueueTarget`
  与 K3 判据"目标命中"字面语义，不做假设性扩展）。

  🔴 **唯独 `Bash` 例外**：`Bash` 的 `tool_input` 只有一个不透明的
  `command` 字符串、没有结构化路径字段，除了在命令文本里找"读命令名 ＋
  目标文件名"两者同时出现，没有别的信号可用——这是本钩子唯一对文本做
  正则匹配的地方，且刻意收窄到四个具名读命令（`Get-Content`/`cat`/
  `grep`/`Select-String`），不管其它命令（如 `git show`/`wc -l`）。

  🔴 **白名单存在的真实理由**（不是防御性调味）：命令行本身在调用
  编辑锁／队列查询／sweep／lint 四个机制工具之一时整条放行——不这样做
  会误伤合法调用。具体撞车实例：本次同批新增的
  `工具-队列查询.py --digest --grep <关键词> --file .../跨桌任务队列-归档-X.md`
  是文档标注的合规用法，命令行字面同时含"grep"（来自 `--grep` 标志）
  与一个归档文件名——若不白名单，K3 新增的 `--grep` 功能会被 K3 自己
  的读守卫反噬。
#>

$ErrorActionPreference = 'Stop'
try { [Console]::OutputEncoding = [Text.UTF8Encoding]::new($false) } catch {}

. (Join-Path $PSScriptRoot 'hooks-common.ps1')

$HookName = 'pretooluse-queue-read-guard'

#: 两份队列真身（精确路径，非前缀/包含）。
$script:ProtectedExactRel = @(
    '1-转型规划/0-全景路线图/跨桌任务队列-机制环境.md'
    '1-转型规划/0-全景路线图/跨桌任务队列-业务场景.md'
)
#: 归档件——同目录下 `跨桌任务队列-归档-*.md`（按父目录 + 文件名正则匹配，
#: 不满足"精确路径"的前提，故与上面两份分开处理）。
$script:ProtectedArchiveDirRel = '1-转型规划/0-全景路线图'
$script:ProtectedArchiveNameRegex = '^跨桌任务队列-归档-.+\.md$'

#: 白名单机制工具——Bash 命令行含其一（作为被执行的脚本路径子串）即整条
#: 放行，见文件头 DESCRIPTION 撞车实例。
$script:AllowlistedToolScripts = @(
    '工具-共享文档编辑锁\.py'
    '工具-队列查询\.py'
    '工具-落库sweep\.py'
    '工具-队列结构lint\.py'
)

#: Bash 读命令名——大小写不敏感匹配（`-imatch`）：PowerShell cmdlet 本就
#: 大小写不敏感，`cat`/`grep` 是常见 POSIX 别名/Git Bash 场景，来源不定。
$script:BashReadVerbs = @('Get-Content', 'cat', 'grep', 'Select-String')

$script:GuidanceMsg = '改用 python 0-学习与工具/工具-队列查询.py --row N' +
    '（判行状态）／--digest（扫池）／--digest --grep <关键词>（核触碰区），' +
    '见 .claude/rules/队列与落库.md「读侧禁通读」（K3，队列 §一 #381⑸）。'

function Resolve-RepoRelative([string]$RepoRoot, [string]$Candidate) {
    try {
        if ([System.IO.Path]::IsPathRooted($Candidate)) {
            return [System.IO.Path]::GetFullPath($Candidate)
        }
        return [System.IO.Path]::GetFullPath((Join-Path $RepoRoot $Candidate))
    } catch { return $null }
}

function Test-ProtectedQueueTarget([string]$RepoRoot, [string]$TargetPath) {
    <# 目标（`file_path`／`path`）是否精确命中两份队列真身或归档件。 #>
    $full = Resolve-RepoRelative $RepoRoot $TargetPath
    if (-not $full) { return $false }

    foreach ($rel in $script:ProtectedExactRel) {
        $candidateFull = Resolve-RepoRelative $RepoRoot $rel
        if ($candidateFull -and $full -eq $candidateFull) { return $true }
    }

    $archiveDirFull = Resolve-RepoRelative $RepoRoot $script:ProtectedArchiveDirRel
    if ($archiveDirFull) {
        $parent = Split-Path -Parent $full
        $leaf = Split-Path -Leaf $full
        if ($parent -eq $archiveDirFull -and $leaf -match $script:ProtectedArchiveNameRegex) {
            return $true
        }
    }
    return $false
}

function Test-BashAllowlisted([string]$Command) {
    foreach ($pattern in $script:AllowlistedToolScripts) {
        if ($Command -match $pattern) { return $true }
    }
    return $false
}

function Test-BashHitsProtectedTarget([string]$Command) {
    <# 返回 @{ Hit=$bool; Verb=<string或$null>; Target=<string或$null> }。
       须同时命中"读命令名"与"目标文件名"两个条件——只命中其一不算
       （见文件头 DESCRIPTION：单独出现"grep"很常见，如 pytest -k grep）。#>
    $verbHit = $null
    foreach ($verb in $script:BashReadVerbs) {
        if ($Command -imatch ('\b' + [regex]::Escape($verb) + '\b')) {
            $verbHit = $verb
            break
        }
    }
    if (-not $verbHit) { return @{ Hit = $false; Verb = $null; Target = $null } }

    foreach ($rel in $script:ProtectedExactRel) {
        $name = Split-Path -Leaf $rel
        if ($Command.Contains($name)) {
            return @{ Hit = $true; Verb = $verbHit; Target = $name }
        }
    }
    $m = [regex]::Match($Command, '跨桌任务队列-归档-[^\s")]+\.md')
    if ($m.Success) {
        return @{ Hit = $true; Verb = $verbHit; Target = $m.Value }
    }
    return @{ Hit = $false; Verb = $null; Target = $null }
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

    if ($toolName -notin @('Read', 'Grep', 'Bash')) {
        # matcher 已在 settings.json 层过滤，理论不会走到这里；防御性放行，
        # 不留痕（同 pretooluse-editlock-guard 既有惯例）。
        exit 0
    }

    $repoRoot = Get-SentinelRepoRoot
    $tiProps = Get-JsonPropertyNames $json.tool_input

    if ($toolName -eq 'Bash') {
        $command = ''
        if ($tiProps -contains 'command') { $command = [string]$json.tool_input.command }
        if (-not $command) {
            Add-HooksAuditLine -RepoRoot $repoRoot -Hook $HookName -Verdict 'undetermined' `
                -Tool $toolName -SessionId $sessionId -Detail 'Bash tool_input 无 command 字段'
            exit 0
        }
        if (Test-BashAllowlisted -Command $command) {
            Add-HooksAuditLine -RepoRoot $repoRoot -Hook $HookName -Verdict 'pass' `
                -Tool $toolName -SessionId $sessionId -Detail '命中机制工具白名单（编辑锁/队列查询/sweep/lint）'
            exit 0
        }
        $hit = Test-BashHitsProtectedTarget -Command $command
        if (-not $hit.Hit) {
            Add-HooksAuditLine -RepoRoot $repoRoot -Hook $HookName -Verdict 'pass' `
                -Tool $toolName -SessionId $sessionId -Detail '未同时命中读命令名与目标文件名'
            exit 0
        }
        $msg = "✗ 队列读侧禁通读：Bash 命令内出现「$($hit.Verb)」直击「$($hit.Target)」。$script:GuidanceMsg"
        Add-HooksAuditLine -RepoRoot $repoRoot -Hook $HookName -Verdict 'violation' `
            -Tool $toolName -SessionId $sessionId -Detail "$($hit.Verb) → $($hit.Target)"
        [Console]::Error.WriteLine($msg)
        exit 2
    }

    # Read／Grep：结构化目标字段——Read 用 file_path，Grep 用 path（可选，
    # 未传时视为"无目标字段可判"，见文件头 DESCRIPTION）。
    $targetPath = ''
    if ($toolName -eq 'Read' -and $tiProps -contains 'file_path') {
        $targetPath = [string]$json.tool_input.file_path
    } elseif ($toolName -eq 'Grep' -and $tiProps -contains 'path') {
        $targetPath = [string]$json.tool_input.path
    }

    if (-not $targetPath) {
        Add-HooksAuditLine -RepoRoot $repoRoot -Hook $HookName -Verdict 'undetermined' `
            -Tool $toolName -SessionId $sessionId -Detail '无结构化目标路径（Grep 未传 path 视为不适用）'
        exit 0
    }

    if (-not (Test-ProtectedQueueTarget -RepoRoot $repoRoot -TargetPath $targetPath)) {
        Add-HooksAuditLine -RepoRoot $repoRoot -Hook $HookName -Verdict 'pass' `
            -Tool $toolName -SessionId $sessionId -Detail "非受保护目标：$targetPath"
        exit 0
    }

    $msg = "✗ 队列读侧禁通读：$toolName 目标 ""$targetPath"" 命中队列真身/归档件。$script:GuidanceMsg"
    Add-HooksAuditLine -RepoRoot $repoRoot -Hook $HookName -Verdict 'violation' `
        -Tool $toolName -SessionId $sessionId -Detail $targetPath
    [Console]::Error.WriteLine($msg)
    exit 2
} catch {
    try {
        Add-HooksAuditLine -RepoRoot (Get-SentinelRepoRoot) -Hook $HookName -Verdict 'error' `
            -Detail $_.Exception.Message
    } catch { }
    exit 0
}
