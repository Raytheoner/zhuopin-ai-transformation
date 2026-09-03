## Purpose

从 U9C 项目成本模块按（项目 × 期间 × 成本类型）采集材料、人工、制造费用，保留来源单据引用以支撑审计追溯。
🔴 工时系统的存在性、维护方与取数能力三问皆未核实，在此之前人工费用归集须 fail-loud，不得以任何分摊估算代替。

## ADDED Requirements

### Requirement: 项目成本采集

系统 SHALL 从 U9C 项目成本模块按（项目 × 期间 × 成本类型）采集材料、人工、制造费用，MUST 保留来源单据引用以支撑审计追溯。

#### Scenario: 三类成本归集
- **WHEN** 给定一个项目与期间
- **THEN** 输出该项目该期间按材料/人工/制造费用分类的成本明细与合计，每条带来源单据号

#### Scenario: 取数通道未核实
- **WHEN** `DATA_SOURCE_DEFAULT` 为真实源而通道未核实
- **THEN** fail-loud，MUST NOT 回退 mock

### Requirement: 工时系统存在性未核实前，人工费用归集须 fail-loud

在工时系统的存在性、维护方与取数能力三问未核实前，系统 MUST NOT 归集人工费用，且 MUST NOT 以任何分摊估算代替。

> 分摊出来的人工费会原样写进加计扣除备查资料，而它看起来和真的一模一样。

#### Scenario: 存在性未核实
- **WHEN** `TIMESHEET_SYSTEM_EXISTS` 为空且请求归集人工费用
- **THEN** 抛出显式异常说明三问未核实与应先做的核实动作，**不返回任何人工费用金额**

#### Scenario: 替代方式也须签认
- **WHEN** 工时系统确认不存在，改用替代归集方式
- **THEN** 该替代方式须经财务/研发侧签认落档，MUST NOT 由实现方自选分摊法

#### Scenario: 骨架期只允许合成工时
- **WHEN** 在 mock 模式下构造工时记录
- **THEN** 其 `source` 为 `"synthetic"`，`rate` 为空（单价口径属判据，未签认）

#### Scenario: 存在性缺口不得并入判据注册表
- **WHEN** 有人把 `TIMESHEET_SYSTEM_EXISTS` 登记进 `CriteriaRegistry`
- **THEN** 该做法被拒绝——它靠**去核实一次**（已独立立行队列 `#477`）解除，不靠财务侧签认解除；并成一条会把"该找谁去解它"一起糊掉

### Requirement: 发票号 join 须先实测字面一致性

若材料费用需与发票对碰，系统 SHALL 先实测税务/发票来源与 U9C 侧发票号的字面一致性（位数、前导零、空格、全半角、代码前缀）再确定 join 键。

> 本项目已实测证伪过「发票号字面 join」一次（FI2 `fi2-tax-export-ingest`，2026-08-07 归档）。该次结论**只证明"不能想当然"，未证明其后 8 位方案对本场景也成立**——两侧来源不同。

#### Scenario: 不得沿用他场景的 join 方案
- **WHEN** 设计本场景的发票对碰
- **THEN** 须基于本场景自身的实测结论定 join 键，MUST NOT 直接沿用 FI2 的后 8 位 ＋ suffix 方案
