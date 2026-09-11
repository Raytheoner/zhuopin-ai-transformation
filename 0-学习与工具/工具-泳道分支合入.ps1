# 单条泳道分支 rebase → ff → push，带全套守卫。
# 用法：pwsh -File ffbranch.ps1 -Branch <分支名> [-Tests <pytest 目标，逗号分隔>]
# 🔴 任一守卫不过即停，不继续；备份 ref 先打，回滚靠它。
# 🔴 ④ 回归闸＝「与纯 master 比失败集合」，不是二值「全绿」（队列 §一 `#562`，`OP-0911-S`，2026-09-11；
#    判据正本 .claude/rules/两桌同步与取证.md §二）；集合比对函数见 `工具-泳道分支合入-回归判定.ps1`。
param([Parameter(Mandatory)][string]$Branch, [string]$Tests = '')

$ErrorActionPreference = 'Stop'
$Repo = 'C:\Dev\zhuopin-ai'
Set-Location $Repo
. (Join-Path $PSScriptRoot '工具-泳道分支合入-回归判定.ps1')

$short = ($Branch -split '/')[-1]
$wt = "C:\Dev\_rb-$short"
$wtMaster = "C:\Dev\_rb-$short-master-baseline"
$bak = "backup/$short-pre-rebase"

Write-Host "=== [$Branch] 起点 ==="
git fetch --quiet
$before = (git rev-parse --short $Branch)
$masterSha = (git rev-parse master)
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

# ④ 回归（仅当给了 -Tests）—— 与纯 master（$masterSha，rebase 前）比失败集合，不是二值「全绿」。
#    分支失败集合 ⊆ master 同命令失败集合 ⇒ 零回归、放行；有新增失败 ⇒ 拒。
$testsOk = $true
$regressionNote = @()
if ($Tests) {
    foreach ($t in ($Tests -split ',')) {
        $cmd = "python -m pytest $t -q -rf"
        Write-Host "  跑 $t ..."
        $branchOut = & python -m pytest $t -q -rf 2>&1
        if ($LASTEXITCODE -ne 0) {
            $branchFailed = @(Get-PytestFailedTests -Output $branchOut)
            $branchSummary = Get-PytestSummaryLine -Output $branchOut
            Write-Host "    分支侧（$cmd）：$branchSummary ｜ 失败：$($branchFailed -join ', ')"

            if (Test-Path $wtMaster) { git worktree remove $wtMaster --force | Out-Null }
            git worktree add --detach $wtMaster $masterSha 2>&1 | Out-Null
            try {
                Push-Location $wtMaster
                $masterOut = & python -m pytest $t -q -rf 2>&1
            } finally {
                Pop-Location
                git worktree remove $wtMaster --force | Out-Null
            }
            $masterFailed = @(Get-PytestFailedTests -Output $masterOut)
            $masterSummary = Get-PytestSummaryLine -Output $masterOut
            Write-Host "    纯 master $($masterSha.Substring(0,7))（同命令 $cmd）：$masterSummary ｜ 失败：$($masterFailed -join ', ')"

            $newFailed = @(Get-NewFailures -BranchFailed $branchFailed -MasterFailed $masterFailed)
            if ($newFailed.Count -gt 0) {
                Write-Host "🔴 新增失败（分支独有，纯 master 同命令不红）：$($newFailed -join ', ')"
                $testsOk = $false
            } else {
                Write-Host "  ✓ 零回归：分支失败集合 ⊆ 纯 master 同命令失败集合，逐条复现"
                $regressionNote += "  · $t ：分支「$branchSummary」，纯 master 同命令同样失败 $($branchFailed -join ', ')"
            }
        } else {
            Write-Host "    ✓ 全绿"
        }
    }
}
Pop-Location
if (-not $testsOk) { Write-Host "🔴 回归有新增失败，不 ff。分支停在 $after，备份在 $bak"; exit 4 }
if ($regressionNote) {
    Write-Host "  零回归明细（判据 .claude/rules/两桌同步与取证.md §二）："
    $regressionNote | ForEach-Object { Write-Host $_ }
}

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
