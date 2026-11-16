try {
  $ErrorActionPreference = 'Stop'
  $raw = [Console]::In.ReadToEnd()
  if ([string]::IsNullOrWhiteSpace($raw)) { exit 0 }
  try { $j = $raw | ConvertFrom-Json } catch { exit 0 }
  $tool = [string]$j.tool_name
# ZHUOPIN_READONLY_HOTFIX_V1
  # Only explicit reads in this repository bypass the old path-only test.
  # Any missing/changed helper or exception falls back to the original guard.
  try {
    $readHelper = 'C:\Dev\zhuopin-ai\0-学习与工具\codex-handoff\readonly_guard_hotfix.ps1'
    if ((Get-FileHash -LiteralPath $readHelper -Algorithm SHA256).Hash -eq '84266b186b0cc53655bee63ae6f34531c9decf6a9f1adb71d4d2edfc6066a55b') {
      . $readHelper
      if (Test-ZhuopinReadOnlyHookEvent -Event $j -RepoRoot 'C:\Dev\zhuopin-ai') { exit 0 }
    }
  } catch { }
  # END_ZHUOPIN_READONLY_HOTFIX_V1
  $ti   = $j.tool_input
  $targets = @()
  if ($ti.file_path)     { $targets += [string]$ti.file_path }
  if ($ti.path)          { $targets += [string]$ti.path }
  if ($ti.notebook_path) { $targets += [string]$ti.notebook_path }
  if ($ti.command)       { $targets += [string]$ti.command }
  if ($ti.edits)         { foreach ($e in $ti.edits) { if ($e.file_path) { $targets += [string]$e.file_path } } }
  if (-not $targets) { exit 0 }
  $cfgPath = Join-Path $PSScriptRoot 'protected-paths.json'
  if (-not (Test-Path $cfgPath)) { exit 0 }
  $cfg = Get-Content $cfgPath -Raw -Encoding UTF8 | ConvertFrom-Json
  $mode = if ($cfg.mode) { [string]$cfg.mode } else { 'block' }
  $patterns = @($cfg.patterns)
  if (-not $patterns) { exit 0 }
  function Norm([string]$s) { ($s -replace '\\','/').ToLowerInvariant() }
  $hit = $null; $hitTarget = $null
  foreach ($t in $targets) {
    $n = Norm $t
    foreach ($p in $patterns) {
      if ($n -like (Norm ([string]$p))) { $hit = [string]$p; $hitTarget = $t; break }
    }
    if ($hit) { break }
  }
  if (-not $hit) { exit 0 }
  try {
    $dir = Join-Path $PSScriptRoot '../../../reports/codex-hooks'
    if (-not (Test-Path -LiteralPath $dir)) { New-Item -ItemType Directory -Path $dir -Force | Out-Null }
    $blog = Join-Path $dir ("audit-blocks-{0:yyyyMMdd}.log" -f (Get-Date))
    $ts = (Get-Date).ToString('o'); $sid = [string]$j.session_id
    $st = ($hitTarget -replace '[\r\n\t]+',' ').Trim()
    $sp = ($hit -replace '[\r\n\t]+',' ').Trim()
    $u = New-Object System.Text.UTF8Encoding($false)
    [System.IO.File]::AppendAllText($blog, "$ts`t$mode`t$tool`t$sid`t$st`t$sp`r`n", $u)
  } catch { }
  if ($mode -eq 'warn') {
    [Console]::Error.WriteLine("[警告] 目标命中受保护规则 '$hit'，建议走人工变更流程(warn 模式，未拦截)。")
    exit 0
  }
  [Console]::Error.WriteLine("[拦截] 目标 `"$hitTarget`" 命中受保护规则 `"$hit`"。该文件属 ISO 26262 安全件/审计/关键配置受控范围，禁止经 AI 工具修改；如确需变更请走人工变更流程并留痕。")
  exit 2
} catch { exit 0 }