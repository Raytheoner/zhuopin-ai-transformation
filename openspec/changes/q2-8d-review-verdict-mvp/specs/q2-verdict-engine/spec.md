## Purpose

对已有 8D 的 D1–D8 段落文本做 L2 预审：结构闸 → 六红线 → 51 条规则评分 → A/B/C/D 分级 → 安全分流 → 处置建议；判据全部来自陈忱签认的 V3.2 覆盖层，AI 只出评级与建议，退回由质量工程师签发。

## ADDED Requirements

### Requirement: 判据只能来自已签认注册表

引擎 SHALL 通过 `CriteriaRegistry`（`q2_8d_verdict/config.py` 的 `CRITERIA`）读取覆盖层参数，MUST NOT 写死分值、阈值或步长；`PENDING` 项读取 MUST 抛 `CriterionNotSignedOffError`。

#### Scenario: 覆盖层全部实名签认
- **WHEN** 导入 `config`
- **THEN** 24 条判据均带 `Signoff(signed_by="陈忱")`，`RULE_VERSION` 不含 `unsigned`，`PENDING_VERSION` 含 `unsigned`

### Requirement: 结构性退回先于红线语义判定

D3–D7 任一整段为空时引擎 MUST 直接输出结构性退回建议，MUST NOT 进入红线判定或评分；客户模板缺 D6 不算空段。

#### Scenario: 七步法第五~七步全空
- **WHEN** 映射后 D5/D6/D7 为空
- **THEN** `structural_return=True`，`redlines` 与 `rules` 为空

### Requirement: 语义类红线永不自动判 D

红线①②③⑤ SHALL 只输出疑似／本批不验收／转人工核；仅④（HIGH 且确认为空 ≥2 项）与⑥（D7 未提及更新流程资产，含填 N）可输出「触发」并判 D。抽取未命中 MUST NOT 当作真为空。

#### Scenario: 追溯字段抽取未命中
- **WHEN** 红线④字段为空但置信度非 HIGH
- **THEN** 状态＝转人工核，不判 D

#### Scenario: D7 固化表填 N
- **WHEN** D7 出现 PFMEA／控制计划字样但填 N
- **THEN** 红线⑥＝触发，等级＝D

### Requirement: 语义层待人工时只出等级区间

语义规则未裁决时引擎 SHALL 输出 `grade=None` 与 `grade_range`，处置＝转人工裁决；人工裁决齐全后 SHALL 输出单一等级。

#### Scenario: 合格样本无人工裁决
- **WHEN** 确定性规则满分、语义规则待人工
- **THEN** `grade is None` 且 `grade_range == ("D","A")`

### Requirement: 安全相关与 ASIL C/D

`safety_related` 为是／未确认时处置 MUST 为转人工裁决；`asil_level ∈ {C, D}` 时 MUST 抛 `AsilExcludedError`。

#### Scenario: ASIL C
- **WHEN** 输入 `asil_level="C"`
- **THEN** 抛 `AsilExcludedError`

### Requirement: 每份判定写审计

每份 8D SHALL 产生一条 `AuditEvent(scenario="Q2", automation_level="L2")`，`decision` 恒含 `rule_version`，`data_sources.rules` 为规则表 sha256。

#### Scenario: 十一份 mock 样本
- **WHEN** 批量判定 mock 夹具
- **THEN** 审计 JSONL 恰 11 行，`rule_version` 全等于 `config.RULE_VERSION`
