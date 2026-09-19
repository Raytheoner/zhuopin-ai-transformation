---
title: "design 审读件 · 口径点台账与 criteria_signoff 打通"
created: 2026-09-19
status: 待你审（Shao Peishen）
来源:
  - `openspec/changes/coverage-point-ledger/{proposal,design,tasks}.md`（D1–D9 已审，本件不重开）
  - `openspec/changes/criteria-signoff-platform/{proposal,design}.md`（G-1…G-7 已于 2026-09-03 审过，本件不重开）
  - `6-人才与组织/部门AI专员跟进/口径点台账/SCHEMA.md` §四（本件要收口的那条待办）
  - `1-转型规划/0-全景路线图/端到端构建workflow优化-方案-2026-09-06.md` §四 W2
承接载体: 队列 §一 `#439`；派出线 `OP-0919-M`
---

# design 审读件 · 口径点台账与 `criteria_signoff` 打通

> **一句话背景**：口径点台账（`coverage-point-ledger`）D1–D9 已于 2026-09-01 审过；代码侧 `criteria_signoff` 底座（`criteria-signoff-platform`）G-1…G-7 已于 2026-09-03 审过——**两者各自审过，但从未合审过**。09-06 的方案件曾计划「合并一次审」，但那时 `criteria-signoff-platform` 已经过审三天了，「合并」这条路径本身已经不成立。本件补的就是这个缺口：**一条从未被正式定过的 Decision，现在单独拿出来定**，不触碰、不重开已裁决的十六条（D1–D9 ＋ G-1…G-7）。
>
> 🔴 **本件止步于「决策点已列清、等你答」，不代拍、不 apply、不改任何既有代码或台账数据。**

---

## 一、现状实证（如实登记，非推断）

**两本账目前"ID 长得一样，但状态互不知道对方"——这不是假设风险，是已经发生的真实漂移。**

实证对象：`FI10-NRV_ESTIMATION_BASIS`（NRV 估算口径）

| 载体 | 当前状态 | 取证方式 |
|---|---|---|
| 口径点台账（`财务域.jsonl`） | **`已签认`**（2026-09-16，`evidence` 指向唐燕萍 09-16 回件落档件，J4/J5/J6 三问已答） | `grep '"id":"FI10-NRV_ESTIMATION_BASIS"' 财务域.jsonl` |
| 代码侧 `criteria_signoff`（`fi10_inventory_writedown/config.py`） | **仍未签认**——`Criterion(key="NRV_ESTIMATION_BASIS", ...)` 声明里没有任何 `Signoff`，`CRITERIA.value_of("NRV_ESTIMATION_BASIS")` 此刻仍会抛 `CriterionNotSignedOffError` | `grep -n "NRV_ESTIMATION_BASIS\|Signoff(" config.py` |

**漂移已持续 3 天（09-16 → 09-19）且无任何告警**——两边都"正确地"各自运行，谁都没做错，只是没人把签认结果从台账搬进代码。这正是 proposal 里"跨引用靠人写的文字维系"那条病灶的最新一例，只是这次的两处不是 README 与队列，是台账与代码。

⚠️ **本件不代为修复这处漂移**（写 `Signoff` 进 `config.py` 是改既有代码，超出本轮"止步 design 可审态"边界）；修复方式取决于下面决策点①怎么答——若选 (a)/(b)，桥接机制建成后这类漂移会被自动消灭；若选 (c)，则仍需一条独立的手工/巡检任务去发现并补，**该任务本身也不在本轮范围内，答复后另行登记**。

---

## 二、决策点（编号问题，按字母项作答，答复格式如 `1a 2a 3a`）

### 决策点① · 两本账打通到什么深度

台账 `id` 形态⑴（`<场景码>-<Criterion.key>`）已在实践中与代码侧 `Criterion.key` 保持一致（本件抽查 FI10 三条、FI2/FI9 等域内 id 命名同形），**命名层面其实已经打通**。真正悬而未决的是**状态是否联动**：

- **(a) 全打通（运行时联动）**：新增一个轻量桥接（如 `criteria_signoff.load_signoffs_from_ledger(scene)`），场景启动或 `CriteriaRegistry` 构造时读取该场景在台账里 `已签认`／`已回灌` 的最新事件行，自动构造 `Signoff(signed_by, signed_on, evidence, rule_version)` 并注入对应 `Criterion`。**台账是唯一真身，注册表是它的运行时投影**（与 D6「信是视图、点是真身」同一形状，只是这次台账本身升格为"点的真身"，注册表变成第二层投影）。往后场景侧 `config.py` 不再需要手工回填任何签认结果。
- **(b) 弱打通（只共享命名，不共享状态）**：维持现状——`id` 命名一致只是约定，两边状态各自独立演进，**定期人工核对有无漂移**（需要一条新的巡检任务，检测"台账已签认但代码未见 Signoff"的行，如 FI10 这一例）。代价是巡检本身也会滞后（这次滞后 3 天才被本件顺带发现，不是巡检发现的）。
- **(c) 否决打通，各走各的**：两本账继续各自独立，`id` 命名一致视为巧合、不作为约定维护。**明确列出但不推荐**——与 D6"信是视图、点是真身"的既定方向相悖，选它需要你显式否决 D6 在这个场景下的延伸适用。

### 决策点② · 若①选 (a) 或 (b)，桥接层／巡检任务何时建、谁建

- **(a) 本轮（`op0919m` 系列）之后紧接着排一棒去建**，不与组 4/5 混排（组 4/5 是"闸取数源切换"与"README 降视图"，与桥接层是不同的触碰区）。
- **(b) 并入本包 tasks 组 4（晋档 3、28 天并跑）同一批次做**——理由：两者都涉及"旧路/手工核对 → 新路/自动联动"的切换验证节奏相近。
- **(c) 单独立一个新变更包**，不占用 `coverage-point-ledger` 本包的组织结构（本包已经很大，九条 Decision＋2bis 缺口补登已经历经四轮 CC 泳道）。

### 决策点③ · 两包 design.md 怎么记这条新 Decision

`criteria-signoff-platform` design 09-03 已审过、`coverage-point-ledger` design 09-01 已审过，都不含这条。补记方式：

- **(a) 两包 design.md 各自追加一条新 Decision**（`coverage-point-ledger` 记为 D10、`criteria-signoff-platform` 在已裁决节后追加一条关联指针），**不重开、不改动已裁决的 D1–D9／G-1…G-7 任何一条**，本件即两包合审的替代形式。
- **(b) 走一次正式的完整重新 design 审**（两包全量重审）——成本高，且已裁决的十六条并无内容变化，纯属走流程。

---

## 三、答复模板（一键复制）

```
1a 2a 3a
```
（示例答案，仅供参考格式；请按你的实际判断替换字母）

---

## 四、答复后本方的动作（预告，不要求你现在确认）

- 决策点①②③ 有了答案后，本方把裁决写回 `coverage-point-ledger/design.md`（新增 D10）与 `criteria-signoff-platform/design.md`（追加关联指针），`SCHEMA.md` §四 由"待两包合审"改判"已裁决，见 D10"，并按②的答案登记新任务的承接载体（队列 §一 新行或 tasks 组内新增项，视答案而定）。
- FI10-NRV_ESTIMATION_BASIS 这处已发生的漂移，视①的答案决定修复路径，另行登记，不在本次追问范围内代拍。
