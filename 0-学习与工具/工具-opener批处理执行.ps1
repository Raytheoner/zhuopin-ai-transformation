# 旧串行入口原生兼容层；统一调用v2，禁止旧CLI或权限绕过回退。
[CmdletBinding()]
param(
    [string]$Plan = '', [string[]]$Only = @(), [switch]$DryRun,
    [switch]$FullAuto, [switch]$Yes, [string]$Model = 'inherit',
    [switch]$Force, [switch]$ConsumerEnabled
)
$ErrorActionPreference = 'Stop'
$target = Join-Path $PSScriptRoot '工具-opener批处理执行v2.ps1'
& $target @PSBoundParameters -MaxParallel 1 -StaggerSec 0
exit $LASTEXITCODE
