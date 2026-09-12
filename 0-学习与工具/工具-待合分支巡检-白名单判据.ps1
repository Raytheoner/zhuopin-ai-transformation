# ff 低风险白名单判据 —— 从 `工具-待合分支巡检.ps1` 抽出的纯判据函数，供单测与 `-EvaluateBranch` 干跑复用。
#
# 派单件：`1-转型规划/0-全景路线图/派单件-【CC】ff低风险白名单-2026-09-12.md`（Shao Peishen 2026-09-12 答 `3b`，OP-0912-E）。
# 🔴 由来：WIP 降不下来的主因是「待 ff」堆积——每条泳道分支都要单独问他一次。他的原话
#    「我是看护者，永远在环，只做审核和决策」⇒ 要改的不是「他审」，是「逐条问」这个形态。
#    本文件只消灭「纯文档分支也要问一次」；**触碰代码／队列／纪律载体的分支照旧停等他一字母**。
#
# 判据（🔴 fail-closed：任一不满足、或任一项取不到 ⇒ 判非白名单，回到「等他一字母」）：
#   ⑴ 该分支相对 base 的 `git diff --name-only <base>...<branch>` 全部文件都在允许集合内：
#      任意路径的 `*.md`；`openspec/**` 下的非可执行文件（可执行＝⑵ 的扩展名表）。
#      派单件另列的 `1-转型规划/**`、`3-治理与合规/**`、`6-人才与组织/**` 的 `.md` 已被「任意路径 `*.md`」覆盖。
#   ⑵ 零可执行／代码文件：`.py .ps1 .psm1 .psd1 .js .ts .bat .cmd .sh .yaml .yml .json`
#      （🔴 `.json` 一律不算低风险——配置与台账都是它；`.psd1` 为本方按同一理由补入，只收紧不放松）。
#   ⑶ 不触碰纪律与门禁载体：两份队列真身（`1-转型规划/0-全景路线图/跨桌任务队列*.md`）、
#      任意层级的 `CLAUDE.md`、`.claude/**`（派单件写的是 `.claude/rules/**` 与 `.claude/settings*.json`，
#      本方收紧到整个 `.claude/`——hooks／skills／agents 同样是门禁载体）、`.gitignore`／`.gitattributes`。
#   ⑷ `git merge-tree --write-tree <base> <branch>` 零冲突（rebase 后能否纯 ff 由 `工具-泳道分支合入.ps1` 步骤③ 实做，
#      冲突即退出码 3，巡检侧只记「合入失败」不重试）。
#   ⑸ 任一判据命令失败／ref 解析不出／差异文件列表为空 ⇒ 判非白名单。
#
# 🔴 允许集合是白名单（allow-list），⑵⑶ 是叠在其上的显式黑名单——一个文件必须同时「在允许集合内」
#    且「不在任何黑名单内」才算通过；`.txt`／`.png`／`.docx` 等既不在允许集合也不在黑名单的文件同样不通过。
#    这样新出现的扩展名默认落在「等他一字母」那侧，而不是默认放行。

$script:FfWhitelistCodeExtensions = @(
    '.py', '.ps1', '.psm1', '.psd1', '.js', '.ts', '.bat', '.cmd', '.sh', '.yaml', '.yml', '.json'
)

function Get-FfWhitelistFileVerdict {
    <#
    .SYNOPSIS
        对单个仓库相对路径做 ⑴⑵⑶ 判定，返回 `[pscustomobject]{ Path; Allowed; Rule; Reason }`。
        `Rule` ∈ 'allow' | 'code' | 'carrier' | 'outside'：分别对应「通过」「⑵ 命中代码扩展名」
        「⑶ 命中纪律载体」「⑴ 不在允许集合」。纯函数，不碰 git，不碰文件系统。
    #>
    param([Parameter(Mandatory)][string]$Path)
    $p = ($Path -replace '\\', '/').Trim().TrimStart('/')
    $lower = $p.ToLowerInvariant()
    $name = ($lower -split '/')[-1]
    $ext = [System.IO.Path]::GetExtension($name)

    # ⑶ 纪律与门禁载体（先判，理由要写成「载体」而非「不在允许集合」，日志才可读）
    if ($lower -like '1-转型规划/0-全景路线图/跨桌任务队列*.md') {
        return [pscustomobject]@{ Path = $p; Allowed = $false; Rule = 'carrier'; Reason = '⑶ 队列真身' }
    }
    if ($name -eq 'claude.md') {
        return [pscustomobject]@{ Path = $p; Allowed = $false; Rule = 'carrier'; Reason = '⑶ CLAUDE.md' }
    }
    if ($lower -like '.claude/*' -or $lower -like '*/.claude/*') {
        return [pscustomobject]@{ Path = $p; Allowed = $false; Rule = 'carrier'; Reason = '⑶ .claude/**' }
    }
    if ($name -eq '.gitignore' -or $name -eq '.gitattributes') {
        return [pscustomobject]@{ Path = $p; Allowed = $false; Rule = 'carrier'; Reason = "⑶ $name" }
    }

    # ⑵ 可执行／代码扩展名
    if ($script:FfWhitelistCodeExtensions -contains $ext) {
        return [pscustomobject]@{ Path = $p; Allowed = $false; Rule = 'code'; Reason = "⑵ 代码扩展名 $ext" }
    }

    # ⑴ 允许集合
    if ($ext -eq '.md') {
        return [pscustomobject]@{ Path = $p; Allowed = $true; Rule = 'allow'; Reason = '⑴ *.md' }
    }
    if ($lower -like 'openspec/*') {
        return [pscustomobject]@{ Path = $p; Allowed = $true; Rule = 'allow'; Reason = '⑴ openspec/** 非可执行文件' }
    }
    return [pscustomobject]@{ Path = $p; Allowed = $false; Rule = 'outside'; Reason = "⑴ 不在允许集合（$ext）" }
}

function Test-FfWhitelist {
    <#
    .SYNOPSIS
        对 `<Branch>` 相对 `<Base>` 做白名单判定。返回
        `[pscustomobject]{ Branch; Base; Hit; Files; Checks }`，其中 `Checks` 是五条 `{ Id; Ok; Detail }`
        （Id ∈ '⑴','⑵','⑶','⑷','⑸'），供日志逐条写明。
        🔴 fail-closed：任何 git 命令非零退出、ref 解析不出、差异文件为空 ⇒ `Hit=$false` 且 ⑸ `Ok=$false`。
    #>
    param(
        [Parameter(Mandatory)][string]$Repo,
        [Parameter(Mandatory)][string]$Branch,
        [string]$Base = 'master'
    )
    $checks = [ordered]@{}
    foreach ($id in '⑴', '⑵', '⑶', '⑷', '⑸') { $checks[$id] = [pscustomobject]@{ Id = $id; Ok = $false; Detail = '未评估' } }
    $files = @()

    function _fail([string]$detail) {
        $checks['⑸'].Ok = $false; $checks['⑸'].Detail = $detail
        return [pscustomobject]@{
            Branch = $Branch; Base = $Base; Hit = $false; Files = @($files)
            Checks = @($checks['⑴'], $checks['⑵'], $checks['⑶'], $checks['⑷'], $checks['⑸'])
        }
    }

    # ref 解析（⑸）
    foreach ($ref in @($Base, $Branch)) {
        $null = git -C $Repo rev-parse --verify --quiet "$ref^{commit}" 2>$null
        if ($LASTEXITCODE -ne 0) { return (_fail "ref 解析不出：$ref") }
    }

    # 差异文件（⑴⑵⑶ 的输入）
    # 🔴 `-c core.quotepath=false`：默认 git 会把含中文的路径写成 `"1-è½¬..."` 八进制转义，
    #    判据按字面比对 `跨桌任务队列`／`CLAUDE.md` 会全部落空、把该拦的当成「不在允许集合」以外的东西——
    #    虽仍是不命中（fail-closed），但日志给不出真实路径，单测里的临时仓库也正是这样撞出来的。
    $raw = @(git -C $Repo -c core.quotepath=false diff --name-only "$Base...$Branch" 2>$null)
    if ($LASTEXITCODE -ne 0) { return (_fail "git diff --name-only $Base...$Branch 非零退出 $LASTEXITCODE") }
    $files = @($raw | Where-Object { $_ -and $_.Trim() } | ForEach-Object { $_.Trim() })
    if ($files.Count -eq 0) { return (_fail "差异文件为空（内容已在 $Base 或分支无改动），无可 ff 之物") }

    # 日志里文件清单最多列 5 个（大代码分支一条能拖出上百个路径，读不了；完整清单在 `Files`）
    function _list($items) {
        $paths = @($items | ForEach-Object { $_ })
        if ($paths.Count -le 5) { return ($paths -join ', ') }
        return (($paths[0..4] -join ', ') + "…等 $($paths.Count) 个")
    }
    $verdicts = @($files | ForEach-Object { Get-FfWhitelistFileVerdict -Path $_ })
    $outside = @($verdicts | Where-Object { $_.Rule -eq 'outside' })
    $code = @($verdicts | Where-Object { $_.Rule -eq 'code' })
    $carrier = @($verdicts | Where-Object { $_.Rule -eq 'carrier' })

    $checks['⑴'].Ok = ($outside.Count -eq 0 -and $code.Count -eq 0 -and $carrier.Count -eq 0)
    $checks['⑴'].Detail = if ($checks['⑴'].Ok) { "$($files.Count) 个文件全部在允许集合" }
        elseif ($outside.Count -gt 0) { "不在允许集合：$(_list ($outside | ForEach-Object { $_.Path }))" }
        else { '被 ⑵/⑶ 拦下（见下）' }
    $checks['⑵'].Ok = ($code.Count -eq 0)
    $checks['⑵'].Detail = if ($checks['⑵'].Ok) { '零代码／可执行文件' }
        else { "代码文件：$(_list ($code | ForEach-Object { $_.Path }))" }
    $checks['⑶'].Ok = ($carrier.Count -eq 0)
    $checks['⑶'].Detail = if ($checks['⑶'].Ok) { '未触碰队列／CLAUDE.md／.claude/**／.gitignore' }
        else { "纪律载体：$(_list ($carrier | ForEach-Object { "$($_.Path)（$($_.Reason)）" }))" }

    # ⑷ merge-tree 零冲突（git ≥ 2.38；退出码 0 无冲突、1 有冲突、其它＝命令失败⇒⑸）
    $null = git -C $Repo merge-tree --write-tree $Base $Branch 2>$null
    $mt = $LASTEXITCODE
    if ($mt -eq 0) { $checks['⑷'].Ok = $true; $checks['⑷'].Detail = "merge-tree --write-tree $Base $Branch 零冲突" }
    elseif ($mt -eq 1) { $checks['⑷'].Ok = $false; $checks['⑷'].Detail = "merge-tree 报冲突（退出码 1）" }
    else { return (_fail "git merge-tree 非零退出 $mt（非 0/1，命令本身失败）") }

    $checks['⑸'].Ok = $true; $checks['⑸'].Detail = '判据命令全部成功取到值'
    $hit = ($checks['⑴'].Ok -and $checks['⑵'].Ok -and $checks['⑶'].Ok -and $checks['⑷'].Ok -and $checks['⑸'].Ok)
    return [pscustomobject]@{
        Branch = $Branch; Base = $Base; Hit = $hit; Files = @($files)
        Checks = @($checks['⑴'], $checks['⑵'], $checks['⑶'], $checks['⑷'], $checks['⑸'])
    }
}

function Format-FfWhitelistVerdict {
    <# 把 `Test-FfWhitelist` 的结果排成日志行（数组），每条判据一行，供 stdout 与审计日志共用。 #>
    param([Parameter(Mandatory)]$Verdict)
    $head = if ($Verdict.Hit) { '✅ 命中白名单' } else { '⛔ 不命中白名单（回到「等他一字母」）' }
    $lines = @("$head：$($Verdict.Branch) → $($Verdict.Base)，差异文件 $($Verdict.Files.Count) 个")
    foreach ($c in $Verdict.Checks) {
        $mark = if ($c.Ok) { '✓' } else { '✗' }
        $lines += "    $($c.Id) $mark $($c.Detail)"
    }
    return $lines
}
