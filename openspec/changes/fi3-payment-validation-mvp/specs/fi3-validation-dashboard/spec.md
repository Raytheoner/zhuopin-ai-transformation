## Purpose

FI3-7 付款申请综合校验仪表盘：一屏汇总四态计数、各子场景命中、拦截与特批明细、到期日清单，可穿透到单张申请。

## ADDED Requirements

### Requirement: 汇总结构

`dashboard.summarize` SHALL 返回 `total`／`by_outcome`（四态全部键位，缺省 0）／`by_check`／`by_level`／`blocked`／`special`／`due_dates`，并带 `rule_version` 与 `automation_level`。

#### Scenario: mock 批量
- **WHEN** 汇总十二张 mock 申请
- **THEN** `by_outcome` ＝ 🟢2／🟡3／🔴6／🟣1，`by_check` 覆盖 FI3-1～FI3-6

### Requirement: 清单呈现纪律

Markdown 清单 SHALL 首行声明「付款执行永远由人在 U9C／银企系统完成」，逐单列出发现与特批信息；MUST NOT 出现完整银行账号。档 2 起提供门户页 `/finance/fi3`（不新起端口，预留网关 auth 接入点）。

#### Scenario: 渲染
- **WHEN** 渲染 mock 批量
- **THEN** 含声明句、含 🟣 特批行、不含任何完整账号
