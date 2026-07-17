## ADDED Requirements

> **v3 新增（2026-07-09，design D12）**：堵 ERP 配票环节可手动改 AP 金额、无 PO 强制校验的控制漏洞。独立于料品汇总五类判定（`fi2-match-engine`/`fi2-result-classify`），合并路由规则见 `fi2-recon-report`。
>
> **R7 定稿真值（2026-07-10，design D14）**：人民币供应商统一容差改 ±2%（替换 CC 占位 ±3%）。外币供应商过渡规则（容差内连续 2 次同向偏移推人工抽查）与"方案一"原始外币单价+下单日汇率升级位，均因缺前置数据（供应商清单/跨运行历史状态）本次未实现，列入 future-work（见 design D14-d、tasks.md 10.12）。

### Requirement: AP-PO 单价强制比对

系统 SHALL 对每条 AP 明细行，比对其 `unit_price` 相对其前置 `(po_no, line_no)` 对应 PO 行 `unit_price` 的偏离比例，超出配置的容差（`config.AP_PO_PRICE_TOLERANCE_PCT`，R7 真值 ±2%）MUST 标记 `exceeds_tolerance=true`。比对 MUST 为纯函数，容差量级 MUST 从配置层读取。

#### Scenario: 价格在容差内（汇率豁口）
- **WHEN** 某 AP 行单价相对其前置 PO 行单价偏离 2%，未超出配置容差（真值 ±2%，等于边界不算超差）
- **THEN** 该 AP 行 SHALL 标记 `exceeds_tolerance=false`

#### Scenario: 价格超容差
- **WHEN** 某 AP 行单价相对其前置 PO 行单价偏离 6%，超出配置容差（真值 ±2%）
- **THEN** 该 AP 行 SHALL 标记 `exceeds_tolerance=true`

### Requirement: AP 行缺少前置 PO 参照时判超差

系统 SHALL 对找不到对应 `(po_no, line_no)` PO 行的 AP 行，标记 `has_po=false` 且 `exceeds_tolerance=true`（视为无法验证价格合理性的数据完整性异常，不得静默放行）。

#### Scenario: AP 行无对应 PO 行
- **WHEN** 某 AP 行的 `(po_no, line_no)` 在 `po_lines` 表中找不到对应记录
- **THEN** 该 AP 行 SHALL 标记 `has_po=false`、`exceeds_tolerance=true`、`price_diff_pct=null`

### Requirement: 金额脱敏

系统 SHALL 只在价格校验结果中保留差异比例（`price_diff_pct`），MUST NOT 落盘 AP 或 PO 的原始单价绝对值。

#### Scenario: 价格校验结果字段脱敏
- **WHEN** 系统输出某 AP 行的价格校验结果
- **THEN** 结果 SHALL 包含 `price_diff_pct`，MUST NOT 包含 AP/PO 原始 `unit_price` 字段
