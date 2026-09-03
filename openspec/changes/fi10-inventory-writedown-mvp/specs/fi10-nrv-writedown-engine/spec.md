## ADDED Requirements

### Requirement: 未签认判据不得默认生效

系统 SHALL 把 NRV 估算口径、库龄超期门限、项目终止未耗物料口径维护在配置层，签认前**一律为空值**，引擎读到空判据时 MUST fail-loud，MUST NOT 回退到任何准则通用解读或行业惯例。

#### Scenario: NRV 口径未签认
- **WHEN** `NRV_ESTIMATION_BASIS` 为空
- **THEN** 引擎抛出显式异常，**不返回任何 NRV 或跌价额**；`WritedownTest.nrv` 保持为空（**而非 0**——0 会被读成"可变现净值为零"，那是最严重的跌价结论）

#### Scenario: CI 守住空值
- **WHEN** 任何人把未签认判据填成实值而无签认落档
- **THEN** `test_unsigned_criteria_stay_none` 失败

### Requirement: 🔴 呆滞口径须与 SC7 同源，无源时不得自定义

链 D 联动点 L9 要求本场景的呆滞/跌价口径与 `SC7` 同口径。在 `SC7` 的呆滞口径落地前，本系统 MUST NOT 自行定义呆滞口径。

> `#474` 原文：「呆滞口径应从那里取、**不得另立一套**」。而 `SC7` 的呆滞库存处置属②期深化（2027-01）尚未落地、业务口径待确认 ⇒ 要对齐的那个口径当前不存在。自行定义即等于另立一套，且属 🟡 `change_criteria`。

#### Scenario: 无源时停下
- **WHEN** `SLOW_MOVING_CRITERIA` 为空
- **THEN** 呆滞识别 fail-loud 并说明"应从 SC7 取而 SC7 尚未落地"，MUST NOT 采用任何自拟口径

#### Scenario: 口径归属变更须拍板
- **WHEN** 拟改由 FI10 先定口径、SC7 后对齐
- **THEN** 该变更属口径归属改动，须经拍板方可执行

### Requirement: NRV vs Cost 准则跌价测试

系统 SHALL 按会计准则对每个（料号 × 批次）执行 NRV vs Cost 比较并计算跌价额，每条结论记录其判定依据与 `RULE_VERSION`。

#### Scenario: 成本高于 NRV
- **WHEN** 账面成本 > 可变现净值
- **THEN** 输出跌价额 ＝ 账面成本 − NRV，并标记需人工复核

#### Scenario: 成本不高于 NRV
- **WHEN** 账面成本 ≤ 可变现净值
- **THEN** 跌价额为 0，结论仍记录依据与版本以备审计

#### Scenario: 账面成本为纯派生
- **WHEN** 计算某批次账面成本
- **THEN** 结果等于数量 × 单位成本（不含任何判据）
