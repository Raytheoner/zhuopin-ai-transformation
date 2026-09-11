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
# ============================================================
# 队列 §一 #560（2026-09-11）：worktree「收工自删」机器守 —— 动作二
# ============================================================
# 🔴 成因：opener 骨架每次都写「worktree：☑（…新 worktree，收工自删）」，但从没有任何
#    机器真的去删——`git worktree list` 只增不减。`OP-0910-H` 实测（2026-09-11）：53 个
#    worktree，其中 `agent-*`（Task/Agent 子泳道留下的）29 个，22 个的分支内容早已合入
#    master 仍占着盘（`.claude/worktrees` 当时 125,738 文件／1.66 GB，外加 42 个常驻
#    `git fsmonitor--daemon` 进程）。当日手工逐个 `git worktree remove`（不加 `--force`）：
#    删掉 14 个、被 git 自己拒掉 8 个（含未提交改动／未跟踪产出，如 `reply_form_detect.py`）。
#
# 🔑 **上方「动作一」管的是『已被登记且获他授权』的分支 ff 入 master；本段管的是
#    『不管走哪条路径并入了 master、事后留在盘上没人删』的那个 worktree 空壳**——
#    两者判据同源（`git merge-base --is-ancestor`）但对象不同，`工具-泳道分支合入.ps1`
#    步骤⑥清的是它自己在 `C:\Dev\_rb-<短名>` 建的临时 rebase worktree（`--force`，
#    因为那是它自己造的、内容早已在 `$Branch` 里有第二份），**从不碰**会话真正
#    工作过的那个 `.claude/worktrees/<name>`——这正是本段要补的空。
#
# 判据（🔴 不新造第二套，全部复用既有口径）：
#   ⑴ 只看 `.claude/worktrees/` 之下的 worktree（建造 worktree 固定落点，同
#      `工具-落库sweep.py::WORKTREES_DIR_REL`）——主工作区与其他路径（如常驻服务
#      `ops/wecom-service-home`）不在本段管辖内；
#   ⑵ 排除**常驻执行体**——任一本机计划任务 Action 指向该 worktree 即跳过（判据同
#      `工具-落库sweep.py::_resident_carriers`：常驻执行体靠 ff 续命、不归"删"管）；
#      🔴 **计划任务查询失败 ⇒ 保守跳过本段整轮**，不代表「零常驻执行体」（同
#      `_query_scheduled_task_actions` 的「查不到≠没有」判据）；
#   ⑶ **判「已合入」只用 `git merge-base --is-ancestor <worktree HEAD> master`**——
#      与本文件「动作一」判分支是否已并入同一把尺子；
#   ⑷ **闲置缓冲 `-IdleBufferMinutes`（默认 60）**——worktree 的 git 管理目录
#      （`.git/worktrees/<name>`，而非整棵工作树，避免对着上千文件的大树递归 stat）
#      最近一次被 git 动过若晚于缓冲窗口，判「可能仍在被一条活跃会话使用」，本轮跳过、
#      下一轮再看。🔴 **这不是判据⑶之外的第二套合入判据，只是把『刚合入、原会话可能
#      还没退出』这一类假阳性挡在窗口内**——`git worktree remove` 本身不认识"正在被
#      用"，只认识"脏不脏"，而一个刚 fresh-branch（HEAD＝master、尚无任何改动）的活跃
#      会话此刻恰好"干净"，缓冲窗口是对这一空子的补丁；
#   ⑸ 满足 ⑴⑵⑶⑷ 才尝试 `git worktree remove`（🔴 **永不加 `--force`**）——git 自己会
#      在有未提交改动或未跟踪内容时非零退出，这正是我们要的「脏的只告警、不删」；
#      remove 失败只记一行警告并点名，**不重试、不强删、不代查是谁在用**。
#
# 用法：pwsh -File 工具-待合分支巡检.ps1 [-DryRun] [-IdleBufferMinutes 60]
param([switch]$DryRun, [int]$IdleBufferMinutes = 60)

$ErrorActionPreference = 'Stop'
$Repo = 'C:\Dev\zhuopin-ai'
Set-Location $Repo
$Reg = Join-Path $Repo 'reports\pending-ff.jsonl'
$Merge = Join-Path $Repo '0-学习与工具\工具-泳道分支合入.ps1'

# ── 动作一：已授权待合分支 → ff 入 master（原有逻辑，判据与行为均未改） ──
if (-not (Test-Path $Reg)) {
    Write-Host '[NO-PENDING] 无待合登记。'
} else {
    $lines = Get-Content $Reg -Encoding UTF8 | Where-Object { $_.Trim() }
    if (-not $lines) {
        Write-Host '[NO-PENDING] 登记处为空。'
    } else {
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
    }
}

# ── 动作二：worktree「收工自删」机器守（队列 §一 #560） ──────────────────

function Get-ScheduledTaskWorktreeNames {
    <# 返回一个大小写不敏感的 HashSet<string>：所有被本机计划任务 Action 引用的
       `.claude/worktrees/<name>` 名字（判据同 `工具-落库sweep.py::_resident_carriers`）。
       🔴 查询失败返回 `$null`——与「查到、且为空集合」是两件相反的事，调用方必须分开
       处理、不得把前者当成后者（同 `_query_scheduled_task_actions` 的「查不到≠没有」）。 #>
    param([Parameter(Mandatory)][string]$WorktreesRootNormalized)
    # 🔴 `Get-ScheduledTask` 实测偶发瞬时失败（本机验证：约每 10 次调用 1 次，无固定
    #    诱因，猜测 CIM 会话抖动）——重试两次、中间让一小段时间再判「真失败」，避免
    #    每轮巡检因一次瞬时抖动就整段空跑（同 `工具-落库sweep.py::_query_scheduled_
    #    task_actions` 的「查询失败要有韧性，不能一次不顺就判定没有」）。
    $tasks = $null
    for ($attempt = 1; $attempt -le 3; $attempt++) {
        try { $tasks = Get-ScheduledTask -ErrorAction Stop; break }
        catch {
            if ($attempt -eq 3) { return $null }
            Start-Sleep -Milliseconds 500
        }
    }
    $names = New-Object 'System.Collections.Generic.HashSet[string]' ([StringComparer]::OrdinalIgnoreCase)
    $prefix = $WorktreesRootNormalized.ToLowerInvariant() + '/'
    foreach ($t in $tasks) {
        foreach ($a in $t.Actions) {
            $raw = ("$($a.Execute) $($a.Arguments)" -replace '\\', '/')
            $idx = $raw.ToLowerInvariant().IndexOf($prefix)
            if ($idx -lt 0) { continue }
            $tail = $raw.Substring($idx + $prefix.Length)
            $name = ($tail -split '/', 2)[0].Trim('"', "'")
            if ($name) { [void]$names.Add($name) }
        }
    }
    # 🔴 必须 `,$names`（一元逗号）——`return $names` 会被 PowerShell 当集合展开进管道：
    #    0 个元素展开成 `$null`（与「查询失败」撞车）、1 个元素展开成裸字符串（类型错、
    #    `.Contains` 语义也变了）。本机实测撞过：测试仓库下无任何计划任务命中时，
    #    调用方拿到的是 `$null`，被误判成「计划任务查询失败」而整段跳过。
    return ,$names
}

function Get-WorktreeEntries {
    <# 解析 `git worktree list --porcelain`，返回 `[{Path, Head}]`。只取 HEAD 的 commit
       祖先关系判「已合入」，不看 `branch`/`detached` 行——两种形态都不影响该判据。
       🔴 判 worktree 身份只认这份注册项，不对任意路径另跑 `git -C`——同
       `工具-落库sweep.py::_registered_worktrees` 那条注释：对非注册目录跑 `git -C`，
       git 会静默向上找到主工作区并回答主工作区自己的状态，照抄会把「该清的空壳」
       误记成「干净、无需处理」。 #>
    param([Parameter(Mandatory)][string]$Repo)
    $raw = git -C $Repo worktree list --porcelain
    $out = @(); $cur = $null
    foreach ($line in $raw) {
        if ($line -like 'worktree *') {
            if ($cur) { $out += [pscustomobject]$cur }
            $cur = @{ Path = ($line.Substring(9).Trim() -replace '\\', '/'); Head = $null }
        } elseif ($cur -and $line -like 'HEAD *') {
            $cur.Head = $line.Substring(5).Trim()
        }
    }
    if ($cur) { $out += [pscustomobject]$cur }
    # 🔴 同上：`,$out` 防止单条 worktree 时被展开成裸对象（同一枚坑，两处都要堵）。
    return ,$out
}

function Test-WorktreeRecentlyTouched {
    <# `.git/worktrees/<name>` 管理目录（不是整棵工作树）最近一次被 git 动过是否在
       `$IdleBufferMinutes` 缓冲窗口内。找不到管理目录 ⇒ 保守判"最近有动"（取不到就
       不删，同 `_rev_count` 失败返回 None 而非 0 的取舍方向）。 #>
    param(
        [Parameter(Mandatory)][string]$Repo,
        [Parameter(Mandatory)][string]$Name,
        [Parameter(Mandatory)][int]$IdleBufferMinutes
    )
    $adminDir = Join-Path $Repo ".git\worktrees\$Name"
    if (-not (Test-Path $adminDir)) { return $true }
    $newest = Get-ChildItem -Path $adminDir -File -Force -ErrorAction SilentlyContinue |
        Measure-Object -Property LastWriteTime -Maximum
    if (-not $newest.Maximum) { return $true }
    return ((Get-Date) - $newest.Maximum).TotalMinutes -lt $IdleBufferMinutes
}

function Invoke-MergedWorktreeAutoRemove {
    param(
        [Parameter(Mandatory)][string]$Repo,
        [switch]$DryRun,
        [int]$IdleBufferMinutes = 60
    )

    $entries = Get-WorktreeEntries -Repo $Repo
    if (-not $entries) { Write-Host '[WT-NONE] git worktree list 无返回。'; return }
    # 🔴 主工作区路径以 git 自己在 `worktree list` 里报的第一条为准，不用传入的 `$Repo`
    #    字符串重新拼——两者在 8.3 短路径／大小写／盘符形式上可能不字节相同（本机测试
    #    环境下 `C:\Users\PAULSH~1\...` vs git 报的 `C:/Users/Paul Shao/...` 就撞过一次，
    #    导致主工作区排除与 `.claude/worktrees` 前缀匹配全部落空、误判「无可清理」）。
    $repoNorm = $entries[0].Path
    $wtRoot = "$repoNorm/.claude/worktrees"

    $carrierNames = Get-ScheduledTaskWorktreeNames -WorktreesRootNormalized $wtRoot
    if ($null -eq $carrierNames) {
        Write-Host '[WT-SKIP] 计划任务查询失败，本轮不做 worktree 自删（保守起见，不代表零常驻执行体）。'
        return
    }

    $removed = @(); $blocked = @(); $skippedCarrier = @(); $skippedRecent = @()
    foreach ($e in $entries) {
        $p = $e.Path
        if ($p.ToLowerInvariant() -eq $repoNorm.ToLowerInvariant()) { continue }                       # 主工作区，不碰
        if (-not $p.ToLowerInvariant().StartsWith("$wtRoot/".ToLowerInvariant())) { continue }         # 不在 .claude/worktrees 下，不归本段管

        $name = $p.Substring($wtRoot.Length + 1)
        if ($carrierNames.Contains($name)) { $skippedCarrier += $name; continue }
        if (-not $e.Head) { continue }

        git -C $Repo merge-base --is-ancestor $e.Head master 2>$null
        if ($LASTEXITCODE -ne 0) { continue }   # 未合入，不是本段该管的（走上方「动作一」）

        if (Test-WorktreeRecentlyTouched -Repo $Repo -Name $name -IdleBufferMinutes $IdleBufferMinutes) {
            $skippedRecent += $name; continue
        }

        if ($DryRun) {
            $short = $e.Head.Substring(0, [Math]::Min(8, $e.Head.Length))
            Write-Host "[DRY] $name（$short）已合入 master 且过了闲置缓冲，本可 remove（未执行）"
            continue
        }

        $out = git -C $Repo worktree remove $p 2>&1
        if ($LASTEXITCODE -eq 0) {
            Write-Host "✅ $name 已合入且干净，已 remove"
            $removed += $name
        } else {
            Write-Host "⏳ $name 已合入但 remove 被拒（多半有未提交/未跟踪内容，未强删）：$out"
            $blocked += $name
        }
    }

    if ($skippedCarrier) { Write-Host "· 常驻执行体（计划任务在引用，跳过）：$($skippedCarrier -join '; ')" }
    if ($skippedRecent) { Write-Host "· 已合入但在闲置缓冲 ${IdleBufferMinutes} 分钟内被动过，本轮先不删：$($skippedRecent -join '; ')" }
    if ($removed) { Write-Host "[WT-REMOVED] $($removed -join '; ')" }
    if ($blocked) { Write-Host "[WT-BLOCKED] $($blocked -join '; ')" }
    if (-not $removed -and -not $blocked) { Write-Host '[WT-NO-ACTION] 本轮无可清理 worktree。' }
}

Invoke-MergedWorktreeAutoRemove -Repo $Repo -DryRun:$DryRun -IdleBufferMinutes $IdleBufferMinutes

# 🔴 显式收尾退出码——本脚本的状态一律读 stdout 的 `[…]` 标记（同 `poll-opener-batch`
#    skill 的既有约定：`[NO-SIGNAL]/[NO-ACTION] 即空跑结束`，读文字不读 errorlevel）。
#    脚本内部大量 `git merge-base --is-ancestor`（判"未合入"时故意非零退出）都不代表
#    脚本本身失败，但若不显式收尾，进程退出码会悄悄继承最后一条原生命令的 $LASTEXITCODE，
#    让任何以退出码判成败的调用方假阳性报错。真异常已在 `$ErrorActionPreference='Stop'`
#    下变成终止性错误、根本到不了这一行。
exit 0
