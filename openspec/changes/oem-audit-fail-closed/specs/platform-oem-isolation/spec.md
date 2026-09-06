## MODIFIED Requirements

### Requirement: 跨 OEM 访问拒绝前写审计
`OEMRouter` SHALL 在抛出 `CrossOEMAccessError`（未注册 OEM 上下文 / 跨客户专属库访问）**之前**写一条 `AuditEvent`（`action="cross_oem_access_denied"`，含 oem/collection/reason），使违规企图留痕。

审计 MUST NOT 是可选的。未显式注入 `audit` 时，`OEMRouter` MUST 使用平台默认 `AuditLogger`；默认 logger 亦不可用时（构造失败或写入失败），`resolve()`/`guard()` MUST 直接拒绝访问（fail-closed），MUST NOT 在无留痕的情况下放行或静默抛错。

本条的 fail-closed 义务范围仅限**拒绝路径**：审计通道故障不改变原本应被允许的访问（本客户专属库 / 通用知识库）的结果——该边界属另一条 Requirement（读取侧无条件放行）的既有语义，本条不扩大。

#### Scenario: 跨 OEM 拒绝前写审计
- **WHEN** 在 OEM-A 上下文中访问属于 OEM-B 的专属集合
- **THEN** 写 `cross_oem_access_denied` 审计事件（含 oem/collection/reason）后抛 `CrossOEMAccessError`

#### Scenario: 未注入 audit 时使用默认 logger
- **WHEN** `OEMRouter` 以默认构造创建，发生跨 OEM 访问
- **THEN** 经平台默认 `AuditLogger` 写留痕后抛 `CrossOEMAccessError`

#### Scenario: 审计通道完全不可用
- **WHEN** 默认 `AuditLogger` 亦不可用（如落盘失败）
- **THEN** `resolve()`/`guard()` 直接拒绝访问，MUST NOT 无留痕放行
