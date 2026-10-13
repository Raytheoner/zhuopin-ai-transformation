# PC-MVP机制自举安全接续差量 v1

状态：§四308待批准；307的1A/2A/3B继续有效。本件只补新增机制身份及干净树，不重做SC2业务设计。

## 1 实测阻塞与新增范围理由

307的唯一机制task `pc-mvp-finite-recovery-1013` 在实现attempt `2e25a7fe954d4aeb882032b36599a197` 被原保护以 `soft_grace_expired` 停止。Guardian记录blocked，Workflow busy=true；正式recover仍blocked_unknown。已保全11路径与固定证据，诊断CI 558 passed/5 failed/4 skipped；其中一个WinError5节点新UUID定向复核1 passed，其余四项仍失败。独立Luna只读审查确认proposal正式接纳、可信终止验证与Guardian对账尚未闭合。该候选不得清自己的锁。

原307限定一个机制task/树。需要一个独立、干净、先CI/独审的自举切片才能安全恢复它，因此新增下述身份超出原限定。自动审批已拒绝未结算时的Guardian recover；本计划不重复该操作，不直接写state/锁，也不使用未审候选自举。

## 2 一次批准的精确差量

新增且仅新增机制task `pc-mvp-bootstrap-kernel-1013`、batch `B-1013_机制自举安全接续`、branch `codex/pc-mvp-bootstrap-kernel-1013`，干净机制树 `C:/Users/Paul Shao/.codex/worktrees/pc-mvp-bootstrap-kernel-1013/zhuopin-ai`。先正式prepare封存现取主仓HEAD/common-dir/源行，再按该HEAD创建树。原机制task/树、SC2业务task/树均保留；不另建SC2任务或第三棵SC2树。

产品/测试范围仍是原307的同一11路径：`0-学习与工具/codex-handoff/`下handoff.py、workflow_driver.py、workflow_recovery.py、workflow_state.py、guardian_adapter.py、guardian_entry.py，以及tests/test_workflow_recovery.py、test_workflow_driver.py、test_workflow_state.py、test_guardian_adapter.py、test_guardian_entry.py。新切片只服务**原机制自身**的安全结算、checkpoint、新上下文及原批次对账，不处理四个业务task。

另仅本新task的OpenSpec四件、主仓本补件与状态/锁登记、ignored报告；仓库外仅 `C:/Dev/Codex/runtimes/zhuopin-ai/approvals/1013-pc-mvp-bootstrap-kernel-v1/` 标准intent/LAN/design/recovery证据及新kernel/原机制两task的正式runtime记录。设计四件沿本计划§3合同，outer strict/seal后按本次批准机械绑定；任何实质差异另审。

## 3 必须闭合的执行链与安全合同

1. **只在隔离夹具实现kernel**：正常默认仍fail-closed。原failed文件只作输入；不在CI/独审前调用真实旧task。固定正式CLI新增 `Workflow settle-approved-stop`、`Workflow advance --new-context --recovery-approval` 和 `Guardian reconcile-item --recovery-approval`；参数命名可按现parser合约落定，但不得提供任意state/观察JSON执行接口。
2. **可信settle**：只接受工作树外批准，精确绑定原机制task、attempt、thread `01a13380-f8d4-7790-986e-4564544e1522`、原树、design HEAD `116cd82e6e771e53a361e3e8a845675b2a6bdac8`、307设计/实现批准SHA及原固定证据全哈希。读取固定producer request/process/result/session/events/outer termination seal原件，核对生产者出处/代码及原文/哈希；D3摘要或caller JSON不能代替。原taskkill /T /F stdout列出11个PID，须验证其完整树关系与每个进程终态，区分活进程、PID重用、退出不可证和子树未知；未知保锁，不杀PID、不改ACL。
3. **受控结算与checkpoint**：仅在独立验收后的kernel正式入口，排他锁内重核state/lock/批准/原HEAD/完整11路径dirty哈希；可信结算原running attempt为blocked，追加审计并保留原termination_observation/原件，只释放匹配的运行锁。保存原设计HEAD、全部批准路径现存/缺失/dirty清单和哈希、未完成项及精简下一段输入。checkpoint不是实现交付，不进入release。
4. **原Guardian批次精确对账**：绑定 `B-1013_PC交付有限恢复` 的封存plan、claim、未变源行及新可信结算回执。现记录task为blocked且前台已返回；旧recover只处理遗留running不能替代此步骤。新正式reconcile只允许该task/批次，以追加历史方式恢复为可显式续行的停点，不放宽通用blocked-batch、不删除无匹配证据的锁；按原lane回答/显式resume。
5. **原机制冷接续**：在原task/原树/原307批准11路径下开新Luna上下文。先核完整checkpoint/同一HEAD和原批准；分段只补已有四项功能缺口，不全景盲读、不整读巨大旧测试模块、不重复读取源码；精确函数/新测试node与必要规则一次提供。工具失败不当功能RED，临时文件新UUID，CI在外层。每段保存部分成果；不得隐式续232k旧thread。最终原机制完整CI及独立Luna通过后，才按307正式接纳SC2、原12路径页面/报告和本地MOCK演示；Q2独立。

## 4 统一验收与停止条件

kernel须正式outer commit、handoff子项目完整CI原文/JUnit/hash和独立Luna审查；负例包含全部绑定漂移、caller伪造、seal缺失、父退子未知、PID重用/活进程、重复/并发结算、额外dirty/staged/link、批次/claim漂移和未验证checkpoint。正常调用兼容回归不能靠改期望抹平。缺陷修复仍原11路径。验收通过后仅使用该候选正式入口，不ff或激活主仓运行机制。

新增设计/实现/测试/必要回归/独审/修复/保全及上述两task的有限接续在本差量一次覆盖。两个连续恢复失败停止该依赖留证；生产、真实数据、凭据、权限、付款和外发不变。若固定原始证据不足，保持锁并报告精确缺口，不把人的批准当终止事实。

工程负责人仍为本会话01a131ce-e044-7962-ab76-2d578938aec2，所有派生明确gpt-6-luna。当前无三指标implementation HEAD或可打开服务，不能给可靠绝对演示时间；原目标仍为工程依赖通过后一个连续执行工作日内首个MOCK闭环。

1A（推荐）：批准本v1第2–4节，追加一个kernel机制task/干净树及同11路径、仅新kernel与原机制自身runtime的安全接续。1B：不追加身份，保全现状与锁；SC2三指标正式接纳保持受阻，已有316回放可用。
