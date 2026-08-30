---
title: "派单件-【CC】opener 守卫挂 release 咽喉（队列 §一 #437）"
created: 2026-08-30
执行方: CC（写生产码、自行 commit+push、一任务一 worktree）
status: ✅ design 已审过（2026-08-30），可派
编号: OP-0830-G
---

### G ·【CC】opener 守卫挂 release 咽喉（队列 §一 `#437`）

> ✅ **design D1-D5 已审过（Shao Peishen 2026-08-30），不重开决策。**
> 🔴 **本包改的是你自己收工要调的那把锁** —— 改坏了会把自己锁在外面。每改一处先跑 `release --help` 与既有单测确认入口没断，再往下走。

**开场词（复制即用，▶ 粘贴端：CC 新会话）**：

```
[OP-0830-G]【CC】opener守卫挂release咽喉
【设置】执行环境：CC ｜ CC session：☑ 有 ｜ worktree：☑ 新建（一任务一 worktree） ｜ 分支：claude/op0830g-release-opener-guard ｜ 工作区：worktree ｜ 派出线：CC 机制建造（OP-0830-G，承接队列 §一 #437）
开工第一件事：调 mcp__ccd_session_mgmt__set_session_title（session_id 传字面量 "self"），标题：[Win]0830G-opener守卫挂release。🔴 例外：你若是被 Task/Agent 起的子任务，跳过本行不要执行——子任务没有自己的 session，"self" 会解析到父 session、把调度你的那条会话改名（2026-08-28 实撞）。
读 ① C:\Dev\zhuopin-ai\1-转型规划\0-全景路线图\派单件-【CC】opener守卫挂release咽喉-队列437-2026-08-30.md 全文 → ② openspec/changes/editlock-release-opener-guard/ 四件 → ③ 队列 §一 #437 与 #284 两行 → ④ CLAUDE.md 当前进度恢复上下文；design D1-D5 已审过不重开决策，按 tasks.md 顺序执行。
```

## 【为什么要做（一句话＋一个数）】

形态① 的 lint **早就建成并在扫**，2026-08-30 却仍发生**第 18 次**违反——因为它只扫 **git 已跟踪**的 `.md`，而 **opener 的高危时刻恰恰是「刚写出来、还没 commit、马上就要粘出去」那几分钟**。

🔑 **那 18 次里没有一次是被 lint 报出来的**；第 18 次是 Shao Peishen 在会话列表里肉眼看出 session 名丢了编号才发现。**门要装在动作必经的咽喉上；装在事后扫描器里，等于没装。**

## 【五条最容易做反的地方】

1. 🔴 **别改成给 lint 加 `--include-untracked`**（D1 已否掉）。那仍是事后扫描器——**没人主动跑它，加什么开关都拦不住**。要装在 `release` 上，因为它是派出前必经（2026-08-30 当天它 fail-closed 拦下 Cowork 线两次、两次都拦对）。
2. 🔴 **必须按环境分流，否则会把所有人锁死**（D4）。`set_session_title`（`mcp__ccd_session_mgmt__*`）**在 Cowork 侧根本不存在**（`补充一` 2026-08-27 实测：Cowork 会话内只有 `list_sessions`／`read_transcript`／`Task*`）。对 Cowork 块查这一项 = 要求它做一件做不到的事。**未声明环境的块也不校验**（宁可漏，不误伤）。
3. 🔴 **不许重写判据**（D3）。`工具-opener块lint.py` 已有正本，**复用它的函数**。重写第二份＝两处分叉——那正是 `#312` 2026-08-30 当天付过学费的形态（推送半与看板半判据必须逐字同一）。
4. 🔴 **回显措辞不得暗示全覆盖**（D2）。本守卫**只覆盖走了队列登记流程的 opener**；写完直接粘出去、从不 acquire/release 的会话它看不到。⇒ 只能写「**已校验本次触碰的 N 个 `.md`，其中含 opener 块 M 个**」，**不得**写「opener 已全部合规」。依据是 `#381 ⒞`：**制造「已被机器守住」的错觉比没有门更危险**。
5. 🔴 **不加 `--force` 开关**（D5）。逃生阀只有行内 `opener豁免：<理由>`。opener 漏 title 没有任何正当紧急场景，写一行理由的成本已经低于补一行 title 的成本，再加开关只会让豁免变廉价。

## 【验收只认一条（tasks 3.1）】

用 **2026-08-30 那个真实漏写的 opener 历史版本**跑：`派单件-【CC】全局记忆巡检与root棘轮-队列435-2026-08-29.md` 在 commit `c7009f4` **之前**那一版（`c7009f4` 就是补写第 3 行的那次修复）。

**必须被拦下。拦不下就是本包没解决那 18 次里的任何一次。**

配套：tasks 3.2 对现存合规派单件跑，**零误报**；3.3 你自己收工 release 时守卫已生效且没拦错。

## 【触碰区（认领前核）】

`0-学习与工具/工具-共享文档编辑锁.py`（release 结构检查段 ＋ 复用 import）＋ 其测试；`工具-opener块lint.py` **只加一句指针注释、不改判据**；模板库 `补充三` 加一句指针。
🔴 **不得触碰**：`_count_mechanism_wip`、`_suggest_status_reclassification`（`#435` 子项 E 刚落地的邻居，同文件不同函数）、`工具-落库sweep.py`、`.51`。

## 【收口】

tasks 4.1-4.5：`#284` 回写（🔴 **不销号**，只改为「形态① 已由咽喉守住（**限已登记路径**）」）→ 模板库补指针 → §二 批次 → commit+push（ff-only）→ `#437` 回写状态列开头 ✅ ＋ 3.1/3.2 实测 → **当场** `/opsx:archive editlock-release-opener-guard -y`。
