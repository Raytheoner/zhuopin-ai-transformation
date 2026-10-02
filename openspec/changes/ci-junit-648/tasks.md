# 【Codex】CI JUnit 修订 Implementation Plan

**Goal:** 使 driver 的逐项目 pytest 命令与 GitHub Actions 一致，以安全留存的 JUnit 原件参与阶段校验，独立 review 后仅到 release-prep。

**Architecture:** 复用现有 driver、state 和 CI/review/release 闸；driver 管执行与文件生命周期，state 管确定性证据校验。旧报告只经显式新 attempt 重跑升级。

**Tech Stack:** 隔离 CPython 3.14、pytest、Windows PowerShell、Git worktree、既有 OpenSpec 外层驱动。

**Spec:** 同目录 `design.md`；执行前全文读取。本阶段只产文档，下列复选项均为尚未执行的外层/后续任务，不是完成声明。任务文件用 OpenSpec 可识别的复选语法，用户回复不需操作复选框。

## Global Constraints

- 模型只写获准文件，不 commit；严格校验与提交由外层处理。本阶段禁止 Probe、OpenSpec CLI、实施和私有 state 访问。
- 本版 design HEAD/SHA256 与 allowed_paths 核准后才实施；旧批准不自行扩展，前一阶段证据不足立即停止。
- 逐受影响 CI 项目 cwd 运行，不在根目录混跑；Python 由 invoke.ps1 解析，不改全局 editable 指针。
- 保留其他人的修改、旧 XML、历史报告和 attempt；不跳过 sandbox/hooks/编辑锁/队列工具。
- 测试采用隔离临时目录和 mock，不读写真实私有状态、队列、生产服务或 OEM 数据。
- 独立 review 后只产 release-prep；ff、部署、外发、L2 不执行。部署入口只引用 zhuopin-lan-closeout 正本。

## Review Focus

| 高风险输入/条件 | 预期 | 所属任务 |
|---|---|---|
| 既有 XML、悬空链接、reparse point、硬链接、清理前换文件 | 不覆盖、不越界读取或删除，阻断留证 | 2 |
| pytest 非零、超时、无 XML、归档失败 | 原始退出结果与可得产物保留，不晋级 | 2、3 |
| XML 畸形/实体声明/计数矛盾、原件篡改 | 确定性校验拒绝，不被 exit=0 掩盖 | 3 |
| 报告跨任务/HEAD/attempt 或漏项目 | 报告与状态不一致即拒绝 | 3 |
| 旧成功/旧 approved 被复用 | 显式重跑并重新 review；篡改不能伪装成缺证 | 4、5 |

## 1. 前置闸与实施范围

- [ ] 1.1 外层对 `ci-junit-648` 运行 OpenSpec strict，保存完整命令、输出与退出码；核三件及 `schema: spec-driven`、`skip_specs: true`，本模型不得代跑。
- [ ] 1.2 外层核验本任务本版设计批准与 design HEAD/SHA256、allowed_paths；确认干净隔离 worktree、真实队列可执行、hooks 正常信任及原编辑锁/登记安排。缺任一项停止实施。
- [ ] 1.3 对照实际 allowed_paths 核以下路径：`0-学习与工具/codex-handoff/workflow_driver.py`、`workflow_state.py`、`tests/test_workflow_driver.py`、`tests/test_workflow_state.py`、`tests/test_workflow_gate.py`、`tests/test_workflow_release.py`、`tests/test_workflow_e2e.py`。未获准路径不得修改；不改 CI workflow、阈值、业务代码。

## 2. 精确命令与 JUnit 安全留存

文件：`workflow_driver.py`、`tests/test_workflow_driver.py`。
接口：保留 `_test(task_id, workspace, attempt, executor)` 与 `affected_ci_roots(...)`；executor 继续接收 argv/cwd/timeout；target 输出新增 `junit_path/junit_sha256`，report 新增 `attempt_id/expected_roots`。

- [ ] 2.1 先写命令回归：fake executor 记录 cwd 与 argv，断言参数恰为 `-m pytest -q --tb=short --junit-xml=pytest-result.xml`；只读解析 ci.yml 的 pytest run 行作独立对照。用两个受影响项目验证 cwd、索引和 XML 归档不串用；仓库根、目录越界拒绝执行。
- [ ] 2.2 写文件生命周期负例：预置普通 XML、目录、悬空链接/reparse point、多链接文件、目标归档冲突；断言 executor 未调用且原件字节不变。另在读取后/清理前替换文件，断言不删除替换件。链接夹具若系统不支持，明确记录阻断，不能写成已验收。
- [ ] 2.3 写成功、pytest 非零、超时、缺 XML、复制异常、清理失败夹具；fake executor 在目标 cwd 生成真实 XML bytes，断言失败也保留可得证据，归档哈希与原始 bytes 相同且不同 attempt 不覆盖。以目标 node-id 运行新测试，保存预期 RED 的具体原因。
- [ ] 2.4 按 design Decisions 1–2 实现精确 argv、源文件所有权检查、排他归档、身份/内容复核后有界清理；任何错误不得产可晋级 CI。原始 stdout/stderr 继续留存，report 保存预期矩阵目标与 attempt。
- [ ] 2.5 重跑 2.1–2.3 新用例至 GREEN，保存命令和退出码；不能通过删除断言或 mock 掉安全检查消除失败。

## 3. 状态和报告校验

文件：`workflow_state.py`、`tests/test_workflow_state.py`，以及相关 gate/release/E2E 测试成功夹具。
接口：保留 `ci_target_is_valid(target, workspace) -> bool`、`ci_evidence_error(current) -> str` 与 `ci_evidence_is_valid(current) -> bool`；错误仍经现有调用链阻断后续阶段。

- [ ] 3.1 写 RED 参数化测试：旧 argv/额外选项/错误 cwd 均拒绝；正确新 argv 接受。有效 `testsuites` 和单 `testsuite` 可用，缺文件、空文件、坏哈希、非绝对路径、任务目录外路径、链接均拒绝。
- [ ] 3.2 写 XML 负例：畸形内容、未知根、无 suite、DTD/ENTITY、负数/非整数计数、exit=0 但 failures/errors 非零或含 failure/error 元素。有效 skipped 用例正常接受，不更改既有覆盖率下界。
- [ ] 3.3 写绑定负例：task/HEAD/attempt 错绑、attempt 不在台账、XML 文件名与 attempt/index 不一致、重复 target、漏 expected_roots、report targets 与 state 不同。保留原 stdout/stderr/report 哈希篡改测试。
- [ ] 3.4 实现 design Decision 3；driver 与 state 可复用纯 bytes XML 校验，拒绝外部实体，不重新序列化 XML。原有检查不能短路丢失。
- [ ] 3.5 升级 gate/release/E2E 成功 fixture：在临时任务目录写真实 XML、正确哈希、attempt 台账与完整 report；不得通过替换 `ci_evidence_is_valid` 为恒真恢复绿灯。重跑新增及受影响测试至 GREEN。

## 4. 旧证据刷新与失败重试

文件：`workflow_driver.py`、`tests/test_workflow_driver.py`，必要的状态测试仍限上述白名单。
接口：沿 `_ci_refresh_reason`、`_prepare_ci_evidence_refresh`、`advance` 与既有 refresh/retry 参数。

- [ ] 4.1 先写 RED：旧命令成功报告、缺 JUnit 或新增 report 字段可被显式刷新识别；无 refresh 请求仍阻断；有效完整报告不得无故刷新；非零 pytest 沿失败重试。旧 review 的原有限制照旧。
- [ ] 4.2 写拒绝测试：已有 XML 哈希漂移/报告错绑不得当作缺证刷新，HEAD 变化/工作树脏不得重跑；含无关 findings 的 review 不被抹除。
- [ ] 4.3 最小修改刷新判定与新 attempt 留证；保留旧 report/XML/attempt，归档原 review 后清除其复用资格；新 CI 后必须新 thread review。用文件哈希断言旧证据未改变。
- [ ] 4.4 重跑 4.1–4.3 至 GREEN，核实际 blocked/ready/paused 结果及下一阶段调用次数，不仅核函数返回 exit=0。

## 5. 正式 CI、独立 review 与发布准备

- [ ] 5.1 外层从最终 implementation diff 与 `工具-CI矩阵发现.py` 取得最具体受影响项目全集；逐项目记录并执行 runtime Python 的 `-m pytest -q --tb=short --junit-xml=pytest-result.xml`。预计 cwd 为 `0-学习与工具/codex-handoff`，新增受影响项目不得漏跑。定向 RED/GREEN 不能替代该正式全项目命令。
- [ ] 5.2 外层核完整目标集合、每项目退出码、stdout/stderr/XML 原件与 SHA256、report/task/attempt/HEAD 绑定，以及执行后工作树状态。测试失败或证据不完整立即停止 review；已有基线问题单列证据，不改断言、skip 或 xfail。
- [ ] 5.3 用独立 Codex 新 thread 只读 review 最终 implementation HEAD、diff、设计批准上下文和真实 CI 证据，覆盖 Review Focus 五项。记录 thread ID、结论、findings、报告引用及哈希；有缺陷先回到有界实施和对应测试，不自审代签。
- [ ] 5.4 全部前置通过后外层仅生成 release-prep；逐项交付实际命令、退出码、HEAD、证据路径、哈希、未闭合项。队列/落库由原工具按 acquire→登记→release 执行；不得模型裸写队列或私有状态。ff、生产部署、外发、L2 签署保持未执行。

## 当前交接状态

仅文档产出；暂不归档。strict、批准绑定、实施、逐项目 CI、独立 review、release-prep 均未在本阶段运行。后续执行沿既有外层驱动，不由本文自行启动或授予权限。
