# PC端MVP提案恢复与财务首批准备 · v2

> 执行者使用executing-plans与zhuopin-lane-watch正式Guardian，所有派生模型显式gpt-6-luna。本计划仅离线意图/提案，不包含产品实现或测试。

**目标**：修复已经取证的输入可读性阻碍，保全SC2现有四件，恢复四条原离线提案，并为FI14/FI5首批各产实际design供审。

**架构**：父会话先把已核技术材料制成带原路径与SHA的只读包；正式工作树在忽略的reports目录接收同字节副本。分两组三泳道，组内独立、90秒错峰；第一组终态后即开第二组，不等待第一组专业/实际设计审批，任何时刻最多4个活模型进程。

**来源**：已批PC端推进计划v1；现有PRD；SC2修订草案；新FI14 intent及FI5兼容意图。专业开放点继续留在业务信/真实判例，不能以本计划签认。

## 1 现时证据与必须新增批准的原因

本次B-1012_PC端MVP提案重派已四条终态：SC2 paused/design review required；Q2/Q9/QD-A blocked/OpenSpec files missing。公开planned receipt按现有guardian_adapter._plan_sha256计算v2指纹为`8cd43e9329db7d244dd2544fde6ba5fac0f583641d983364848e362891602626`，watch SHA`647fcb0c1cb3fddf3d97884368153fa0804e245c61f47bdd05f6936cacdd8ba6`。执行前重新绑定真实plan与当前busy，任何漂移停该动作。

按官方task/attempt及provider固定证据命名只读定位三份result.json，核source_id/attempt/workspace/requested_model/actual_model均绑定Luna，再按thread_id用native read_thread取最终答复。没有遍历私有state或读原会话凭据。失败原因：Q2主仓Test-Path读前被hook拒绝；QD-A单独哈希核验被拒绝；Q9原参考路径未知、定位命令被拒绝。不是专业材料未签导致无法写任何技术方案。

原1A只批退役四个B-1003旧批，未批本B-1012新批退役；当前入口不能仅退役三失败lane，也没有受支持的design amend。整体retire会释放SC2暂停claim，但保留工作树/四件/attempt/历史；本计划不宣称继续保有旧SC2 claim。

## 2 需要批准的确切外部范围

1. 仅在`C:/Dev/Codex/runtimes/zhuopin-ai/approvals/1012-pc-mvp-v2/`写绑定本人答复、计划及输入哈希的retire/intent/LAN证据；正式Guardian/Workflow共享runtime写本次状态和日志。
2. 用正式retire整体退役上述B-1012未完成claim；禁止删除或篡改四个现有树、原attempt、SC2 design HEAD `23d9e97e462c8cbc5feb5c73c0eff510a6e0c4d7`/SHA`2d09c3a0ef4b2ad060bf32da7abeb4278cf1495f3fbaeddb26d61a49955576e2`与所有历史。
3. 原生创建六个新隔离树，仅`C:/Users/Paul Shao/.codex/worktrees/pc-mvp-1012-v2-<sc2|fi14|fi5|q2|q9|qda>/zhuopin-ai`；其中只读输入副本限`reports/pc-mvp-input/`，父会话核原/副本SHA相同且git clean/source HEAD后才prepare/start。既有docs/intent如尚未落库，先完成既有sweep再固定source HEAD；不跳过clean检查。
4. 确认本计划所引用FI14 intent的PC只读范围，以及FI5兼容意图范围；只有明确确认后FI14 status才写已确认。两份不是专业口径签认或design批准。

## 3 六项队列与触碰区

| 组 | 任务/原行 | 只出提案的目标目录 | 必备输入与停点 |
|---|---|---|---|
| PC首批 | sc2-three-metric-evidence-1012v2 / #654 | openspec/changes/sc2-three-metric-evidence-1012v2/ | 现有intent、23/24拆件、原四件和docs/superpowers/specs/2026-10-12-sc2-three-metric-evidence-revision.md；修订三项，不改G01–G04；新实际design单独审 |
| PC首批 | fi14-payment-plan-pc-mvp-1012v2 / #678 | openspec/changes/fi14-payment-plan-pc-mvp-1012v2/ | 新FI14 intent、PRD v0.3/C1及脱敏样本资产清点；只读账龄/草稿/人工/审计，未签处显式 |
| PC首批 | fi5-wecom-pc-review-alignment-1012v2 / #470 | openspec/changes/fi5-wecom-pc-review-alignment-1012v2/ | FI5兼容意图、旧intent/design/tasks、PRD v0.3、成果包清点/v3条目；旧包不覆盖，企微/预算来源未就绪不编造 |
| 质量独立 | q2-semantic-offline-source-1012v2 / #652 | openspec/changes/q2-semantic-offline-source-1012v2/ | Q2移交/准备输入、既有intent/design/tasks；线上PendingSemantic与专业校准闸保留，不重做门户 |
| 质量独立 | q9-apqp-evidence-pilot-1012v2 / #653 | openspec/changes/q9-apqp-evidence-pilot-1012v2/ | Q9已确认intent、已批准备计划、八mock案例、移交单；原旧三件只在可读时辅助复用，未知旧位置不作为停笔前置。旧文件不删，不假装已完整取件，全部专业G01–G06 PENDING |
| 质量独立 | qda-seven-step-extraction-1012v2 / #656 | openspec/changes/qda-seven-step-extraction-1012v2/ | QD-A移交、实际doc_reader/既有Q2映射的单文件只读来源；只设计显式七步raw extraction与兼容，不改专业映射/阈值 |

主仓新意图/修订文件与只读输入包是准备载体；新派生模型仅写各自上表目录内proposal.md、design.md、tasks.md及specs/<capability>/spec.md（可按strict需要附.openspec.yaml）。不改场景源码、生产、旧快照、专业正本或共享平台。新FI14 intent已确认后须随source HEAD进入树；FI5深化沿独立兼容意图，不重复grill旧已确认点。

## 4 按序执行步骤

1. **输入核验**：父会话逐件直接读已存在的必要来源，保存原路径/内容SHA/角色/签认边界。真实OEM/凭据不进包；专业附件只存已脱敏或规则摘要，不执行附件代码/SQL。单独Get-Content可读输入已预核，模型不再漫游寻址、组合哈希命令或查询队列。必备输入不可读则停该任务，保留证据。
2. **保全后retire**：正式observe/status确认四busy=false/attempt终态/对应plan无漂移；外部retire证据绑定本计划批准原话。整体retire回执只报实际释放和保留，不删任何旧资产。
3. **队列与source准备**：持锁更新六原行的next_action/触碰区及新绑定，登记全部精确文件；特别四旧冻结源行只在retire成功后修改。FI14 intent明确确认后更新status并走sweep，不靠父会话手工commit混入旧脏文件。
4. **正式规划与派发**：六新task_id逐项Workflow prepare；官方opener生成/lint、manifest/LAN分类、同仓linked树/clean/HEAD、Guardian DryRun全过后才run。先PC三项，再质量三项；每次0或output_needs_review均只标阶段完成，四件和strict/设计HEAD/模型实际型号回执齐才称提案成件。
5. **审查**：逐件独立只读review，必要修订形成具体供审稿；实际design按确切HEAD/SHA请求。未批实施不运行产品测试；ff、生产、真实取数、付款、外发均逐项另审。

## 5 Review Focus与验收证据

1. 来源同字节可读、旧路径不存在/守卫拒绝与缺材料不同，父/子不得把失败判成文件不存在。
2. SC2公式仅已签字段可计算；未知/PENDING/零分开，版本快照/audit/日历具体且旧金样不动。
3. FI14资金/排序/账龄未知显示缺口，不能输出可执行支付；FI5 OCR与验真、预算提示与最终审批分开，旧包自陈不当验收。
4. Q2/Q9/QD-A保留专业PENDING、OEM分区和ASIL/L2边界；技术四件不被缺专业签认整体卡住，真实数据不得进提案。
5. 输出必须是本task_id下四件且外层strict通过；不把正文答复/进程0/提案完整当实际design已批或产品交付。

完成口径：两封信已发、输入核验和新批仅按实际证据报告。旧计划v1及本计划一经绑定批准不原位改SHA；新偏差另件记录。尚未批准本计划，不写外部v2证据、不retire本B-1012、不建立新外部树、不派模型。
