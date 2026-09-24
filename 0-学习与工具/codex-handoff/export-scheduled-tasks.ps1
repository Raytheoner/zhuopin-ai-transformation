
param([string]$Destination='C:\Dev\Codex\runtimes\zhuopin-ai\scheduler-export')
$ErrorActionPreference='Stop'
New-Item -ItemType Directory -Path $Destination -Force | Out-Null
$records=@()
try {
  $tasks=Get-ScheduledTask -ErrorAction Stop
  foreach($task in $tasks) {
    $joined = ($task.Actions | ForEach-Object { "$($_.Execute) $($_.Arguments) $($_.WorkingDirectory)" }) -join ' '
    if ($joined -notmatch '(?i)zhuopin|卓品|Claude|Codex|落库|泳道|chaijian|huijian|opener') { continue }
    $bytes=[Text.Encoding]::UTF8.GetBytes("$($task.TaskPath)$($task.TaskName)")
    $id=[Convert]::ToHexString([Security.Cryptography.SHA256]::HashData($bytes)).Substring(0,16)
    $xml=Export-ScheduledTask -TaskName $task.TaskName -TaskPath $task.TaskPath
    # Full definitions are private local evidence, never automatically uploaded.
    [IO.File]::WriteAllText((Join-Path $Destination "$id.xml"),$xml,[Text.UTF8Encoding]::new($false))
    $actions=@($task.Actions | ForEach-Object {
      $arg=[string]$_.Arguments
      @{ Execute=$_.Execute; WorkingDirectory=$_.WorkingDirectory;
         ArgumentsSHA256=[Convert]::ToHexString([Security.Cryptography.SHA256]::HashData([Text.Encoding]::UTF8.GetBytes($arg)));
         ClaudeModelConsumer=($arg -match '(?i)claude|claude-code' -or $_.Execute -match '(?i)claude');
         CodexConsumer=($arg -match '(?i)codex' -or $_.Execute -match '(?i)codex') }
    })
    $info=Get-ScheduledTaskInfo -InputObject $task
    $records+=@{ Name=$task.TaskName; Path=$task.TaskPath; State=[string]$task.State;
                 Enabled=$task.Settings.Enabled; Actions=$actions; Triggers=$task.Triggers;
                 LastRunTime=$info.LastRunTime; LastTaskResult=$info.LastTaskResult;
                 NextRunTime=$info.NextRunTime; PrivateDefinition="$id.xml" }
  }
  @{Status='verified'; ExportedAt=(Get-Date -Format o); Tasks=$records} |
    ConvertTo-Json -Depth 12 | Set-Content -LiteralPath (Join-Path $Destination 'summary.json') -Encoding utf8
  Write-Output "只读导出完成：$($records.Count) 项；$Destination"
} catch {
  @{Status='unverified'; ExportedAt=(Get-Date -Format o); ErrorType=$_.Exception.GetType().FullName} |
    ConvertTo-Json | Set-Content -LiteralPath (Join-Path $Destination 'summary.json') -Encoding utf8
  throw
}
