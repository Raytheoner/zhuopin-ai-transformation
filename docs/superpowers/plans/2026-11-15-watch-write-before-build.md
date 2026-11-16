# Watch write-before-build Implementation Plan

> **For agentic workers:** Default to superpowers:executing-plans in this session, serially. No subagents, no automatic commit/push. Steps use checkbox syntax for tracking.

**Goal:** 修复本人指定的看护消费和写前登记三点，单短口令在隔离回归内产生首个合法候选并回写。

**Architecture:** 保持原队列/锁/只读入口和验收。只在原driver补前台认领衔接与串行接续，原hook仅补精确短口令的消费上下文；不创建独立执行器/状态库/后台。

**Tech Stack:** Python、pytest、现有Git fixture、原队列CLI、OpenSpec。

**Spec:** openspec/changes/watch-write-before-build-1115/design.md 与 specs/serial-test-first-construction/spec.md。

## Global Constraints

- 本主会话串行；#715及§二B-1115_watch-write-before-build已在任何目标写前登记。
- 禁接管KH2/#563/#636候选和#670；禁后台/生产/外发/commit/push。
- execution_ready=false不授新权也不构成新阻碍；原批准、锁、冻结、专业与发布闸保持。
- 预登记用原在办（预登记，收工时精确化）；不先造目标、不放宽普通登记校验。

## Review Focus

- 预登记失败或回读不一致：实施回调调用数=0，目标不存在。
- 他人当前认领藏在原归属文字之后：识别当前唯一写方，不误领。
- 缺失/坏SHA与路径穿越/目录/链：首笔写前拒绝，不能借预登记豁免。
- 第一项阻塞、池后续新增：重取原池后执行下一独立项，不需第二次用户唤醒。
- 回调候选与自然主会话不同：JUnit/文件/hash/回写是真实隔离实证，但level=mock，不声称自然运行完成。

### Task 1: 写前认领与原预登记

**Files:** workflow_driver.py、handoff.py、tests/test_foreground_watch.py、test_工具-共享文档编辑锁.py。
**Interfaces:** claim_native_slice(root, plan, execute)消耗原行SHA/原批准引用/精确allowed_paths和原锁；产出仅绑定该行的claim回执，不授业务权限。

- [x] 写test_preregister_missing_target_before_first_write/test_rejected_registration_never_writes_target及普通登记缺实体反例。
- [x] 在codex-handoff目录运行python -m pytest tests/test_foreground_watch.py -q，保留RED。
- [x] 接原append/edit/query流程，严格scope，先§二成功与原行反查再回实施者；薄CLI只转交，不运行模型。
- [x] 同一命令GREEN并核普通登记仍拒缺实体，保留证据，不提交。

### Task 2: 原短口令消费闭环

**Files:** queue_context.py、workflow_driver.py、hook_bridge.py、tests/test_queue_context.py、tests/test_foreground_watch.py、tests/test_hook_optimization.py、原泳道skill及需求/队列规则。
**Interfaces:** consume_native_watch(root, resolve_scope, perform_slice, execute)复用Task1；前台回调仅测试Agent替身，不是后台执行器。

- [x] 写单wake候选/回写、首项阻塞下一项、停前池刷新、冻结/复核/写方冲突反例并先跑RED。
- [x] 同一driver前台串行调用原claim与当前实施者；每轮重取原池，checkpoint不代替业务验收。
- [x] 修context交接文案与精确短口令上下文，普通UserPrompt/Stop保持既有边界；skill要求实际推进及停前重查。
- [x] 定向GREEN，核模型/后台/生产入口均未调用。

### Task 3: 完整回归与原落库

**Files:** 原spec/INDEX/§一#715/原§二、本批docs/codex证据。

- [x] 在codex-handoff目录python -m pytest tests -q并留JUnit；工具目录完整锁工具原测试，不在仓库根混跑。
- [x] 将七个spec场景映射真实通过用例、候选/test/hash及功能记录，原check-acceptance level=mock。
- [x] 四门禁/strict，主spec同步；仅本包tasks实际全勾后归档。持锁完成#715/§二/结果接力，release/status；自然实跑未执行单列。
