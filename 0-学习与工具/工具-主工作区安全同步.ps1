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
    Write-Host "   若这些改动是你想保留的在办工作，请先自行 commit 或 stash，再重跑本脚本。" -ForegroundColor DarkYellow
    Write-Host "   若确认这些改动已过时（比如被更早一次 stash 又写回来了），可以：" -ForegroundColor DarkYellow
    Write-Host "     git checkout -- <文件>   （单个文件放弃改动）" -ForegroundColor DarkGray
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
