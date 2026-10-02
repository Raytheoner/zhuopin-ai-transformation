# 【Codex】CI 命令一致性与 JUnit 证据设计

## Context

范围为队列 §一 #648 的 CI 修订。用户说明外层已核实时队列、批准 intent 和 HEAD；本阶段仅写本 change 的文档。本文是待外层校验及逐版本绑定的设计产物，不自行声明新授权已生效。

现有 `workflow_driver.py::_test` 通过 `affected_ci_roots` 从动态矩阵挑选最具体受影响项目，要求干净 implementation HEAD，串行调用注入 executor，并保存每个目标 stdout/stderr 与报告。`workflow_state.py::ci_target_is_valid` 检查项目路径和旧命令，`ci_evidence_error` 检查输出哈希以及 report/task/HEAD/targets 一致性。review 和 release 复用这些闸。

GitHub Actions 的权威 pytest 命令为 `python -m pytest -q --tb=short --junit-xml=pytest-result.xml`。旧 driver 的 `-p no:cacheprovider` 不是该命令的一部分。本包在保留隔离解释器和逐项目 cwd 的前提下消除差异。

## Goals / Non-Goals

目标：命令参数一致；JUnit 原始字节可追溯；文件所有权和路径安全；证据缺失或漂移 fail closed；旧证据通过显式重跑升级；独立 review 后仅达 release-prep。

非目标：更改 CI 矩阵发现算法或覆盖率下界，修其他项目基线，重写 GitHub workflow，增加后台调度，自动批准、提交、ff、部署、外发或签署。当前模型不运行 OpenSpec CLI、pytest、Probe，也不读取或写入 ZHUOPIN_CODEX_STATE 私有目录。未来外层执行器写证据与本模型阶段的禁止访问严格区分。

## Decisions

### 1. 命令以 GitHub Actions 为准

driver 构造 argv 为 `[sys.executable, "-m", "pytest", "-q", "--tb=short", "--junit-xml=pytest-result.xml"]`，cwd 为该矩阵项目真实目录。`sys.executable` 必须来自 invoke.ps1 解析的隔离 runtime。参数数组执行，不拼 shell 字符串；不额外加 `-p no:cacheprovider`、node-id 或绝对 XML 路径来冒充相同命令。

state 接受相同参数；保留绝对 Python 路径检查、nodeid 非空且无绝对路径/冒号/反斜线/点段、cwd 必须等于 workspace 内对应项目且不能为仓库根。测试直接对照 `ci.yml` 的 pytest run 行，防止 driver 与 validator 同时改错却互相自证。CI workflow 命令后续改变时回归必须显式报差异。

备选：只补 `--tb=short` 仍缺结构化证据；将 XML 直接输出到私有绝对路径虽便捷但不满足命令逐参数一致；本方案在项目目录生成后安全归档，接受少量文件生命周期处理成本。

### 2. XML 生命周期与所有权

源路径固定为 `<project>/pytest-result.xml`；外层归档路径为既有 task 目录下 `ci-<attempt-id>-<target-index>.junit.xml`，不得由报告自由指定写入位置。

| 时点/输入 | 必须行为 |
|---|---|
| 执行前已有源文件、目录、符号链接、悬空链接或 reparse point | 阻断且不启动该目标，不删除、不覆盖、不读取外链内容；报告冲突路径 |
| 项目或源路径解析出 workspace 边界 | 阻断，不执行 pytest |
| 目标归档名已存在或经过链接重定向 | 阻断，不覆盖旧 attempt 的证据 |
| executor 返回，包括 pytest 非零 | 保存 stdout/stderr、真实退出码；尝试留存本次拥有的 XML 原始字节；失败结果不得因 XML 有效而转绿 |
| XML 缺失、目录、链接、无法读取或替换迹象 | 标记证据错误并阻断，保留现场，不猜测修复 |
| 归档成功 | 排他创建归档文件；核对源/归档字节哈希一致；仅清理仍是本次同一普通文件、内容未变且位于项目目录的源文件 |
| 归档或清理失败 | 保留已经得到的原文和失败信息，不能产出可晋级 CI；不递归删除、不清其他文件 |
| 异常、超时、中断 | 尽可能封存已得到的 stdout/stderr/XML；缺数据明确标缺失，由现有 attempt/recover 留痕，不伪造 exit=0 |

使用 `lstat`/文件身份信息识别符号链接、Windows reparse point 与清理前替换；对可疑硬链接（多链接计数）拒绝处理。读取后再次核对身份/元信息，归档用排他创建防止覆盖；文件存在性判断不能只用会忽略悬空链接的 `exists()`。本机制保护受控隔离 worktree 的证据处理，不宣称能防御任意恶意测试进程的所有 OS 级竞态；仍依赖既有独占 attempt 和 workspace 闸。

不自动备份并覆盖未知旧 XML，不根据 gitignore 推断文件可删。Git 忽略只解决产物登记，不代表所有权。

### 3. 证据契约及状态校验

每个 target 在既有 `nodeid/argv/cwd/exit/stdout_path/stdout_sha256/stderr_path/stderr_sha256` 上新增 `junit_path` 和 `junit_sha256`。失败可记录 `junit_error`（稳定原因），不得给缺失文件填假哈希。原始 XML 按 bytes 留存，不能重新序列化或用 stdout 摘要合成。

CI report 继续绑定 `task_id`、`implementation_head`、`targets`；增加 `attempt_id` 与本次预期项目列表 `expected_roots`，用于核对目标覆盖完整性和归档命名。state 必须核对当前 CI attempt 属于任务 attempt 台账、报告 targets 与状态相同、项目不重复且集合等于 expected_roots；由 driver 从当前受影响矩阵产生列表，不采用模型自报。旧报告缺这些字段不得晋级。

`ci_evidence_error(current)` 在现有检查上追加：

1. JUnit 引用为绝对路径，实际归档位于该 task 证据目录，文件名与 report attempt/index 一致；拒绝链接、越界、非普通文件或空/非 SHA256 摘要。通过已有 task id 计算目录，不从任意 target 反推信任根。
2. 重读原始 bytes 核 SHA256；按安全 XML 解析方式拒绝 DTD/ENTITY，不能解析外部实体或访问网络。接受 pytest 标准 `testsuites` 或 `testsuite` 根且存在 suite；计数必须为非负整数，畸形 XML 或无 suite 失败。
3. pytest exit 必须为 0，XML 中 failures/errors 必须为 0，且不能含 failure/error 子元素与成功判定矛盾。不把父级与子级 totals 重复相加，不引入新的业务覆盖率阈值；skip 不自动失败，零收集沿 pytest 非零退出规则处理。
4. stdout/stderr/report 的原有哈希与 task/HEAD 绑定检查继续全部执行；成功至少要求预期目标全部运行、所有 exit=0、全部 JUnit 和原始输出有效、报告一致。不得因新增 XML 检查而缩窄旧覆盖面。

可在 state 内增加纯字节 XML 校验 helper 供 driver 留证后复用；文件路径及归档所有权留在 driver/state 各自现有职责中，不增加另一套状态机。校验返回具体错误供外层消费，不新增只有告警无人承接的机制。

### 4. 兼容、刷新与恢复

旧命令或缺 JUnit/attempt/expected_roots 的成功报告为过期证据；不自动改字段、补 XML、重新计算旧哈希或借旧 review 豁免。`_ci_refresh_reason` 扩充为识别这些明确的历史格式缺项；`--refresh-ci-evidence` 仍要求同一干净 implementation HEAD、可核的旧报告及原有 review 限制。有效完整报告没有刷新理由。

XML 已有字段但哈希损坏、跨任务引用、报告冲突属于篡改/漂移阻断，不能作为普通“缺证”自动刷新。原测试非零使用 `--retry-failed-ci` 的既有入口。refresh/retry 均使用新 attempt 和独立归档名；保留旧报告、原文与 attempt，已存在 review 按原规则归档，重跑后必须新 thread review，旧 approved 不复用。安全文件冲突先保留现场，不能为了重试删除未知文件。

### 5. 影响范围与授权

生产代码只预期修改 `workflow_driver.py` 与 `workflow_state.py`。相关测试覆盖 `test_workflow_driver.py`、`test_workflow_state.py`、`test_workflow_gate.py`、`test_workflow_release.py`、`test_workflow_e2e.py`；升级成功夹具为含真实临时 XML 的完整证据，不 mock 掉新增校验，不删除旧断言。需要其他文件时先报路径差异，由外层核准后再做。

不修改 release/gate 的授权规则；通过其既有调用 state 校验的入口拒绝无效 XML。测试发现存在绕过时停止并报告，不超白名单改生产模块。部署程序仅引用 `zhuopin-lan-closeout` 正本。

## Risks / Trade-offs

- 旧本地结果将失效，需要显式重跑；这是证据升级成本，不重写历史成功记录。
- 使用精确相同命令会恢复 pytest 默认 cache 行为；由既有忽略规则处理，不在本包删除 cache 或改 pytest 全局配置。
- Windows 链接与文件共享占用可能导致安全阻断；以隔离夹具验证，不用生产文件演练删除。
- XML 解析及计数判断可能误拒绝标准 pytest 输出；用实际最小 pytest JUnit 与有效/无效 fixture 双向测试，失败时修 parser，不能绕过闸。
- 正式矩阵测试可能暴露已有失败；保存真实结果，按同命令/同环境基线取证，不删断言、skip 或 xfail。当前任务不授予 ff。

## Validation Strategy

先对新增命令、文件安全、XML/报告校验、刷新拒绝路径做 RED/GREEN，再由外层从动态矩阵选择全部受影响项目，分别在其 cwd 执行精确 CI 命令。预计项目根为 `0-学习与工具/codex-handoff`，实际以实施 diff 与矩阵发现为准；不得在仓库根混跑。

每次记录实际隔离 Python 绝对路径、cwd、argv、HEAD、attempt、退出码、stdout/stderr/XML 路径及 SHA256。单测 fixture 使用临时目录并在模块载入前隔离 state；不得命中真实私有目录、服务、队列或授权记录。

独立 review 使用另一 Codex thread，绑定 implementation HEAD、diff、设计批准摘要、CI report 和原件引用；重点检查文件越界/覆盖、失败保留、旧证据绕过和所有目标完整性。review 通过后外层仅生成 release-prep，不执行 ff、生产或外发。

## Migration Plan / Current Stop

当前仅 proposal/design/tasks 与工具变更元数据；暂不归档。外层依次运行 strict、核本版 design HEAD/SHA256 与 allowed_paths、实施、逐项目 CI、独立 review、release-prep。任一证据不足即停止其依赖步骤。本文不证明 strict、设计批准绑定或后续阶段已经执行。
