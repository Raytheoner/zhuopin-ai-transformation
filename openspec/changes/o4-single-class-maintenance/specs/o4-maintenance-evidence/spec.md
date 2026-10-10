## Purpose

为O4单类预测维护的后续试点先提供类别无关合成证据结构合同，保留输入身份、版本、来源引用和scope，
如实报告缺数/冲突/关联问题。此阶段输出未评估状态与审计证据，不提供设备风险预测或维护动作。

## ADDED Requirements

### Requirement: 显式合成身份与冻结输入
系统 SHALL 要求非空bundle_id/revision/schema与显式synthetic=true、scope，并在计算前冻结所有输入值。
来源引用 SHALL 仅作为证据标识，不在此入口访问真实系统。类别在此阶段可未确定，不得自动选择设备例子。

#### Scenario: 非合成或无身份输入
- **WHEN** 输入非synthetic或关键身份缺失
- **THEN** 拒绝完整合成run，不能默认为合成或用标签补身份

#### Scenario: 原对象随后改变
- **WHEN** 调用方在封套建立后修改原数据
- **THEN** 本次输出与hash仍绑定冻结值，不读取变化后的对象

### Requirement: 原值缺口和冲突检查
系统 SHALL 保留原值、原声明单位、发生/获取时点、来源事件ID/版本，报告缺值、未关联、
单位声明冲突、无时区及同事件版本值冲突。MUST NOT 补数/换算/自行归故障标签或吞冲突版本。

#### Scenario: C02到C07结构问题
- **WHEN** 输入分别含无资产引用、缺原值、单位冲突、无时区、原值版本冲突或跨资产关联
- **THEN** 各问题有明确来源引用与issue，不填默认值/时区/单位、不产物理故障结论

#### Scenario: 零值和缺值可区分
- **WHEN** 同信号分别有原值0与None
- **THEN** 0原值保留，None标缺失，二者不能被同一缺省转换合并

### Requirement: 跨范围身份隔离
资产关联 SHALL 使用显式scope与asset_id组合；同显示标签MUST NOT成为跨scope关联键。
输入重复记录/冲突revision SHALL 保留，使原证据可追溯。

#### Scenario: C08相同标签不同scope
- **WHEN** 两合成范围使用同一显示标签
- **THEN** 分别保留其身份/输出/hash，不合并为同资产或共享历史

### Requirement: 输出严格保持未评估
本阶段所有健康分数、故障概率/模式、RUL、维护/备件建议及OEE实绩 SHALL 未提供；
prediction_status SHALL not_evaluated，professional_signoff SHALL 空，结构可读不等于预测就绪。

#### Scenario: C01结构完整
- **WHEN** 合成资产/测量/维护关联完整但无类别及专业基准
- **THEN** 可提供结构检查结果，预测值仍空/not_evaluated，不输出默认阈值或动作

### Requirement: 版本hash与审计失败关闭
完整run SHALL 非空可归责actor、完整输入/output版本hash和可写平台audit。
事件 SHALL 明示synthetic/not_evaluated/无专业签认，仅摘要与引用hash；没有audit或写失败MUST传播失败。
纯检查preview不得被当作完整L2交付或专业确认。

#### Scenario: 实际合成JSONL事件
- **WHEN** 完整run成功
- **THEN** 可从实际JSONL读回对应输入/output hash和检查版本事件，不以no-op sink称成功

#### Scenario: 相同摘要不同内容
- **WHEN** 输入原值/版本变而issue计数相同
- **THEN** 输入及关联输出hash可区分，不能只hash摘要计数

#### Scenario: 审计失败和非法数
- **WHEN** audit不可写或输入有NaN/Inf
- **THEN** 不返回完整run成功；非法数明确拒绝，不以JSON替代字符或null吞掉

