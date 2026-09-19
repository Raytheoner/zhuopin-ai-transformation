# git 锁与 worktree 占用诊断 —— `工具-worktree体检.ps1` 与 `工具-泳道分支合入.ps1` 共用（队列 §一 #618）。
#
# 两件事：
#   (1) Get-GitLockStatus：扫 `<Repo>/.git/**/*.lock`，逐条给 age／size／clearable。
#       🔴 清除三条判据（队列 #618 拍板）：`Get-Process git` 计数为零 ＋ 锁文件 0 字节 ＋ 陈旧超阈值，三条齐备才 clearable。
#       只判定、不删除——删除动作留在调用方（`工具-worktree体检.ps1` 的 `-ClearStaleLocks`）。
#   (2) Find-WorktreeByBranch：给一个分支名，答「哪个 worktree 正检出它」，答不出返回 $null。
#       用于 `git worktree add` 撞 "already used by worktree" 时点名占用者——git 自己的报错文本里其实已带
#       占用路径，本函数是防报错文案跨版本变化的兜底核验，两者一起打印。

function Get-GitLockStatus {
    <#
    .SYNOPSIS
        扫描 `<Repo>/.git` 下全部 `*.lock`，逐条给 age(分钟)／size(字节)／clearable。
    .PARAMETER StaleMinutes
        陈旧阈值，默认 30（队列 #618 拍板值，与泳道看护看门狗同值）。
    .PARAMETER GitProcessCount
        测试可覆盖；不传则实测 `Get-Process git` 计数。
    #>
    param(
        [Parameter(Mandatory)][string]$Repo,
        [int]$StaleMinutes = 30,
        [Nullable[int]]$GitProcessCount = $null,
        [datetime]$Now = (Get-Date)
    )
    $gitDir = Join-Path $Repo '.git'
    $procCount = if ($null -ne $GitProcessCount) { $GitProcessCount } else { @(Get-Process git -ErrorAction SilentlyContinue).Count }
    $rows = @()
    if (Test-Path $gitDir) {
        $locks = @(Get-ChildItem -Path $gitDir -Recurse -Filter '*.lock' -File -ErrorAction SilentlyContinue)
        foreach ($lf in $locks) {
            $ageMin = [math]::Round(($Now - $lf.LastWriteTime).TotalMinutes, 1)
            $isStale = $ageMin -gt $StaleMinutes
            $isZeroByte = $lf.Length -eq 0
            $noGitProc = ($procCount -eq 0)
            $rows += [pscustomobject]@{
                path       = $lf.FullName.Substring($gitDir.Length).TrimStart('\', '/')
                fullPath   = $lf.FullName
                ageMinutes = $ageMin
                size       = $lf.Length
                clearable  = ($isStale -and $isZeroByte -and $noGitProc)
            }
        }
    }
    return [pscustomobject]@{ GitProcessCount = $procCount; StaleMinutes = $StaleMinutes; Locks = $rows }
}

function Format-GitLockStatusLines {
    <# 把 Get-GitLockStatus 的结果转成人读文本行数组，两处调用方（体检报告／ff 失败诊断）共用同一措辞。 #>
    param([Parameter(Mandatory)]$Status)
    $lines = @()
    if ($Status.Locks.Count -eq 0) {
        $lines += "锁状态：0 个 *.lock（git 进程数=$($Status.GitProcessCount)）"
        return $lines
    }
    $lines += "锁状态：$($Status.Locks.Count) 个 *.lock（git 进程数=$($Status.GitProcessCount)，陈旧阈值 $($Status.StaleMinutes) 分钟）："
    foreach ($r in $Status.Locks) {
        $tag = if ($r.clearable) { '可清' } else { '不可清' }
        $lines += "  .git\$($r.path)  age=$($r.ageMinutes)min size=$($r.size)B  $tag"
    }
    return $lines
}

function Find-WorktreeByBranch {
    <#
    .SYNOPSIS
        在 `$Repo` 的 `git worktree list --porcelain` 里找出哪个 worktree 正检出 `$Branch`。
    .OUTPUTS
        命中的 worktree 路径；未命中返回 $null。
    #>
    param(
        [Parameter(Mandatory)][string]$Repo,
        [Parameter(Mandatory)][string]$Branch
    )
    $raw = & git -C $Repo worktree list --porcelain 2>&1
    $curPath = $null; $curBranch = $null
    foreach ($line in $raw) {
        $s = [string]$line
        if ($s.StartsWith('worktree ')) {
            if ($curBranch -eq $Branch) { return $curPath }
            $curPath = $s.Substring(9); $curBranch = $null
        } elseif ($s.StartsWith('branch ')) {
            $curBranch = $s.Substring(7) -replace '^refs/heads/', ''
        }
    }
    if ($curBranch -eq $Branch) { return $curPath }
    return $null
}
