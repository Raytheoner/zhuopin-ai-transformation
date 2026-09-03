# fi10-alerting-and-provision Specification

## Purpose

产出库龄超期、项目终止未耗物料等跌价预警，并生成跌价准备计提建议表与 what-if 模拟。
🔴 计提建议影响财务报表：每行必须携带免责标注，未经实名确认者不得据以入账；芯片降价类预警在芯片价格 API 前置满足前不得产生。

## Requirements

### Requirement: 🔴 依赖芯片价格 API 的预警在前置满足前不得产生

芯片降价超阈值预警依赖尚未选型签约的芯片价格 API（队列 `#475` 独立立行）。在该前置满足前，系统 MUST NOT 产生该类预警，也 MUST NOT 以任何替代价格源（手工表、历史采购价推算、公开行情抓取）代替。

> 且该前置的**标的本身尚待判定**：「芯片**供货** API」与「芯片**市场价格** API」命名／服务对象／时点三项均不同，是否同一项未定。**判定前不得开始选型，否则可能选错标的。**

#### Scenario: 前置未满足即不产生
- **WHEN** `CHIP_PRICE_API` 为空
- **THEN** 系统中不存在生成 `chip_price_drop` 类预警的代码路径

#### Scenario: 不得以替代价格源顶替
- **WHEN** 有人以历史采购价推算"价格趋势"
- **THEN** 该做法被拒绝——推算出的趋势看起来正常但与市场无关，且不会报错

### Requirement: 库龄超期与项目终止未耗物料预警

系统 SHALL 按签认门限产生库龄超期预警与项目终止未耗物料预警。

#### Scenario: 门限未签认
- **WHEN** `AGING_ALERT_THRESHOLD` 或 `TERMINATED_PROJECT_ALERT_CRITERIA` 为空
- **THEN** 对应预警 fail-loud，MUST NOT 采用任何默认天数

#### Scenario: 项目终止后的在途处理
- **WHEN** 某 OEM 项目已终止而其物料仍有在途采购
- **THEN** 预警须显式覆盖在途部分，MUST NOT 只看已入库存量

### Requirement: 跌价准备计提建议 —— L2 门禁

系统 SHALL 生成跌价准备计提建议表，且 MUST NOT 自动入账。计提建议影响财务报表，每行 MUST 显式携带免责标注，未经实名确认者 MUST NOT 据以入账。

#### Scenario: 免责标注必填
- **WHEN** 生成一行 `ProvisionAdvice`
- **THEN** 其 `disclaimer` 为必填项（无默认值），标注「AI 测算建议，须财务/供应链经理确认」

#### Scenario: 未确认不得入账
- **WHEN** 某行 `confirmed_by` 为空
- **THEN** 该行 MUST NOT 进入任何入账流程

#### Scenario: 测算默认需人工
- **WHEN** 构造一条 `WritedownTest`
- **THEN** 其 `needs_manual_review` 为真

### Requirement: what-if 模拟

系统 SHALL 支持跌价测算的 what-if 模拟（如价格再降 N%、某项目提前 EOP）。

#### Scenario: 情景与基线可区分
- **WHEN** 输出 what-if 结果
- **THEN** 结果显著标注为假设情景并可追溯到基线测算

### Requirement: 判定全链写平台 audit

系统 SHALL 把每次跌价判定、预警与计提建议写入平台 `audit`（append-only，3 年留存）。

#### Scenario: 留痕
- **WHEN** 产生一次判定、预警或建议
- **THEN** 一条含依据、门限值、`RULE_VERSION` 与时刻的审计事件被追加写入
