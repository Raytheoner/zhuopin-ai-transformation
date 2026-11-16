## Context

见proposal.md。原watch-context纯读取，原§二已有PREREGISTERED_STATUS_PREFIX；问题在消费交接与调用状态，不再造任务表/调度器/模型执行器。本次三点限定设计由本人本轮明确指令确定，串行执行。

## Goals / Non-Goals

只修前台持续消费、写前原行/§二绑定和隔离验收；不接管KH2/#563/#636候选或#670。不更改旧headless封存、生产、提交、审批、专业签认合同。

## Decisions

1. 读取器保留permissions_granted=[]和execution_ready=false，但返回明确consumer_action=verify_existing_scope_then_claim_and_build；原UserPromptSubmit仅对精确“开启泳道看护”注入执行衔接，不触发其他prompt、不调用模型/进程。泳道skill明确本轮不能以取证完成为收口依据。
2. 原workflow_driver增加claim_native_slice(root, plan, execute)：复用原共享锁（调用者先acquire）、原查询与append/edit-row。plan是前台从原批准形成的临时实施参数，不是新批准，含row/who/batch/queue_sha256/approval_scope/approval_refs/allowed_paths/active_writers。严格根相对路径、SHA、原行状态、当前写方与触碰重叠核验后，先§二既有预登记状态并回读，再将原行唯一写方、原批准指针和精确物理路径落下并回读。未成功不交实施；不建占位业务文件。handoff.py增加claim-slice薄CLI，参数仍由Agent从原件生成，用户不填表。
3. 原driver增加consume_native_watch(root, resolve_scope, perform_slice, execute)：仅同进程前台调用链，不派发/启后台；当前会话是实施者，测试以受控回调替代Agent。每项前/每次留步前重新取池，忽略装载器execution_ready=false这一非授权字段，仍核实际原批准/冻结/写方。单项失败记录结果后继续独立项；原合法claim回执验证后才调用实施回调。回调必须保持原锁流程，原候选/检查点经原行回写且不以该回调自动销母项。
4. 预登记只使用原状态，不改普通落库路径/Git/凭据/列结构/锁校验；收工仍精确化为实际可审阅证据。预登记既有豁免不是允许任意路径：新claim入口对新scope另做严格路径检查，拒绝绝对/越界/通配/目录/符号链及凭据形态，原普通入口保持原强度。
5. 用真实临时Git/队列和原工具建立fixture，模拟仅限本机前台Agent实施回调及旧批准的测试来源。实际创建候选、运行pytest并回写原行；真实时间线来自KH2只读记录。结论只为隔离mock，不称自然语言自然实跑已通过。

## Risks / Trade-offs

- 机器不能判断业务批准语义 → 原批准由当前执行会话从原件核实，参数只绑定原引用/hash和物理路径，不授新权。
- 原行或引用漂移 → 按当前SHA拒绝，不写目标；当前写方不确定即留该项，不接管。
- 全局锁释放失败 → 不进入实施回调，保留原锁证据，不清锁。
- 单项候选未满足完整验收 → 只写候选检查点/原下一动作，归档仍走原check-acceptance与完整项目闸。

## Migration Plan

只有本线已登记范围内源文件变更；旧调用与只读list形态保持。新短口令消息只作用于后续对应请求；当前KH2运行不被强制换合同。不启停任何消费者。回退保留本批前SHA与差量，不清其他现场。
