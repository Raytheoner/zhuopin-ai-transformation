## ADDED Requirements

### Requirement: 跨 OEM 访问拒绝前写审计
`OEMRouter` SHALL 支持注入 `audit`，并在抛出 `CrossOEMAccessError`（未注册 OEM 上下文 / 跨客户专属库访问）**之前**写一条 `AuditEvent`（`action="cross_oem_access_denied"`，含 oem/collection/reason），使违规企图留痕，与"必须审计"的红线一致。无 audit 注入时仅抛错（向后兼容）。

#### Scenario: 跨客户访问被拒前留痕
- **WHEN** 注入 audit 的 `OEMRouter.guard(oem="比亚迪", collection="oem_saic")`
- **THEN** 先写 `cross_oem_access_denied` 审计，再抛 `CrossOEMAccessError`

#### Scenario: 未注册 OEM 被拒前留痕
- **WHEN** 注入 audit 的 `OEMRouter.resolve(oem="未知客户")`
- **THEN** 先写 `cross_oem_access_denied` 审计，再抛 `CrossOEMAccessError`
