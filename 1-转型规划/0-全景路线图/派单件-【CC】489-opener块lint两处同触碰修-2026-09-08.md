---
title: "派单件 ·【CC】#489 opener 块 lint 两处同触碰修（OP-0908-L）"
created: 2026-09-08
status: 待粘贴（软序已满足：single-guarded-copy 包 09-08 23:2x 已在 origin/master）
派出线: Cowork 环境总线 OP-0907-AL
承接: 队列 §一 #489（2026-09-08 20:2x 去 🛑，WIP 实测 21/22→22/22）
---

# 派单件 ·【CC】#489

▶ 粘贴端：CC（新开）—— **随时可粘**：软序由会话自己机判（做什么 1），不靠人看 git log。机器判据（🔴 09-08 23:2x 改为内容口径：ff-only＋rebase 下老分支 SHA 永远不是 master 祖先，`merge-base --is-ancestor` 恒 exit 1，是错量具）＝`git cat-file -e origin/master:openspec/changes/single-guarded-copy/design.md` 退出码 0（泳道 `503-opener-single` 的产出已在 master；23:2x 实测 exit 0，**现在可粘**）；≠0 ⇒ 会话 `pause` 报一句即停、零改动。

▶ 首次派出：[OP-0908-L]

```
[OP-0908-L]【CC】489lint双修
【设置】执行环境：CC ｜ 分支：master（从 master 起 `claude/op0908l-opener-lint-489`）｜ worktree：☑（489-opener-lint，新 worktree，收工自删）｜ 工作区：无（纯库内，不触碰 `.51`／企微机器人／定时任务）｜ session：新开 ｜ 派出线：Cowork 环境总线 OP-0907-AL
开工第一件事：调 mcp__ccd_session_mgmt__set_session_title（session_id 传字面量 "self"），标题：[Win]0908L-489lint双修。🔴 例外：你若是被 Task/Agent 起的子任务，跳过本行不要执行——子任务没有自己的 session，"self" 会解析到父 session、把调度你的那条会话改名（2026-08-28 实撞）。
读 ① 队列 §一 `#489`（`python 0-学习与工具/工具-队列查询.py --row 489 --section 一 --field all`，两处缺陷的实证／期望产出全在该行）→ ② `CLAUDE.md` §3／§5 与 `.claude/rules/队列与落库.md` 恢复上下文，按该行执行。本件为 A 类，直接开工。

做什么：
1. 前置（机判，不问人，内容口径）：`git fetch origin` 后跑 `git cat-file -e origin/master:openspec/changes/single-guarded-copy/design.md`；退出码 0 ⇒ 继续（`#503`／`#487` 本轮只出 openspec 包止步 design 审、未动 lint 工具，与本棒不撞文件；其 apply 在本棒之后叠加）；≠0 ⇒ `python 0-学习与工具/工具-泳道看护状态机.py pause --no-notify` 报一句「软序未到：op0908p 未 ff」即停，不在旧基线上改、不轮询等待。
2. ⑴ 判据正本自身被当成被判对象：`工具-opener块lint.py` 与编辑锁 release 侧 opener 守卫对 `opener骨架.md`／`专线opener模板库.md` 的占位骨架块豁免（按文件名或「骨架」frontmatter 标记二选一，收工汇总写明取舍）；⑵ 全量 `--enforce` 跑 9 小时输出 0 字节：定位挂死点（按行内实证），加超时与进度输出，单文件失败不拖死全量。
3. 顺带核 `#489` 末段登记的「骨架样例句含『子任务』而无『例外／跳过本行』触发 F2」：二选一（骨架样例补句／F2 对 §三bis 块豁免），在收工汇总给推荐与代价，🟡 等他一字母再改骨架。
4. 单测与实测：对骨架、模板库、近三份看护件各跑一次 `--file --enforce`，判据正本零误报、真实 opener 判定不变；全量 `--enforce` 在 5 分钟内出结果。
5. 🆕 **机制化（Shao Peishen 2026-09-08 答 1a，`#284` 退休制阈值触发，并入 `#461` 生成器）**：`0-学习与工具/工具-opener生成.py` 加 `--variant reference`——只输出四行引用版（`[OP]【CC／Cowork】<短名>` 标题／`【设置】`六字段／`set_session_title` 行（Cowork 变体无此行）／「读 `<派单件仓库根相对路径>` 全文＋ CLAUDE.md 恢复上下文，按该件执行。本件为 A／B 类」），须过 `工具-opener块lint.py --enforce`；参数 `--ref-file <路径>` 必填、`--do`／`--dont` 传入即 fail-loud（引用版正文在文件里）。单测：Cowork／CC 两变体各一条 golden 对照。并在 `opener骨架.md`「状态标记三式」节下加一行纪律：「🔴 聊天里给他的开场词＝`--variant reference` 输出原样贴入，禁手抄；>500 字有派单件一律引用版」（骨架改动与步骤 3 同批、等他一字母）。`#461` 状态列追加指针、不改其 `[S:done]`。
6. 收工：push 自己分支（不 ff master）；走锁回写 `#489` 状态列＋`#461` 追加指针＋登记 §二；收工汇总末附「待你一字母」与答复模板。

不做什么：
- 不 ff master、不在主仓 commit；不改 lint 的六个失效形态判据本身，只修「判据正本被误判」与「全量挂死」两处。
- 不动 `opener骨架.md` 正文（3 的改法待他定）；不碰 `#503`／`#487` 已合入的改动。
```
