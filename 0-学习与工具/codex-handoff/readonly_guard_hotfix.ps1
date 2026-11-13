# Narrow read-only exception for the existing protected-path guard.
# Dot-source only after verifying the SHA256 recorded by the installer.
function Test-ZhuopinReadOnlyHookEvent {
    param($Event, [string]$RepoRoot)
    try {
        if (-not $Event.cwd -or -not $RepoRoot) { return $false }
        $root = [IO.Path]::GetFullPath($RepoRoot).TrimEnd('\','/')
        $cwd = [IO.Path]::GetFullPath([string]$Event.cwd).TrimEnd('\','/')
        if (-not ($cwd.Equals($root,[StringComparison]::OrdinalIgnoreCase) -or
            $cwd.StartsWith($root+[IO.Path]::DirectorySeparatorChar,[StringComparison]::OrdinalIgnoreCase))) {
            return $false
        }
        $tool = [string]$Event.tool_name
        if ($tool -in @('Read','Grep','Glob')) { return $true }
        if ($tool -notin @('Bash','PowerShell','exec_command','functions.exec_command')) { return $false }
        $inputObject = $Event.tool_input
        $command = if ($inputObject.cmd) { [string]$inputObject.cmd } else { [string]$inputObject.command }
        if ([string]::IsNullOrWhiteSpace($command) -or $command.Length -gt 32768) { return $false }
        $tokens=$null; $parseErrors=$null
        $ast=[Management.Automation.Language.Parser]::ParseInput($command,[ref]$tokens,[ref]$parseErrors)
        if ($parseErrors.Count -or $ast.BeginBlock -or $ast.ProcessBlock -or $ast.ParamBlock) { return $false }
        $unsafe=@($ast.FindAll({param($n)
            $n -is [Management.Automation.Language.AssignmentStatementAst] -or
            $n -is [Management.Automation.Language.RedirectionAst] -or
            $n -is [Management.Automation.Language.InvokeMemberExpressionAst] -or
            $n -is [Management.Automation.Language.MemberExpressionAst] -or
            $n -is [Management.Automation.Language.ScriptBlockExpressionAst] -or
            $n -is [Management.Automation.Language.SubExpressionAst] -or
            $n -is [Management.Automation.Language.VariableExpressionAst] -or
            $n -is [Management.Automation.Language.TypeExpressionAst]
        },$true))
        if ($unsafe.Count) { return $false }
        $statements=@($ast.EndBlock.Statements)
        if (-not $statements.Count -or $ast.EndBlock.Traps.Count) { return $false }
        $allowed=@('Get-Content','gc','cat','type','Get-Item','Get-ChildItem','ls','dir',
            'Test-Path','Select-String','Select-Object','Get-Date','Get-FileHash',
            'Write-Output','Out-String','Format-Table','Format-List')
        foreach ($statement in $statements) {
            if ($statement -isnot [Management.Automation.Language.PipelineAst]) { return $false }
            foreach ($node in $statement.PipelineElements) {
                if ($node -isnot [Management.Automation.Language.CommandAst] -or
                    $node.InvocationOperator -ne [Management.Automation.Language.TokenKind]::Unknown -or
                    $node.GetCommandName() -notin $allowed) { return $false }
            }
        }
        return $true
    } catch { return $false }
}
