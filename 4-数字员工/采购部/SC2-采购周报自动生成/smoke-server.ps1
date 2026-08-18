# SC2 deployment smoke test - runs ON the server. ASCII-only output.
# Reads ZP_GATE_PASSWORD from C:\sc2\.env itself; never prints the secret.
$ErrorActionPreference = "Continue"
$ProgressPreference = "SilentlyContinue"
$Port = 8096
$Prefix = "/procurement/sc2"
$Root = "http://127.0.0.1:$Port$Prefix"

Write-Host "=== 0. process identity ==="
$conn = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
if (-not $conn) { Write-Host "FAIL: nothing listening on $Port"; exit 1 }
$proc = Get-CimInstance Win32_Process -Filter "ProcessId=$($conn.OwningProcess)"
Write-Host ("PID={0}  CreationDate={1}" -f $proc.ProcessId, $proc.CreationDate.ToString("yyyy-MM-dd HH:mm:ss"))
Write-Host ("CmdLine={0}" -f $proc.CommandLine)
$task = Get-ScheduledTask -TaskName Sc2WebServer
$info = Get-ScheduledTaskInfo -TaskName Sc2WebServer
Write-Host ("Task state={0}  LastResult={1}  LastRun={2}" -f $task.State, $info.LastTaskResult, $info.LastRunTime)

Write-Host "=== 1. /api/ping (gate-exempt) ==="
try { $r = Invoke-WebRequest -Uri "$Root/api/ping" -TimeoutSec 10 -UseBasicParsing
      Write-Host ("ping HTTP {0}  body={1}" -f $r.StatusCode, $r.Content) }
catch { Write-Host ("ping FAILED: {0}" -f $_.Exception.Message) }

Write-Host "=== 2. gate blocks anonymous access to key page ==="
try { $r = Invoke-WebRequest -Uri "$Root/" -TimeoutSec 20 -UseBasicParsing -MaximumRedirection 0
      Write-Host ("anon HTTP {0} (expected 302)" -f $r.StatusCode) }
catch { $sc = if ($_.Exception.Response) { [int]$_.Exception.Response.StatusCode } else { -1 }
        Write-Host ("anon HTTP {0} (expected 302 = gate active)" -f $sc) }

Write-Host "=== 3. login with shared gate password ==="
$pw = $null
foreach ($line in Get-Content "C:\sc2\.env") {
  if ($line -match "^\s*ZP_GATE_PASSWORD=(.+)$") { $pw = $Matches[1].Trim() }
}
if (-not $pw) { Write-Host "FAIL: ZP_GATE_PASSWORD not found in C:\sc2\.env"; exit 1 }
$sess = $null
try {
  $r = Invoke-WebRequest -Uri "http://127.0.0.1:$Port/_gate/login" -Method POST -TimeoutSec 20 `
        -UseBasicParsing -Body @{ password = $pw; next = "$Prefix/" } -SessionVariable sess -MaximumRedirection 0
  Write-Host ("login HTTP {0}" -f $r.StatusCode)
} catch {
  $sc = if ($_.Exception.Response) { [int]$_.Exception.Response.StatusCode } else { -1 }
  Write-Host ("login HTTP {0} (302 = OK, redirects to page)" -f $sc)
}
$pw = $null

Write-Host "=== 4. key page after login ==="
try { $r = Invoke-WebRequest -Uri "$Root/" -TimeoutSec 300 -UseBasicParsing -WebSession $sess
      Write-Host ("page HTTP {0}  bytes={1}" -f $r.StatusCode, $r.RawContentLength)
      $hasConfirm = $r.Content -match "confirmed_by"
      $hasWeek = $r.Content -match "2026-W"
      Write-Host ("page has confirm form: {0}   has ISO week label: {1}" -f $hasConfirm, $hasWeek) }
catch { Write-Host ("page FAILED: {0}" -f $_.Exception.Message) }

Write-Host "=== 5. full real recompute via POST /api/refresh ==="
$sw = [System.Diagnostics.Stopwatch]::StartNew()
try { $r = Invoke-WebRequest -Uri "$Root/api/refresh" -Method POST -TimeoutSec 900 -UseBasicParsing -WebSession $sess
      $sw.Stop()
      Write-Host ("refresh HTTP {0}  elapsed={1}s  body={2}" -f $r.StatusCode, [int]$sw.Elapsed.TotalSeconds, $r.Content) }
catch { $sw.Stop(); Write-Host ("refresh FAILED after {0}s: {1}" -f [int]$sw.Elapsed.TotalSeconds, $_.Exception.Message) }

Write-Host "=== 6. key page again (snapshot path, must be fast) ==="
$sw2 = [System.Diagnostics.Stopwatch]::StartNew()
try { $r = Invoke-WebRequest -Uri "$Root/" -TimeoutSec 60 -UseBasicParsing -WebSession $sess
      $sw2.Stop()
      Write-Host ("page HTTP {0}  elapsed={1}s  bytes={2}" -f $r.StatusCode, [int]$sw2.Elapsed.TotalSeconds, $r.RawContentLength) }
catch { $sw2.Stop(); Write-Host ("page FAILED: {0}" -f $_.Exception.Message) }

Write-Host "=== 7. process still alive (no crash during recompute) ==="
$conn2 = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
if ($conn2) {
  $p2 = Get-CimInstance Win32_Process -Filter "ProcessId=$($conn2.OwningProcess)"
  Write-Host ("PID={0}  CreationDate={1}  (same PID as step 0 = never restarted)" -f $p2.ProcessId, $p2.CreationDate.ToString("yyyy-MM-dd HH:mm:ss"))
} else { Write-Host "FAIL: port no longer listening" }
Write-Host "=== SMOKE DONE ==="
