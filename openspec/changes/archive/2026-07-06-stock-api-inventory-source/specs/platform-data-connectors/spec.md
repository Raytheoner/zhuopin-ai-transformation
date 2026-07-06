## MODIFIED Requirements

### Requirement: 卓品 zp ERP 真实数据连接器
平台 SHALL 提供卓品 zp REST API 连接器，读取真实 ERP 的采购订单（PO）、物料数据与**库存现货**。连接器凭据 MUST 从环境变量/`.env` 注入，不得硬编码或写入仓库。库存现货 SHALL 经卓品自建 `GET /zp/api/Stock/Query`（apiKey 走 URL query，`STOCK_API_BASE`/`STOCK_API_KEY` 环境注入）取真实 `StoreQty`/`AvailQty`；`get_inventory` 在 real 模式 MUST 返回真实现货，不得再恒返回 `current_stock=0`（旧桩废止），real 缺端点/不可用时 fail-loud。

#### Scenario: 读取 PO 与物料数据
- **WHEN** 场景请求采购订单或物料主数据
- **THEN** 连接器经 zp REST API（或测试夹具）返回 PO/物料记录，凭据来自环境注入而非源码

#### Scenario: 读取真实库存现货
- **WHEN** 场景请求某料号集合的库存
- **THEN** `get_inventory` 经 `/zp/api/Stock/Query` 返回真实现货（`current_stock` 非恒 0），apiKey 脱敏不入日志/审计

#### Scenario: real 模式库存端点不可用即 fail-loud
- **WHEN** real 模式下 Stock API 鉴权失败或不可达
- **THEN** `get_inventory` 抛错，不静默回退 mock、不以 0 冒充真实现货
