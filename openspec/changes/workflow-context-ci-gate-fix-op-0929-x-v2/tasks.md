# 【Codex】v3 CI 独立修复实施计划（尚未执行）

Goal：保留批准 gate 拒绝结果，修正 Windows 夹具的换行字节不一致，独立修复 task 验证至 release-prep。

Architecture：仅限制 advance 中 timed-out helper 的调用资格，并固定测试输入字节；沿用原 gate、证据、CI 和 review 机制。

Tech Stack：Python 3.14、pytest、PowerShell、现有 Workflow/OpenSpec 外层驱动。

Spec：本目录 `design.md`。实施时按 executing-plans 逐项执行；当前阶段不得实施。下列复选框供 OpenSpec 机器跟踪，未勾选不表示用户需要点击。

## 1. 外层前置与设计批准

- [ ] 1.1 外层执行 `openspec validate "workflow-context-ci-gate-fix-op-0929-x-v2" --strict`，保留命令、退出码和报告；本模型 sandbox 不运行 CLI。失败立即停止。
- [ ] 1.2 外层绑定独立修复 task 与 §一 #648 的实时查询/intent 证据，保留 v3 原 task/失败 CI 引用；本阶段不访问私有状态、不重复 prepare/Probe、不改原任务。
- [ ] 1.3 完成人工设计审，获得绑定本包 design HEAD/hash 的实施批准，allowed_paths 仅 `0-学习与工具/codex-handoff/workflow_driver.py` 与 `0-学习与工具/codex-handoff/tests/test_workflow_driver.py`；缺失批准即停。

## 2. 定点复现与两文件最小修复

- [ ] 2.1 外层核独立工作树、HEAD、原有修改和所需锁，解析隔离 Python。实施前在 `0-学习与工具/codex-handoff` cwd 执行 `-m pytest -q --tb=short "tests/test_workflow_driver.py::test_timed_out_implementation_preserves_gate_rejection" "tests/test_workflow_driver.py::test_implementation_rejects_dirty_approved_head_before_model"`，保存原失败回显与退出码；若失败原因不匹配设计先停查。
- [ ] 2.2 在测试文件将两处固定 LF 夹具改为 write_bytes，保持 read_bytes 严格断言；再次定点跑测，区分换行假失败与仍存在的 gate 失败，不把夹具修正当作 gate 已修。
- [ ] 2.3 保留四种 gate_case × 两条 dirty_path 的参数覆盖；增加 helper 不得调用的哨兵、ready implement 合法续跑正例、非法证据拒绝及非 implement 阶段不调用 helper 用例。测试原始文件集合、bytes、HEAD、零模型副作用；使用隔离假 task，不触碰 v3。
- [ ] 2.4 仅修改 workflow_driver.py::advance，将 helper 检查及覆盖 decision 的分支限定在原 gate 的 ready + implement 下；保留原 helper 内证据校验、普通 implement 与显式 CI retry/refresh 流程。
- [ ] 2.5 用两个原 node-id 及新增测试的完整 node-id 验证转绿，保留 Windows 下命令、cwd、退出码和回显；不跳过用例、不降低断言，不使用 -k。

## 3. 目标子项目 CI

- [ ] 3.1 外层核变更仅命中批准两文件，并按现时动态 CI 矩阵与最具体项目根解析受影响项，保存选择依据；不可用快照代替现时矩阵。
- [ ] 3.2 每项独立 cwd 用隔离 Python 执行 `-m pytest -q --tb=short --junit-xml=pytest-result.xml`，设置 PYTHONUTF8=1，保留 implementation HEAD、命令、退出码、stdout/stderr 原文与 SHA256、JUnit；任何失败停止下游，不根目录混跑、不共享全局 editable 安装。
- [ ] 3.3 核对 gate、普通实现、正常续跑、拒绝证据以及 CI retry/refresh 相关结果；若有新失败且需超白名单改动，停止并报告，保留每次 attempt，不覆盖 v3 或首轮失败。

## 4. 独立 review 与发布准备

- [ ] 4.1 CI 通过后由外层安排另一只读 thread 独立 review，报告绑定 implementation HEAD；核拒绝字典原样返回、零副作用、正向续跑可达、字节断言未弱化、修改范围及历史证据未变。
- [ ] 4.2 review 驳回时保留报告，批准范围内修正后重做受影响测试/CI 与独立 review；前一阶段证据不合格不得继续。
- [ ] 4.3 外层汇总本修复 task 的 release-prep：命令、实际退出码、证据路径/哈希、HEAD 与未闭合项；明确原 v3 任务及其 CI 失败保留，不宣称 v3 自动恢复。
- [ ] 4.4 停于发布准备，不执行 ff、部署、外发或 L2 签署；部署程序仅引用 `.agents/skills/zhuopin-lan-closeout/SKILL.md` 正本。模型不 git commit，队列登记和锁按既有外层流程处理。

暂不归档：仅完成设计起草；strict、设计批准、实现、CI、独立 review 与 release-prep 均待后续阶段实际取证。
