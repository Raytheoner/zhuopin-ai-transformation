# platform-oem-isolation Specification

## Purpose
OEM 数据隔离层：按客户路由数据访问，拒绝跨 OEM 越权访问，质量域含 OEM 信息的数据（8D/客诉/PPAP/FMEA）强隔离，供应商/制造自有数据不隔离。所有拒绝操作前留痕审计。

## Requirements

### Requirement: 跨 OEM 访问拒绝前写审计
`OEMRouter` SHALL 支持注入 `audit`，并在抛出 `CrossOEMAccessError`（未注册 OEM 上下文 / 跨客户专属库访问）**之前**写一条 `AuditEvent`（`action="cross_oem_access_denied"`，含 oem/collection/reason），使违规企图留痕，与"必须审计"的红线一致。无 audit 注入时仅抛错（向后兼容）。

#### Scenario: 跨 OEM 拒绝前写审计
- **WHEN** 在 OEM-A 上下文中访问属于 OEM-B 的专属集合
- **THEN** 写 `cross_oem_access_denied` 审计事件（含 oem/collection/reason）后抛 `CrossOEMAccessError`

#### Scenario: 无 audit 注入时仅抛错
- **WHEN** `OEMRouter` 无 audit 注入，发生跨 OEM 访问
- **THEN** 直接抛 `CrossOEMAccessError`，不崩溃

### Requirement: OEM 隔离边界（质量域扩展）
隔离边界 SHALL 覆盖研发/OEM 技术数据（R 系列）与质量域中含 OEM 信息的数据（PPAP/FMEA、8D/客诉中含特定 OEM 信息的部分），MUST 按客户分库/分检索域路由。隔离边界 MUST NOT 覆盖采购连接器的 SRM/ERP 供应商数据与公司自有制造数据（IQC/SPC）——这两类数据不强加 OEM 隔离路由。

#### Scenario: 研发技术数据路由
- **WHEN** 访问包含 OEM 技术参数的知识库（R 系列）
- **THEN** 按 OEM 上下文路由，拒绝跨客户访问

#### Scenario: 采购 SRM 连接器不走隔离路由
- **WHEN** `ZpConnector`/`XkySrmConnector` 访问供应商/库存数据
- **THEN** 不经 OEMRouter，直接访问，不要求 OEM 上下文注入
