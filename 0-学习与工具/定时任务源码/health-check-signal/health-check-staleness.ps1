# SessionStart 钩子：把 Claude-Env-HealthCheck 的心跳读出来，过期/失败/有未处理
# 发现就在会话开头横幅告警（队列 #398 ⑴，2026-08-25，CC）。
#
# 🔴 安装位置：`C:\Users\Paul Shao\.claude\hooks\health-check-staleness.ps1`
#    本文件是**库内镜像**。该目录命中 `protected-paths.json` 的
#    `*/.claude/hooks/*` 规则（ISO 26262 受控范围），AI 工具写入会被
#    PreToolUse 守卫拦截 ⇒ 必须由 Shao Peishen 人工复制安装。
#    安装步骤见同目录 `README-安装步骤.md`。
#
# 为什么信号挂在这里，而不是再建一个后台任务：
#   #398 这一批三处失效的共同点是"失败不产生信号，成功与失败在外部观察上长得
#   一样"。再建一个后台守卫去守月度体检，只是把同一个失效模式往外挪一层——
#   那个守卫自己停了，照样没人知道。会话启动横幅是**人每天都会真的看到**的
#   界面，且钩子自身报错时 Claude Code 会显式提示，不存在"静默不响"这一态。
#
# 判据（monthly 任务，阈值随周期机械推出，非业务口径）：
#   · 心跳文件不存在        -> 告警（从未跑过，或被删）
#   · lastRun 距今 > 40 天  -> 告警（月度任务给足一次补跑窗口仍未跑）
#   · ok = false            -> 告警（跑了但崩了）
#   · findingCount > 0      -> 告警（跑通了，但结论没人看——§一 #82 教训）
# 一切正常时**完全静默**，不产生噪音。

$ErrorActionPreference = 'Stop'
try { [Console]::OutputEncoding = [Text.UTF8Encoding]::new($false) } catch {}

$STALE_DAYS = 40
$MAX_SHOWN  = 3   # 横幅里最多列几条发现，其余折成计数——防止刷屏把信号自己淹掉

function Write-HookMessage([string]$msg) {
  $payload = @{
    systemMessage = $msg
    hookSpecificOutput = @{
      hookEventName     = 'SessionStart'
      additionalContext = $msg
    }
  }
  $payload | ConvertTo-Json -Depth 5 -Compress
}

try {
  $statusPath = Join-Path $env:USERPROFILE '.claude\health-check-status.json'

  if (-not (Test-Path $statusPath)) {
    Write-HookMessage ("[环境体检] 🔴 找不到心跳文件 $statusPath —— Claude-Env-HealthCheck 可能从未跑过或已被移除。" +
                       "手动核：Get-ScheduledTaskInfo -TaskName Claude-Env-HealthCheck")
    exit 0
  }

  $status  = Get-Content $statusPath -Raw -Encoding UTF8 | ConvertFrom-Json
  $lastRun = [datetime]::Parse($status.lastRunIso)
  $ageDays = [math]::Floor(((Get-Date) - $lastRun).TotalDays)

  $alerts = @()
  if ($ageDays -gt $STALE_DAYS) {
    $alerts += "已 $ageDays 天未运行（月度任务，上限 $STALE_DAYS 天）"
  }
  if (-not $status.ok) {
    $alerts += "上次运行异常终止：$($status.fatal)"
  }
  if ($status.findingCount -gt 0) {
    $all   = @($status.findings)
    $shown = $all | Select-Object -First $MAX_SHOWN
    $tail  = if ($all.Count -gt $MAX_SHOWN) { "…等共 $($all.Count) 项" } else { "" }
    $alerts += "上次运行有 $($status.findingCount) 项待处理发现 —— " + (($shown) -join '；') + $tail
  }

  if ($alerts.Count -gt 0) {
    Write-HookMessage ("[环境体检] 🔴 Claude-Env-HealthCheck（上次 $($status.lastRunLocal)）：" +
                       ($alerts -join ' ｜ ') +
                       "。手动跑：powershell -NoProfile -ExecutionPolicy Bypass -File `"$env:USERPROFILE\.claude\health-check.ps1`"")
  }
  exit 0
}
catch {
  # 钩子自己坏了也必须出声——这正是本钩子存在的理由，不能自己犯同一个错。
  Write-HookMessage "[环境体检] ⚠ 心跳检查钩子自身报错：$($_.Exception.Message)（钩子：hooks\health-check-staleness.ps1）"
  exit 0
}
