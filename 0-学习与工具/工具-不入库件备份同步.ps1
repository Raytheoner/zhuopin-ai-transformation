# ================================================================
#  工具-不入库件备份同步.ps1
#  用途：把仓库里**不入 git 的件**增量同步到 OneDrive 下的备份目录。
#        队列 §一 #412（M1 · T4）产出；Shao Peishen 2026-08-25 定。
#
#  为什么需要它：仓库迁出 OneDrive 之后，根 CLAUDE.md §5 那条「平时全关、
#  每周手动开一次作纯离线备份」的惯例就没有承接物了——.env / 7-外部文档 /
#  各处 reports/ 都在 .gitignore 里，**GitHub 上没有它们**。工作树迁走后，
#  这些件不再被 OneDrive 覆盖 ⇒ 必须另起一条备份路径，否则一次磁盘故障
#  就把专员回件、真实报表与凭据一起带走。
#
#  🔴 边界：本脚本**只备份不入库件**，不备份工作树、不备份 .git。
#     （备份 .git 就等于把 OneDrive 又请回来同步 pack —— 那正是本次迁移要治的病。）
#
#  用法：
#    # 手动跑一次
#    powershell -File "<仓库根>\0-学习与工具\工具-不入库件备份同步.ps1"
#    # 干跑，只打印要同步什么
#    powershell -File "…\工具-不入库件备份同步.ps1" -WhatIf
#
#  注册为每周计划任务见同目录 工具-注册不入库件备份任务.ps1。
# ================================================================
[CmdletBinding()]
param(
    # 仓库根。默认取本脚本上一级（本脚本住在 <仓库根>\0-学习与工具\ 下）。
    [string] $RepoRoot,

    # 备份落点（Shao Peishen 2026-08-25 定：在 OneDrive 内另设「仅不入库件」备份目录）。
    [string] $BackupRoot = "$env:USERPROFILE\OneDrive\Backups\企业AI转型-不入库件",

    [switch] $WhatIf
)

$ErrorActionPreference = "Stop"

if (-not $RepoRoot) { $RepoRoot = Split-Path (Split-Path $PSCommandPath -Parent) -Parent }
if (-not (Test-Path -LiteralPath $RepoRoot)) { Write-Error "仓库根不存在：$RepoRoot"; exit 1 }

$stamp = Get-Date -Format 'yyyy-MM-dd HH:mm:ss'
$logDir = Join-Path $BackupRoot "_logs"
$logFile = Join-Path $logDir ("sync-" + (Get-Date -Format 'yyyyMMdd-HHmmss') + ".log")

Write-Host "`n== 不入库件备份同步 ==" -ForegroundColor Cyan
Write-Host "   仓库根 : $RepoRoot"
Write-Host "   备份到 : $BackupRoot"
Write-Host "   时间   : $stamp$(if ($WhatIf) { '   [-WhatIf 干跑]' })`n"

# ── 同步项 ──
#  每项：Rel＝仓库内相对路径；Kind＝Dir/File；Recurse＝目录是否整树同步
$items = @(
    [pscustomobject]@{ Rel = ".env";        Kind = 'File'; Desc = "凭据（WECOM_WEBHOOK_URL / SRM / U9C 等）" }
    [pscustomobject]@{ Rel = "7-外部文档";  Kind = 'Dir';  Desc = "专员回件与外部正式材料（R6 归集地）" }
)

$copied = 0
$missing = New-Object System.Collections.Generic.List[string]

function Sync-Dir([string] $src, [string] $dst, [string] $label) {
    if ($WhatIf) { Write-Host "   （不执行）robocopy `"$src`" `"$dst`" /E /COPY:DAT /DCOPY:DAT /R:1 /W:1" -ForegroundColor DarkGray; return }
    New-Item -ItemType Directory -Force -Path $dst | Out-Null
    & robocopy $src $dst /E /COPY:DAT /DCOPY:DAT /R:1 /W:1 /NFL /NDL /NP /LOG+:$logFile | Out-Null
    $rc = $LASTEXITCODE
    if ($rc -ge 8) { Write-Error "robocopy 同步 $label 返回 $rc（≥8 即有真实失败）。日志：$logFile"; exit 1 }
    $n = (Get-ChildItem -LiteralPath $dst -Recurse -Force -File -ErrorAction SilentlyContinue).Count
    Write-Host "   ✅ $label  → $n 个文件（robocopy rc=$rc）" -ForegroundColor Green
    $script:copied += $n
}

if (-not $WhatIf) { New-Item -ItemType Directory -Force -Path $logDir | Out-Null }

# ── 1. 固定项 ──
foreach ($it in $items) {
    $src = Join-Path $RepoRoot $it.Rel
    if (-not (Test-Path -LiteralPath $src)) { $missing.Add($it.Rel) | Out-Null; continue }
    $dst = Join-Path $BackupRoot $it.Rel
    if ($it.Kind -eq 'File') {
        if ($WhatIf) { Write-Host "   （不执行）复制文件 $($it.Rel)" -ForegroundColor DarkGray; continue }
        New-Item -ItemType Directory -Force -Path (Split-Path $dst -Parent) | Out-Null
        Copy-Item -LiteralPath $src -Destination $dst -Force
        Write-Host "   ✅ $($it.Rel)  （$($it.Desc)）" -ForegroundColor Green
        $copied++
    } else {
        Sync-Dir $src $dst $it.Rel
    }
}

# ── 2. 全树 reports/ ──
#  🔴 用 -Directory -Filter 逐个找，不用 robocopy 的通配 —— reports/ 散落在
#     各场景目录下（含 worktree 内的），路径含中文与空格，通配容易漏。
$reportDirs = @(Get-ChildItem -LiteralPath $RepoRoot -Recurse -Directory -Force -Filter "reports" -ErrorAction SilentlyContinue |
    Where-Object { $_.FullName -notlike "*\.git\*" })
Write-Host "`n   找到 reports 目录 $($reportDirs.Count) 个" -ForegroundColor Yellow
foreach ($d in $reportDirs) {
    $rel = $d.FullName.Substring($RepoRoot.Length).TrimStart('\')
    Sync-Dir $d.FullName (Join-Path $BackupRoot $rel) $rel
}

# ── 3. .env（各 worktree / 场景各自独立，不共用）──
$envFiles = @(Get-ChildItem -LiteralPath $RepoRoot -Recurse -File -Force -Filter ".env" -ErrorAction SilentlyContinue |
    Where-Object { $_.FullName -notlike "*\.git\*" })
Write-Host "`n   找到 .env 文件 $($envFiles.Count) 个" -ForegroundColor Yellow
foreach ($f in $envFiles) {
    $rel = $f.FullName.Substring($RepoRoot.Length).TrimStart('\')
    if ($WhatIf) { Write-Host "   （不执行）复制 $rel" -ForegroundColor DarkGray; continue }
    $dst = Join-Path $BackupRoot $rel
    New-Item -ItemType Directory -Force -Path (Split-Path $dst -Parent) | Out-Null
    Copy-Item -LiteralPath $f.FullName -Destination $dst -Force
    Write-Host "   ✅ $rel" -ForegroundColor Green
    $copied++
}

# ── 收尾 ──
if ($missing.Count) {
    Write-Host "`n   ⚠ 以下固定项在仓库内不存在（如属预期可忽略）：" -ForegroundColor Yellow
    $missing | ForEach-Object { Write-Host "     · $_" -ForegroundColor Yellow }
}

if ($WhatIf) {
    Write-Host "`n   ▶ 以上为 -WhatIf 干跑，未复制任何文件。" -ForegroundColor Cyan
} else {
    $marker = Join-Path $BackupRoot "_LAST-SYNC.txt"
    Set-Content -LiteralPath $marker -Value "最后同步：$stamp`n仓库根：$RepoRoot`n本次落盘文件数（含增量前已有）：$copied" -Encoding UTF8
    Write-Host "`n   ▶ 同步完成。新鲜度标记：$marker" -ForegroundColor Cyan
    Write-Host "     （根 CLAUDE.md §5「最多一周旧」的判据此后读这个文件，不再靠人记得开没开 OneDrive）" -ForegroundColor DarkGray
}
