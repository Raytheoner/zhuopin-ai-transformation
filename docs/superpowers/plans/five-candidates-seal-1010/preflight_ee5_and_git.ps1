[CmdletBinding()]
param(
    [Parameter(Mandatory)][ValidateSet('SC10','SC11')][string]$Lane,
    [Parameter(Mandatory)][ValidateSet('cherry-pick','tests')][string]$Step,
    [Parameter(Mandatory)][string]$AuthorizationPath,
    [Parameter(Mandatory)][string]$RegistrationEvidencePath,
    [Parameter(Mandatory)][string]$NativeRoot,
    [Parameter(Mandatory)][string]$CheckpointPath,
    [Parameter(Mandatory)][string]$EvidencePath
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$MainRoot = 'C:\Dev\zhuopin-ai'
$RootStatusPath = Join-Path $MainRoot '0-学习与工具/codex-handoff/EE5根作业状态-2026-10-10.json'
$FreezeStatusPath = Join-Path $MainRoot '0-学习与工具/codex-handoff/EE5临时状态行冻结与执行-2026-10-10.json'
$AllowedWorktreePrefix = 'C:\Users\Paul Shao\.codex\worktrees\'
$GitExe = 'C:\Program Files\Git\cmd\git.exe'
$FormalScriptPath = Join-Path $MainRoot 'docs/superpowers/plans/five-candidates-seal-1010/preflight_ee5_and_git.ps1'
$EvidenceRoot = [IO.Path]::GetFullPath((Join-Path $MainRoot 'reports/candidate-integration-1010'))
$EvidencePath = [IO.Path]::GetFullPath($EvidencePath)
if (-not $EvidencePath.StartsWith($EvidenceRoot + '\',[StringComparison]::OrdinalIgnoreCase)) { throw 'evidence path outside approved ignored root' }
if (Test-Path -LiteralPath $EvidencePath) { throw 'evidence path already exists; never overwrite' }
if (-not (Test-Path -LiteralPath ([IO.Path]::GetDirectoryName($EvidencePath)) -PathType Container)) { throw 'evidence parent directory must already exist' }
$script:GitCallEvidence = @()

function Get-Sha256([string]$Path) {
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) { throw "missing file: $Path" }
    return (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToUpperInvariant()
}

function Get-Sha256Text([string]$Text) {
    $bytes = [Text.UTF8Encoding]::new($false).GetBytes($Text)
    return [Convert]::ToHexString([Security.Cryptography.SHA256]::HashData($bytes))
}

function Invoke-GitRead([string[]]$GitArgs,[switch]$AllowNoMatch) {
    $global:LASTEXITCODE = 0
    $out = @(& $GitExe --no-pager --no-optional-locks @GitArgs 2>&1)
    $code = $LASTEXITCODE
    $outputText = [string]::Join("`n",@($out | ForEach-Object { [string]$_ }))
    $script:GitCallEvidence += [ordered]@{ argv = @('--no-pager','--no-optional-locks') + $GitArgs; actual_exit = $code; output_line_count = $out.Count; output_sha256 = Get-Sha256Text $outputText }
    if ($code -eq 1 -and $AllowNoMatch) { return }
    if ($code -ne 0) { throw "git read failed (exit=$code; argv=$($GitArgs -join ' '))" }
    return $out
}

function Get-ConfigRecords([string]$Root) {
    $pattern = '^(core\.hookspath|core\.fsmonitor|commit\.gpgsign|gpg\.program|include\.path|includeif\..*\.path|filter\..*\.(clean|smudge|process|required))$'
    $records = @(Invoke-GitRead @('-C',$Root,'config','--show-origin','--get-regexp',$pattern) -AllowNoMatch)
    $safe = @()
    foreach ($line in $records) {
        $text = [string]$line
        if ($text -notmatch '^file:(?<origin>.+?)\t(?<key>\S+)\s+(?<value>.*)$') {
            throw 'unparseable selected git config record'
        }
        $originPath = $Matches.origin
        $key = $Matches.key.ToLowerInvariant()
        $value = $Matches.value
        if ($key -like 'filter.*') {
            if (-not (Test-Path -LiteralPath $originPath -PathType Leaf)) { throw "selected config source unavailable: $originPath" }
            $safe += [ordered]@{ origin = $originPath; source_sha256 = Get-Sha256 $originPath; key = $key; value_sha256 = Get-Sha256Text $value }
            continue
        }
        if ($value -match '(?i)(https?://|token|password|credential|://[^/]*@)') {
            throw "sensitive or unclassifiable value in selected config key: $key"
        }
        if (-not (Test-Path -LiteralPath $originPath -PathType Leaf)) { throw "selected config source unavailable: $originPath" }
        $safe += [ordered]@{ origin = $originPath; source_sha256 = Get-Sha256 $originPath; key = $key; value = $value }
    }
    return $safe
}

function Get-FilterAttributeInventory([string]$Root,[string[]]$Paths) {
    $inventory = @()
    foreach ($path in $Paths) {
        $answer = @(Invoke-GitRead @('-C',$Root,'-c','core.quotepath=false','check-attr','filter','--',$path))
        if ($answer.Count -ne 1) { throw "filter attribute query not singular: $path" }
        $line = [string]$answer[0]
        $prefix = "$path`: filter: "
        if (-not $line.StartsWith($prefix,[StringComparison]::Ordinal)) { throw "filter attribute response path mismatch: $path" }
        $value = $line.Substring($prefix.Length)
        if ($value -notin @('unspecified','unset')) { throw "effective filter attribute active or unknown: $path" }
        $inventory += [ordered]@{ path = $path; filter = $value }
    }
    return $inventory
}

function Test-ConflictStatus([string]$Porcelain) {
    foreach ($line in ($Porcelain -split "`n")) {
        if ($line.StartsWith('u ',[StringComparison]::Ordinal)) { return $true }
        if ($line.StartsWith('1 ',[StringComparison]::Ordinal) -or $line.StartsWith('2 ',[StringComparison]::Ordinal)) {
            $parts = $line.Split(' ')
            if ($parts.Count -gt 1 -and $parts[1].Contains('U')) { return $true }
        }
    }
    return $false
}

function Get-HeadBlobOid([string]$Root,[string]$RelativePath) {
    $lines = @(Invoke-GitRead @('-C',$Root,'ls-tree','--format=%(objectname)','HEAD','--',$RelativePath))
    if ($lines.Count -eq 0 -or [string]::IsNullOrWhiteSpace([string]$lines[0])) { return $null }
    if ($lines.Count -ne 1 -or [string]$lines[0] -notmatch '^[0-9a-f]{40,64}$') { throw "unparseable HEAD blob OID: $RelativePath" }
    return ([string]$lines[0]).Trim()
}

function Get-RawBlobOid([string]$Root,[string]$RelativePath) {
    $lines = @(Invoke-GitRead @('-C',$Root,'hash-object',"--path=$RelativePath",'--',$RelativePath))
    if ($lines.Count -ne 1) { throw "canonical path blob hash was not singular: $RelativePath" }
    return ([string]$lines[0]).Trim()
}

function Test-ExpectedOrSweptClean([string]$Root,[string]$RelativePath,[string]$Porcelain,[string]$ExpectedPorcelain) {
    if (Test-ConflictStatus $Porcelain) { return $false }
    if ($Porcelain -ceq $ExpectedPorcelain.TrimEnd([char[]]"`r`n")) { return $true }
    if ($Porcelain -cne '') { return $false }
    $headBlob = Get-HeadBlobOid $Root $RelativePath
    if ($null -eq $headBlob) { return $false }
    return $headBlob -ceq (Get-RawBlobOid $Root $RelativePath)
}

function Get-HookInventory([string]$Root,[object[]]$Config) {
    $configured = @($Config | Where-Object { $_.key -eq 'core.hookspath' })
    if ($configured.Count -gt 1) { throw 'multiple core.hooksPath entries are unclassifiable' }
    if ($configured.Count -eq 1) {
        $hookPath = [string]$configured[0].value
        if (-not [IO.Path]::IsPathRooted($hookPath)) { $hookPath = Join-Path $Root $hookPath }
    } else {
        $raw = @(Invoke-GitRead @('-C',$Root,'rev-parse','--git-path','hooks'))
        if ($raw.Count -ne 1) { throw 'git hooks directory resolution was not singular' }
        $hookPath = [string]$raw[0]
        if (-not [IO.Path]::IsPathRooted($hookPath)) { $hookPath = Join-Path $Root $hookPath }
    }
    $hookPath = [IO.Path]::GetFullPath($hookPath)
    if (-not (Test-Path -LiteralPath $hookPath -PathType Container)) {
        return [ordered]@{ directory = $hookPath; files = @(); active_or_unknown = @() }
    }
    $files = @()
    $active = @()
    $hookDir = Get-Item -LiteralPath $hookPath -Force
    if (($hookDir.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) { throw 'hook directory is a reparse point' }
    foreach ($file in (Get-ChildItem -LiteralPath $hookPath -File -Force | Sort-Object Name)) {
        if (($file.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) { throw "hook entry is a reparse point: $($file.Name)" }
        $item = [ordered]@{
            name = $file.Name
            bytes = $file.Length
            sha256 = (Get-Sha256 $file.FullName)
            attributes = [string]$file.Attributes
        }
        $files += $item
        if ($file.Name -notlike '*.sample') { $active += $file.Name }
    }
    return [ordered]@{ directory = $hookPath; files = $files; active_or_unknown = $active }
}

$record = [ordered]@{
    schema = 'five-candidate-alignment-preflight/v1'
    lane = $Lane
    step = $Step
    started_local = (Get-Date).ToString('o')
    success = $false
    failure = $null
    authorization_sha256 = $null
    registration_evidence_sha256 = $null
    formal_plan_sha256 = $null
    amendment_sha256 = $null
    native_checkpoint_sha256 = $null
    native_checkpoint = $null
    git = $null
    ee5_root = $null
    ee5_freeze = $null
    main_config = $null
    native_config = $null
    main_filter_attributes = $null
    native_filter_attributes = $null
    main_hooks = $null
    native_hooks = $null
    status_checks = $null
    native_status = $null
    git_commands = @()
}

try {
    if ([IO.Path]::GetFullPath($PSCommandPath) -ine [IO.Path]::GetFullPath($FormalScriptPath)) { throw 'execution is allowed only from the reviewed formal plan-pack script path; ignored draft is not an execution source' }
    $blockedGitEnv = @(Get-ChildItem Env: | Where-Object {
        if ($_.Name -eq 'GIT_PAGER') { return $false }
        if ($_.Name -in @('GIT_OPTIONAL_LOCKS','GIT_TERMINAL_PROMPT') -and $_.Value -ceq '0') { return $false }
        return $_.Name -like 'GIT_*'
    } | ForEach-Object Name)
    if ($blockedGitEnv.Count) { throw "unsupported Git environment controls present: $($blockedGitEnv -join ',')" }

    $authPath = [IO.Path]::GetFullPath($AuthorizationPath)
    $expectedAuthPath = Join-Path $MainRoot '0-学习与工具/codex-handoff/五候选整合批准消费-2026-10-10.json'
    if ($authPath -ne [IO.Path]::GetFullPath($expectedAuthPath)) { throw 'authorization path differs from formal consume path' }
    $authBytes = [IO.File]::ReadAllBytes($authPath)
    $auth = [Text.Encoding]::UTF8.GetString($authBytes) | ConvertFrom-Json -AsHashtable
    $record.authorization_sha256 = Get-Sha256 $authPath
    $registrationPath = [IO.Path]::GetFullPath($RegistrationEvidencePath)
    if (-not $registrationPath.StartsWith($EvidenceRoot + '\',[StringComparison]::OrdinalIgnoreCase) -or
        $registrationPath -ne [IO.Path]::GetFullPath($auth.after_registration_evidence_path)) {
        throw 'registration evidence path differs from the approved auth pointer'
    }
    $registrationBytes = [IO.File]::ReadAllBytes($registrationPath)
    $registration = [Text.Encoding]::UTF8.GetString($registrationBytes) | ConvertFrom-Json -AsHashtable
    $record.registration_evidence_sha256 = Get-Sha256 $registrationPath
    if ($registration.authorization_path -ne $authPath -or
        $registration.authorization_sha256 -ne $record.authorization_sha256 -or
        $registration.formal_plan_sha256 -ne $auth.alignment_plan_sha256) {
        throw 'after-registration evidence does not bind the current auth and formal plan'
    }
    $authControls = @($auth.controls | Sort-Object -Property path -CaseSensitive)
    $registeredControls = @($registration.controls | Sort-Object -Property path -CaseSensitive)
    if ($authControls.Count -ne $registeredControls.Count) { throw 'control registration set differs from approved auth' }
    for ($i = 0; $i -lt $authControls.Count; $i++) {
        if ($authControls[$i].path -cne $registeredControls[$i].path -or
            $authControls[$i].sha256 -ne $registeredControls[$i].sha256 -or
            $authControls[$i].expected_porcelain_v2 -ne $registeredControls[$i].expected_porcelain_v2) {
            throw "registered control binding differs from approved auth: $($authControls[$i].path)"
        }
    }
    if ($auth.approved -ne $true -or $auth.scope_exception -ne 'sealed_candidate_alignment_verification_only' -or
        @($auth.authorized_operations) -notcontains "$Lane`:$Step") {
        throw 'explicit alignment approval or exact scope exception is absent'
    }
    if ($auth.ee5_gate.status -ne 'completed' -or $auth.ee5_gate.ee5_root_operation_active -ne $false -or
        $auth.ee5_gate.word_qa_completed -ne $true -or $auth.ee5_gate.restored -ne $true) {
        throw 'approved EE5 gate snapshot is incomplete or not closed'
    }
    $record.formal_plan_sha256 = Get-Sha256 (Join-Path $MainRoot 'docs/superpowers/plans/2026-10-10-five-candidates-alignment.md')
    $record.amendment_sha256 = Get-Sha256 (Join-Path $MainRoot 'docs/superpowers/plans/five-candidates-seal-1010/alignment-amendment.md')
    if ($record.formal_plan_sha256 -ne $auth.alignment_plan_sha256 -or
        $record.amendment_sha256 -ne $auth.formal_amendment_sha256 -or
        (Get-Sha256 $FormalScriptPath) -ne $auth.preflight_script_sha256) {
        throw 'formal plan/amendment/preflight SHA differs from approved binding'
    }

    $rootSha = Get-Sha256 $RootStatusPath
    $freezeSha = Get-Sha256 $FreezeStatusPath
    $rootStatus = Get-Content -LiteralPath $RootStatusPath -Raw -Encoding UTF8 | ConvertFrom-Json -AsHashtable
    $freezeStatus = Get-Content -LiteralPath $FreezeStatusPath -Raw -Encoding UTF8 | ConvertFrom-Json -AsHashtable
    if ($rootSha -ne $auth.ee5_gate.root_record_sha256 -or $freezeSha -ne $auth.ee5_gate.freeze_record_sha256 -or
        $rootStatus.status -ne 'completed' -or $rootStatus.ee5_root_operation_active -ne $false -or
        $rootStatus.scope_limit -ne '只证明本根EE5作业真实状态；不是§三无冻结证明或场景解冻授权' -or
        $freezeStatus.word_qa_completed -ne $true -or $freezeStatus.restored -ne $true -or
        $freezeStatus.total_table_written -ne $true -or
        $rootStatus.operation_evidence -ne $freezeStatus.operation_evidence) {
        throw 'current EE5 records differ from the approved completed/inactive snapshot'
    }
    $rootStat = Get-Item -LiteralPath $RootStatusPath
    $freezeStat = Get-Item -LiteralPath $FreezeStatusPath
    $record.ee5_root = [ordered]@{ path = $RootStatusPath; sha256 = $rootSha; bytes = $rootStat.Length; mtime_utc = $rootStat.LastWriteTimeUtc.ToString('o'); status = $rootStatus.status; active = $rootStatus.ee5_root_operation_active }
    $record.ee5_freeze = [ordered]@{ path = $FreezeStatusPath; sha256 = $freezeSha; bytes = $freezeStat.Length; mtime_utc = $freezeStat.LastWriteTimeUtc.ToString('o'); word_qa_completed = $freezeStatus.word_qa_completed; restored = $freezeStatus.restored }

    if ((Get-Sha256 $GitExe) -ne $auth.git.executable_sha256) { throw 'Git executable SHA differs from approved binding' }
    $gitVersion = [string]::Join(' ', (Invoke-GitRead @('--version')))
    if ($gitVersion -ne $auth.git.version) { throw 'Git executable version differs from approved binding' }
    $record.git = [ordered]@{ executable = $GitExe; sha256 = Get-Sha256 $GitExe; version = $gitVersion }

    $mainPath = [IO.Path]::GetFullPath($MainRoot)
    $nativePath = [IO.Path]::GetFullPath($NativeRoot)
    if (-not $nativePath.StartsWith($AllowedWorktreePrefix,[StringComparison]::OrdinalIgnoreCase)) { throw 'Native actual path outside approved allowed prefix' }
    $checkpointPath = [IO.Path]::GetFullPath($CheckpointPath)
    if (-not $checkpointPath.StartsWith($EvidenceRoot + '\',[StringComparison]::OrdinalIgnoreCase)) { throw 'Native checkpoint outside approved ignored root' }
    $checkpointBytes = [IO.File]::ReadAllBytes($checkpointPath)
    $checkpoint = [Text.Encoding]::UTF8.GetString($checkpointBytes) | ConvertFrom-Json -AsHashtable
    $record.native_checkpoint_sha256 = Get-Sha256 $checkpointPath
    $checkpointStat = Get-Item -LiteralPath $checkpointPath
    $record.native_checkpoint = [ordered]@{ path = $checkpointPath; sha256 = $record.native_checkpoint_sha256; bytes = $checkpointStat.Length; mtime_utc = $checkpointStat.LastWriteTimeUtc.ToString('o') }
    if ([IO.Path]::GetFullPath($checkpoint.native.returned_root) -ne $nativePath -or
        $checkpoint.operation -ne "$Lane`:$Step" -or
        $checkpoint.native.expected_branch -ne $auth.native.expected_branch) { throw 'Native checkpoint does not bind this actual path/branch and next operation' }
    if (((Get-Item -LiteralPath $checkpointPath -Force).Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) { throw 'Native checkpoint is a reparse point' }
    $record.main_config = Get-ConfigRecords $mainPath
    $record.native_config = Get-ConfigRecords $nativePath
    foreach ($entry in @(@{ Root=$mainPath; Config=$record.main_config },@{ Root=$nativePath; Config=$record.native_config })) {
        foreach ($config in $entry.Config) {
            if ($config.key -eq 'core.fsmonitor' -and $config.value -notmatch '^(false|0|no)$') {
                throw "active or unknown fsmonitor configuration at $($config.origin)"
            }
            if ($config.key -eq 'commit.gpgsign' -and $config.value -notmatch '^(false|0|no)$') {
                throw "commit.gpgsign is not explicitly disabled or unset at $($config.origin)"
            }
            if ($config.key -eq 'core.hookspath' -and [string]::IsNullOrWhiteSpace($config.value)) {
                throw "empty hooksPath configuration at $($config.origin)"
            }
        }
    }
    $mainConfigJson = $record.main_config | ConvertTo-Json -Depth 6 -Compress
    $nativeConfigJson = $record.native_config | ConvertTo-Json -Depth 6 -Compress
    if ($auth.git.main_config_sha256 -ne (Get-Sha256Text $mainConfigJson) -or
        $checkpoint.native.config_sha256 -ne (Get-Sha256Text $nativeConfigJson)) {
        throw 'selected Git config source/value inventory differs from frozen approval/checkpoint'
    }
    $manifestPath = Join-Path $MainRoot 'docs/superpowers/plans/five-candidates-seal-1010/manifest.json'
    if ((Get-Sha256 $manifestPath) -ne $auth.seal_manifest_sha256) { throw 'formal seal manifest SHA differs from approved binding' }
    $manifest = Get-Content -LiteralPath $manifestPath -Raw -Encoding UTF8 | ConvertFrom-Json -AsHashtable
    if (@($manifest.candidates).Count -ne 5) { throw 'formal manifest candidate count is not five' }
    $manifestPaths = [string[]]@($manifest.candidates | ForEach-Object { $_.files } | ForEach-Object { $_.path })
    $authPaths = [string[]]@($auth.product_paths)
    $manifestUnique = @($manifestPaths | Sort-Object -Unique -CaseSensitive)
    $authUnique = @($authPaths | Sort-Object -Unique -CaseSensitive)
    [Array]::Sort($manifestPaths,[StringComparer]::Ordinal)
    [Array]::Sort($authPaths,[StringComparer]::Ordinal)
    if ($manifestPaths.Count -ne 41 -or $authPaths.Count -ne 41 -or
        $manifestUnique.Count -ne 41 -or $authUnique.Count -ne 41 -or
        (@(Compare-Object -ReferenceObject $manifestPaths -DifferenceObject $authPaths -CaseSensitive).Count -ne 0)) {
        throw 'approved product path set differs from the exact 41-path formal manifest'
    }
    $mainAttributePaths = @($authPaths) + @($registration.controls | ForEach-Object { $_.path }) + @([IO.Path]::GetRelativePath($MainRoot,$authPath),[IO.Path]::GetRelativePath($MainRoot,$registrationPath))
    $record.main_filter_attributes = Get-FilterAttributeInventory $mainPath $mainAttributePaths
    $record.native_filter_attributes = Get-FilterAttributeInventory $nativePath $authPaths
    $record.main_hooks = Get-HookInventory $mainPath $record.main_config
    $record.native_hooks = Get-HookInventory $nativePath $record.native_config
    if ($record.main_hooks.active_or_unknown.Count -or $record.native_hooks.active_or_unknown.Count) {
        throw 'non-sample hooks exist; inspect individually and obtain a revised approval before any commit operation'
    }
    $mainHookJson = $record.main_hooks | ConvertTo-Json -Depth 6 -Compress
    $nativeHookJson = $record.native_hooks | ConvertTo-Json -Depth 6 -Compress
    if ($auth.git.hook_inventory.main_sha256 -ne (Get-Sha256Text $mainHookJson)) { throw 'main hook inventory differs from approved binding' }
    if ($checkpoint.native.hook_inventory_sha256 -ne (Get-Sha256Text $nativeHookJson)) { throw 'Native hook inventory differs from prior checkpoint evidence' }

    $record.status_checks = @()
    $fullNativeStatus = [string]::Join("`n",(Invoke-GitRead @('-C',$nativePath,'status','--porcelain=v2','--untracked-files=all')))
    $record.native_full_worktree_status = $fullNativeStatus
    if ($fullNativeStatus -cne '') { throw 'full Native worktree is not clean after config/filter/hooks gates; stop' }
    foreach ($control in $registration.controls) {
        if ([IO.Path]::IsPathRooted([string]$control.path)) { throw 'control path must be main-root relative' }
        $controlPath = [IO.Path]::GetFullPath((Join-Path $MainRoot $control.path))
        if (-not $controlPath.StartsWith($mainPath + '\',[StringComparison]::OrdinalIgnoreCase)) { throw 'control file escapes main root' }
        if ((Get-Sha256 $controlPath) -ne $control.sha256) { throw "control content SHA drift: $($control.path)" }
        $relative = [IO.Path]::GetRelativePath($MainRoot,$controlPath)
        $porcelain = [string]::Join("`n",(Invoke-GitRead @('-C',$mainPath,'status','--porcelain=v2','--untracked-files=all','--ignored=matching','--',$relative)))
        if (-not (Test-ExpectedOrSweptClean $mainPath $relative $porcelain ([string]$control.expected_porcelain_v2))) { throw "control status drift/content is not committed as the frozen bytes: $($control.path)" }
        $controlStat = Get-Item -LiteralPath $controlPath
        $record.status_checks += [ordered]@{ path = $control.path; sha256 = $control.sha256; bytes = $controlStat.Length; mtime_utc = $controlStat.LastWriteTimeUtc.ToString('o'); porcelain_v2 = $porcelain }
    }
    $authRelative = [IO.Path]::GetRelativePath($MainRoot,$authPath)
    $authPorcelain = [string]::Join("`n",(Invoke-GitRead @('-C',$mainPath,'status','--porcelain=v2','--untracked-files=all','--ignored=matching','--',$authRelative)))
    if (-not (Test-ExpectedOrSweptClean $mainPath $authRelative $authPorcelain ([string]$registration.authorization_porcelain_v2))) {
        throw 'authorization control status drift/conflict'
    }
    $record.status_checks += [ordered]@{ path = $authPath; sha256 = $record.authorization_sha256; bytes = $authBytes.Length; mtime_utc = (Get-Item -LiteralPath $authPath).LastWriteTimeUtc.ToString('o'); porcelain_v2 = $authPorcelain }
    $expectedWorktree = $nativePath
    $head = [string]::Join('', (Invoke-GitRead @('-C',$expectedWorktree,'rev-parse','HEAD'))).Trim()
    $branch = [string]::Join('', (Invoke-GitRead @('-C',$expectedWorktree,'branch','--show-current'))).Trim()
    $status = [string]::Join("`n", (Invoke-GitRead (@('-C',$expectedWorktree,'status','--porcelain=v2','--untracked-files=all','--ignored=matching','--') + $authPaths)))
    $record.native_status = [ordered]@{ head = $head; branch = $branch; porcelain_v2 = $status }
    if ($head -ne $checkpoint.native.head -or $branch -ne $checkpoint.native.branch -or
        $branch -ne $auth.native.expected_branch -or $status -ne $checkpoint.native.status -or $status -ne '') {
        throw 'Native HEAD/ref/status differs from prior operation checkpoint'
    }

    $record.success = $true
} catch {
    $record.failure = [ordered]@{ message = $_.Exception.Message; type = $_.Exception.GetType().FullName }
}

$record.git_commands = $script:GitCallEvidence
$record.finished_local = (Get-Date).ToString('o')
$payload = [Text.Encoding]::UTF8.GetBytes(($record | ConvertTo-Json -Depth 12) + "`n")
try {
    $stream = [IO.File]::Open($EvidencePath,[IO.FileMode]::CreateNew,[IO.FileAccess]::Write,[IO.FileShare]::None)
    try { $stream.Write($payload,0,$payload.Length); $stream.Flush($true) } finally { $stream.Dispose() }
} catch {
    [Console]::Error.WriteLine('Could not create unique preflight evidence; no operation is authorized.')
    exit 2
}
if (-not $record.success) { [Console]::Error.WriteLine('Preflight rejected; see the new evidence file.'); exit 1 }
exit 0
