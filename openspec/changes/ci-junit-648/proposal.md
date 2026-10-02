# 【Codex】队列 §一 #648：CI 命令与 JUnit 证据修订

## Why

GitHub Actions 的 `.github/workflows/ci.yml` 在每个矩阵项目目录执行 `python -m pytest -q --tb=short --junit-xml=pytest-result.xml`。当前 `workflow_driver.py::_test` 使用 `-q -p no:cacheprovider`，`workflow_state.py::ci_target_is_valid` 固定接受旧参数，CI 证据仅留存 stdout/stderr。两者命令不一致，且本地阶段链缺少可重新校验的 JUnit 原件。

本包按用户给定的 CI 修订意图整理 proposal/design/tasks；外层已核实时队列、intent 批准和 HEAD。本模型阶段不重跑 Probe、不访问私有状态、不把历史队列或旧批准解释为本版设计批准。后续严格校验、design HEAD/SHA256 与逐项授权绑定均由外层核验，失败即停止。

### 既有守卫退休说明

替换 driver 和 state 中旧 pytest 参数的执行/接受规则，不再保留两套可接受命令。保留既有 cwd、HEAD、原始输出哈希、设计批准和独立 review 闸：它们分别验证执行范围、版本、证据完整性和授权，JUnit 不能替代这些覆盖面。不新增并行巡检、告警或调度器。

## What Changes

1. 每个受影响 CI 矩阵项目继续独立运行；pytest 参数与 GitHub Actions 一致，解释器使用当前 runtime 的隔离 Python。
2. 安全处理项目内 `pytest-result.xml`：拒绝覆盖既有文件或链接；仅归档、清理本 attempt 确认拥有的产物。按 task/attempt/项目留存原始 XML 和 SHA256，失败也留证。
3. 状态校验同时核对命令、cwd、stdout/stderr、JUnit 路径/哈希/XML 格式及报告绑定；缺失、损坏、漂移或矛盾证据阻断 review/release。
4. 旧成功 CI 不能自动晋级；保留原报告，经显式证据刷新重跑后重新独立 review。测试失败沿原失败重试入口，不伪装为成功证据刷新。
5. 更新相关 driver/state/gate/release/E2E 测试夹具和负例；后续只推进到 release-prep。

## Capabilities

### New Capabilities

无业务能力新增。本包为既有开发工具 CI 执行与证据校验修订，采用 `.openspec.yaml` 的 `schema: spec-driven`、`skip_specs: true`，不生成业务 delta specs。

### Modified Capabilities

无业务主规格变更；工具内部数据契约与拒绝条件在 `design.md` 明确。不得借 skip_specs 跳过设计批准、strict 或实现验收。

## 知识资产三问（强制，全景规划 §1.4 第 2 条）

1. **哪些判断是人脑默会经验？** 本次没有部门业务阈值提取；需要显性化的是 CI 命令一致性、XML 所有权、旧证据不可沿用和失败不能晋级的工程判据。来源是现有 CI workflow、阶段设计与实际代码，不靠模型口头判断替代机器证据。
2. **由谁显性化？** 沿项目设计审责任，由 Shao Peishen 确认；缺席代理按规则由孙涛承接允许的 design 审范围。本包不新任命业务 Champion 或扩大代理权限。
3. **用什么方法提取？** AI 起草·专家批改，加历史案例反推；固化成命令契约、文件处理表、失败用例与独立 review 记录。

## 验收与晋档条件（强制，四档口径）

- **交付档位**：内部机制变更，验收上限按档1隔离/mock 验证描述；release-prep 不是内部服务上线，更不是对客交付。本阶段仅产出文档，尚未完成档1验收。
- **晋下一档条件**：外层 strict 通过且本版设计批准绑定有效；实施仅触碰批准白名单；逐受影响 CI 项目真实测试和完整证据通过；独立新 thread review 通过；发布准备证据齐全。ff、生产及外发仍分别取得授权，本任务不执行。
- **价值指标**：质量型——所有受影响项目实际 argv 与 workflow pytest 参数一致，JUnit 原件及 SHA256 覆盖全部已运行目标；风险型——缺 XML、篡改、旧报告复用、越界或既有文件覆盖等负例全部阻断。基线为源码可核的旧命令和缺 JUnit 字段，不虚构节省工时。
- **LLM 黄金集**：本次 CI 判定为确定性逻辑，不新增 LLM 业务判断；独立 review 不能替代机器校验。

## Impact

预期实施文件为 `0-学习与工具/codex-handoff/workflow_driver.py`、`workflow_state.py` 及该目录 `tests/test_workflow_driver.py`、`test_workflow_state.py`、`test_workflow_gate.py`、`test_workflow_release.py`、`test_workflow_e2e.py`。确切可写范围以外层本版 `allowed_paths` 为准；缺路径即停，不自行扩白名单。不改 `.github/workflows/ci.yml`、覆盖率阈值、生产服务或业务场景代码。

### 自动生成文件与忽略规则

未来执行产生项目内 `pytest-result.xml`，并由外层在原任务证据目录留存 `ci-<attempt>-<index>.junit.xml`。已执行只读命令 `git check-ignore -v -- "0-学习与工具/codex-handoff/pytest-result.xml" ".codex/state/runs/ci-junit-648/ci-attempt-0.junit.xml"`，退出码 0：分别命中 `.gitignore:25:pytest-result.xml` 与 `.gitignore:121:.codex/state/`。这里只查询路径字符串的忽略规则，未读写私有目录；外置 runtime state 由外层管理，不入库。本阶段不创建任何 XML 或状态文件。

### 权威来源与阶段边界

已读根 AGENTS/CLAUDE、适用规则、接力卡、codex-handoff README、全景规划 §1.4、实施计划第七节，以及 `codex-mechanism-migration` 的 intent、intent-deploy-design/plan 与 tasks。历史 `review-approval-context-648/design.md` 仅解释前次 CI 差异，不构成本包的命令豁免。读取时 HEAD 为 `8eb88c52d4ed3e320a91c17240e8724494a6fe54`；不是未来 implementation HEAD。

不改全景排期，不接真实 OEM 数据，不代 L2 或 ASIL 判定。真实队列/编辑锁登记由外层沿原工具处理，本阶段不改队列、接力或私有状态。部署程序只引用 `zhuopin-lan-closeout` 正本，不复制纪律。

暂不归档：本包尚待外层 strict、批准绑定核验、实现、CI、独立 review 和 release-prep。
