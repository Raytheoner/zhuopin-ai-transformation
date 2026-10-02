# Codex workflow MVP 收口补充设计

## Context

批准基线：v5 task workflow-path-guard-observability-op-0930-x-v5-no-backup；design HEAD f9fffa26472ee1b252888964a695aacb01c94b39；design SHA256 bd1b310f03c5b52c64f9ee2980ed9f19fa77e5987c8557e6df877d2a9b5e9d61。已批准的v5路径诊断仍按原设计实施。本补充解决驱动授权丢失、失败定位及用户要求的Luna路由。原生会话读取证明模型因阶段冲突停在写入前；本机Git复查空diff/HEAD不变仅为后验旁证。

## Goals / Non-Goals

目标：修通当前入口，使已有批准能正确传给执行模型并完成本地任务驱动MVP。验收分三层：基础消费者已有验收；单任务原生链本次补齐；guardian人守启动及停点恢复再联验。不得用基础消费者/模拟测试替代后两层。

不建设新的诊断平台或后台调度，不开启业务消费者。不改主仓、旧任务/intent/封存proposal，不删除旧worktree。ff、.51部署、外发、L2均不执行；Off/unknown LAN只做离线拒绝/转出承接验证。

## Decisions

### D1 有界自举

选择在新隔离worktree workflow-mvp-closure 中修复控制器，定点TDD、子项目回归及独立只读review后用其阶段入口恢复v5。不依赖当前有缺陷的控制器来启动修复它自己的模型。拒绝另起一轮相同proposal试运气，也拒绝手工改state制造通过。

代码允许路径精确为：
- 0-学习与工具/codex-handoff/workflow_driver.py
- 0-学习与工具/codex-handoff/handoff.py
- 0-学习与工具/codex-handoff/tests/test_workflow_driver.py
- 0-学习与工具/codex-handoff/tests/test_handoff.py

自举源HEAD、补丁commit、文件哈希和测试结果单独留证。自举修复与v5原批准实现保持各自证据；若候选源码整合改变待验HEAD，必须对最终候选补充回归和原生闭环，不用旧报告冒充。

### D2 授权正文传递

复用_approval_snapshot验证结果，_implement把完整approved_design_context传入_run_model。实施提示中将历史intent明确标为任务来源；将已验证的当前阶段授权以结构化数据区呈现，逐字保留text与task_id/design_head/design_sha256/allowed_paths/authorization_sha256。明确当前实施允许必要定点测试，既有proposal-only限制仅是先前阶段范围；不能把自由文本任意执行为shell或系统指令。机器准入仍只认原绑定与路径白名单，未知/缺失/漂移不允许模型运行。review原有授权上下文保持原语义。

不修改原intent。v5封存tasks不在实施白名单，实施提示明确禁止勾选/写回。仅路径白名单相同不等于授权范围可扩大；本补充需批准后生效。

### D3 失败证据

路径拒绝仍blocked/delivery_accepted=false。保留已有legacy reason，新增有限path_guard原因区分empty_changes/path_not_approved/path_outside_workspace/not_regular_file/status_command_failed，详细v5诊断继续按其设计实现。失败outcome保留model的thread_id、工具失败计数、状态、phase/attempt及既有证据目录定位；不在status中倾倒prompt全文、原始stderr、凭据或OEM内容。无原生ID明确null，不能伪造。用户可经app-server thread/read取得模型末答；本次不新建私有state直读出口。

### D4 Luna模型单次路由

为Workflow advance新增可选--model，依次传至advance→run_one_stage→_run_model→provider.run(model=...)。不指定时保留既有默认；本次显式gpt-6-luna。只接受单个模型字符串而不拼shell，provider既有argv留存实际选择。明确错误不得静默切换更贵模型；复杂审查必要时先说明升级理由。resume沿既有provider能力，不能为改模型重写原thread或状态。

### D5 连续推进与恢复

用户批准本补充后，一并覆盖四文件自举实现/测试/独立review、已获批准v5的implement→CI→独立review→release-prep，以及修复原因后的同授权有界重试（最多两次同阶段；相同失败不盲重试）。每步检查busy/HEAD/批准/现场，不使用state手术。CI使用受影响codex-handoff子项目规定命令；review使用不同原生thread，只读已登记原始报告。

真实运行失败若需要超出四文件或新语义修复，先形成具体diff/补充设计再集中报批，不擅自拓宽。生成的新设计内容若与已批准设计不同，仍需实际版本审批；本包不预批未知未来设计。原v5失败现场和已封存批准文件保留。

单任务链通过后，按已有guardian协议验证人守启动、阶段推进、设计停点/明确恢复、重复触发不双跑、off/unknown LAN拒绝。不新开后台定时任务。完整workflow MVP必须同时证明单任务链与人守入口接缝；只有前者通过就明确报告前者，不冒称全部通过。

## Risks / Trade-offs

- 后续授权与旧intent冲突：用已核验正文和时序说明，保留机器授权边界；不靠模型猜。
- 自举与最终候选代码不同：记录两者HEAD和哈希，最终候选重新验证相关链。
- Luna速度/能力差异：实际运行和review判定，不以模型名推断成功。
- 通用reason历史模糊：新字段只描述同次观察，旧记录不回填。

## Migration Plan

批准补充设计与计划→四文件TDD自举→独立review→原v5通过阶段接口恢复→CI/review/release-prep→最终候选集成核验→guardian联验→报告具体剩余ff/生产项。回退仅停止本次新控制器调用，保留原代码、状态、证据和工作树，不动已运行服务。

暂不归档：MVP真实验收尚未完成。本包无backup待补项。
