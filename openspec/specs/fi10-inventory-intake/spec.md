# fi10-inventory-intake Specification

## Purpose

采集 U9C 库存账龄、在途采购与 BOM 用量，并按 OEM 客户路由访问 OEM 项目生命周期（APQP/EOP）数据。
🔴 OEM 项目数据属专属数据，须经隔离层按客户路由、禁跨库；在途量口径与 O2 齐套引擎对齐，不另立一套。

## Requirements

### Requirement: 存货与在途数据采集

系统 SHALL 采集 U9C 库存账龄、在途采购与 BOM 用量，作为跌价测试的输入。

#### Scenario: 三类输入齐备
- **WHEN** 给定一个测算基准日
- **THEN** 输出该日的库存账龄明细、在途采购明细与相关 BOM 用量，各带来源引用

#### Scenario: 取数通道未核实
- **WHEN** 请求真实源而 U9C 库存模块通道未核实
- **THEN** fail-loud，MUST NOT 回退 mock

### Requirement: 在途量口径与 O2 齐套引擎对齐

系统 SHALL 采用与 `zhuopin_platform.agents.kit_engine` 一致的在途量口径（已订 − 已收），MUST NOT 另立一套。

> 同一个概念在两个场景里算出两个数，是最难查的一类不一致。

#### Scenario: 在途量定义
- **WHEN** 计算某采购单的在途量
- **THEN** 结果等于 `qty_ordered − qty_received`

### Requirement: 🔴 OEM 项目数据须按客户路由、禁跨库

OEM 项目计划（APQP/EOP 生命周期）属 OEM 专属数据。系统 SHALL 经 `zhuopin_platform.data_isolation_layer.OEMRouter` 按客户路由访问，跨库访问 MUST 抛 `CrossOEMAccessError`。比亚迪/上汽/理想的项目数据严格隔离、不得交叉（根 `CLAUDE.md` §7-3）。

> 不可套用"财务数据不隔离"的结论。本场景骨架期曾写"五个财务场景里**唯一**触及 OEM 隔离的一个"——该句已被 2026-09-03 裁决 `EE-3` 推翻：`FI9` 研发费用归集按项目走、OEM 项目几乎必然出现，故 `FI9` **亦会**带出 OEM 项目标识（其接法另走 design 审）。本要求本身不因此改变，改变的只是"唯一"二字。

#### Scenario: 客户归属必填
- **WHEN** 构造一条 `OemProjectPhase`
- **THEN** `oem_customer` 为必填项（无默认值）——不知属谁的 OEM 数据在隔离体系里无处安放

#### Scenario: 跨库访问被拒
- **WHEN** 以某客户身份访问另一客户的项目数据
- **THEN** 抛出 `CrossOEMAccessError`

#### Scenario: 夹具不得含真实客户名
- **WHEN** 提供 mock 夹具
- **THEN** OEM 客户名为占位值，MUST NOT 使用真实 OEM 名称
