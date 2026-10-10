# O4 分阶段 design · 设备预测性维护

状态：完整intent已确认；本书面design D1–D7待审，不授权产品/测试/真实源。首期1类与类别后定不重问。

## Context

已确认intent见场景正本。现有OPS-EVIDENCE-DRAFT/r1的O4-C01–C08为共同结构材料，实际运行/专业签认均空；
无O4模型或真实资料通路实证。main specs现时目录枚举暂无O4/maintenance能力；平台已有AuditEvent/AuditLogger。
本包先把类别无关证据结构建成可核验入口；完整单类业务试点仍依实际选类和专业资料。

## Goals / Non-Goals

Goals：版本化合成输入封套、确定性的结构缺口/冲突/关联检查、可追溯not_evaluated输出、合成审计；
不阻断未来专属模型/人工复核设计。
Non-Goals：健康分数、故障概率/RUL/风险等级、维护时机、OEE实绩；真实接口、任何设备控制/工单/采购/自动告警。

## Decisions

| 决策 | 推荐A | 备选与取舍 |
|---|---|---|
| D1 分阶段 | Stage0类别无关合成结构；Stage1实际盘点选1类/专属design；Stage2专业签认后试点；Stage3扩展另包 | 直接选择炉/台架并造阈值无资料依据。等待所有未来专业前置后才做结构会丢失可推进首项。 |
| D2 输入身份 | immutable封套含bundle_id/revision/schema_version/synthetic=true及显式scope、source references/hash，冻结资产/测量/维护原值 | 不用设备显示名作键；不覆盖原资料，身份缺失报告结构不完整，非synthetic入口拒绝。 |
| D3 关联检查 | (scope,asset_id)复合身份；source event ID/revision保留冲突；报告资产未关联、原值缺失、单位声明冲突、无时区、事件版冲突/跨资产 | 不换算/补数、不中选最后一版、不把维护原记录当故障真值；同标签跨scope独立。 |
| D4 输出状态 | evidence schema/readiness/issues附精确引用；所有health/failure/RUL及维护/OEE结果为空，prediction_status=not_evaluated | C01结构完整也不解模型闸；检查issue是结构证据，不诊断物理设备。 |
| D5 hash | UTF-8 canonical JSON，显式字段映射、原值类型/单位/时区声明保留；排序按canonical bytes，重复记录保留；NaN/Inf拒绝，SHA256绑定版本/完整输入/输出 | 不用repr/摘要计数hash。结构manifest不是源系统真实性证明，合成输入必须显著标记。 |
| D6 audit | 完整run须非空actor和可写平台AuditLogger；record→sink.write后可读回合成JSONL，记录输入/output hash、检查规则版本、not_evaluated/no professional_signoff | 低层pure check无IO只能preview；audit=None/写失败不得完整run成功。事件不带原值/长原文，只引用/hash/issue计数。 |
| D7 产品入口与兼容 | 新O4包内分离models/evidence/checks/agent及测试，提供单次合成run；平台只复用，无Web/服务/数据库/设备读取 | 不加通用平台模型，不创建独立端口；门户与专业人工复核UI待后续实际单类design。 |

### D2/D3 具体合同

bundle必须显式synthetic=true、非空scope/bundle/revision/schema；category在Stage0可空且状态未确定。
每封套仅一个scope，含其他scope的记录须拒绝而非跨范围拼接；C08用两个独立封套/run保留各自输出/hash，绝不共享可变累积状态。
资产、测量、维护各保留来源ID/版本及source_ref；输入检查不访问source_ref。
actor为合成核验操作者标识，不能充当Owner/维护工程师。
发生/获取时点分列；原时间无时区即issue，不补时区。原始value=None与0区分，未声明单位不赋物理单位。
同一scope/来源事件两revision值冲突均保留并报告；跨scope记录不合并。不把同来源的重复行自动去重。
先定义具体schema/issue枚举和canonical字段映射于获批后实施计划，不在本design以可变字典默认规则代替。

### 八例对照与未闭专业项

C01通用资产/测量/维护对齐仅结构可读；
C02资产引用缺记录；C03原值缺失；C04同信号声明单位冲突；
C05发生时间无时区；C06同来源事件版本原值冲突；C07测量与维护跨资产；
C08同显示标签跨scope独立。均prediction not_evaluated，所有预测、维护及OEE结果为空，无专业签认。
八例是类别无关的结构样例，不是预测黄金集、设备类别样本或专业效果验证。
验收比较预期结构issues和实际run证据，不把旧actual_run=null样例算已运行。

O4-G-01–05为待专业点占位：标签、信号质量、风险维护阈值、预测适用/黄金、备件/OEE。
Owner/backup/维护签认实名、真实类/资产/接口与权限等属于Stage1/2；
不猜人名、不代签，不把本包算法结构用来解除它们。

## Risks / Trade-offs

- [结构C01被误读为预测通过] → 输出字段强制空/not_evaluated，报告标题标synthetic evidence，独立专业闸。
- [同标签跨资产/客户污染] → scope+asset复合键，合成仅白名单；真实OEM资料另做平台隔离与权限评审。
- [冲突版本被last-write吞掉] → 全量冻结/重复保留并报issue，hash覆盖完整值。
- [audit失败后仍报成功] → orchestration必须写成功，actual JSONL验收与异常传播，纯函数只preview。
- [未来模型未知而过度造框架] → 本包只证据/检查/audit；接口仅一合成run，不装ML库/队列/IoT/服务。
- [新报告误被Sweep收入] → 只new UUID reports目录，已check-ignore根.gitignore:59 **/reports/；具体计划逐路径复核。

## Migration Plan

1. 已确认intent→本design审；若批准再锁schema/issue/代码/测试白名单及具体Native隔离计划审。
2. 实施只mock，在独立候选树；现主仓仅文档，不复制真实数据/凭据。
3. 完整synthetic evidence review与交付，保持全部预测not_evaluated，不晋真实档/不发版/不归档全业务包。
4. Stage1盘点专业回件到位后单类专属design/plan；Stage2真实试点另取权限与验证；Stage3另包。
回退保留输入/报告/旧记录；新O4无既有服务切换，不执行生产回滚动作。

## Open Questions

设备类别/资产、实际信号及维护历史、Owner/backup/维护专业签认人与阈值仍未知，
它们仅影响明确后置的Stage1/2，不改变本Stage0证据结构方案。
若实际资料要求不同schema或多类范围，提出带证据的下一设计修订，不暗改本包或自填缺口。

