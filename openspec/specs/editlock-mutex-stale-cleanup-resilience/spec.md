# editlock-mutex-stale-cleanup-resilience Specification

## Purpose
TBD - created by archiving change editlock-mutex-stale-cleanup-resilience. Update Purpose after archive.
## Requirements
### Requirement: 陈旧 mutex 清理失败不得跳过等待超时判断
`_acquire_mutex` 在判定内部互斥 mutex 陈旧（年龄 > `MUTEX_STALE_SECONDS`）并尝试清理时，SHALL 仅在清理**确认成功**（canonical mutex 路径已不存在）后才重试原子创建；清理失败时 SHALL NOT 无条件跳过等待超时（`MUTEX_WAIT_TIMEOUT_SECONDS`）判断，MUST 落到既有的 deadline 判断逻辑——到点即抛 `TimeoutError`，未到点按既有轮询间隔（`MUTEX_POLL_SECONDS`）重试。

#### Scenario: 清理彻底失败（unlink 与退路均失败），超时窗口内 fail-loud
- **WHEN** 一枚 mutex 已陈旧（年龄 > `MUTEX_STALE_SECONDS`），且清理该 mutex 的所有已知路径（含 `unlink` 与 rename-away 退路）均以 `OSError` 失败
- **THEN** `_acquire_mutex` SHALL NOT 无限循环、零输出地挂起；SHALL 在 `MUTEX_WAIT_TIMEOUT_SECONDS` 到点时抛出 `TimeoutError`，异常消息 MUST 包含目标 mutex 路径

#### Scenario: 清理成功后立即重试并可正常接管
- **WHEN** 一枚 mutex 已陈旧，且清理动作（`unlink` 或退路）成功清空了 canonical 路径
- **THEN** `_acquire_mutex` SHALL 立即重试 `O_CREAT|O_EXCL` 原子创建，无需等待完整的 `MUTEX_WAIT_TIMEOUT_SECONDS`

### Requirement: 无删除权限环境下的清理退路
当 `unlink()` 因权限或其它 `OSError` 失败时，`_acquire_mutex` 的陈旧 mutex 清理逻辑与 `release` 路径的释放逻辑 MUST 尝试一条不依赖删除权限的退路（`os.replace` 原子改名到固定伴生路径），使 canonical mutex 路径能够被清空，让后续 `acquire` 不必等待完整的陈旧超时窗口即可命中空闲路径。退路目标路径 SHALL 为同一目标文件固定复用的一个路径（不得每次清理事件生成一个新文件名），避免清理事件累积产生无界数量的遗留文件。

#### Scenario: unlink 因无删除权限失败，rename-away 退路成功清空 canonical 路径
- **WHEN** `unlink()` 对 mutex 文件抛出 `OSError`（如 Cowork 沙箱挂载目录无删除权限），且改名到固定伴生路径的 `os.replace` 调用成功
- **THEN** canonical mutex 路径 SHALL 不再存在；下一次针对该路径的 `O_CREAT|O_EXCL` 创建 SHALL 能够成功

#### Scenario: release 路径同步使用退路，不必等待陈旧超时
- **WHEN** 持有者释放互斥（`_acquire_mutex` 的 `finally` 块执行），且 `unlink()` 因无删除权限失败
- **THEN** SHALL 尝试同一退路（`os.replace` 到固定伴生路径）清空 canonical 路径；成功时下一次 `acquire` SHALL 无需等待 `MUTEX_STALE_SECONDS` 即可直接创建成功

#### Scenario: 多个等待者并发清理同一陈旧 mutex，不产生双持有
- **WHEN** 两个及以上等待者同时判定同一 mutex 陈旧并尝试清理
- **THEN** 至多一个清理调用能够实际清空 canonical 路径（其余调用因源文件已被移走而收到 `OSError`，视为清理失败、不得据此假定自己已清空路径）；后续争夺 canonical 路径上 `O_CREAT|O_EXCL` 的创建权仍然是唯一的互斥判定点，SHALL NOT 出现两个调用方同时认为自己持有互斥的情况

