# 【Codex】批准 gate 优先与确定性字节夹具设计

## Context

任务来自 §一 #648，当前只获准起草。外层提供已核 intent/队列/HEAD 的前提，不等于本设计已批准。v3 原 task、attempt、CI 报告与 OpenSpec 包保持不变；本包不继承 v3 的批准来实施。

源码定位：`workflow_driver.py::advance`、`_timed_out_implementation_thread`；`tests/test_workflow_driver.py::test_timed_out_implementation_preserves_gate_rejection` 与 `test_implementation_rejects_dirty_approved_head_before_model`。gate 正本仍是 `workflow_gate.py::decide_next`，本次不修改该文件。

## Goals / Non-Goals

目标：续跑只能发生在 gate 已允许 implementation 的分支；拒绝状态与理由不被 helper 覆盖；跨平台夹具保留严格字节语义。

非目标：不新增自动恢复、不扩大 timeout/context-stop 白名单、不修改 provider/D3 终止证据、批准 schema、CI 配置或状态机；不重构驱动，不更改全局换行设置，不修无关失败。不访问私有状态目录、不重跑或洗白 v3 原任务。

## Decisions

### D1：在调用边界限制 helper

保留 `collect_evidence → gate.decide_next`。仅在该次原始 decision 同时满足 `status == "ready"` 和 `next_phase == "implement"` 时，进入现有 `_timed_out_implementation_thread` 的 try/except 与续跑分支。helper 返回 thread 时才沿用原显式续跑参数；返回 None 时保持普通 implement；抛 ValueError 时仍 fail closed。

gate 为 blocked/paused 时不能调用 helper，避免先抛 ValueError 改写原拒绝原因。对本次 timed-out implementation 用例，`advance` 必须原样返回 gate 字典（含 status、reason、next_phase），不得创建 attempt、写状态、调用模型或改 HEAD。

选择调用边界限流，是因为仅删除 ready 覆盖语句仍可能由 helper 异常遮蔽 gate 拒绝；在所有非 ready 决策处统一提前 return 又可能破坏后续已存在的 `--retry-failed-ci`、`--refresh-ci-evidence` 特殊流程。保留这两条显式 CI 流程原位置与原语义，只调整 timed-out implementation 分支。原 gate 指向 test/review/release_ready 时也不得调用此 helper。

不把 state.phase_status=blocked 一概判为不可运行：是否具备下一阶段资格仍由 gate 判定。必须保留 helper 现有 task/attempt、terminal result、批准引用与绑定、HEAD、approved dirty paths 校验。正向回归只使用 gate 真正放行的现有条件，不伪造批准来放宽拒绝。

### D2：夹具按断言单位写入

上述两处 `dirty.write_text("VALUE = 1\n", encoding="utf8")` 改为 `dirty.write_bytes(b"VALUE = 1\n")`，保留原 `dirty.read_bytes() == b"VALUE = 1\n"`。这样只固定测试输入，不弱化被测行为。禁止将断言改为 `read_text()`、strip/replace，或对真实 CI/批准/证据哈希做换行归一化。

可在同一测试文件追加显式 CRLF 输入的独立不变性用例，写入与比较同一原始 bytes，证明拒绝前后不会悄悄重写换行；不需要修改 repository core.autocrlf 或系统默认编码。

### D3：验证矩阵与零副作用

| 路径 | 输入 | 验收 |
|---|---|---|
| 真实 gate 拒绝 | real-blocked × service.py/outside.py | 返回 expected，模型未调用，task 文件集合及内容、dirty bytes、HEAD 不变 |
| 注入 gate 拒绝 | blocked/paused × 两条 dirty path | 原字典返回；可给 helper 装失败哨兵以证明完全未调用 |
| 缺批准 | authorization=None × 两条 dirty path | 保留 paused / design review required，不改成 helper 的 blocked |
| gate 放行 implement | 合法超时 terminal/批准/HEAD/path 证据 | helper 被检查，合法 thread 仍传入原实现流程 |
| gate 放行但续跑证据坏 | 批准引用漂移、terminal 证据缺失或越界 dirty path | fail closed，无模型启动，不放松既有核验 |
| 普通阶段与 CI 重试 | 非超时 implement、test/review；显式 retry/refresh | 原行为保持，续跑 helper 不抢占其他阶段 |
| 字节输入 | LF；如扩展则显式 CRLF | 原始 bytes 保持，不借文本读取隐藏变化 |

未来执行先在隔离环境重现定点失败，再改两文件；使用 invoke.ps1 解析的独立 Python，设置 PYTHONUTF8=1。定点命令在 `0-学习与工具/codex-handoff` cwd 用 `-m pytest -q --tb=short` 加上述两个完整 node-id，不用 `-k`。新增正向用例同样列具体 node-id。

随后按 `.github/workflows/ci.yml` 的动态发现和最具体项目选择器确定受影响矩阵项，逐项切 cwd，运行 `-m pytest -q --tb=short --junit-xml=pytest-result.xml`；预计命中 `0-学习与工具/codex-handoff`，必须以届时实测结果为准，不在仓库根混跑。记录命令、cwd、Python 路径、implementation HEAD、退出码、stdout/stderr 原文及 SHA256、JUnit；失败即停，不以减少用例或仅定点通过代替目标 CI。

### D4：阶段与证据所有权

1. 本阶段只写本包文件；`.openspec.yaml` 声明 spec-driven/skip_specs，不新增规格能力。模型不运行 OpenSpec CLI。
2. 外层 strict 验证通过后封存设计 HEAD/hash，取得该 task 的逐文件 allowed_paths 批准。批准缺失或前置证据不足停止实施。
3. 实施模型只修改白名单两个文件，不 commit；外层按既有驱动核验并处理提交、证据与编辑锁/队列登记。本包不要求模型绕过锁或直接写队列。
4. CI 通过后用独立只读 review thread，绑定 implementation HEAD，重点审 D1 拒绝优先、D2 原始字节、正向续跑及 CI retry/refresh 无回归。实现者自查不算独立 review。
5. review 通过才生成本修复 task 的 release-prep，列出 v3 仍保留的失败及未闭合项，不把本修复通过倒写成 v3 通过。不执行 ff、生产部署或对外发送。部署纪律仅引用 `.agents/skills/zhuopin-lan-closeout/SKILL.md` 正本。

## Risks / Trade-offs

过宽提前返回会破坏 CI 恢复，所以限制局部调用条件；只看 status 不看 next_phase 会错误调用 helper，所以同时检查两字段。只测拒绝会漏掉正常超时续跑被禁用，所以必须有正向用例。模拟 gate 不能代替真实 gate，因此保留 real-blocked 与 missing-approval 用例。

本阶段没有 CI 原始报告可供私有目录以外的核验；外层须关联原 v3 attempt 与失败证据，不在文档填猜测路径。若定点复现与当前设计不符，停止并补证据，不扩大实施白名单。

## Migration / Rollback

没有数据或状态迁移。未发布前失败保留新 task 的现场与原 v3 证据；如需回退，只回退本独立修复的两个文件差异，经外层核验不得覆盖他人修改，不删除旧任务、attempt 或日志。
