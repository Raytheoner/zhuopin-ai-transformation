try {
  $ErrorActionPreference = 'Stop'
  $raw = [Console]::In.ReadToEnd()
  if ([string]::IsNullOrWhiteSpace($raw)) { exit 0 }
  try { $j = $raw | ConvertFrom-Json } catch { exit 0 }
  $tool = [string]$j.tool_name
  if ($tool -ne 'mcp__plugin_outlook_outlook__outlook_send_mail') { exit 0 }

  # 基线权限已把 outlook_send_mail 加入 allow（无人值守/headless 模式必须这样才不会被
  # "you haven't granted it yet" 拦死）。这个 hook 反过来当主动裁决者：
  # save_only=true（只存草稿）才放行；否则（真实发送）主动 deny，不给交互确认的机会。
  $ti = $j.tool_input
  $saveOnly = $false
  if ($null -ne $ti.save_only) { $saveOnly = [bool]$ti.save_only }

  if ($saveOnly) {
    $decision = 'allow'
    $reason = '仅存草稿(save_only=true)，自动放行。'
  } else {
    $decision = 'deny'
    $reason = 'save_only 非 true（即将真实发送），主动拦截。如需真实发送邮件，请直接在 Outlook 里手动点发送，或明确要求走人工确认流程。'
  }

  try {
    $dir = Join-Path $PSScriptRoot '../../../reports/codex-hooks'
    if (-not (Test-Path -LiteralPath $dir)) { New-Item -ItemType Directory -Path $dir -Force | Out-Null }
    $glog = Join-Path $dir ("audit-outlook-draft-guard-{0:yyyyMMdd}.log" -f (Get-Date))
    $ts = (Get-Date).ToString('o')
    $sid = [string]$j.session_id
    $u = New-Object System.Text.UTF8Encoding($false)
    [System.IO.File]::AppendAllText($glog, "$ts`t$tool`tsave_only=$saveOnly`t$decision`t$sid`r`n", $u)
  } catch { }

  $out = @{ hookSpecificOutput = @{ hookEventName = 'PreToolUse'; permissionDecision = $decision; permissionDecisionReason = $reason } }
  Write-Output ($out | ConvertTo-Json -Depth 5 -Compress)
  exit 0
} catch { exit 0 }
