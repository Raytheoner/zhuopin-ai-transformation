---
title: "派单件-【CC】执行体对齐 · wecom-service-home 落后 174 提交（队列 §一 #438）"
created: 2026-08-30
执行方: CC（改常驻执行体、跑注册脚本、重启服务）
status: 待派——🔴 须 Shao Peishen 在场时做（动常驻机器人）
编号: OP-0830-F
---

### F ·【CC】执行体对齐 · `wecom-service-home` 落后 174 提交（队列 §一 `#438`）

> 🔴 **须他在场时做**：本件动的是**正在跑的企微机器人执行体**与**每日跟进信派发计划任务**。中途 worktree 被 reset 时，计划任务指向的文件会短暂消失——**撞上触发时刻那次派发就失败**。

**开场词（复制即用，▶ 粘贴端：CC 新会话）**：

```
[OP-0830-F]【CC】执行体对齐wecom-service-home
【设置】执行环境：CC ｜ CC session：☑ 有 ｜ worktree：☐ 不新建（本件的对象就是既有执行体 worktree，新建反而错） ｜ 分支：master（挑拣）＋ ops/wecom-service-home（对齐） ｜ 工作区：主工作区 ＋ .claude/worktrees/wecom-service-home ｜ 派出线：CC 机制建造（OP-0830-F，承接队列 §一 #438）
开工第一件事：调 mcp__ccd_session_mgmt__set_session_title（session_id 传字面量 "self"），标题：[Win]0830F-执行体对齐wecom-service-home。🔴 例外：你若是被 Task/Agent 起的子任务，跳过本行不要执行——子任务没有自己的 session，"self" 会解析到父 session、把调度你的那条会话改名（2026-08-28 实撞）。
读 ① C:\Dev\zhuopin-ai\1-转型规划\0-全景路线图\派单件-【CC】执行体对齐-wecom-service-home落后174-队列438-2026-08-30.md 全文 → ② 队列 §一 #438 行 → ③ CLAUDE.md 当前进度恢复上下文；按本件五步顺序执行，每步过判据才走下一步。
```

## 【为什么这件事要紧（一句话＋一个数）】

**跑企微机器人的执行体落后 master 174 个提交** —— 2026-08-30 当天 `#435`／`#312` 落地的全部修复（A4 备份巡检、root 棘轮、`[A:]` 排除、opener 环境过滤）**在机器人侧一条都没生效**。今早 08:31 那条把 `#435` 误报成「可立即开工」的推送就是它发的；不对齐，**明天还会照发老行为**。

🔑 **这是 `CLAUDE.md` 顶部 `OP-0819-A` ⑷ 那条判据的第二次发生**（首次＝`ZhuopinDecisionReminderDaily` 落后 246 个，其间所有修复均未生效）。**同一个坑，换了个执行体。**

## 【现状实测（2026-08-30 14:0x，本机 git）】

| 项 | 值 |
|---|---|
| 执行体 worktree | `.claude/worktrees/wecom-service-home` |
| 分支 | `ops/wecom-service-home` |
| **落后 master** | **174 个提交** |
| 领先 master | **1 个**（`de68cc9`） |
| 脏文件 | 0 |
| 自动对齐工具干跑 | **退出码 11，不可 ff，已停手**（`是否祖先=False, ahead=1`） |

**领先的那 1 个提交**：`de68cc9 wip(aibot): 保存未提交的 run-followup-dispatch-check.ps1`（15 行，**master 上不存在**）。

## 【🔴 三条改变处置方式的取证（别跳过）】

1. **那 15 行是生成物，不是手写源码** —— 文件头两行自己写着「由 `register-followup-dispatch-task.ps1` 生成，**勿手改——重跑注册脚本会覆盖此文件**」。生成脚本**在 master 上存在** ⇒ 可重新生成。
2. **但它不能被简单丢弃** —— 计划任务 `ZhuopinFollowupDispatchDaily` 的 Action 实测是：
   `wscript.exe "C:\Dev\zhuopin-ai\.claude\worktrees\wecom-service-home\5-平台底座\wecom-aibot-service\run-followup-dispatch-hidden.vbs"`
   **计划任务指向的就是这个 worktree 里的文件**。`reset --hard` 会让它们短暂消失 ⇒ **撞上每日触发时刻，那次跟进信派发就失败**。
3. **那 15 行里有不能丢的知识** —— 它显式设 `WECOM_AIBOT_QUEUE_PATH` 指向**主工作区**队列，注释写明理由：不设的话 `dispatch_followup_letters.py` 会按 `__file__` 反推、读到 **worktree 自己的队列副本**（滞后），审计也写进 worktree 自己的 `reports/` 与其余脚本分裂——**正是队列 `#126` 修过的同类问题**。⇒ **重新生成后必须核这一行还在。**

## 【五步，每步过判据才走下一步】

1. **挑拣**：把 `de68cc9` 挑进 master（`cherry-pick` 或等价），push。**判据**：`git cat-file -e master:5-平台底座/wecom-aibot-service/run-followup-dispatch-check.ps1` 成功。
2. **选时间窗**：确认距 `ZhuopinFollowupDispatchDaily` 下次触发 **≥30 分钟**（`Get-ScheduledTask … | Get-ScheduledTaskInfo` 看 `NextRunTime`）。**判据**：窗口够，否则等下一个窗口，**不要硬做**。
3. **对齐**：`powershell -NoProfile -File "0-学习与工具/工具-执行体对齐重启.ps1" -WorktreeName wecom-service-home -DryRun` **先干跑**——此时应已可 ff（ahead=0）。干跑过了再去掉 `-DryRun` 实跑。**判据**：退出码 0，且 `git -C <worktree> rev-list --count HEAD..master` ＝ **0**。
4. **重生成**：跑 `register-followup-dispatch-task.ps1` 重新生成包装脚本与 `.vbs`。**判据**：两个文件都在磁盘上；且 `run-followup-dispatch-check.ps1` 里**仍有那行 `WECOM_AIBOT_QUEUE_PATH` 指向主工作区**（取证 ③，丢了就是 `#126` 复发）。
5. **验活**：手动触发一次计划任务（或干跑 `dispatch_followup_letters.py`），确认能跑通且审计落点在**主工作区** `reports/`，不在 worktree 自己的 `reports/`。**判据**：审计文件路径正确。

## 【触碰区】

`.claude/worktrees/wecom-service-home`（整个执行体）；master 上 `5-平台底座/wecom-aibot-service/run-followup-dispatch-check.ps1`（新增）；Windows 计划任务 `ZhuopinFollowupDispatchDaily` 的生成物。
🔴 **不得触碰**：`.51` 现网服务；队列写入路径（本件不改队列，只在收工回写 `#438`）。

## 【收口】

五步全过 → §二 批次登记 → commit+push（ff-only）→ `#438` 回写状态列开头 ✅ 并附**对齐后的 `落后 master` 实测数字**（必须是 0）。
⚠️ **本件不走 openspec**：纯运维对齐动作，不改任何模块对外语义、不改全项目口径（§5 门槛三条均未命中）。
