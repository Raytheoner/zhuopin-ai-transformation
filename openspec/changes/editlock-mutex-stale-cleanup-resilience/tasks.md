## 0. design 审前置

- [x] 0.1 **Shao Peishen 已拍板选候选 A**（"rename-away 到固定伴生路径"，2026-08-10 聊天原话回复"a"）——unlink 优先，失败退路为 `os.replace` 原子改名到固定 `.stale` 伴生路径；候选 B/C 不采用（理由见 design.md 决策点 1）。

## 1. 单测先行

- [x] 1.1 白盒复现"mutex 存在、unlink 恒失败"场景（`test_stale_mutex_unlink_always_fails_falls_back_to_rename_away`，用 `unittest.mock.patch.object(Path, "unlink", side_effect=PermissionError(...))` 模拟权限失败）：验证 `_acquire_mutex` 在 `MUTEX_WAIT_TIMEOUT_SECONDS` 内成功接管，不挂起；另补 `test_cleanup_completely_fails_raises_timeout_not_hang`（unlink 与 `os.replace` 均 mock 失败）验证两条退路都失败时在超时窗口内 fail-loud 抛 `TimeoutError`，不无限挂起。
- [x] 1.2 `test_stale_companion_path_is_fixed_not_proliferating`：验证清理成功场景下 canonical mutex 路径确实被清空（rename-away 到固定伴生路径），且 3 轮陈旧清理事件后目录内只有同一个 `.stale` 伴生文件，不重复生成新文件名。
- [x] 1.3 `test_release_falls_back_to_rename_when_unlink_fails`：release 路径同步验证——无删除权限时 `finally` 块释放后 canonical 路径立即清空，不必等待 `MUTEX_STALE_SECONDS`。
- [x] 1.4 既有三个白盒用例（`test_mutex_not_left_behind_after_normal_use`/`test_mutex_blocks_concurrent_holder`/`test_stale_mutex_is_reclaimed_promptly`）与黑盒并发用例（`test_concurrent_acquire_many_processes_exactly_one_winner`/`test_concurrent_stale_takeover_exactly_one_winner`）全量回归零漂移，均在 136 passed 内。

## 2. 实现

- [x] 2.1 新增清理助手函数 `_discard_mutex_path`（unlink 优先，失败则 `os.replace` 到固定 `.stale` 伴生路径，两者皆失败返回 `False`）。
- [x] 2.2 stale-mutex 清理分支改用助手函数：仅清理成功才 `continue`；失败不再无条件 `continue`，落到既有 deadline 判断。
- [x] 2.3 `finally` release 块同步改用助手函数。
- [x] 2.4 模块 docstring 补充 #322 说明段（比照 #121(a)/#197 先例行文风格，注明退路机制、成因与不引入双持有风险的论证）。

## 3. 顺手清理（与技术决策无关，可独立于 0.1 拍板先行）

- [x] 3.1 `git rm` 沙箱遗留 junk 文件 `1-转型规划/0-全景路线图/__cowork沙箱遗留-待CC删除.tmp`（已确认被 08-10 第二班巡逻批次意外提交入库）。

## 4. 验证

- [x] 4.1 全量回归：`0-学习与工具/test_工具-共享文档编辑锁.py` **136 passed, 5 subtests passed**，零漂移（较修改前 131 passed 净增 5 个新用例，无失败无跳过）。
- [x] 4.2 `openspec validate editlock-mutex-stale-cleanup-resilience --strict` 通过；`openspec validate --all --strict` **75/75** 全绿。

## 5. 收工

- [ ] 5.1 队列 #322 行回填完工状态。
- [ ] 5.2 `/opsx:archive editlock-mutex-stale-cleanup-resilience -y`。
