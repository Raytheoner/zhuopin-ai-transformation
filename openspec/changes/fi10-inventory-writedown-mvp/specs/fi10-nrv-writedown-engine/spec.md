## Purpose

按会计准则对每个（料号 × 批次）执行 NRV vs Cost 跌价测试，并按签认口径识别呆滞物料。
🔴 NRV 口径、库龄门限、项目终止口径与呆滞认定口径均须财务侧签认；呆滞口径的归属已定为「FI10 先出、SC7 后对齐」，但口径本身仍未签认。

## ADDED Requirements

### Requirement: 未签认判据不得默认生效

系统 SHALL 把 NRV 估算口径、库龄超期门限、项目终止未耗物料口径与**呆滞物料认定口径**登记在平台判据签认注册表（`zhuopin_platform.criteria_signoff.CriteriaRegistry`，本场景声明于 `fi10_inventory_writedown/config.py`），签认前**一律未签认**，引擎读取未签认判据时 MUST 抛 `CriterionNotSignedOffError`，MUST NOT 回退到任何准则通用解读或行业惯例，读值路径 MUST NOT 提供 `default` 参数或任何等价旁路。

#### Scenario: NRV 口径未签认
- **WHEN** 读取 `NRV_ESTIMATION_BASIS`
- **THEN** 引擎抛出显式异常，**不返回任何 NRV 或跌价额**；`WritedownTest.nrv` 保持为空（**而非 0**——0 会被读成"可变现净值为零"，那是最严重的跌价结论）

#### Scenario: CI 守住未签认状态
- **WHEN** 任何人把未签认判据签成实值而无签认落档
- **THEN** `test_criteria_registry_all_unsigned` 失败

#### Scenario: 版本号与签认状态不得互相撒谎
- **WHEN** 尚有判据未签认而 `RULE_VERSION` 不自陈 `unsigned`，或判据已全部签认而版本号仍带 `unsigned`
- **THEN** 配置模块在**导入期**即抛

#### Scenario: 前置未满足的缺口不得并入判据注册表
- **WHEN** 有人把 `CHIP_PRICE_API` 登记进 `CriteriaRegistry`
- **THEN** 该做法被拒绝——它靠**上游前置（队列 `#475`）落地**解除，不靠财务侧签认解除；且其标的本身尚待判定，登记成"待财务侧签认的判据"会把它派给一个解不了它的人

### Requirement: 🔴 呆滞口径归属 —— FI10 先定、SC7 后对齐

链 D 联动点 L9 要求本场景的呆滞/跌价口径与 `SC7` 同口径。**口径归属已于 2026-09-03 由 Shao Peishen 拍板（`EE-4` ＝ (a)）：FI10 先出该口径，`SC7` 其②期深化落地时与本口径对齐。** 本系统 SHALL 把该口径作为一条标准的待签认判据登记进判据注册表，`owner` 为财务侧；签认前 MUST NOT 使用任何自拟口径。

> 成因值得留下：`#474` 原文写的是「呆滞口径应从 `SC7` 取、**不得另立一套**」，而 `SC7` 的呆滞库存处置属②期深化（2027-01）尚未落地、业务口径待确认 ⇒ **要对齐的那个口径当时并不存在**。该状态一度被登记为「判据无源可取」；`EE-4` 反过来把归属定给 FI10，它才从「无源可取」变成一条**标准的待签认判据**（连带触发 `G-3`：归进注册表）。
>
> ⚠️ **「先定」不等于「现在就填」**：被定下的只是**口径归属**，口径本身仍未签认。
>
> `owner` 归**财务侧**而非 `SC7` 业务口径确认人，因为该口径用于存货跌价计提、进财务报表；`SC7` 口径确认人是**签认前须知会**的对象，不是签认人。

#### Scenario: 未签认时停下
- **WHEN** 读取 `SLOW_MOVING_CRITERIA`
- **THEN** 呆滞识别抛出显式异常并指明须财务侧签认、签认前须知会 `SC7` 口径确认人，MUST NOT 采用任何自拟口径

#### Scenario: 登记不等于填值
- **WHEN** 该判据被登记进注册表
- **THEN** 其值仍为空、读取仍抛——登记解决的是"这条判据在不在查缺视野里"，不是"这条判据定了没有"

#### Scenario: SC7 落地时的对齐方向
- **WHEN** `SC7` ②期深化落地并需要呆滞口径
- **THEN** 由 `SC7` 与本场景已签认的口径对齐，MUST NOT 各自签一套

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
