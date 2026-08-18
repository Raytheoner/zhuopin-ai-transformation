# pmc-priority-allocation Specification

## Purpose
TBD - created by archiving change shortage-baoguan-criteria-v3. Update Purpose after archive.
## Requirements
### Requirement: PMC 优先级占用框架（桩实现）
系统 SHALL 定义"PMC 月度优先级占用"这一能力的接口形状（输入：物料号 + 竞争该物料的成品行列表；输出：按优先级排序的成品行列表），但**不实现**真实的 PMC 数据解析与占用逻辑——真实数据源到位后作为独立后续任务实现。

#### Scenario: 无 PMC 数据表时兜底为"各算各的"
- **WHEN** 没有可用的 PMC 月度优先级表（当前恒成立，本次未接入真实数据源）
- **THEN** 系统按现状行为运行——每个成品行独立判断共用子件现货是否满足自身毛需求，不发生跨行占用/抢占

#### Scenario: 接口预留、不影响现有判定
- **WHEN** 系统未来接入真实 PMC 优先级数据源
- **THEN** 可通过实现 `priority_resolver`（见 `stock-inventory-source` 能力）接入，无需改动本次已实现的其他口径（A1/A2/B2/B3）

#### Scenario: 同时服务 B2 的多需求排序（2026-07-10 会议定稿）
- **WHEN** 同一物料被多个不同需求（不同 FO/SO）在同一时间窗口竞争，且 `delivery-date-forecast` 能力的周期累计供需匹配（B2）需要决定谁先占用供应量
- **THEN** 使用同一个 `priority_resolver` 挂钩点（不为 B2 另建一套框架）；本次仍只提供接口形状，真实排序逻辑待 PMC 数据源到位后实现

### Requirement: 预测订单优先级三级判据
在没有真实 PMC 月度优先级表（`priority_resolver`）时，系统 SHALL 按以下三级判据决定多张
预测订单行竞争同一叶子件现货时的占用次序：

1. **计划出货日期在前的优先**（如 2026-08-10 优先于 2026-08-20）；
2. **出货日期相同时，ERP 预测订单数量大的优先**（如同为 2026-08-10 的 `F02N.0224` 数量 1100
   优先于 `F02N.0226` 数量 600）；
3. **数量与出货日期都相同时，按取值的自然顺序**，先取值的先占用。

该三级判据来源＝姚祖怡（采购部 AI 专员）2026-08-12 采购部#13 回件书面给出。

#### Scenario: 出货日期不同时按日期排序
- **WHEN** 两张预测订单行竞争同一叶子件、计划出货日期不同
- **THEN** 出货日期在前的先占用现货

#### Scenario: 出货日期相同时按数量降序
- **WHEN** 两张预测订单行竞争同一叶子件、计划出货日期相同、数量不同
- **THEN** 数量大的先占用现货

#### Scenario: 日期与数量都相同时按取值顺序
- **WHEN** 多张预测订单行竞争同一叶子件、出货日期与数量均相同
- **THEN** 按其在取数结果中的原始先后顺序占用，先取值的先占用

### Requirement: 真实 PMC 优先级表优先于三级判据
当传入真实 `priority_resolver`（#15 PMC 月度优先级表）时，系统 SHALL 以其给出的 so_id 次序
为准；三级判据仅作为**同一 so_id 下多个行项**（resolver 接口粒度到 so_id，对行项无从区分）
的二级判据。

#### Scenario: resolver 给出次序时不被数量判据反超
- **WHEN** `priority_resolver` 明确给出两个不同 so_id 的先后次序
- **THEN** 系统按其次序占用，MUST NOT 因数量更大而反超

#### Scenario: 同一 so_id 多行项用三级判据作二级排序
- **WHEN** 同一 FO 文档下多个行项共享同一 so_id，resolver 对其无从区分
- **THEN** 这些行项之间按三级判据排序（与无 resolver 时同一口径）

