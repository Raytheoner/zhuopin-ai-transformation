# 合入链路留痕 —— `工具-待合分支巡检.ps1` 与 `工具-泳道分支合入.ps1` 共用的落盘函数（队列 §一 `#571` ⑹⑺，OP-0913-E 并入，2026-09-13）。
#
# 🔴 成因：合入链路的机器把活干了，却没把结论留给下一个人。`OP-0913-E` 当日实证三次——配套支
#    `claude/op0913f-v2-launcher-json-571` 08:34、09:18 各被 rebase 一次、至今未合，而 `reports/` 下本轮
#    零日志；`claude/op0913g-align-proc-freshness-570` 08:34:26 已 ff 进 master，它那行 09:3x 仍留在
#    `pending-ff.jsonl`。看护者三次都只能靠 `git reflog` ＋进程表反推——**反推一次就是一次人守**。
#    🔑 判据一句：一个只把结论写进「某条会话」的机器，对其它会话等于没跑过。
#
# 两件产出（形态照抄 `reports/ff-whitelist-autoff.log` 的「每次处置追加一条」，只是改成 jsonl 便于机器读）：
#   ⑹ `<登记册目录>/ff-patrol-<yyyyMMdd>.jsonl`：巡检与合入各自把**每次处置**追加一行——分支、各关通过与否、
#      ④ 两侧失败集合、最终动作（合入／拒绝／被打断）。两个脚本各写各的（`actor` 字段区分），同一次合入
#      会留两行：合入脚本那行是它自己的六关明细，巡检那行是「我调了它、它回了什么退出码」。
#   ⑺ `<登记册目录>/pending-ff.done-<yyyyMMdd>.jsonl`：登记册收尾销行——「已是 master 祖先」／「分支已不存在」／
#      「本轮合入」的行从 `pending-ff.jsonl` 迁走并附销行原因，使 `pending-ff.jsonl` 恒等于「真待合清单」。
#      🔴 迁走不是删——原行字段（含他的授权原文）原样保留，只追加 `done_at`／`done_reason`／`master_sha`。
#
# 🔴 登记册目录＝`1-转型规划/0-全景路线图/合入登记/`（`OP-0913-L`，2026-09-13，Shao Peishen 答「第一环就按你的
#    设计安排」）。原落点 `reports/` 被 `.gitignore` `**/reports/` 整棵忽略、`git ls-files reports` ＝ 0，即
#    🟡 人工 ff 授权原文的唯一载体不入版本控制——当日实证 `reports/pending-ff.jsonl` 09:46–09:55 间整个文件
#    无痕消失（取证件-2026-09-13-ff登记册无痕消失）。目录级 `**/reports/` 对否定式免疫（git 不下探被排除的目录），
#    唯一出路是把正本搬出来、在 `**/*.jsonl` 之后加目录级否定（同 `.gitignore` 口径点台账先例，例外不递归）。
#    三个文件名形态（`pending-ff.jsonl`／`pending-ff.done-*`／`ff-patrol-*`）只有目录变了，字段与行为不变。
#    🔴 路径只从 `Get-FfLedgerDir` 取，三个脚本不得各自再拼一遍。
#
# 🔴 落盘函数一律不抛：留痕失败只 `Write-Host` 一行警告，不能让「写不进日志」反过来把合入本身拦下
#    （留痕是给下一个人看的副产品，主产品是合入判定；两者失败模式不许耦合）。
#
# 时间一律本地（UTC+8）ISO 8601 带偏移（`2026-09-13T09:41:07+08:00`），字段名 `ts`，读者不必再猜基准。

$script:FfLedgerDirRel = '1-转型规划\0-全景路线图\合入登记'

function Get-FfLedgerDir {
    <# 登记册目录：`<Repo>/1-转型规划/0-全景路线图/合入登记`——`pending-ff.jsonl`／done／ff-patrol 三类文件的唯一落点。
       🔴 不建子目录（`.gitignore` 例外不递归，子目录内 .jsonl 会被静默忽略）。 #>
    param([Parameter(Mandatory)][string]$Repo)
    return (Join-Path $Repo $script:FfLedgerDirRel)
}

function Get-PendingFfRegistryPath {
    <# 「已授权待合」登记册：`<登记册目录>/pending-ff.jsonl`——恒等于「真待合清单」。 #>
    param([Parameter(Mandatory)][string]$Repo)
    return (Join-Path (Get-FfLedgerDir -Repo $Repo) 'pending-ff.jsonl')
}

function Get-FfPatrolTracePath {
    <# ⑹ 留痕文件路径：`<登记册目录>/ff-patrol-<yyyyMMdd>.jsonl`，按本地日期分文件。 #>
    param([Parameter(Mandatory)][string]$Repo, [datetime]$Now = (Get-Date))
    return (Join-Path (Get-FfLedgerDir -Repo $Repo) ('ff-patrol-' + $Now.ToString('yyyyMMdd') + '.jsonl'))
}

function Get-PendingFfDonePath {
    <# ⑺ 销行落点：`<登记册目录>/pending-ff.done-<yyyyMMdd>.jsonl`（该命名 09-12／09-13 已各有一份手工件，沿用）。 #>
    param([Parameter(Mandatory)][string]$Repo, [datetime]$Now = (Get-Date))
    return (Join-Path (Get-FfLedgerDir -Repo $Repo) ('pending-ff.done-' + $Now.ToString('yyyyMMdd') + '.jsonl'))
}

function Get-LocalIsoNow {
    param([datetime]$Now = (Get-Date))
    return ([datetimeoffset]$Now).ToString('yyyy-MM-ddTHH:mm:sszzz')
}

function Add-JsonlLine {
    <# 追加一行紧凑 JSON（UTF-8 无 BOM，`\n` 结尾）。目录不存在即建。失败返回原因字符串、不抛。 #>
    param([Parameter(Mandatory)][string]$Path, [Parameter(Mandatory)]$Object)
    try {
        $dir = Split-Path $Path -Parent
        if ($dir -and -not (Test-Path $dir)) { New-Item -ItemType Directory -Path $dir -Force | Out-Null }
        $json = $Object | ConvertTo-Json -Depth 8 -Compress
        # 🔴 不用 `Add-Content -Encoding UTF8`：Windows PowerShell 5.1 下它会写 BOM，jsonl 逐行读会把
        #    第一行的 `{` 前多出 U+FEFF；`File.AppendAllText` 配无 BOM 编码两版 pwsh 行为一致。
        [System.IO.File]::AppendAllText($Path, $json + "`n", (New-Object System.Text.UTF8Encoding $false))
        return $null
    } catch { return $_.Exception.Message }
}

function Write-FfPatrolTrace {
    <#
    .SYNOPSIS
        ⑹ 追加一条处置记录到当日 `ff-patrol-<yyyyMMdd>.jsonl`。
    .PARAMETER Actor
        `巡检`（工具-待合分支巡检.ps1）或 `合入`（工具-泳道分支合入.ps1）——两个脚本各写各的。
    .PARAMETER Branch
        分支名。
    .PARAMETER Action
        最终动作，取值固定：`合入`／`拒绝`／`被打断`／`跳过`／`销行`（🔴 `-DryRun` 不留痕，没有「干跑」这一档）。
        - 合入：ff 已进 master；
        - 拒绝：某道守卫说「不」（脏文件交集、回归新增失败、白名单不命中、无授权原文）——判定成立、动作不做；
        - 被打断：流程没能走到判定（rebase 冲突停在冲突态、ff 失败、四 ref 不一致、脚本异常、子进程非零退出）；
        - 跳过：本轮不处理（前置未满足等下一轮、超窗口）；销行：登记册行迁 done。
    .PARAMETER Gates
        各关结果，哈希表 `@{ '①备份ref'=$true; '②脏文件零交集'=$false; … }`——键名带序号，读者对着脚本注释就能对上。
    .PARAMETER FailedBranch / FailedMaster
        ④ 两侧失败集合（用例名数组）。没跑回归即空数组，`tests` 字段写空串。
    .PARAMETER Extra
        其它字段（退出码、master 前后 sha、授权原文摘要、备注……）直接并进顶层。
    #>
    param(
        [Parameter(Mandatory)][string]$Repo,
        [Parameter(Mandatory)][ValidateSet('巡检', '合入')][string]$Actor,
        [Parameter(Mandatory)][string]$Branch,
        [Parameter(Mandatory)][ValidateSet('合入', '拒绝', '被打断', '跳过', '销行')][string]$Action,
        [hashtable]$Gates = @{},
        [string[]]$FailedBranch = @(),
        [string[]]$FailedMaster = @(),
        [hashtable]$Extra = @{},
        [datetime]$Now = (Get-Date)
    )
    # 🔴 用有序字典而不是 `[pscustomobject]@{}`：hashtable 字面量的键序不稳定，jsonl 逐行 diff 时会假抖。
    $rec = [ordered]@{
        ts            = Get-LocalIsoNow -Now $Now
        actor         = $Actor
        branch        = $Branch
        action        = $Action
        gates         = [ordered]@{}
        failed_branch = @($FailedBranch)
        failed_master = @($FailedMaster)
    }
    foreach ($k in ($Gates.Keys | Sort-Object)) { $rec.gates[$k] = $Gates[$k] }
    foreach ($k in ($Extra.Keys | Sort-Object)) { if (-not $rec.Contains($k)) { $rec[$k] = $Extra[$k] } }
    $path = Get-FfPatrolTracePath -Repo $Repo -Now $Now
    $err = Add-JsonlLine -Path $path -Object $rec
    if ($err) { Write-Host "⚠ 留痕未写入 $path（$err）——不影响合入判定本身" }
    return $path
}

function Add-PendingFfDoneRow {
    <#
    .SYNOPSIS
        ⑺ 把登记册的一行（原始 JSON 文本）迁进当日 `pending-ff.done-<yyyyMMdd>.jsonl`，附销行原因。
    .PARAMETER RawLine
        `pending-ff.jsonl` 里的原行文本；解析失败时原样以 `raw` 字段保存，不丢。
    .PARAMETER Reason
        `已是 master 祖先`／`分支已不存在`／`本轮合入`。
    #>
    param(
        [Parameter(Mandatory)][string]$Repo,
        [Parameter(Mandatory)][string]$RawLine,
        [Parameter(Mandatory)][ValidateSet('已是 master 祖先', '分支已不存在', '本轮合入')][string]$Reason,
        [string]$MasterSha = '',
        [datetime]$Now = (Get-Date)
    )
    $rec = [ordered]@{}
    try {
        $e = $RawLine | ConvertFrom-Json
        foreach ($p in $e.PSObject.Properties) { $rec[$p.Name] = $p.Value }
    } catch { $rec['raw'] = $RawLine }
    $rec['done_at'] = Get-LocalIsoNow -Now $Now
    $rec['done_reason'] = $Reason
    $rec['master_sha'] = $MasterSha
    $path = Get-PendingFfDonePath -Repo $Repo -Now $Now
    $err = Add-JsonlLine -Path $path -Object $rec
    if ($err) { Write-Host "⚠ 销行记录未写入 $path（$err）" }
    return $path
}

function Invoke-PendingFfRegistrySweep {
    <#
    .SYNOPSIS
        ⑺ 登记册收尾销行：把 `pending-ff.jsonl` 里「分支已不存在」或「已是 master 祖先」的行迁进当日 done 文件，
        其余原样保留（含解析失败的行——它们由动作一自己报）。幂等：跑两次第二次零动作。
    .OUTPUTS
        `[pscustomobject]@{ Moved = @(分支名…); Kept = 保留行数; DonePath = 落点 }`；登记册不存在／为空 ⇒ Moved 空。
    .NOTES
        🔴 只销「机器能自证」的两种；不碰无授权原文的行、不碰前置未满足的行——那是动作一的事，本函数不代判。
        🔴 `-DryRun` 只报不写（登记册与 done 文件都不动）。
    #>
    param(
        [Parameter(Mandatory)][string]$Repo,
        [Parameter(Mandatory)][string]$RegistryPath,
        [string]$Base = 'master',
        [switch]$DryRun,
        [datetime]$Now = (Get-Date)
    )
    $moved = @(); $kept = @()
    $donePath = Get-PendingFfDonePath -Repo $Repo -Now $Now
    if (-not (Test-Path $RegistryPath)) {
        return [pscustomobject]@{ Moved = @(); Kept = 0; DonePath = $donePath }
    }
    $lines = @(Get-Content $RegistryPath -Encoding UTF8 | Where-Object { $_.Trim() })
    $masterSha = (git -C $Repo rev-parse $Base 2>$null)
    foreach ($line in $lines) {
        $e = $null
        try { $e = $line | ConvertFrom-Json } catch { $kept += $line; continue }
        $br = [string]$e.branch
        if (-not $br) { $kept += $line; continue }
        $reason = $null
        git -C $Repo show-ref --verify --quiet "refs/heads/$br"
        if ($LASTEXITCODE -ne 0) {
            $reason = '分支已不存在'
        } else {
            git -C $Repo merge-base --is-ancestor $br $Base 2>$null
            if ($LASTEXITCODE -eq 0) { $reason = '已是 master 祖先' }
        }
        if (-not $reason) { $kept += $line; continue }
        $moved += [pscustomobject]@{ Branch = $br; Reason = $reason }
        if (-not $DryRun) {
            Add-PendingFfDoneRow -Repo $Repo -RawLine $line -Reason $reason -MasterSha $masterSha -Now $Now | Out-Null
            Write-FfPatrolTrace -Repo $Repo -Actor '巡检' -Branch $br -Action '销行' `
                -Extra @{ reason = $reason; master_sha = $masterSha; registry = (Split-Path $RegistryPath -Leaf) } -Now $Now | Out-Null
        }
    }
    if (-not $DryRun -and $moved.Count -gt 0) {
        if ($kept.Count -gt 0) {
            [System.IO.File]::WriteAllText($RegistryPath, (($kept -join "`n") + "`n"), (New-Object System.Text.UTF8Encoding $false))
        } else {
            Remove-Item $RegistryPath -Force
        }
    }
    return [pscustomobject]@{ Moved = @($moved); Kept = $kept.Count; DonePath = $donePath }
}
