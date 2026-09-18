# FI3 deployment smoke test - runs ON the server (.51). ASCII-only output (SSH console is GBK).
# Implements 3-治理与合规/.51部署标准清单 §五 smoke trio for FI3 (queue #615):
#   1. /api/ping 200 (local; the external leg is run from the laptop)
#   2. anonymous key page -> 302 to /_gate/login (gate active); logged-in -> 200
#   3. main flow: index renders mock verdict table; assert rule_version + mock banner keywords
# Reads ZP_GATE_PASSWORD from C:\fi3\.env itself; never prints the secret.
$ErrorActionPreference = "Continue"
$ProgressPreference = "SilentlyContinue"
$Port = 8097
$Prefix = "/finance/fi3"
$Root = "http://127.0.0.1:$Port$Prefix"
$EnvFile = "C:\fi3\.env"
$fail = 0

Write-Host "=== 0. process identity (proves the code that is running) ==="
$conn = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
if (-not $conn) { Write-Host "FAIL: nothing listening on $Port"; exit 1 }
$proc = Get-CimInstance Win32_Process -Filter "ProcessId=$($conn.OwningProcess)"
Write-Host ("PID={0}  CreationDate={1}" -f $proc.ProcessId, $proc.CreationDate.ToString("yyyy-MM-dd HH:mm:ss"))
Write-Host ("CmdLine={0}" -f $proc.CommandLine)
$task = Get-ScheduledTask -TaskName Fi3WebServer -ErrorAction SilentlyContinue
if ($task) {
  $info = Get-ScheduledTaskInfo -TaskName Fi3WebServer
  Write-Host ("Task state={0}  LastResult={1}  LastRun={2}  Trigger={3}  User={4}" -f $task.State, $info.LastTaskResult, $info.LastRunTime, ($task.Triggers | ForEach-Object { $_.CimClass.CimClassName }) -join ',', $task.Principal.UserId)
} else { Write-Host "FAIL: task Fi3WebServer not registered"; $fail++ }
$hash = (Get-FileHash "C:\fi3\app\fi3_payment_validation\webapp.py" -Algorithm SHA256).Hash
Write-Host ("webapp.py sha256={0}" -f $hash)
$fw = Get-NetFirewallRule -DisplayName "Fi3-WebServer-$Port" -ErrorAction SilentlyContinue
if ($fw) { $addr = ($fw | Get-NetFirewallAddressFilter).RemoteAddress; Write-Host ("firewall rule enabled={0} remote={1}" -f $fw.Enabled, $addr) }
else { Write-Host "FAIL: firewall rule Fi3-WebServer-$Port missing"; $fail++ }

Write-Host "=== 1. /api/ping (gate-exempt, local leg) ==="
try { $r = Invoke-WebRequest -Uri "$Root/api/ping" -TimeoutSec 10 -UseBasicParsing
      Write-Host ("ping HTTP {0}  body={1}" -f $r.StatusCode, $r.Content)
      if ($r.StatusCode -ne 200) { $fail++ } }
catch { Write-Host ("ping FAILED: {0}" -f $_.Exception.Message); $fail++ }

Write-Host "=== 2a. gate blocks anonymous access to key page ==="
$anon = -1
try { $r = Invoke-WebRequest -Uri "$Root/" -TimeoutSec 20 -UseBasicParsing -MaximumRedirection 0
      $anon = [int]$r.StatusCode }
catch { if ($_.Exception.Response) { $anon = [int]$_.Exception.Response.StatusCode } }
Write-Host ("anon HTTP {0} (expected 302 = gate active)" -f $anon)
if ($anon -ne 302) { Write-Host "FAIL: gate not active (ZP_GATE_PASSWORD empty or not loaded)"; $fail++ }

Write-Host "=== 2b. login with shared gate password ==="
$pw = $null
if (Test-Path $EnvFile) {
  foreach ($line in Get-Content $EnvFile) {
    if ($line -match "^\s*ZP_GATE_PASSWORD=(.+)$") { $pw = $Matches[1].Trim() }
  }
}
if (-not $pw) { Write-Host "FAIL: ZP_GATE_PASSWORD not found in $EnvFile"; exit 1 }
$sess = $null
$login = -1
try {
  $r = Invoke-WebRequest -Uri "http://127.0.0.1:$Port/_gate/login" -Method POST -TimeoutSec 20 `
        -UseBasicParsing -Body @{ password = $pw; next = "$Prefix/" } -SessionVariable sess -MaximumRedirection 0
  $login = [int]$r.StatusCode
} catch { if ($_.Exception.Response) { $login = [int]$_.Exception.Response.StatusCode } }
$pw = $null
Write-Host ("login HTTP {0} (302 = OK, redirects to page)" -f $login)

Write-Host "=== 3. key page after login = main flow (mock verdict table) ==="
try { $r = Invoke-WebRequest -Uri "$Root/" -TimeoutSec 120 -UseBasicParsing -WebSession $sess
      Write-Host ("page HTTP {0}  bytes={1}" -f $r.StatusCode, $r.RawContentLength)
      $hasMock    = $r.Content -match "<b>mock</b>"
      $hasBanner  = $r.Content -match "并非真实付款申请"
      $hasRule    = $r.Content -match "fi3-v1-tangyanping-2026-07-10"
      $hasTable   = $r.Content -match "<th>结果态</th>"
      Write-Host ("mock banner: {0}   not-real-payment notice: {1}   rule_version: {2}   outcome table: {3}" -f $hasMock, $hasBanner, $hasRule, $hasTable)
      if ($r.StatusCode -ne 200 -or -not ($hasMock -and $hasBanner -and $hasRule -and $hasTable)) { $fail++ } }
catch { Write-Host ("page FAILED: {0}" -f $_.Exception.Message); $fail++ }

Write-Host "=== 4. process still alive (same PID = no crash/restart during main flow) ==="
$conn2 = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
if ($conn2) {
  $p2 = Get-CimInstance Win32_Process -Filter "ProcessId=$($conn2.OwningProcess)"
  Write-Host ("PID={0}  CreationDate={1}  samePID={2}" -f $p2.ProcessId, $p2.CreationDate.ToString("yyyy-MM-dd HH:mm:ss"), ($p2.ProcessId -eq $proc.ProcessId))
} else { Write-Host "FAIL: port no longer listening"; $fail++ }

Write-Host ("=== SMOKE DONE  failures={0} ===" -f $fail)
exit $fail
