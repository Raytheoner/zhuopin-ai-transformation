# 【Codex】独立修复 v3 CI：批准 gate 与 Windows 字节夹具

## Why

队列 §一 #648 的 v3 CI 失败已由本次任务输入确认。本包建立独立修复设计，不续写或重判 `workflow-context-continuation-op-0929-x-v3` 原任务。本阶段外层已核真实队列行、intent 批准及 HEAD；模型仅起草文件，不重复 Probe，不读取或写入 ZHUOPIN_CODEX_STATE，不以仓库接力快照代替实时队列。

源码检查发现：`workflow_driver.advance()` 在 `gate.decide_next()` 后无条件尝试 timed-out implementation 续跑；helper 可抛出另一拒绝原因，或把已有 blocked/paused 决策改为 ready。另有两处夹具用 `write_text()` 写入换行，再用固定 LF 字节断言；Windows 文本换行转换会导致该断言失败。

证据边界：本阶段读取了当前源码、测试、v3 design/tasks 及 CI 配置，未读取私有 CI 原始报告、未复跑失败测试；失败次数、CI attempt 路径及退出码须由外层留证，不在本包虚构。

## What Changes

- 仅在原 gate 已返回 `status=ready` 且 `next_phase=implement` 时检查 timed-out 续跑资格；原 gate 的 blocked/paused/缺失批准结果不能被续跑覆盖。
- 两处固定字节夹具改用明确字节写入，保留 `read_bytes()` 精确比较及未变更断言；不归一化生产证据。
- 回归覆盖拒绝结果原样返回、零模型调用、状态/证据/工作文件/HEAD 不变，以及批准正常路径与既有 CI 显式重试路径未受损。

## Capabilities

### New Capabilities

无。纯工具 bugfix，不引入业务能力或新授权语义。

### Modified Capabilities

无规格变更；修复实现对既有批准门禁的违背。按本次任务许可，用 `.openspec.yaml` 的 `schema: spec-driven` 与 `skip_specs: true` 声明纯工具变更，不生成 delta specs。strict 由外层运行，模型不声称已通过。

## Impact

未来实现白名单仅两项：

- `0-学习与工具/codex-handoff/workflow_driver.py`
- `0-学习与工具/codex-handoff/tests/test_workflow_driver.py`

本阶段仅新增本 change 的三份 Markdown 及 schema 元数据；不修改代码、队列、v3 文件或证据，不执行 commit、实施、ff、部署或外发。全景规划 §0.1/§1.4 与实施计划第七节为规划背景，本修复不调整场景、排期或晋档。

## 守卫退休与伴生文件

不退休既有守卫：批准 gate、超时证据核验、路径白名单、CI/review 闸各有独立约束，本修复让调用顺序遵守原 gate，未证明任何守卫冗余。不增加告警、巡检或第二套批准判断。本变更不新增任何运行时自动生成文件形态，故无需新增 `.gitignore` 规则；本包规划文件是显式交付件。

## 知识资产三问（强制，全景规划 §1.4 第 2 条）

1. 默会判断：此处没有新增业务阈值；需显性化的是“续跑资格不等于批准”和“字节不变不能用文本归一化验证”两条工程判据。
2. 显性化责任：以既有 gate、测试及本包为载体；设计裁决沿用项目 design 审权限。本任务未指定新的知识持有人及 backup，不虚构人员任命；若需建立业务知识资产，须另案指定，本工具修复不依赖该任命。
3. 提取方法：历史失败案例反推，加 AI 起草、人工设计审与独立代码 review；不使用 OEM 或生产业务数据。

## 验收与晋档条件（强制，四档口径）

本包为机制修复，不给业务场景晋档；测试采用隔离 mock，属于档1验证性质，不能宣称档2真实数据或档3服务上线。交付目标是修复独立 task 达到 release-prep，不代表 v3 CI 已转绿。

验收条件：外层 strict 通过、取得绑定本包设计 HEAD/hash 的批准、两文件实现、目标子项目 CI 通过、绑定 implementation HEAD 的独立 review 通过、发布准备证据完整。任一前置失败即停。价值为风险型：既有拒绝用例全部保持原 gate 结果且零副作用；Windows 换行不再制造夹具假失败。不宣称未经确认的工时或收益基线。
