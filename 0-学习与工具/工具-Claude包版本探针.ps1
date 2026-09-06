<#
.SYNOPSIS
  Claude 桌面端包版本错位探针（队列 §一 `#486`，OP-0906-J）。**纯只读**：不改服务、
  不提权、不写任何系统状态，只读三处并给判定。

.DESCRIPTION
  ## 为什么要有这个探针（根因，2026-09-04 事件日志实证）

  Claude 桌面端的 MSIX 自更新是**两段式**，两段之间隔着 2–3 小时：

    第一段 `Add` ＋ `DeferRegistrationWhenPackagesAreInUse`
        新版本被**暂存**进 `C:\Program Files\WindowsApps\Claude_<版本>_x64__<pfn>`，
        但因为 Claude 正在跑而**推迟注册**。此时磁盘上多出一个「比已注册版本更高、
        却尚未注册」的目录 —— 这就是本探针要抓的那个信号。

    第二段 `RegisterByPackageFamilyName` ＋ `ForceApplicationShutdownOption`
        推迟的注册被强制执行，**掐掉正在跑的 Claude**。

  实证（`Microsoft-Windows-AppXDeploymentServer/Operational`，Id 603/607/400）：

    | 暂存（Add，Defer） | 强制注册（Force） | 间隔 |
    |---|---|---|
    | 2026-09-04 13:01:40 → `1.46388.1.0` | 2026-09-04 **15:42:25** | 2h41m |
    | 2026-09-04 22:51:24 → `1.46388.2.0` | 2026-09-05 02:11:24 | 3h20m |
    | 2026-09-05 07:44:37 → `1.46388.3.0` | 2026-09-05 09:43:01 | 1h58m |
    | 2026-09-05 11:44:19 → `1.46388.4.0` | 2026-09-05 13:38:37 | 1h54m |

  队列 `#486` 记的「2026-09-04 15:42 Claude 异常退出」＝ 上表第一行的第二段，实锤。
  ⇒ **只要开场时磁盘上已有「更高版本已暂存」，这个会话就随时可能被强关**，
  「勿直接开长会话」这句提示的判据就在这里。

  ## 判定口径（🔴 与队列行字面的一处**收紧**，刻意为之，勿改回）

  队列 `#486` 行内写「三者不一致即提示」。**照字面实现会天天误报**：本机
  `WindowsApps` 下常年躺着 3 个**低于**已注册版本的残留旧目录
  （`1.30096.0.0` / `1.32352.1.0` / `1.34493.0.0`，2026-09-06 实测），
  它们同样「已暂存未注册」，但**是垃圾残留、不是待应用的更新**，
  且 `Restart-Service` 对它们毫无作用 —— 一道每次开场都响、响了又没有对应动作的
  提示，等于把横幅训练成噪音。故本探针把判据收紧为：

    ⑴ `pending-update` —— 存在**版本高于已注册版本**的已暂存目录。
       ⇒ 强制注册随时可能发生，别开长会话。
    ⑵ `service-drift` —— `CoworkVMService` 的 `PathName` 里的包版本 ≠ 已注册版本。
       ⇒ 服务登记项还指着另一个包，按 `#486` 行内口径先提权重启服务。
    ⑶ 低于已注册版本的暂存目录 ⇒ 只作为 `staleStagedVersions` **信息项**列出，
       **不触发任何提示**。

  ## 🔴 本探针**测不到**的一种错位（别据此认为「服务一定是新的」）

  `Win32_Service.PathName` 是**注册表状态**，注册那一步会把它改成新包路径；而**正在跑的
  那个 `cowork-svc.exe` 进程仍是老镜像**。要分辨这一种，必须读进程的
  `ExecutablePath` —— 2026-09-06 实测，非提权下 `Win32_Process.ExecutablePath` 与
  `Get-Process.Path` **都返回空**（是读不到，不是没有），故本探针**不做**这项判定，
  也**不假装**做了。⇒ `verdict=ok` 只代表「注册表口径三者对得上」，
  不代表「跑着的服务就是新版」。

  ## 静默回退的边界（本项目纪律：只读结果「太干净」先怀疑没读到对象）

  三处任一读不出来 ⇒ `verdict=unknown` ＋ `errors` 列原因，**绝不**因为「没读到差异」
  就报 `ok`。

.PARAMETER Json
  输出机器可读 JSON（单测与下游工具的契约面）。

.PARAMETER BannerLine
  只输出**一行**给 CC SessionStart 开场横幅用；`ok` 时**不输出任何内容**（正常态不加噪音）。

.PARAMETER Quiet
  抑制人类可读的多行输出（与 -Json 同用时无意义，留给纯取退出码的调用方）。

.OUTPUTS
  退出码恒为 0 —— 这是**诊断探针**，不是门禁；它自身的成败不该拦住调用它的钩子。
  判定结果一律走 stdout（`-Json` 的 `verdict` 字段 / `-BannerLine` 的那一行）。

.NOTES
  单测夹具：环境变量 `ZHUOPIN_CLAUDE_PROBE_FAKE` ＝ 一段 JSON，注入**三处原始读数**
  （不是注入判定结果 —— 解析逻辑本身也要被测到）：

      {
        "registered":      ["1.46388.4.0"],          // 缺省/null ⇒ 模拟「这一处读不出来」
        "servicePathName": "\"C:\\...\\Claude_1.46388.4.0_x64__pzs8sxrjxfjjc\\app\\...\\cowork-svc.exe\"",
        "stagedDirs":      ["Claude_1.30096.0.0_x64__pzs8sxrjxfjjc", "Claude_1.46388.5.0_x64__pzs8sxrjxfjjc"]
      }

  生产运行时该变量不存在，三处一律真读。
#>

[CmdletBinding()]
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
    <# 单测夹具：解析 `ZHUOPIN_CLAUDE_PROBE_FAKE`。未设或解析失败 ⇒ 返回 $null（走真读）。#>
    $raw = $env:ZHUOPIN_CLAUDE_PROBE_FAKE
    if ([string]::IsNullOrWhiteSpace($raw)) { return $null }
    try { return ($raw | ConvertFrom-Json) } catch { return $null }
}

function Test-HasProperty {
    <# StrictMode 下不能直接摸不存在的属性，统一走这个判定。#>
    param($Object, [string]$Name)
    if ($null -eq $Object) { return $false }
    return ($Object.PSObject.Properties.Name -contains $Name)
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
    try {
        $pkgs = @(Get-AppxPackage -Name 'Claude' -ErrorAction Stop)
        if ($pkgs.Count -eq 0) {
            # 🔴 空 ≠ ok：没有已注册的 Claude 包，本机口径下就是「没读到对象」。
            $r.Error = 'Get-AppxPackage Claude 返回空（无已注册的 Claude 包，或当前用户上下文读不到）'
            return $r
        }
        $r.Ok = $true
        $r.Value = @($pkgs | ForEach-Object { [string]$_.Version })
        return $r
    } catch {
        $r.Error = "Get-AppxPackage Claude 失败：$($_.Exception.Message)"
        return $r
    }
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
    try {
        $svc = Get-CimInstance -ClassName Win32_Service -Filter "Name='$ServiceName'" -ErrorAction Stop
        if ($null -eq $svc) {
            $r.Error = "Win32_Service 查不到 $ServiceName（服务未安装，或本上下文读不到）"
            return $r
        }
        $r.Ok = $true
        $r.Value = [string]$svc.PathName
        return $r
    } catch {
        $r.Error = "读 Win32_Service $ServiceName 失败：$($_.Exception.Message)"
        return $r
    }
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
    try {
        if (-not (Test-Path -LiteralPath $WindowsAppsRoot)) {
            $r.Error = "WindowsApps 目录不存在：$WindowsAppsRoot"
            return $r
        }
        # 🔴 `Program Files\WindowsApps` 是 ACL 受限目录：本机 2026-09-06 实测可列出，
        #    但换机器／换账户可能直接 Access Denied ⇒ 那时必须落到 unknown，不能当 ok。
        $dirs = @(Get-ChildItem -LiteralPath $WindowsAppsRoot -Filter 'Claude_*' -Directory -ErrorAction Stop)
        $r.Ok = $true
        $r.Value = @($dirs | ForEach-Object { $_.Name })
        return $r
    } catch {
        $r.Error = "列 $WindowsAppsRoot\Claude_* 失败：$($_.Exception.Message)"
        return $r
    }
}


# ── 判定 ──────────────────────────────────────────────────────────────────────

function Get-ClaudePackageVerdict {
    <#
      汇总三处读数出判定。返回一个 ordered 哈希（不是数组，避开 PowerShell 单元素展平坑）。
      verdict ∈ ok | pending-update | service-drift | unknown
      （pending-update 与 service-drift 同时成立时，verdict 取 pending-update，
        reasons 里两条都在 —— 前者是「会被强关」，后者是「跑的可能是旧的」，
        前者更急，但两条都得让人看见。）
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
        reasons             = @()
        errors              = @()
        remedy              = ''
    }

    $reg    = Read-RegisteredVersions -Fake $Fake
    $svc    = Read-ServicePathName    -Fake $Fake
    $staged = Read-StagedDirNames     -Fake $Fake

    foreach ($src in @($reg, $svc, $staged)) {
        if (-not $src.Ok) { $out.errors = @($out.errors) + @($src.Error) }
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

    if ($isPending) { $out.verdict = 'pending-update' }
    elseif ($isDrift) { $out.verdict = 'service-drift' }
    else {
        $out.verdict = 'ok'
        $out.reasons = @($out.reasons) +
            @("✓ 已注册 / 服务 PathName 均为 $($out.registeredVersion)，无更高版本待注册")
    }

    if ($out.verdict -ne 'ok') { $out.remedy = $RemedyText }

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
        'ok'             { '🟢 ok' }
        'pending-update' { '🔴 pending-update' }
        'service-drift'  { '🔴 service-drift' }
        default          { '⚠ unknown' }
    }
    $lines = @(
        "Claude 包版本探针（只读，队列 #486）",
        "  判定           : $mark",
        "  已注册版本     : $(if ($Verdict.registeredVersion) { $Verdict.registeredVersion } else { '（未读到）' })",
        "  服务 PathName  : $(if ($Verdict.serviceVersion) { $Verdict.serviceVersion } else { '（未读到）' })",
        "  暂存目录版本   : $(if (@($Verdict.stagedVersions).Count) { @($Verdict.stagedVersions) -join ', ' } else { '（未读到）' })"
    )
    foreach ($r in @($Verdict.reasons)) { $lines += "  · $r" }
    foreach ($e in @($Verdict.errors))  { $lines += "  ! $e" }
    if ($Verdict.remedy) { $lines += "  ⇒ $($Verdict.remedy)（🔴 本探针不代跑，须你本人提权执行）" }
    return ($lines -join "`n")
}


# ── 主流程 ────────────────────────────────────────────────────────────────────

try {
    $fake = Get-FakeInjection
    $verdict = Get-ClaudePackageVerdict -Fake $fake

    if ($Json) {
        [pscustomobject]$verdict | ConvertTo-Json -Depth 5 -Compress
    } elseif ($BannerLine) {
        $line = Format-BannerLine -Verdict $verdict
        if ($line) { $line }
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
            servicePathName = ''; reasons = @(); errors = @($msg); remedy = ''
        } | ConvertTo-Json -Depth 5 -Compress
    } elseif ($BannerLine) {
        "📦 Claude 包版本探针不可用：$($_.Exception.Message)"
    } elseif (-not $Quiet) {
        $msg
    }
    exit 0
}
