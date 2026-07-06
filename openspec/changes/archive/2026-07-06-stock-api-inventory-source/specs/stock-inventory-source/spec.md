## ADDED Requirements

### Requirement: 库存实时取数走卓品 Stock API
平台 SHALL 经卓品自建 REST `GET /zp/api/Stock/Query`（apiKey 走 URL query）取真实现货，用于 `get_inventory`。base 与 apiKey MUST 从环境变量注入（`STOCK_API_BASE` / `STOCK_API_KEY`），不得硬编码或入库。取数 SHALL 只读，不得调用任何写端点。

#### Scenario: 取真实现货
- **WHEN** 场景请求某料号集合的库存
- **THEN** 连接器经 `/zp/api/Stock/Query` 返回真实 `StoreQty`(现存)/`AvailQty`(可用)，凭据来自环境注入

#### Scenario: 替换恒零桩
- **WHEN** `get_inventory` 在 real 模式运行
- **THEN** 返回真实 `current_stock`，不得再恒返回 0（旧桩行为废止）

### Requirement: 齐套可用仓白名单口径
`get_inventory` 用于齐套/缺料判定时，SHALL 只计入白名单仓 `whCode ∈ {WW01, ZP01, ZP21, ZP22, ZP02, ZP23}`（委外仓/物料仓/半成品库/委外半成品库/成品库/委外成品库），其余仓（不良品仓、委外线边仓等）MUST 排除。过滤 SHALL 在请求侧用 `whCode` 逗号多值下发。

#### Scenario: 只计白名单仓
- **WHEN** 某料号在不良品仓有库存、在物料仓也有库存
- **THEN** 聚合结果只含白名单仓部分，不良品仓库存被排除

#### Scenario: 白名单可配置
- **WHEN** 白名单仓集合需调整
- **THEN** 该集合为显式配置常量（非散落魔法值），修改集中一处

### Requirement: 逐料号查询与精确匹配聚合
因 `itemCode` 为模糊匹配、不支持逗号多值，且 `limit≤1000` 无分页，平台 SHALL 按料号逐个查询（`itemCode`+`whCode` 白名单），并 MUST 按 `ItemCode` **精确匹配**过滤响应（剔除模糊命中的他料），再跨白名单仓聚合 `StoreQty`/`AvailQty` 得每料现货/可用量。多料号查询 MAY 并发。

#### Scenario: 剔除模糊命中
- **WHEN** 查询 `itemCode=R01A.0012` 且 API 模糊返回 `R01A.0012` 与 `R01A.00120`
- **THEN** 只保留精确等于 `R01A.0012` 的行参与聚合

#### Scenario: 跨白名单仓聚合
- **WHEN** 某料在物料仓与委外仓各有现货
- **THEN** 返回其在白名单仓的 `StoreQty`/`AvailQty` 合计为单条 `InventoryRow`

### Requirement: apiKey 脱敏且 real 缺端点 fail-loud
apiKey MUST NOT 出现在异常信息、日志或审计中（报错用不含 apiKey 的 URL）。real 模式下 Stock API 不可用（网络/鉴权/接口错误）时 SHALL fail-loud（抛错），MUST NOT 静默回退 mock 或返回 0 冒充真实现货。每次取数 SHALL 写平台 `audit` 轻量访问痕迹（数据源=Stock）。

#### Scenario: apiKey 不外泄
- **WHEN** Stock API 调用抛出异常
- **THEN** 异常信息与审计记录均不含 apiKey 明文

#### Scenario: real 不可用即报错
- **WHEN** real 模式下 Stock API 返回鉴权失败或网络不可达
- **THEN** `get_inventory` 抛错（fail-loud），不返回 0、不回退 mock

### Requirement: 保供现货净额逻辑加开关默认关
SC8 保供看板消费真实现货做净额判定（现货净额≥毛需求的子件退出待催/催货）SHALL 挂开关 `SC8_NET_INVENTORY`，默认 **OFF = 现行为、零保供四色漂移**。翻 ON（改变保供四色）MUST 先由采购专员重核保供黄金基准并登记原因，未签字不得默认开启。

#### Scenario: 默认关不漂移
- **WHEN** `SC8_NET_INVENTORY` 未设置或为 OFF
- **THEN** 保供看板输出与接入前完全一致，黄金基准不漂移

#### Scenario: 开启后净出现货
- **WHEN** `SC8_NET_INVENTORY=ON` 且某子件白名单仓现货≥其毛需求
- **THEN** 该子件退出待催/催货集合，不再被误判为追料对象
