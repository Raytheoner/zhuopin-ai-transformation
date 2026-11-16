# Compatibility entry; canonical implementation is Codex-native.
& (Join-Path $PSScriptRoot '../codex-handoff/guards/hooks-pretooluse-queue-read-guard.ps1') @args
exit $LASTEXITCODE
