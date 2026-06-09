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

### Requirement: U9C 骨架连接器（待真实接口）
平台 SHALL 提供 U9C 连接器骨架，当前以 CSV 回退提供数据，保留待 2026-07-01 U9C MCP 接口就绪后补真实实现的接入点。骨架 MUST 与其余连接器遵循同一抽象接口。

#### Scenario: U9C 接口未就绪时以 CSV 回退运行
- **WHEN** 场景请求 U9C 数据而真实 MCP 接口尚未接入
- **THEN** 连接器经 CSV 回退返回同结构数据，并标注为骨架/回退模式，不阻塞上层逻辑

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

