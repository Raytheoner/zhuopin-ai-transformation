## Purpose

付款申请审批前跑完 FI3-1～FI3-6 六项校验并归入四态（🟢通过／🟡提醒放行／🔴拦截／🟣特批），输出 L3 旁路校验清单。判据 R1–R8 由财务总监签认后登记于平台判据签认注册表；AI 只出建议，付款执行永远人工。

## ADDED Requirements

### Requirement: 判据只能来自已签认注册表

引擎 SHALL 通过 `zhuopin_platform.criteria_signoff.CriteriaRegistry`（`fi3_payment_validation/config.py` 的 `CRITERIA`）读取 R1–R8，MUST NOT 在任何引擎文件内写死阈值、档位或天数。未签认项（`PENDING`）读取时 MUST 抛 `CriterionNotSignedOffError`。

#### Scenario: R1–R8 全部实名签认
- **WHEN** 导入 `config`
- **THEN** 八条判据均带 `Signoff(signed_by="唐燕萍", evidence=就绪清单回复件)`，`RULE_VERSION` 不含 `unsigned`，`PENDING_VERSION` 含 `unsigned`

#### Scenario: 未签认的账龄天数
- **WHEN** 读取 `PENDING.value_of("PREPAY_AGEING_WARN_DAYS")`
- **THEN** 抛出并指明应由谁签；引擎只输出账龄度量、不判预警

### Requirement: 主数据缺失不得视作通过

供应商无生效收款账户、合同号在合同主数据中不存在、正式付款未附发票或发票无 FI2 匹配结果时，引擎 MUST 产出拦截级发现，MUST NOT 跳过该项。

#### Scenario: 无主数据供应商
- **WHEN** 申请的供应商在收款账户主数据中无生效记录
- **THEN** 结论为 🔴拦截，发现 `account_mismatch` 说明「缺主数据不等于通过」

### Requirement: 四态归类与紧急特批

引擎 SHALL 按 R1 分级归类：任一拦截级发现 ⇒ 🔴；仅提醒／预警级 ⇒ 🟡；无发现 ⇒ 🟢。拦截级发现**全部**为「三单未配齐」且申请标紧急时 ⇒ 🟣特批，按 R7 记录审批人 CFO、标签「紧急特批」、按工作日算出补齐期限并写入《未匹配付款跟踪清单》。紧急标记 MUST NOT 豁免其它拦截项。

#### Scenario: 紧急且仅三单未配齐
- **WHEN** 申请 `is_urgent` 且唯一拦截项为 FI3-1
- **THEN** 结论 🟣，`special_approval.backfill_deadline` ＝ 基准日后第 7 个工作日（按节假日日历）

#### Scenario: 紧急但账户不符
- **WHEN** 申请 `is_urgent` 且存在 `account_mismatch`
- **THEN** 结论仍为 🔴拦截

### Requirement: 每笔判定写审计且不含原始账号

每张申请 SHALL 产生一条 `AuditEvent(scenario="FI3", automation_level="L3")`，`decision` 恒含 `rule_version` 与 `automation_level`；审计 payload、报告与发现证据中的银行账号 MUST 只保留尾 4 位。

#### Scenario: 十二张 mock 申请
- **WHEN** 批量校验 mock 夹具
- **THEN** 审计 JSONL 恰 12 行，全部 `rule_version="fi3-v1-tangyanping-2026-07-10"`，全文不出现任何完整账号

### Requirement: L3 恒定直至会签

`ValidationVerdict.needs_manual_review` SHALL 恒为 `True`，`AUTOMATION_LEVEL` SHALL 为 `L3`；升 L4 的唯一前提是 `PENDING.L4_PROMOTION_COSIGN` 以 Shao Peishen ＋ CFO 会签底稿签认。

#### Scenario: 会签前
- **WHEN** 任何结论产出
- **THEN** `automation_level == "L3"` 且 `needs_manual_review is True`
