## 0. design 审前置

- [ ] 0.1 **待 Shao Peishen 审 design.md 决策点 1**（清理退路机制：推荐候选 A "rename-away 到固定伴生路径"，候选 B "内容标记" 因削弱互斥正确性边界不推荐，候选 C "不设退路" 无法解决核心诉求）——**本变更 apply 阶段前必须等到拍板，不得按默认值直接开工**（与本项目多数机制类变更包不同，此决策此前未经任何讨论，无默认执行项）。

## 1. 单测先行

- [ ] 1.1 白盒复现"mutex 存在、unlink 恒失败"场景（借用既有 `AcquireMutexInternalsTests`，用只读文件属性或 mock `Path.unlink` 模拟权限失败）：验证 `_acquire_mutex` 在 `MUTEX_WAIT_TIMEOUT_SECONDS` 内要么成功接管、要么抛 `TimeoutError`，不得挂起（须设置测试自身的超时保护，避免回归时死循环拖垮整个测试进程）。
- [ ] 1.2 验证清理成功场景下 canonical mutex 路径确实被清空（rename-away 到固定伴生路径），且不重复生成新文件名（同一目标文件多次陈旧清理事件复用同一伴生路径）。
- [ ] 1.3 release 路径同步验证：无删除权限时 `finally` 块释放后 canonical 路径清空，下一次 acquire 不必等待 `MUTEX_STALE_SECONDS`。
- [ ] 1.4 既有三个白盒用例（`test_mutex_not_left_behind_after_normal_use`/`test_mutex_blocks_concurrent_holder`/`test_stale_mutex_is_reclaimed_promptly`）与黑盒并发用例（`test_concurrent_acquire_many_processes_exactly_one_winner`/`test_concurrent_stale_takeover_exactly_one_winner`）全量回归零漂移。

## 2. 实现

- [ ] 2.1 新增清理助手函数（unlink 优先，失败则 `os.replace` 到固定 `.stale` 伴生路径，两者皆失败返回失败标志）。
- [ ] 2.2 stale-mutex 清理分支改用助手函数：仅清理成功才 `continue`；失败不再无条件 `continue`，落到既有 deadline 判断。
- [ ] 2.3 `finally` release 块同步改用助手函数。
- [ ] 2.4 模块 docstring 补充说明（比照 #121(a) `.editlock` 先例行文风格，注明退路机制与不引入的正确性风险边界）。

## 3. 顺手清理（与技术决策无关，可独立于 0.1 拍板先行）

- [x] 3.1 `git rm` 沙箱遗留 junk 文件 `1-转型规划/0-全景路线图/__cowork沙箱遗留-待CC删除.tmp`（已确认被 08-10 第二班巡逻批次意外提交入库）。

## 4. 验证

- [ ] 4.1 全量回归：`0-学习与工具/test_工具-共享文档编辑锁.py` 零漂移。
- [ ] 4.2 `openspec validate editlock-mutex-stale-cleanup-resilience --strict` 通过；`openspec validate --all --strict` 全绿。

## 5. 收工

- [ ] 5.1 队列 #322 行回填完工状态。
- [ ] 5.2 `/opsx:archive editlock-mutex-stale-cleanup-resilience -y`。
