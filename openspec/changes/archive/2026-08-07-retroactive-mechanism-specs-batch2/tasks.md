## 1. 补写 capability spec（纯文档，零代码改动）

- [x] 1.1 `editlock-queue-number-reservation`——对照 `工具-共享文档编辑锁.py` 的 `_reserve_ids`/`cmd_acquire`/`_parse_reserve_multi`/`_validate_release_structure` 编号校验段与现有测试
- [x] 1.2 `aibot-queue-append-lock-deferral`——对照 `queue_lock_pending.py` 与现有测试

## 2. 收尾

- [x] 2.1 `openspec validate retroactive-mechanism-specs-batch2 --strict` 通过
- [x] 2.2 `/opsx:archive`（本变更零代码改动，无需跑测试回归；`openspec validate --all --strict` 复核不引入新失败）
- [x] 2.3 队列 #195 行回填：本批完成范围（2 项）+ 累计完成（7/8，FI2 走 #299 独立 sync 路径）+ 理由
