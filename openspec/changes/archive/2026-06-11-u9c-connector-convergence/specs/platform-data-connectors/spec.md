## REMOVED Requirements

### Requirement: U9C 骨架连接器（待真实接口）
**Reason**：U9CConnector 骨架已删除（零消费方、鉴权口径过时）。U9C/ERP 接入由唯一规范连接器 `ZpConnector` 承担（见下新增要求）；实体名映射调研已归档保全于连接器收敛设计文档附录 A。

## ADDED Requirements

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
