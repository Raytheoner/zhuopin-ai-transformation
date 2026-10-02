# 【Codex】D3：生产进程终止证据与 fail-closed 消费

## Context

本设计只定义 #648 同一 Workflow 内单次 context_stopped 承接的 D3 前置条件；D3 通过不是承接许可、阶段成功或交付验收。其他承接条件仍须由经批准的整体设计独立满足。本工作树未提供旧单次承接设计包，本包不重建 D1/D2 或借旧授权补全实现范围，也不接触 v2 现场。

源码依据：`0-学习与工具/codex-handoff/model_provider.py`，读取时 HEAD 为 `8c041bb2b2798f9c8ebb74a81f8aa8a9870805a5`，文件 SHA256 为 `38e2d3e8e3e66692ed4223a5cbb220677824928cce071af8a0b07e65f3817290`。此锚仅说明设计依据，不是实现授权。

| 当前源码位置 | 实际行为及局限 |
|---|---|
| `run()` 创建 Popen 后写 process.json | 仅 `pid`、`started_at`；后者取自 Popen 之前的 provider 起始时间，不是 OS 创建时间，不能防 PID 重用 |
| `stop_child()` 首次 poll | 已退出即直接返回，不调用 taskkill 或显式 wait，不证明后代全部退出 |
| Windows subprocess.run | argv 为 `taskkill /PID <proc.pid> /T /F`，capture_output=True、timeout=15；当前 returncode/stdout/stderr 均未落盘 |
| taskkill 非零且 proc 仍活 | 回退 `proc.kill()`，仅直接子进程，不得等价为树终止 |
| `proc.wait(timeout=15)` | 由 provider 父进程等待其直接子进程；可超时/抛错，不等待所有后代 |
| run 异常与结果分支 | 清理异常进 error；只要 context_reason 非空，status 仍优先写 context_stopped。因此该 status 不是终止证明 |

术语：“父进程 wait”指 provider 对持有的 `Popen` 调用 wait；被等待对象是 taskkill 所针对进程树的根，不是等待 provider 自己退出。

## Goals / Non-Goals

目标是给 D3 一个可由生产路径真实生成、可由外层确定性复核的最小契约。终止证据不得由模型补写，不能以测试夹具 JSON、PID 不存在、turn.completed、退出码 0 或 context_stopped 单项代替。

不修改阈值和超时，不增加自动重试、常驻服务、跨任务恢复或 thread resume，不实施 Job Object 管理，不承诺捕获脱离进程树的任意后台进程。本阶段不运行进程终止试验，不修改 provider 或 Workflow。

## Decisions

### D3.1 方案选择与证明边界

采用“现有 taskkill 原始结果 + 同一个 Popen 的后续 wait + attempt 绑定”的契约。仅凭 PID 查询或 wait 成本低但不能证明树终止，拒绝采用；Job Object 可提供更强的生命周期约束，但改变进程创建机制，超出本次 D3 修订范围。

`tree_termination_confirmed` 的精确定义是：Windows taskkill 对本次持有根进程执行 `/T /F` 成功返回，且随后 provider 成功回收该根进程。它是 OS 命令成功报告与根进程回收的联合证据，不是对所有逃逸后代做过穷举证明。未来若要求绝对无逃逸进程，须另行设计，不能扩大本字段含义。

### D3.2 证据载体与生产者

保留 `process.json` 的原字段，新增版本化身份字段：`evidence_version: 1`、`attempt_id`、`source_id`、规范化绝对 `workspace`、`request_sha256`。`attempt_id` 由外层已持有的 Workflow attempt 传给 provider；`request_sha256` 是本 attempt 已落盘 request.json 的原始字节 SHA256。`pid` 必须为正整数且拒绝 bool；`started_at` 标明 UTC provider 启动时间，不冒充 OS 创建时间。

provider 的 `result.json` 新增 `termination` 对象，以下均是拟新增契约，当前源码尚未实现：

| 字段 | 生产约束 |
|---|---|
| `evidence_version`, `attempt_id`, `source_id`, `workspace`, `pid`, `process_sha256` | 与 process.json 及外层 attempt 一致；process_sha256 为该文件最终原始字节哈希 |
| `trigger`, `requested_at`, `finished_at`, `platform` | trigger 为本次 context_reason；UTC 时间由 provider 采集；Windows 正例限定 platform=win32 |
| `attempts` | 有序清理调用记录；异常分支重入不得覆盖或抹掉首个失败；每项含序号、开始/结束 UTC、poll_before、taskkill、fallback、wait、error |
| `taskkill` | invoked、argv、timeout_seconds=15、returncode、stdout_base64、stderr_base64、对应原始字节 SHA256、timed_out、error；未调用明确 invoked=false，其他未知值为 null |
| `fallback` | invoked、method、error；proc.kill 若发生必须记录，不能称树终止 |
| `wait` | invoked、timeout_seconds=15、returned、returncode、poll_after、timed_out、error、开始/结束 UTC；必须源自同一 Popen 实际观察 |
| `outcome` | 只能取 tree_termination_confirmed、parent_exited_only、termination_failed、termination_unknown；由下述谓词推导，非自由文本自述 |

stdout/stderr 使用 base64 无损保存 taskkill 的 bytes，不依赖 Windows 本地化文字解析。空输出允许，但仍须带空字节哈希；缺失输出不得当作空输出。taskkill 超时保存可取得的部分输出并标 timed_out，不伪造 returncode。wait 返回码可以非零，强杀后的非零不等于 wait 调用失败；taskkill 自己的 returncode 则必须为整数 0。

在 stop 请求前先持久化 pending 终止记录（outcome=termination_unknown）；动作发生后更新实测字段，最后使用已有 write_json 的临时文件 replace 机制写完整 result。证据写入失败仍尽力清理自己持有的进程，但无完整报告就禁止承接。崩溃留下 pending、临时件或缺失 result 均不放行。沿用既有文件名及临时文件形态，不新增独立日志。

### D3.3 生产顺序与异常语义

1. 外层创建唯一 attempt 与独立 evidence 目录，先封存 task/phase/workspace/request 关联；provider 保存 process.json，持有原 Popen 引用。
2. context_guard 触发时记录原因与 pending；终止只针对该 Popen 的 PID，禁止从外部 JSON 取任意 PID 去 kill，禁止按名称清理。
3. 首次 poll 已退出：记录 parent_exited_only，不执行旧 PID 的 taskkill；不能据此推断树已结束。
4. 仍活动：执行既有 Windows taskkill；捕获命令自身结果，再调用并记录父进程 wait。非零、异常、超时及 fallback 全保留；清理尝试可继续，但本 attempt D3 保持失败，不通过第二次成功洗白第一次失败。
5. 汇总 result；保留原 context_reason/status 用作停止原因，单独记录终止是否被证明。即使 status=context_stopped 也不得绕过 termination 验证。
6. provider 返回后，外层封存 process/result/request 原始文件 SHA256，再进入只读 D3 验证。模型可写工作树不能成为终止证据生产者；证据使用外层既有受保护运行目录，本阶段不访问该目录。

### D3.4 消费接受谓词

仅当以下全部成立，D3 返回 satisfied；否则返回 blocked_unknown 或 blocked_termination，并且不启动下一个模型、不删除不确定锁、不写“承接完成”。D3 不自行调用 recover 或修改阶段状态。

1. 外层已确认此 task/phase/attempt 是本次 context 停止候选；task、attempt、source_id、workspace、request 哈希及 process PID 全匹配，拒绝跨 task/attempt/thread 拼接。thread 关联沿用 session.json 与现有原生证据闸，不新造 thread。
2. process/result/request 来自外层指定的同一 evidence 目录；解析为受支持版本且必需字段类型严格正确；文件字节与外层封存哈希一致，process 的引用哈希一致。拒绝证据路径逃逸、错文件、缺字段及后写漂移。
3. result.status=context_stopped，context_reason 与 trigger 一致，result.error 为空且 timed_out=false；reason 是否允许单次承接继续交既有整体设计判断，D3 不扩大 reason 白名单。
4. 唯一终止调用记录的 poll_before=null；Windows taskkill invoked=true，argv 精确对应 process.pid 的 `/PID … /T /F`，returncode 为整数 0（非 bool）；无超时或异常，原始输出及哈希完整；fallback.invoked=false。
5. 其后的 wait.invoked=true、returned=true，无超时或异常；wait.returncode、poll_after、result.exit_code 都为非 bool 整数且相等。wait 不要求返回 0。
6. 时序满足 provider started_at ≤ requested_at ≤ taskkill 开始 ≤ taskkill 结束 ≤ wait 开始 ≤ wait 结束 ≤ finished_at ≤ result.ended_at；内部序号一致。时间异常或倒退阻断，不拿时间替代 attempt 身份。
7. 消费方依据 1–6 自行算出 tree_termination_confirmed，结果与报告 outcome 一致。不能仅检查 outcome=true 类声明；人工补填的生产证据无效。

外层封存哈希保证封存后未变，并不单独证明生产者可信；生产者身份依赖已有 provider 调用、专有 evidence 目录与当前 attempt 生命周期。这些关联不可核验时 fail closed，禁止用旧 process.json 的 pid+started_at 临时推断。

### D3.5 必须拒绝的边界

| 输入或故障 | D3 结果 |
|---|---|
| taskkill=0，wait 成功返回非零，完整同 attempt 证据 | satisfied，仅通过终止子闸 |
| taskkill 非零，根随后自行退出或 fallback kill 成功 | blocked_termination；父退出不替代树成功 |
| taskkill 超时/权限拒绝/无法启动；wait 超时/抛错 | blocked_termination；保留原始结果与所有清理尝试 |
| poll 一开始已退出；只有 PID 不存在观察 | blocked_unknown；不杀可能重用的 PID |
| provider 崩溃、写盘失败、result 不完整或缺生产封存 | blocked_unknown；保留锁与现场 |
| 旧版 process.json、未知版本、错 PID/attempt/workspace/hash、摘要自称成功 | blocked_unknown；不补造旧证据 |
| 非 Windows proc.kill + wait | 本契约不满足；不冒充 Windows 树终止 |
| error 含 cleanup failed 但 status=context_stopped | blocked_termination；停止原因不能掩盖清理失败 |

## Validation Strategy

先在隔离测试夹具中驱动真实 provider 写入函数，再由真实 D3 消费函数回读；不允许正例仅靠手写一份“全绿 JSON”。单测注入 taskkill/Popen 观察，覆盖上表及字段逐项破坏；另设 Windows 隔离父子进程集成验证，真实执行 taskkill /T /F 后记录 wait，并以测试侧子进程句柄独立观察夹具已退出。只终止测试自身创建的进程，不触碰生产/v2。

集成验证还需覆盖首次已退出、taskkill 失败与 wait 超时；故障注入留原始错误，不能把 mock 的结果声称为原生 OS 实测。CI 依实际 `.github/workflows/ci.yml` 与项目选择器确认受影响子项目，固定该项目 cwd 与 node-id，保留命令、stdout/stderr、退出码、哈希；不在根混跑。本阶段不执行以上测试。

外层另运行 `openspec validate "workflow-context-continuation-op-0929-x-v3" --strict` 并封存回显和退出码；该命令此处仅记录待执行验证，不表示已运行或通过。

## Risks / Trade-offs

- 对自然退出和 taskkill 非零竞态保守阻断，牺牲自动承接可用性以避免并发旧进程；不在本包增加宽松恢复分支。
- taskkill 成功报告不是防逃逸容器；若业务要求超过此证明边界，应拒绝基于本契约上线并另审更强方案。
- 新版本报告不兼容旧证据是有意的 fail-closed 行为；禁止迁移、补填或重放 v2 现场。
- 此处生产表示将来真实 provider 生成的证据，不表示已经在生产验收。

## Migration Plan

本阶段只写设计；无运行状态迁移。外层 strict 后停在设计审，实施须针对新的 design HEAD、设计文件集合 SHA256 和 allowed_paths 另行批准。实施失败保持旧运行策略并停止承接，不清理旧锁或旧 attempt。ff、部署、外发、L2 均不在本包授权内；部署只引用 zhuopin-lan-closeout 正本。

## Open Questions

进入实现前需在设计审明确：接受 D3.1 的证明边界、确认实际复核责任人与逐文件 allowed_paths。任何未满足项均不启动实现。暂不归档：设计未批准且验证未执行。
