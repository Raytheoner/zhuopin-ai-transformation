# 【Codex】CI/JUnit review 修订实施计划

**Goal:** 删除超时实施续跑例外，保留 CI/JUnit，沿原阶段链至 release-prep。

**Architecture:** 复用原 gate、批准绑定和证据链；driver 删除旁路，driver 测试验证拒绝及原成功路径。

**Scope:** 本模型仅写本 change 三件与 `.openspec.yaml`；以下全部为待外层/后续阶段执行的任务。OpenSpec 复选项用于机读，不代表用户回复格式。旧 task/attempt/证据及他人修改不动。

## 1. 外层前置闸

- [ ] 1.1 对本 change 执行 `openspec validate ci-junit-review-fix-648 --strict`，保存命令、输出、退出码及本版产物哈希；核 `schema: spec-driven` 与 `skip_specs: true`，不得伪造 specs 或模型代跑 CLI。
- [ ] 1.2 将本次 intent、实时 #648 查询与原独立 review finding 关联到外层证据；核本版 design HEAD/SHA256 和该任务批准，缺失或漂移立即停止。不得以 intent 已批代替设计已批。
- [ ] 1.3 核干净隔离工作树、hooks 正常信任、编辑锁/登记安排及 allowed_paths；预期仅 driver 与 driver 测试两文件。范围不足停报，不扩权，不清他人修改。

## 2. 有界修订与定向回归

- [ ] 2.1 读取本版 design 与原 CI/JUnit 设计，核 `_timed_out_implementation_thread`、`resume_thread`、续跑 prompt 的所有调用者，记录两文件修订边界；保留清单作为 diff 审查依据。
- [ ] 2.2 使用既有隔离 fixture 添加最小 RED：超时记录不得覆盖 blocked/paused、不得启动模型或新 attempt；脏文件和旧记录字节不变；实施入口拒绝脏树。定向 node-id 运行，记录真实失败原因、命令和退出码。
- [ ] 2.3 删除 driver helper、advance 例外及专用参数/提示/thread 注入；恢复无条件干净设计 HEAD 前置。删除仅肯定绕过的 `test_timed_out_implementation_resumes_same_thread_without_losing_dirty_work`，不删 pytest 超时字节留存测试及通用失败测试。
- [ ] 2.4 重跑新增拒绝用例和原正常实施用例至 GREEN；确认干净获批实施不传旧 thread，且批准绑定与原生 tool/hook 检查仍生效。核无死引用、不引入替代 resume 入口。
- [ ] 2.5 逐项核 design 的 CI/JUnit 保留清单；确认 state/gate/provider/release、其他测试、CI workflow 和旧 change/证据未被本修订改动。外层核 diff 白名单并形成 implementation HEAD；模型不 add/commit。

## 3. 正式逐项目 CI

- [ ] 3.1 外层根据最终 diff 和 `工具-CI矩阵发现.py` 得到受影响项目全集，使用 invoke.ps1 解析的隔离 Python；逐项目 cwd 执行 `python -m pytest -q --tb=short --junit-xml=pytest-result.xml`，其中 python 实际绝对路径须记录。预计项目为 `0-学习与工具/codex-handoff`，不可用定向回归替代正式项目全测。
- [ ] 3.2 保存每目标命令、cwd、真实退出码、stdout/stderr/XML 原件、SHA256、attempt/HEAD 与 report；核完整目标集合及安全归档、绑定验证通过。失败、超时、漏跑、损坏或环境阻断均停止 review，不改断言、不 skip/xfail、不降阈值。

## 4. 独立 review

- [ ] 4.1 外层开启独立新 Codex thread 只读 review，绑定新 implementation HEAD、diff、本版批准上下文和新 CI 原件；逐项复核原 finding、门禁不被覆盖、脏树拒绝、零模型调用、旧证据保留及完整 CI/JUnit 保留清单。
- [ ] 4.2 保存独立 thread ID、结论、findings、报告路径与哈希。changes_required 或证据不足即停；如进入获准修订，回到有界实施后重新 CI/review，不复用旧 approved，不自审代签。

## 5. 发布准备与交接

- [ ] 5.1 外层仅在上述证据全部满足后生成 release-prep，核其绑定最终 HEAD 和新 CI/review；完整交付命令、退出码、证据路径与未闭合项。
- [ ] 5.2 外层按原工具完成队列与编辑锁登记，保留旧 task 和证据；ff、生产部署、真实外发、L2 签署均明确未执行。部署程序仅引用 zhuopin-lan-closeout 正本，不复制纪律、不触发 transfer/deploy。

## 当前状态

仅文档产出；strict 由外层待运行。设计批准、实施、逐项目 CI、独立 review、release-prep 未在本阶段执行。暂不归档，不声明队列 #648 已闭合。
