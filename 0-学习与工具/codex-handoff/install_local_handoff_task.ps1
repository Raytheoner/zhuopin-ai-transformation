param([switch]$Install)
$ErrorActionPreference='Stop'
$repo=(Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '../..')).Path
$runtime=Get-Content -LiteralPath (Join-Path $repo '.codex/runtime.local.json') -Raw -Encoding UTF8 | ConvertFrom-Json
$worker=Join-Path $PSScriptRoot 'local_handoff_schedule.py'
$raw=& $runtime.python $worker --root $repo --describe
if ($LASTEXITCODE -ne 0) { throw '不能解析本地维护配置' }
$proposal=$raw | ConvertFrom-Json
$marker='zhuopin-local-handoff:'+ $proposal.identity
$next=[DateTimeOffset]::Parse($proposal.next_beijing)
$local=$next.ToLocalTime()
$user=[Security.Principal.WindowsIdentity]::GetCurrent().Name
function Esc([string]$s) { [Security.SecurityElement]::Escape($s) }
$arguments='"'+$worker+'" --root "'+$repo+'" --run-due'
$day=$local.DayOfWeek.ToString()
$xml=@"
<?xml version="1.0" encoding="UTF-16"?>
<Task version="1.4" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
 <RegistrationInfo><Description>$(Esc $marker)</Description></RegistrationInfo>
 <Triggers><CalendarTrigger><StartBoundary>$($local.ToString('yyyy-MM-ddTHH:mm:sszzz'))</StartBoundary><Enabled>true</Enabled><ScheduleByWeek><WeeksInterval>1</WeeksInterval><DaysOfWeek><$day /></DaysOfWeek></ScheduleByWeek></CalendarTrigger><LogonTrigger><Enabled>true</Enabled><UserId>$(Esc $user)</UserId></LogonTrigger></Triggers>
 <Principals><Principal id="Author"><UserId>$(Esc $user)</UserId><LogonType>InteractiveToken</LogonType><RunLevel>LeastPrivilege</RunLevel></Principal></Principals>
 <Settings><MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy><StartWhenAvailable>true</StartWhenAvailable><WakeToRun>true</WakeToRun><ExecutionTimeLimit>PT20M</ExecutionTimeLimit><RestartOnFailure><Interval>PT1H</Interval><Count>3</Count></RestartOnFailure><Enabled>false</Enabled><Hidden>true</Hidden></Settings>
 <Actions Context="Author"><Exec><Command>$(Esc $runtime.python)</Command><Arguments>$(Esc $arguments)</Arguments><WorkingDirectory>$(Esc $repo)</WorkingDirectory></Exec></Actions>
</Task>
"@
@{mode='proposal-only';task_name=$proposal.task_name;identity=$proposal.identity;next_beijing=$proposal.next_beijing;next_local=$local.ToString('o');system_timezone=(Get-TimeZone).Id;python=$runtime.python;script=$worker;working_directory=$repo;xml=$xml} | ConvertTo-Json -Depth 5 | Write-Output
# 先全量取得可访问列表；失败不是“没有同名任务”，不能覆盖/注册。
$all=@(Get-ScheduledTask -ErrorAction Stop)
$related=@($all | Where-Object { $_.Description -eq $marker -or @($_.Actions | Where-Object { $_.Execute -eq $runtime.python -and $_.Arguments -eq $arguments }).Count -gt 0 })
if (@($related | Where-Object { $_.TaskName -ne $proposal.task_name -or $_.TaskPath -ne '\' }).Count) { throw '发现同仓库同用途的其他任务路径；先核实去重，不再新建第二个主任务。' }
$old=@($all | Where-Object { $_.TaskName -eq $proposal.task_name -and $_.TaskPath -eq '\' })
if ($old.Count -gt 1) { throw '同名任务归属不唯一' }
if ($old.Count -eq 1) {
 if ($old[0].Description -ne $marker -or $old[0].Actions.Count -ne 1 -or $old[0].Actions[0].Arguments -ne $arguments -or $old[0].Actions[0].Execute -ne $runtime.python) { throw '同名任务不属于当前仓库相同纯本地入口；不替换' }
}
if (-not $Install) { Write-Output 'Preflight passed; no task changed.'; exit 0 }
& $runtime.python (Join-Path $PSScriptRoot 'quality_handoff.py') --root $repo --domain all --check
if ($LASTEXITCODE -ne 0) { throw '资料完整性未通过，安装停止' }
$backup=Join-Path $repo ('reports/local-handoff-install/'+$proposal.identity+'/'+(Get-Date -Format 'yyyyMMdd-HHmmss'))
[IO.Directory]::CreateDirectory($backup) | Out-Null
[IO.File]::WriteAllText((Join-Path $backup 'proposed.xml'),$xml,[Text.Encoding]::Unicode)
$oldXml=$null; $oldEnabled=$false; $oldConfig=$null; $newConfigHash=$null; $changedTask=$false
if ($old.Count) {
 $oldXml=Export-ScheduledTask -TaskName $proposal.task_name -TaskPath '\'; $oldEnabled=[bool]$old[0].Settings.Enabled
 [IO.File]::WriteAllText((Join-Path $backup 'before.xml'),$oldXml,[Text.Encoding]::Unicode)
}
if (Test-Path -LiteralPath $proposal.config) { $oldConfig=[IO.File]::ReadAllBytes($proposal.config); [IO.File]::WriteAllBytes((Join-Path $backup 'before-config.json'),$oldConfig) }
try {
 Register-ScheduledTask -TaskName $proposal.task_name -TaskPath '\' -Xml $xml -Force | Out-Null
 $changedTask=$true
 $installedConfig=& $runtime.python $worker --root $repo --configure
 if ($LASTEXITCODE -ne 0) { throw '本地配置写入失败' }
 $newConfigHash=(Get-FileHash -LiteralPath $proposal.config).Hash
 $installedConfig | Set-Content -LiteralPath (Join-Path $backup 'installed-config.json') -Encoding utf8
 Enable-ScheduledTask -TaskName $proposal.task_name -TaskPath '\' | Out-Null
 $installed=Get-ScheduledTask -TaskName $proposal.task_name -TaskPath '\' -ErrorAction Stop
 if ($installed.Description -ne $marker -or $installed.Actions[0].Execute -ne $runtime.python -or $installed.Actions[0].Arguments -ne $arguments -or -not $installed.Settings.Enabled) { throw '注册回读不一致' }
 Start-ScheduledTask -TaskName $proposal.task_name -TaskPath '\'
 $started=Get-Date
 do { Start-Sleep -Seconds 1; $info=Get-ScheduledTaskInfo -TaskName $proposal.task_name -TaskPath '\'; $state=Get-ScheduledTask -TaskName $proposal.task_name -TaskPath '\' } while (($state.State -eq 'Running' -or $info.LastRunTime -lt $started.AddSeconds(-2)) -and (Get-Date) -lt $started.AddSeconds(25))
 if ($state.State -eq 'Running' -or $info.LastTaskResult -ne 0 -or $info.LastRunTime -lt $started.AddSeconds(-2)) { throw '受控真实任务安全到期检查未通过' }
 $receipt=@{task=$proposal.task_name;enabled=$true;last_result=$info.LastTaskResult;last_run=$info.LastRunTime;next_actual_run=$info.NextRunTime;timezone=(Get-TimeZone).Id;python=$runtime.python;script=$worker;working_directory=$repo;first_period='installation skips all older Beijing cycles'}
 $receipt | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath (Join-Path $backup 'receipt.json') -Encoding utf8
 $receipt | ConvertTo-Json -Depth 4 | Write-Output
} catch {
 $_ | Out-String | Set-Content -LiteralPath (Join-Path $backup 'install-failure.txt') -Encoding utf8
 if ($changedTask) {
  if ($oldXml) { Register-ScheduledTask -TaskName $proposal.task_name -TaskPath '\' -Xml $oldXml -Force | Out-Null; if (-not $oldEnabled) { Disable-ScheduledTask -TaskName $proposal.task_name -TaskPath '\' | Out-Null } }
  else { Unregister-ScheduledTask -TaskName $proposal.task_name -TaskPath '\' -Confirm:$false }
 }
 if ($newConfigHash -and (Test-Path -LiteralPath $proposal.config) -and (Get-FileHash -LiteralPath $proposal.config).Hash -eq $newConfigHash) {
  if ($oldConfig) { [IO.File]::WriteAllBytes($proposal.config,$oldConfig) } else { Remove-Item -LiteralPath $proposal.config }
 }
 throw
}
