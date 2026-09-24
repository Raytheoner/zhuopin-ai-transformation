
param(
 [ValidateSet('Probe','Hook','Workflow','Test')][string]$Mode='Probe',
 [Parameter(ValueFromRemainingArguments=$true)][string[]]$Arguments
)
# A failed Hook launcher must not become an implicitly allowed tool call.
trap {
  if ($Mode -eq 'Hook' -and $hookEventName -notin @('SessionStart','UserPromptSubmit','PostToolUse','Stop')) {
    Write-Output '{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"deny","permissionDecisionReason":"Codex hook launcher failed; inspect runtime configuration."}}'
    exit 0
  }
  [Console]::Error.WriteLine($_.Exception.Message)
  if ($Mode -eq 'Hook') { exit 2 }
  exit 1
}
$ErrorActionPreference='Stop'
$hookInput = $null
$hookEventName = $null
if ($Mode -eq 'Hook') {
  [Console]::InputEncoding = [Text.UTF8Encoding]::new($false)
  $OutputEncoding = [Text.UTF8Encoding]::new($false)
  $hookInput = [Console]::In.ReadToEnd()
  try {
    $hookEnvelope = $hookInput | ConvertFrom-Json -ErrorAction Stop
    if ($hookEnvelope.hook_event_name -is [string]) { $hookEventName = $hookEnvelope.hook_event_name }
  } catch { } # The bridge rejects malformed or unclassifiable input explicitly.
}
$env:PYTHONUTF8='1'
$env:PYTHONDONTWRITEBYTECODE='1'
$repo = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '../..')).Path
$configPath = if ($env:ZHUOPIN_CODEX_RUNTIME) { $env:ZHUOPIN_CODEX_RUNTIME } else { Join-Path $repo '.codex/runtime.local.json' }
if (-not (Test-Path -LiteralPath $configPath)) {
    $common = & git -c "safe.directory=$($repo.Replace('\','/'))" -C $repo rev-parse --git-common-dir
    if ($LASTEXITCODE -ne 0) { throw '不能解析共享仓库runtime' }
    $commonPath = if ([IO.Path]::IsPathRooted($common)) { $common } else { Join-Path $repo $common }
    $configPath = Join-Path (Split-Path ([IO.Path]::GetFullPath($commonPath)) -Parent) '.codex/runtime.local.json'
}
if (-not (Test-Path -LiteralPath $configPath)) { throw "缺少本机运行时配置：$configPath；参见同目录 README.md。" }
$config = Get-Content -LiteralPath $configPath -Raw -Encoding UTF8 | ConvertFrom-Json
if (-not (Test-Path -LiteralPath $config.python)) { throw "运行时不存在：$($config.python)" }
$env:ZHUOPIN_CODEX_RUNTIME = $configPath
$env:ZHUOPIN_CODEX_STATE = $config.state_root
$nodeBin = 'C:\Dev\Codex\runtimes\zhuopin-ai\node\node_modules\.bin'
if (Test-Path -LiteralPath $nodeBin) { $env:PATH = "$nodeBin;$env:PATH" }
$entry = Join-Path $PSScriptRoot 'handoff.py'
if ($Mode -eq 'Hook') {
  $hookInput | & $config.python (Join-Path $PSScriptRoot 'hook_bridge.py')
  if ($LASTEXITCODE -ne 0 -and $hookEventName -notin @('SessionStart','UserPromptSubmit','PostToolUse','Stop')) { throw 'Codex hook bridge failed.' }
} elseif ($Mode -eq 'Test') {
  & $config.python -m pytest (Join-Path $PSScriptRoot 'tests') -q -p no:cacheprovider @Arguments
} elseif ($Mode -eq 'Workflow') {
  & $config.python $entry @Arguments
} else {
  & $config.python $entry probe @Arguments
}
exit $LASTEXITCODE
