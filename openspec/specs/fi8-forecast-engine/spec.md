# fi8-forecast-engine Specification

## Purpose

整合应收/应付计划、历史回款周期与在手订单，输出未来 4/8/12 周的逐周现金流预测。
🔴 银行账户余额的取数授权尚未取得（涉资金安全，须财务侧 ＋ CFO 办公室批），未授权时预测须 fail-loud，不得以任何推算的期初余额继续出数。

## Requirements

### Requirement: 4/8/12 周滚动现金流预测

系统 SHALL 整合应收/应付计划、历史回款周期与在手订单，输出未来 4、8、12 周的逐周现金流预测点（流入、流出、期末余额）。

#### Scenario: 三个视界同时输出
- **WHEN** 给定预测起点与输入数据集
- **THEN** 分别输出 4／8／12 周视界的逐周预测序列，每个点标注所属视界与所用 `RULE_VERSION`

#### Scenario: 分客户/供应商建模
- **WHEN** 某客户有足够历史回款样本
- **THEN** 该客户的应收按其自身回款周期分布落到相应周，而非一律按到期日落账

### Requirement: 银行账户余额取数须经授权，未授权时 fail-loud

系统 MUST NOT 在未取得财务侧与 CFO 办公室授权前读取真实银行账户余额。未授权时，预测引擎 MUST fail-loud，MUST NOT 以 0 余额、期初推算值或任何其他替代值继续出预测。

> 一个凭空推出来的期初余额会让整条 12 周曲线看起来完全正常，而它是错的，且不会报错。

#### Scenario: 未授权即拒绝出预测
- **WHEN** `BANK_BALANCE_ACCESS` 为空且请求使用真实余额
- **THEN** 引擎抛出显式异常说明授权缺口与须谁批准，**不返回任何预测结果**

#### Scenario: 骨架期只允许合成期初
- **WHEN** 在 mock 模式下构造期初余额
- **THEN** 其 `source` 为 `"synthetic"`

#### Scenario: 替代方案也须签认
- **WHEN** 采用"期初 ＋ 流水推算"替代实时余额
- **THEN** 该替代方案本身须经 CFO 签认并落档，MUST NOT 由实现方自选

#### Scenario: 授权缺口不得并入判据注册表
- **WHEN** 有人把 `BANK_BALANCE_ACCESS` 登记进 `CriteriaRegistry`
- **THEN** 该做法被拒绝——它是**权限缺口**（靠 CFO 办公室审批解除），不是**判据缺口**（靠财务侧签认解除）；并成一条会连"该找谁去解它"一起丢掉

#### Scenario: 授权推进的责任人已明确
- **WHEN** 问「这条授权卡在谁那里」
- **THEN** 答案是 Shao Peishen 本人推进（2026-09-03 裁决 `EE-2`），本场景在授权到位前只做**不依赖余额的部分**

### Requirement: 回款周期取样口径不得由实现方自定

系统 SHALL 从配置读取回款周期的取样口径（样本月数、集中趋势度量、异常单剔除规则），未签认时 fail-loud。

> 取几个月、中位数还是均值、剔不剔春节/年结异常单，不同选法能差出两周。

#### Scenario: 口径未签认
- **WHEN** `PAYMENT_CYCLE_SAMPLING` 为空
- **THEN** 引擎抛出显式异常，MUST NOT 采用任何默认统计口径

### Requirement: 链 D L8 —— 收入递延口径与 O2 缺口口径对齐

系统 SHALL 把 `O2` 物料齐套缺口映射为收入递延时，采用 `O2` 既有的缺口语义（`zhuopin_platform.agents.kit_engine.calc_shortage`），MUST NOT 另立一套缺口定义。

#### Scenario: 引用既有实现而非重写
- **WHEN** 定义收入递延的输入口径
- **THEN** 口径描述显式指向 `calc_shortage` 的语义（可用量 ＝ 库存 − 安全库存 ＋ 在途；缺口 ＝ max(毛需求 − 可用量, 0)）

#### Scenario: missing_snapshot 分支必须显式处理
- **WHEN** 某物料不在库存快照中（`calc_shortage` 的 B6 路径，在途仍计入可用量并记入 `missing_snapshot`）
- **THEN** 收入递延口径 MUST 显式规定该情形如何处理，MUST NOT 当作缺口为 0
