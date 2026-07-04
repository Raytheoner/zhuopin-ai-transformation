# platform-kit-engine Specification

## Purpose
平台齐套计算引擎：给定 BOM 展开需求与库存/在途快照，计算各物料缺口，输出齐套能否满足的判定与缺料清单。是 SC5 / O2 等多场景的共享底座（rule-of-three 触发后提升至平台）。

## Requirements

### Requirement: 齐套计算在途量不因缺库存快照被忽略
`kit_engine.calc_shortage` SHALL 在物料不在库存快照（`inventory` 无对应行）时**仍计入其在途量**（`available = 在途`），不得把 available 当 0 而高估缺口。缺库存快照的物料 MUST 输出到告警清单（`missing_snapshot`），供下游提示数据缺口。真实库存端点未就绪（`get_inventory` 恒返回 0 库存项）时该路径不再误报虚高缺口。

#### Scenario: 缺库存快照仍计在途量
- **WHEN** 某物料在 BOM 需求中存在，但不在库存快照
- **THEN** available = 在途量（而非 0），缺口正确计算；该物料出现在 `missing_snapshot` 告警清单

#### Scenario: 库存快照有该物料时正常计算
- **WHEN** 物料既有库存快照也有在途量
- **THEN** `available = 库存 + 在途`，缺口 = max(0, need - available)

#### Scenario: 全量零库存快照时不虚报缺口
- **WHEN** `get_inventory` 返回空（真实库存端点未就绪）
- **THEN** 缺口以在途量抵扣，不因库存快照缺失而把全部需求报为缺料

### Requirement: 黄金值精确相等，不浮点近似
`kit_engine.calc_shortage` 的黄金基准断言 MUST 使用精确相等（`==`）而非近似比较（`pytest.approx` / 允差）。auto_total=35850 / review_total=640000 / grand_total=675850 为当前黄金值快照，任何逻辑变更导致偏差 MUST 回归失败，不得静默通过。

#### Scenario: 黄金值不漂移
- **WHEN** 对标准黄金基准样本运行 `calc_shortage`
- **THEN** 结果与黄金值精确相等（auto_total=35850, review_total=640000）
