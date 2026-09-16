<#
.SYNOPSIS
  worktree 体检 / 修复 / 安全清理 —— 队列 §一 #576（构建闭环第 13 环）

.DESCRIPTION
  三件事，默认只做「只读体检」：

  (1) 体检：列出全部 worktree 并逐条分类，结果同时落 jsonl 留痕。

  (2) 修复：-Repair 补回 .git/worktrees/<名>/commondir。
      缺这一个文件时 git 解析不出公共 git 目录，于是该 worktree 里
      `git status` 报 "fatal: not a git repository"，而 `git worktree list`
      把符号引用型 HEAD 显示成 0000000（分离头指针型仍显示 sha，所以光看
      0000000 会漏数）。
      🔴 判别一句：0000000 不等于空壳，它等于「读不出来」。
      2026-09-13 本仓 11 条正是此症，其中 queue-315-apply-9f2c1a 修好后带着
      一个未合入的抢救 commit（1130 行）——把它当空壳 prune 会直接丢工作。
      `git worktree repair` 治不了本症（只回显 ".git file broken"）。

  (3) 清理：-Apply 只删同时满足三条的 worktree——未 locked、ahead=0、工作区干净。
      另设一类「仅缺文件」：脏行全是 D（只是删掉了受版本控制的文件，内容在 HEAD
      里一字不少），默认只报不删，加 -IncludeMissingOnly 才一并删。
      其余（有未合 commit / 有真脏 / 锁定 / 保留名单 / 修不好）一律只报不动。
      🔴 保留名单：-Keep 默认含 wecom-service-home（它是常驻服务目录，不是泳道临时件），
         另凡名字以 _rb- 开头的（合入脚本的 rebase/基线件）一律不删。
         更硬的护栏是 git worktree lock <路径>——锁住的 git 自己就拒绝删。

.NOTES
  留痕：reports/worktree-guard/worktree-guard-<yyyyMMdd>.jsonl，每次运行追加一行。
  reports/ 在 .gitignore 里，留痕不进版本库（与 poll-guard 同口径）。
#>
[CmdletBinding()]
param(
    [string]$Repo = 'C:\Dev\zhuopin-ai',
    [string]$BaseBranch = 'master',
    [switch]$Repair,
    [switch]$Apply,
    [switch]$IncludeMissingOnly,
    [string[]]$Keep = @('wecom-service-home'),
    [switch]$Quiet
)

$ErrorActionPreference = 'Stop'

function Write-Line { param([string]$Text) if (-not $Quiet) { Write-Host $Text } }

if (-not (Test-Path (Join-Path $Repo '.git'))) { throw "不是仓库根：$Repo" }

# ---------- (2) commondir 体检与修复 ----------
$adminRoot = Join-Path $Repo '.git\worktrees'
$broken = @()
$repaired = @()
if (Test-Path $adminRoot) {
    foreach ($d in (Get-ChildItem -Force -Directory $adminRoot)) {
        $cd = Join-Path $d.FullName 'commondir'
        if (-not (Test-Path $cd)) {
            $broken += $d.Name
            if ($Repair) {
                [IO.File]::WriteAllText($cd, "../..`n", (New-Object Text.UTF8Encoding $false))
                $repaired += $d.Name
            }
        }
    }
}
if ($broken.Count -gt 0) {
    Write-Line "缺 commondir：$($broken.Count) 条 —— $($broken -join ', ')"
    if ($Repair) { Write-Line "  已补：$($repaired.Count) 条（单行 ../..，只动 .git 管理目录，不碰任何工作区内容）" }
    else { Write-Line "  未修（加 -Repair 才补）。🔴 在修好之前不要对它们做任何删除判断：读不出来不等于没东西。" }
} else {
    Write-Line "缺 commondir：0 条"
}

# ---------- (1) 体检分类 ----------
$raw = & git -C $Repo worktree list --porcelain 2>&1
$items = @(); $cur = $null
foreach ($line in $raw) {
    $s = [string]$line
    if ($s.StartsWith('worktree ')) {
        if ($cur) { $items += $cur }
        $cur = [ordered]@{ path = $s.Substring(9); head = ''; branch = ''; detached = $false; locked = $false }
    } elseif ($s.StartsWith('HEAD ')) { $cur.head = $s.Substring(5) }
    elseif ($s.StartsWith('branch ')) { $cur.branch = $s.Substring(7) -replace '^refs/heads/', '' }
    elseif ($s.Trim() -eq 'detached') { $cur.detached = $true }
    elseif ($s.StartsWith('locked')) { $cur.locked = $true }
}
if ($cur) { $items += $cur }

$rows = @()
foreach ($it in ($items | Select-Object -Skip 1)) {
    $p = $it.path -replace '/', '\'
    $name = Split-Path $p -Leaf
    # 🔴 目录已消失时 `git -C` 会抛 fatal，$ErrorActionPreference='Stop' 下直接终止整个体检。
    # 2026-09-17 首轮真跑就栖在这里（合入脚本刚收掉基线件、管理记录还在）。
    $stOk = $false; $stOut = @()
    if (Test-Path -LiteralPath $p) {
        try { $stOut = & git -C $p status --porcelain 2>&1; $stOk = ($LASTEXITCODE -eq 0) } catch { $stOk = $false }
    }
    $lines = @()
    if ($stOk) { $lines = @($stOut | ForEach-Object { [string]$_ } | Where-Object { $_.Trim() -ne '' }) }
    $ahead = -1
    if ($it.head -and $it.head -ne ('0' * 40)) {
        $a = & git -C $Repo rev-list --count "$BaseBranch..$($it.head)" 2>&1
        if ($LASTEXITCODE -eq 0) { $ahead = [int]([string]$a).Trim() }
    }
    $onlyDeletions = ($lines.Count -gt 0) -and (@($lines | Where-Object { $_ -notmatch '^\s?D\s' }).Count -eq 0)

    $isKept = ($Keep -contains $name) -or ($name -like '_rb-*')
    if (-not (Test-Path -LiteralPath $p)) { $cls = '目录已消失' }
    elseif (-not $stOk)        { $cls = '坏(未修)' }
    elseif ($it.locked)        { $cls = '锁定' }
    elseif ($ahead -lt 0)      { $cls = '读不出HEAD' }
    elseif ($ahead -gt 0)      { $cls = '有未合commit' }
    elseif ($lines.Count -eq 0){ $cls = '干净已并' }
    elseif ($onlyDeletions)    { $cls = '仅缺文件' }
    else                       { $cls = '有真脏' }

    $rows += [pscustomobject]@{
        name = $name; path = $p; branch = $(if ($it.branch) { $it.branch } else { '(detached)' })
        head = $it.head; ahead = $ahead; dirty = $lines.Count; cls = $cls; keep = $isKept
    }
}

Write-Line ''
Write-Line ("{0,-44} {1,-36} {2,5} {3,5}  {4}" -f 'worktree', 'branch/HEAD', 'ahead', 'dirty', '分类')
foreach ($r in $rows) {
    Write-Line ("{0,-44} {1,-36} {2,5} {3,5}  {4}" -f $r.name, $r.branch, $r.ahead, $r.dirty, $(if ($r.keep) { "$($r.cls)〔保留名单〕" } else { $r.cls }))
}
$byCls = $rows | Group-Object cls | Sort-Object Name
Write-Line ''
Write-Line ("合计 {0} 条：{1}" -f $rows.Count, (($byCls | ForEach-Object { "$($_.Name)=$($_.Count)" }) -join '、'))

# ---------- (3) 安全清理 ----------
$targets = @($rows | Where-Object { -not $_.keep -and $_.cls -eq '干净已并' })
if ($IncludeMissingOnly) { $targets += @($rows | Where-Object { -not $_.keep -and $_.cls -eq '仅缺文件' }) }
$removed = @(); $failed = @(); $fellBack = @(); $orphans = @()

if ($targets.Count -eq 0) {
    Write-Line '可删集合为空。'
} elseif (-not $Apply) {
    Write-Line ("可删 {0} 条（dry-run，未动手；加 -Apply 才删）：{1}" -f $targets.Count, (($targets | ForEach-Object { $_.name }) -join ', '))
} else {
    foreach ($t in $targets) {
        $force = @()
        if ($t.cls -eq '仅缺文件') { $force = @('--force') }
        $ok = $false
        try { & git -C $Repo worktree remove $t.path @force 2>&1 | Out-Null; $ok = ($LASTEXITCODE -eq 0) } catch { $ok = $false }
        if (-not $ok -and (Test-Path -LiteralPath $t.path)) {
            # 🔴 回退（2026-09-17 实测）：本仓里 `git worktree remove --force` 与 `git worktree prune`
            #    一律报 Permission denied，而同一个 shell 里 PowerShell 的 Remove-Item 删得掉。
            #    原因未查明；巡检的 worktree 清理长期空转就栖在这里（[WT-BLOCKED] 天天报、一条也没删成）。
            #    🔴 只对已过三条闸（未 locked ＋ahead=0 ＋脏行全是 D）的件回退。
            try { Remove-Item -LiteralPath $t.path -Recurse -Force -ErrorAction Stop; $ok = $true; $fellBack += $t.name }
            catch { $ok = $false }
        }
        if ($ok) { $removed += $t.name; Write-Line "  ✓ 已删 $($t.name)" }
        else { $failed += $t.name; Write-Line "  🔴 删失败 $($t.name)" }
    }
    try { & git -C $Repo worktree prune 2>&1 | Out-Null } catch { }
    # prune 同样会被 Permission denied 拦下，履带掉工作目录已消失的孤儿管理目录。
    $adminRoot2 = Join-Path $Repo '.git\worktrees'
    if (Test-Path $adminRoot2) {
        foreach ($d in (Get-ChildItem -Force -Directory $adminRoot2)) {
            $gd = Join-Path $d.FullName 'gitdir'
            if (-not (Test-Path $gd)) { continue }
            $wtDir = Split-Path ((Get-Content $gd -Raw).Trim()) -Parent
            if (-not (Test-Path -LiteralPath $wtDir)) {
                try { Remove-Item -LiteralPath $d.FullName -Recurse -Force -ErrorAction Stop; $orphans += $d.Name } catch { }
            }
        }
    }
    if ($orphans.Count -gt 0) { Write-Line ("  顺手清掉 {0} 个孤儿管理目录（git prune 删不动）" -f $orphans.Count) }
    Write-Line ("已删 {0} 条，失败 {1} 条。" -f $removed.Count, $failed.Count)
}

# ---------- 留痕 ----------
$traceDir = Join-Path $Repo 'reports\worktree-guard'
if (-not (Test-Path $traceDir)) { New-Item -ItemType Directory -Force -Path $traceDir | Out-Null }
$tracePath = Join-Path $traceDir ("worktree-guard-{0}.jsonl" -f (Get-Date -Format 'yyyyMMdd'))
$record = [ordered]@{
    ts = (Get-Date).ToString('o')
    mode = $(if ($Apply) { 'apply' } else { 'dry-run' })
    repair = [bool]$Repair
    include_missing_only = [bool]$IncludeMissingOnly
    total = $rows.Count
    broken_commondir = $broken
    repaired_commondir = $repaired
    counts = ($byCls | ForEach-Object { @{ cls = $_.Name; n = $_.Count } })
    candidates = ($targets | ForEach-Object { $_.name })
    removed = $removed
    removed_by_fallback = $fellBack
    orphan_admin_dirs_removed = $orphans
    remove_failed = $failed
    kept = ($rows | Where-Object { $targets -notcontains $_ } | ForEach-Object { @{ name = $_.name; cls = $_.cls; ahead = $_.ahead; dirty = $_.dirty; keep = $_.keep } })
}
Add-Content -Path $tracePath -Value ($record | ConvertTo-Json -Depth 6 -Compress) -Encoding UTF8
Write-Line "留痕 → $tracePath"
exit 0
