# Standalone behavioral test. Every network/deployment command is mocked.
$ErrorActionPreference = 'Stop'
$testBase = [IO.Path]::GetFullPath([IO.Path]::GetTempPath())
$testRoot = Join-Path $testBase ('sales-publish-test-' + [guid]::NewGuid().ToString('N'))
$fixtureCC = Join-Path $testRoot 'repo\1-转型规划\AI运营指挥中心'
$fakeServer = Join-Path $testRoot 'fake-server\sales_dashboard_data.json'
$global:SalesPublishFixture = @{
    Copies = [Collections.Generic.List[string]]::new()
    Restarts = 0
    Conversions = 0
    ServerFile = $fakeServer
}

# These functions shadow executables/cmdlets in the script under test.
function Import-Module { param($Name, [switch]$Force) }
function Publish-ZhuopinDeployToolsModule { param($SshAlias, $ServerBase) }
function Restart-ZhuopinTask {
    param($TaskName, $CheckMode, $Port)
    $global:SalesPublishFixture.Restarts++
    return @{ Ok = $true }
}
function ssh { $global:LASTEXITCODE = 0 }
function python { $global:SalesPublishFixture.Conversions++; $global:LASTEXITCODE = 0 }
function scp {
    param($Source, $Target)
    $global:SalesPublishFixture.Copies.Add($Target)
    if ($Target.EndsWith('/data/sales_dashboard_data.json')) {
        Copy-Item -LiteralPath $Source -Destination $global:SalesPublishFixture.ServerFile
    }
    $global:LASTEXITCODE = 0
}

try {
    New-Item -ItemType Directory -Path (Join-Path $fixtureCC 'data') -Force | Out-Null
    New-Item -ItemType Directory -Path (Split-Path $fakeServer -Parent) -Force | Out-Null
    Copy-Item -LiteralPath (Join-Path $PSScriptRoot '..\sync-to-server.ps1') -Destination $fixtureCC
    Set-Content -LiteralPath (Join-Path $fixtureCC 'AI运营指挥中心-框架原型-test.html') -Value '<html>fixture</html>' -Encoding utf8
    Set-Content -LiteralPath (Join-Path $fixtureCC 'data\sales_dashboard_data.json') -Value '{"sync_time":"2026-06-25"}' -Encoding utf8
    Set-Content -LiteralPath $fakeServer -Value '{"sync_time":"2026-10-11T08:00:00+08:00"}' -Encoding utf8
    $before = [IO.File]::ReadAllText($fakeServer)

    & (Join-Path $fixtureCC 'sync-to-server.ps1')

    if ([IO.File]::ReadAllText($fakeServer) -ne $before) {
        throw 'FAIL: site publication overwrote the newer server sales snapshot'
    }
    if ($global:SalesPublishFixture.Conversions -ne 0) { throw 'FAIL: site publication invoked the notebook sales converter' }
    if (-not ($global:SalesPublishFixture.Copies -contains 'supplychain-server:C:/command-center/index.html')) {
        throw 'FAIL: the normal portal page publication was removed'
    }
    if ($global:SalesPublishFixture.Restarts -ne 1) { throw 'FAIL: the existing site restart flow changed' }
    Write-Host 'PASS: portal publication keeps the server sales snapshot and existing site flow'
}
finally {
    # Remove only this test's newly created, resolved absolute fixture directory.
    $resolvedTest = [IO.Path]::GetFullPath($testRoot)
    $prefix = $testBase.TrimEnd('\', '/') + [IO.Path]::DirectorySeparatorChar
    if (-not $resolvedTest.StartsWith($prefix, [StringComparison]::OrdinalIgnoreCase) -or
        -not ([IO.Path]::GetFileName($resolvedTest).StartsWith('sales-publish-test-'))) {
        throw 'Unsafe fixture cleanup target'
    }
    if (Test-Path -LiteralPath $resolvedTest) { Remove-Item -LiteralPath $resolvedTest -Recurse -Force }
    Remove-Variable -Name SalesPublishFixture -Scope Global
}
