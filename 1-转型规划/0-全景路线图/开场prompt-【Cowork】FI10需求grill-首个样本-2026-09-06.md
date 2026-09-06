---
title: "开场 prompt ·【Cowork】FI10 需求 grill · 存量补 grill 首个样本（会话末即 design 审）"
created: 2026-09-06
派出线: Cowork 环境总线 OP-0906-W
队列行: §一 #436 ⑶①（人的那半）；场景承接行 §一 #474（业务场景队列）
依据: 端到端构建workflow优化-方案-2026-09-06.md §六 决议 ③⑤；rules/场景建造与合规 §二「新场景 propose 前置＝intent.md」
status: 待你在 Cowork 里起
---

# 开场 prompt ·【Cowork】FI10 需求 grill（存量 8 包补 grill 之一，首个）

> 为什么先 FI10：8 个 09-03 无头泳道落包的新场景里，FI10 已勾 24 条任务、未勾 26 条里 2.1–2.6 全是「口径归属／判据签认／持有人实名」——需求点最集中、收口最近。grill 产出即 design 审材料：会话末当场审 `fi10-inventory-writedown-mvp/design.md`（现无此文件）。
> ✅ 前置已清：skill `zhuopin-requirement-grill` 已安装版是**引用式指针**（只指向源码 `0-学习与工具/skills源码/zhuopin-需求grill/SKILL.md`），源码 2026-09-06 已改（产出定名 `intent.md`）即刻生效，**不需要重装**（21:5x 核过安装版正文＝指针，`/sessions…/.claude/skills/zhuopin-requirement-grill/SKILL.md` 3,167 B）。

▶ 首次派出：[OP-0906-V]

**开场词（复制即用，▶ 粘贴端：Cowork 新会话）**：

```
[OP-0906-V]【Cowork】FI10需求grill
【设置】执行环境：Cowork ｜ 分支：master ｜ worktree：☐（不建，只产 `intent.md` 与 `design.md`）｜ 工作区：无 ｜ session：新开 ｜ 派出线：Cowork 环境总线 OP-0906-W
读 ① `1-转型规划/0-全景路线图/开场prompt-【Cowork】FI10需求grill-首个样本-2026-09-06.md` → ② `CLAUDE.md` §4 路由表 → `.claude/rules/场景建造与合规.md` §二（intent.md 前置一句）恢复上下文，按该件执行。本件为 A 类（口径已定：产出定名 `intent.md`、三节固定、会话末 design 审），直接开工。

做什么：
1. 调 skill `zhuopin-requirement-grill`，受访者＝Shao Peishen 本人（不问任何专员）。M2 先扫：全景规划 FI10 场景块、`4-数字员工/财务部/FI10-存货跌价智能分析/`（`config.py` 四条 `Criterion`、`data/mock/`、tasks 2.1–2.6）、`openspec/changes/fi10-inventory-writedown-mvp/`（proposal＋tasks，无 design）、`5-平台底座/zhuopin_platform/zhuopin_platform/criteria_signoff/`（注册表：`unsigned_keys()` 即待问点）、`#474`／`#475`（芯片价格 API 独立行）／`#477`（FI9 工时系统前置，同族「无主的事」）。凡能查到的一律不问。
2. 按前沿分轮问他（每轮 §二 格式：编号＋(a)/(b)＋推荐＋默认项），直到前沿为空。三选一分流每一问：能查的自查／只有他能定的本轮问／只有专员知道的落 §三 待专员（带口径点 ID 占位，形如 `FI10-G-01`，与 `Criterion.key` 同名）。
3. 产出 `4-数字员工/财务部/FI10-存货跌价智能分析/intent.md`（frontmatter `status: 待确认`／`场景: FI10`／`grill会话: OP-0906-V`／`进入判例包的开放点数量: N`；三节：§一 M2 已自查事实／§二 已定／§三 待专员）。他确认后改 `status: 已确认`。
4. 同一会话把 §二 写进 `openspec/changes/fi10-inventory-writedown-mvp/design.md` Decisions、§三 写进 Open Questions「待专员」；**会话末当场 design 审**（他一个字母），审过在 design.md 顶部记「design 审：✅ 已过 —— Shao Peishen 2026-09-06」。
5. 记录 `进入判例包的开放点数量`（SC2 基线＝4）；§三 待专员各点在 `#474` 行内登「判例包待办」指针（走锁 `edit-row --append`），不发信、不起草判例包（判例包另起会话；判闸只用 `python 0-学习与工具/工具-跟进闸查询.py --to 唐燕萍`，不凭记忆判在途）。

不做什么：
- 🔴 不对专员跑 grill、不发任何对外消息、不改 `config.py` 判据值（`None` 占位保持）。
- 🔴 不动其余 7 包（各自另起会话，次序：FI8 → FI6 → FI5 → FI9 → SC10 → SC11 → SC4）。
- 🔴 design 审不代拍：他不答即停在 `status: 待确认`。

收工：产出登记 §二 待 commit 批次（走 `0-学习与工具/工具-共享文档编辑锁.py`，勿裸改、勿自行 commit；路径反引号包裹：`intent.md`、`design.md`），由落库 sweep 取活；`#436` 行追加一句「FI10 grill 已做，开放点 N，design 审结果」。收工自检逐条过转场判据五条并出声。
```

## 次序与并行矩阵（存量 8 包）

| 序 | 场景包 | 能否立即 | 并行 | 备注 |
|---|---|---|---|---|
| 1 | FI10 `fi10-inventory-writedown-mvp` | 本件 | 与 CC 看护批 `B-0906_P` 并行（不同触碰区） | 首个样本 |
| 2–5 | FI8 → FI6 → FI5 → FI9 | FI10 会话末即可复制本件改场景名 | 同上 | FI9 已有 design.md，grill 后只补 Decisions |
| 6–7 | SC10 → SC11 | 同上 | 同上 | 采购域 `#468`／`#469` |
| 8 | SC4 `sc4-contract-clause-extraction` | 已正式顺延（09-03），最后 | — | 法务侧两前置已滑 |
