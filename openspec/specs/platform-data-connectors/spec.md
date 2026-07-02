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
平台 SHALL 提供卓品 zp REST API 连接器，读取真实 ERP 的采购订单（PO）与物料数据。连接器凭据 MUST 从环境变量/`.env` 注入，不得硬编码或写入仓库。

#### Scenario: 读取 PO 与物料数据
- **WHEN** 场景请求采购订单或物料主数据
- **THEN** 连接器经 zp REST API（或测试夹具）返回 PO/物料记录，凭据来自环境注入而非源码

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

