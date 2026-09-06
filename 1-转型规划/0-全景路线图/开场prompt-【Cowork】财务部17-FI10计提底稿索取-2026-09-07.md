---
title: "开场 prompt ·【Cowork】财务部#17 · FI10 计提底稿索取（台账投影第一封信）"
created: 2026-09-07
派出线: Cowork 环境总线 OP-0906-W
队列行: §一 #474（业务场景队列）；口径点 `FI10-G-07`（`口径点台账/财务域.jsonl`）
依据: FI10 intent.md §三 第 7 条＋design D9「第一封信只索取底稿」；端到端构建workflow优化-方案-2026-09-06.md §四 W2「信是视图、点是真身」
status: 待你在 Cowork 里起
---

# 开场 prompt ·【Cowork】财务部#17 · FI10 计提底稿索取

> 这是**第一封从口径点台账投影出来的信**：台账里 FI10 七个点已建（2026-09-07 06:31，`OP-0906-W`，经 `LedgerStore.append_many`），其中 `FI10-G-07` 是 `材料索取`、其余六条 `判据类` 待问。按 design D9，**第一封只要底稿**——没有真实计提底稿，判例批改表就没有真实案例可用，六条判据类一条都不能问。
> 闸：`工具-跟进闸查询.py --to 唐燕萍` 2026-09-07 06:30 实测 ✅ 开（`财务部#16` 已闭环，下一个可用号 `财务部#17`）；起草前再现取一次。
> 🔴 与 CC 批 `B-0907_E`（六个 openspec 包起草）零触碰重叠。

▶ 首次派出：[OP-0907-L]

**开场词（复制即用，▶ 粘贴端：Cowork 新会话）**：

```
[OP-0907-L]【Cowork】财务部17底稿索取
【设置】执行环境：Cowork ｜ 分支：master ｜ worktree：☐（不建，只产信件 md+docx 与 README 登记）｜ 工作区：无 ｜ session：新开 ｜ 派出线：Cowork 环境总线 OP-0906-W
读 ① `1-转型规划/0-全景路线图/开场prompt-【Cowork】财务部17-FI10计提底稿索取-2026-09-07.md` → ② `CLAUDE.md` §4 路由表 → `.claude/rules/跟进信与专员.md`＋`6-人才与组织/CLAUDE.md` 恢复上下文，按该件执行。本件为 A 类（收信人／内容／类型已由 design D9 与 intent §三 定死），直接开工。

做什么：
1. 现取闸：`python 0-学习与工具/工具-跟进闸查询.py --to 唐燕萍`，锁即停并登记「待前信闭环后发」；开则继续。
2. 读台账取点（不 Read 主表、不凭记忆）：`python -c "import sys; sys.path.insert(0,'5-平台底座/zhuopin_platform'); from zhuopin_platform.coverage_point_ledger.store import LedgerStore; from zhuopin_platform.coverage_point_ledger.models import Domain; s=LedgerStore('6-人才与组织/部门AI专员跟进/口径点台账'); [print(e.id, e.status.value, e.type.value, e.case_text) for e in s.read_domain(Domain.for_id('FI10-x'))]"`——本信只投影 `FI10-G-07`（材料索取），六条判据类**不进本信**（D9），只在信末「本场景还剩 N 项待确认」按 §六 计数写 6。
3. 调 skill `zhuopin-followup-letter`（已安装版＝引用式指针，会带你读源码 v3.8）起草 B 类三要素信 `6-人才与组织/部门AI专员跟进/财务部-唐燕萍-跟进-2026-09-07-FI10存货跌价计提底稿索取.md`：做什么＝提供近 2–3 年跌价准备计提底稿（按年度／按物料类别各一份样例即可，不必全量；脱敏可）、怎么交＝企微私聊机器人放文件、什么时候交＝请其自定并回一个日期；frontmatter 必写 `决策点: 1 项（材料索取：近 2–3 年跌价准备计提底稿）`；正文明写这是 FI10 第一封、后续判据确认以其底稿里的真实案例成判例包三选一。称呼一律按 `6-人才与组织/人员名录-称谓与性别-正本.md`，第三人称先核。
4. 代词自检 → `md-to-word` 出同名 docx → `python 0-学习与工具/工具-跟进信README登记.py append …`（🔴 登记 CLI 已上线 `决策点:` 校验——缺字段会被拒，这是该机器守的**首次真实触发机会**，被拒即如实记一句）。状态只写 `⏳ 待你审`。
5. 台账回写（投影留痕，走模块不手写）：对 `FI10-G-07` append 一条 `转态`→`在途`，`letters=["财务部#17（待你审，暂不占号）"]`，`fact_date`＝起草日，`by`＝本会话编号；六条判据类**不动**。
6. 收工：§二 批次（信件 md＋docx、README 主表由登记 CLI 改、`口径点台账/财务域.jsonl`），`#474` 行追加一句「财务部#17 已起草待审，投影自台账 G-07」。转场判据五条出声。

不做什么：
- 🔴 不发送（发送＝skill `zhuopin-send-followup`，须他读回「收信人＋编号＋标题」后答「发」）；不问六条判据类；不改 `config.py`；不碰 `B-0907_E` 六个 openspec 包目录。
- 🔴 不手写 JSONL、不改台账既有行；不给姚祖怡起草（`采购部#21` 闸锁，会签信待其闭环）。

收工：产出登记 §二 待 commit 批次（走 `0-学习与工具/工具-共享文档编辑锁.py`，勿裸改、勿自行 commit），由落库 sweep 取活。
```
