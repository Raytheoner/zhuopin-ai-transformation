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


# ─────────────────────────────────────────────────────────────────────────────
# 队列 §一 `#567` 同族第三例（2026-09-20 `OP-0919-K` 实撞补立）：**回归段会挂死，且挂死不落哨兵。**
# 实证：2026-09-19 23:54 起的一条 ff，`python -m pytest` 跑到一半机器休眠，醒来后进程还在、
# 日志 **8 小时 47 分一个字没写**；`工具-泳道分支合入.ps1` 同步等 `& python`，永远等不到返回 ⇒
# 外层包装的 `<log>.done` 哨兵也永远不落 ⇒ **看护者按「只探哨兵」的纪律会一直判成「还在跑」**。
# 🔑 判词：一个只会在成功时返回的调用，等同于没有超时；**挂死必须自己变成一个结局**，否则它
# 会伪装成「进行中」直到有人用肉眼发现。同 `#550`（哨兵缺失）／`#618`（陈旧锁）一族。
#
# 修法＝**空闲超时**（不是总时长超时）：只要还在产出就不打断（全量回归本来就要 29 分钟），
# 连续 `IdleTimeoutSeconds` 没有任何新输出才判挂死、杀进程树、如实返回 `TimedOut`。
# 🔴 判超时不等于判回归失败——调用方须把它记成「被打断」（退出码 7），不得记成「新增失败」。
function Invoke-PytestWithIdleTimeout {
    <# 跑一条 pytest，带空闲超时。返回 @{ Output=<string[]>; ExitCode=<int>; TimedOut=<bool>; IdleSeconds=<int> }。
       `-Command`／`-ArgList` 可注入（单测用假命令验证超时与正常两条路径，不需要真 pytest）。#>
    param(
        [Parameter(Mandatory)][string]$PytestTarget,
        [string]$WorkingDirectory = '.',
        [int]$IdleTimeoutSeconds = 1200,
        [int]$PollSeconds = 5,
        [string]$Command = 'python',
        [string[]]$ArgList = $null
    )
    if (-not $ArgList) { $ArgList = @('-m', 'pytest', $PytestTarget, '-q', '-rf') }
    $outFile = [System.IO.Path]::GetTempFileName()
    $errFile = [System.IO.Path]::GetTempFileName()
    try {
        $p = Start-Process -FilePath $Command -ArgumentList $ArgList -WorkingDirectory $WorkingDirectory `
             -RedirectStandardOutput $outFile -RedirectStandardError $errFile -NoNewWindow -PassThru
        $lastSize = -1
        $lastChange = Get-Date
        while (-not $p.HasExited) {
            Start-Sleep -Seconds $PollSeconds
            $size = 0
            foreach ($f in @($outFile, $errFile)) {
                if (Test-Path -LiteralPath $f) { $size += (Get-Item -LiteralPath $f).Length }
            }
            if ($size -ne $lastSize) { $lastSize = $size; $lastChange = Get-Date }
            elseif (((Get-Date) - $lastChange).TotalSeconds -ge $IdleTimeoutSeconds) {
                # 杀进程树：pytest 常有子进程，只杀父进程会留孤儿继续占着 worktree。
                try { & taskkill /PID $p.Id /T /F 2>&1 | Out-Null } catch { }
                try { Stop-Process -Id $p.Id -Force -ErrorAction SilentlyContinue } catch { }
                $txt = @()
                foreach ($f in @($outFile, $errFile)) {
                    if (Test-Path -LiteralPath $f) { $txt += (Get-Content -LiteralPath $f -ErrorAction SilentlyContinue) }
                }
                return [pscustomobject]@{
                    Output = $txt; ExitCode = 124; TimedOut = $true
                    IdleSeconds = [int]((Get-Date) - $lastChange).TotalSeconds
                }
            }
        }
        $p.WaitForExit()
        $txt = @()
        foreach ($f in @($outFile, $errFile)) {
            if (Test-Path -LiteralPath $f) { $txt += (Get-Content -LiteralPath $f -ErrorAction SilentlyContinue) }
        }
        return [pscustomobject]@{ Output = $txt; ExitCode = $p.ExitCode; TimedOut = $false; IdleSeconds = 0 }
    } finally {
        foreach ($f in @($outFile, $errFile)) { Remove-Item -LiteralPath $f -Force -ErrorAction SilentlyContinue }
    }
}
