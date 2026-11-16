
param(
 [ValidateSet('Probe','Hook','Workflow','Guardian','Test','R5Card')][string]$Mode='Probe',
 [ValidateSet('help','register','status','queue-status','acquire','release','queue-release','check','apply','recover')][string]$R5Action,
 [string]$R5Batch,
 [string]$R5Who,
 [string]$R5Note,
 [string[]]$R5Waiver = @(),
 [Parameter(ValueFromRemainingArguments=$true)][string[]]$Arguments
)
# A failed Hook launcher must not become an implicitly allowed tool call.
trap {
  if ($Mode -eq 'Hook' -and $hookEventName -notin @('SessionStart','UserPromptSubmit','PostToolUse','Stop')) {
    Write-Output '{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"deny","permissionDecisionReason":"Codex hook launcher failed; inspect runtime configuration."}}'
    exit 0
  }
  [Console]::Error.WriteLine($_.Exception.Message)
  if ($Mode -eq 'Hook') { exit 2 }
  exit 1
}
$ErrorActionPreference='Stop'
$hookInput = $null
$hookEventName = $null
if ($Mode -eq 'Hook') {
  [Console]::InputEncoding = [Text.UTF8Encoding]::new($false)
  $OutputEncoding = [Text.UTF8Encoding]::new($false)
  $hookInput = [Console]::In.ReadToEnd()
  try {
    $hookEnvelope = $hookInput | ConvertFrom-Json -ErrorAction Stop
    if ($hookEnvelope.hook_event_name -is [string]) { $hookEventName = $hookEnvelope.hook_event_name }
  } catch { } # The bridge rejects malformed or unclassifiable input explicitly.
}
$env:PYTHONUTF8='1'
$env:PYTHONDONTWRITEBYTECODE='1'
$repo = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '../..')).Path
$configPath = if ($env:ZHUOPIN_CODEX_RUNTIME) { $env:ZHUOPIN_CODEX_RUNTIME } else { Join-Path $repo '.codex/runtime.local.json' }
if (-not (Test-Path -LiteralPath $configPath)) {
    $common = & git -c "safe.directory=$($repo.Replace('\','/'))" -C $repo rev-parse --git-common-dir
    if ($LASTEXITCODE -ne 0) { throw '不能解析共享仓库runtime' }
    $commonPath = if ([IO.Path]::IsPathRooted($common)) { $common } else { Join-Path $repo $common }
    $configPath = Join-Path (Split-Path ([IO.Path]::GetFullPath($commonPath)) -Parent) '.codex/runtime.local.json'
}
if (-not (Test-Path -LiteralPath $configPath)) { throw "缺少本机运行时配置：$configPath；参见同目录 README.md。" }
$config = Get-Content -LiteralPath $configPath -Raw -Encoding UTF8 | ConvertFrom-Json
if (-not (Test-Path -LiteralPath $config.python)) { throw "运行时不存在：$($config.python)" }
$env:ZHUOPIN_CODEX_RUNTIME = $configPath
$env:ZHUOPIN_CODEX_STATE = $config.state_root
$nodeBin = 'C:\Dev\Codex\runtimes\zhuopin-ai\node\node_modules\.bin'
if (Test-Path -LiteralPath $nodeBin) { $env:PATH = "$nodeBin;$env:PATH" }
$entry = Join-Path $PSScriptRoot 'handoff.py'
if ($Mode -eq 'R5Card') {
  # R5Card is a fixed-path facade over the existing queue and file-lock tools.
  # Single-item edits use the guarded editor; apply/recover generate indexes under the same official card lock.
  if (-not $R5Action) { throw 'R5Card requires -R5Action help|register|status|acquire|release|queue-release|check|apply|recover.' }
  $cardPath = '0-学习与工具/codex-handoff/质量域-R5接力-2026-10-20.md'
  $entryPath = '0-学习与工具/codex-handoff/invoke.ps1'
  $queuePath = '1-转型规划/0-全景路线图/跨桌任务队列-业务场景.md'
  $queueQuery = Join-Path $repo '0-学习与工具/工具-队列查询.py'
  $lockTool = Join-Path $repo '0-学习与工具/工具-共享文档编辑锁.py'

  function Read-R5BatchProof {
    param([Parameter(Mandatory)][string]$Batch)
    if ($Batch -notmatch '^B-\d{4}_.+$' -or $Batch.Contains('|') -or $Batch.Contains("`n") -or $Batch.Contains("`r")) {
      throw 'R5 batch id must use B-YYYY_semantic form without separators or newlines.'
    }
    $jsonArgs = @('--row', $Batch, '--section', '二', '--field', 'all', '--format', 'json')
    $jsonLines = & $config.python $queueQuery @jsonArgs
    $queryExit = $LASTEXITCODE
    if ($queryExit -ne 0) { throw "Official queue query failed with exit code $queryExit." }
    $proof = ($jsonLines -join "`n") | ConvertFrom-Json -ErrorAction Stop
    if ($proof.error -or @($proof.read_errors).Count -gt 0) { throw 'Official queue query reported an error or read error.' }
    return $proof
  }

  function Assert-R5BatchRegistered {
    param([Parameter(Mandatory)][string]$Batch)
    $proof = Read-R5BatchProof -Batch $Batch
    if (-not $proof.found -or $proof.done -or $proof.reason -ne 'live-open') {
      throw "R5 update batch '$Batch' is not live/open; no card lock action was taken."
    }
    $detailArgs = @('--row', $Batch, '--section', '二', '--field', 'all')
    $detailLines = & $config.python $queueQuery @detailArgs
    $detailExit = $LASTEXITCODE
    if ($detailExit -ne 0) { throw "Official queue detail query failed with exit code $detailExit." }
    $detail = $detailLines -join "`n"
    foreach ($requiredPath in @($queuePath, $entryPath, $cardPath)) {
      if (-not $detail.Contains($requiredPath)) {
        throw "R5 update batch '$Batch' does not register required path '$requiredPath'."
      }
    }
  }

  if ($R5Action -notin @('help','status','queue-status','check')) {
    if ([string]::IsNullOrWhiteSpace($R5Who)) { throw 'R5Card requires -R5Who for this action.' }
  }

  if ($R5Action -eq 'help') {
    @(
      'R5Card is fixed to 0-学习与工具/codex-handoff/质量域-R5接力-2026-10-20.md.'
      'Register: invoke.ps1 -Mode R5Card -R5Action register -R5Batch B-YYYY_semantic -R5Who <identity> -R5Note <reason>'
      'Acquire/release: pass -R5Batch and -R5Who; the batch must be live/open and list the queue, invoke.ps1 and R5 card paths.'
      'Status: invoke.ps1 -Mode R5Card -R5Action status. Queue lock recovery: -R5Action queue-release with the batch and same lock owner.'
      'Edit single-item records through the guarded editor; index/pages are generated locally. Queue registration and all locks continue through the official tools.'
      'Generated quality index: check is read-only; apply/recover require the same live registered batch and the existing official card lock.'
    ) | Write-Output
    exit 0
  }

  if ($R5Action -eq 'check') {
    & $config.python (Join-Path $PSScriptRoot 'quality_handoff.py') --root $repo --check
    exit $LASTEXITCODE
  }

  if ($R5Action -eq 'register') {
    if ([string]::IsNullOrWhiteSpace($R5Batch) -or [string]::IsNullOrWhiteSpace($R5Note)) {
      throw 'R5Card register requires -R5Batch and -R5Note.'
    }
    $proof = Read-R5BatchProof -Batch $R5Batch
    if ($proof.found) { throw "R5 update batch '$R5Batch' already exists; registration stopped." }
    $queueStatusLines = & $config.python $lockTool status
    $queueStatusExit = $LASTEXITCODE
    if ($queueStatusExit -ne 0) { throw "Official lock status failed with exit code $queueStatusExit." }
    $queueStatusText = $queueStatusLines -join "`n"
    $ourRegistrationLock = $queueStatusText.Contains("占用方：$R5Who") -and $queueStatusText.Contains('登记质量R5固定路径更新入口')
    if (-not $ourRegistrationLock -and $queueStatusText.Contains('占用方：')) {
      throw 'A different queue lock is active; R5 batch registration stopped.'
    }
    if (-not $ourRegistrationLock) {
      $registrationNote = "登记质量R5固定路径更新入口；批次 $R5Batch；$R5Note"
      $acquireArgs = @('acquire', '--who', $R5Who, '--note', $registrationNote)
      & $config.python $lockTool @acquireArgs
      $queueAcquireExit = $LASTEXITCODE
      if ($queueAcquireExit -ne 0) { exit $queueAcquireExit }
    }

    $files = '`' + $queuePath + '`；`' + $entryPath + '`；`' + $cardPath + '`'
    $appendArgs = @(
      'append-row', '--who', $R5Who, '--section', '二', '--domain', '业',
      '--cell', $R5Batch, '--cell', $files,
      '--cell', 'docs: 增加质量R5卡固定目标更新入口并登记本次卡片更新',
      '--cell', '在办（预登记；未授权提交）：R5资料维护，实际完成后按具体授权落库。'
    )
    & $config.python $lockTool @appendArgs
    $appendExit = $LASTEXITCODE
    if ($appendExit -ne 0) {
      [Console]::Error.WriteLine("append-row failed with exit code $appendExit; attempting official release of the R5 registration lock.")
      $recoveryReleaseArgs = @('release', '--who', $R5Who)
      foreach ($waiver in $R5Waiver) { $recoveryReleaseArgs += @('--waiver', $waiver) }
      & $config.python $lockTool @recoveryReleaseArgs
      $recoveryReleaseExit = $LASTEXITCODE
      if ($recoveryReleaseExit -ne 0) {
        [Console]::Error.WriteLine("Official recovery release failed with exit code $recoveryReleaseExit; lock remains held.")
      }
      exit $appendExit
    }
    $queueReleaseArgs = @('release', '--who', $R5Who)
    foreach ($waiver in $R5Waiver) { $queueReleaseArgs += @('--waiver', $waiver) }
    & $config.python $lockTool @queueReleaseArgs
    exit $LASTEXITCODE
  }

  if ($R5Action -eq 'status') {
    $lockArgs = @('--file', $cardPath, 'status')
    & $config.python $lockTool @lockArgs
    exit $LASTEXITCODE
  }

  if ($R5Action -eq 'queue-status') {
    & $config.python $lockTool status
    exit $LASTEXITCODE
  }

  if ($R5Action -eq 'queue-release') {
    if ([string]::IsNullOrWhiteSpace($R5Batch)) { throw 'R5Card queue-release requires -R5Batch.' }
    $null = Read-R5BatchProof -Batch $R5Batch
    $statusLines = & $config.python $lockTool status
    $statusExit = $LASTEXITCODE
    if ($statusExit -ne 0) { throw "Official lock status failed with exit code $statusExit." }
    $statusText = $statusLines -join "`n"
    if (-not $statusText.Contains("占用方：$R5Who") -or -not $statusText.Contains('登记质量R5固定路径更新入口')) {
      throw 'Queue lock is not held by this identity with the R5 registration marker; release stopped.'
    }
    $queueReleaseArgs = @('release', '--who', $R5Who)
    foreach ($waiver in $R5Waiver) { $queueReleaseArgs += @('--waiver', $waiver) }
    & $config.python $lockTool @queueReleaseArgs
    exit $LASTEXITCODE
  }

  if ([string]::IsNullOrWhiteSpace($R5Batch)) { throw "R5Card $R5Action requires -R5Batch." }
  Assert-R5BatchRegistered -Batch $R5Batch

  if ($R5Action -in @('apply','recover')) {
    & $config.python (Join-Path $PSScriptRoot 'quality_handoff.py') --root $repo "--$R5Action" --who $R5Who
    exit $LASTEXITCODE
  }

  if ($R5Action -eq 'acquire') {
    if ([string]::IsNullOrWhiteSpace($R5Note)) { throw 'R5Card acquire requires -R5Note.' }
    $lockArgs = @('--file', $cardPath, 'acquire', '--who', $R5Who, '--note', "R5 batch $R5Batch; $R5Note")
  } elseif ($R5Action -eq 'release') {
    $lockArgs = @('--file', $cardPath, 'release', '--who', $R5Who)
    foreach ($waiver in $R5Waiver) { $lockArgs += @('--waiver', $waiver) }
  }
  & $config.python $lockTool @lockArgs
  exit $LASTEXITCODE
} elseif ($Mode -eq 'Hook') {
  $hookInput | & $config.python (Join-Path $PSScriptRoot 'hook_bridge.py')
  if ($LASTEXITCODE -ne 0 -and $hookEventName -notin @('SessionStart','UserPromptSubmit','PostToolUse','Stop')) { throw 'Codex hook bridge failed.' }
} elseif ($Mode -eq 'Test') {
  & $config.python -m pytest (Join-Path $PSScriptRoot 'tests') -q -p no:cacheprovider @Arguments
} elseif ($Mode -eq 'Workflow') {
  & $config.python $entry @Arguments
} elseif ($Mode -eq 'Guardian') {
  & $config.python (Join-Path $PSScriptRoot 'guardian_entry.py') @Arguments
} else {
  & $config.python $entry probe @Arguments
}
exit $LASTEXITCODE
