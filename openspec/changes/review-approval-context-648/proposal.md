# 【Codex】review-approval-context-648 Proposal

## Why

源任务：§一 #648；task_id：`review-approval-context-648`；action_key：`worktree_local_build`。

独立 reviewer 当前接收 implementation HEAD、CI 原文引用及原生执行证据，却未收到本任务经批准的设计授权上下文。因此可能重复报告已由 Shao Peishen 针对同一 design_head/design_sha256 明确纠正的 CI 命令勘误。需要把经过确定性核验的最小批准摘要作为审查条件传入，同时保留对无关缺陷的独立判断。

本次按用户明确的 #648 已批准三文件任务续做，当前阶段仅更新 proposal/design/tasks。队列行、intent 批准及 HEAD 已由本次外层驱动核验（本次任务输入）；本模型未独立复核该运行时证据，不读取私有状态、不运行 Probe，也不把 resumption.md 等历史接力当实时证明。更新后的 strict 结果、设计 HEAD 和批准绑定仍由外层核验；本文件不自授设计批准，不将历史两文件批准自动扩展为三文件批准。

## What Changes

- 在实施获准、模型启动前封存仓库外设计批准文件引用及 SHA256；绑定 task_id、design_head、design_sha256 和 allowed_paths。
- review 启动前重新核验引用、原始文件字节、设计和范围，仅把白名单字段构成的批准摘要传入独立只读 reviewer。
- 摘要说明：仅明确获批且与实测证据一致的 CI 勘误可视为已授权条件；继续报告其他缺陷，不能把整类 `CI_TARGET_SCOPE` findings 自动清空。
- 无效、缺失、漂移授权均阻断，不传摘要、不静默降级成“已批准”。review 返回后及驱动内复用 review/release-prep 前再次核验。
- 测试使用临时仓库、临时外部批准文件与 fake model，覆盖有效授权、篡改、错绑、路径越界、恢复及独立审查约束。
- 保留并适配 `tests/test_workflow_release.py` 的 `release_ready` 回归：有效批准可进入既有发布准备，无效或漂移批准不得调用发布准备模块。

## Capabilities

### New Capabilities

无业务规格新增。本变更为现有工作流工具内部的授权上下文传递，使用 `.openspec.yaml` 的 `schema: spec-driven` 与 `skip_specs: true`，不新增 specs 文件。

### Modified Capabilities

无主规格修改；实现约束及可验证行为详见 design.md。

## Impact

后续实施的三文件边界如下；外层须将这份清单与本任务具体版本的已有批准逐项核对，不符即停止：

1. `0-学习与工具/codex-handoff/workflow_driver.py`
2. `0-学习与工具/codex-handoff/tests/test_workflow_driver.py`
3. `0-学习与工具/codex-handoff/tests/test_workflow_release.py`

不修改 gate/state/release 模块、CI 矩阵、业务场景或平台底座，不改变 CI 命令、覆盖范围、退出码判据和真实授权权限。现有私有状态及 review 证据载体可增加字段，不新增依赖、调度器或消费者。无 OEM 技术数据、真实库、L2 签署或 ASIL 代码；不 ff、不连 .51、不外发。将来部署只引用 `zhuopin-lan-closeout` 正本，本包不复制部署纪律。

## 既有守卫退休与伴生文件

不退休授权、CI、独立 review 或 release 门禁：本变更补齐审查输入，不能替代任一既有守卫的证据覆盖。消除的是逐次人工搬运同一授权解释的需要，不新增常驻告警。摘要的消费者就是独立 reviewer；确定性核验由 driver 承担。

不新增自动生成文件名形态。只扩展现有 `state.json`、`review-input-<attempt>.json`、`review.json` 的内容及现有模型 prompt 留痕；这些运行时载体仍在外层私有状态位置。本次手写 OpenSpec 文档不是自动生成伴生文件，故不存在新增文件名的 gitignore 核验对象。

## 知识资产三问（强制，全景规划 §1.4 第 2 条）

1. 默会判断是“哪些 CI 差异属于针对指定设计的明确勘误，哪些仍是缺陷”。将批准原文、绑定条件与反例固化，不能由模型推断“以往批准过，所以这次也批准”。
2. 持有人为 Shao Peishen；backup 按现有场景建造规则为孙涛（缺席时的设计审代理），本包不新增授权。本任务所述既有纠正仍以 Shao Peishen 的逐项外部批准证据为准。
3. 方法为 AI 起草、专家批改，配合脱敏历史案例反推。以有效勘误、越界勘误、篡改授权及独立缺陷并存案例形成回归材料，不复制真实私有批准文件入库。

## 验收与晋档条件（强制，四档口径）

- 本包属于机制工具，验收目标按档1 mock 验证口径：确定性单测与 codex-handoff 子项目 CI；本设计草案本身不代表已达档1，更不宣称业务晋档。
- 后续现场验证须先完成设计批准、TDD、目标 CI、独立只读 review、release-prep；正式使用的授权与发布仍走现有逐项门禁。
- 质量指标：有效绑定摘要准确传入；全部负例不调用 reviewer 或不接纳其结果；无关 findings 完整保留。风险指标：无失效授权放行。人工重复纠正次数的实际基线由 Shao Peishen 确认，不虚构节省量。
- LLM 判断黄金集：冻结脱敏输入，覆盖“仅获批 CI 勘误”“获批勘误加独立缺陷”“未获批 CI 差异”；专家确认期望结论。fake model 单测只能验证传递与门禁，不能证明真实 reviewer 的语义判断已经稳定。
