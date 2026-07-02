# connector-schema-validation Specification

## Purpose
TBD - created by archiving change platform-hardening-p2. Update Purpose after archive.
## Requirements
### Requirement: SRM 响应行 Pydantic 边界校验
`XkySrmConnector` SHALL 在将 API 响应解析为内部 dataclass 前，对每个响应"行"对象（`lineList` 条目、`itemList` 条目）进行 Pydantic 模型校验。`ValidationError` MUST 被捕获并转换为 `ConnectorValidationError(source="SRM", field=<字段>, raw=<原始行>)`，不得静默忽略或让脏数据流入下游预测引擎。

#### Scenario: SRM 响应缺少必填字段时被拦截
- **WHEN** SRM 返回的 `itemList` 行缺少 `answerQty` 或 `boardDate` 字段
- **THEN** `ConnectorValidationError` 被抛出，不产生 `SrmDeliveryOrder`

#### Scenario: SRM 响应类型不符时被拦截
- **WHEN** SRM 返回的 `vExpectedDate` 字段为非数字字符串
- **THEN** `ConnectorValidationError` 被抛出，含 field 和 raw 上下文

#### Scenario: 有效响应正常通过
- **WHEN** SRM 返回格式正确的响应行
- **THEN** 正常构造 `SrmDeliveryOrder`，无异常

### Requirement: zp ERP 响应行 Pydantic 边界校验
`ZpConnector` SHALL 对 zp API 的 PO 行（`ZpViewPurOrder` 响应条目）和 U9C BOM component 行进行 Pydantic 模型校验，`ValidationError` 转换为 `ConnectorValidationError(source="zp_ERP", field=<字段>, raw=<原始行>)`。

#### Scenario: ERP PO 行缺少料号字段时被拦截
- **WHEN** `ZpViewPurOrder` 响应行 `itemCode` 为 null 且不可降级
- **THEN** `ConnectorValidationError` 被抛出，不产生 `PurchaseOrder`

#### Scenario: BOM component 行校验通过
- **WHEN** `_u9c_bom_post` 返回格式正确的 BOM component 行
- **THEN** 正常构造 `BomRow`，无异常

### Requirement: ConnectorValidationError 携带上下文
`ConnectorValidationError` SHALL 为标准 Python 异常，含以下属性：`source: str`（"SRM" / "zp_ERP"）、`field: str`（首个校验失败字段名）、`raw: dict`（原始响应行，用于 debug）。异常消息 MUST 包含 source 和 field 信息，便于 AIOps 排障。

#### Scenario: 异常消息含 source 和 field
- **WHEN** `ConnectorValidationError` 被捕获
- **THEN** `str(exc)` 含数据源名称和字段名，如 "SRM validation error: field=answerQty"

