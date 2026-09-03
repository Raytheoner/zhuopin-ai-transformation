## ADDED Requirements

### Requirement: 未签认判据不得默认生效

系统 SHALL 把三类异常的判定口径与升级门限维护在配置层，且在财务侧实名签认前**一律为空值**。检测器读到空判据时 MUST fail-loud，MUST NOT 回退到任何内置默认（含"3 倍标准差"这类通用统计经验值）。

> 异常检测最容易被「先随便设个 3 倍标准差」蒙混过去——那个数一旦落地就静默决定谁被推给财务主管、谁被放过，且永远不会报错。

#### Scenario: 判据未签认时检测器拒绝判定
- **WHEN** `AMOUNT_SURGE_CRITERIA` / `FREQUENCY_ANOMALY_CRITERIA` / `RELATED_PARTY_CRITERIA` 任一为空
- **THEN** 对应检测器抛出显式异常并指明缺哪一项、须谁签认，**不返回任何判定结论**

#### Scenario: CI 守住空值
- **WHEN** 任何人把未签认判据填成实数而无签认落档
- **THEN** `test_unsigned_criteria_stay_none` 失败，CI 变红

### Requirement: 关联方口径未定义前不得引入关联标志字段

在 `RELATED_PARTY_CRITERIA` 签认前，往来单位主数据模型 MUST NOT 包含任何"是否关联方"的布尔字段。

> 留一个 `is_related` 字段会诱使实现方先填上再说——判据就是这样被默默造出来的。

#### Scenario: 模型层守住
- **WHEN** `PartyProfile` 上出现 `is_related` / `is_related_party` / `related` / `related_party` 任一字段而口径仍为空
- **THEN** `test_party_profile_has_no_related_flag` 失败

### Requirement: 三类模式检测器

系统 SHALL 提供金额突增、频率异常、关联方交易三类检测器，逐笔比对历史模式基线，输出命中的模式集合、风险等级与判定依据。

#### Scenario: 金额突增
- **WHEN** 某笔交易金额相对该（单位 × 科目 × 方向）的历史基线满足签认的突增口径
- **THEN** 判定结论的 `patterns` 含 `amount_surge`，并记录所用基线与 `RULE_VERSION`

#### Scenario: 频率异常
- **WHEN** 某单位在签认窗口内的交易笔数超出签认口径
- **THEN** `patterns` 含 `frequency`，并记录窗口定义与实际笔数

#### Scenario: 关联方交易
- **WHEN** 交易对手方按签认的关联口径被判定为关联方
- **THEN** `patterns` 含 `related_party`，并记录命中的关联依据字段

#### Scenario: 历史基线不足
- **WHEN** 某（单位 × 科目 × 方向）的历史样本月数不足以支撑签认口径
- **THEN** 标记需人工复核并说明样本不足，MUST NOT 以"无历史即正常"放行

### Requirement: 无案例库时不得视作阴性

在可疑交易案例库尚未建立时，系统 MUST NOT 把"查不到历史异常记录"当作交易正常的证据。

> 那是把空数据当成阴性结论，与本项目其他"静默回退"事故同族。

#### Scenario: 空案例库
- **WHEN** 案例库为空或不可用
- **THEN** 判定结论显式标注"无案例库参照"，并保持 `needs_manual_review` 为真
