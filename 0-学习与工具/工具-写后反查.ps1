<#
.SYNOPSIS
  写后反查三件套（队列 #255，2026-08-06）——把「不信工具说成功了，写完必反查
  落盘」从人守规则变成机制守的②工具化部分。

.DESCRIPTION
  背景：2026-08-05 环境保障线单 session 内 4 次违反"写完必反查落盘"这条纯
  人守规则；凡是真反查了的都当场抓到了问题（Edit 对 outputs 报 success 但
  零落盘 / Write 对 Cowork memory 报 success 但零落盘 / #254 队列行插错分区），
  凡是没反查的就漏过去了——命中率完全取决于当时记不记得，属 CLAUDE.md §5
  规则退休制点名要淘汰的形态。这类失效的共同形态是"不报错，只是安静地
  给出反向答案"（同 §5「工具静默回退」）。

  本脚本只做只读校验，不写入任何内容：给定路径与期望关键词，检查
  ① 文件存在（Test-Path）② 若提供 -BeforeBytes 则报告写前写后字节数
  变化（仅提示，不作为失败判据——同长度替换合法存在）③ 文件内容含期望
  关键词（Select-String，至少命中一次）。三项里只有①③是硬性失败判据，
  ②纯提示。

  本工具是可选的机制化通道，不设为强制写入路径（若设为强制，将触及
  "改变现有写入流程的对外语义"，按 CLAUDE.md §5 机制类触发门槛须走
  openspec + design 审——本次未做此扩展，见队列 #255 design 边界说明）。

.PARAMETER Path
  待反查的文件绝对路径。

.PARAMETER Keyword
  预期应出现在文件内容中的关键词（字面子串匹配，非正则）。

.PARAMETER BeforeBytes
  可选：写入前的文件字节数（不存在则传 -1 或不传），用于打印写前写后
  差异提示,不参与失败判定。

.EXAMPLE
  # 轻量①（一行可复制 PowerShell 片段，不依赖本脚本）：
  $before = if (Test-Path $path) { (Get-Item $path).Length } else { -1 }
  # ...执行写入...
  if (-not (Test-Path $path)) { throw "✗ 写后反查失败：$path 不存在" }
  if (-not (Select-String -Path $path -Pattern ([regex]::Escape($keyword)) -Quiet)) {
      throw "✗ 写后反查失败：未在 $path 中找到预期关键词「$keyword」"
  }
  Write-Host "✓ 写后反查通过：$path"

.EXAMPLE
  # ②工具化：
  pwsh -File "0-学习与工具/工具-写后反查.ps1" -Path "C:\...\目标.md" -Keyword "预期关键词" -BeforeBytes 1024
#>
param(
    [Parameter(Mandatory = $true)]
    [string]$Path,

    [Parameter(Mandatory = $true)]
    [string]$Keyword,

    [long]$BeforeBytes = -1
)

if (-not (Test-Path -LiteralPath $Path)) {
    Write-Error "✗ 写后反查失败：文件不存在——$Path（工具可能报了 success 但零落盘，见队列 #255）"
    exit 1
}

$afterBytes = (Get-Item -LiteralPath $Path).Length

if ($BeforeBytes -ge 0) {
    if ($afterBytes -eq $BeforeBytes) {
        Write-Warning "⚠ 写前写后字节数相同（$BeforeBytes → $afterBytes）——可能是同长度替换（正常），也可能是根本没写入（可疑），仅提示不作为失败判据，请结合关键词命中结果判断。"
    } else {
        Write-Host "写前写后字节数：$BeforeBytes → $afterBytes"
    }
}

$hits = (Select-String -LiteralPath $Path -Pattern ([regex]::Escape($Keyword)) -AllMatches -ErrorAction SilentlyContinue)
$hitCount = if ($hits) { ($hits | Measure-Object).Count } else { 0 }

if ($hitCount -eq 0) {
    Write-Error "✗ 写后反查失败：未在 $Path 中找到预期关键词「$Keyword」——工具可能报了 success，但内容并非预期写入（见队列 #255）。"
    exit 2
}

Write-Host "✓ 写后反查通过：$Path（关键词「$Keyword」命中 $hitCount 次，字节数 $afterBytes）"
exit 0
