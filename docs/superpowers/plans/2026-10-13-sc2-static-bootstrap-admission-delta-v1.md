# SC2优先静态收口与四件接纳差量 v1

状态：§四309待批准。307的1A/2A/3B与308的1A继续有效；不重新审批SC2业务目标、口径或原12路径。

## 1 唯一阻塞与已核证据

原机制attempt `2e25a7fe954d4aeb882032b36599a197` 和kernel attempt `1d00135d6d814cbcb91b9618353ea4b7` 均已context-stopped，正式入口只取得D3_only，仍保留busy/锁。旧生产者只生成内存seal，没有持久seal及完整逐PID创建/终态证明；当前PID不存在不能补造历史证据。kernel本身又被busy挡住正式commit/CI/review，不能未审自清锁。

kernel全11路径保全，7处dirty；HEAD仍为design `e503aa805bce6f7952d23457c4b0f02f45f263e0`。完整13源测试模块的隔离诊断为551 passed、2 failed、4 skipped，前后11路径哈希不变。失败为缺`guardian_entry.reconcile_item`、CLI夹具断言结构不匹配；独立Luna只读审查changes_required，端到端正例未闭合。这不是正式验收。

SC2原task `sc2-three-metric-cold-1013v5` 已重核busy=false，原proposal失败与四件仍保留。因此SC2需要的是可信四件接纳组件，不必等待上述两次历史终止结算。

证据：`reports/pc-mvp-correction-1013/kernel-stopped-preservation.json`、`kernel-stopped-diagnostic-result.json`、`kernel-stopped-independent-review.json`、`three-task-current-stop-check.json`。原308设计SHA `7e1cbed15efe9033040a72bf3e96d92b94ea2c2515a84579384a6bfee59b3c9a`不改。

## 2 一次批准的精确差量

仅复用既有kernel task/树/branch和原SC2 task/树；不创建第三恢复task、第三SC2树、新工具层或并行实现。当前唯一会话为静态补丁负责人，在kernel既有11机制/测试路径内直接收口已保全代码，正常hooks、编辑锁、路径白名单与审计仍执行。原两次停止attempt的state、busy、锁、claim保持原样，不调用它们的恢复/结算/清锁，不将其标成成功。

新增一次**受控bootstrap静态接纳**权限：原task busy未结算时，可在不改变其状态/锁、不启动该task模型的前提下，完成静态补丁、隔离完整测试、独立Luna审查、受控outer commit和绑定commit的完整CI/独审。只生成真实的bootstrap组件验收记录；不得伪装成原Workflow阶段已通过或release-ready。仅经该流程验收的候选可供下项使用；不ff、激活主仓或修改全局消费者/保护阈值。

kernel作用范围新增且仅新增**原SC2非busy失败proposal的四件接纳**：复用307已批的保全、源/审批/原生证据重核、独立只读Luna、OpenSpec strict、受控四件commit/seal、机械绑定原12路径实施授权。每一步留真实独立收据，原失败不覆盖；有原批次时只按其精确收据追加对账并显式续行，不放宽通用blocked-batch。不处理Q2/Q9/FI14等其他业务task。

新增外部记录仅在308既有approval目录、kernel/SC2各自正式runtime的bootstrap/接纳记录及ignored报告内；不直接编辑旧任务status。SC2正常实现、必要定向测试/回归、独审和缺陷修复继续沿用307及原12路径授权。该差量改变的是bootstrap接纳路径与kernel的SC2作用范围，推荐项不代表已获批准。

## 3 门禁与停止条件

全11路径manifest含现存/缺失/dirty/hash，绑定同仓/common-dir、冻结design、原批准、实际代码commit、CI cwd/argv/JUnit/原文hash及独立审查。诊断命令以项目根下全部`tests/`源模块为集合；保留首次非测试缓存收集WinError5，不读/改其ACL，不清理旧报告。正式bootstrap CI亦须证明完整覆盖，不以命令退出码代替验收。

SC2接纳前重核原source HEAD `b2933132b733756b30b94e309e2066bbd50d6e43`、源行、旧attempt、四件原批准SHA、dirty范围、原生工具失败与当前busy=false；不得盲重跑proposal、改四件字节或用caller JSON当可信证据。unknown/pending继续明确展示。

旧终止证据不足保持未知，不回填历史seal、不改默认timeout/D3/Guardian保护，不新增日志采集/进程观察工具。任一步关键证明不足或独审不通过，保全并停止该依赖，集中报告具体缺口；不串接下一恢复任务。

## 4 交付与批准选项

唯一业务首交付仍为SC2三指标MOCK页面/API/来源明细/审计及同一快照标识；有效数值、unknown、pending分别显示。复用PRD/UI及已有代码，不重写设计。BizType316与历史对账独立。临时本地127.0.0.1:8096演示仍走307正常MOCK门禁；真实数据、生产、凭据、权限、付款、外发另闸。

首个MOCK目标为安全接纳门禁通过后一个连续执行工作日；这是工程估计，无可靠绝对演示时刻或上线承诺。两个旧机制停止记录不计业务完成。

1A（推荐）：批准本v1第2–4节，复用同kernel/同树/11路径的静态bootstrap收口与受控组件接纳，作用仅新增原SC2非busy四件接纳；旧停止state/锁保留，原307/308其余授权沿用。影响：解除SC2对当前不能合法恢复的旧停点的依赖，不降低终止证明要求。

1B：不批准该例外；保持全部产物和锁，SC2三指标正式接纳仍受阻，已有316合成回放保持可用。影响：不能仅凭当前批准安全启动下一实现。
