# Versioned native sweep entry. Preview by default; production Run is main-only.
[CmdletBinding()]
param([switch]$Run, [switch]$VerifyOnly)

Set-StrictMode -Version 2.0
$ErrorActionPreference = 'Stop'
try { [Console]::OutputEncoding = New-Object Text.UTF8Encoding $false } catch { }

$toolsRoot = Split-Path -Parent $PSScriptRoot
$codeRoot = Split-Path -Parent $toolsRoot
$sweepPath = Join-Path $toolsRoot '工具-落库sweep.py'

function Reject-Launcher([string]$Reason) {
    [pscustomobject]@{ status = 'launcher-rejected'; reason = $Reason } | ConvertTo-Json -Compress
    exit 9
}

function Read-LauncherGit([string[]]$GitArguments) {
    $value = & $script:gitExe -C $script:codeRoot @GitArguments 2>$null
    $nativeExit = $LASTEXITCODE
    if ($nativeExit -ne 0) { throw 'Git metadata unavailable' }
    return (($value -join "`n").Trim())
}

try {
    if ($Run -and $VerifyOnly) { Reject-Launcher 'run-and-verify-conflict' }
    if (-not (Test-Path -LiteralPath $sweepPath -PathType Leaf)) { Reject-Launcher 'sweep-missing' }

    $gitCommand = Get-Command git -CommandType Application -ErrorAction SilentlyContinue | Select-Object -First 1
    $gitExe = if ($gitCommand) { $gitCommand.Source } else { Join-Path $env:ProgramFiles 'Git/cmd/git.exe' }
    if (-not (Test-Path -LiteralPath $gitExe -PathType Leaf)) { Reject-Launcher 'git-missing' }
    $branch = Read-LauncherGit -GitArguments @('branch', '--show-current')
    if ($Run -and -not ($branch -cin @('master', 'main'))) { Reject-Launcher 'run-requires-main-branch' }

    $runtimePath = Join-Path $codeRoot '.codex/runtime.local.json'
    if (-not (Test-Path -LiteralPath $runtimePath -PathType Leaf)) {
        $commonDir = Read-LauncherGit -GitArguments @('rev-parse', '--path-format=absolute', '--git-common-dir')
        $runtimePath = Join-Path (Split-Path -Parent $commonDir) '.codex/runtime.local.json'
    }
    if (-not (Test-Path -LiteralPath $runtimePath -PathType Leaf)) { Reject-Launcher 'runtime-missing' }
    $runtime = Get-Content -LiteralPath $runtimePath -Raw -Encoding UTF8 | ConvertFrom-Json
    if ($null -eq $runtime -or $null -eq $runtime.PSObject.Properties['python']) { Reject-Launcher 'runtime-python-missing' }
    $pythonExe = [string]$runtime.python
    $pythonRoot = [IO.Path]::GetPathRoot($pythonExe)
    if ($pythonRoot.Length -ne 3 -or $pythonRoot -notmatch '^[A-Za-z]:') { Reject-Launcher 'runtime-python-not-absolute-local-path' }
    $pythonFile = Get-Item -LiteralPath $pythonExe -ErrorAction SilentlyContinue
    if (-not $pythonFile -or $pythonFile.PSIsContainer -or $pythonFile.Name -ine 'python.exe' -or $pythonFile.Length -eq 0 -or
        ($pythonFile.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) { Reject-Launcher 'runtime-python-invalid' }

    if (-not $Run) {
        [pscustomobject]@{
            mode = 'verify-only'; code_root = $codeRoot; branch = $branch
            sweep_path = $sweepPath; runtime_path = $runtimePath; python_executable = $pythonExe
            sweep_arguments = @()
        } | ConvertTo-Json -Depth 4 -Compress
        exit 0
    }

    & $pythonExe $sweepPath
    $sweepExit = $LASTEXITCODE
    if ($null -eq $sweepExit) { Reject-Launcher 'sweep-not-started' }
    exit ([int]$sweepExit)
} catch {
    Reject-Launcher 'launcher-validation-or-start-error'
}
