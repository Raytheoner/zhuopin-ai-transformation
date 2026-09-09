---
title: "开场 prompt ·【Cowork】FI5 需求 grill · 存量补 grill 第四个样本（会话末即 design 审）"
created: 2026-09-09
派出线: Cowork 环境总线 OP-0907-AL（代执行：本周计划-09-09 第 4 步「下午 1 小时 grill FI5」无人出 opener，按 CLAUDE.md §5 代执行优先直接出件）
队列行: §一 #436 ⑶①（人的那半，机制环境队列）；场景承接行 §一 #470（业务场景队列）
依据: 端到端构建workflow优化-方案-2026-09-06.md §六 决议 ③⑤；rules/场景建造与合规 §二「新场景 propose 前置＝intent.md」；rules/文档与全景治理 §二「排期＝不晚于」（2026-09-08）；同形样本 `开场prompt-【Cowork】FI6需求grill-第三个样本-2026-09-08.md`
status: 待你在 Cowork 里起
---

# 开场 prompt ·【Cowork】FI5 需求 grill（存量补 grill 之四）

> 与 FI10／FI8／FI6 同形，只换场景。FI5 包 `fi5-expense-audit-mvp`：**无 `design.md`**、tasks 29 项未勾／15 项已勾；`config.py` **四条 `Criterion` 全部未签认**（`TRAVEL_STANDARD_TABLE`／`ENTERTAINMENT_LIMIT_TABLE`／`L2_BUDGET_BLOCK_PCT`／`RISK_GRADE_BOUNDARIES`）；`data/mock/` 三件（`expense_claims`／`expense_lines`／`budget_balance`）；`跨场景前置数据与知识库任务总表.md` **实测无 FI5 行**（与 FI6／FI8 同族，本身即一个前沿问题）；权威排期 **2027-02 启动**（全景规划 §加速启动总览排期表，L645 场景块）——按 2026-09-08 口径「排期＝不晚于」，本次 grill 就是提前开工，不改排期表。
> ✅ 财务部串行闸 **2026-09-09 21:3x 现取 `✅ 开`**（`财务部#17` 已回件回灌）——FI5 的待专员点仍只进 §三、不在 grill 会话起草信；起草归业务总线按台账「待问」点投影。
> 📌 次序（`#463` 十四场景补 grill 队列）：FI10 ✅ → FI8 ✅ → FI6 ✅ → **FI5（本件）** → FI9 → SC10 → SC11 → SC4 → O3／O4／Q4／FI4／FI7（`#508`–`#512`，09-08 新立）。

▶ 首次派出：[OP-0909-Y]

**开场词（复制即用，▶ 粘贴端：Cowork 新会话）**：

```
[OP-0909-Y]【Cowork】FI5需求grill
【设置】执行环境：Cowork ｜ 分支：master ｜ worktree：☐（不建，只产 `intent.md` 与 `design.md`） ｜ 工作区：无 ｜ session：新开 ｜ 派出线：Cowork 环境总线 OP-0907-AL
读 ① `1-转型规划/0-全景路线图/开场prompt-【Cowork】FI5需求grill-第四个样本-2026-09-09.md` → ② `CLAUDE.md` §4 路由表 → `.claude/rules/场景建造与合规.md` §二（intent.md 前置一句） 恢复上下文，按下述执行。本件为 A 类。

做什么：
1. 调 skill `zhuopin-requirement-grill`，受访者＝Shao Peishen 本人（不问任何专员）。M2 先扫：全景规划 `卓品智能AI转型全景规划.md` §2.1.4「场景 FI5：费用报销智能审核」块（L645 起）＋§加速启动总览排期表财务列（**FI5 权威排期＝2027-02 启动＝不晚于**，只读、不改排期表）、`4-数字员工/财务部/FI5-费用报销智能审核/`（`fi5_expense_audit/config.py` **四条 `Criterion` 全未签认**：`TRAVEL_STANDARD_TABLE`／`ENTERTAINMENT_LIMIT_TABLE`／`L2_BUDGET_BLOCK_PCT`／`RISK_GRADE_BOUNDARIES`；`data/mock/` 三件；`tests/`）、`openspec/changes/fi5-expense-audit-mvp/`（proposal＋specs 四份＋tasks **29 项未勾／15 项已勾，无 `design.md`**）、`5-平台底座/zhuopin_platform/zhuopin_platform/criteria_signoff/`（`unsigned_keys()` 即待问点）、队列 §一 `#470`／`#463`（`工具-队列查询.py --row N --section 一`，🔴 不得 Read／grep 队列真身）、`跨场景前置数据与知识库任务总表.md`（**实测无 FI5 行——这本身就是一个前沿问题**）、FI10／FI8／FI6 的 `intent.md` §一（U9C 取数通道、财务侧 L2 双签岗位等同族事实，直接复用不重问）。凡能查到的一律不问。
2. 按前沿分轮问他（每轮 §二 格式：编号＋(a)/(b)＋推荐＋默认项，末尾一行答复模板），直到前沿为空。三选一分流每一问：能查的自查／只有他能定的本轮问／只有专员知道的落 §三 待专员（带口径点 ID 占位：与 `Criterion.key` 同名的写 `FI5-TRAVEL_STANDARD_TABLE` 等四个，注册表没有的新点形如 `FI5-G-01`）。🔴 判据／口径／阈值类永不默认生效；`L2_BUDGET_BLOCK_PCT` 涉 L2 门禁，只定「谁签、签什么」不定自动放行。
3. 产出 `4-数字员工/财务部/FI5-费用报销智能审核/intent.md`（frontmatter `status: 待确认`／`场景: FI5`／`scenario_name: 费用报销智能审核`／`grill会话: OP-0909-Y`／`受访者: Shao Peishen`／`进入判例包的开放点数量: N`；三节：§一 M2 已自查事实／§二 已定／§三 待专员）。他确认后改 `status: 已确认` 并补 `确认人`／`确认日期`。
4. 同一会话把 §二 写进 `openspec/changes/fi5-expense-audit-mvp/design.md`（**该文件本不存在，本次新建**）Decisions、§三 写进 Open Questions「待专员」；**会话末当场 design 审**（他一个字母），审过在 `design.md` 顶部记「design 审：✅ 已过 —— Shao Peishen <日期>」。
5. 记录 `进入判例包的开放点数量`（基线 SC2＝4、FI10＝7、FI8＝8、FI6＝见其 intent）；§三 待专员各点在 `#470` 行内登「判例包待办」指针（走 `0-学习与工具/工具-共享文档编辑锁.py` 的 `edit-row --append`，域 业）；**台账建点交环境线**（经 `LedgerStore.append_many` 写 `口径点台账/财务域.jsonl`，不手写 JSONL）——本会话只产 intent，不写台账。
6. 收工另做两件：⑴ 机制环境队列 `#436` 行追加一句「FI5 grill 已做，开放点 N，design 审结果」（`edit-row --append`，域 机）；⑵ 逐条过 skill `zhuopin-kickoff-prompt` 转场判据五条并出声。

不做什么：
- 🔴 不对专员跑 grill、不发任何对外消息、不在本会话起草信（闸虽开，起草归业务总线按台账待问点投影）；不改 `config.py` 判据值（`None` 占位保持）。
- 🔴 不改排期表：FI5 权威排期 2027-02＝不晚于，本次提前 grill 是口径允许的，排期表本身由全景线在重组循环里改。
- 🔴 不动其余包（次序：FI9 → SC10 → SC11 → SC4 → `#508`–`#512`，各自另起会话）。
- 🔴 design 审不代拍：他不答即停在 `status: 待确认`。

收工：产出登记 §二 待 commit 批次（走 `0-学习与工具/工具-共享文档编辑锁.py`，勿裸改、勿自行 commit），由落库 sweep 取活。
```
