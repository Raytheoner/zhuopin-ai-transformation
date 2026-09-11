# 待合分支巡检 —— 把「等条件满足后再 ff」从人守转机器守。
#
# 🔴 成因（Shao Peishen 2026-09-11 当场指出）：本方说「sweep 落库后你说一句我再 ff」，
#    他反问「为何必须要我说一句？就又加了一条人为判断，就会出错」。**他是对的**：
#    `UPS5:7` 给的是两个触发器（他的下一句话 / 一条能当场指名的机器规则），本方挑了差的；
#    而同日他刚立的 `UPS5:6` 收窄一档写死——**唯二可交给他的动作＝可复制粘贴的命令行、
#    以及必须提权的 shell**。「请你记着来说一句」两者都不是。
#
# 本脚本即那条机器规则：读「已授权待合」登记处，逐条检查前置是否已满足，
# 满足即调 `工具-泳道分支合入.ps1`（六道守卫，任一不过非零退出），成功后销登记。
#
# 🔴 它不放松 D1 🟡 档：**授权仍须他先给**，登记处里必须有他的授权原文；
#    本脚本只负责「他已经答过的事，不要再问第二遍」。没有授权记录的分支一律不碰。
#
# 用法：pwsh -File 工具-待合分支巡检.ps1 [-DryRun]
param([switch]$DryRun)

$ErrorActionPreference = 'Stop'
$Repo = 'C:\Dev\zhuopin-ai'
Set-Location $Repo
$Reg = Join-Path $Repo 'reports\pending-ff.jsonl'
$Merge = Join-Path $Repo '0-学习与工具\工具-泳道分支合入.ps1'

if (-not (Test-Path $Reg)) { Write-Host '[NO-PENDING] 无待合登记。'; exit 0 }
$lines = Get-Content $Reg -Encoding UTF8 | Where-Object { $_.Trim() }
if (-not $lines) { Write-Host '[NO-PENDING] 登记处为空。'; exit 0 }

git fetch --quiet
$dirty = git status --porcelain | ForEach-Object { $_.Substring(3).Trim('"') }
$kept = @(); $done = @(); $blocked = @()

foreach ($line in $lines) {
    try { $e = $line | ConvertFrom-Json } catch { Write-Host "⚠ 登记行解析失败，原样保留：$line"; $kept += $line; continue }
    $br = $e.branch

    git show-ref --verify --quiet "refs/heads/$br"
    if ($LASTEXITCODE -ne 0) { Write-Host "· $br 分支已不存在，销登记"; continue }

    # 已经并进 master 了 ⇒ 销登记，不重复做
    git merge-base --is-ancestor $br master 2>$null
    if ($LASTEXITCODE -eq 0) { Write-Host "· $br 内容已在 master，销登记"; continue }

    # 🔴 授权是硬前置：没有他的原文就不碰
    if (-not $e.authorized_text) { Write-Host "⚠ $br 无授权原文，跳过（本脚本绝不代授权）"; $kept += $line; continue }

    # 前置：该分支触碰的文件在主仓不得有未提交改动（ff 会覆盖）
    $touched = git show --name-only --format='' $br | Where-Object { $_ }
    $x = $touched | Where-Object { $dirty -contains $_ }
    if ($x) {
        Write-Host "⏳ $br 前置未满足：与脏文件交集 $($x -join ', ')"
        $blocked += "$br ← $($x -join ', ')"; $kept += $line; continue
    }

    if ($DryRun) { Write-Host "[DRY] $br 前置已满足，本可合入（未执行）"; $kept += $line; continue }

    Write-Host "▶ $br 前置已满足，按授权合入（授权原文：$($e.authorized_text)）"
    $args = @('-NoProfile', '-File', $Merge, '-Branch', $br)
    if ($e.tests) { $args += @('-Tests', $e.tests) }
    & pwsh @args
    if ($LASTEXITCODE -eq 0) { Write-Host "✅ $br 已合入"; $done += $br }
    else { Write-Host "🔴 $br 合入失败（退出码 $LASTEXITCODE），保留登记待人看"; $kept += $line }
}

if (-not $DryRun) {
    if ($kept) { Set-Content -Path $Reg -Value $kept -Encoding UTF8 } else { Remove-Item $Reg -Force }
}

if ($done) { Write-Host "[MERGED] $($done -join '; ')" }
elseif ($blocked) { Write-Host "[WAITING] $($blocked -join ' ｜ ')" }
else { Write-Host '[NO-ACTION] 本轮无可合入项。' }
