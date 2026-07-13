# platform-data-connectors Specification

## Purpose
TBD - created by archiving change platform-harvest-connectors. Update Purpose after archive.
## Requirements
### Requirement: DataConnector 统一抽象与 CSV 回退
平台 SHALL 提供统一的 `DataConnector` 抽象基类，所有数据源连接器（SRM/ERP/U9C）MUST 实现同一读取接口（Provider 模式），使上层场景无需关心具体数据源。当主数据源不可用或处于离线/脱敏模式时，连接器 MUST 能回退到 CSV 数据提供器，返回结构一致的数据。

#### Scenario: 主数据源不可用时回退 CSV
- **WHEN** 上层场景请求数据而真实数据源（如 zp ERP）连接失败或未配置凭据
- **THEN** 连接器返回由 CSV 提供器加载的同结构数据，并在日志中标注数据来源为 CSV 回退，不抛出未处理异常

#### Scenario: 不同数据源遵循同一抽象接口
- **WHEN** 上层场景以同一组接口方法调用 SRM、zp ERP 或 U9C 任一连接器
- **THEN** 各连接器返回符合统一约定的数据结构，上层代码无需按数据源分支

### Requirement: 携客云 SRM 承诺交期只读连接器
平台 SHALL 提供携客云 SRM 只读连接器，用于读取供应商承诺交期（vExpectedDate）等履约数据。该连接器 MUST 为只读，不得对 SRM 执行任何写操作。

#### Scenario: 读取供应商承诺交期
- **WHEN** 场景请求某采购订单的供应商承诺交期
- **THEN** 连接器从 SRM（或脱敏夹具）返回该 PO 的 vExpectedDate 字段，且全程未发起任何写请求

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

### Requirement: 连接器审计采用轻量访问痕迹，合规决策审计留在场景层
连接器 MUST 复用平台既有 `zhuopin_platform.audit.AuditLogger`（不得重建），但只记录**轻量数据访问痕迹**（数据源/动作/目标标识/时间），SHALL NOT 在每次读数时写入一条合规决策记录。完整的 IATF 合规决策审计（每次 AI 决策一条）SHALL 由**场景层**负责写入，避免连接器刷屏造成审计噪声。连接器审计接入采用构造时依赖注入 `AuditLogger`。

#### Scenario: 连接器只留轻量访问痕迹
- **WHEN** 某连接器完成一次数据读取
- **THEN** 至多产生一条轻量访问痕迹（数据源/动作/目标标识/时间），不写入场景级合规决策记录

#### Scenario: 合规决策审计由场景层写入
- **WHEN** 上层场景基于连接器返回的数据做出一次 AI 决策
- **THEN** 由场景层写入一条 IATF 合规审计记录，连接器不重复写

### Requirement: 供应商敏感全文不进合规审计，调试日志默认关闭
连接器的请求/响应全文（含供应商敏感字段）SHALL NOT 进入合规 audit。如需排障，连接器 MAY 提供**可选 debug 日志**，但该日志 MUST 默认关闭、与合规 audit 物理分开、且被 `.gitignore` 排除。

#### Scenario: 默认不产生 req/resp 全文日志
- **WHEN** 连接器以默认配置运行
- **THEN** 不产生任何包含 req/resp 全文的日志文件；合规 audit 中不含供应商敏感全文

#### Scenario: 显式开启 debug 日志时物理隔离
- **WHEN** AIOps 显式开启连接器 debug 日志用于排障
- **THEN** req/resp 全文写入独立的、被 gitignore 的 debug 文件，不与合规 audit 混写

### Requirement: 采购连接器不强加 OEM 隔离路由
SRM/ERP/U9C 采购供应商数据不属于 OEM 技术数据隔离范围，因此采购连接器 SHALL NOT 强制经过 `data_isolation_layer` 的 OEM 路由。平台 MUST 保留 `data_isolation_layer` 接入点供后续研发/知识库场景使用，但本批连接器默认不调用 OEM 路由。

#### Scenario: 采购数据读取不触发 OEM 路由
- **WHEN** 场景通过采购连接器读取供应商 PO/交期数据
- **THEN** 数据正常返回，不要求提供 OEM 客户上下文，也不触发 `CrossOEMAccessError`

### Requirement: 脱敏/mock 优先验证
收割迁移 SHALL 优先以脱敏/mock 数据与 supplychain 现有测试夹具验证连接器逻辑。本次变更 MUST NOT 连接真实 SRM/ERP/U9C 生产端点。

#### Scenario: 测试全程不触真实端点
- **WHEN** 运行平台连接器测试套件
- **THEN** 所有测试使用夹具/mock 数据通过，无任何对真实生产端点的网络调用

### Requirement: ERP/U9C 唯一规范连接器
平台 SHALL 以单一规范连接器（`ZpConnector`，`erp_connector` 包）作为 U9C/ERP 的唯一数据接入实现，覆盖 U9C 标准 webapi（`/U9C/webapi/*`，含 OAuth2 鉴权与 BOM 查询）与卓品自建 REST 视图（`/zp/api/*`）。平台 MUST NOT 为同一 ERP 端点保留第二个并行连接器实现（单一可信源）。

#### Scenario: BOM 单一来源
- **WHEN** 任一场景需要 U9C BOM
- **THEN** 经 `ZpConnector.get_bom_for_products`（`/U9C/webapi/BOM/Query`）取数，不存在第二处 BOM 连接器实现

#### Scenario: 退役重复骨架连接器
- **WHEN** 存在零消费方、与规范连接器端点重复的骨架连接器（`U9CConnector`）
- **THEN** 该骨架连接器及其测试被删除，其实体名映射调研先归档保全（收敛设计文档附录），不在代码中保留重复实现

### Requirement: U9C 数据源开关与真实来源审计
平台 ERP 连接器 SHALL 支持 `U9C_DATA_SOURCE=mock|real` 开关（默认 mock）。审计 MUST 如实标注每路数据来源（按实际端点：BOM→`U9C_webapi`、zp 视图→`zp_ERP`、回退→`CSV_mock`），不得标记为已废弃的占位来源名（`U9C_CSV回退`）。

#### Scenario: 切真实源并按端点如实标审计
- **WHEN** `U9C_DATA_SOURCE=real` 且连接器从真实端点取数成功
- **THEN** 审计来源按实际端点标注（BOM→`U9C_webapi`、zp 视图→`zp_ERP`），不混一个、不标占位名

#### Scenario: mock 模式走 CSV 回退
- **WHEN** `U9C_DATA_SOURCE=mock`
- **THEN** 无真实端点的方法走 CSV 回退、审计标 `CSV_mock`，上层不被阻断

### Requirement: real 模式无真实端点 fail-loud
当 `U9C_DATA_SOURCE=real` 且某方法无真实端点（如生产计划 zp 无端点、CommonEntity 外网未开放）时，连接器 SHALL **显式报错**（`真实端点未就绪`），MUST NOT 静默回退 CSV mock —— 避免 mock 数据混入真实决策（合规+正确性风险）。仅当调用方**显式 opt-in** 回退时才允许 CSV，且该结果 MUST 标「非权威/mock」并审计 `CSV_mock`，MUST NOT 进入任何对客 / L2 决策路径。

#### Scenario: real 模式缺真实端点显式报错
- **WHEN** `U9C_DATA_SOURCE=real` 调用一个无真实端点的方法（未显式 opt-in 回退）
- **THEN** 抛出「真实端点未就绪」错误，不返回 CSV mock 数据

#### Scenario: 显式 opt-in 回退须标非权威且禁入 L2
- **WHEN** `U9C_DATA_SOURCE=real` 但调用方显式开启 mock 回退
- **THEN** 返回结果标「非权威/mock」、审计标 `CSV_mock`，且禁止进入对客/L2 决策路径

### Requirement: 鉴权采用 OAuth2 且凭据不入库
平台 ERP 连接器 SHALL 采用 OAuth2（client_id/secret 经 `/webapi/OAuth2/AuthLogin` 换 JWT，置于请求头 `token`），不依赖 admin 密码（`U9C_API_PASSWORD`）。凭据 MUST 仅从 `.env`/SecretsProvider 注入、不得硬编码进代码或提交；`U9C_API_BASE` 为 host-only（不含 `/U9C` 子路径，由连接器内部拼接）。

#### Scenario: 凭据仅来自环境且 base 为 host-only
- **WHEN** 连接器 `from_env` 构造
- **THEN** 仅从环境/SecretsProvider 读取凭据，`U9C_API_BASE` 为 host-only，连接器内部拼 `/U9C` 与 `/zp` 路径

### Requirement: 连接器边界强 Schema 校验
平台连接器 SHALL 在输入/输出边界对外部数据（U9C ERP、携客云 SRM）做强 Schema 校验（Pydantic），字段缺失/类型不符/上游改字段 MUST 被挡下并以 `ConnectorValidationError` 显式报错，不得让脏数据流入预测引擎。

#### Scenario: 上游脏数据被边界拦截
- **WHEN** U9C/SRM 返回缺字段或类型不符的记录
- **THEN** 连接器在边界校验失败、抛出 `ConnectorValidationError`，脏数据不进入下游预测

### Requirement: 携客云 SRM 限流退避
平台 SRM 连接器 SHALL 遵守携客云限流约束（30s 重复查询限制、查询跨度≤60 天、错误码 `900301`）：以令牌桶限流（进程级，1 req/30s per endpoint）+ 指数退避重试（最多 3 次），避免多实例并发超限导致拉黑。`900301` MUST 触发退避，不静默丢失。

#### Scenario: 命中限流时退避重试
- **WHEN** SRM 返回限流错误码 `900301` 或触发 30s 重复限制
- **THEN** 连接器按退避策略延迟重试，不立即重发、不静默丢失请求

### Requirement: 凭证通过 SecretsProvider 注入
平台连接器 SHALL 通过 `SecretsProvider` 协议读取凭证，不直接硬编码或直接调用 `os.environ`。`from_env()` 默认行为不变（向后兼容），同时支持注入自定义 `SecretsProvider`（如 Vault 实现）。

#### Scenario: 默认 from_env() 行为保持不变
- **WHEN** 调用 `XkySrmConnector.from_env()` 且环境变量已设置
- **THEN** 连接器正常构造，凭证从环境变量读取，与修改前行为一致

### Requirement: U9C/ERP 连接器默认开启 TLS 证书校验
平台 `ZpConnector`（U9C/ERP 唯一规范连接器）SHALL 对所有公网请求（含携带 `client_secret` 的 OAuth2 `AuthLogin`、`zp` 视图查询、`U9C/webapi/BOM/Query`）默认启用 TLS 证书与主机名校验（`ssl.create_default_context()`，`verify_mode=CERT_REQUIRED`、`check_hostname=True`）。MUST NOT 全局关闭证书校验。逃生阀 `U9C_TLS_INSECURE=true` 仅允许在 `mock` 模式下生效，`real` 模式下强制开启校验，配置显式逃生阀不影响 real 模式。

#### Scenario: 默认 TLS 校验开启
- **WHEN** `ZpConnector` 以默认配置发起 HTTPS 请求
- **THEN** TLS 证书与主机名均经校验，伪造证书请求被拒绝

#### Scenario: real 模式忽略逃生阀
- **WHEN** `U9C_TLS_INSECURE=true` 且 `mode=real`
- **THEN** 连接器仍开启 TLS 校验，记录警告日志，不使用不安全上下文

### Requirement: BOM 拉取失败显式信号，不静默吞错
`ZpConnector.get_bom_for_products` SHALL 在单品 BOM 查询失败时收集失败料号清单，不得静默丢弃返回残缺 BOM。部分失败 MUST 返回 `(rows, failed_ids)` 并写审计痕迹；全部产品查询失败 MUST 抛出带失败明细的错误，绝不返回空结果当成功。下游齐套据此不再因残缺 BOM 算出虚低毛需求。

#### Scenario: 部分 BOM 失败返回失败清单
- **WHEN** N 个产品查询中 M 个失败
- **THEN** 返回 `(成功行列表, 失败料号列表)`，失败列表非空，写审计

#### Scenario: 全部失败抛出错误
- **WHEN** 所有产品 BOM 查询均失败
- **THEN** 抛出含失败明细的错误，不返回空成功结果

### Requirement: BOM 取数按生效日期区间过滤当前版本（B3，2026-07-10 会议定稿，字段更正）
`get_bom_for_products` SHALL 对同一物料返回的多条 BOM 主记录，按 `m_effectiveDate ≤ 今天 < m_disableDate` 区间判定，只保留当前生效的那一条版本；该条内的子件行才纳入返回结果。`BomRow` 字段结构不变。

#### Scenario: 单一版本母件行为不变
- **WHEN** 某母件只有一条 BOM 主记录（无版本历史）
- **THEN** 该条记录正常参与 `get_bom_for_products` 结果，行为与本变更包实施前一致

#### Scenario: 多版本母件只取当前生效版本
- **WHEN** 某母件存在多条 BOM 主记录（版本历史），其中恰好一条满足 `m_effectiveDate ≤ 今天 < m_disableDate`
- **THEN** 只使用该条记录的子件行构造 `BomRow`，其余版本（含已失效的历史版本）不参与结果

#### Scenario: 修复现状"无条件取第一条"的活 bug
- **WHEN** 某母件的多条 BOM 主记录中，当前生效版本不是返回列表的第一条（生产环境实测确认存在此情况）
- **THEN** 系统正确选中区间判定满足的那一条，不再无条件使用列表第一条

#### Scenario: 无任何版本满足区间时 fail-safe 回退
- **WHEN** 某母件的全部 BOM 主记录都不满足 `m_effectiveDate ≤ 今天 < m_disableDate`（数据异常或版本空档期）
- **THEN** 回退选取 `m_disableDate` 最大的一条作为兜底，并写 audit 记录该异常，不静默返回空 BOM

### Requirement: 采购单到货日接真实 SRM 确认数据（A1 扩展，2026-07-10 会议定稿）
`get_purchase_orders` SHALL 对已取得的采购单，按 `(erpNo, supplyCode)` 配对查询携客云 SRM 的答交确认日期，查到则将 `PurchaseOrder.supplier_confirmed_date` 设为该真实确认日期；查不到则退回 `expected_date`。

#### Scenario: SRM 有确认日期时使用真实值
- **WHEN** 某采购单按 PO+供应商配对能在 SRM 查到确认交期
- **THEN** `supplier_confirmed_date` 设为该 SRM 确认日期，不再等于 `expected_date` 的占位值

#### Scenario: SRM 无确认记录时退回预期到货日
- **WHEN** 某采购单在 SRM 查不到对应确认记录
- **THEN** `supplier_confirmed_date` 退回 `expected_date`（与本变更包实施前行为一致）

#### Scenario: SRM 查询失败不阻断其他采购单
- **WHEN** 部分采购单的 SRM 查询发生异常（超时/接口错误）
- **THEN** 其余采购单的取数与确认日期查询不受影响，异常采购单退回 `expected_date` 并留痕，不中断整体流程

