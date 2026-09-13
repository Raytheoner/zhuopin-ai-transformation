# 单条泳道分支 rebase → ff → push，带全套守卫。
# 用法：pwsh -File ffbranch.ps1 -Branch <分支名> [-Tests <pytest 目标，逗号分隔>] [-Repo <仓库根>] [-TempRoot <临时 worktree 父目录>]
# 🔴 任一守卫不过即停，不继续；备份 ref 先打，回滚靠它。
# 🔴 ④ 回归闸＝「与纯 master 比失败集合」，不是二值「全绿」（队列 §一 `#562`，`OP-0911-S`，2026-09-11；
#    判据正本 .claude/rules/两桌同步与取证.md §二）；集合比对函数见 `工具-泳道分支合入-回归判定.ps1`。
# 🔴 ⑹ 每次运行不论结局都在 `1-转型规划/0-全景路线图/合入登记/ff-patrol-<yyyyMMdd>.jsonl` 留一行（队列 §一 `#571` ⑹，
#    OP-0913-E；落点 OP-0913-L 自被 gitignore 整棵忽略的 reports/ 迁出）：各关通过与否、④ 两侧失败集合、
#    最终动作（合入／拒绝／被打断）＋退出码。落盘函数与路径正本在 `工具-合入链路留痕.ps1`（`Get-FfLedgerDir`）；
#    写不进日志只告警，不反过来拦合入。
#    `-Repo`／`-TempRoot` 只为单测能指向临时仓库而设，默认值即生产值，调用方不传即不变。
param(
    [Parameter(Mandatory)][string]$Branch,
    [string]$Tests = '',
    [string]$Repo = 'C:\Dev\zhuopin-ai',
    [string]$TempRoot = 'C:\Dev'
)

$ErrorActionPreference = 'Stop'
Set-Location $Repo
. (Join-Path $PSScriptRoot '工具-泳道分支合入-回归判定.ps1')
. (Join-Path $PSScriptRoot '工具-合入链路留痕.ps1')

$short = ($Branch -split '/')[-1]
$wt = Join-Path $TempRoot "_rb-$short"
$wtMaster = Join-Path $TempRoot "_rb-$short-master-baseline"
$bak = "backup/$short-pre-rebase"

# ⑹ 留痕状态：各关默认 $null＝没走到；走到即写 $true/$false。退出码→动作的映射见 Resolve-MergeAction。
$gates = @{ '①备份ref' = $null; '②脏文件零交集' = $null; '③rebase零冲突' = $null; '④回归零新增' = $null; '⑤ff+push' = $null; '⑥四ref一致' = $null }
$failedBranchAll = @(); $failedMasterAll = @()
$extra = @{ tests = $Tests; master_before = ''; master_after = ''; branch_before = ''; branch_after = ''; exit = $null; note = '' }

function Resolve-MergeAction {
    <# 退出码 → 最终动作。0 合入；2（脏文件交集）／4（回归新增失败）＝守卫说「不」＝拒绝；
       3（rebase 冲突）／5（ff 失败）／6（四 ref 不一致）／9（脚本异常）＝流程没走到判定＝被打断。 #>
    param([int]$Code)
    switch ($Code) { 0 { '合入' } 2 { '拒绝' } 4 { '拒绝' } default { '被打断' } }
}

function Invoke-LaneMerge {
    <# 六关主体。返回退出码；留痕由外层 finally 统一写，本函数只填 $script:gates／$script:extra。
       🔴 函数体内原生命令的 stdout 一律经 Write-Host 走宿主流，不能漏进输出流——否则返回值变成数组，
       `[int]` 转换即炸（首跑单测实撞）。 #>
    Write-Host "=== [$Branch] 起点 ==="
    git fetch --quiet
    $before = (git rev-parse --short $Branch)
    $masterSha = (git rev-parse master)
    $script:extra.branch_before = $before
    $script:extra.master_before = (git rev-parse --short master)
    Write-Host "  分支 $before ｜ master $($script:extra.master_before)"

    # ① 备份 ref（已存在则不覆盖，保留最早那份）
    git show-ref --verify --quiet "refs/heads/$bak"
    if ($LASTEXITCODE -ne 0) { git branch $bak $Branch | Out-Null; Write-Host "  备份 ref $bak = $before" }
    else { Write-Host "  备份 ref 已存在，保留原值 $(git rev-parse --short $bak)" }
    $script:gates['①备份ref'] = $true

    # ② 脏文件零交集守卫
    $touched = git show --name-only --format='' $Branch | Where-Object { $_ }
    $dirty = git status --porcelain | ForEach-Object { $_.Substring(3).Trim('"') }
    $x = $touched | Where-Object { $dirty -contains $_ }
    if ($x) {
        Write-Host "🔴 与脏文件有交集，停手：$($x -join ', ')"
        $script:gates['②脏文件零交集'] = $false; $script:extra.note = "脏文件交集：$($x -join ', ')"
        return 2
    }
    Write-Host "  ✓ 触碰 $($touched.Count) 文件，与 $($dirty.Count) 个脏文件零交集"
    $script:gates['②脏文件零交集'] = $true

    # ③ 临时 worktree 里 rebase（不动主 checkout 的脏工作区）
    if (Test-Path $wt) { git worktree remove $wt --force | Out-Null }
    git worktree add $wt $Branch 2>&1 | Out-Null
    Push-Location $wt
    git rebase master 2>&1 | Select-Object -Last 2 | ForEach-Object { Write-Host "  $_" }
    if ($LASTEXITCODE -ne 0) {
        Write-Host "🔴 rebase 有冲突，已停在冲突态。人工处理或 git rebase --abort 后回 $bak"
        Pop-Location
        $script:gates['③rebase零冲突'] = $false; $script:extra.note = "rebase 冲突，停在 $wt"
        return 3
    }
    $after = (git rev-parse --short HEAD)
    $script:extra.branch_after = $after
    Write-Host "  ✓ rebase 零冲突：$before → $after"
    $script:gates['③rebase零冲突'] = $true

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
                $script:failedBranchAll += $branchFailed

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
                $script:failedMasterAll += $masterFailed

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
    if (-not $testsOk) {
        Write-Host "🔴 回归有新增失败，不 ff。分支停在 $after，备份在 $bak"
        $script:gates['④回归零新增'] = $false
        return 4
    }
    $script:gates['④回归零新增'] = $true
    if ($regressionNote) {
        Write-Host "  零回归明细（判据 .claude/rules/两桌同步与取证.md §二）："
        $regressionNote | ForEach-Object { Write-Host $_ }
    }

    # ⑤ ff + push
    git merge --ff-only $Branch 2>&1 | Select-Object -Last 1 | ForEach-Object { Write-Host "  $_" }
    if ($LASTEXITCODE -ne 0) { Write-Host "🔴 ff 失败"; $script:gates['⑤ff+push'] = $false; return 5 }
    $script:extra.master_after = (git rev-parse --short master)
    Write-Host "  ✓ master → $($script:extra.master_after)"
    git push origin master 2>&1 | Select-Object -Last 1 | ForEach-Object { Write-Host "  $_" }
    git push --force-with-lease origin "${Branch}:${Branch}" 2>&1 | Select-Object -Last 1 | ForEach-Object { Write-Host "  $_" }
    $script:gates['⑤ff+push'] = $true

    # ⑥ 四 ref 核对 ＋ 清理
    $m = git rev-parse --short master; $b = git rev-parse --short $Branch
    $om = git rev-parse --short origin/master; $ob = git rev-parse --short "origin/$Branch"
    Write-Host "  四 ref：master=$m origin/master=$om 分支=$b origin/分支=$ob"
    if (($m -ne $b) -or ($m -ne $om) -or ($m -ne $ob)) {
        Write-Host "🔴 四 ref 不一致，人工核"
        $script:gates['⑥四ref一致'] = $false; $script:extra.note = "master=$m origin/master=$om 分支=$b origin/分支=$ob"
        return 6
    }
    $script:gates['⑥四ref一致'] = $true
    git worktree remove $wt --force | Out-Null
    Write-Host "✅ [$Branch] 完成，临时 worktree 已清"
    return 0
}

$code = 9
try {
    $code = [int](@(Invoke-LaneMerge) | Select-Object -Last 1)
} catch {
    # 🔴 `$ErrorActionPreference='Stop'` 下任何原生命令／cmdlet 抛错都落到这里：算「被打断」，不算「拒绝」。
    Write-Host "🔴 合入脚本异常中断：$($_.Exception.Message)"
    $extra.note = "异常：$($_.Exception.Message)"
    $code = 9
} finally {
    $extra.exit = $code
    $tracePath = Write-FfPatrolTrace -Repo $Repo -Actor '合入' -Branch $Branch -Action (Resolve-MergeAction -Code $code) `
        -Gates $gates -FailedBranch $failedBranchAll -FailedMaster $failedMasterAll -Extra $extra
    Write-Host "  留痕 → $tracePath（action=$(Resolve-MergeAction -Code $code)，exit=$code）"
}
exit $code
