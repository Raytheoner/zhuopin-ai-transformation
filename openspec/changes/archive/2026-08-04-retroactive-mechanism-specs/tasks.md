## 1. 补写 capability spec（纯文档，零代码改动）

- [x] 1.1 `platform-service-auth-gate`——对照 `simple_gate.py` 现有实现与测试，写判据/豁免清单/残余风险三段
- [x] 1.2 `platform-repo-root-resolution`——对照 `repo_paths.py`
- [x] 1.3 `aibot-decision-reminder`——对照 `decision_reminder.py`
- [x] 1.4 `aibot-liveness-heartbeat`——对照 `liveness.py`
- [x] 1.5 `sweep-fork-alert`——对照 `工具-落库sweep.py` 的 `SweepAbort`/`_handle_fork_detected`

## 2. 收尾

- [x] 2.1 `openspec validate retroactive-mechanism-specs --strict` 通过
- [x] 2.2 `/opsx:archive`（本变更零代码改动，无需跑测试回归；`openspec validate --all --strict` 复核不引入新失败）
- [x] 2.3 队列 #195 行回填：已完成范围（5 项）+ 明确延后范围（`--reserve`/`queue_lock_pending`/FI2）+ 理由
