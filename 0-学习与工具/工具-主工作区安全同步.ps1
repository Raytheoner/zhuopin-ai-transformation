# ================================================================
#  工具-主工作区安全同步.ps1
#  用途：主工作区（C:\...\企业AI转型，非 worktree）常年被 Cowork 留有未提交编辑，
#  当某个 CC worktree 完工推送 master 后，主工作区的本地 master 指针会落后、
#  且遗留编辑可能已被吸收进新提交——本脚本把"确认安全→同步"这套检查固化下来，
#  避免每次都临场判断，遇到类似场景（CC 推送后需要把主工作区同步到最新）直接跑。
#  首次由 QD-B 极简版发布收口（2026-07-23，commit eabbfca）收工时的真实场景抽出。
#
#  用法：在任意目录，管理员或普通 PowerShell 均可（脚本会自己 cd 到主工作区）：
#    powershell -ExecutionPolicy Bypass -File "0-学习与工具\工具-主工作区安全同步.ps1"
#
#  只做检查+安全操作，遇到任何不确定情况一律中止、不替你做判断：
#    有活跃 git 进程/锁文件 → 中止
#    工作区有未预期的未提交改动 → 中止
#    本地领先 origin（非单纯落后）→ 中止（需人工 rebase/merge）
#    干净且单纯落后 → git pull --ff-only
#    有遗留 stash → 只打印查看/删除命令，不自动 drop（不可逆操作需人工确认）
#
#  队列 #101①（2026-08-05 补）：脏文件检查新增硬检查——命中 §二「待 commit 批次」
#  声明清单的脏文件不再建议 `git checkout --`，改为提示触发 sweep 落库（协议〇.8
#  "批次即扫 + checkout 前核对 §二"落到工具上）。核验复用
#  `工具-落库sweep.py --check-dirty-in-pending-batch`（与 sweep 自身批次匹配同一套
#  逻辑，不另起一套判据）；该脚本不可用或调用失败时按更保守方式处理（视为命中，
#  不建议 checkout），不会因核验失败而放行危险操作。
# ================================================================
$ErrorActionPreference = "Stop"
$REPO = "C:\Users\Paul Shao\OneDrive\Projects\企业AI转型"

Write-Host "`n== 主工作区安全同步 ==" -ForegroundColor Cyan
Write-Host "   目录: $REPO`n"

Set-Location $REPO

# ── 1. 活跃进程/锁文件检查 ──
Write-Host "[1/5] 检查是否有活跃 git 进程或锁文件..." -ForegroundColor Yellow
$gitProcs = Get-Process git -ErrorAction SilentlyContinue
if ($gitProcs) {
    Write-Host "   ✗ 发现正在运行的 git 进程（PID: $($gitProcs.Id -join ', ')），可能有会话正在操作本仓库。" -ForegroundColor Red
    Write-Host "     请先确认该进程是否是别的会话在用，不要强行继续。已中止。" -ForegroundColor Red
    exit 1
}
$lockFile = Join-Path $REPO ".git\index.lock"
if (Test-Path $lockFile) {
    $age = (Get-Date) - (Get-Item $lockFile).LastWriteTime
    Write-Host "   ✗ 发现 .git\index.lock（存在 $([int]$age.TotalMinutes) 分钟）。" -ForegroundColor Red
    Write-Host "     没有活跃 git 进程时，这多半是残留锁文件，但为稳妥起见本脚本不自动删——" -ForegroundColor Red
    Write-Host "     确认无活跃会话后可手动执行： Remove-Item '$lockFile'  再重跑本脚本。" -ForegroundColor Red
    exit 1
}
Write-Host "   ✓ 无活跃 git 进程、无锁文件" -ForegroundColor Green

# ── 2. 工作区状态检查（是否还有未预期的未提交改动）──
Write-Host "[2/5] 检查工作区状态..." -ForegroundColor Yellow
$dirty = git status --porcelain
if ($dirty) {
    Write-Host "   ⚠ 工作区仍有未提交改动：" -ForegroundColor DarkYellow
    $dirty | ForEach-Object { Write-Host "     $_" -ForegroundColor DarkYellow }

    # 队列 #101①：checkout 前先核对 §二"待 commit 批次"声明清单（协议〇.8
    # "批次即扫 + checkout 前核对 §二"）——2026-07-24 曾有一批文件在 sweep
    # 敞口期被本脚本按"改动已过时"误弃，靠会话记录重打恢复（见 CLAUDE.md
    # §5、队列 #101 行）。本检查把这条纸面规则落到工具上：脏文件命中任一
    # 待处理批次声明时，禁止建议 git checkout --，改为提示触发 sweep。
    $dirtyPaths = $dirty | ForEach-Object { $_.Substring(3).Trim().Trim('"') }
    $sweepScript = Join-Path $REPO "0-学习与工具\工具-落库sweep.py"
    $checkOutput = @()
    $hitBatch = $false
    if ((Test-Path $sweepScript) -and $dirtyPaths.Count -gt 0) {
        $checkOutput = & python $sweepScript --check-dirty-in-pending-batch @dirtyPaths 2>$null
        if ($LASTEXITCODE -eq 0) {
            $matched = $checkOutput | Where-Object { $_ -like "MATCH*" }
            if ($matched) { $hitBatch = $true }
        } else {
            Write-Host "   ⚠ §二 批次核验脚本调用失败（退出码 $LASTEXITCODE），无法确认脏文件是否命中待处理批次，按更保守的方式处理——不建议 checkout。" -ForegroundColor DarkYellow
            $hitBatch = $true   # 核验本身失败时，不能假装"未命中"，从低取值
        }
    }

    if ($hitBatch) {
        Write-Host "`n   🔴 以下脏文件命中 §二「待 commit 批次」的声明清单——禁止 git checkout --，那会丢弃尚未落库的合法在办工作：" -ForegroundColor Red
        $matched | ForEach-Object { Write-Host "     $_" -ForegroundColor Red }
        Write-Host "   正确处置：触发一次 sweep 落库，不要自己判断丢弃。" -ForegroundColor Cyan
        Write-Host "     Start-ScheduledTask -TaskName ZhuopinCommitSweep" -ForegroundColor DarkGray
        Write-Host "   sweep 落库后这些文件会自动变为 clean，再重跑本脚本即可继续同步。" -ForegroundColor Cyan
    } else {
        Write-Host "   若这些改动是你想保留的在办工作，请先自行 commit 或 stash，再重跑本脚本。" -ForegroundColor DarkYellow
        Write-Host "   若确认这些改动已过时（比如被更早一次 stash 又写回来了），可以：" -ForegroundColor DarkYellow
        Write-Host "     git checkout -- <文件>   （单个文件放弃改动）" -ForegroundColor DarkGray
    }
    Write-Host "   本脚本不会替你决定，到此暂停。" -ForegroundColor DarkYellow
    exit 1
}
Write-Host "   ✓ 工作区干净" -ForegroundColor Green

# ── 3. fetch + 检查落后情况 ──
Write-Host "[3/5] git fetch origin..." -ForegroundColor Yellow
git fetch origin
$behind = git rev-list --count "HEAD..origin/master"
$ahead  = git rev-list --count "origin/master..HEAD"
Write-Host "   本地 master 落后 origin/master $behind 个提交，领先 $ahead 个" -ForegroundColor DarkGray

if ($behind -eq 0) {
    Write-Host "   ✓ 已是最新，无需拉取" -ForegroundColor Green
} elseif ($ahead -gt 0) {
    Write-Host "   ✗ 本地有 origin 没有的提交（$ahead 个），不是简单落后场景，--ff-only 会失败。" -ForegroundColor Red
    Write-Host "     这种情况需要人工判断（rebase/merge），本脚本不处理，已中止。" -ForegroundColor Red
    exit 1
} else {
    # ── 4. fast-forward 拉取 ──
    Write-Host "[4/5] git pull --ff-only..." -ForegroundColor Yellow
    git pull --ff-only
    Write-Host "   ✓ 已同步到最新" -ForegroundColor Green
}

# ── 5. stash 提示（不自动 drop）──
Write-Host "[5/5] 检查遗留 stash..." -ForegroundColor Yellow
$stashes = git stash list
if ($stashes) {
    Write-Host "   发现以下 stash：" -ForegroundColor DarkYellow
    $stashes | ForEach-Object { Write-Host "     $_" -ForegroundColor DarkYellow }
    Write-Host "`n   查看内容确认是否已过时（内容应已体现在刚同步的 master 里）：" -ForegroundColor Cyan
    Write-Host "     git stash show -p stash@{0}" -ForegroundColor DarkGray
    Write-Host "   确认无用后手动删除：" -ForegroundColor Cyan
    Write-Host "     git stash drop stash@{0}" -ForegroundColor DarkGray
    Write-Host "   （本脚本不会替你自动删，这是不可逆操作，需要你自己确认）" -ForegroundColor DarkYellow
} else {
    Write-Host "   ✓ 无遗留 stash" -ForegroundColor Green
}

Write-Host "`n完成。" -ForegroundColor Cyan
