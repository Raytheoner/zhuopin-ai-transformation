# fi2-recon-report Specification

## Purpose
TBD - synced from change fi2-recon-mvp (change remains active, not yet archived). Update Purpose after archive.

## Requirements

> **v3 口径修正（2026-07-09，design D11/D12）**：聚合单元从"PO 行"改"料品"（ap_no+item_code）；"无 GR 支撑"改名"无发票支撑"；新增 AP-PO 单价校验（价格超差）与五类判定的合并路由规则。
>
> **R5 门禁新增（2026-07-10，design D14；范围 2026-07-16 Paul 拍板确认）**：新增"整单差异总额分级 L2/L3"门禁，仅对"金额微差"类生效（Paul 已确认不扩大到"明细错位"，为最终口径，见 design D14-b）；报告状态由二态（`needs_review`/`l3_suggested_pass`）扩为三态，新增 `l2_self_resolved`。

### Requirement: 报告聚合与 L3 门禁

系统 SHALL 将逐料品匹配分类结果聚合为对账报告，且按 L3 门禁规则路由：🟡金额微差 / 🔴明细错位 / 🔴数量金额不符 / 🔴无发票支撑 四类 MUST 标记为 `needs_review`（需人工确认）；🟢完全匹配类标记为 `l3_suggested_pass`（AI 建议通过）。任何结果 MUST NOT 被系统自动标记为已过账或已结案——本 MVP 不实现自动过账路径。

#### Scenario: 非完全匹配强制转人工
- **WHEN** 某料品分类为"数量金额不符"
- **THEN** 该料品报告状态 SHALL 为 `needs_review`

#### Scenario: 完全匹配标建议通过但不自动过账
- **WHEN** 某料品分类为"完全匹配"且未触发价格超差
- **THEN** 该料品报告状态 SHALL 为 `l3_suggested_pass`，报告文案 MUST 明确标注"AI 建议通过，未过账"

### Requirement: AP-PO 价格超差强制转人工（design D12）

系统 SHALL 将 AP-PO 单价校验（`fi2-price-check`）结果并入报告聚合层：若某料品对应的任一 AP 行价格超差（`exceeds_tolerance=True`），该料品报告状态 MUST 被强制改写为 `needs_review`，**即便其五类判定结果为"完全匹配"**；五类判定结果本身（`classification` 字段）MUST NOT 被价格校验覆盖，仅路由状态被覆盖。

#### Scenario: 完全匹配但价格超差仍转人工
- **WHEN** 某料品五类判定为"完全匹配"，但其 AP 单价相对 PO 单价超出 R7 容差
- **THEN** 该料品报告状态 SHALL 为 `needs_review`，`classification` 字段仍为"完全匹配"，报告 MUST 标记 `price_check_failed=true`

### Requirement: R5 门禁——整单差异总额分级 L2/L3（design D14）

系统 SHALL 对分类为"金额微差"的料品，按其所属 `ap_no` 聚合未税金额差异总额，相对该 `ap_no` 关联 PO 行的未税金额合计（"整单"），计算是否在门禁线内（差异总额 ≤¥1，或占比 ≤0.5%，两者取宽松者）；在门禁线内 SHALL 将报告状态改写为 `l2_self_resolved`（AP 自行消化，不转人工），超线 MUST 维持 `needs_review`。本门禁 MUST NOT 应用于"无发票支撑"/"明细错位"/"数量金额不符"三类（结构性问题不因总额小而降级）。价格超差（`fi2-price-check`）优先级 MUST 高于本门禁——即便整单差异在门禁线内，价格超差料品仍 MUST 强制 `needs_review`。

#### Scenario: 整单差异在门禁线内降级 L2
- **WHEN** 某料品分类为"金额微差"，其所属 `ap_no` 下"金额微差"料品的未税金额差异总额为 ¥0.3，该 `ap_no` 关联 PO 行未税金额合计为 ¥1000
- **THEN** 该料品报告状态 SHALL 改写为 `l2_self_resolved`，`needs_review` 为 `false`

#### Scenario: 整单累计差异超门禁线维持 L3
- **WHEN** 同一 `ap_no` 下存在多个"金额微差"料品，各自差异均在容差内，但未税金额差异总额超出门禁线（¥1 且占比超 0.5%）
- **THEN** 这些料品报告状态 SHALL 维持 `needs_review`，不得因单料品差异小而降级

#### Scenario: 价格超差优先于 R5 门禁
- **WHEN** 某"金额微差"料品的整单差异总额在门禁线内，但其对应 AP 行价格超差
- **THEN** 该料品报告状态 SHALL 为 `needs_review`，不得因门禁在线内而降级为 `l2_self_resolved`

### Requirement: 审计留痕（金额脱敏）

系统 SHALL 为每个料品匹配判定写入一条平台 `AuditEvent`（`scenario="FI2"`），记录应付单号/料品编码/分类结果/差异比例/触发维度/价格校验标记；MUST NOT 在审计记录中写入原始发票单价、未税金额或税额的绝对值。

#### Scenario: 审计事件字段脱敏
- **WHEN** 系统为某料品超容差判定写审计事件
- **THEN** 审计记录 SHALL 包含分类结果与差异比例，MUST NOT 包含该料品原始未税金额、税额或单价的绝对数值

### Requirement: L3 人工改判 CLI

系统 SHALL 提供命令行工具，供财务人员对 `needs_review` 状态的料品录入人工结论；`--reason`（改判原因）MUST 为必填项，缺失或为空 MUST 拒绝执行；同一料品重复提交改判 MUST 幂等（不重复写审计，提示已存在记录）。

#### Scenario: 改判原因缺失被拒绝
- **WHEN** 财务人员调用改判 CLI 但未提供 `--reason` 或提供空字符串
- **THEN** 系统 SHALL 拒绝执行并提示错误，不写入审计记录

#### Scenario: 重复改判幂等
- **WHEN** 同一料品已存在改判记录，财务人员再次提交相同料品的改判
- **THEN** 系统 SHALL 跳过重复写入，打印警告而非报错
