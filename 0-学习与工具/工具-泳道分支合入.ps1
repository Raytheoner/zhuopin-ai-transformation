# 单条泳道分支 rebase → ff → push，带全套守卫。
# 用法：pwsh -File ffbranch.ps1 -Branch <分支名> [-Tests <pytest 目标，逗号分隔>]
# 🔴 任一守卫不过即停，不继续；备份 ref 先打，回滚靠它。
param([Parameter(Mandatory)][string]$Branch, [string]$Tests = '')

$ErrorActionPreference = 'Stop'
$Repo = 'C:\Dev\zhuopin-ai'
Set-Location $Repo

$short = ($Branch -split '/')[-1]
$wt = "C:\Dev\_rb-$short"
$bak = "backup/$short-pre-rebase"

Write-Host "=== [$Branch] 起点 ==="
git fetch --quiet
$before = (git rev-parse --short $Branch)
Write-Host "  分支 $before ｜ master $(git rev-parse --short master)"

# ① 备份 ref（已存在则不覆盖，保留最早那份）
git show-ref --verify --quiet "refs/heads/$bak"
if ($LASTEXITCODE -ne 0) { git branch $bak $Branch | Out-Null; Write-Host "  备份 ref $bak = $before" }
else { Write-Host "  备份 ref 已存在，保留原值 $(git rev-parse --short $bak)" }

# ② 脏文件零交集守卫
$touched = git show --name-only --format='' $Branch | Where-Object { $_ }
$dirty = git status --porcelain | ForEach-Object { $_.Substring(3).Trim('"') }
$x = $touched | Where-Object { $dirty -contains $_ }
if ($x) { Write-Host "🔴 与脏文件有交集，停手：$($x -join ', ')"; exit 2 }
Write-Host "  ✓ 触碰 $($touched.Count) 文件，与 $($dirty.Count) 个脏文件零交集"

# ③ 临时 worktree 里 rebase（不动主 checkout 的脏工作区）
if (Test-Path $wt) { git worktree remove $wt --force | Out-Null }
git worktree add $wt $Branch 2>&1 | Out-Null
Push-Location $wt
git rebase master 2>&1 | Select-Object -Last 2
if ($LASTEXITCODE -ne 0) {
    Write-Host "🔴 rebase 有冲突，已停在冲突态。人工处理或 git rebase --abort 后回 $bak"
    Pop-Location; exit 3
}
$after = (git rev-parse --short HEAD)
Write-Host "  ✓ rebase 零冲突：$before → $after"

# ④ 回归（仅当给了 -Tests）
$testsOk = $true
if ($Tests) {
    foreach ($t in ($Tests -split ',')) {
        Write-Host "  跑 $t ..."
        $out = & python -m pytest $t -q 2>&1 | Select-Object -Last 2
        Write-Host "    $out"
        if ($LASTEXITCODE -ne 0) { $testsOk = $false }
    }
}
Pop-Location
if (-not $testsOk) { Write-Host "🔴 回归未全绿，不 ff。分支停在 $after，备份在 $bak"; exit 4 }

# ⑤ ff + push
git merge --ff-only $Branch 2>&1 | Select-Object -Last 1
if ($LASTEXITCODE -ne 0) { Write-Host "🔴 ff 失败"; exit 5 }
Write-Host "  ✓ master → $(git rev-parse --short master)"
git push origin master 2>&1 | Select-Object -Last 1
git push --force-with-lease origin "${Branch}:${Branch}" 2>&1 | Select-Object -Last 1

# ⑥ 四 ref 核对 ＋ 清理
$m = git rev-parse --short master; $b = git rev-parse --short $Branch
$om = git rev-parse --short origin/master; $ob = git rev-parse --short "origin/$Branch"
Write-Host "  四 ref：master=$m origin/master=$om 分支=$b origin/分支=$ob"
if (($m -ne $b) -or ($m -ne $om) -or ($m -ne $ob)) { Write-Host "🔴 四 ref 不一致，人工核" ; exit 6 }
git worktree remove $wt --force | Out-Null
Write-Host "✅ [$Branch] 完成，临时 worktree 已清"
