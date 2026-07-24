# ================================================================
#  工具-注册落库sweep计划任务.ps1
#  用途：把 工具-落库sweep.py 注册为 Windows 计划任务（队列 #68③，Paul 2026-07-24
#  拍板五条硬要求之④"计划任务 Action 指主工作区稳定路径 + SYSTEM + AtStartup +
#  绝对路径烘焙（勿指建造 worktree，防 #49/#79 两个旧坑）"）。
#
#  #49 坑：曾有长驻 worktree（wecom-service-home）独占 master checkout，导致主
#          工作区一度无法字面 checkout master——本任务 Action 只认下面这个主
#          工作区稳定路径常量，不指向任何 .claude\worktrees\<name>；即便将来
#          某个建造 worktree 完工被 `git worktree remove` 掉，本任务不受影响。
#  #79 坑：CommandCenterWeb 曾用 AtLogOn 交互式登录触发 + 裸命令 "python"——
#          Administrator 会话"已断开"时无法启动新进程（0x80070002），且 python
#          是当前用户级安装（AppData\Local\Programs），SYSTEM 账户的 PATH 里
#          根本没有这个目录，裸命令连"找不到命令"都不会明确报——已改
#          SYSTEM + AtStartup + 注册时解析绝对路径烘焙进启动包装脚本，
#          不依赖运行时环境变量，本注册脚本沿用同一套（同 SC8/QD-B 惯例）。
#
#  用法（本机管理员 PowerShell，在主工作区目录下执行一次；重复执行幂等——
#        会先注销旧任务再重建，用于路径变化后刷新）：
#    powershell -ExecutionPolicy Bypass -File "0-学习与工具\工具-注册落库sweep计划任务.ps1"
#
#  验证：
#    Start-ScheduledTask -TaskName ZhuopinCommitSweep   # 立即手动跑一次
#    Get-ScheduledTaskInfo -TaskName ZhuopinCommitSweep # 查看上次结果
#    Get-Content "...\企业AI转型\reports\sweep-commit.log" -Tail 20
#
#  回滚：
#    schtasks /End /TN ZhuopinCommitSweep          # 停止本次运行（若正在跑）
#    schtasks /Delete /TN ZhuopinCommitSweep /F     # 彻底注销
# ================================================================
$ErrorActionPreference = "Stop"

$REPO           = "C:\Users\Paul Shao\OneDrive\Projects\企业AI转型"
$SWEEP_SCRIPT   = Join-Path $REPO "0-学习与工具\工具-落库sweep.py"
$WRAPPER        = Join-Path $REPO "0-学习与工具\run-commit-sweep.ps1"
$TASK           = "ZhuopinCommitSweep"
$INTERVAL_HOURS = 4

Write-Host "`n== 注册落库 sweep 计划任务 ==" -ForegroundColor Cyan
Write-Host "   主工作区: $REPO"
Write-Host "   sweep 脚本: $SWEEP_SCRIPT"
Write-Host "   周期    : 开机启动 + 此后每 $INTERVAL_HOURS 小时一次`n"

if (-not (Test-Path $SWEEP_SCRIPT)) {
    Write-Error "未找到 $SWEEP_SCRIPT —— 请确认在主工作区（非 worktree）执行本脚本。"
    exit 1
}
$gitMarker = Join-Path $REPO ".git"
if (-not (Test-Path $gitMarker -PathType Container)) {
    Write-Error "$gitMarker 不是目录（当前路径可能是某个 linked worktree，而非主工作区）——已中止。"
    exit 1
}

# ── 1. 解析绝对路径（#79 教训：SYSTEM 账户看不到当前用户的 PATH）──
Write-Host "[1/3] 解析 python / git 绝对路径..." -ForegroundColor Yellow
$pyCmd = Get-Command python -ErrorAction SilentlyContinue
if (-not $pyCmd) { Write-Error "未找到 python，请确认已安装并加入当前用户 PATH。"; exit 1 }
$pyExe = $pyCmd.Source
$gitCmd = Get-Command git -ErrorAction SilentlyContinue
if (-not $gitCmd) { Write-Error "未找到 git。"; exit 1 }
$gitDir = Split-Path $gitCmd.Source -Parent
Write-Host "      python: $pyExe" -ForegroundColor Green
Write-Host "      git   : $gitDir" -ForegroundColor Green

# ── 2. 生成启动包装脚本（绝对路径烘焙进文件内容,不依赖 SYSTEM 账户运行时的 PATH）──
Write-Host "[2/3] 生成 run-commit-sweep.ps1..." -ForegroundColor Yellow
$wrapperContent = @"
# 落库 sweep 启动包装（由 工具-注册落库sweep计划任务.ps1 生成,勿手改——
# 重跑注册脚本会覆盖此文件）。
# SYSTEM 账户的 PATH 不含当前用户级 python 安装目录、也未必含 git，
# 此处把两者的绝对目录显式烘焙进来，不依赖计划任务运行时的环境变量。
`$env:PATH = "$gitDir;`$env:PATH"
& "$pyExe" "$SWEEP_SCRIPT"
exit `$LASTEXITCODE
"@
Set-Content -Path $WRAPPER -Value $wrapperContent -Encoding UTF8
Write-Host "      已生成 $WRAPPER" -ForegroundColor Green

# ── 3. 注册计划任务（SYSTEM + AtStartup + N 小时重复,永不过期）──
Write-Host "[3/3] 注册计划任务 $TASK..." -ForegroundColor Yellow
if (Get-ScheduledTask -TaskName $TASK -ErrorAction SilentlyContinue) {
    Unregister-ScheduledTask -TaskName $TASK -Confirm:$false   # 重建以更新路径
}
$psArgs = "-NoProfile -ExecutionPolicy Bypass -File `"$WRAPPER`""
$action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument $psArgs -WorkingDirectory $REPO

$triggerStartup = New-ScheduledTaskTrigger -AtStartup
$triggerRepeat  = New-ScheduledTaskTrigger -Once -At (Get-Date) `
    -RepetitionInterval (New-TimeSpan -Hours $INTERVAL_HOURS) `
    -RepetitionDuration ([TimeSpan]::MaxValue)

$principal = New-ScheduledTaskPrincipal -UserId "SYSTEM" -LogonType ServiceAccount -RunLevel Highest
$settings  = New-ScheduledTaskSettingsSet -ExecutionTimeLimit (New-TimeSpan -Minutes 30) `
    -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries

Register-ScheduledTask -TaskName $TASK `
    -Action $action -Trigger @($triggerStartup, $triggerRepeat) `
    -Principal $principal -Settings $settings `
    -Description ("跨桌任务队列 §二 落库 sweep（队列 #68③）——只 add 批次声明文件、" +
                  "非 clean/非 master/推送非快进即整轮跳过不强推，详见 工具-落库sweep.py") `
    | Out-Null
Write-Host "      已注册（开机启动 + 此后每 $INTERVAL_HOURS 小时一次）" -ForegroundColor Green

Write-Host "`n注册完成。" -ForegroundColor Green
Write-Host "   立即手动跑一次（验证）: Start-ScheduledTask -TaskName $TASK" -ForegroundColor DarkGray
Write-Host "   查看上次运行结果      : Get-ScheduledTaskInfo -TaskName $TASK" -ForegroundColor DarkGray
Write-Host "   日志                  : $REPO\reports\sweep-commit.log" -ForegroundColor DarkGray
Write-Host "   回滚                  : schtasks /End /TN $TASK ; schtasks /Delete /TN $TASK /F" -ForegroundColor DarkGray
