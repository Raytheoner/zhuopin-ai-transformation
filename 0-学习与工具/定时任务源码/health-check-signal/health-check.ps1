# ===== Claude Code Environment Monthly Health Check =====
#
# 队列 #398 ⑴（2026-08-25，CC）修复要点 —— 本脚本此前**能跑、但没人知道它没跑**：
#   · 根因不在脚本，在计划任务设置：`DisallowStartIfOnBatteries=true`
#     （笔记本常态就是电池供电）⇒ 触发后进 Queued 一直等交流电，
#     最终以 0x800710E0（4320 操作员/管理员拒绝了请求）收场；
#     `StartWhenAvailable` 未开 ⇒ 错过的月度触发永不补跑。
#     2026-08-25 实测复现：电池状态下 Start-ScheduledTask 即刻卡在 Queued，
#     事件日志 325「已排队」，日志文件不被写；同一时刻直接跑本脚本 ⇒ 秒过。
#   · 失败不产生任何信号：日志只在**脚本真的跑起来**时才写，没跑＝没输出，
#     没输出与"跑了、没问题"在外部观察上完全一样（同 §一 #82 教训）。
#
# 因此本脚本除了做检查，还必须**留下可被别人读到的心跳**：
#   ⑴ 每次运行结束（含异常）写 `health-check-status.json`——机器可读，
#      带时间戳、发现数、是否成功；
#   ⑵ 由 `hooks/health-check-staleness.ps1` 在**每次 Claude Code 会话启动**
#      时读它，过期或有未处理发现就横幅告警。
#      —— signal 挂在"人每天都会看到的界面"上，不新造后台守卫；
#         新造一个后台守卫，等于用同一种失效方式去守它自己。
#   ⑶ 检查项 [4] 反过来核这条信号链自身是否还在（钩子是否注册、
#      计划任务电池闸/补跑是否被改回去）——守卫与信号互查，缺一即告警。

$base = "C:\Users\Paul Shao"; $claude = "$base\.claude"

# $projectRoots = 「项目根的父目录」清单（它的每个子目录才是一个项目）。
# 2026-08-28（OP-0828-F）由单值 $projects 改为多值：
#   本仓库 zhuopin-ai 于 2026-08-26 由 $base\OneDrive\Projects\企业AI转型 迁至 C:\Dev\zhuopin-ai，
#   而 OneDrive\Projects 下仍住着 claude-howto／supplychain／行业研报／SalesMarketing 等其余项目。
#   ⇒ **不能简单把旧值换成 C:\Dev**——那会把本项目找回来、却把其余全部丢掉，
#     且丢掉不产生任何信号（只是少列几行，然后照常写 Done）。这正是 08-26 迁移
#     后本脚本已经踩上的坑：目标搬走了，而判据不知道目标搬走了。
# 🔴 新增项目根父目录时，往这个数组里加一行即可；路径含空格，一律带引号。
$projectRoots = @("$base\OneDrive\Projects", "C:\Dev")
$statusPath = "$claude\health-check-status.json"
$startedAt = Get-Date
$findings = @()      # 需要人处理的发现（[!] 级）
$notes = @()         # 仅供参考（[i] 级）
$fatal = $null

try { Start-Transcript -Path "$claude\health-check.log" -Append | Out-Null } catch {}
$W="Yellow"; $OKC="Green"; $H="Cyan"

try {
  Write-Host "`n===== Health Check $(Get-Date -Format 'yyyy-MM-dd HH:mm') =====`n" -ForegroundColor $H

  # [0] Scan-root sanity（OP-0828-F 新增）——本脚本此前的失效形态是「扫描根搬走了、
  #     它照常写 Done」。故先核每个根是否还在、其下是否真的数得到项目；
  #     根不存在或根下零项目 ⇒ 记为 finding，而不是静默少列几行。
  Write-Host "[0] Scan roots" -ForegroundColor $H
  foreach ($pr in $projectRoots) {
    if (-not (Test-Path -LiteralPath $pr)) {
      Write-Host "  [!] scan root MISSING: $pr" -ForegroundColor $W
      $findings += "[0] 扫描根不存在：$pr（是不是又搬家了？搬了就改 projectRoots）"
      continue
    }
    $sub = @(Get-ChildItem -LiteralPath $pr -Directory -EA SilentlyContinue)
    if ($sub.Count -eq 0) {
      Write-Host "  [!] scan root EMPTY (0 project dirs): $pr" -ForegroundColor $W
      $findings += "[0] 扫描根下零个项目目录：$pr"
    } else {
      Write-Host ("  [OK] {0}  ({1} project dirs)" -f $pr, $sub.Count) -ForegroundColor $OKC
    }
  }

  # [1] Duplicate skill names (user + project, excl cache/node_modules)
  Write-Host "`n[1] Duplicate skills" -ForegroundColor $H
  $roots = @("$claude\skills") + ($projectRoots | Where-Object { Test-Path -LiteralPath $_ } |
      ForEach-Object { Get-ChildItem -LiteralPath $_ -Directory -EA SilentlyContinue } |
      ForEach-Object { "$($_.FullName)\.claude\skills" })
  $skills = foreach ($r in $roots) { if (Test-Path $r) {
      Get-ChildItem $r -Recurse -Filter SKILL.md -EA SilentlyContinue |
        Where-Object { $_.FullName -notmatch 'node_modules' } |
        ForEach-Object { [PSCustomObject]@{ Name=$_.Directory.Name; Path=$_.FullName } } } }
  $dups = $skills | Group-Object Name | Where-Object Count -gt 1
  if ($dups) { foreach ($g in $dups) {
      Write-Host "  [!] '$($g.Name)' x$($g.Count)" -ForegroundColor $W
      $findings += "[1] 技能重名 '$($g.Name)' x$($g.Count)"
      $g.Group.Path | ForEach-Object { Write-Host "      $_" } }
  } else { Write-Host "  [OK] none" -ForegroundColor $OKC }

  # [2] Non-active plugin cache versions (INFO ONLY - do not delete manually)
  Write-Host "`n[2] Plugin cache (non-active versions)" -ForegroundColor $H
  $instFile = "$claude\plugins\installed_plugins.json"
  $orphans = @()
  if (Test-Path $instFile) {
    $inst = Get-Content $instFile -Raw | ConvertFrom-Json
    $active = @{}
    $inst.PSObject.Properties | ForEach-Object {
      $_.Value.PSObject.Properties | ForEach-Object {
        $p = $_.Value.installPath
        if ($p) { $active[$p.TrimEnd('\').ToLower()] = $true } } }
    $seen = @{}
    foreach ($ap in $active.Keys) {
      $parent = Split-Path $ap -Parent
      if ($seen[$parent]) { continue }
      $seen[$parent] = $true
      Get-ChildItem $parent -Directory -EA SilentlyContinue | ForEach-Object {
        if (-not $active[$_.FullName.TrimEnd('\').ToLower()]) { $orphans += $_.FullName } } }
  } else {
    Write-Host "  [?] installed_plugins.json not found" -ForegroundColor $W
    $findings += "[2] installed_plugins.json 不存在，插件缓存这一项未核"
  }
  if ($orphans.Count) {
    $orphans | Sort-Object | ForEach-Object { Write-Host ("  [i] non-active: " + $_.Replace($claude,'~')) -ForegroundColor $H }
    $notes += "[2] $($orphans.Count) 个非激活插件缓存版本（仅提示，勿手删）"
    Write-Host "      NOTE: do NOT delete these manually (breaks CC cache pointer)." -ForegroundColor DarkGray
    Write-Host "      To reclaim space, manage plugins via /plugins inside Claude Code." -ForegroundColor DarkGray
  } elseif (Test-Path $instFile) { Write-Host "  [OK] none" -ForegroundColor $OKC }

  # [3] Project CLAUDE.md stacking depth + overlap with global
  Write-Host "`n[3] CLAUDE.md stacking / overlap" -ForegroundColor $H
  $global = Get-Content "$claude\CLAUDE.md" -EA SilentlyContinue
  # 排除 `.claude\worktrees\` —— 那是同一批受版本控制的 CLAUDE.md 的临时副本，
  # 每多一个在办 worktree，同一处发现就被重复报一遍（2026-08-25 实测：2 个真实
  # 发现被 13 个 worktree 放大成 28 条）。重复告警等于没有告警，会把心跳横幅
  # 淹掉，属"信号被噪音吃掉"这一类失效，与本次要修的问题同族。
  $cmds = $projectRoots | Where-Object { Test-Path -LiteralPath $_ } |
    ForEach-Object { Get-ChildItem -LiteralPath $_ -Recurse -Filter CLAUDE.md -EA SilentlyContinue } |
    Where-Object { $_.FullName -notmatch 'node_modules' -and $_.FullName -notmatch '\\\.claude\\worktrees\\' }
  foreach ($f in $cmds) {
    $proj = Get-Content $f.FullName
    $shared = if ($global) { (Compare-Object $global $proj -IncludeEqual -ExcludeDifferent).Count } else { 0 }
    $ratio = if ($proj.Count) { [math]::Round($shared/$proj.Count*100) } else { 0 }
    $depth = ($cmds | Where-Object { $f.FullName -eq $_.FullName -or $f.FullName.StartsWith($_.Directory.FullName + '\') }).Count + 1
    $bad = ($ratio -ge 40 -or ($depth -ge 3 -and $ratio -ge 30))
    $mark = if ($bad) { "[!]" } else { "   " }
    $rel = $f.FullName
    foreach ($pr in $projectRoots) {
      if ($rel.StartsWith($pr, [StringComparison]::OrdinalIgnoreCase)) { $rel = $rel.Substring($pr.Length); break } }
    if ($bad) { $findings += "[3] CLAUDE.md 叠加超阈 depth=$depth overlap=$ratio% $rel" }
    Write-Host ("  {0} depth={1} overlap={2,3}%  {3}" -f $mark, $depth, $ratio, $rel) -ForegroundColor $(if($bad){$W}else{$OKC})
  }
  Write-Host ("`n  Scanned {0} CLAUDE.md across {1} root(s)." -f @($cmds).Count, $projectRoots.Count) -ForegroundColor DarkGray
  Write-Host "  Threshold: overlap>=40%, or depth>=3 AND overlap>=30% -> trim" -ForegroundColor DarkGray

  # [4] Self-signal integrity (队列 #398 ⑴) —— 守卫反过来核自己的信号链。
  #     没有这一项，本脚本修好之后仍然可能被"钩子被删/电池闸被改回去"
  #     悄悄退回原状，而那同样不产生任何信号。
  Write-Host "`n[4] Self-signal integrity" -ForegroundColor $H
  $hookPath = "$claude\hooks\health-check-staleness.ps1"
  if (-not (Test-Path $hookPath)) {
    Write-Host "  [!] staleness hook script missing: $hookPath" -ForegroundColor $W
    $findings += "[4] 心跳告警钩子脚本不存在，本检查停摆将再次无人知晓"
  } else { Write-Host "  [OK] staleness hook script present" -ForegroundColor $OKC }

  $settingsPath = "$claude\settings.json"
  $hookRegistered = $false
  if (Test-Path $settingsPath) {
    $raw = Get-Content $settingsPath -Raw -Encoding UTF8
    $hookRegistered = $raw -match 'health-check-staleness'
  }
  if (-not $hookRegistered) {
    Write-Host "  [!] SessionStart hook NOT registered in settings.json" -ForegroundColor $W
    $findings += "[4] settings.json 未注册 SessionStart 心跳钩子"
  } else { Write-Host "  [OK] SessionStart hook registered" -ForegroundColor $OKC }

  $task = Get-ScheduledTask -TaskName "Claude-Env-HealthCheck" -EA SilentlyContinue
  if (-not $task) {
    Write-Host "  [!] scheduled task Claude-Env-HealthCheck not found" -ForegroundColor $W
    $findings += "[4] 计划任务 Claude-Env-HealthCheck 不存在"
  } else {
    if ($task.Settings.DisallowStartIfOnBatteries) {
      Write-Host "  [!] DisallowStartIfOnBatteries is ON -> will stall on battery (root cause of 2026-08 stall)" -ForegroundColor $W
      $findings += "[4] 计划任务电池闸被改回 ON——本机是笔记本，这会让它再次卡 Queued"
    } else { Write-Host "  [OK] battery gate off" -ForegroundColor $OKC }
    if (-not $task.Settings.StartWhenAvailable) {
      Write-Host "  [!] StartWhenAvailable is OFF -> missed monthly trigger never catches up" -ForegroundColor $W
      $findings += "[4] 计划任务未开 StartWhenAvailable，错过的月度触发不会补跑"
    } else { Write-Host "  [OK] StartWhenAvailable on" -ForegroundColor $OKC }
  }

  Write-Host "`n===== Done =====`n" -ForegroundColor $H
}
catch {
  $fatal = $_.Exception.Message
  Write-Host "`n[FATAL] $fatal" -ForegroundColor Red
}
finally {
  # 心跳必须无论如何都写——异常路径尤其要写，否则"崩了"与"没跑"仍然一个样。
  $status = [ordered]@{
    lastRunLocal   = $startedAt.ToString("yyyy-MM-dd HH:mm:ss")
    lastRunIso     = $startedAt.ToString("o")
    durationSec    = [math]::Round(((Get-Date) - $startedAt).TotalSeconds, 1)
    ok             = [bool]($null -eq $fatal)
    fatal          = $fatal
    findingCount   = $findings.Count
    findings       = @($findings)
    notes          = @($notes)
    host           = $env:COMPUTERNAME
  }
  try {
    $status | ConvertTo-Json -Depth 5 | Set-Content -Path $statusPath -Encoding UTF8
    Write-Host "心跳已写入：$statusPath（发现 $($findings.Count) 项）" -ForegroundColor DarkGray
  } catch {
    Write-Host "[FATAL] 心跳写入失败：$($_.Exception.Message)" -ForegroundColor Red
  }
  try { Stop-Transcript | Out-Null } catch {}
}

if ($fatal) { exit 1 }
exit 0
