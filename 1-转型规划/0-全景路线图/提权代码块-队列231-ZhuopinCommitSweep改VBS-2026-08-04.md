---
title: "提权代码块 · 队列 #231 ZhuopinCommitSweep 改用 VBS 免弹窗启动"
created: 2026-08-04
来源: CC，队列 #231 部署验证（本轮续跑）
status: 待发
---

# 提权代码块 · 队列 #231 ZhuopinCommitSweep 改用 VBS 免弹窗启动

## 背景

队列 #231 已把 `工具-注册落库sweep计划任务.ps1` 的 Action 从
`Execute=powershell.exe` 改为 `Execute=wscript.exe`（拉起新增的
`run-commit-sweep-hidden.vbs`，同 `ZhuopinAibotDevListener` 既有的
`WScript.Shell.Run` SW_HIDE(0) 免弹窗范式）。同批 `ZhuopinDecisionReminderDaily`
（`LogonType Interactive`）已重跑注册脚本生效并复核确认（`Actions[0].Execute`
现为 `wscript.exe`）。

**`ZhuopinCommitSweep` 本轮重跑注册脚本失败**：`LogonType S4U`，脚本内部
`Unregister-ScheduledTask` 在非提权 PowerShell 下报 `拒绝访问`
（`HRESULT 0x80070005`）——本机 S4U 类计划任务不仅**注册新任务**需要管理员权限
（#96 清单已记录的 `LogonType S4U` 门槛），**注销/修改现存 S4U 任务同样需要**
（本次新增的数据点）。**⚠️ 不以"脚本跑过了"为准**：脚本执行到"[2/3] 已生成
`run-commit-sweep.ps1`"仍打印为绿色成功，实际到"[3/3] 注册计划任务"这步才失败
——`Get-ScheduledTaskInfo`/表面日志均不会体现这一差异，唯一可靠的复核方式是
下方 `Actions[0].Execute` 检查。

**执行方式选用 `Set-ScheduledTask` 原地改 Action，而非重跑完整注册脚本**：
后者会先 `Unregister-ScheduledTask` 再 `Register-ScheduledTask`（整任务重建，
触发器/Principal/Settings 全部要求你手动核对是否走样），前者只替换 Action
一项、其余（触发器/`LogonType S4U`/`StartWhenAvailable`/电池策略等既有设置）
原样保留，风险面更小——同 2026-08-02 `提权代码块-队列199与193次要项` 处理
`ZhuopinDecisionReminderDaily`/`ZhuopinAibotDevListener` 时的同一手法。

## 执行方式

以**管理员身份**打开 PowerShell（右键 → 以管理员身份运行），整段粘贴执行：

```powershell
# 队列 #231：ZhuopinCommitSweep 改用 wscript.exe 拉起 VBS 免弹窗启动器，需管理员权限
$repo = "C:\Users\Paul Shao\OneDrive\Projects\企业AI转型"
$vbs  = Join-Path $repo "0-学习与工具\run-commit-sweep-hidden.vbs"

if (-not (Test-Path $vbs)) {
    throw "未找到 $vbs —— 请确认主工作区已同步到含本文件的提交（队列 #231）。"
}

$newAction = New-ScheduledTaskAction -Execute "wscript.exe" -Argument "`"$vbs`"" -WorkingDirectory $repo
Set-ScheduledTask -TaskName "ZhuopinCommitSweep" -Action $newAction

Get-ScheduledTask -TaskName "ZhuopinCommitSweep","ZhuopinDecisionReminderDaily" |
  ForEach-Object {
    [PSCustomObject]@{
      Task      = $_.TaskName
      Execute   = $_.Actions[0].Execute
      Argument  = $_.Actions[0].Arguments
      LogonType = $_.Principal.LogonType
    }
  } | Format-List
```

## 验证

最后一段 `Get-ScheduledTask` 两任务并列输出应显示：

- `ZhuopinCommitSweep`：`Execute` = `wscript.exe`，`Argument` 含
  `run-commit-sweep-hidden.vbs`，`LogonType` 仍为 `S4U`（本次不改登录类型，
  只换 Action）
- `ZhuopinDecisionReminderDaily`：`Execute` = `wscript.exe`（已于本轮非提权
  环境下重注册成功，此处并列只是复核未被这次操作意外改动）

改完**手动触发一次**验证真实生效（不弹窗、日志有新时间戳）：

```powershell
Start-ScheduledTask -TaskName "ZhuopinCommitSweep"
Start-Sleep -Seconds 5
Get-Content "C:\Users\Paul Shao\OneDrive\Projects\企业AI转型\reports\sweep-commit.log" -Tail 5
```

请把 `Get-ScheduledTask`/`Get-Content` 的实际输出回复给 CC 或下一位领取方**自行
复核**，不采信"跑过了"——不得仅凭本文件已执行就改写队列 #231 验收口径。

## 回滚

`Register-ScheduledTask`/`Set-ScheduledTask` 均不影响历史触发记录；若 VBS 路径
有问题导致 sweep 不再触发，改回原 Action 即可恢复：

```powershell
$repo = "C:\Users\Paul Shao\OneDrive\Projects\企业AI转型"
$wrapper = Join-Path $repo "0-学习与工具\run-commit-sweep.ps1"
$oldAction = New-ScheduledTaskAction -Execute "powershell.exe" `
    -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$wrapper`"" -WorkingDirectory $repo
Set-ScheduledTask -TaskName "ZhuopinCommitSweep" -Action $oldAction
```
