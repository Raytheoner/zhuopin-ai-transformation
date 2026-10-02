# 【Codex】超时续跑例外移除设计

## Context

本包仅处理 §一 #648 的已批准 CI/JUnit 范围内 review 修订。原设计 `ci-junit-648/design.md` 要求不修改 release/gate 授权规则、异常超时留证且失败不晋级；上游 `codex-mechanism-migration/intent-deploy-design.md` 要求每阶段证据完整和干净隔离实施。当前 driver 的特殊续跑路径与这两个约束冲突。

外层已核实时队列、intent 和 HEAD。本稿是待外层 strict 与本版设计批准核验的产物，不是授权文件。本模型不得访问 `ZHUOPIN_CODEX_STATE`，故不伪造旧 review 的 thread、报告路径、哈希或结论细节；后续外层应将真实原 review finding 与修订 diff 关联。

## Goals / Non-Goals

目标：删除超时实施续跑例外；恢复正常门禁和干净工作树前置；保留 CI/JUnit 实现；旧 task/attempt/证据不改；新证据链最终仅到 release-prep。

非目标：设计新的 resume/recover 机制、删除未提交工作、修复不相关基线、改 CI 矩阵或阈值、重写状态机、修改 provider 通用能力、替换授权、自动提交/ff/部署/外发或 L2 签署。本模型阶段只写指定目录，不运行 OpenSpec CLI、pytest 或 Probe。

## Decisions

### 1. 选择删除例外，保留原阶段判定

删除 `_timed_out_implementation_thread()`；删除 `advance()` 中该 helper 的调用、例外处理及将 decision 置为 implement/ready 的覆盖语句。超时状态依照既有 `collect_evidence()` 和 `gate.decide_next()` 判定，不能因有 thread ID、结束时间或批准路径内脏文件而额外放行。

保留已批准的 `retry_failed_ci`、`refresh_ci_evidence` 流程，不将本修订泛化为删除全部 decision 更新。它们只按原条件处理 CI 证据，不成为 implement 超时后门。

备选方案是在续跑 helper 再补门禁检查；这仍会保留第二套实施前置和批准范围外的恢复行为，不符合本次明确的删除要求，故不采用。也不整体回滚 CI/JUnit 变更，以免撤销应保留的证据能力。

### 2. 删除专用传参，恢复干净实施入口

从 `_run_model()`、`_implement()`、`run_one_stage()` 及相应调用点删除仅供本例外使用的 `resume_thread` 参数；删除续跑 prompt 和传给 provider 的 `thread` 注入。只删除已经确认无其他调用者的专用代码或 import，不借机重构公共 provider。

`_implement()` 的前置恢复为 HEAD 必须等于批准设计锚且 `_clean(workspace)` 必须为真；不存在续跑豁免。批准快照、不可替换绑定、allowed_paths、原生 tool/hook 证据、外层提交等原流程继续生效。

超时后的工作树保持原样；本包不 reset、stash、删除或改写旧 task。若旧 task 因超时或脏树停住，保持停住；后续由外层在既有授权流程核定恢复/新任务承接，不能用本包文档手工将历史失败改成成功。

### 3. 精确测试边界

删除 `tests/test_workflow_driver.py::test_timed_out_implementation_resumes_same_thread_without_losing_dirty_work`。只移除肯定该例外的专用 fixture/断言，不删除一般超时、失败留证及原门禁测试。

保留 `test_default_pytest_executor_preserves_timeout_bytes`、JUnit 文件所有权与归档、XML 解析/哈希/绑定、CI refresh/retry 与 review 上下文相关用例。`workflow_state.py`、gate/release/E2E 测试及 CI workflow 预期零 diff。

在既有临时仓库和隔离 state fixture 内补最小回归，不访问真实任务状态：

| 输入 | 必须观察的结果 |
|---|---|
| 原续跑 fixture 的终止超时记录、获批范围内脏文件、原 gate 拒绝 | 返回原 gate 的非 ready 判定；模型零调用；不创建新 attempt；脏文件内容与历史记录不变 |
| 同类超时记录但原 gate 为 paused/缺批准 | 不被超时元数据覆盖为 ready，不启动模型 |
| 直接到实施入口但工作树脏，HEAD 和批准匹配 | 实施前置拒绝，模型零调用，未提交文件保留 |
| 干净获批正常实施 | 仍走原新实施路径，不传旧 thread，不因删除例外破坏原成功流程 |

优先复用真实 gate 与现有 fixture；若为证明 decision 不被覆盖而注入固定判定，另保留真实 gate 集成用例，不能只靠 mock 自证。负例应在旧代码暴露续跑行为，修改后拒绝；不更改断言以容忍失败。

### 4. CI/JUnit 保留清单

- 正式 CI argv 保持隔离 Python 的 `-m pytest -q --tb=short --junit-xml=pytest-result.xml`，cwd 为每个受影响矩阵项目；不在根目录混跑。
- JUnit 原始字节、安全归档、所有权检查、stdout/stderr 原文及 SHA256 保持。
- report 的 task/implementation HEAD/attempt/expected_roots/targets 绑定、XML 解析与矛盾检查保持。
- 旧报告显式 refresh、失败 CI 显式 retry、历史 review 留存及新 thread 评审要求保持。
- 不将 pytest timeout 的字节保留逻辑误删为 implement timeout 续跑逻辑。

### 5. 阶段与授权

按 intent 已核 → 本包 proposal/design/tasks → 外层 strict → 本版设计批准核验 → 有界实施 → 逐项目 CI → 独立 review → release-prep 顺序执行；上一阶段证据不足立即停止依赖步骤。结构校验不等于设计批准，旧批准不自动绑定本稿。

后续生产代码范围为 driver 和对应 driver 测试两文件；实际可写集合以外层批准的 allowed_paths 为准。外层沿既有队列/锁工具 acquire→写→登记→release，正常 sandbox/hooks trust 不得绕过。部署程序仅引用 `.agents/skills/zhuopin-lan-closeout/SKILL.md`；本任务不执行部署。

## Risks / Trade-offs

删除例外会使已有超时任务继续阻断，这是恢复 fail-closed 的预期行为；不承诺自动续完旧 task。删除参数可能遗漏调用点，因此源码引用核对与完整受影响子项目测试缺一不可。CI 已通过只是历史背景，新 implementation HEAD 必须重测、重新 review；出现新失败即停，不 skip/xfail、缩窄正式 CI 或下调阈值。

## Validation Strategy

本阶段只做文件结构、范围、内容回读；strict 由外层执行。实施阶段先做定向 RED/GREEN，再依据最终 diff 与 `工具-CI矩阵发现.py` 选择最具体受影响项目全集。预计为 `0-学习与工具/codex-handoff`，若发现其他项目不得漏跑。正式逐项目使用上述精确 CI 命令；隔离解释器由 invoke.ps1 解析，不改变全局 editable 指针。

外层每次记录完整命令、cwd、退出码、HEAD、attempt、stdout/stderr/JUnit/report 路径及 SHA256。独立新 Codex thread review 绑定最终 HEAD、diff、设计批准和新 CI 证据，核本稿删除清单及保留清单。review changes_required 则停，修订后重新验证，不复用旧 approved。

## Migration Plan / Current Stop

无需状态迁移或补造历史报告。当前仅提交供外层审查的文档产物，模型不 git commit。旧 `ci-junit-648` 和其他 change 文件不改。暂不归档：本阶段 strict、设计批准、实施、CI、review、release-prep 均未执行。
