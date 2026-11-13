# 兼容参数及证据输入；现役实现只接受历史 JSON，不再探测旧安装或启动 CLI。
param([switch]$Json,[switch]$BannerLine,[switch]$Quiet)
$previous = $env:ZHUOPIN_PACKAGE_EVIDENCE_JSON
try {
    if (-not $previous -and $env:ZHUOPIN_CLAUDE_PROBE_FAKE) {
        $env:ZHUOPIN_PACKAGE_EVIDENCE_JSON = $env:ZHUOPIN_CLAUDE_PROBE_FAKE
    }
    & (Join-Path $PSScriptRoot '工具-历史包读数核对.ps1') @PSBoundParameters
    $result = $LASTEXITCODE
} finally { $env:ZHUOPIN_PACKAGE_EVIDENCE_JSON = $previous }
exit $result
