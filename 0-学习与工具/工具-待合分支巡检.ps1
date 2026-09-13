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
# ============================================================
# 队列 §一 #571 ⑹⑺（2026-09-13，OP-0913-E 并入）：合入链路留痕 ＋ 登记册收尾销行
# ============================================================
# 🔴 成因：机器把 rebase／ff 做了，结论只留在某条会话的 stdout 里——对其它会话等于没跑过，
#    看护者只能靠 `git reflog` ＋进程表反推（反推一次就是一次人守）。
#   ⑹ 本脚本每处置一条分支（白名单命中／不命中／脏文件交集／干跑／调合入脚本得到退出码／销行）
#      都在 `<登记册目录>/ff-patrol-<yyyyMMdd>.jsonl` 追加一行；合入脚本自己另写它的六关明细行，两行
#      以 `actor` 区分（巡检／合入）。落盘函数正本在 `工具-合入链路留痕.ps1`。
#   ⑺ 动作一开头先做登记册收尾销行：「分支已不存在」「已是 master 祖先」的行迁进
#      `<登记册目录>/pending-ff.done-<yyyyMMdd>.jsonl`（附 done_reason／master_sha），本轮合入成功的行
#      同样迁走（done_reason=本轮合入）——`pending-ff.jsonl` 从此恒等于「真待合清单」。
#   🔴 登记册目录＝`1-转型规划/0-全景路线图/合入登记/`（`OP-0913-L`，2026-09-13）：原 `reports/` 被 gitignore
#      整棵忽略，🟡 授权原文的唯一载体不入库、当日已无痕消失过一次；路径只从 `Get-FfLedgerDir` 取。
#   `-Repo`／`-TempRoot` 只为单测指向临时仓库而设，默认值即生产值。
#
# 用法：pwsh -File 工具-待合分支巡检.ps1 [-DryRun] [-IdleBufferMinutes 60] [-NoAutoWhitelist] [-WhitelistMaxAgeDays 14] [-Repo <仓库根>] [-TempRoot <临时 worktree 父目录>]
#       pwsh -File 工具-待合分支巡检.ps1 -EvaluateBranch <ref> [-EvaluateBase master]   # 只干跑白名单判据，不合入
param(
    [string]$Repo = 'C:\Dev\zhuopin-ai',
    [string]$TempRoot = 'C:\Dev',
    [switch]$DryRun,
    [int]$IdleBufferMinutes = 60,
    [switch]$NoAutoWhitelist,          # 动作〇 总开关之一（另一个＝标记文件 reports/ff-whitelist.OFF）
    [int]$WhitelistMaxAgeDays = 14,    # 动作〇 候选窗口：只看最近 N 天内有提交的 claude/* 分支
    [string]$EvaluateBranch = '',      # 只评估这一条 ref 的白名单判据并退出（干跑）
    [string]$EvaluateBase = 'master'
)

$ErrorActionPreference = 'Stop'
Set-Location $Repo
# 🔴 合入脚本按本脚本所在目录找（不是按 $Repo 拼）——单测把 -Repo 指到临时仓库时，脚本本体仍在源码目录。
$Merge = Join-Path $PSScriptRoot '工具-泳道分支合入.ps1'
. (Join-Path $PSScriptRoot '工具-合入链路留痕.ps1')
# 登记册路径只从留痕库取（`OP-0913-L`：正本已从被 gitignore 整棵忽略的 reports/ 迁到 1-转型规划/0-全景路线图/合入登记/）。
$Reg = Get-PendingFfRegistryPath -Repo $Repo

function Resolve-MergeExitAction {
    <# 合入脚本退出码 → 本脚本留痕动作（与 `工具-泳道分支合入.ps1::Resolve-MergeAction` 同一张表）：
       0 合入；2 脏文件交集／4 回归新增失败＝拒绝；其余（3 rebase 冲突／5 ff 失败／6 四 ref 不一致／9 异常）＝被打断。 #>
    param([int]$Code)
    switch ($Code) { 0 { '合入' } 2 { '拒绝' } 4 { '拒绝' } default { '被打断' } }
}

function Write-PatrolTrace {
    <# 本脚本的留痕入口（actor 固定＝巡检）。🔴 `-DryRun` 一律不留痕——同白名单审计日志「干跑只看 stdout」：
       干跑什么都没做，也就没有「结论」可留给下一个人。 #>
    param(
        [Parameter(Mandatory)][string]$Branch,
        [Parameter(Mandatory)][string]$Action,
        [hashtable]$Gates = @{},
        [hashtable]$Extra = @{}
    )
    if ($DryRun) { return }
    Write-FfPatrolTrace -Repo $Repo -Actor '巡检' -Branch $Branch -Action $Action -Gates $Gates -Extra $Extra | Out-Null
}

function Get-TodayWhitelistMissKeys {
    <# 当日留痕里已记过的「白名单不命中」键集合（`分支|分支sha`）。白名单候选常年几十条、每轮都不命中，
       若每轮都追加一行，一天就是上千行噪声；同一 sha 的同一结论只记一次，分支一有新提交再记。 #>
    $set = New-Object 'System.Collections.Generic.HashSet[string]'
    $path = Get-FfPatrolTracePath -Repo $Repo
    if (-not (Test-Path $path)) { return ,$set }
    foreach ($line in (Get-Content $path -Encoding UTF8 | Where-Object { $_.Trim() })) {
        try { $r = $line | ConvertFrom-Json } catch { continue }
        if ($r.actor -eq '巡检' -and $r.action -eq '拒绝' -and $r.path -eq '白名单' -and $r.branch_sha) {
            [void]$set.Add("$($r.branch)|$($r.branch_sha)")
        }
    }
    return ,$set
}

function Invoke-MergeScript {
    <# 调 `工具-泳道分支合入.ps1` 并返回退出码；参数原样透传 -Repo／-TempRoot，使单测与生产走同一条路。 #>
    param([Parameter(Mandatory)][string]$Branch, [string]$Tests = '')
    $a = @('-NoProfile', '-File', $Merge, '-Branch', $Branch, '-Repo', $Repo, '-TempRoot', $TempRoot)
    if ($Tests) { $a += @('-Tests', $Tests) }
    # 🔴 子进程 stdout 经 Write-Host 走宿主流（仍逐行实时回显），不能漏进本函数输出流——否则返回值变成数组、
    #    `[int]` 转换即炸（单测实撞）。`$LASTEXITCODE` 取的是 pwsh 子进程自己的退出码，与管道末端无关。
    & pwsh @a | ForEach-Object { Write-Host $_ }
    return [int]$LASTEXITCODE
}

# ============================================================
# 动作〇：ff 低风险白名单 —— 「纯文档分支也要问一次」的机器那一半
# （派单件 `1-转型规划/0-全景路线图/派单件-【CC】ff低风险白名单-2026-09-12.md`，
#   Shao Peishen 2026-09-12 答 `3b`，OP-0912-E，批 B-0912_落库瘦身）
# ============================================================
# 🔴 成因：WIP 降不下来的主因是「待 ff」堆积——`OP-0912-E` 取证：计入 WIP 的行里 `partial`
#    占 54%，抽样 16 条里尾巴就是「待 ff」的 4 条；同日 sweep 第 16 类 B 类真未落地分支 15 条。
#    泳道产分支的速度远大于 ff 的速度，因为**每条分支都要单独问他一次**。他的原话「我是看护者，
#    永远在环，只做审核和决策」⇒ 要改的不是「他审」，是「逐条问」这个形态。
#
# 判据正本在 `工具-待合分支巡检-白名单判据.ps1`（⑴ 全部文件在允许集合 ／ ⑵ 零代码文件 ／
# ⑶ 不触碰队列·CLAUDE.md·.claude/**·.gitignore ／ ⑷ merge-tree 零冲突 ／ ⑸ 取不到即不命中）。
# 🔴 fail-closed：任一不满足即回到「等他一字母」（动作一那条路径），本段一律不碰。
#
# 候选集（本段自己的前置过滤，不是第六条判据，只把明显不该碰的分支挡在门外）：
#   · 只看本地 `refs/heads/claude/*`（泳道分支固定前缀；`backup/*`／`ops/*` 不在内）；
#   · 内容尚未在 master（`git merge-base --is-ancestor` 非零）；
#   · 🔴 不在『已授权待合』登记处（那条路径有他的原文授权，不与本条混用——派单件 §二）；
#   · 🔴 未被任何 worktree 检出（活跃泳道还在上面提交；且 `工具-泳道分支合入.ps1` 步骤③
#     `git worktree add` 对已检出分支会失败）；
#   · 最近一次提交在 `-WhitelistMaxAgeDays`（默认 14）天内——更老的分支多半是被放弃的草稿或
#     已被别的分支承接，自动复活它们不是「低风险」；它们照旧留在动作一那侧等他一字母。
#
# 合入仍调 `工具-泳道分支合入.ps1`（六道守卫一条不改；docs 分支无测试目标 ⇒ 不传 `-Tests`、
# 日志写明「跳过回归」——白名单 ⑵ 已保证零代码文件，没有可回归之物），**不新造第二条合入路径**。
#
# 留痕与可撤销：
#   · 每条命中分支的判据 ⑴–⑸ 逐条结果写 stdout ＋ 追加 `reports/ff-whitelist-autoff.log`；
#   · 本轮有实际合入／失败 ⇒ 汇总一条推运维群（`.env` 的 `WECOM_WEBHOOK_URL_OPS`；未配置即只落
#     日志、不回落业务群，同 `工具-泳道看护状态机.py` 的 fail-closed 取向）；
#   · 🔴 总开关两种，任一即关停：参数 `-NoAutoWhitelist`；或存在标记文件 `reports/ff-whitelist.OFF`
#     （他一句话，本方 `New-Item reports/ff-whitelist.OFF` 即关；删除即开）。
#
# 干跑单条 ref 的判据（不合入、不写日志）：
#   pwsh -File 工具-待合分支巡检.ps1 -EvaluateBranch <ref> [-EvaluateBase <ref>]

. (Join-Path $PSScriptRoot '工具-待合分支巡检-白名单判据.ps1')

$WlOffMarker = Join-Path $Repo 'reports\ff-whitelist.OFF'
$WlAuditLog = Join-Path $Repo 'reports\ff-whitelist-autoff.log'
$WlOpsWebhookKey = 'WECOM_WEBHOOK_URL_OPS'

function Send-OpsWecomMarkdown {
    <# 推一条 markdown 到运维群。成功返回 `$null`，失败返回原因字符串（调用方只记日志，不抛）。
       🔴 键名带 `=` 精确前缀匹配——`WECOM_WEBHOOK_URL` 是 `WECOM_WEBHOOK_URL_OPS` 的真前缀，
       不带 `=` 会把两键读混、把汇总发回业务群（`test_工具-落库sweep.py` 记过这一坑）。 #>
    param([Parameter(Mandatory)][string]$Repo, [Parameter(Mandatory)][string]$Content)
    $envPath = Join-Path $Repo '.env'
    if (-not (Test-Path $envPath)) { return "未找到 $envPath" }
    $prefix = "$WlOpsWebhookKey="
    $line = Get-Content $envPath -Encoding UTF8 | Where-Object { $_.Trim().StartsWith($prefix) } | Select-Object -First 1
    if (-not $line) { return ".env 未配置 $WlOpsWebhookKey（fail-closed，不回落业务群）" }
    $url = $line.Trim().Substring($prefix.Length).Trim().Trim('"', "'")
    if (-not $url) { return "$WlOpsWebhookKey 为空" }
    $body = @{ msgtype = 'markdown'; markdown = @{ content = $Content } } | ConvertTo-Json -Depth 4 -Compress
    try {
        $r = Invoke-RestMethod -Method Post -Uri $url -ContentType 'application/json; charset=utf-8' `
            -Body ([System.Text.Encoding]::UTF8.GetBytes($body)) -TimeoutSec 10
        if ($r.errcode -ne 0) { return "errcode=$($r.errcode) errmsg=$($r.errmsg)" }
        return $null
    } catch { return "推送异常：$($_.Exception.Message)" }
}

function Get-RegisteredPendingBranches {
    <# 『已授权待合』登记处里的分支名集合（解析失败的行跳过——它们由动作一自己报）。 #>
    param([Parameter(Mandatory)][string]$RegistryPath)
    $set = New-Object 'System.Collections.Generic.HashSet[string]'
    if (-not (Test-Path $RegistryPath)) { return ,$set }
    foreach ($line in (Get-Content $RegistryPath -Encoding UTF8 | Where-Object { $_.Trim() })) {
        try { $e = $line | ConvertFrom-Json; if ($e.branch) { [void]$set.Add([string]$e.branch) } } catch { }
    }
    return ,$set
}

function Get-CheckedOutBranches {
    <# 所有 worktree 当前检出的分支名集合（`git worktree list --porcelain` 的 `branch refs/heads/<name>` 行）。 #>
    param([Parameter(Mandatory)][string]$Repo)
    $set = New-Object 'System.Collections.Generic.HashSet[string]'
    foreach ($line in (git -C $Repo worktree list --porcelain)) {
        if ($line -like 'branch refs/heads/*') { [void]$set.Add($line.Substring(18).Trim()) }
    }
    return ,$set
}

function Invoke-WhitelistAutoFf {
    param(
        [Parameter(Mandatory)][string]$Repo,
        [Parameter(Mandatory)][string]$RegistryPath,
        [Parameter(Mandatory)][string]$MergeScript,
        [switch]$DryRun,
        [int]$MaxAgeDays = 14
    )
    $stamp = Get-Date -Format 'yyyy-MM-dd HH:mm:ss'   # 本地时间（UTC+8），日志里统一标「本地」
    $registered = Get-RegisteredPendingBranches -RegistryPath $RegistryPath
    $checkedOut = Get-CheckedOutBranches -Repo $Repo
    $cutoff = (Get-Date).AddDays(-$MaxAgeDays)

    $refs = @(git -C $Repo for-each-ref --format='%(refname:short)|%(committerdate:iso-strict)' refs/heads/claude/)
    $candidates = @(); $skipped = @{ merged = 0; registered = 0; checkedOut = 0; old = 0 }
    foreach ($r in $refs) {
        $parts = $r -split '\|', 2
        $br = $parts[0].Trim(); if (-not $br) { continue }
        $when = $null; try { $when = [datetimeoffset]::Parse($parts[1]) } catch { }
        if ($null -eq $when -or $when.LocalDateTime -lt $cutoff) { $skipped.old++; continue }
        if ($registered.Contains($br)) { $skipped.registered++; continue }
        if ($checkedOut.Contains($br)) { $skipped.checkedOut++; continue }
        git -C $Repo merge-base --is-ancestor $br master 2>$null
        if ($LASTEXITCODE -eq 0) { $skipped.merged++; continue }
        $candidates += $br
    }
    Write-Host "· 白名单候选 $($candidates.Count) 条（claude/* 共 $($refs.Count)；跳过：已在 master $($skipped.merged)／已登记待合 $($skipped.registered)／被 worktree 检出 $($skipped.checkedOut)／超 $MaxAgeDays 天或无日期 $($skipped.old)）"
    if (-not $candidates) { Write-Host '[WL-NO-ACTION] 无白名单候选。'; return }

    $dirty = git -C $Repo status --porcelain | ForEach-Object { $_.Substring(3).Trim('"') }
    $done = @(); $failed = @(); $waiting = @(); $notHit = @(); $audit = @(); $dryHits = @()
    $missLogged = Get-TodayWhitelistMissKeys

    foreach ($br in $candidates) {
        $v = Test-FfWhitelist -Repo $Repo -Branch $br -Base master
        $lines = @(Format-FfWhitelistVerdict -Verdict $v)
        $wlGates = @{}
        foreach ($c in $v.Checks) { $wlGates["白名单$($c.Id)"] = [bool]$c.Ok }
        if (-not $v.Hit) {
            $why = @($v.Checks | Where-Object { -not $_.Ok } | ForEach-Object { "$($_.Id) $($_.Detail)" }) -join '；'
            Write-Host "⛔ $br 不命中白名单，留在「等他一字母」：$why"
            $sha = (git -C $Repo rev-parse --short $br 2>$null)
            if (-not $missLogged.Contains("$br|$sha")) {
                Write-PatrolTrace -Branch $br -Action '拒绝' -Gates $wlGates `
                    -Extra @{ path = '白名单'; branch_sha = $sha; reason = "不命中白名单：$why" }
            }
            $notHit += $br; continue
        }
        $lines | ForEach-Object { Write-Host $_ }
        $audit += "[$stamp 本地] $($lines -join "`n")"

        $x = @($v.Files | Where-Object { $dirty -contains $_ })
        if ($x) {
            Write-Host "⏳ $br 命中白名单但前置未满足：与脏文件交集 $($x -join ', ')"
            Write-PatrolTrace -Branch $br -Action '跳过' -Gates $wlGates -Extra @{ path = '白名单'; reason = "脏文件交集：$($x -join ', ')" }
            $waiting += "$br ← $($x -join ', ')"; $audit += "    ⏳ 脏文件交集，本轮未合入：$($x -join ', ')"; continue
        }
        if ($DryRun) {
            Write-Host "[DRY] $br 命中白名单、前置已满足，本可自动 ff（未执行）"
            $dryHits += $br; continue
        }

        Write-Host "▶ $br 命中白名单，自动 ff（docs 分支无测试目标，跳过回归——⑵ 已保证零代码文件）"
        $code = Invoke-MergeScript -Branch $br
        $masterNow = (git -C $Repo rev-parse --short master)
        Write-PatrolTrace -Branch $br -Action (Resolve-MergeExitAction -Code $code) -Gates $wlGates `
            -Extra @{ path = '白名单'; merge_exit = $code; master_after = $masterNow; tests = '' }
        if ($code -eq 0) {
            Write-Host "✅ $br 已自动 ff（白名单）"; $done += $br; $audit += "    ✅ 已 ff，master → $masterNow"
        } else {
            Write-Host "🔴 $br 自动 ff 失败（工具-泳道分支合入.ps1 退出码 $code），留在「等他一字母」"
            $failed += "$br（退出码 $code）"; $audit += "    🔴 合入失败，退出码 $code"
        }
    }

    if ($audit -and -not $DryRun) {   # 干跑不落审计日志，只看 stdout
        $dir = Split-Path $WlAuditLog -Parent
        if (-not (Test-Path $dir)) { New-Item -ItemType Directory -Path $dir -Force | Out-Null }
        Add-Content -Path $WlAuditLog -Value ($audit -join "`n") -Encoding UTF8
    }

    if (-not $DryRun -and ($done -or $failed)) {
        $msg = @("🌿 待合分支巡检：**白名单自动 ff**（$stamp 本地；判据逐条见 reports/ff-whitelist-autoff.log）")
        if ($done) { $msg += "✅ 已合入 $($done.Count) 条："; $done | ForEach-Object { $msg += "    · $_" } }
        if ($failed) { $msg += "🔴 合入失败（留在等他一字母）：$($failed -join '；')" }
        if ($waiting) { $msg += "⏳ 命中但脏文件交集：$($waiting -join '；')" }
        $msg += '关停：New-Item reports/ff-whitelist.OFF（或加 -NoAutoWhitelist）。'
        $err = Send-OpsWecomMarkdown -Repo $Repo -Content ($msg -join "`n")
        if ($err) { Write-Host "⚠ 运维群汇总未推出（$err），仅落日志 $WlAuditLog" } else { Write-Host '· 运维群汇总已推送' }
    }

    if ($notHit) { Write-Host "· 不命中白名单 $($notHit.Count) 条（照旧等他一字母）" }
    if ($done) { Write-Host "[WL-MERGED] $($done -join '; ')" }
    if ($failed) { Write-Host "[WL-FAILED] $($failed -join '; ')" }
    if ($waiting) { Write-Host "[WL-WAITING] $($waiting -join ' ｜ ')" }
    if ($dryHits) { Write-Host "[WL-DRY] $($dryHits.Count) 条命中且前置已满足，本可自动 ff：$($dryHits -join '; ')" }
    elseif (-not $done -and -not $failed -and -not $waiting) { Write-Host '[WL-NO-ACTION] 本轮白名单无可合入项。' }
}

if ($EvaluateBranch) {
    $v = Test-FfWhitelist -Repo $Repo -Branch $EvaluateBranch -Base $EvaluateBase
    Format-FfWhitelistVerdict -Verdict $v | ForEach-Object { Write-Host $_ }
    Write-Host ($(if ($v.Hit) { '[WL-EVAL-HIT]' } else { '[WL-EVAL-MISS]' }))
    exit 0
}

if ($NoAutoWhitelist) {
    Write-Host '[WL-OFF] 白名单自动 ff 已关停（参数 -NoAutoWhitelist）。'
} elseif (Test-Path $WlOffMarker) {
    Write-Host "[WL-OFF] 白名单自动 ff 已关停（存在标记文件 $WlOffMarker，删除即恢复）。"
} else {
    Invoke-WhitelistAutoFf -Repo $Repo -RegistryPath $Reg -MergeScript $Merge -DryRun:$DryRun -MaxAgeDays $WhitelistMaxAgeDays
}

# ── 动作一：已授权待合分支 → ff 入 master（判据未改；#571 ⑹⑺ 加留痕与销行） ──
# ⑺ 登记册收尾销行：先把「分支已不存在」「已是 master 祖先」的行迁进 done 文件，再读真待合清单。
$sweep = Invoke-PendingFfRegistrySweep -Repo $Repo -RegistryPath $Reg -DryRun:$DryRun
if ($sweep.Moved.Count -gt 0) {
    $sweep.Moved | ForEach-Object { Write-Host "· $($_.Branch) $($_.Reason)，$(if ($DryRun) { '[DRY] 本可销行' } else { '已销行' })" }
    if (-not $DryRun) { Write-Host "[PENDING-SWEPT] $($sweep.Moved.Count) 行 → $($sweep.DonePath)" }
}
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

            # 「分支已不存在」「已是 master 祖先」两类正常已被上方 ⑺ sweep 迁走；这里只在 -DryRun（sweep 不写）
            # 或两次读之间状态变化时兜底，行为与 sweep 同（销行留痕，不静默丢）。
            git show-ref --verify --quiet "refs/heads/$br"
            if ($LASTEXITCODE -ne 0) {
                Write-Host "· $br 分支已不存在，销登记"
                if (-not $DryRun) { Add-PendingFfDoneRow -Repo $Repo -RawLine $line -Reason '分支已不存在' | Out-Null }
                continue
            }
            git merge-base --is-ancestor $br master 2>$null
            if ($LASTEXITCODE -eq 0) {
                Write-Host "· $br 内容已在 master，销登记"
                if (-not $DryRun) { Add-PendingFfDoneRow -Repo $Repo -RawLine $line -Reason '已是 master 祖先' -MasterSha (git rev-parse master) | Out-Null }
                continue
            }

            # 🔴 授权是硬前置：没有他的原文就不碰
            if (-not $e.authorized_text) {
                Write-Host "⚠ $br 无授权原文，跳过（本脚本绝不代授权）"
                Write-PatrolTrace -Branch $br -Action '拒绝' -Gates @{ '授权原文' = $false } -Extra @{ path = '登记册'; reason = '无授权原文，本脚本绝不代授权' }
                $kept += $line; continue
            }

            # 前置：该分支触碰的文件在主仓不得有未提交改动（ff 会覆盖）
            $touched = git show --name-only --format='' $br | Where-Object { $_ }
            $x = $touched | Where-Object { $dirty -contains $_ }
            if ($x) {
                Write-Host "⏳ $br 前置未满足：与脏文件交集 $($x -join ', ')"
                Write-PatrolTrace -Branch $br -Action '跳过' -Gates @{ '授权原文' = $true; '脏文件零交集' = $false } -Extra @{ path = '登记册'; reason = "脏文件交集：$($x -join ', ')" }
                $blocked += "$br ← $($x -join ', ')"; $kept += $line; continue
            }

            if ($DryRun) { Write-Host "[DRY] $br 前置已满足，本可合入（未执行）"; $kept += $line; continue }

            Write-Host "▶ $br 前置已满足，按授权合入（授权原文：$($e.authorized_text)）"
            $code = Invoke-MergeScript -Branch $br -Tests ([string]$e.tests)
            $masterNow = (git rev-parse master)
            Write-PatrolTrace -Branch $br -Action (Resolve-MergeExitAction -Code $code) `
                -Gates @{ '授权原文' = $true; '脏文件零交集' = $true } `
                -Extra @{ path = '登记册'; merge_exit = $code; tests = [string]$e.tests; master_after = $masterNow.Substring(0, 7)
                          authorized_text = [string]$e.authorized_text }
            if ($code -eq 0) {
                Write-Host "✅ $br 已合入"; $done += $br
                Add-PendingFfDoneRow -Repo $Repo -RawLine $line -Reason '本轮合入' -MasterSha $masterNow | Out-Null
            }
            else { Write-Host "🔴 $br 合入失败（退出码 $code），保留登记待人看"; $kept += $line }
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
