## MODIFIED Requirements

### Requirement: 报告聚合与 L3 门禁

> **本次修订（起点反转）**：状态由三态扩为四态，新增中性态 `l0_pending_invoice`；原「无发票支撑」在路由表中的位置由「长期待票」承接。R5 门禁的适用范围、价格超差的优先级、以及其余四类的路由 **一字不变**。

系统 SHALL 将逐料品匹配分类结果聚合为对账报告，并按下列路由：🟡金额微差 / 🔴明细错位 / 🔴数量金额不符 / 🔴长期待票 四类 MUST 标记为 `needs_review`（需人工确认）；🟢完全匹配类标记为 `l3_suggested_pass`（AI 建议通过）；**🔵待票 MUST 标记为 `l0_pending_invoice`**。

🔴 `l0_pending_invoice` 的语义是「正常在途、尚无需任何人动作」。该状态 MUST NOT 被计入需人工确认的结果集，MUST NOT 进入对外的未通过清单，MUST NOT 触发对任何人的点名或通知。它 SHALL 在报告与面板中被如实计数与展示，使「今天有多少张单还在等票」可见。

任何结果 MUST NOT 被系统自动标记为已过账或已结案——本场景不实现自动过账路径。

#### Scenario: 非完全匹配强制转人工
- **WHEN** 某料品分类为「数量金额不符」
- **THEN** 该料品报告状态 SHALL 为 `needs_review`

#### Scenario: 完全匹配标建议通过但不自动过账
- **WHEN** 某料品分类为「完全匹配」且未触发价格超差
- **THEN** 该料品报告状态 SHALL 为 `l3_suggested_pass`，报告文案 MUST 明确标注「AI 建议通过，未过账」

#### Scenario: 待票不进人工队列也不触发通知
- **WHEN** 某料品分类为「待票」
- **THEN** 其报告状态 SHALL 为 `l0_pending_invoice`，不计入 `needs_review` 计数，不出现在对外未通过清单中，不触发任何点名

#### Scenario: 待票在报告中如实可见
- **WHEN** 当日结果集中存在若干「待票」料品
- **THEN** 报告与面板 SHALL 给出其数量与所属 AP 单，MUST NOT 因其为中性态而从展示中省略

#### Scenario: 长期待票转人工
- **WHEN** 某料品分类为「长期待票」
- **THEN** 其报告状态 SHALL 为 `needs_review`，并进入对外未通过清单

### Requirement: R5 门禁——整单差异总额分级 L2/L3（design D14）

> **本次修订仅补一句适用范围**，门禁算法、阈值与优先级一字不变。

系统 SHALL 对分类为「金额微差」的料品，按其所属 `ap_no` 聚合未税金额差异总额，相对该 `ap_no` 关联 PO 行的未税金额合计计算是否在门禁线内；在门禁线内 SHALL 将报告状态改写为 `l2_self_resolved`，超线 MUST 维持 `needs_review`。

本门禁 MUST NOT 应用于「明细错位」/「数量金额不符」/「长期待票」三类（结构性问题不因总额小而降级），亦 MUST NOT 应用于「待票」（该态本就不在人工队列内，门禁对它无意义）。

价格超差优先级 MUST 高于本门禁——即便整单差异在门禁线内，价格超差料品仍 MUST 强制 `needs_review`。

#### Scenario: 整单差异在门禁线内降级 L2
- **WHEN** 某料品分类为「金额微差」，其所属 AP 单的「金额微差」未税金额差异总额在门禁线内
- **THEN** 该料品报告状态 SHALL 改写为 `l2_self_resolved`

#### Scenario: 长期待票不受门禁降级
- **WHEN** 某料品分类为「长期待票」，且其所属 AP 单的差异总额很小
- **THEN** 该料品报告状态 SHALL 维持 `needs_review`，MUST NOT 被降级

#### Scenario: 价格超差优先于 R5 门禁
- **WHEN** 某「金额微差」料品的整单差异总额在门禁线内，但其对应 AP 行价格超差
- **THEN** 该料品报告状态 SHALL 为 `needs_review`
