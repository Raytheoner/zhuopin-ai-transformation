param([switch]$Full,[string]$TempRoot)
$ErrorActionPreference='Stop'
$repo=(Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '../..')).Path
$config=Get-Content -LiteralPath (Join-Path $repo '.codex/runtime.local.json') -Raw -Encoding UTF8 | ConvertFrom-Json
$stamp=(Get-Date -Format 'yyyyMMdd-HHmmss-fff')+'-'+[Guid]::NewGuid().ToString('N').Substring(0,6)
$logs=Join-Path $repo ('reports/hook-optimization-20261031/verify-'+$stamp)
[IO.Directory]::CreateDirectory($logs) | Out-Null
$oldTemp=$env:TEMP;$oldTmp=$env:TMP
function CandidateHashes {
    $paths=@(Get-ChildItem -LiteralPath $PSScriptRoot -File | Where-Object {$_.Extension -in @('.py','.ps1')})
    $paths+=@(Get-ChildItem -LiteralPath (Join-Path $PSScriptRoot 'tests') -Recurse -File -Filter '*.py')
    $paths+=@(Get-ChildItem -LiteralPath (Join-Path $repo '0-学习与工具/hooks') -File -Filter '*.ps1')
    $paths+=@(Get-ChildItem -LiteralPath (Join-Path $repo '0-学习与工具') -File -Filter 'test_hooks*.py')
    $paths+=@(Get-Item -LiteralPath (Join-Path $repo '.claude/settings.json'),(Join-Path $repo '.codex/hooks.json'))
    $value=@{};foreach($path in $paths){$value[$path.FullName]=(Get-FileHash -LiteralPath $path.FullName -Algorithm SHA256).Hash}
    return $value
}
try {
    $env:PYTHONUTF8='1';$env:PYTHONDONTWRITEBYTECODE='1'
    if($Full) {
        if(-not $TempRoot){$TempRoot=Join-Path ([IO.Path]::GetTempPath()) ('hook-full-'+[Guid]::NewGuid().ToString('N'))}
        $target=[IO.Path]::GetFullPath($TempRoot)
        if($target.Equals($repo,[StringComparison]::OrdinalIgnoreCase) -or $target.StartsWith($repo.TrimEnd('\')+'\',[StringComparison]::OrdinalIgnoreCase)){throw '全量测试必须使用仓库外临时目录；不能规避外部审批证据边界。'}
        if(Test-Path -LiteralPath $target){throw '只接受新专用目录，不删除或复用旧现场。'}
        [IO.Directory]::CreateDirectory($target) | Out-Null
        $probe=& $config.python -c 'from pathlib import Path;import sys;p=Path(sys.argv[1])/"pytest mode700 中文";p.mkdir(mode=0o700);assert p.is_dir();f=p/"probe.txt";f.write_bytes(b"test");assert f.read_bytes()==b"test";f.unlink();p.rmdir()' $target 2>&1
        $probeExit=$LASTEXITCODE
        @{exit=$probeExit;output=($probe -join "`n");temp=$target;python=$config.python} | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $logs 'preflight.json') -Encoding utf8
        if($probeExit -ne 0){
            @{exit=2;stage='external-pytest-temp-preflight';pytest_started=$false;full_verified=$false} | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $logs 'result.json') -Encoding utf8
            Write-Output "exit=2; 全量测试未启动，Python外部临时目录权限失败；证据=$logs";exit 2
        }
        $env:TEMP=$target;$env:TMP=$target
    } else {
        $target=Join-Path $logs 'fixtures'
        [IO.Directory]::CreateDirectory($target) | Out-Null
        $env:TEMP=$target;$env:TMP=$target
    }
    $before=CandidateHashes
    $before | ConvertTo-Json -Depth 3 | Set-Content -LiteralPath (Join-Path $logs 'candidate-before.json') -Encoding utf8
    $projects=@(
        @{name='tools';cwd=(Join-Path $repo '0-学习与工具');focus=@('test_hooks-pretooluse-queue-read-guard.py','test_hooks-native-read-scope.py','test_hooks-stop-numeric.py','test_hooks-p3.py','test_工具-CLAUDE进度段lint.py')},
        @{name='handoff';cwd=$PSScriptRoot;focus=@('tests/test_handoff.py','tests/test_hook_identity.py','tests/test_hook_launcher.py','tests/test_hook_optimization.py','tests/test_hook_configuration.py','tests/test_hook_log_archive.py')}
    )
    $results=@();$exitCode=0
    foreach($project in $projects){
        $arguments=@('-m','pytest')
        if(-not $Full){$arguments+=@($project.focus)}
        $arguments+=@('-q','--tb=short','-p','no:cacheprovider','--basetemp',(Join-Path $target $project.name),'--junitxml',(Join-Path $logs ($project.name+'.xml')))
        @{python=$config.python;argv=$arguments;cwd=$project.cwd;full=[bool]$Full} | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath (Join-Path $logs ($project.name+'-command.json')) -Encoding utf8
        Push-Location -LiteralPath $project.cwd
        try {& $config.python @arguments *> (Join-Path $logs ($project.name+'.log'));$code=$LASTEXITCODE} finally {Pop-Location}
        $results+=@{project=$project.name;exit=$code}
        if($code -ne 0){$exitCode=2}
    }
    $after=CandidateHashes
    $drift=@(@($before.Keys)+@($after.Keys) | Sort-Object -Unique | Where-Object {$before[$_] -ne $after[$_]})
    if($drift.Count){$exitCode=2}
    $after | ConvertTo-Json -Depth 3 | Set-Content -LiteralPath (Join-Path $logs 'candidate-after.json') -Encoding utf8
    @{exit=$exitCode;full_requested=[bool]$Full;full_verified=([bool]$Full -and $exitCode -eq 0);source_drift=$drift;projects=$results} | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $logs 'result.json') -Encoding utf8
    Write-Output "exit=$exitCode; evidence=$logs";exit $exitCode
} finally {$env:TEMP=$oldTemp;$env:TMP=$oldTmp}
