param([switch]$Full, [string]$TempRoot)
$ErrorActionPreference='Stop'
$repo=(Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '../..')).Path
$config=Get-Content -LiteralPath (Join-Path $repo '.codex/runtime.local.json') -Raw -Encoding UTF8 | ConvertFrom-Json
& $config.python (Join-Path $PSScriptRoot 'quality_handoff.py') --root $repo --domain all --check
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
if (-not $Full) { exit 0 }
if (-not $TempRoot) { $TempRoot=Join-Path ([IO.Path]::GetTempPath()) ('zhuopin-sr-'+[Guid]::NewGuid().ToString('N')) }
$target=[IO.Path]::GetFullPath($TempRoot)
if ($target.TrimEnd('\').Equals($repo,[StringComparison]::OrdinalIgnoreCase) -or $target.StartsWith($repo.TrimEnd('\')+'\',[StringComparison]::OrdinalIgnoreCase)) { throw '完整测试需要仓库外临时目录，避免把外部审批fixture误判成仓库内证据。' }
if (Test-Path -LiteralPath $target) { throw '仅接受尚不存在的专用临时目录，不清理或覆盖旧目录。' }
[IO.Directory]::CreateDirectory($target) | Out-Null
$logRoot=Join-Path $repo ('reports/construction-mechanism-20261030/verify-'+(Get-Date -Format 'yyyyMMdd-HHmmss'))
[IO.Directory]::CreateDirectory($logRoot) | Out-Null
function Get-CandidateHashes {
  $hashes=@{}
  $files=@(Get-ChildItem -LiteralPath $PSScriptRoot -File | Where-Object {$_.Extension -in @('.py','.ps1')})
  $files+=@(Get-ChildItem -LiteralPath (Join-Path $PSScriptRoot 'tests') -Recurse -File -Filter '*.py')
  $files+=@(Get-ChildItem -LiteralPath (Join-Path $repo 'docs/handoff') -Recurse -File | Where-Object {$_.Extension -in @('.json','.md','.bin') -and $_.FullName -notmatch '[\\/](transaction-data|transactions)[\\/]' -and $_.Name -ne '.pending.json'})
  $entries=& $config.python -c 'import sys;sys.path.insert(0,sys.argv[1]);from quality_handoff import DOMAINS;print("\n".join(p["entry"] for p in DOMAINS.values()))' $PSScriptRoot
  if ($LASTEXITCODE -ne 0) { throw '无法绑定接力入口候选哈希' }
  $files+=@($entries | ForEach-Object {Get-Item -LiteralPath (Join-Path $repo $_)})
  $files+=@(Get-Item -LiteralPath (Join-Path $repo '.github/workflows/ci.yml'))
  foreach($file in $files) { $hashes[$file.FullName]=(Get-FileHash -LiteralPath $file.FullName -Algorithm SHA256).Hash }
  return $hashes
}
$oldTemp=$env:TEMP; $oldTmp=$env:TMP
try {
  $env:TEMP=$target; $env:TMP=$target; $env:PYTHONUTF8='1'; $env:PYTHONDONTWRITEBYTECODE='1'
  $tempProbe=& $config.python -c 'from pathlib import Path;import sys;p=Path(sys.argv[1])/"preflight 中文 空格";p.mkdir(mode=0o700);assert p.is_dir();f=p/"utf8.txt";f.write_bytes("核验".encode());assert f.read_bytes()=="核验".encode();f.unlink();p.rmdir()' $target 2>&1
  $probeExit=$LASTEXITCODE
  @{exit=$probeExit;output=($tempProbe -join "`n");temp=$target} | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $logRoot 'temp-preflight.json') -Encoding utf8
  if($probeExit -ne 0) {
    @{exit=2;stage='python-temp-preflight';pytest_started=$false;log=$logRoot} | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $logRoot 'result.json') -Encoding utf8
    Write-Output "测试Python不能写入外部临时目录；pytest未启动。evidence=$logRoot"
    exit 2
  }
  $before=Get-CandidateHashes
  $argv=@('-m','pytest','tests','-q','--tb=short','-p','no:cacheprovider','--basetemp',(Join-Path $target 'pytest'),'--junitxml',(Join-Path $logRoot 'junit.xml'))
  @{python=$config.python;argv=$argv;cwd=$PSScriptRoot;temp=$target;hashes=$before} | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $logRoot 'command.json') -Encoding utf8
  Push-Location -LiteralPath $PSScriptRoot
  try { & $config.python @argv *> (Join-Path $logRoot 'pytest.log'); $result=$LASTEXITCODE } finally { Pop-Location }
  $pytestExit=$result; $after=Get-CandidateHashes
  $drift=@(@($before.Keys)+@($after.Keys) | Sort-Object -Unique | Where-Object {$before[$_] -ne $after[$_]})
  if($drift.Count -gt 0 -and $result -eq 0) { $result=2 }
  @{exit=$result;pytest_exit=$pytestExit;source_drift=$drift;log=$logRoot;completed=(Get-Date -Format o)} | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $logRoot 'result.json') -Encoding utf8
  Write-Output "exit=$result; evidence=$logRoot"
  exit $result
} finally { $env:TEMP=$oldTemp; $env:TMP=$oldTmp }
