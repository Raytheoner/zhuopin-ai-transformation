<#
.SYNOPSIS
  一次装完 2026-09-21 两个钩子（Stop 上下文读取面 ＋ PreToolUse 重复调用去重守）。

.DESCRIPTION
  `.claude/settings.json` 命中 `~/.claude/protected-paths.json` 的
  `*/.claude/settings.json`（`mode: block`），CC 工具层拒写，故这一步只能由
  Shao Peishen 本人执行——**本脚本由他跑，不是本方旁路绕过那道 block**。

  纪律：**纯文本插入，不做 JSON round-trip**——`ConvertFrom-Json | ConvertTo-Json`
  会把整份文件的键序重排，制造与内容无关的巨大 diff（2026-09-21 已被当作噪音丢弃过一次）。
  幂等：已装过即跳过；先备份、插完立刻解析校验，校验不过自动回滚。

.PARAMETER SettingsPath
  目标 settings.json；默认项目那份。改这个参数可先在副本上试跑。
.PARAMETER DryRun
  只打印将做什么，不写盘。
#>
param(
    [string]$SettingsPath = 'C:\Dev\zhuopin-ai\.claude\settings.json',
    [switch]$DryRun
)

$ErrorActionPreference = 'Stop'
try { [Console]::OutputEncoding = [Text.UTF8Encoding]::new($false) } catch {}

$HookDir  = 'C:\Dev\zhuopin-ai\0-学习与工具\hooks'
$StopHook = 'hooks-stop-context-meter.ps1'
$DedupHook = 'hooks-pretooluse-dedup-guard.ps1'

# 两个钩子各自独立判存在——`hooks-stop-context-meter.ps1` 目前只在未 ff 的
# 分支 `claude/op0921i-639-lane-readface` 上，主工作区可能没有；缺哪个就只装另一个，
# 并把缺的原因打出来，不因此整体失败（缺件不是本脚本能替他决定 ff 的事）。
$HaveStop  = Test-Path -LiteralPath (Join-Path $HookDir $StopHook)
$HaveDedup = Test-Path -LiteralPath (Join-Path $HookDir $DedupHook)
if (-not $HaveStop) {
    Write-Host "· 跳过 Stop 读取面：$StopHook 不在主工作区（它在未 ff 的分支 claude/op0921i-639-lane-readface 上，ff 属 🟡 档，等你一字母）" -ForegroundColor DarkYellow
}
if (-not $HaveDedup) {
    Write-Host "✗ $DedupHook 不在 $HookDir —— 去重守装不了，先确认该文件在位。" -ForegroundColor Red
}
if (-not $HaveStop -and -not $HaveDedup) { exit 1 }
if (-not (Test-Path -LiteralPath $SettingsPath)) { Write-Host "✗ 找不到 $SettingsPath" -ForegroundColor Red; exit 1 }

$raw = [System.IO.File]::ReadAllText($SettingsPath)
$orig = $raw
# 🔴 行尾归一：本脚本里的 here-string 是 LF，而 settings.json 在盘上是 CRLF，
# 直接 -like/-Replace 一定匹配不上（2026-09-21 实测撞过，同日 CRLF 已骗过三次：
# 根 CLAUDE.md 磁盘 12,146 vs blob 12,077、#629 续棒那 69 B、本处锚点）。
# 故所有锚点与插入串在比对前按目标文件的实际行尾重铺。
$NL = if ($raw.Contains("`r`n")) { "`r`n" } else { "`n" }
function Use-FileEol { param([string]$Text) return (($Text -split "`r?`n") -join $NL) }
$did = @()
$skip = @()

# ---------- ① PreToolUse 追加去重守（新增第三个 matcher） ----------
if (-not $HaveDedup) {
    $skip += 'PreToolUse 去重守（脚本缺件）'
} elseif ($raw -like "*$DedupHook*") {
    $skip += 'PreToolUse 去重守（已装）'
} else {
    $anchor = @'
            "command": "pwsh -NoProfile -File \"C:\\Dev\\zhuopin-ai\\0-学习与工具\\hooks\\hooks-pretooluse-queue-read-guard.ps1\"",
            "timeout": 10
          }
        ]
      }
    ],
'@
    $anchor = Use-FileEol $anchor
    if ($raw -notlike "*$anchor*") { Write-Host '✗ PreToolUse 锚点没匹配上（文件结构与预期不符），未改任何东西。' -ForegroundColor Red; exit 2 }
    $add = @'
            "command": "pwsh -NoProfile -File \"C:\\Dev\\zhuopin-ai\\0-学习与工具\\hooks\\hooks-pretooluse-queue-read-guard.ps1\"",
            "timeout": 10
          }
        ]
      },
      {
        "matcher": "Read|Grep|Edit|Bash",
        "hooks": [
          {
            "type": "command",
            "command": "pwsh -NoProfile -File \"C:\\Dev\\zhuopin-ai\\0-学习与工具\\hooks\\hooks-pretooluse-dedup-guard.ps1\"",
            "timeout": 10
          }
        ]
      }
    ],
'@
    $raw = $raw.Replace($anchor, (Use-FileEol $add))
    $did += 'PreToolUse 去重守'
}

# ---------- ② Stop 追加上下文读取面 ----------
if (-not $HaveStop) {
    $skip += 'Stop 读取面（脚本缺件，待 #639 分支 ff）'
} elseif ($raw -like "*$StopHook*") {
    $skip += 'Stop 读取面（已装）'
} else {
    $anchor2 = @'
            "command": "pwsh -NoProfile -File \"C:\\Dev\\zhuopin-ai\\0-学习与工具\\hooks\\hooks-stop-decision-check.ps1\"",
            "timeout": 10
          }
'@
    $anchor2 = Use-FileEol $anchor2
    if ($raw -notlike "*$anchor2*") { Write-Host '✗ Stop 锚点没匹配上，未改任何东西。' -ForegroundColor Red; exit 2 }
    $add2 = @'
            "command": "pwsh -NoProfile -File \"C:\\Dev\\zhuopin-ai\\0-学习与工具\\hooks\\hooks-stop-decision-check.ps1\"",
            "timeout": 10
          },
          {
            "type": "command",
            "command": "pwsh -NoProfile -File \"C:\\Dev\\zhuopin-ai\\0-学习与工具\\hooks\\hooks-stop-context-meter.ps1\"",
            "timeout": 10
          }
'@
    $raw = $raw.Replace($anchor2, (Use-FileEol $add2))
    $did += 'Stop 读取面'
}

if ($skip.Count) { $skip | ForEach-Object { Write-Host "· 跳过：$_" -ForegroundColor DarkGray } }
if (-not $did.Count) { Write-Host '✓ 两个钩子都已在位，无需改动。' -ForegroundColor Green; exit 0 }

if ($DryRun) {
    Write-Host ("[DryRun] 将追加：" + ($did -join '、') + "；字节 $($orig.Length) → $($raw.Length)。未写盘。") -ForegroundColor Yellow
    exit 0
}

$bak = "$SettingsPath.bak-" + (Get-Date -Format 'yyyyMMdd-HHmmss')
[System.IO.File]::WriteAllText($bak, $orig, (New-Object System.Text.UTF8Encoding $false))
[System.IO.File]::WriteAllText($SettingsPath, $raw, (New-Object System.Text.UTF8Encoding $false))

try {
    $j = Get-Content -LiteralPath $SettingsPath -Raw -Encoding UTF8 | ConvertFrom-Json
    $pre = @($j.hooks.PreToolUse).Count
    $stp = @($j.hooks.Stop[0].hooks).Count
    $needPre = if ($did -contains 'PreToolUse 去重守') { 3 } else { 2 }
    $needStp = if ($did -contains 'Stop 读取面') { 2 } else { 1 }
    if ($pre -lt $needPre -or $stp -lt $needStp) { throw "校验不过：PreToolUse=$pre（应 ≥$needPre）、Stop[0].hooks=$stp（应 ≥$needStp）" }
    Write-Host ("✓ 已装：" + ($did -join '、')) -ForegroundColor Green
    Write-Host "✓ 校验：PreToolUse matcher 数 = $pre ；Stop[0].hooks 数 = $stp" -ForegroundColor Green
    Write-Host "  备份：$bak"
    Write-Host "  下一步：跟 Cowork 说一句「钩子装好了」即可（这条没有机器触发器）。"
    exit 0
} catch {
    [System.IO.File]::WriteAllText($SettingsPath, $orig, (New-Object System.Text.UTF8Encoding $false))
    Write-Host "✗ $($_.Exception.Message) ⇒ 已自动回滚到原样（备份仍留在 $bak）。" -ForegroundColor Red
    exit 3
}
