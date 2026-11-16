# Compatibility entry; canonical implementation is Codex-native.
& (Join-Path $PSScriptRoot '../codex-handoff/guards/sentinel-pronoun.ps1') @args
exit $LASTEXITCODE
