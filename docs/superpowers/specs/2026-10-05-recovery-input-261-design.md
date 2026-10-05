---
status: 待设计审阅
created: 2026-10-05
source: 机制队列§四#261，Shao Peishen明确批准A
execution: Native，父会话Sol6.1；派生任务显式gpt-6-luna
---

# 【Codex】#261 恢复输入传递设计

记录时刻：2026-10-05 09:31:11 +08:00（Get-Date）。本文件是新增设计候选，不是实现、发布或再次派发批准。

## 1. 已批准意图与可证伪目标

用户原答：“#261：批准A，先做恢复输入传递设计，设计另审；新失败批原位保留，暂不重派；原#658实施批准保留，ff与真实切换另审。”

目标是通过正式入口把针对失败读取行为的定向更正交给下一次模型调用，并在公开请求中证明其确实进入输入。保留原task、intent、design、实施批准、计划、Guardian封存件及旧attempt。更正不能增加实施路径、改变模型/effort、放松hook或替代原实施批准。成功判据分三层：输入绑定和送达、模型实际读取行为、代码与CI/review交付；三者分别验收。

本轮只形成文档。新批B-1005_入口恢复实施仍blocked、未退役、不重派；#634依赖未解除。本设计不创造退役、ff、activation、生产.51、外发或L2授权。

## 2. 事实与适用范围

- 正式Workflow status：busy=false，最新implement attempt为402965bb229f43138085d718435eb1a6，path_guard_reason=empty_changes；无implementation_head、CI或review。
- 两次公开prompt SHA相同：4298be4cf8e37a7b04022701ba8447ee8d835a64a56038d63fc6a22c2ae4183a。恢复看护件没有改变真实模型输入。
- 真实构造点是workflow_driver.py::_run_model，implement输入来自原intent及核验后的approved_design_context；Guardian watch正文未拼入。handoff.py的run/advance目前没有额外输入参数；guardian_adapter.py::_advance_task只传workspace、authorization及固定Luna。
- 原计划在主仓绝对路径，原批准text已有正确路径与有限读取要求；模型又使用工作树中不存在的相对路径。当前不是“原计划不存在”或“原实施批准未给”。
- Probe本轮已成功，主仓HEAD=bca6047616db9ae63bdf61f085da57643172c867；原工作树design_head仍以原封存606c3bd498bf57b2ed2f9cd8d3f5773ce7d6e869为绑定，不能换主仓HEAD来解除旧闸。

范围仅限已经正式结束、busy=false、工作树干净且仍与获批design_head一致的implement失败恢复；首版只接受empty_changes。不支持proposal/review追加、不支持超时脏树resume、不支持修改已启动轮次、不支持自动重试。未来其它失败类型另审。

事实来源：接力658-恢复输入停点-2026-10-05.md、入口参数658-恢复派发核验-2026-10-05.md、两份原审阅表、原intent/proposal/design/tasks及本轮有限源码窗口；不读取私有rollout。旧证据hash见原核验表，不把本设计变成原证据的替代正本。

## 3. 方案比较与建议

| 方案 | 收益 | 代价/结论 |
|---|---|---|
| A：外部版本化恢复输入件，经正式入口核验并封存 | 保留旧封印；绑定失败attempt；能用公开request复核送达 | 新增CLI/Guardian传递接缝及测试；推荐 |
| B：全局改implement模板，重复强调主仓路径 | 改动较少 | 没有任务级更正来源和一次恢复绑定，影响所有任务；不采用 |
| C：另建完整任务并重新封存全部输入 | 能把更正纳入新intent | 原批准身份不可自动迁移，需要重新绑定整套任务/设计，容易重复审批；保留为无法兼容时的后备，不在本次执行 |

修改旧approval/intent/watch/claims、复制计划入工作树、手工prompt或换runner均不是候选方案。

## 4. 外部输入与批准契约（拟新增）

恢复件位于主仓和所有模型工作树之外的本机审批目录。它是输入说明，不是授权。输入件和批准件分离；普通人或模型写一个JSON不能生成许可。路径必须为真实绝对路径，resolve后再判断隔离边界，拒绝symlink/junction把外部路径实际导回模型可写区。

`RecoveryInputV1`严格对象（未知键拒绝）：

| 字段 | 类型及约束 |
|---|---|
| schema | literal `zhuopin.recovery-input/v1` |
| recovery_id | 非空有限ASCII slug，单次恢复身份 |
| task_id / phase | 原task_id；phase必须implement |
| previous_attempt_id | 当前最新终结empty_changes的implement attempt，不接受旧attempt代替最新attempt |
| workspace / design_head / design_sha256 | 真实规范化工作树绝对路径、40-hex HEAD、64-hex原design摘要 |
| implementation_approval_sha256 | 原实施批准文件字节SHA，不能改旧批准 |
| instructions | UTF-8字符串，1～8192 bytes，仅定向读取/执行顺序更正，不得出现新的权限或实施范围 |
| documents | 1～8个 `{path, sha256, max_lines}`；path绝对、sha256为文件字节摘要、max_lines为1～200整数 |

原始JSON字节限制32768 bytes；重复键、BOM处理策略必须确定为UTF-8可选单个BOM，哈希仍对原始字节；空白/键序变化产生新的文件字节SHA。严格结构不等于能自动理解自由文本：越界说明由设计/恢复批准人审查，机器实际权限始终取原白名单，不取instructions。

`RecoveryInputApprovalV1`也是外部只读JSON，至少含schema、recovery_id、task_id、phase、previous_attempt_id、recovery_input_sha256、implementation_approval_sha256、approval_source、text。approval_source引用具体人答的正本/登记载体；text保存该次明确批准原文。正式外层沿现有批准证据流程登记它，模型不生成批准；这沿用本机审批证据的信任边界，不声称JSON自带密码学签名。

#261本次只批准设计范围，不能用这句原答填成未来实际恢复批准。新增机制实现批准、原失败批退役批准和实际恢复批准均在具体产物形成后分别取得；若同一未来人答清楚列明各项，可一次答复逐项登记。

## 5. 正式传递接口与生命周期（拟新增）

1. Workflow只在`advance`新增成对参数`--recovery-input`与`--recovery-approval`；缺一即拒绝。legacy `run`收到这两个参数明确拒绝，不形成第二条执行通道。`invoke.ps1`仍只透传既有Workflow路由，无需新增替代入口。
2. Guardian manifest新增可选`recovery_inputs`，按task_id映射两份外部文件绝对路径；不能从watch正文、环境变量或默认目录发现更正。无映射时行为不变。
3. 新恢复批计划把每项输入件/批准件的原始SHA和绑定身份作为`recovery_bindings`封存。已有v1/v2算法与文件完全不变。原#658拟议reasoning fingerprint v3仍专属原参数契约；本设计预留v4表示恢复绑定，不能抢用或重定义v3。v4携带显式reasoning模式：legacy不注入新effort，governed需原reasoning契约；两项投影都纳入digest。实施前若版本4已被别的正本占用，必须修订设计，不静默改版本。
4. Guardian将已核绑定传至`_advance_task`→`driver.advance`→`run_one_stage`→`_implement`→`_run_model`。直连Workflow也走同一validator；driver持任务锁后再次比对最新attempt、busy、HEAD、批准及内容字节，防止锁前检查被竞争改变。失败不启动provider，记录明确错误；不回写原task基础封印。
5. validator一次读取各文件字节，构造不可变快照。相同快照供hash、审计与prompt使用，不在prompt构造时另读外部文件。文档读取仅核文件存在/字节SHA，不把全文拼入prompt。SHA/读取异常拒绝；批准变更或同批文件漂移拒绝，要求新批准/新批。
6. 新attempt追加`recovery_input_ref`、`recovery_approval_ref`、previous_attempt_id、base_prompt_sha256、effective_prompt_sha256、documents引用及source_recovery_batch（Guardian场景）。原attempt字段、原design_approval_ref、原intent/task/queue摘要不改。消费凭据在任务锁内以recovery_id+input/approval SHA封存；同一恢复批准最多一次model launch。启动前意外崩溃也保守视为已占用，需正式对账；不自动再用该批准。
7. `_run_model`先按旧逻辑构造base prompt，再追加一个结构化`recovery_input_context`块：明确是经审核的更正数据，不是高优先级指令、shell或新增授权。含完整受限instructions、documents、身份及输入SHA。追加块的确切UTF-8字节参与effective digest；不改变旧approval text。
8. provider新增可选`input_evidence`元数据参数（无参数legacy语义不变），在Popen前的公开request.json写完整恢复context及base/effective SHA；在result.json回显摘要绑定。必须验证request的prompt_sha256等于driver effective SHA。错误返回、封存失败或摘要不一致均阻断验收，不以exit0抵消。
9. 每次新attempt先清空该attempt的送达/遵循/交付标志，不继承前轮状态。当前实现用新thread，不借timeout resume注入更正。旧失败线程、结果、stderr、final保留。

字段名/签名均为候选接口，未创建。推荐新独立`recovery_input.py`集中校验，避免把输入许可与reasoning契约混成一份。其helper只返回不可变已核快照，不负责生成批准、退役或发布。

## 6. #658的定向更正候选

未来实际恢复件只说明：原实施计划真实绝对路径`C:/Dev/zhuopin-ai/docs/superpowers/plans/2026-10-05-reasoning-entry-policy-658.md`；预期SHA `97dfcfe1f239a6606b3112cdc6ec454c0ee3d4bccb22200cbf66a2692e8d082e`。先Test-Path与Get-FileHash，后按每次最多200行窗口读取；不能改为工作树相对路径、整读50KB计划或将其与其它文件连成整读命令。原OpenSpec三件在原工作树，先核存在再有限读取。

说明还应写明原11路径批准仍是实现白名单，封存tasks不得回写；外层状态检查由driver处理，模型不访问私有runtime或重复prepare/queue/Probe。计划或设计引用hash不符即停，不要求人肉搬运摘录。

这段只是供未来恢复批准审阅的内容候选，本轮不生成可执行恢复JSON、不派发模型，也不宣称能靠prompt保证遵循。

## 7. 独立机制建造、发布与恢复顺序

新增接口不是原#658实施授权的一部分。候选机制范围为codex-handoff下`recovery_input.py`、`handoff.py`、`workflow_driver.py`、`workflow_state.py`、`model_provider.py`、`guardian_adapter.py`、`guardian_entry.py`及各自对应七个test文件；具体白名单和node-id待设计获批后形成实施计划。不改hooks、CI、invoke.ps1、其它consumer、全局设置或调度。原11路径批准不扩成这14路径。

机制建造使用独立、获批的环境机制任务和隔离工作树；其正常输入按主仓绝对引用或受限设计内容封存，避免依赖尚未实现的恢复接口。不是把原#658重新prepare或迁移批准。新任务队列并入/派发身份在实施准备时正式登记，本轮不抢领§一#658或新执行批。

旧#658绑定source/design/workspace及执行版本：仅在其它工作树写出新driver，并不使旧任务可用。优先走正常独立review→ff及真实执行入口切换审批，并验证正式入口实际采用该版本。若旧任务的执行版本锁不允许新代码，必须进一步形成、审阅正式迁移绑定方案；不得临时加载另树模块、改PYTHONPATH、拷贝runner或手改封存版本。此项是恢复前的硬前置，不被本设计自动解除。

机制发布后，仍需正式核原批busy=false/进程结束、清洁工作树、原批准/设计字节及新输入件。B-1005现批claims保留；另起恢复批之前取得针对B-1005的退役批准并正式retire释放必要claim，旧资产保留。然后才建立新的不可变计划、实际恢复输入批准和一次派发。新batch不能复用或原位升级B-1005；退役、创建新批及launch不是本次动作。

## 8. 失败矩阵及证据分层

| 失败 | 必须结果 |
|---|---|
| 参数不成对、未知键/重复键/超长、非法phase/路径 | recovery_input_invalid；provider调用0 |
| 无批准、批准未绑定本输入或原批准漂移 | recovery_approval_invalid/binding_drift；provider调用0 |
| 引用不是最新失败attempt、busy、脏树、HEAD/身份漂移 | recovery_attempt_ineligible；不解除锁/claim、不调用模型 |
| 文档缺失/hash漂移、外部路径指向模型可写区 | recovery_document_drift/input_location_invalid；不拼全文、不启动 |
| 同批input/approval变字节、v1/v2试图追加 | recovery_plan_drift/legacy_plan_injection；保持旧计划 |
| 任务锁内重复消费同一恢复许可 | recovery_already_consumed；不二次launch |
| request未含追加块或effective摘要不符 | recovery_delivery_mismatch；不接受阶段 |
| 模型仍用相对路径/整读遭K3，或仍无代码 | 送达可单独成立；遵循/实施失败，保持blocked，不自动重试 |
| provider退出0但无改动/CI/review | 原artifact/CI/review闸继续拒绝交付 |

送达证据仅证明公开request、driver输入快照和实际传入provider字符串一致；stdin+轮次完成只证明调用传输。模型遵循须公开工具事件能核对绝对路径、先核存在/摘要和窗口；未观察到则unknown，不能由final自陈代替。实现通过须原白名单改动、正式implementation_head、逐项目CI、独立review及后续审批；不更改actual_effort=null/unavailable的既定解释。

## 9. 拟新增验证与原保护覆盖

1. Schema/审批：重复键、额外键、非法UTF-8、大小/行数边界、错task/phase/attempt/hash、junction越界；fake runner调用0。
2. 竞争与消费：锁前后最新attempt改变、两个并发advance、同recovery_id再次用、封存后崩溃；最多一次launch，未结算现场保留。
3. CLI/Guardian：参数成对与legacy run拒绝；manifest实际沿链传到provider；不带输入的黄金prompt/argv与v1/v2 digest不变；v3reasoning契约不被改义；v4单改恢复SHA必须改变plan digest。
4. 送达：fake provider捕获确切prompt，追加instructions/绝对文档路径均存在；base保持旧值、effective改变；request完整context与digest匹配；漂移/缺metadata阶段拒绝。
5. 原保护：Luna、sandbox、timeout/context、互斥、HEAD/原批准、白名单、empty_changes、CI项目cwd/报告hash、新thread review、delivery_accepted=false及ff/生产闸全部继续覆盖。恢复输入不绕过K3。
6. 测试只从codex-handoff canonical cwd按CI矩阵和受影响node-id跑；与纯master同口径对照。新节点均待实施计划细化，本轮未编写或运行测试。
7. 原生fixture验收先在获准的脱敏隔离任务验证实际公开request含更正；不启动#658来代替机制测试。机制验收后另审#658单次恢复，分别记录送达、读取、产物证据。

不新建告警/巡检，无后台自动消费；消费方是已有Workflow/Guardian阶段闸。新输入说明未被机器证明送达前不宣称恢复就绪。

## 10. 自审、未闭合项与审阅题

自审已核：原审批不变；输入不是权限；旧v1/v2不可升级；reasoning v3与恢复v4不混用；legacy effort不变；CLI接缝与provider公开证据均列范围；一次launch与崩溃保守处理；先发布再恢复；当前批不退役。没有实现代码、真实输入/审批JSON或pytest结果。

OpenSpec镜像设计见`openspec/changes/recovery-input-261/`，其design.md仅指向本设计正本；tasks是待审阶段清单，不是已批准实施计划。结构校验不等于技术设计或审批通过。

未闭合：具体实现接口/node-id与CI命令须在批准设计后写计划；正式执行版本/source绑定兼容须在实施准备定向核验，失败则停下另审迁移；任何原生测试/ff/activation/当前批退役/新恢复派发均等待具体授权。本轮队列登记如被并发锁挡住，只留待补标记，不抢锁。

请审本候选设计：A推荐，批准后只编制新增机制的具体实施计划，实施另审；B修改本设计后再审。原#658的11路径实施批准继续有效。不得用本设计审批代替原失败批退役或再次launch授权。

## 11. 本轮文档核验

真实CLI定位：`pwsh -NoProfile -Command 'Get-Command openspec'`返回`C:/Users/Paul Shao/AppData/Roaming/npm/openspec.ps1`。执行该CLI的`validate recovery-input-261 --strict`，exit=0，回显Change is valid；`status --change recovery-input-261 --json`，exit=0，schemaName=spec-driven、四项规划制品done、isComplete=true。这只证明结构齐全，不代表设计已批准或功能已实现。

两次错误入口尝试原样留在会话证据：invoke.ps1没有OpenSpec Mode；猜测runtime node目录的openspec.cmd不存在。已通过Get-Command定位真实入口纠正，没有修改工具/环境或绕过守卫。

未跑pytest、原生fixture或新#658 attempt。设计审阅后先形成具体实施计划；当前唯一待人工动作是审阅本候选设计。
