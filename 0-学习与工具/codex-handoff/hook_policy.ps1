param(
    [Parameter(Mandatory=$true)][ValidateSet('Protected','Mail')][string]$Kind,
    [Parameter(Mandatory=$true)][string]$RepoRoot,
    [Parameter(Mandatory=$true)][string]$LegacyGuard
)
# Native guard authority is mandatory. LegacyGuard is a caller ABI alias only.
$ErrorActionPreference = 'Stop'
$raw = [Console]::In.ReadToEnd()
try {
    $j = $raw | ConvertFrom-Json
    $root = [IO.Path]::GetFullPath($RepoRoot).TrimEnd('\','/')
    $cwd = [IO.Path]::GetFullPath([string]$j.cwd).TrimEnd('\','/')
    $inside = $cwd.Equals($root,[StringComparison]::OrdinalIgnoreCase) -or
        $cwd.StartsWith($root+[IO.Path]::DirectorySeparatorChar,[StringComparison]::OrdinalIgnoreCase)
    # Always select owned native sources, even if the route directory is missing.
    $nativeName = if ($Kind -eq 'Protected') { 'protected-native.ps1' } else { 'mail-native.ps1' }
    $nativeGuard = Join-Path $PSScriptRoot ('guards/' + $nativeName)
    $nativePolicy = Join-Path $PSScriptRoot 'guards/protected-paths.json'
    if (-not (Test-Path -LiteralPath $nativeGuard) -or -not (Test-Path -LiteralPath $nativePolicy)) { throw 'native guard source unavailable' }
    $nativeCfg = Get-Content -LiteralPath $nativePolicy -Raw -Encoding UTF8 | ConvertFrom-Json
    if ($nativeCfg.mode -notin @('block','warn') -or -not @($nativeCfg.patterns).Count) { throw 'native protected policy invalid' }
    $LegacyGuard = $nativeGuard
    if ($inside) {
        $tool = [string]$j.tool_name
        if ($Kind -eq 'Mail' -and $tool -eq 'mcp__codex_apps__microsoft_outlook_email_send_email') {
            # The new connector has no verified legacy save_only contract.
            @{hookSpecificOutput=@{hookEventName='PreToolUse';permissionDecision='deny';permissionDecisionReason='本仓库原生邮件发送守卫：未核验草稿/人工发送授权契约；转人工确认，不自动发送。'}} |
                ConvertTo-Json -Depth 4 -Compress
            exit 0
        }
        if ($Kind -eq 'Protected') {
            if ($tool -in @('Read','Grep','Glob')) { exit 0 }
            $ti = $j.tool_input
            if ($tool -in @('exec_command','functions.exec_command','Bash','PowerShell')) {
                $command = if ($ti.cmd) { [string]$ti.cmd } else { [string]$ti.command }
                $tokens=$null; $errors=$null
                $ast=[Management.Automation.Language.Parser]::ParseInput($command,[ref]$tokens,[ref]$errors)
                $commands=@($ast.FindAll({param($n) $n -is [Management.Automation.Language.CommandAst]},$true))
                $unsafe=@($ast.FindAll({param($n)
                    $n -is [Management.Automation.Language.RedirectionAst] -or
                    $n -is [Management.Automation.Language.InvokeMemberExpressionAst] -or
                    $n -is [Management.Automation.Language.ScriptBlockExpressionAst]
                },$true))
                $readOnly=$commands.Count -gt 0 -and -not $errors.Count -and -not $unsafe.Count
                foreach($node in $commands) {
                    if ($node.GetCommandName() -notin @('Get-Content','gc','cat','type','Get-Item','Get-ChildItem','Test-Path','Select-String','Select-Object','Write-Output','Get-Date','Get-FileHash')) {
                        $readOnly=$false
                    }
                }
                if($readOnly) { exit 0 }
                $cfgPath=$nativePolicy
                $cfg=Get-Content -LiteralPath $cfgPath -Raw -Encoding UTF8 | ConvertFrom-Json
                $norm=$command.Replace('\','/').ToLowerInvariant()
                foreach($pattern in $cfg.patterns) {
                    $needle=([string]$pattern).Replace('\','/').ToLowerInvariant().Trim('*').TrimStart('/')
                    if($needle -and $norm -like ('*'+$needle+'*')) {
                        [Console]::Error.WriteLine('命令可能写入受保护配置；只读已单独放行，写入须人工受控变更。')
                        if($cfg.mode -eq 'warn') { exit 0 }
                        exit 2
                    }
                }
                # Add the native field that the old guard never inspected.
                $j.tool_input = @{command=$command}
                $raw=$j | ConvertTo-Json -Depth 40 -Compress
            } elseif ($tool -in @('apply_patch','functions.apply_patch')) {
                $patch=if($ti -is [string]){$ti}else{
                    @($ti.command,$ti.patch,$ti.input) | Where-Object {$_} | Select-Object -First 1
                }
                $paths=@([regex]::Matches([string]$patch,'(?m)^\*\*\* (?:Add File|Update File|Delete File|Move to): (.+)\r?$') | ForEach-Object {$_.Groups[1].Value.TrimEnd("`r")})
                if(-not $paths.Count) { throw 'unrecognized patch targets' }
                $targets=@($paths | ForEach-Object {
                    $p=if([IO.Path]::IsPathRooted($_)){$_}else{Join-Path $cwd $_}
                    @{file_path=[IO.Path]::GetFullPath($p)}
                })
                $j.tool_input=@{edits=$targets}
                $raw=$j | ConvertTo-Json -Depth 40 -Compress
            }
        }
    }
    # Preserved historical sources are never execution targets. Payload goes over stdin.
    $raw | & pwsh -NoProfile -File $LegacyGuard
    exit $LASTEXITCODE
} catch {
    if($Kind -eq 'Mail') {
        @{hookSpecificOutput=@{hookEventName='PreToolUse';permissionDecision='deny';permissionDecisionReason='邮件守卫解析失败，保留人工确认。'}} | ConvertTo-Json -Depth 4 -Compress
        exit 0
    }
    [Console]::Error.WriteLine('受保护路径适配失败，保留现场并人工核验。')
    exit 2
}
