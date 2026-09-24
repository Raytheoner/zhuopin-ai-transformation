
param(
 [ValidateSet('Probe','Hook','Workflow','Test')][string]$Mode='Probe',
 [Parameter(ValueFromRemainingArguments=$true)][string[]]$Arguments
)
$ErrorActionPreference='Stop'
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
  & $config.python (Join-Path $PSScriptRoot 'hook_bridge.py')
} elseif ($Mode -eq 'Test') {
  & $config.python -m pytest (Join-Path $PSScriptRoot 'tests') -q -p no:cacheprovider @Arguments
} elseif ($Mode -eq 'Workflow') {
  & $config.python $entry @Arguments
} else {
  & $config.python $entry probe @Arguments
}
exit $LASTEXITCODE
