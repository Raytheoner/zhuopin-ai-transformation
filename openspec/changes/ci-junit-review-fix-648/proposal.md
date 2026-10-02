# 【Codex】队列 §一 #648：移除 CI/JUnit 修订中的超时续跑例外

## Why

本包承接用户已批准的 CI/JUnit 修订意图及独立 review 指出的超时续跑门禁绕过。当前源码中，`workflow_driver.py::advance()` 在调用 `gate.decide_next()` 后，通过 `_timed_out_implementation_thread()` 将结果改写为 implement/ready；`_implement()` 在存在 `resume_thread` 时允许脏工作树。这偏离原阶段链的失败停止与干净设计 HEAD 前置。

本阶段由外层驱动核验实时队列行、intent 批准与 HEAD；本模型不重复 Probe、不访问私有状态。review 缺陷来源为本次派工，源码读取用于确认修订位置；本阶段未读取私有 review 报告，不声称已重新独立评审。历史 `ci-junit-648` 文档与 task/attempt/报告均保持原样。

### 既有守卫退休说明

删除超时续跑例外及仅服务该例外的校验/helper、参数传递和正向测试，不另建恢复机制。该例外不是可取代原门禁的授权来源。保留原 `gate.decide_next()`、干净工作树、HEAD、批准绑定、hooks、证据完整性及独立 review 守卫：各自覆盖阶段、版本、权限或证据，不能因已有 CI 通过而退休。

## What Changes

1. 删除 driver 的超时实施续跑分支、对应 `resume_thread` 调用链及续跑提示，不覆盖原阶段门禁判定。
2. 恢复实施入口无条件要求干净且匹配获批设计 HEAD；超时保留失败记录和未提交工作，不自动继续或清理。
3. 删除 `test_timed_out_implementation_resumes_same_thread_without_losing_dirty_work` 及仅肯定该例外的断言；补有界负例验证原门禁拒绝后不调用模型、不新开 attempt、不改旧证据。
4. 保留现有 CI 命令、JUnit 安全归档与证据验证、显式 CI retry/refresh、批准上下文传递及其已有测试。pytest 超时字节留存测试不属删除范围。
5. 后续按原阶段链重新取得 strict、逐项目 CI、独立 review，止于 release-prep。

## Capabilities

### New Capabilities

无。纯内部工具纠偏，`.openspec.yaml` 使用 `schema: spec-driven`、`skip_specs: true`，不创建 delta specs。

### Modified Capabilities

无业务主规格变更。恢复既有阶段闸，不增加恢复接口或放宽授权；具体删除边界见 design。

## 知识资产三问（强制，全景规划 §1.4 第 2 条）

1. **哪些判断是人脑默会经验？** 本次是工程规则显性化：超时不是授权，局部续跑校验不能覆盖全阶段闸，旧成功证据不能证明修订后的 HEAD。无新增部门业务阈值。
2. **由谁显性化？** 持有人 Shao Peishen；backup 孙涛，仅沿原规则允许的 design 审代理范围。本包不授予新的批准或签署权限。
3. **用什么方法提取？** AI 起草·专家批改，结合本次 review 问题与源码案例反推，固化为删除清单、拒绝用例和新的独立 review 核验项。

## 验收与晋档条件（强制，四档口径）

- **交付档位**：内部工具，按档1隔离/mock 验证验收；本阶段仅提案文档，不宣称档1已通过或内部服务已上线。
- **晋下一档条件**：外层 strict 通过；该任务本版 design 批准与 HEAD/SHA256/allowed_paths 有效绑定；有界实施完成；受影响矩阵项目真实 CI 及 JUnit 证据通过；独立新 thread review 通过；外层 release-prep 证据齐备。任何缺项停在原阶段；ff、生产、外发不在本任务执行范围。
- **价值指标**：风险型——超时路径不能将 blocked/paused 改为 implement/ready，拒绝时模型调用和新 attempt 均为零；质量型——既有 CI/JUnit 契约及负例覆盖保留，新 HEAD 的逐项目结果与原始证据齐全。基线为本次源码可见的例外路径，不虚构通过数量或节省工时。

## Impact

预期实施仅修改 `0-学习与工具/codex-handoff/workflow_driver.py` 与 `0-学习与工具/codex-handoff/tests/test_workflow_driver.py`，仍须外层核准本版 allowed_paths。若证据显示必须扩大范围，停止并报告，不擅自改 gate/state/provider 或其他测试。

本变更不新增任何自动生成文件名形态，沿用既有 CI/JUnit/report 产物；无新增 `.gitignore` 项。文档目录四件为人工提案文件。不改全景排期、CI workflow、覆盖率下界、业务场景、OEM 数据、L2 或 ASIL 判定。

权威依据：根 AGENTS/CLAUDE、适用规则、codex-handoff README、接力卡、全景规划 §1.4、实施计划第七节、`codex-mechanism-migration/intent.md` 与 `intent-deploy-design.md`/`intent-deploy-plan.md`、`ci-junit-648` proposal/design/tasks。历史授权及历史通过记录只作背景，不自动扩大本包权限。

队列与编辑锁/登记由外层沿既有专用工具处理，本模型仅写指定 change 目录。部署程序只引用 `.agents/skills/zhuopin-lan-closeout/SKILL.md` 正本入口，不复制部署纪律。

暂不归档：strict、该版设计批准、实施、CI、独立 review、release-prep 尚待后续阶段。
