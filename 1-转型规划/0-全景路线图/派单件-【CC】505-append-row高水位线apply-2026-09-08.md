---
title: "派单件 ·【CC】#505 apply —— append-row 高水位线回写（OP-0908-X）"
created: 2026-09-08
status: 待粘贴（前置已解除：OP-0908-W 收工，#482 内容已在 master；design 审 1a/2a/3a/4a/5a 已落包）
派出线: Cowork 环境总线 OP-0907-AL
承接: 队列 §一 #505（design 包 `openspec/changes/editlock-append-row-highwater-writeback/`，OP-0908-K 出件、Shao Peishen 2026-09-08 审过）
---

# 派单件 ·【CC】#505 apply

▶ 粘贴端：CC（新开）—— 与 `OP-0908-L`（lint 工具）不撞文件，可并行；与 `OP-0908-K`／`W` 串行关系＝二者已收工。

▶ 首次派出：[OP-0908-X]

```
[OP-0908-X]【CC】505高水位线apply
【设置】执行环境：CC ｜ 分支：master（从 master 起 `claude/op0908x-appendrow-hwm-apply`）｜ worktree：☑（505-hwm-apply，新 worktree，收工自删）｜ 工作区：无（纯库内，不触碰 `.51`／企微机器人／定时任务）｜ session：新开 ｜ 派出线：Cowork 环境总线 OP-0907-AL
开工第一件事：调 mcp__ccd_session_mgmt__set_session_title（session_id 传字面量 "self"），标题：[Win]0908X-505高水位线apply。🔴 例外：你若是被 Task/Agent 起的子任务，跳过本行不要执行——子任务没有自己的 session，"self" 会解析到父 session、把调度你的那条会话改名（2026-08-28 实撞）。
读 ① `openspec/changes/editlock-append-row-highwater-writeback/tasks.md`（design 已审过：D1 (a) 自愈型／D2 (a) 先推线后写行／D3 (a) 单调 max／D4 (a) 只对队列系统目标；§0.8 与 design 顶部已落字）→ ② 队列 §一 `#505`（`python 0-学习与工具/工具-队列查询.py --row 505 --section 一 --field all`）→ ③ `CLAUDE.md` §3／§5 与 `.claude/rules/队列与落库.md` 恢复上下文，按 tasks 执行。本件为 A 类（口径已定、判据已写死），无需再问澄清，直接开工。

做什么：
1. 前置（机判，内容口径）：`git fetch origin`；`git cat-file -e origin/master:openspec/changes/editlock-append-row-highwater-writeback/design.md` 退出码 0 且 `git log origin/master --oneline --grep="#482" -1` 非空 ⇒ 继续；任一不过 ⇒ `pause --no-notify` 报一句即停。🔴 不用 `merge-base --is-ancestor <老分支>` 判前置（ff-only＋rebase 下恒假）。
2. 按 tasks.md 逐项 apply：`0-学习与工具/工具-共享文档编辑锁.py` 的 `append-row --number N` 写入成功后走与 `--reserve` 同一条高水位线回写路径（D1 自愈型、D2 先推线后写行、D3 `max(当前,N)`、D4 只对队列系统目标）；回写失败 fail-loud。
3. 单测：`0-学习与工具/test_工具-共享文档编辑锁.py` 加 ⑴ `--number` 写入后高水位线＝新行号 ⑵ 紧接 `--reserve` 取号不撞 ⑶ 非队列目标不推线；全量回归以 `OP-0908-W` 实测基线（4 failed／3347 passed／3 skipped，4 条为 master 既有）对照，**零回归即过**（Shao Peishen 2026-09-08 答 1a：验收闸＝零回归、非全绿）。
4. 收工：push 自己分支（不 ff master，🟡 待他一字母）；走锁回写 `#505` 状态列（commit、单测数、回归对照）＋登记 §二；收工汇总末附「待你一字母」与答复模板；`/opsx:archive` 留到 ff 后由下一棒或 sweep 归档。

不做什么：
- 不 ff master、不在主仓 commit；不改 `--reserve` 既有语义；不碰 `工具-落库sweep.py`、`工具-opener块lint.py`（`OP-0908-L` 触碰区）。
- 不修 `#464`（release 侧时序缺陷另有其行）；不复述队列协议。
```
