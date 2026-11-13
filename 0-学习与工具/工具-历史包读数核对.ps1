# 历史包读数核对：只接受 ZHUOPIN_PACKAGE_EVIDENCE_JSON 的显式 JSON 证据。
# 版本与引号解析算法保留；不探测旧安装、不读旧配置、不启动 CLI、不重启服务。
# 原始全文在 docs/codex/retired-evidence/工具-Claude包版本探针.ps1.txt。
param(
    [switch]$Json,
    [switch]$BannerLine,
    [switch]$Quiet
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
try { [Console]::OutputEncoding = [Text.UTF8Encoding]::new($false) } catch { }

# ── 常量 ──────────────────────────────────────────────────────────────────────
$WindowsAppsRoot = Join-Path $env:ProgramFiles 'WindowsApps'
$ServiceName     = 'CoworkVMService'
# `Claude_1.46388.4.0_x64__pzs8sxrjxfjjc` 里的版本段；2–4 段数字都收，MSIX 允许四段。
$VersionInName   = 'Claude_(\d+(?:\.\d+){1,3})_'

# 🔴 提示语正文与队列 `#486` 行内原话保持一致，改这句前先改队列行，别两处分叉。
$RemedyText = '先跑提权 Restart-Service CoworkVMService -Force，勿直接开长会话'


# ── 小工具 ────────────────────────────────────────────────────────────────────

function ConvertTo-VersionOrNull {
    <# 把 "1.46388.4.0" 转成 [version]；转不动返回 $null（不抛，读不出来是常态之一）。#>
    param([string]$Text)
    if ([string]::IsNullOrWhiteSpace($Text)) { return $null }
    $v = $null
    if ([version]::TryParse($Text.Trim(), [ref]$v)) { return $v }
    return $null
}

function Get-VersionFromPackageName {
    <# 从 `Claude_<版本>_x64__<pfn>` 形态的名字或路径里抠出版本字符串；抠不到返回 ''。#>
    param([string]$Text)
    if ([string]::IsNullOrWhiteSpace($Text)) { return '' }
    $m = [regex]::Match($Text, $VersionInName)
    if ($m.Success) { return $m.Groups[1].Value }
    return ''
}

function Get-FakeInjection {
    <# 单测夹具：解析 `ZHUOPIN_PACKAGE_EVIDENCE_JSON`。未设或解析失败 ⇒ 返回 $null（走真读）。#>
    $raw = $env:ZHUOPIN_PACKAGE_EVIDENCE_JSON
    if ([string]::IsNullOrWhiteSpace($raw)) { return $null }
    try { return ($raw | ConvertFrom-Json) } catch { return $null }
}

function Test-HasProperty {
    <# StrictMode 下不能直接摸不存在的属性，统一走这个判定。#>
    param($Object, [string]$Name)
    if ($null -eq $Object) { return $false }
    return ($null -ne $Object.PSObject.Properties[$Name])
}


# ── 三处原始读数（每处都返回 @{ Ok; Value; Error }，读不到就如实说读不到）────────

function Read-RegisteredVersions {
    param($Fake)
    $r = [ordered]@{ Ok = $false; Value = @(); Error = '' }
    if ($null -ne $Fake) {
        if (-not (Test-HasProperty $Fake 'registered') -or $null -eq $Fake.registered) {
            $r.Error = '（夹具）已注册版本一处被置为读不出来'
            return $r
        }
        $r.Ok = $true; $r.Value = @($Fake.registered | ForEach-Object { [string]$_ })
        return $r
    }
    $r.Ok = $false; $r.Error = '只接受显式历史读数；旧默认来源已退役'
    return $r
}


function Read-ServicePathName {
    param($Fake)
    $r = [ordered]@{ Ok = $false; Value = ''; Error = '' }
    if ($null -ne $Fake) {
        if (-not (Test-HasProperty $Fake 'servicePathName') -or $null -eq $Fake.servicePathName) {
            $r.Error = "（夹具）$ServiceName 的 PathName 一处被置为读不出来"
            return $r
        }
        $r.Ok = $true; $r.Value = [string]$Fake.servicePathName
        return $r
    }
    $r.Ok = $false; $r.Error = '只接受显式历史读数；旧默认来源已退役'
    return $r
}


function Read-StagedDirNames {
    param($Fake)
    $r = [ordered]@{ Ok = $false; Value = @(); Error = '' }
    if ($null -ne $Fake) {
        if (-not (Test-HasProperty $Fake 'stagedDirs') -or $null -eq $Fake.stagedDirs) {
            $r.Error = '（夹具）WindowsApps 目录清单一处被置为读不出来'
            return $r
        }
        $r.Ok = $true; $r.Value = @($Fake.stagedDirs | ForEach-Object { [string]$_ })
        return $r
    }
    $r.Ok = $false; $r.Error = '只接受显式历史读数；旧默认来源已退役'
    return $r
}


function Read-ProjectDeclaredPlugins {
    <#
      读本项目 `.claude/settings.json` 的 `enabledPlugins`，取值为 true 的键（`<插件>@<市场>`）——
      这是「本项目声明要用」的插件清单，用来跟 `claude plugin list` 的实际启用态对照（队列 `#584` ⑷）。
      🔴 缺省语义见上方 `.NOTES`：夹具缺此键 ＝ 不关心（Ok=true 空清单，不进 errors）；
      键存在但为 null ＝ 模拟这一处读不出来。
    #>
    param($Fake)
    $r = [ordered]@{ Ok = $true; Value = @(); Error = '' }
    if ($null -ne $Fake -and (Test-HasProperty $Fake 'projectDeclaredPlugins')) {
        if ($null -eq $Fake.projectDeclaredPlugins) {
            $r.Ok = $false; $r.Error = '（夹具）项目声明插件清单一处被置为读不出来'
            return $r
        }
        $r.Value = @($Fake.projectDeclaredPlugins | ForEach-Object { [string]$_ })
        return $r
    }
    if ($null -ne $Fake) { return $r }
    $r.Ok = $false; $r.Error = '只接受显式历史读数；旧默认来源已退役'
    return $r
}


function Read-ClaudePluginList {
    <# 跑 `claude plugin list --json`，返回条目数组（每条含 `id`/`enabled`）。缺省语义同上一函数。#>
    param($Fake)
    $r = [ordered]@{ Ok = $true; Value = @(); Error = '' }
    if ($null -ne $Fake -and (Test-HasProperty $Fake 'pluginList')) {
        if ($null -eq $Fake.pluginList) {
            $r.Ok = $false; $r.Error = '（夹具）claude plugin list 一处被置为读不出来'
            return $r
        }
        $r.Value = @($Fake.pluginList)
        return $r
    }
    if ($null -ne $Fake) { return $r }
    $r.Ok = $false; $r.Error = '只接受显式历史读数；旧默认来源已退役'
    return $r
}


function Get-ClaudePackageVerdict {
    <#
      汇总三处读数出判定。返回一个 ordered 哈希（不是数组，避开 PowerShell 单元素展平坑）。
      verdict ∈ ok | pending-update | service-drift | plugin-disabled | unknown
      （多个同时成立时优先级：pending-update > service-drift > plugin-disabled，
        reasons 里全部命中的条目都在 —— 越靠前越急，但每一条都得让人看见。）
    #>
    param($Fake)

    $out = [ordered]@{
        verdict             = 'unknown'
        registeredVersion   = ''
        serviceVersion      = ''
        stagedVersions      = @()
        pendingVersions     = @()   # 高于已注册 ⇒ 待应用的更新（本探针的主信号）
        staleStagedVersions = @()   # 低于已注册 ⇒ 残留旧包，信息项，不触发提示
        servicePathName     = ''
        declaredPlugins     = @()   # 队列 #584 ⑷：项目 settings.json 声明启用的插件
        missingPlugins      = @()   # 声明了但 claude plugin list 里未见 enabled 的那些
        reasons             = @()
        errors              = @()
        remedy              = ''
    }

    $reg      = Read-RegisteredVersions      -Fake $Fake
    $svc      = Read-ServicePathName         -Fake $Fake
    $staged   = Read-StagedDirNames          -Fake $Fake
    $declared = Read-ProjectDeclaredPlugins  -Fake $Fake

    foreach ($src in @($reg, $svc, $staged, $declared)) {
        if (-not $src.Ok) { $out.errors = @($out.errors) + @($src.Error) }
    }
    $out.declaredPlugins = @($declared.Value)

    # 没声明插件、或声明清单本身读不出来 ⇒ 不必多起一次 `claude plugin list` 进程；
    # 声明清单读失败已经进了上面的 errors，没必要再问第二遍。
    $pluginListRead = $null
    if ($declared.Ok -and @($declared.Value).Count -gt 0) {
        $pluginListRead = Read-ClaudePluginList -Fake $Fake
        if (-not $pluginListRead.Ok) { $out.errors = @($out.errors) + @($pluginListRead.Error) }
    }

    # 已注册版本：正常只有一个；万一多个（同族多版本并存）取最高，并把这个反常写进 reasons。
    $regVer = $null
    if ($reg.Ok) {
        $parsed = @(@($reg.Value) | ForEach-Object { ConvertTo-VersionOrNull $_ } | Where-Object { $null -ne $_ })
        if ($parsed.Count -eq 0) {
            $out.errors = @($out.errors) + @("已注册版本解析不出来：$(@($reg.Value) -join ', ')")
        } else {
            $regVer = ($parsed | Sort-Object -Descending)[0]
            $out.registeredVersion = $regVer.ToString()
            if ($parsed.Count -gt 1) {
                $out.reasons = @($out.reasons) +
                    @("⚠ 同时有 $($parsed.Count) 个已注册 Claude 包（$(@($reg.Value) -join ', ')），按最高版本判定")
            }
        }
    }

    # 服务 PathName 里的包版本
    $svcVer = $null
    if ($svc.Ok) {
        $out.servicePathName = $svc.Value
        $svcVerText = Get-VersionFromPackageName $svc.Value
        if (-not $svcVerText) {
            $out.errors = @($out.errors) +
                @("$ServiceName 的 PathName 里抠不到 Claude 包版本：$($svc.Value)")
        } else {
            $svcVer = ConvertTo-VersionOrNull $svcVerText
            if ($null -eq $svcVer) {
                $out.errors = @($out.errors) + @("$ServiceName 的 PathName 版本段解析不出来：$svcVerText")
            } else {
                $out.serviceVersion = $svcVer.ToString()
            }
        }
    }

    # WindowsApps 下的暂存目录版本
    $stagedVers = @()
    if ($staged.Ok) {
        foreach ($name in @($staged.Value)) {
            $t = Get-VersionFromPackageName $name
            $v = ConvertTo-VersionOrNull $t
            if ($null -ne $v) { $stagedVers = @($stagedVers) + @($v) }
        }
        $stagedVers = @($stagedVers | Sort-Object -Unique)
        $out.stagedVersions = @($stagedVers | ForEach-Object { $_.ToString() })
        if (@($staged.Value).Count -gt 0 -and $stagedVers.Count -eq 0) {
            $out.errors = @($out.errors) +
                @("WindowsApps 下有 $(@($staged.Value).Count) 个 Claude_* 目录，但一个版本都解析不出来")
        }
    }

    # ── 三处任一没读到 ⇒ unknown，绝不因「没看见差异」而报 ok ──
    if (@($out.errors).Count -gt 0) {
        $out.verdict = 'unknown'
        $out.reasons = @($out.reasons) + @('⚠ 三处读数不完整，无法判定错位（读不到 ≠ 没有错位）')
        return $out
    }

    # 走到这里三处都读到了；$regVer 必非空（否则上面已进 errors）
    if ($null -ne $regVer -and $stagedVers.Count -gt 0) {
        $out.pendingVersions     = @($stagedVers | Where-Object { $_ -gt $regVer } | ForEach-Object { $_.ToString() })
        $out.staleStagedVersions = @($stagedVers | Where-Object { $_ -lt $regVer } | ForEach-Object { $_.ToString() })
    }

    $isPending = @($out.pendingVersions).Count -gt 0
    $isDrift   = ($null -ne $regVer -and $null -ne $svcVer -and $svcVer -ne $regVer)

    # 队列 #584 ⑷：声明启用但 `claude plugin list` 里查不到 enabled 记录的插件——
    # 只在真的跑过 plugin list 时判（$pluginListRead 为 $null ＝ 没声明插件、天然没有缺失项）。
    $missingPlugins = @()
    if ($null -ne $pluginListRead) {
        $enabledIds = @()
        foreach ($p in @($pluginListRead.Value)) {
            if ((Test-HasProperty $p 'id') -and (Test-HasProperty $p 'enabled') -and $p.enabled) {
                $enabledIds = @($enabledIds) + @([string]$p.id)
            }
        }
        $missingPlugins = @(@($declared.Value) | Where-Object { $enabledIds -notcontains $_ })
    }
    $out.missingPlugins = @($missingPlugins)
    $isPluginDisabled = @($missingPlugins).Count -gt 0

    if ($isPending) {
        $out.reasons = @($out.reasons) + @(
            ("🔴 已暂存未注册的**更高**版本：$(@($out.pendingVersions) -join ', ')（当前已注册 $($out.registeredVersion)）" +
             ' —— 强制注册（RegisterByPackageFamilyName ＋ ForceApplicationShutdownOption）随时会掐掉正在跑的 Claude，实测暂存到强关间隔 2–3 小时')
        )
    }
    if ($isDrift) {
        $out.reasons = @($out.reasons) + @(
            "🔴 $ServiceName 的 PathName 指向包版本 $($out.serviceVersion)，与已注册版本 $($out.registeredVersion) 不一致"
        )
    }
    $pluginRemedy = ''
    if ($isPluginDisabled) {
        $pluginRemedy = (@($missingPlugins) | ForEach-Object { "claude plugin install $_ --scope project -y" }) -join '；'
        $out.reasons = @($out.reasons) + @(
            "🔴 项目 .claude/settings.json 声明启用但 claude plugin list 里未见 enabled：$(@($missingPlugins) -join ', ') —— 修复：$pluginRemedy"
        )
    }

    if ($isPending) { $out.verdict = 'pending-update' }
    elseif ($isDrift) { $out.verdict = 'service-drift' }
    elseif ($isPluginDisabled) { $out.verdict = 'plugin-disabled' }
    else {
        $out.verdict = 'ok'
        $out.reasons = @($out.reasons) +
            @("✓ 已注册 / 服务 PathName 均为 $($out.registeredVersion)，无更高版本待注册")
    }

    if ($isPluginDisabled -and $out.verdict -eq 'plugin-disabled') { $out.remedy = $pluginRemedy }
    elseif ($out.verdict -ne 'ok') { $out.remedy = $RemedyText }

    if (@($out.staleStagedVersions).Count -gt 0) {
        $out.reasons = @($out.reasons) +
            @("ℹ WindowsApps 下另有 $(@($out.staleStagedVersions).Count) 个低于已注册版本的残留旧包（$(@($out.staleStagedVersions) -join ', ')）——" +
              '属垃圾残留，不触发提示，Restart-Service 对它们无作用')
    }

    return $out
}


# ── 呈现 ──────────────────────────────────────────────────────────────────────

function Format-BannerLine {
    <# 开场横幅那一行；ok 时返回 ''（正常态不加噪音，由调用方决定不打）。#>
    param($Verdict)
    switch ($Verdict.verdict) {
        'pending-update' {
            return ("📦 Claude 包版本错位：已注册 $($Verdict.registeredVersion)，" +
                    "已暂存待注册 $(@($Verdict.pendingVersions) -join ', ') —— $RemedyText")
        }
        'service-drift' {
            return ("📦 Claude 包版本错位：已注册 $($Verdict.registeredVersion)，" +
                    "$ServiceName PathName 指向 $($Verdict.serviceVersion) —— $RemedyText")
        }
        'plugin-disabled' {
            return ("📦 项目声明启用但实际未启用的插件：$(@($Verdict.missingPlugins) -join ', ') —— " +
                    "$($Verdict.remedy)")
        }
        'unknown' {
            return ("📦 Claude 包版本探针读数不完整（读不到 ≠ 没有错位）：" +
                    (@($Verdict.errors) -join '；'))
        }
        default { return '' }
    }
}

function Format-HumanReport {
    param($Verdict)
    $mark = switch ($Verdict.verdict) {
        'ok'              { '🟢 ok' }
        'pending-update'  { '🔴 pending-update' }
        'service-drift'   { '🔴 service-drift' }
        'plugin-disabled' { '🔴 plugin-disabled' }
        default           { '⚠ unknown' }
    }
    $lines = @(
        "Claude 包版本探针（只读，队列 #486／#584）",
        "  判定           : $mark",
        "  已注册版本     : $(if ($Verdict.registeredVersion) { $Verdict.registeredVersion } else { '（未读到）' })",
        "  服务 PathName  : $(if ($Verdict.serviceVersion) { $Verdict.serviceVersion } else { '（未读到）' })",
        "  暂存目录版本   : $(if (@($Verdict.stagedVersions).Count) { @($Verdict.stagedVersions) -join ', ' } else { '（未读到）' })",
        "  项目声明插件   : $(if (@($Verdict.declaredPlugins).Count) { @($Verdict.declaredPlugins) -join ', ' } else { '（未声明）' })",
        "  未启用的声明插件: $(if (@($Verdict.missingPlugins).Count) { @($Verdict.missingPlugins) -join ', ' } else { '（无）' })"
    )
    foreach ($r in @($Verdict.reasons)) { $lines += "  · $r" }
    foreach ($e in @($Verdict.errors))  { $lines += "  ! $e" }
    if ($Verdict.remedy) { $lines += "  ⇒ $($Verdict.remedy)（🔴 本探针不代跑，须你本人提权执行）" }
    return ($lines -join "`n")
}


# ── 主流程 ────────────────────────────────────────────────────────────────────

try {
    $fake = Get-FakeInjection
    $retired = $null -eq $fake
    if ($retired) { $fake = [pscustomobject]@{} }
    $verdict = Get-ClaudePackageVerdict -Fake $fake
    if ($retired) {
        $verdict['retired'] = $true
        $verdict.remedy = ''
        $verdict.errors += '旧实机探测入口已退役；未读取旧配置或启动旧引擎'
    }

    if ($Json) {
        [pscustomobject]$verdict | ConvertTo-Json -Depth 5 -Compress
    } elseif ($BannerLine) {
        $line = Format-BannerLine -Verdict $verdict
        if ($line -and -not $retired) { $line }
    } elseif (-not $Quiet) {
        Format-HumanReport -Verdict $verdict
    }
    exit 0
} catch {
    # 探针自身炸了也不许拖累调用方 —— 但必须说出来，不许静默当 ok。
    $msg = "Claude 包版本探针自身报错：$($_.Exception.Message)"
    if ($Json) {
        [pscustomobject]@{
            verdict = 'unknown'; registeredVersion = ''; serviceVersion = ''
            stagedVersions = @(); pendingVersions = @(); staleStagedVersions = @()
            servicePathName = ''; declaredPlugins = @(); missingPlugins = @()
            reasons = @(); errors = @($msg); remedy = ''
        } | ConvertTo-Json -Depth 5 -Compress
    } elseif ($BannerLine) {
        "📦 Claude 包版本探针不可用：$($_.Exception.Message)"
    } elseif (-not $Quiet) {
        $msg
    }
    exit 0
}
