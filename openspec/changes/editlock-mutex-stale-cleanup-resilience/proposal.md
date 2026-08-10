# editlock-mutex-stale-cleanup-resilience Proposal

## Why

队列 #322（2026-08-10 拆件巡逻实测坐实，P1）：`工具-共享文档编辑锁.py::_acquire_mutex` 判定内部互斥 mutex 陈旧（>`MUTEX_STALE_SECONDS`=10s）后会尝试 `unlink()` 强制接管；若 `unlink()` 抛 `OSError`（Cowork 沙箱对挂载目录**没有删除权限**，实测连自建临时文件都 `PermissionError`，但 `rename` 可用）——现有代码是 `except OSError: pass` 之后**无条件 `continue`**，这个 `continue` 跳过了紧随其后的 `deadline` 判断，于是 `MUTEX_WAIT_TIMEOUT_SECONDS=5` 形同虚设：**不是超时报错，是无限循环、零输出**。

组合后果：Cowork 每成功占一次锁，`finally` 释放时同样因无删除权限而 `unlink` 静默失败（同一 `except OSError: pass` 模式），把 mutex 文件遗留在原地；下一个 Cowork session 对同一目标文件 `acquire` 时，一旦触及这个陈旧 mutex 的清理分支就直接卡死——**不是变慢，是永久挂起**。本次巡逻开工时发现 5 枚遗留 mutex（财务域/采购域接力已卡 3 天、Phase1收口接力/队列/README 各一），只能用 `os.rename` 手工挪走恢复，这是绕过工具的人工急救，不是修复。Windows 侧因为能正常删除、10 秒后自动接管，此前从未暴露——本条属根 CLAUDE.md §5「工具静默回退」家族的又一变种：外观是卡住不动，不报任何错。

**已用两条证伪命令复核前提仍成立**（开工原样重跑）：① 环境事实——沙箱/只读文件确实 `unlink` 恒失败；② 死循环——对一枚 stale 且不可删的 mutex 跑 `acquire`，在 Windows 上用只读属性模拟"删不掉"环境本地复现：进程被 `timeout 15` 杀掉、退出码 124、**全程零输出**，与队列行描述的失败形态完全吻合。

## What Changes

- **stale-mutex 清理分支（`FileExistsError` 判定超龄之后）**：不再"尝试 unlink → 无论成败都 `continue`"，改为统一走一个清理助手——**优先 `unlink()`；失败则退路为 `os.replace()` 把 mutex 原子改名挪到一个固定的 `.stale` 伴生路径**（同一目标文件复用同一伴生文件名，`os.replace` 覆盖式改名，不随每次 stale 事件新增一个文件、避免无界堆积）。只要清理助手判定"canonical 路径已清空"（无论是靠 unlink 还是靠改名），才 `continue` 重试原子创建；**两条路都失败时不再 `continue`**，落到既有的 `deadline` 判断——到点即 `TimeoutError`，未到点正常 `sleep` 后重试，恢复"fail-loud，禁止静默死循环"的原始设计意图。
- **release 路径（`finally` 块）同步加固**：现状同样是 `unlink` 失败即 `except OSError: pass`，把 mutex 遗留在原地、等下一次 acquire 撞见后再靠 stale 超龄判定接管（Cowork 环境下每次 release 后都要浪费一整个 `MUTEX_STALE_SECONDS` 窗口）。改为复用同一清理助手：`unlink` 失败时立即尝试 `os.replace` 挪到 `.stale` 伴生路径——**Cowork 沙箱下 release 后 canonical 路径能立即清空，下一次 acquire 直接命中 `O_CREAT|O_EXCL` 快路径，不必等待/触发 stale 分支**，比现状更早、更干净地解除占用。
- **单测新增**：白盒复现"mutex 存在、`unlink` 恒失败"场景（借用既有 `AcquireMutexInternalsTests` 白盒测试类），验证：① 该场景下 `_acquire_mutex` 在 `MUTEX_WAIT_TIMEOUT_SECONDS` 内要么成功接管、要么抛 `TimeoutError`，不得挂起；② canonical mutex 路径确实被清空（改名到 `.stale` 伴生文件，而非留在原地）；③ 正常路径（可删除环境）行为不回归。
- **顺手清理**：删除本次拆件巡逻遗留在库内的沙箱 junk 文件 `1-转型规划/0-全景路线图/__cowork沙箱遗留-待CC删除.tmp`（0 字节，已被 08-10 第二班巡逻批次意外提交入库——原巡逻报告的"勿提交入库"意图未达成，本次一并 `git rm` 收口）。与本变更的技术决策无关，随本次 commit 一并处理。
- **BREAKING**：无——`_acquire_mutex` 对外行为从"某些环境下永久挂起（bug）"变为"要么成功接管、要么在超时窗口内 fail-loud 抛 `TimeoutError`（原始设计意图）"，是修复而非行为收窄；调用方（`acquire`/`release`/`--reserve` 等所有经过 `_acquire_mutex` 临界区的路径）无需改动，异常类型不变（`TimeoutError` 本就是既有契约的一部分，只是此前在 Cowork 环境下从未真正被触发过）。

## Capabilities

### Added Capabilities

- `editlock-mutex-stale-cleanup-resilience`：陈旧 mutex 清理与 release 路径在无删除权限环境下必须有可用退路，且清理失败时不得跳过等待超时判断（不得静默死循环）。

## 知识资产三问（强制，全景规划 §1.4 第 2 条）

1. **本流程哪些判断是人脑默会经验？** "清理陈旧锁文件失败时该怎么办"这一权衡此前完全隐式在代码里——原实现选择了"忽略错误、假装清理成功、重试"（`except OSError: pass` 后直接 `continue`），这个选择从未被显式论证过，是随手写的默认路径，直接导致了本 bug。本变更把这一权衡显式化为固定判据：**先穷尽已知的可用退路（unlink → rename-away），全部失败才允许 fail-loud**，不再有"假装成功"的中间态。
2. **由谁显性化？** 持有人：**Shao Peishen**（design 拍板，尤其是"rename-away 伴生文件 vs 内容标记"两种退路方案的取舍，见 design.md 决策点 1）；backup：**Claude Code**（本变更的代码落地与后续任何接手 session，判断依据均已 record 在案）。
3. **用什么方法提取？** **历史案例反推**——2026-08-10 拆件巡逻实测坐实的 5 枚真实遗留 mutex（财务域/采购域接力卡 3 天）+ 本次开工用只读属性本地复现的死循环（`timeout 15` 杀掉、退出码 124、零输出），判据设计直接来自这次真实故障的取证，非预先设计。不涉及 LLM 判断。

## 本次退休哪一个既有守卫；若不能退，写明为何不能

**不退休任何既有守卫**——本变更修复的是 `_acquire_mutex` 这一互斥原语自身的正确性缺陷（把"静默假装清理成功"改为"穷尽退路后 fail-loud"），不是新增一层校验去替代或收窄某个既有校验的适用范围。当前机制里没有与本变更判断重叠、可被本变更吸收替代的姊妹守卫。与 `editlock-causal-assertion-falsifiability-gate`（2026-08-09 归档）同类先例一致——那次也是"首次机制化，无可退休对象"。

## 验收与晋档条件（强制，四档口径）

- **本变更包交付后场景所处档位**：跨项目治理机制（编辑锁互斥原语是全项目 Cowork×CC 共享写入的咽喉），非独立业务场景，不套用四档"对客交付"口径；近似映射＝**档1 mock 验证**（design 记录完成、代码与单测完成，单测用只读文件属性/mock 模拟"删不掉"环境，尚未在真实 Cowork 沙箱会话里端到端观察一次"本次修复自动化解了一个真实死锁场景"）。
- **晋下一档的条件**（晋档2 真实数据跑通）：① 全部既有回归零漂移（含 `AcquireMutexInternalsTests` 既有三个用例 `test_mutex_not_left_behind_after_normal_use`/`test_mutex_blocks_concurrent_holder`/`test_stale_mutex_is_reclaimed_promptly`）；② 至少一次真实 Cowork session 在 acquire 时命中一枚由本修复之前遗留的历史陈旧 mutex（如本次巡逻发现的 5 枚之一，若届时仍未被人工清理），验证被自动接管而非再次卡死；③ 至少一次真实 Cowork session 在 release 后确认 canonical mutex 路径已清空（不必等待 `MUTEX_STALE_SECONDS`）。
- **价值指标**（风险型）：消除"下一个 Cowork session 对同一文件 acquire 永久卡死"这一 P1 故障模式。基线＝已知产生 5 次真实卡死遗留（08-07～08-10 累积最长 3 天，均靠人工 `os.rename` 急救）；目标＝此后同类场景 100% 在 `MUTEX_WAIT_TIMEOUT_SECONDS`（5s）内收敛（自动接管成功，或 fail-loud 报错），不再出现"零输出、无限挂起"的形态。
- **LLM 判据黄金集**：不适用（纯文件系统操作与异常处理，不含 LLM 运行时判断）。

## Impact

- **受影响代码**：`0-学习与工具/工具-共享文档编辑锁.py::_acquire_mutex`（约 L479-517，stale 清理分支 + `finally` release 块）＋ 新增清理助手函数。
- **受影响测试**：`0-学习与工具/test_工具-共享文档编辑锁.py`（`AcquireMutexInternalsTests` 新增"unlink 恒失败"场景正反例）。
- **受影响文档**：模块顶部 docstring 补充说明（比照 #121(a) `.editlock` "改写为释放标记、不删除"先例的行文风格）；队列 #322 行回填完工状态；本次一并 `git rm` 沙箱遗留 junk 文件（与本变更技术决策无关的顺手清理，见 What Changes 末条）。
- **红线核对**：mock 先行——不适用（纯工具内部机制，非业务场景）；audit 留痕——不适用（不是业务决策，是队列文件写入侧的互斥原语）；OEM 隔离——不适用；L2 人工确认门禁——不适用；ISO 26262——不适用（非车规安全相关代码）。
