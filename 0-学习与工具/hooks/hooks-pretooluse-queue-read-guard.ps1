<#
.SYNOPSIS
  PreToolUse 钩子（队列 §一 #381⑸ⓗ2，K3 口径；`followup-readme-phase2` D4
  扩展保护目标至跟进信 README）：`Read`/`Grep`/`Bash` 目标命中两份队列真身／
  队列归档件，或跟进信 README 主表／README 归档件时拒绝本次调用，提示改用
  对应查询工具。

.DESCRIPTION
  判据正本＝队列 §一 #381⑸ⓗ2 原文 ＋
  `1-转型规划/0-全景路线图/跨桌任务队列瘦身-方案-2026-09-04.md` §二 K3 ＋
  `.claude/rules/队列与落库.md`「读侧禁通读」；README 一侧正本＝
  `openspec/changes/followup-readme-phase2/specs/followup-readme-read-guard/spec.md`
  （D4，2026-09-06 由 `followup-readme-phase2` 扩展）。

  两份队列真身单行可达 78 KB、跟进信 README 主表曾达 178 KB——`Read` 全文
  或对其 `Grep` 一次命中就把整份/整行原文灌进上下文（队列侧实测 ≈3 万
  tokens／行）。本钩子只做"挡在门口"这一件事，队列合法读法（判行状态
  `--row`、扫池 `--digest`、核触碰区 `--digest --grep`）一律指向
  `工具-队列查询.py`；README 合法读法（登记 `append`/`set-status`、只读
  digest）一律指向 `工具-跟进信README登记.py`／`工具-跟进信README查询.py`。

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

#: 队列真身 ＋ 跟进信 README 主表（精确路径，非前缀/包含）。
$script:ProtectedExactRel = @(
    '1-转型规划/0-全景路线图/跨桌任务队列-机制环境.md'
    '1-转型规划/0-全景路线图/跨桌任务队列-业务场景.md'
    '6-人才与组织/部门AI专员跟进/README-跟进机制与命名约定.md'
)
#: 归档件——两组各自的"父目录 + 文件名正则"，不满足"精确路径"的前提，
#: 故与上面几份分开处理。README 归档件与主表同居一个目录，与队列归档件
#: 所在目录不同，因此按（目录, 正则）配对存放，不与队列那对共用同一个
#: 目录变量（`followup-readme-phase2` D4 续棒补充，2026-09-06）。
$script:ProtectedArchivePatterns = @(
    @{ Dir = '1-转型规划/0-全景路线图'; Regex = '^跨桌任务队列-归档-.+\.md$' }
    @{ Dir = '6-人才与组织/部门AI专员跟进'; Regex = '^README-归档-.+\.md$' }
)

#: 白名单机制工具——Bash 命令行含其一（作为被执行的脚本路径子串）即整条
#: 放行，见文件头 DESCRIPTION 撞车实例。跟进信 README 三个机制工具
#: （登记／归档／查询）随 D4 续棒补充加入——`工具-跟进信README查询.py`
#: 原已存在但从未入过白名单，否则它自己读 README 会被本钩子拦下。
$script:AllowlistedToolScripts = @(
    '工具-共享文档编辑锁\.py'
    '工具-队列查询\.py'
    '工具-落库sweep\.py'
    '工具-队列结构lint\.py'
    '工具-跟进信README登记\.py'
    '工具-跟进信README归档\.py'
    '工具-跟进信README查询\.py'
    '工具-跟进信README行长外置\.py'
)

#: Bash 读命令名——大小写不敏感匹配（`-imatch`）：PowerShell cmdlet 本就
#: 大小写不敏感，`cat`/`grep` 是常见 POSIX 别名/Git Bash 场景，来源不定。
$script:BashReadVerbs = @('Get-Content', 'cat', 'grep', 'Select-String')

$script:QueueGuidanceMsg = '改用 python 0-学习与工具/工具-队列查询.py --row N' +
    '（判行状态）／--digest（扫池）／--digest --grep <关键词>（核触碰区），' +
    '见 .claude/rules/队列与落库.md「读侧禁通读」（K3，队列 §一 #381⑸）。'
$script:ReadmeGuidanceMsg = '改用 python 0-学习与工具/工具-跟进信README登记.py' +
    '（append／set-status，登记与改状态）／工具-跟进信README查询.py --digest' +
    '（只读扫描，`--file` 可指向归档件），见 openspec 变更包 ' +
    'followup-readme-phase2（D4，跟进信 README 读侧禁通读）。'

function Get-GuidanceForTarget([string]$Target) {
    <# README 主表/归档件与队列真身/归档件命中同一个钩子逻辑，但正确的
       "改用什么工具"提示并不相同——按目标文件名字面含"README"分流。 #>
    if ($Target -match 'README') { return $script:ReadmeGuidanceMsg }
    return $script:QueueGuidanceMsg
}

function Resolve-RepoRelative([string]$RepoRoot, [string]$Candidate) {
    try {
        if ([System.IO.Path]::IsPathRooted($Candidate)) {
            return [System.IO.Path]::GetFullPath($Candidate)
        }
        return [System.IO.Path]::GetFullPath((Join-Path $RepoRoot $Candidate))
    } catch { return $null }
}

function Test-ProtectedQueueTarget([string]$RepoRoot, [string]$TargetPath) {
    <# 目标（`file_path`／`path`）是否精确命中队列真身／README 主表，
       或队列归档件／README 归档件之一。 #>
    $full = Resolve-RepoRelative $RepoRoot $TargetPath
    if (-not $full) { return $false }

    foreach ($rel in $script:ProtectedExactRel) {
        $candidateFull = Resolve-RepoRelative $RepoRoot $rel
        if ($candidateFull -and $full -eq $candidateFull) { return $true }
    }

    $parent = Split-Path -Parent $full
    $leaf = Split-Path -Leaf $full
    foreach ($pattern in $script:ProtectedArchivePatterns) {
        $archiveDirFull = Resolve-RepoRelative $RepoRoot $pattern.Dir
        if ($archiveDirFull -and $parent -eq $archiveDirFull -and $leaf -match $pattern.Regex) {
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

function Get-GitToplevel([string]$Dir) {
    <# 队列 #600 ⑶：解析 `$Dir` 所在 git 仓库的 toplevel；判不了返回 `$null`
       （不是 fail-loud——调用方须把「判不了」与「判定为主仓」区分开，保守放行）。#>
    if (-not $Dir -or -not (Test-Path -LiteralPath $Dir)) { return $null }
    try {
        $out = & git -C $Dir rev-parse --show-toplevel 2>$null
        if ($LASTEXITCODE -eq 0 -and $out) {
            return (Resolve-Path -LiteralPath $out.Trim()).Path.TrimEnd('\', '/')
        }
    } catch { }
    return $null
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
    foreach ($archiveNamePattern in @('跨桌任务队列-归档-[^\s")]+\.md', 'README-归档-[^\s")]+\.md')) {
        $m = [regex]::Match($Command, $archiveNamePattern)
        if ($m.Success) {
            return @{ Hit = $true; Verb = $verbHit; Target = $m.Value }
        }
    }
    return @{ Hit = $false; Verb = $null; Target = $null }
}

function Get-NativeLiteral($Node) {
    if ($Node -is [System.Management.Automation.Language.StringConstantExpressionAst]) {
        return [string]$Node.Value
    }
    if ($Node -is [System.Management.Automation.Language.ExpandableStringExpressionAst] -and
        $Node.NestedExpressions.Count -eq 0) { return [string]$Node.Value }
    if ($Node -is [System.Management.Automation.Language.CommandParameterAst]) {
        return [string]$Node.Extent.Text
    }
    if ($Node -is [System.Management.Automation.Language.ConstantExpressionAst]) {
        return [string]$Node.Value
    }
    return $null
}

function Test-NativePathTraversesReparsePoint([string]$Candidate) {
    # Inspect each lexical component before GetFullPath can collapse a link/.. pair.
    try {
        $root = [IO.Path]::GetPathRoot($Candidate)
        if (-not $root) { return $true }
        $part = $root
        foreach ($segment in $Candidate.Substring($root.Length).Split([char[]]@('\', '/'),
                [StringSplitOptions]::RemoveEmptyEntries)) {
            if ($segment -eq '.') { continue }
            if ($segment -eq '..') {
                $parent = Split-Path -Parent $part
                if (-not $parent) { return $true }
                $part = $parent
                continue
            }
            $part = Join-Path $part $segment
            if (Test-Path -LiteralPath $part) {
                $attributes = (Get-Item -LiteralPath $part -Force).Attributes
                if ($attributes -band [IO.FileAttributes]::ReparsePoint) { return $true }
            }
        }
        return $false
    } catch { return $true }
}
function Test-NativeProtectedScope([string]$RepoRoot, [string]$Cwd, [string]$Target) {
    # Scope is resolved from actual exec cwd; globs/links are never a safety waiver.
    $rawPath = if ([IO.Path]::IsPathRooted($Target)) { $Target } else { Join-Path $Cwd $Target }
    if (Test-NativePathTraversesReparsePoint $rawPath) { return $true }
    $full = Resolve-RepoRelative $Cwd $Target
    if (-not $full -or $Target -match '[*?\[\]]') { return $true }
    try {
        $part = [IO.Path]::GetPathRoot($full)
        foreach ($segment in $full.Substring($part.Length).Split([char[]]@('\', '/'),
                [StringSplitOptions]::RemoveEmptyEntries)) {
            $part = Join-Path $part $segment
            if (Test-Path -LiteralPath $part) {
                if ((Get-Item -LiteralPath $part -Force).Attributes -band
                    [IO.FileAttributes]::ReparsePoint) { return $true }
            }
        }
        if (Test-ProtectedQueueTarget $RepoRoot $full) { return $true }
        if (-not (Test-Path -LiteralPath $full)) { return $true }
        if (-not (Test-Path -LiteralPath $full -PathType Container)) { return $false }
        $prefix = $full.TrimEnd('\', '/') + [IO.Path]::DirectorySeparatorChar
        foreach ($rel in $script:ProtectedExactRel) {
            $protected = Resolve-RepoRelative $RepoRoot $rel
            if ($protected.Equals($full, [StringComparison]::OrdinalIgnoreCase) -or
                $protected.StartsWith($prefix, [StringComparison]::OrdinalIgnoreCase)) {
                return $true
            }
        }
        foreach ($pattern in $script:ProtectedArchivePatterns) {
            $directory = Resolve-RepoRelative $RepoRoot $pattern.Dir
            if ($directory.Equals($full, [StringComparison]::OrdinalIgnoreCase) -or
                $directory.StartsWith($prefix, [StringComparison]::OrdinalIgnoreCase)) {
                return $true
            }
        }
        return $false
    } catch { return $true }
}

function Test-NativeQueryCommand([string[]]$Argv, [string]$Root, [string]$Cwd) {
    $name = [IO.Path]::GetFileName($Argv[0])
    if ($name -notmatch '^(python(\d+(\.\d+)?)?|py)(\.exe)?$') { return $false }
    $i = 1
    while ($i -lt $Argv.Count -and $Argv[$i] -in @('-B', '-u', '-I', '-E', '-s')) { $i++ }
    if ($i -ge $Argv.Count -or $Argv[$i].StartsWith('-')) { return $false }
    $actual = Resolve-RepoRelative $Cwd $Argv[$i]
    foreach ($scriptPattern in $script:AllowlistedToolScripts) {
        $name = $scriptPattern.Replace('\.py', '.py')
        $expected = Resolve-RepoRelative $Root ('0-学习与工具/' + $name)
        if ($actual -and $actual -eq $expected) { return $true }
    }
    return $false
}

function Get-NativeRgTargets([string[]]$Argv) {
    $paths = [Collections.Generic.List[string]]::new()
    $pattern = $false
    $explicitPattern = $false
    $files = $false
    $content = $false
    $literal = $false
    $flags = @('-n', '--line-number', '-i', '--ignore-case', '-s', '--case-sensitive',
        '-S', '--smart-case', '-F', '--fixed-strings', '-w', '--word-regexp',
        '-x', '--line-regexp', '-a', '--text', '-U', '--multiline',
        '--multiline-dotall', '--hidden', '--no-ignore', '--no-ignore-vcs',
        '--no-ignore-parent', '--no-ignore-global', '--no-messages', '--no-heading',
        '--heading', '--with-filename', '--no-filename', '--sort-files', '--stats',
        '--json', '--pcre2', '-P', '--crlf', '--passthru', '--null', '-0',
        '--no-config', '--no-unicode', '--unicode')
    $contentFlags = @('-l', '--files-with-matches', '--files-without-match',
        '-c', '--count', '--count-matches', '-q', '--quiet', '-v', '--invert-match',
        '-o', '--only-matching', '--replace')
    $values = @('-g', '--glob', '--iglob', '-t', '--type', '-T', '--type-not',
        '--type-add', '--type-clear', '-e', '--regexp', '-f', '--file',
        '-A', '--after-context', '-B', '--before-context', '-C', '--context',
        '-m', '--max-count', '--max-depth', '--max-filesize', '--encoding',
        '--color', '--colors', '--sort', '--sortr', '--threads', '-j',
        '--path-separator', '--engine', '--replace')
    for ($i = 1; $i -lt $Argv.Count; $i++) {
        $arg = $Argv[$i]
        if (-not $literal -and $arg -eq '--') { $literal = $true; continue }
        if (-not $literal -and $arg.StartsWith('-')) {
            $option = $arg.Split('=', 2)[0]
            if ($option -eq '--files') { $files = $true; continue }
            if ($option -in $values) {
                if (-not $arg.Contains('=')) {
                    $i++
                    if ($i -ge $Argv.Count -or $Argv[$i].StartsWith('-')) {
                        return @{ Invalid = $true; FilesOnly = $false; Paths = @() }
                    }
                }
                if ($option -in @('-e', '--regexp', '-f', '--file')) {
                    $explicitPattern = $true; $content = $true
                }
                if ($option -eq '--replace') { $content = $true }
                # A pattern file is itself a read target.
                if ($option -in @('-f', '--file')) {
                    $paths.Add($(if ($arg.Contains('=')) { $arg.Split('=', 2)[1] } else { $Argv[$i] }))
                }
                continue
            }
            if ($option -in $contentFlags) { $content = $true; continue }
            if ($option -in $flags) { continue }
            return @{ Invalid = $true; FilesOnly = $false; Paths = @() }
        }
        if (-not $files -and -not $explicitPattern -and -not $pattern) {
            $pattern = $true
        } else { $paths.Add($arg) }
    }
    $filesOnly = $files -and -not $content
    if (-not $filesOnly -and $paths.Count -eq 0) { $paths.Add('.') }
    return @{ Invalid = $false; FilesOnly = $filesOnly; Paths = @($paths.ToArray()) }
}

function Get-NativeReadHit([string]$Command, [string]$Root, [string]$Cwd) {
    $deny = @{ Hit = $true; Verb = 'native-read'; Target = '保护范围或无法解析的读取' }
    if (-not $Cwd -or -not [IO.Path]::IsPathRooted($Cwd) -or
        -not (Test-Path -LiteralPath $Cwd -PathType Container)) { return $deny }
    $tokens = $null; $parseErrors = $null
    $ast = [Management.Automation.Language.Parser]::ParseInput($Command,
        [ref]$tokens, [ref]$parseErrors)
    if ($parseErrors.Count) { return $deny }
    $commands = $ast.FindAll({
        param($node) $node -is [Management.Automation.Language.CommandAst]
    }, $true)
    foreach ($node in $commands) {
        # Write-Output only formats output. FindAll still visits every nested
        # command, so $(rg ...) and dynamic reader calls remain checked below.
        $commandLiteral = Get-NativeLiteral $node.CommandElements[0]
        if ($null -ne $commandLiteral -and $commandLiteral -ieq 'Write-Output') { continue }
        if ($null -ne $commandLiteral -and $commandLiteral -ieq 'Select-Object') {
            # Only literal formatting properties are accepted; calculated or
            # dynamic properties remain denied. FindAll still checks readers.
            for ($index = 1; $index -lt $node.CommandElements.Count; $index++) {
                $element = $node.CommandElements[$index]
                # An inline parameter owns its value AST. Inspect that value,
                # never treat the complete parameter extent as a literal.
                if ($element -is [Management.Automation.Language.CommandParameterAst]) {
                    if ($null -eq $element.Argument) { continue }
                    $element = $element.Argument
                }
                $parts = if ($element -is [Management.Automation.Language.ArrayLiteralAst]) {
                    @($element.Elements)
                } else { @($element) }
                foreach ($part in $parts) {
                    if ($null -eq (Get-NativeLiteral $part)) { return $deny }
                }
            }
            continue
        }
        $argv = [Collections.Generic.List[string]]::new()
        foreach ($element in $node.CommandElements) {
            $value = Get-NativeLiteral $element
            if ($null -eq $value) { return $deny }
            $argv.Add($value)
        }
        if ($argv.Count -eq 0) { return $deny }
        if (Test-NativeQueryCommand $argv.ToArray() $Root $Cwd) { continue }
        $name = [IO.Path]::GetFileName($argv[0])
        if ($name -in @('rg', 'rg.exe')) {
            $scope = Get-NativeRgTargets $argv.ToArray()
            if ($scope.Invalid) { return $deny }
            if ($scope.FilesOnly) { continue }
            foreach ($path in $scope.Paths) {
                if (Test-NativeProtectedScope $Root $Cwd $path) {
                    return @{ Hit = $true; Verb = $name; Target = $path }
                }
            }
        } elseif ($name -ieq 'Get-Content') {
            # Parse Get-Content's value-taking parameters so values such as -Tail 80
            # are not mistaken for file paths. Unknown options fail closed.
            $pathArgs = [Collections.Generic.List[string]]::new()
            $valueOptions = @('-Tail', '-TotalCount', '-Head', '-ReadCount',
                '-Encoding', '-Delimiter', '-Stream')
            $switchOptions = @('-Raw', '-Wait', '-Force', '-AsByteStream',
                '-NoNewline', '-UseTransaction')
            for ($i = 1; $i -lt $argv.Count; $i++) {
                $arg = $argv[$i]
                if (-not $arg.StartsWith('-')) { $pathArgs.Add($arg); continue }
                $parts = $arg.Split(':', 2)
                $option = $parts[0]
                $hasInlineValue = $parts.Count -gt 1
                if ($option -in @('-Path', '-LiteralPath', '-PSPath')) {
                    if ($hasInlineValue) {
                        if (-not $parts[1]) { return $deny }
                        $pathArgs.Add($parts[1])
                    } else {
                        $i++
                        if ($i -ge $argv.Count -or $argv[$i].StartsWith('-')) { return $deny }
                        $pathArgs.Add($argv[$i])
                    }
                } elseif ($option -in $valueOptions) {
                    if (-not $hasInlineValue) {
                        $i++
                        if ($i -ge $argv.Count -or $argv[$i].StartsWith('-')) { return $deny }
                    }
                } elseif ($option -in $switchOptions -and -not $hasInlineValue) {
                    continue
                } else { return $deny }
            }
            foreach ($path in $pathArgs) {
                if (Test-NativeProtectedScope $Root $Cwd $path) {
                    return @{ Hit = $true; Verb = $name; Target = $path }
                }
            }
        } elseif ($name -in $script:BashReadVerbs) {
            foreach ($path in @($argv.ToArray() | Select-Object -Skip 1)) {
                if ($path.StartsWith('-')) { continue }
                if (Test-NativeProtectedScope $Root $Cwd $path) {
                    return @{ Hit = $true; Verb = $name; Target = $path }
                }
            }
        } elseif ($name -in @('pwsh', 'pwsh.exe', 'powershell', 'powershell.exe',
                'cmd', 'cmd.exe', 'bash', 'bash.exe', 'sh', 'sh.exe')) {
            # Wrapper programs hide command nodes: do not infer a safe inner read.
            if (($argv -join ' ') -match '(?i)\brg(\.exe)?\b|跨桌任务队列|README-归档|README-跟进') {
                return $deny
            }
        }
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
        $native = ($jsonProps -contains '_zhuopin_codex_adapter') -and
            ($json._zhuopin_codex_adapter -eq 'native-v1')
        if ($native) {
            $nativeCwd = if ($tiProps -contains 'cwd') { [string]$json.tool_input.cwd } else { [string]$json.cwd }
            $nativeHit = Get-NativeReadHit $command $repoRoot $nativeCwd
            if ($nativeHit.Hit) {
                Add-HooksAuditLine -RepoRoot $repoRoot -Hook $HookName -Verdict 'violation' -Tool $toolName -SessionId $sessionId -Detail "native-read: $($nativeHit.Verb)"
                [Console]::Error.WriteLine("✗ Codex 读侧禁通读：$($nativeHit.Target)。$(Get-GuidanceForTarget $nativeHit.Target)")
                exit 2
            }
        }
        if (-not $native -and (Test-BashAllowlisted -Command $command)) {
            Add-HooksAuditLine -RepoRoot $repoRoot -Hook $HookName -Verdict 'pass' `
                -Tool $toolName -SessionId $sessionId -Detail '命中机制工具白名单（编辑锁/队列查询/sweep/lint/README登记/README归档/README查询/README行长外置）'
            exit 0
        }

        # 队列 #600 ⑶：`ZHUOPIN_LANE_WORKTREE` 存在时（本泳道已由 v2.ps1 建好隔离
        # worktree），命令内含 git 写操作子命令、且 harness 上报的当前 cwd 之 toplevel
        # 正是主工作区 ⇒ 拒绝——防泳道漏切目录时把 commit/push/merge/reset 等误落主仓
        # （worktree 内同类命令 toplevel≠主仓，不受影响；只看列出的写子命令，不管
        # log/status/diff/show/fsck/rev-parse/worktree 这类只读或本就无害的子命令）。
        $laneWorktree = $env:ZHUOPIN_LANE_WORKTREE
        if ($laneWorktree) {
            $gitWriteRe = '\bgit\b[^&|;`r`n]*\b(commit|push|merge|rebase|reset|checkout|switch|stash|apply|cherry-pick|restore|clean)\b'
            if ($command -match $gitWriteRe) {
                $bashCwd = ''
                if ($tiProps -contains 'cwd') { $bashCwd = [string]$json.tool_input.cwd }
                if (-not $bashCwd -and $jsonProps -contains 'cwd') { $bashCwd = [string]$json.cwd }
                if (-not $bashCwd) { $bashCwd = $repoRoot }
                $toplevel = Get-GitToplevel -Dir $bashCwd
                $repoRootFull = $null
                try { $repoRootFull = (Resolve-Path -LiteralPath $repoRoot).Path.TrimEnd('\', '/') } catch { }
                if ($toplevel -and $repoRootFull -and $toplevel.Equals($repoRootFull, [System.StringComparison]::OrdinalIgnoreCase)) {
                    $laneMsg = "✗ 泳道隔离门禁：ZHUOPIN_LANE_WORKTREE=$laneWorktree 已设置，命令内出现 git 写操作" +
                        "（commit/push/merge/rebase/reset/checkout/switch/stash/apply/cherry-pick/restore/clean 之一），" +
                        "但当前目录 toplevel 是主工作区（$repoRootFull），不是该 worktree —— 拒绝执行。请在 worktree 内操作。"
                    Add-HooksAuditLine -RepoRoot $repoRoot -Hook $HookName -Verdict 'violation' `
                        -Tool $toolName -SessionId $sessionId -Detail "lane-isolation-git-write：$command"
                    [Console]::Error.WriteLine($laneMsg)
                    exit 2
                }
            }
        }

        $hit = if ($native) { @{ Hit = $false; Verb = $null; Target = $null } } else { Test-BashHitsProtectedTarget -Command $command }
        # 🔴 大文件整读守卫·Bash 侧（09-16 根治口径，与 Read 侧同阈值）：`cat／type／Get-Content／gc <文件>`
        # 且整条命令未出现截断手段（head／tail／sed -n／Select-Object -First|-Last／-TotalCount／-Tail／wc）
        # 且目标为 >阈值 的文本类文件 ⇒ 拒绝。路径解析失败一律放行（fail-open）。
        if (-not $hit.Hit) {
            $lbLimit = 24000
            if ($env:ZHUOPIN_LARGE_READ_BYTES -match '^\d+$') { $lbLimit = [int]$env:ZHUOPIN_LARGE_READ_BYTES }
            $lbMatch = [regex]::Match($command, '(?:^|[;&|]\s*)(?:cat|type|Get-Content|gc)\s+(?:-\S+\s+)*(?:"([^"]+)"|''([^'']+)''|(\S+))')
            $lbTruncated = $command -match '\|\s*(head|tail|sed\s+-n|Select-Object|select|wc)\b|-TotalCount|\s-Tail\s|\s-First\s'
            if ($lbMatch.Success -and -not $lbTruncated) {
                $lbPath = @($lbMatch.Groups[1].Value, $lbMatch.Groups[2].Value, $lbMatch.Groups[3].Value) | Where-Object { $_ } | Select-Object -First 1
                try {
                    if ($lbPath -and (Test-Path -LiteralPath $lbPath -PathType Leaf)) {
                        $lbExt = [IO.Path]::GetExtension($lbPath).ToLowerInvariant()
                        $lbTextExt = @('.md', '.ps1', '.psm1', '.py', '.json', '.jsonl', '.txt', '.log', '.yaml', '.yml', '.csv', '.ts', '.js', '.html', '.toml', '.ini', '.cfg', '.sql')
                        $lbSize = (Get-Item -LiteralPath $lbPath).Length
                        if (($lbTextExt -contains $lbExt) -and $lbSize -gt $lbLimit) {
                            $msg = "✗ 大文件禁整读：Bash 整份输出 `"$lbPath`" 约 $([math]::Round($lbSize/1024))KB。请先 grep -n 定位，再用 sed -n '起,止p' 或 Read 的 offset＋limit 分段读（单段建议 ≤200 行）。"
                            Add-HooksAuditLine -RepoRoot $repoRoot -Hook $HookName -Verdict 'violation' `
                                -Tool $toolName -SessionId $sessionId -Detail "large-read-bash ${lbSize}B：$lbPath"
                            [Console]::Error.WriteLine($msg)
                            exit 2
                        }
                    }
                } catch { }
            }
        }
        if (-not $hit.Hit) {
            Add-HooksAuditLine -RepoRoot $repoRoot -Hook $HookName -Verdict 'pass' `
                -Tool $toolName -SessionId $sessionId -Detail '未同时命中读命令名与目标文件名'
            exit 0
        }
        $msg = "✗ 读侧禁通读：Bash 命令内出现「$($hit.Verb)」直击「$($hit.Target)」。$(Get-GuidanceForTarget $hit.Target)"
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
        # 🔴 大文件整读守卫（2026-09-16 Shao Peishen「这个问题需要根治」，Token 优化 OP-0916-T）：
        # 实测 09-16 两条无头泳道开工 3／7 分钟即触 150k，主因是整份 Read 30KB 级文件
        # （opener骨架.md 34KB、工具-opener批处理执行v2.ps1 26KB、其测试 29KB）且同文件重复整读。
        # 判据：Read 未带 offset 且未带 limit、目标是文本类文件、体积 > 阈值 ⇒ 拒绝并指路分段读。
        # 带 offset／limit 任一即放行；阈值可用环境变量 ZHUOPIN_LARGE_READ_BYTES 覆盖；任何异常 fail-open。
        if ($toolName -eq 'Read') {
            $hasRange = ($tiProps -contains 'offset') -or ($tiProps -contains 'limit')
            $limitBytes = 24000
            if ($env:ZHUOPIN_LARGE_READ_BYTES -match '^\d+$') { $limitBytes = [int]$env:ZHUOPIN_LARGE_READ_BYTES }
            $ext = [IO.Path]::GetExtension($targetPath).ToLowerInvariant()
            $textExt = @('.md', '.ps1', '.psm1', '.py', '.json', '.jsonl', '.txt', '.log', '.yaml', '.yml', '.csv', '.ts', '.js', '.html', '.toml', '.ini', '.cfg', '.sql')
            if (-not $hasRange -and ($textExt -contains $ext) -and (Test-Path -LiteralPath $targetPath -PathType Leaf)) {
                $size = (Get-Item -LiteralPath $targetPath).Length
                if ($size -gt $limitBytes) {
                    $kb = [math]::Round($size / 1024)
                    $msg = "✗ 大文件禁整读：`"$targetPath`" 约 ${kb}KB（阈值 $([math]::Round($limitBytes/1024))KB），整份读入会把上下文一次抬高数千至上万 token。" +
                           "请先用 Grep（带 -n）定位要看的行号，再用 Read 的 offset＋limit 分段读（单段建议 ≤200 行）；同一会话已读过的段不要重读。"
                    Add-HooksAuditLine -RepoRoot $repoRoot -Hook $HookName -Verdict 'violation' `
                        -Tool $toolName -SessionId $sessionId -Detail "large-read ${size}B：$targetPath"
                    [Console]::Error.WriteLine($msg)
                    exit 2
                }
            }
        }
        Add-HooksAuditLine -RepoRoot $repoRoot -Hook $HookName -Verdict 'pass' `
            -Tool $toolName -SessionId $sessionId -Detail "非受保护目标：$targetPath"
        exit 0
    }

    $msg = "✗ 读侧禁通读：$toolName 目标 ""$targetPath"" 命中受保护目标。$(Get-GuidanceForTarget $targetPath)"
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
