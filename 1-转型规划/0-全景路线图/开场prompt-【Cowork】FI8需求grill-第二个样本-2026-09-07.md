---
title: "开场 prompt ·【Cowork】FI8 需求 grill · 存量补 grill 第二个样本（会话末即 design 审）"
created: 2026-09-07
派出线: Cowork 环境总线 OP-0906-W
队列行: §一 #436 ⑶①（人的那半）；场景承接行 §一 #472（业务场景队列）
依据: 端到端构建workflow优化-方案-2026-09-06.md §六 决议 ③⑤；rules/场景建造与合规 §二「新场景 propose 前置＝intent.md」；FI10 样本 `开场prompt-【Cowork】FI10需求grill-首个样本-2026-09-06.md`（同形，改场景）
status: 待你在 Cowork 里起
---

# 开场 prompt ·【Cowork】FI8 需求 grill（存量 8 包补 grill 之二）

> 与 FI10 同形，只换场景。FI8 包 `fi8-cashflow-forecast-mvp`：无 `design.md`、26 项未勾；`config.py` 三条 `Criterion`（`CASH_GAP_THRESHOLD`／`COLLECTION_ESCALATION_CRITERIA`／`PAYMENT_CYCLE_SAMPLING`）全部未签认；前置总表实测无 FI8 行；链 D 联动点 L8（O2 缺口 → FI8 收入递延）。
> ⚠️ 财务部串行闸：`财务部#17`（FI10 底稿索取）正在起草/待审，FI8 的待专员点**只进 §三、不起草信**——本来 grill 就不发信。

▶ 首次派出：[OP-0907-M]

**开场词（复制即用，▶ 粘贴端：Cowork 新会话）**：

```
[OP-0907-M]【Cowork】FI8需求grill
【设置】执行环境：Cowork ｜ 分支：master ｜ worktree：☐（不建，只产 `intent.md` 与 `design.md`）｜ 工作区：无 ｜ session：新开 ｜ 派出线：Cowork 环境总线 OP-0906-W
读 ① `1-转型规划/0-全景路线图/开场prompt-【Cowork】FI8需求grill-第二个样本-2026-09-07.md` → ② `CLAUDE.md` §4 路由表 → `.claude/rules/场景建造与合规.md` §二（intent.md 前置一句）恢复上下文，按该件执行。本件为 A 类（口径已定：产出定名 `intent.md`、三节固定、会话末 design 审；FI10 样本已走通一遍），直接开工。

做什么：
1. 调 skill `zhuopin-requirement-grill`，受访者＝Shao Peishen 本人（不问任何专员）。M2 先扫：全景规划 §2.1.4「场景 FI8」块＋§5 链 D／联动点 L8 段＋唯一权威排期表财务列（只读，不改排期）、`4-数字员工/财务部/FI8-现金流预测与智能预警/`（`config.py` 三条 `Criterion`、`data/mock/`、tasks 未勾 26 项）、`openspec/changes/fi8-cashflow-forecast-mvp/`（proposal＋tasks，无 design）、`5-平台底座/zhuopin_platform/zhuopin_platform/criteria_signoff/`（`unsigned_keys()` 即待问点）、`#472`／`#463`、`业务特性驱动的四链联动蓝图-42场景重梳-2026-07-05.md`（链 D 数据契约）、`跨场景前置数据与知识库任务总表.md`（实测无 FI8 行——本身就是一个前沿问题）、FI10 的 `intent.md` §一（U9C 取数通道无主等同族事实，直接复用不重问）。凡能查到的一律不问。
2. 按前沿分轮问他（每轮 §二 格式：编号＋(a)/(b)＋推荐＋默认项，末尾一行答复模板），直到前沿为空。三选一分流每一问：能查的自查／只有他能定的本轮问／只有专员知道的落 §三 待专员（带口径点 ID 占位，形如 `FI8-G-01`，注册表已有的与 `Criterion.key` 同名：`FI8-CASH_GAP_THRESHOLD` 等）。
3. 产出 `4-数字员工/财务部/FI8-现金流预测与智能预警/intent.md`（frontmatter `status: 待确认`／`场景: FI8`／`grill会话: OP-0907-M`／`进入判例包的开放点数量: N`；三节：§一 M2 已自查事实／§二 已定／§三 待专员）。他确认后改 `status: 已确认`。
4. 同一会话把 §二 写进 `openspec/changes/fi8-cashflow-forecast-mvp/design.md` Decisions、§三 写进 Open Questions「待专员」；**会话末当场 design 审**（他一个字母），审过在 design.md 顶部记「design 审：✅ 已过 —— Shao Peishen <日期>」。
5. 记录 `进入判例包的开放点数量`（基线 SC2＝4、FI10＝7）；§三 待专员各点在 `#472` 行内登「判例包待办」指针（走锁 `edit-row --append`，域 业）；**台账建点交环境线**（同 FI10 做法：经 `LedgerStore.append_many` 写 `口径点台账/财务域.jsonl`，不手写 JSONL）——本会话只产 intent，不写台账。

不做什么：
- 🔴 不对专员跑 grill、不发任何对外消息、不起草信（财务部闸正被 `财务部#17` 占用）、不改 `config.py` 判据值（`None` 占位保持）。
- 🔴 不动其余 6 包（次序：FI6 → FI5 → FI9 → SC10 → SC11 → SC4，各自另起会话）。
- 🔴 design 审不代拍：他不答即停在 `status: 待确认`。

收工：产出登记 §二 待 commit 批次（走 `0-学习与工具/工具-共享文档编辑锁.py`，勿裸改、勿自行 commit；路径反引号包裹：`intent.md`、`design.md`），由落库 sweep 取活；`#436` 行追加一句「FI8 grill 已做，开放点 N，design 审结果」。收工自检逐条过转场判据五条并出声。
```
