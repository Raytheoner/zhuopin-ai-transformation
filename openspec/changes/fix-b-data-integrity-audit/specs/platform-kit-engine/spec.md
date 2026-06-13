## ADDED Requirements

### Requirement: 齐套计算在途量不因缺库存快照被忽略
`kit_engine.calc_shortage` SHALL 在物料不在库存快照（`inventory` 无对应行）时**仍计入其在途量**（`available = 在途`），不得把 available 当 0 而高估缺口。缺库存快照的物料 MUST 输出到告警清单（`missing_snapshot`），供下游提示数据缺口。真实库存端点未就绪（`get_inventory` 恒返回 0 库存项）时该路径不再误报虚高缺口。

#### Scenario: 缺快照但有在途的物料缺口正确
- **WHEN** 某物料毛需求 100、不在库存快照、在途 80
- **THEN** 缺口为 20（= 100 − 80），而非 100；该物料进入 `missing_snapshot` 告警清单

#### Scenario: 有快照物料行为不变
- **WHEN** 某物料在库存快照中（current/safety/在途齐全）
- **THEN** `available = current - safety + 在途`，缺口计算不变
