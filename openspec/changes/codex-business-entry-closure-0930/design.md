# Codex业务Workflow六入口收口设计

## Context

承接已批准workflow-mvp-closure-0930（design SHA aff3d46185fe1f428b3b89611972e97479f5edd80575b7aadd664cda67bb447a），不改其批准原件。旧v5 design SHA bd1b310f03c5b52c64f9ee2980ed9f19fa77e5987c8557e6df877d2a9b5e9d61。当前四文件自举正在补齐超时终止确认并验证；旧v5工作树和attempt全部保留。

## Goals / Non-Goals

六入口全部提供Codex可执行路径及分层验收。单任务绿不能冒称整套绿。先完成可逆本地工作；ff、生产消费者启用/新调度启用、真实外发和.51部署分别以实际对象放行。本包没有新的后台构建轮询，也不恢复Claude执行。

## Decisions

### D1 精确入口文件范围

允许变更：
1. .agents/skills/zhuopin-lane-watch/SKILL.md
2. .agents/skills/weekly-status-update/SKILL.md（新建）
3. .agents/skills/zhuopin-lan-closeout/SKILL.md
4. .agents/skills/zhuopin-send-followup/SKILL.md
5. 0-学习与工具/codex-handoff/README.md

本包proposal/design/spec/tasks/acceptance材料可随验收更新，已批准design本身不静默改版。原四文件自举属于此前授权，未扩大到其它生产模块。源技能正文、通用规则和OEM业务口径不改；入口只映射当前工具及引用正本。

### D2 开启与查看泳道

开启口令沿候选已有Guardian流程：实时队列、LAN分类、看护件与锁登记、绑定task与worktree、start审计划、同manifest --run，在当前会话推进到批准停点或release-ready。中断/忙锁先正式observe/recover，不删锁、不切无头、不伪称后台自动续跑。

查看口令是只读：先调用现有泳道状态机show --json（无需指定lane），从输出关联批次；逐批Guardian observe，再按返回的task_id调用Workflow status补实际phase、最新attempt、busy、线程/证据引用。运行中没有原生thread_id时明确尚未形成，不猜百分比。每条区分批次状态与任务现时状态；空、损坏、未知绑定和不可读分别报告。不直接遍历私有state目录，也不把查询当启动/恢复许可。

### D3 最终候选的唯一有效证据链

先把已批准自举和本包入口文档测试/review完并形成可追溯commit。然后以该基线创建独立linked target和承接workflow任务 workflow-path-guard-v5-mvp-0930，仍承接实时开放#648，不双跑旧v5。

新intent明确：只在proposal阶段原字节复制旧v5包到本task同名目录，不重新发挥设计；当前任务身份以外层绑定为准，旧包内v5称谓仅作设计来源。严格验证后核新proposal/design/tasks及spec哈希与源相同，尤其design必须仍为bd1b310f03c5b52c64f9ee2980ed9f19fa77e5987c8557e6df877d2a9b5e9d61。任何内容差异不续跑。

批准本包即覆盖这个确定的承接intent/分类，以及在原设计字节不变、真实proposal回执和新HEAD被外层核实后，形成新的task/design_head绑定并实施原两文件scope。批准原文与本包hash进入外部新授权证据；不重用旧task批准文件，不预批不同设计。新任务从Guardian启动，设计停点后按同一批准条件恢复，再CI、不同thread的只读review和release-prep。最终全部报告绑定该target真实HEAD；同阶段修复原因后最多两次有界重试。

### D4 真实回件的隔离验收

复用实际followup_readme_bridge、patrol_dispatch、provider、watcher及队列工具；不再由假进程代写结果。独立可信linked worktree放合成人员、信件README、脱敏docx和两份最小合法队列；临时consumer仅在该fixture启用，model=gpt-6-luna。生产配置保持不变。

验收单独进程显式设置 WECOM_AIBOT_REPO_ROOT、WECOM_AIBOT_QUEUE_PATH、ZHUOPIN_CODEX_RUNTIME、ZHUOPIN_CODEX_STATE为fixture绝对路径；queue锚点不得经git-common-dir落回主仓。真实拆件章程只在临时副本替换硬编码项目根，记录源/派生hash及单行diff。先验证sandbox主仓写入拒绝与实际hooks，再运行脱敏回灌。所有信号/锁/失败记录/日志/provider证据都落fixture，超时保留现场。

验收要求实际归档/README变更、真实Codex线程/工具/hooks、拆件新增队列行、原生专用查询、重复输入抑制和失败信号保留。入队后按人守规则读取该行并生成manifest，Guardian须接纳候选；回件自动入队不自动代用户启动业务构建。fixture/harness放临时证据目录，不新增生产代码或真实外发。正式provider内部读取自身审计属正常接口；仍禁止agent直接读真实项目私有state。

### D5 值周计划与既有调度

新skill引用现有weekly-status-update章程，映射到Codex工具：专用队列审计/逐行查询、实际计划文件、锁登记、写后反查。保留周一10:00、计划≤10000B、四节和决策规则；不得执行旧会话API或用旧计划日期冒充当前。手动口令生成一份当前计划并验证。

复用已有自动化zhuopinai（zhuopinAI · 周报接力），不创建重复调度。准备的执行提示为：在C:/Dev/zhuopin-ai，按.agents/skills/weekly-status-update/SKILL.md执行值周计划，先以正式审计工具核现时队列，生成本周计划并按锁和登记流程留档；返回计划指针与需决策项；不得启动业务构建、ff、部署、L2签署或真实发送。建议模型gpt-6-luna，保留原周期/项目绑定。先保持PAUSED；手动验收和主仓交付后将完整更新与启用动作放入最后集中放行清单。其它四项自动化不批量启用，尤其不让巡检与事件消费者双跑。

### D6 回LAN和跟进信边界

Codex技能明确旧PowerShell/MCP/CC接口的当前工具映射，查询队列只走专用工具；源规程中的禁止动作和业务判据原样保留。回LAN先实际探针，off/unknown留步且不连接生产；on仍按具体项目授权、.51单项串行快照→执行→冒烟→回写，失败回滚停链。仅接口/拒绝/转出通过不标实际部署完成。跟进信草稿与回件可在脱敏fixture验证，真实发送另有明确对象和批准；不从这次迁移请求推导外发许可。

### D7 最后集中放行

本包只批准入口实现与可逆验收及D3确定条件下的承接绑定。待实际CI/review、patch-id与发布请求齐全，再一次列：具体ff分支/HEAD、主仓patrol从false到true并指定Luna的配置差异与待消费信号范围、既有周报自动化完整更新。实际.51和真实外发只在对象/动作明确时单列；不预签未知操作。若新实测要求其它生产代码变更，先给具体缺陷和最小diff补审，不扩散建设。

## Risks / Trade-offs

- 旧证据错配新版本：每条保留task/HEAD/哈希，最终候选重跑必要链。
- 临时队列落回主仓：双queue环境覆盖、绝对根派生、前后主仓对照与sandbox证据，任何偏移停止。
- 模型误读旧proposal-only/任务名：新intent/已核授权正文明确阶段和来源，design原字节不变才允许承接。
- 只读查询误触发构建：单独技能场景验证工具序列不得含start --run/resume/写状态。
- 原生联验发现新缺陷：先保留失败，不修改封存状态，不把测试替身换回来冒充通过。

## Migration Plan

完成当前P1和完整回归/独立review→本包获批后入口skills场景测试与修改→原生回灌隔离联验、当前值周计划→最终基线commit→承接Guardian原生链/查看口令联验→生成实际集中放行包→获准后交付主仓/运行开关并核验。回退为停止新消费保留信号/证据，旧现场保留；不删除旧worktree、不启动Claude。
## 参考ClaudetoCodex skill的取舍（2026-09-30）

参考件：Shao Peishen提供的Mac项目claude-to-codex SKILL.md。它是外部经验资料，不替代本项目批准与规则。

采用：执行器/调度器/服务/hooks/技能/提交通道逐调用点盘点；业务往返通道不变；先真实最小调用再联验；实际PID/终止证据判断进程；模型写产物、外层有批准才提交收口；调度器实际PATH与退出码实测；未知成本/计量留未知；运行中的执行器源码冻结；规则和缺口当次落档。

不采用：双引擎切回Claude（本项目已明确封存）；dangerously-bypass-hook-trust或任何绕sandbox/trust参数；把PARTIAL/OPENER_DONE当交付；无人批准自动merge/push；Mac pgrep/Seatbelt/launchd结论直接套Windows；该Mac版本的旗标、DeepSeek路由或上下文峰值口径直接移植。正常项目/hooks信任和现有原生证据契约不变。

据此缩短实施：不新增观察状态API，不新建调度器，不改现有生产dispatcher；只补5个入口说明、用真实现有通道跑验收。若某通道原生实测暴露必修缺陷，只修该调用点并保留反例；不以迁移为由扩建通用框架。
模型执行说明：当前子代理全部使用gpt-6-luna；直接Workflow advance和隔离回件dispatcher显式指定Luna。现有Guardian入口暂未暴露model参数，会继承本机当前gpt-6-astra/medium；为避免扩大本轮代码范围，其必须的原生链调用记录实际model并提前说明，不静默切换、不改全局模型配置。此项是尽量采用Luna偏好的明确例外，不新增Guardian模型路由工程。
