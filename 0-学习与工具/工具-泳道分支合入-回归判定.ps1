# 泳道分支合入 ④ 的回归判定逻辑，从 `工具-泳道分支合入.ps1` 抽出以便单测（不依赖真实 git/pytest 环境）。
# 判据正本：.claude/rules/两桌同步与取证.md §二 ——
#   "零回归"＝同一组失败用例在纯 master（零改动）用同一条命令复跑一次，逐条复现；
#   有任何一条只在本棒分支上红 ⇒ 新增失败，不绿即停。
# 修于 队列 §一 `#562`（`OP-0911-S`，2026-09-11）：原 ④ 用 `$LASTEXITCODE -ne 0` 二值判「未全绿」，
# 与本判据不一致——K2 行长闸日期夹具 2026-09-11 起在纯 master 上永久红，会天天假阳拦下每条分支。

function Get-PytestFailedTests {
    <#
    .SYNOPSIS
        从 `pytest -q -rf`（含 "short test summary info" 段）的完整输出中提取失败用例名集合。
    .PARAMETER Output
        pytest 的完整 stdout+stderr（多行字符串，或已按行拆好的字符串数组）。
    .OUTPUTS
        已排序去重的失败用例名字符串数组（可能为空数组）。
    #>
    param([Parameter(Mandatory)] $Output)
    $lines = if ($Output -is [string]) { $Output -split "`r?`n" } else { $Output }
    $names = foreach ($line in $lines) {
        if ($line -match '^FAILED\s+(\S+)') { $Matches[1] }
    }
    return @($names | Sort-Object -Unique)
}

function Get-PytestSummaryLine {
    <#
    .SYNOPSIS
        取 pytest 输出里被 `=====` 包住的结语行（如 `2 failed, 561 passed in 12.34s`），
        取不到则退回最后一行非空输出——供日志里"写出手段＋真实回显"用，不只是一句结论。
    #>
    param([Parameter(Mandatory)] $Output)
    $lines = if ($Output -is [string]) { $Output -split "`r?`n" } else { $Output }
    $m = $lines | Where-Object { $_ -match '=+\s*\d+\s+(passed|failed|error|skipped|warning)' } | Select-Object -Last 1
    if ($m) { return (($m -replace '^=+\s*', '') -replace '\s*=+$', '').Trim() }
    return (($lines | Where-Object { $_.Trim() } | Select-Object -Last 1))
}

function Get-NewFailures {
    <#
    .SYNOPSIS
        分支失败集合相对纯 master 失败集合的"新增"部分（集合差 BranchFailed - MasterFailed）。
        空 ⇒ 零回归、放行；非空 ⇒ 这些是本分支独有的新红、应拒。
    #>
    param(
        [Parameter(Mandatory)] [AllowEmptyCollection()] [string[]] $BranchFailed,
        [Parameter(Mandatory)] [AllowEmptyCollection()] [string[]] $MasterFailed
    )
    $masterSet = @{}
    foreach ($m in $MasterFailed) { $masterSet[$m] = $true }
    return @($BranchFailed | Where-Object { -not $masterSet.ContainsKey($_) })
}
