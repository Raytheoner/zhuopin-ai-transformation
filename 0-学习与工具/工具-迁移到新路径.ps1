# ================================================================
#  工具-迁移到新路径.ps1
#  用途：把本仓库整树迁出 OneDrive，从 <OldRoot> 移到 <NewRoot>，并逐项修指针。
#        队列 §一 #412（M1）产出；执行归属 M2 窗口，由 Shao Peishen 择日发起。
#
#  正本方案：3-治理与合规/仓库迁出OneDrive-迁移方案（未批准·方案阶段）-2026-08-25.md
#            —— 本脚本按其 §五 S0→S3 实现，逐步对照；细节判据以方案件为准。
#
#  🔴 三条硬要求（派单件 T3，实现时逐条落到代码里）：
#    1. **可从仓库外运行** —— 执行时仓库正在被移动，脚本自身必须先被复制到仓库外
#       （如 C:\Dev\），内部**不引用任何仓库内相对路径**。开头有自检，脚本若还躺在
#       $OldRoot 里则直接拒绝运行。
#    2. **每一步失败即停并明确报错**，不得继续（$ErrorActionPreference=Stop ＋ 逐步显式判据）。
#    3. **-WhatIf 把每一步要做什么原样打印出来，不执行**（含只读探测也不执行——
#       窗口日先跑一次 -WhatIf 给 Shao Peishen 过目，那一次不该花 61 秒去数文件）。
#
#  用法（管理员 PowerShell，先复制到仓库外再跑）：
#    Copy-Item "<旧仓库>\0-学习与工具\工具-迁移到新路径.ps1" C:\Dev\ -Force
#    # ① 先干跑，把每步要做什么打印出来过目
#    C:\Dev\工具-迁移到新路径.ps1 -WhatIf
#    # ② 真跑（一条命令跑完 S0→S3）
#    C:\Dev\工具-迁移到新路径.ps1
#    # ③ 也可分阶段跑／重跑某一段
#    C:\Dev\工具-迁移到新路径.ps1 -Phase S3
#
#  🔴 为什么必须提权：S4U 计划任务的 Register/Unregister/Enable/Disable 一律需要
#     SeTcbPrivilege（2026-08-25 实测，与任务属主是不是本人无关）。非提权跑，结果不是
#     报错中断，而是**四个任务原封不动、仍指旧路径**——而旧路径此时已空 ⇒ 触发时静默
#     失败。故本脚本开头 fail-loud 判提权，不许在非提权下走到 S1。
# ================================================================
[CmdletBinding()]
param(
    # 旧仓库根（当前 OneDrive 路径）。
    [string] $OldRoot = "C:\Users\Paul Shao\OneDrive\Projects\企业AI转型",

    # 新仓库根（Shao Peishen 2026-08-25 已定夺：全英文短路径，最深路径由 246 降到 219）。
    [string] $NewRoot = "C:\Dev\zhuopin-ai",

    # S0 固证与整树备份落点。🔴 必须在仓库外**且非 OneDrive**——方案 §七.3 未核证
    # 「旧路径被 /MOVE 清空后 OneDrive 会不会把云端副本判为用户删除并同步删掉」，
    # 备份放 OneDrive 里等于把回滚件押在这个未知上。
    [string] $BackupRoot = "C:\zhuopin-migration-backup",

    # 阶段选择；默认 All＝S0→S3 一条命令跑完。
    [ValidateSet('All', 'S0', 'S1', 'S2', 'S3')]
    [string[]] $Phase = @('All'),

    # 只打印每一步要做什么，不执行任何动作。
    [switch] $WhatIf,

    # 杀完机器人后的复核等待秒数。🔴 必须 ≥70 —— 守护脚本第一级退避是 60 秒，
    # 2026-08-25 实测：杀完 Start-Sleep 2 就复核返回**空**（看起来干净），
    # 60 秒后进程无声回来。这是「一次返回干净的复核，对象在退避窗口后自己回来」。
    [int] $RobotSettleSeconds = 90
)

$ErrorActionPreference = "Stop"
$script:StepNo = 0
$script:Findings = New-Object System.Collections.Generic.List[string]

# ─────────────────────── 输出与流程控制 ───────────────────────

function Say([string] $msg, [string] $color = "Gray") { Write-Host $msg -ForegroundColor $color }

function Head([string] $title) {
    Say ""
    Say ("=" * 72) Cyan
    Say "  $title" Cyan
    Say ("=" * 72) Cyan
}

function Fail([string] $msg) {
    Say ""
    Say "❌ 已中止：$msg" Red
    Say "   迁移未完成。回滚见方案件 §五「回滚」段；S0 备份在 $BackupRoot" Red
    exit 1
}

function Note([string] $msg) {
    $script:Findings.Add($msg) | Out-Null
    Say "   ⚠ $msg" Yellow
}

# 每一个会改变系统状态的动作都走这里：-WhatIf 只打印、不执行。
function Step {
    param(
        [Parameter(Mandatory)] [string]   $What,   # 这一步要做什么（原样打印）
        [Parameter(Mandatory)] [scriptblock] $Do   # 真跑时执行的动作
    )
    $script:StepNo++
    $tag = "[{0:d2}]" -f $script:StepNo
    if ($WhatIf) {
        Say "$tag （-WhatIf 不执行）$What" DarkGray
        return $null
    }
    Say "$tag $What" Yellow
    & $Do
}

# ─────────────────────── 预检（无条件跑，-WhatIf 也跑） ───────────────────────

Head "预检"

$selfPath = $PSCommandPath
if (-not $selfPath) { $selfPath = $MyInvocation.MyCommand.Path }
Say "  本脚本位置 : $selfPath"
Say "  旧仓库根   : $OldRoot"
Say "  新仓库根   : $NewRoot"
Say "  备份落点   : $BackupRoot"
Say "  阶段       : $($Phase -join ', ')$(if ($WhatIf) { '   [-WhatIf 干跑]' })"

# 🔴 硬要求 1：脚本自身不得躺在被搬的树里。
if ($selfPath -and $selfPath.StartsWith($OldRoot, [StringComparison]::OrdinalIgnoreCase)) {
    Fail @"
本脚本当前位于将被移动的仓库内（$selfPath）。
robocopy /MOVE 会把脚本自己一起抽走，执行到一半必然崩。
请先复制到仓库外再跑，例如：
    New-Item -ItemType Directory -Force C:\Dev | Out-Null
    Copy-Item "$OldRoot\0-学习与工具\工具-迁移到新路径.ps1" C:\Dev\ -Force
    C:\Dev\工具-迁移到新路径.ps1 -WhatIf
"@
}

# 备份落点不得在 OneDrive 里（方案 §七.3 未核证项）。
if ($BackupRoot -match '(?i)OneDrive') {
    Fail "备份落点 $BackupRoot 落在 OneDrive 内。回滚件不能押在「OneDrive 会不会把清空判为删除」这个未核证项上——请换一个非 OneDrive 路径。"
}
if ($BackupRoot.StartsWith($OldRoot, [StringComparison]::OrdinalIgnoreCase) -or
    $BackupRoot.StartsWith($NewRoot, [StringComparison]::OrdinalIgnoreCase)) {
    Fail "备份落点 $BackupRoot 落在仓库树内，起不到备份作用。"
}

# 🔴 提权自检（-WhatIf 豁免：干跑不碰任何任务）。
$isAdmin = ([Security.Principal.WindowsPrincipal] `
    [Security.Principal.WindowsIdentity]::GetCurrent()
).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if ($WhatIf) {
    Say "  提权       : $isAdmin（-WhatIf 干跑，不作要求）"
} elseif (-not $isAdmin) {
    Fail @"
当前会话非提权。S4U 计划任务的 Register/Unregister/Enable/Disable 一律需要 SeTcbPrivilege。
非提权跑下去的落地状态不是「报错停住」，而是**四个任务原封不动、仍指着旧路径**——
而旧路径此时已被清空 ⇒ 机器人不在线、sweep 空跑，且无人被通知。
请在管理员 PowerShell 里重跑本脚本。
"@
} else {
    Say "  提权       : True" Green
}

if (-not (Test-Path -LiteralPath $OldRoot)) { Fail "旧仓库根不存在：$OldRoot" }

$doS0 = $Phase -contains 'All' -or $Phase -contains 'S0'
$doS1 = $Phase -contains 'All' -or $Phase -contains 'S1'
$doS2 = $Phase -contains 'All' -or $Phase -contains 'S2'
$doS3 = $Phase -contains 'All' -or $Phase -contains 'S3'

if ($doS2 -and -not $WhatIf -and (Test-Path -LiteralPath $NewRoot)) {
    Fail "新仓库根已存在：$NewRoot —— robocopy /MOVE 到一个已有目录会把两棵树混在一起。请先确认它是什么，人工清理后再跑。"
}

$TASKS = @(
    'ZhuopinAibotDevListener',
    'ZhuopinCommitSweep',
    'ZhuopinDecisionReminderDaily',
    'ZhuopinFollowupDispatchDaily'
)
$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$snapDir = Join-Path $BackupRoot "snapshot-$stamp"
$treeBackup = Join-Path $BackupRoot "tree-$stamp"
# 2026-08-26 窗口内修复（可重入性）：$stamp 每次调用都取当前时间，单独跑 -Phase S3 时
#   $snapDir 会指向一个从未建过的目录，[09] 于是报「找不到 Listener 的 XML 备份」。
#   S0 不在本次阶段列表里时，回落到 $BackupRoot 下已存在的最新 snapshot-*。
if (($Phase -notcontains 'All') -and ($Phase -notcontains 'S0')) {
    $prev = Get-ChildItem -LiteralPath $BackupRoot -Directory -Filter 'snapshot-*' -EA SilentlyContinue |
            Sort-Object Name -Descending | Select-Object -First 1
    if ($prev) {
        $snapDir = $prev.FullName
        $stampPrev = $prev.Name -replace '^snapshot-', ''
        $tb = Join-Path $BackupRoot "tree-$stampPrev"
        if (Test-Path -LiteralPath $tb) { $treeBackup = $tb }
        Write-Host "  [快照] 本次未跑 S0，沿用已存在的快照：$snapDir" -ForegroundColor DarkCyan
    }
}
$moveLog = Join-Path $BackupRoot "robocopy-move-$stamp.log"

# ═══════════════════════════ S0 · 迁移前固证 ═══════════════════════════

if ($doS0) {
    Head "S0 · 迁移前固证（不可省——回滚全靠它）"

    Step "新建固证目录 $snapDir" {
        New-Item -ItemType Directory -Force -Path $snapDir | Out-Null
    }

    Step "git fsck --connectivity-only（旧路径，确认搬之前对象库是好的）" {
        & git -C $OldRoot fsck --connectivity-only 2>&1 |
            Tee-Object -FilePath (Join-Path $snapDir "git-fsck-before.txt")
        if ($LASTEXITCODE -ne 0) { Fail "迁移前 git fsck 就不通过（退出码 $LASTEXITCODE）——先修对象库，不要在坏树上做迁移。" }
    }

    Step "记录 HEAD / status / config / worktree 清单" {
        & git -C $OldRoot rev-parse HEAD          | Set-Content (Join-Path $snapDir "head.txt")
        & git -C $OldRoot log -1 --format=%H%n%s  | Set-Content (Join-Path $snapDir "log-1.txt")
        # 🔴 git status 在本仓库实测耗时约 61 秒（47,578 文件 ＋ 云盘占位符）。
        #    不要因为「命令没立刻返回」就以为它挂了而中断——中断后拿到的是空输出，
        #    而空输出看起来正好像「很干净」。
        Say "      · git status 约需 60 秒，请勿中断…" DarkGray
        & git -C $OldRoot status --porcelain      | Set-Content (Join-Path $snapDir "status-before.txt")
        & git -C $OldRoot config --list           | Set-Content (Join-Path $snapDir "config-before.txt")
        & git -C $OldRoot worktree list           | Set-Content (Join-Path $snapDir "worktree-list-before.txt")
    }

    Step "逐个 worktree 回读 --git-common-dir（🔴 不能只信 worktree list：实测有 2 个「静默隐身」worktree，gitdir 文件缺失 ⇒ list 根本不列出它们）" {
        $wtRoot = Join-Path $OldRoot ".claude\worktrees"
        $lines = New-Object System.Collections.Generic.List[string]
        if (Test-Path -LiteralPath $wtRoot) {
            foreach ($d in Get-ChildItem -LiteralPath $wtRoot -Directory) {
                $common = & git -C $d.FullName rev-parse --git-common-dir 2>&1
                $ok = ($LASTEXITCODE -eq 0)
                $lines.Add(("{0}`t{1}`t{2}" -f $d.Name, $(if ($ok) { 'OK' } else { 'BROKEN' }), $common)) | Out-Null
            }
        }
        $lines | Set-Content (Join-Path $snapDir "worktree-common-dir-before.tsv")
        $broken = ($lines | Where-Object { $_ -match "`tBROKEN`t" }).Count
        Say "      · worktree 目录 $($lines.Count) 个，其中 git 不认的 $broken 个（孤儿幽灵，迁移不修复它们，只如实记录）" DarkGray
    }

    Step "导出四个计划任务 XML 定义（回滚与 Listener 重注册的唯一依据）" {
        foreach ($t in $TASKS) {
            $out = Join-Path $snapDir "task-$t.xml"
            # 2026-08-26 窗口内修复：/TN <名字> 必须配 /XML ONE；原写 /XML ALL 会报
            #   "Improper display format type specified"，而错误信息本身就是非 0 长度的文件，
            #   刚好通过下面「存在且长度非 0」的校验 ==> 四份 XML 全是废的却一路绿灯，
            #   Listener 的回滚依据从头到尾不存在（实测 174 字节 x4）。
            & schtasks /Query /TN $t /XML ONE 2>&1 | Set-Content -Encoding Unicode $out
            $head = if (Test-Path $out) { (Get-Content -LiteralPath $out -Encoding Unicode -TotalCount 1) } else { '' }
            if (-not (Test-Path $out) -or (Get-Item $out).Length -lt 500 -or ($head -notmatch '<\?xml')) {
                Fail "导出计划任务 $t 的 XML 失败——没有它就无法回滚 Listener，不能继续。"
            }
        }
    }

    Step "记录 editable 安装现状（pip freeze ＋ 10 份 direct_url.json）" {
        & python -m pip list --format=freeze | Set-Content (Join-Path $snapDir "pip-freeze.txt")
        $sp = & python -c "import site;print([p for p in site.getsitepackages() if p.endswith('site-packages')][0])"
        Say "      · site-packages: $sp" DarkGray
        $rows = New-Object System.Collections.Generic.List[string]
        foreach ($di in Get-ChildItem -LiteralPath $sp -Directory -Filter "*.dist-info") {
            $du = Join-Path $di.FullName "direct_url.json"
            if (-not (Test-Path $du)) { continue }
            $j = Get-Content $du -Raw | ConvertFrom-Json
            if (-not $j.dir_info.editable) { continue }
            Copy-Item $du (Join-Path $snapDir ("direct_url-" + $di.Name + ".json")) -Force
            $rows.Add(("{0}`t{1}" -f $di.Name, $j.url)) | Out-Null
        }
        $rows | Set-Content (Join-Path $snapDir "editable-direct-urls.tsv")
        Say "      · editable 包 $($rows.Count) 个已记录" DarkGray
    }

    Step "整树**复制**一份到 $treeBackup（复制、不是移动——回滚靠它）" {
        New-Item -ItemType Directory -Force -Path $treeBackup | Out-Null
        # /COPY:DAT 而非 /COPYALL：后者要复制 SACL，需备份特权，未提权会成片 ERROR 5。
        # 🔴 2026-08-26 窗口内修复：原写法 `/LOG:(Join-Path ...)` —— PowerShell 调用原生命令时
        #    **不会**把括号表达式拼到 `/LOG:` 后面，而是拆成两个参数（空的 `/LOG:` ＋ 一个多余
        #    的位置参数）⇒ robocopy 返回 16、零复制、**连日志都不写**（实测：备份目录建出来了
        #    但是空的，且 $BackupRoot 下一个 .log 都没有）。日志路径必须先进变量再整体加引号。
        #    S2 的 move 那处用的是 `/LOG:$moveLog`（变量形式），本来就是对的，不受影响。
        $backupLog = Join-Path $BackupRoot "robocopy-backup-$stamp.log"
        & robocopy $OldRoot $treeBackup /E /COPY:DAT /DCOPY:DAT /R:1 /W:1 /NFL /NDL "/LOG:$backupLog" | Out-Null
        $rc = $LASTEXITCODE
        if ($rc -ge 8) { Fail "整树备份 robocopy 返回 $rc（≥8 即有真实失败）——没有可用备份，不能继续。" }
        Say "      · robocopy 返回 $rc（≤7 为成功）" Green
    }

    Step "核备份文件数与源一致" {
        $src = (Get-ChildItem -LiteralPath $OldRoot -Recurse -Force -File -ErrorAction SilentlyContinue).Count
        $dst = (Get-ChildItem -LiteralPath $treeBackup -Recurse -Force -File -ErrorAction SilentlyContinue).Count
        Say "      · 源 $src 个文件 / 备份 $dst 个文件" DarkGray
        if ($src -ne $dst) { Fail "备份文件数与源不一致（$src vs $dst）——备份不可信，不能继续。" }
    }

    if (-not $WhatIf) { Say "  ✅ S0 完成，固证在 $snapDir，整树备份在 $treeBackup" Green }
}

# ═══════════════════════════ S1 · 停服 ═══════════════════════════

if ($doS1) {
    Head "S1 · 停服"

    Step "停 ZhuopinAibotDevListener 计划任务（🔴 只做这一步不够，见下两步）" {
        Stop-ScheduledTask -TaskName 'ZhuopinAibotDevListener' -ErrorAction SilentlyContinue
    }

    Step "杀守护 powershell（start-aibot-service-dev）—— 🔴 顺序不能反：先守护后 python，只杀 python 必被 60 秒退避拉回来" {
        Get-CimInstance Win32_Process -Filter "Name='powershell.exe'" |
            Where-Object { $_.CommandLine -like '*start-aibot-service-dev*' } |
            ForEach-Object { Say "      · 杀 PID $($_.ProcessId)" DarkGray; Stop-Process -Id $_.ProcessId -Force }
    }

    Step "杀服务 python（run_aibot_service）" {
        Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
            Where-Object { $_.CommandLine -like '*run_aibot_service*' } |
            ForEach-Object { Say "      · 杀 PID $($_.ProcessId)" DarkGray; Stop-Process -Id $_.ProcessId -Force }
    }

    Step "等待 $RobotSettleSeconds 秒后复核（🔴 必须 ≥70：守护第一级退避 60 秒；等 2 秒复核会返回「空」，60 秒后进程无声回来）" {
        if ($RobotSettleSeconds -lt 70) { Fail "RobotSettleSeconds=$RobotSettleSeconds < 70，复核会给出假的「已停」。" }
        Start-Sleep -Seconds $RobotSettleSeconds
        $py = @(Get-CimInstance Win32_Process -Filter "Name='python.exe'" | Where-Object { $_.CommandLine -like '*run_aibot_service*' })
        $ps = @(Get-CimInstance Win32_Process -Filter "Name='powershell.exe'" | Where-Object { $_.CommandLine -like '*start-aibot-service-dev*' })
        if ($py.Count -or $ps.Count) {
            Fail "机器人未真正停下（python $($py.Count) 个 / 守护 $($ps.Count) 个仍在）——继续迁移会在移动中途被它写文件。"
        }
        Say "      · 两者皆空，机器人确已停" Green
    }

    Step "禁用四个计划任务（防迁移中途被触发）" {
        foreach ($t in $TASKS) {
            # 🔴 方案 §五 S1 原文只写「其余三个」——Listener 因触发器只有 Logon+Boot、
            #    杀完本次登录内不会自起。本脚本把 Listener 也一并 Disable：窗口里若发生
            #    重启，Boot 触发器会把它拉起来指向一个已被清空的旧路径。它在 S3 会按 XML
            #    重注册，Disable 不产生额外代价。**这是相对方案件的一处增补，已在收工报告登记。**
            Disable-ScheduledTask -TaskName $t -ErrorAction SilentlyContinue | Out-Null
            $st = (Get-ScheduledTask -TaskName $t -ErrorAction SilentlyContinue).State
            Say "      · $t → $st" DarkGray
            if ($st -ne 'Disabled') { Fail "$t 未能禁用（当前 $st）——非提权或权限不足，停下。" }
        }
    }

    Step "退出 OneDrive 客户端" {
        $od = "$env:LOCALAPPDATA\Microsoft\OneDrive\OneDrive.exe"
        if (Test-Path $od) { & $od /shutdown; Start-Sleep -Seconds 5 }
        Get-Process OneDrive -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
        Start-Sleep -Seconds 3
        $left = @(Get-Process OneDrive -ErrorAction SilentlyContinue)
        if ($left.Count) { Fail "OneDrive 进程仍在（$($left.Count) 个）——它会一边同步一边被 move 抽走文件。" }
        Say "      · OneDrive 已退出" Green
    }

    Say ""
    Say "  ⚠ 人工确认（脚本判不出，方案 §四判据 5 的第二类）：" Yellow
    Say "    · 所有 CC / Cowork 窗口、编辑器、终端均未在操作旧路径" Yellow
    Say "    · 停机器人期间的来件**不可恢复**（企微无离线补推）——窗口起止时间应已在" Yellow
    Say "      采购/财务/质量三个部门群告知；事后须核一遍窗口期有无来件线索" Yellow

    if (-not $WhatIf) { Say "  ✅ S1 完成" Green }
}

# ═══════════════════════════ S2 · 移动 ═══════════════════════════

if ($doS2) {
    Head "S2 · 移动"

    Step "🔴 确认无云端占位符（robocopy 搬占位符会得到「文件数对、内容是空壳」的副本，而且不报错）" {
        $ph = @(Get-ChildItem -LiteralPath $OldRoot -Recurse -Force -File -ErrorAction SilentlyContinue |
            Where-Object { (($_.Attributes -band 0x400000) -ne 0) -or (($_.Attributes -band 0x1000) -ne 0) })
        Say "      · 占位符文件 $($ph.Count) 个" DarkGray
        if ($ph.Count -ne 0) {
            $ph | Select-Object -First 10 -ExpandProperty FullName | ForEach-Object { Say "        $_" Red }
            Fail "存在 $($ph.Count) 个云端占位符——必须先全部 hydrate（在资源管理器里「始终保留在此设备上」）再迁。"
        }
    }

    $script:BaseCount = 0
    Step "当场取文件数基线（🔴 不写死期望值：实测同日 1.5 小时内涨过 4,092，基线必须在冻结窗口内取）" {
        $script:BaseCount = (Get-ChildItem -LiteralPath $OldRoot -Recurse -Force -File -ErrorAction SilentlyContinue).Count
        Say "      · 基线 = $($script:BaseCount) 个文件" Green
        Set-Content (Join-Path $BackupRoot "filecount-baseline-$stamp.txt") $script:BaseCount
    }

    Step "robocopy /MOVE 整树搬到 $NewRoot（🔴 用 /COPY:DAT 不用 /COPYALL——后者要 SACL，需备份特权，实测 0.1 秒退 16）" {
        New-Item -ItemType Directory -Force -Path (Split-Path $NewRoot -Parent) | Out-Null
        # 2026-08-26 同批加固：变量形式本来就对（当前 $BackupRoot 无空格），但补上引号，
        # 免得将来有人传一个含空格的 -BackupRoot 时踩上一处同族的静默失败。
        & robocopy $OldRoot $NewRoot /MOVE /E /COPY:DAT /DCOPY:DAT /R:1 /W:1 /NFL /NDL "/LOG:$moveLog" | Out-Null
        $rc = $LASTEXITCODE
        Say "      · robocopy 返回 $rc（≤7 为成功），日志 $moveLog" $(if ($rc -ge 8) { 'Red' } else { 'Green' })
        if ($rc -ge 8) { Fail "robocopy 返回 $rc（≥8 即有真实失败）。日志：$moveLog" }
        $failed = Select-String -Path $moveLog -Pattern '^\s*Failed\s*:' -ErrorAction SilentlyContinue |
            ForEach-Object { $_.Line }
        if ($failed) {
            Say "      · 日志 Failed 行：" DarkGray
            $failed | ForEach-Object { Say "        $_" DarkGray }
            if ($failed -notmatch '\s0\s+0\s+0\s+0\s+0\s*$' -and ($failed -join '') -match '\s[1-9]\d*\s') {
                Note "robocopy 日志 Failed 计数非 0，请人工判读 $moveLog"
            }
        }
    }

    Step "核文件数：新路径应与基线严格相等" {
        $dst = (Get-ChildItem -LiteralPath $NewRoot -Recurse -Force -File -ErrorAction SilentlyContinue).Count
        Say "      · 基线 $($script:BaseCount) / 新路径 $dst" DarkGray
        if ($dst -ne $script:BaseCount) { Fail "文件数不一致（基线 $($script:BaseCount) vs 新路径 $dst）——有文件没搬过去。" }
        Say "      · 相等 ✅" Green
    }

    Step "🔴 中文完整性抽验（读回 3 处含中文的深层路径文件，确认无 U+FFFD——编码事故指纹）" {
        $samples = @(
            "1-转型规划\0-全景路线图\跨桌任务队列-机制环境.md",
            "6-人才与组织\部门AI专员跟进\README-跟进机制与命名约定.md",
            "4-数字员工\质量部\QD-B-立项审核门禁\tests\test_golden_product_class.py"
        )
        foreach ($rel in $samples) {
            $p = Join-Path $NewRoot $rel
            if (-not (Test-Path -LiteralPath $p)) { Fail "抽验文件不存在：$p" }
            $txt = Get-Content -LiteralPath $p -Raw -Encoding UTF8
            if ($txt -match "`u{FFFD}") { Fail "抽验文件含 U+FFFD（编码损坏指纹）：$p" }
            Say "      · OK  $rel" DarkGray
        }
        if (Get-ChildItem -LiteralPath $NewRoot -Recurse -Force -ErrorAction SilentlyContinue |
            Where-Object { $_.Name -match "`u{FFFD}" } | Select-Object -First 1) {
            Fail "新树内存在含 U+FFFD 的文件/目录名——按乱码哨兵纪律立即停手隔离，不直删。"
        }
    }

    Step "🔴 git fsck --full（不是 --connectivity-only）—— .git 632 MB / 8,251 文件刚被逐字节搬过，连通性检查验不出 pack 内部的字节损伤。这一步耗时较长，但它是整次迁移唯一能证明「对象库没搬坏」的动作" {
        & git -C $NewRoot fsck --full 2>&1 | Tee-Object -FilePath (Join-Path $BackupRoot "git-fsck-full-after-$stamp.txt")
        if ($LASTEXITCODE -ne 0) { Fail "git fsck --full 未通过（退出码 $LASTEXITCODE）——对象库可能在搬运中损伤，立即走回滚。" }
        Say "      · fsck --full 通过 ✅" Green
    }

    if (-not $WhatIf) { Say "  ✅ S2 完成" Green }
}

# ═══════════════════════════ S3 · 修指针 ═══════════════════════════

if ($doS3) {
    Head "S3 · 修指针"

    # ── 10. worktree ──
    Step "修 worktree 双向指针（🔴 禁止裸跑 `git worktree repair`：它的作用对象由「它读到的路径」决定，不由「你在哪个仓库里执行」决定。裸跑在复制场景会改坏源仓库、在移动场景静默什么都不做，两种误用都无声）" {
        $wtRoot = Join-Path $NewRoot ".claude\worktrees"
        if (-not (Test-Path -LiteralPath $wtRoot)) { Say "      · 无 worktree 目录，跳过" DarkGray; return }
        # 只把「目录内有 .git」的传进去；孤儿幽灵目录（git 完全不认识）不传，只如实统计。
        $all = @(Get-ChildItem -LiteralPath $wtRoot -Directory)
        $wts = @($all | Where-Object { Test-Path -LiteralPath (Join-Path $_.FullName ".git") } | ForEach-Object { $_.FullName })
        Say "      · worktree 目录 $($all.Count) 个，其中带 .git 的 $($wts.Count) 个将显式传入 repair" DarkGray
        if ($all.Count -ne $wts.Count) {
            Note "有 $($all.Count - $wts.Count) 个 worktree 目录不带 .git（孤儿幽灵）——本脚本不动它们；清理另立队列行"
        }
        if ($wts.Count) { & git -C $NewRoot worktree repair @wts }
    }

    Step "逐个回读 --git-common-dir 校验（🔴 不得只看 `git worktree list`：实测有 2 个「静默隐身」worktree，gitdir 文件缺失 ⇒ list 根本不列出它们，连 prunable 都不会报）" {
        $wtRoot = Join-Path $NewRoot ".claude\worktrees"
        if (-not (Test-Path -LiteralPath $wtRoot)) { return }
        $bad = New-Object System.Collections.Generic.List[string]
        $ghost = New-Object System.Collections.Generic.List[string]
        foreach ($d in Get-ChildItem -LiteralPath $wtRoot -Directory) {
            if (-not (Test-Path -LiteralPath (Join-Path $d.FullName ".git"))) { continue }
            $common = (& git -C $d.FullName rev-parse --git-common-dir 2>&1) -join ''
            if ($LASTEXITCODE -ne 0) { $ghost.Add("$($d.Name)：git 不认（$common）") | Out-Null; continue }
            $abs = (Resolve-Path -LiteralPath (Join-Path $d.FullName $common) -ErrorAction SilentlyContinue)
            $probe = if ($abs) { $abs.Path } else { $common }
            if (-not $probe.Replace('\','/').StartsWith($NewRoot.Replace('\','/'), [StringComparison]::OrdinalIgnoreCase)) {
                $bad.Add("$($d.Name)：common-dir 仍指 $probe") | Out-Null
            }
        }
        if ($ghost.Count) {
            $ghost | ForEach-Object { Say "        $_" DarkYellow }
            Note "上列 $($ghost.Count) 个为孤儿幽灵 worktree（S0 已如实记录、repair 亦已排除）——不计入失败，清理另立队列行"
        }
        if ($bad.Count) {
            $bad | ForEach-Object { Say "        $_" Red }
            Fail "$($bad.Count) 个 worktree 的 common-dir 未指向新路径。"
        }
        Say "      · 全部 worktree 的 common-dir 已指向新路径 ✅" Green
    }

    # ── 11bis. 仓库内「不入库」脚本的旧路径改字 ──
    #  🔴 B 类源码常量已在 M1 随 master 改完。但**有三个脚本不在 master 上**
    #     （M1 实测：start-aibot-service-dev.ps1 与 run-decision-reminder-check.ps1 被
    #     .gitignore 忽略、run-followup-dispatch-check.ps1 未跟踪），它们只存在于
    #     ops/wecom-service-home worktree 的磁盘上 ⇒ **只改 master 改不到它们**。
    #     其中两个 run-*-check.ps1 会被重跑注册脚本覆盖重生成（模板里的路径来自已改好的
    #     $MAIN_WORKSPACE_QUEUE），start-aibot-service-dev.ps1 与 run-commit-sweep.ps1
    #     则必须在这里就地改。
    Step "就地改「不入库」脚本里的旧路径（这三个不在 master 上，只改 master 改不到）" {
        $targets = @(
            "0-学习与工具\run-commit-sweep.ps1",
            ".claude\worktrees\wecom-service-home\5-平台底座\wecom-aibot-service\start-aibot-service-dev.ps1",
            ".claude\worktrees\wecom-service-home\5-平台底座\wecom-aibot-service\run-decision-reminder-check.ps1",
            ".claude\worktrees\wecom-service-home\5-平台底座\wecom-aibot-service\run-followup-dispatch-check.ps1"
        )
        foreach ($rel in $targets) {
            $p = Join-Path $NewRoot $rel
            if (-not (Test-Path -LiteralPath $p)) { Note "未找到（可能已随注册脚本重生成）：$rel"; continue }
            $bytes = [System.IO.File]::ReadAllBytes($p)
            $txt = [System.Text.Encoding]::UTF8.GetString($bytes)
            if ($txt -notlike "*$OldRoot*") { Say "      · 无旧路径，跳过  $rel" DarkGray; continue }
            $n = ([regex]::Matches($txt, [regex]::Escape($OldRoot))).Count
            # 字节级写回，保留 BOM 与 CRLF 原样（assert-no-orphan-cr.ps1 会检孤立 CR）
            $new = $txt.Replace($OldRoot, $NewRoot)
            [System.IO.File]::WriteAllBytes($p, [System.Text.Encoding]::UTF8.GetBytes($new))
            Say "      · 已改 $n 处  $rel" Green
        }
    }

    Step "全树扫描残留旧路径（.ps1/.py/.vbs/.json/.env/.cfg/.toml；.md 按「历史记录不追改」不扫）" {
        $hits = Get-ChildItem -LiteralPath $NewRoot -Recurse -File -Force -ErrorAction SilentlyContinue `
                    -Include *.ps1, *.py, *.vbs, *.json, *.cfg, *.toml, *.env |
            Where-Object { $_.FullName -notlike "*\.git\*" } |
            Select-String -SimpleMatch -Pattern $OldRoot -ErrorAction SilentlyContinue
        if ($hits) {
            Say "      · 仍含旧路径的文件（须人工判读，不自动改）：" Yellow
            $hits | Group-Object Path | ForEach-Object { Say "        $($_.Name)  ×$($_.Count)" Yellow }
            Note "全树扫描发现 $(($hits | Group-Object Path).Count) 个文件仍含旧路径——见上方清单"
        } else {
            Say "      · 零残留 ✅" Green
        }
    }

    # ── 12. editable 安装 ──
    Step "重装 editable 包（先全部 uninstall，再从新路径逐个 pip install -e）" {
        # 🔴 M1 实测（2026-08-26）：现状与方案件 §七.1（2026-08-25）**已不同**——
        #    10 个包里 9 个已正确指向主工作树，只剩 unified_portal_gateway 指向
        #    早已删除的 worktree `unified-portal-design-8a2ce3`，且该包源码在主工作树与
        #    git 里都**不存在** ⇒ 它无处可装，只能卸载后另行处置（已登记队列）。
        $sp = & python -c "import site;print([p for p in site.getsitepackages() if p.endswith('site-packages')][0])"
        $plan = New-Object System.Collections.Generic.List[object]
        foreach ($di in Get-ChildItem -LiteralPath $sp -Directory -Filter "*.dist-info") {
            $du = Join-Path $di.FullName "direct_url.json"
            if (-not (Test-Path $du)) { continue }
            $j = Get-Content $du -Raw | ConvertFrom-Json
            if (-not $j.dir_info.editable) { continue }
            $old = [uri]::UnescapeDataString(($j.url -replace '^file:///', '')).Replace('/', '\')
            $name = $di.Name -replace '-\d[^-]*\.dist-info$', ''
            $new = if ($old.StartsWith($OldRoot, [StringComparison]::OrdinalIgnoreCase)) {
                $NewRoot + $old.Substring($OldRoot.Length)
            } else { $old }
            $plan.Add([pscustomobject]@{ Name = $name; Old = $old; New = $new; Installable = (Test-Path -LiteralPath $new) }) | Out-Null
        }
        foreach ($e in $plan) {
            Say ("      · {0,-30} 可装={1,-5} {2}" -f $e.Name, $e.Installable, $e.New) DarkGray
        }
        foreach ($e in $plan) { & python -m pip uninstall -y $e.Name | Out-Null }
        # 2026-08-26 窗口内修复：原实现按 dist-info 目录序安装，而各场景包的 pyproject
        #   依赖底座包 zhuopin_platform；先全部 uninstall 后再按字母序装，装 fi1 时
        #   zhuopin_platform 尚未装回 ==> pip 跑去 PyPI 找一个本地包，报
        #   "No matching distribution found for zhuopin_platform" 而中止。
        #   修法：底座包排最前，且安装一律 --no-deps（本次迁移只改路径、未动任何第三方
        #   依赖，重装的唯一目的是让 editable 指针指向新路径）。
        $baseFirst = @('zhuopin_platform', 'wecom_aibot_service')
        $ordered = @($plan | Sort-Object @{ Expression = { $k = $baseFirst.IndexOf($_.Name); if ($k -lt 0) { 99 } else { $k } } }, Name)
        foreach ($e in $ordered) {
            if (-not $e.Installable) {
                Note "editable 包 $($e.Name) 的源目录在新路径下不存在（$($e.New)）——已卸载、未重装，须另行处置"
                continue
            }
            & python -m pip install -e $e.New --no-build-isolation --no-deps 2>&1 | Select-Object -Last 2 | ForEach-Object { Say "        $_" DarkGray }
            if ($LASTEXITCODE -ne 0) { Fail "pip install -e $($e.New) 失败（退出码 $LASTEXITCODE）。" }
        }
    }

    Step "import 实测回读（确认真的解析到新路径，不只看 pip 说成功）" {
        $probe = @'
import importlib.util as u
mods = ["zhuopin_platform","aibot_service","fi1","fi2","o2_kit_shortage","qd_b_gate","sc7_inventory","sc8","src"]
bad = []
for m in mods:
    try:
        s = u.find_spec(m)
        o = s.origin if s else "NOT_FOUND"
    except Exception as e:
        o = f"ERR {e}"
    print(f"{m:20} {o}")
    if "NOT_FOUND" in o or "ERR" in o or "OneDrive" in o:
        bad.append(m)
print("BAD=" + ",".join(bad))
'@
        $out = $probe | & python -
        $out | ForEach-Object { Say "        $_" DarkGray }
        if (($out | Where-Object { $_ -like 'BAD=*' }) -notmatch '^BAD=$') {
            Fail "有包未解析到新路径（见上方 BAD= 行）。"
        }
        Say "      · 全部解析到新路径 ✅" Green
    }

    # ── 13. 计划任务 ──
    Step "重跑三个注册脚本（从**新路径**跑；它们会顺带重生成 run-commit-sweep.ps1 与两个 run-*-check.ps1 包装）" {
        $regs = @(
            (Join-Path $NewRoot "0-学习与工具\工具-注册落库sweep计划任务.ps1"),
            (Join-Path $NewRoot ".claude\worktrees\wecom-service-home\5-平台底座\wecom-aibot-service\register-decision-reminder-task.ps1"),
            (Join-Path $NewRoot ".claude\worktrees\wecom-service-home\5-平台底座\wecom-aibot-service\register-followup-dispatch-task.ps1")
        )
        foreach ($r in $regs) {
            if (-not (Test-Path -LiteralPath $r)) { Fail "注册脚本不存在：$r" }
            Say "      · 跑 $r" DarkGray
            & $r
            if ($LASTEXITCODE -ne 0 -and $null -ne $LASTEXITCODE) { Fail "注册脚本失败（退出码 $LASTEXITCODE）：$r" }
        }
    }

    Step "⚠ ops/wecom-service-home worktree 须先同步到含改字 commit 的 master，再跑上一步 —— 若上一步报「未找到 …\scripts\*.py」或改字未生效，先做同步再重跑本阶段" {
        # 2026-08-26 窗口内修复：$HOME 是 PowerShell 只读内置变量（变量名大小写不敏感），
        #   赋值直接抛 "Cannot overwrite variable HOME"，把一步纯只读的检查变成整阶段中断。
        $svcHome = Join-Path $NewRoot ".claude\worktrees\wecom-service-home"
        if (Test-Path -LiteralPath $svcHome) {
            $behind = (& git -C $svcHome rev-list --count HEAD..master 2>&1) -join ''
            Say "      · wecom-service-home 落后 master $behind 个提交" $(if ($behind -eq '0') { 'Green' } else { 'Yellow' })
            if ($behind -ne '0') { Note "ops/wecom-service-home 落后 master $behind 个提交——机器人跑的是旧代码，须同步后重启" }
        }
    }

    Step "按 S0 备份的 XML 重注册 ZhuopinAibotDevListener（把 XML 里的旧路径换成新路径）" {
        $xml = Join-Path $snapDir "task-ZhuopinAibotDevListener.xml"
        if (-not (Test-Path -LiteralPath $xml)) { Fail "找不到 Listener 的 XML 备份：$xml（S0 未跑或备份丢失，不能凭空重建）。" }
        $txt = Get-Content -LiteralPath $xml -Raw -Encoding Unicode
        $n = ([regex]::Matches($txt, [regex]::Escape($OldRoot))).Count
        Say "      · XML 内旧路径 $n 处，替换为新路径" DarkGray
        $txt = $txt.Replace($OldRoot, $NewRoot)
        $newXml = Join-Path $snapDir "task-ZhuopinAibotDevListener-newpath.xml"
        Set-Content -LiteralPath $newXml -Value $txt -Encoding Unicode
        Unregister-ScheduledTask -TaskName 'ZhuopinAibotDevListener' -Confirm:$false -ErrorAction SilentlyContinue
        & schtasks /Create /TN 'ZhuopinAibotDevListener' /XML $newXml /F
        if ($LASTEXITCODE -ne 0) { Fail "重注册 ZhuopinAibotDevListener 失败（退出码 $LASTEXITCODE）。回滚 XML：$xml" }
    }

    Step "🔴 四个任务全部回读 Execute/Arguments/WorkingDirectory 确认新路径（「注册没报错」不等于「路径刷新了」）" {
        $bad = New-Object System.Collections.Generic.List[string]
        foreach ($t in $TASKS) {
            $task = Get-ScheduledTask -TaskName $t -ErrorAction SilentlyContinue
            if (-not $task) { $bad.Add("$t：任务不存在") | Out-Null; continue }
            foreach ($a in $task.Actions) {
                $line = "{0} | Execute={1} | Args={2} | WD={3}" -f $t, $a.Execute, $a.Arguments, $a.WorkingDirectory
                Say "        $line" DarkGray
                if ($line -like "*$OldRoot*") { $bad.Add("$t 仍含旧路径") | Out-Null }
            }
        }
        if ($bad.Count) {
            $bad | ForEach-Object { Say "        $_" Red }
            Fail "$($bad.Count) 处计划任务未刷新到新路径。"
        }
        Say "      · 四个任务均已指向新路径 ✅" Green
    }

    Step "启用四个计划任务" {
        foreach ($t in $TASKS) {
            Enable-ScheduledTask -TaskName $t -ErrorAction SilentlyContinue | Out-Null
            $st = (Get-ScheduledTask -TaskName $t).State
            Say "      · $t → $st" DarkGray
        }
        Say "      ⚠ 若本次迁移仍处于全局冻结窗口内，请按冻结要求把不该启用的任务改回 Disabled" Yellow
    }

    # ── 14. 仓库外件 ──
    Step "改仓库外载体里的旧路径（Claude\Scheduled 两份 SKILL.md ＋ ~/.claude/CLAUDE.md）" {
        $ext = @(
            "$env:USERPROFILE\Claude\Scheduled\huijian-chaijian-patrol\SKILL.md",
            "$env:USERPROFILE\Claude\Scheduled\weekly-status-update\SKILL.md",
            "$env:USERPROFILE\.claude\CLAUDE.md"
        )
        foreach ($p in $ext) {
            if (-not (Test-Path -LiteralPath $p)) { Note "仓库外载体不存在：$p"; continue }
            $txt = [System.IO.File]::ReadAllText($p, [System.Text.Encoding]::UTF8)
            if ($txt -notlike "*$OldRoot*") { Say "      · 无旧路径，跳过  $p" DarkGray; continue }
            $n = ([regex]::Matches($txt, [regex]::Escape($OldRoot))).Count
            Copy-Item $p (Join-Path $snapDir ("ext-" + (Split-Path (Split-Path $p -Parent) -Leaf) + "-" + (Split-Path $p -Leaf))) -Force
            # 🔴 2026-08-26 修复：`[System.Text.Encoding]::UTF8` 这个静态属性**默认带 BOM**，
            #   会给原本无 BOM 的文件加上 EF BB BF。实测后果：两个 Claude 定时任务的 SKILL.md
            #   被加 BOM 后，`\ufeff` 把 YAML frontmatter 的 `---` 顶到第 4 字节 ⇒ 应用报
            #   「Task file not found or has unexpected format」⇒ Instructions 读不出来 ⇒
            #   必填项为空 ⇒ Save 与 Run now 全灰，任务无法手动运行也无法改目录。
            #   ~/.claude/CLAUDE.md 同样被波及。修法：读时判 BOM，写时原样保持。
            $rawBytes = [System.IO.File]::ReadAllBytes($p)
            $hadBom = ($rawBytes.Length -ge 3 -and $rawBytes[0] -eq 0xEF -and $rawBytes[1] -eq 0xBB -and $rawBytes[2] -eq 0xBF)
            [System.IO.File]::WriteAllText($p, $txt.Replace($OldRoot, $NewRoot), (New-Object System.Text.UTF8Encoding($hadBom)))
            Say "      · 已改 $n 处  $p" Green
        }
    }

    Step "核 Claude\Scheduled 真身与仓库内 0-学习与工具/定时任务源码/ 镜像哈希一致" {
        $mirror = Join-Path $NewRoot "0-学习与工具\定时任务源码"
        if (-not (Test-Path -LiteralPath $mirror)) { Note "未找到镜像目录 $mirror，跳过哈希核对"; return }
        foreach ($name in @('huijian-chaijian-patrol', 'weekly-status-update')) {
            $real = "$env:USERPROFILE\Claude\Scheduled\$name\SKILL.md"
            $mir = Join-Path $mirror "$name\SKILL.md"
            if (-not (Test-Path -LiteralPath $real) -or -not (Test-Path -LiteralPath $mir)) {
                Note "$name：真身或镜像缺失，无法核哈希"; continue
            }
            $h1 = (Get-FileHash -LiteralPath $real -Algorithm SHA256).Hash
            $h2 = (Get-FileHash -LiteralPath $mir -Algorithm SHA256).Hash
            if ($h1 -ne $h2) { Note "$name：真身与镜像哈希不一致（真身 $($h1.Substring(0,12))… / 镜像 $($h2.Substring(0,12))…）——须人工对齐" }
            else { Say "      · $name 哈希一致 ✅" Green }
        }
    }

    # ── 15. 备份替代 ──
    Step "T4 · 建不入库件备份目录并首次同步（注册每周任务由 工具-注册不入库件备份任务.ps1 单独做）" {
        $sync = Join-Path $NewRoot "0-学习与工具\工具-不入库件备份同步.ps1"
        if (-not (Test-Path -LiteralPath $sync)) { Note "未找到 $sync，跳过"; return }
        & $sync -RepoRoot $NewRoot
        if ($LASTEXITCODE -ne 0 -and $null -ne $LASTEXITCODE) { Note "不入库件首次同步返回 $LASTEXITCODE，请人工核对" }
    }

    if (-not $WhatIf) { Say "  ✅ S3 完成" Green }
}

# ═══════════════════════════ 收尾 ═══════════════════════════

Head "S4 · 冒烟清单（人工逐项，全绿才算完）"
@"
  1. git status / git log -1 哈希与 S0 一致；git config --list 与 $snapDir\config-before.txt 逐行一致
     核完可删除 .git 内三个 -SPSThinkpadWIN 冲突副本（迁出 OneDrive 后不会再产生新的）
  2. python "$NewRoot\0-学习与工具\工具-队列查询.py" --row 170 --section 一   正常返回
  3. 编辑锁 acquire → release 一个来回成功
  4. python "$NewRoot\0-学习与工具\工具-落库sweep.py"   手动跑一轮，落库成功
  5. Start-ScheduledTask ZhuopinAibotDevListener → 审计 jsonl 出现 authenticated（且全程仅一条，防双实例）
     🔴 再从企微发一条真实测试消息，确认机器人真的回 ——「探针通了 ≠ 机制通了」（OP-0819-F）
  6. 手动触发 ZhuopinDecisionReminderDaily / ZhuopinFollowupDispatchDaily 各一次
     🔴 退出码只认被执行进程自己那一层：用独立 .ps1 读 `$LASTEXITCODE，
        **不要用 cmd /c … %ERRORLEVEL%**（它在 cmd 解析期就展开，会给出假的 0）
  7. pytest 全量（至少 QD-A / QD-B / FI2 三处含绝对路径的测试）
  8. Cowork 侧：由 Shao Peishen 重新选择文件夹到 $NewRoot，并读一次队列确认可达
  9. 观察期 5 个工作日：每日核 sweep 有落库、机器人在线、拆件巡逻两班有产出
     🔴 旧路径整树备份（$treeBackup）保留至观察期结束再删
"@ | Write-Host

if ($script:Findings.Count) {
    Head "本次运行的告警（不阻断，但须人工判读）"
    $i = 0
    foreach ($f in $script:Findings) { $i++; Say "  $i. $f" Yellow }
} else {
    Say ""
    Say "  本次运行无告警。" Green
}

Say ""
if ($WhatIf) {
    Say "  ▶ 以上为 -WhatIf 干跑，未执行任何动作。确认无误后去掉 -WhatIf 重跑。" Cyan
} else {
    Say "  ▶ 脚本执行完毕。固证与备份：$BackupRoot" Cyan
}
