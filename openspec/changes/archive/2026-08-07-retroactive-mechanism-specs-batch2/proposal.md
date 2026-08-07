# 机制/工具类模块补写 openspec capability（第二批：--reserve / queue_lock_pending）Proposal

## Why

队列 #195（2026-07-31 立行）取证确认 8 个机制/工具类候选缺失 openspec capability，其中 5 项已于 2026-08-04 经变更包 `retroactive-mechanism-specs` 补齐归档（`platform-service-auth-gate`/`platform-repo-root-resolution`/`aibot-decision-reminder`/`aibot-liveness-heartbeat`/`sweep-fork-alert`）。剩余 2 项——`工具-共享文档编辑锁.py` 的 `--reserve`/`--reserve-multi` 取号能力（#163）与 `wecom-aibot-service/aibot_service/queue_lock_pending.py`（#168）——当时因"近期仍在演进（#185/#192 在途），补完即过时"而有意延后，建议"待其落地后一并补"。

2026-08-07（队列 #299/#195 同车批）复核：`--reserve-multi`（#185）已于 2026-08-04 落地并稳定运行 3 天以上（协议〇.7 已据其更新为正式口径"此后新行编号一律用 `--reserve` 取"）；`queue_lock_pending.py` 自 #168（2026-07-30）落地后仅在 #286（2026-08-06）新增一个中立复用模块 `pending_jsonl.py`（不改变本模块对外行为契约，只是内部实现改为复用共享读写函数）。两者均已稳定，且均命中 CLAUDE.md §5"机制/工具类模块 openspec 触发门槛"的判据①（改变全项目口径——`--reserve` 是队列编号分配的唯一合法路径；`queue_lock_pending` 定义了机器人写队列文件时与人类编辑锁协作的语义），本变更包补齐这最后 2 项。

## What Changes

本变更**不改动任何代码**——两个模块均已在 master 上线运行，本变更只是把其现有的、已通过测试验证的行为，补写成 openspec capability spec。

- 新增 `editlock-queue-number-reservation`：`工具-共享文档编辑锁.py` 的 `--reserve`/`--reserve-multi` 原子取号能力——单/多分区预留、fail-loud（不回落可能撞号的替代计算）、预留前核对高水位线是否已滞后于文件实际内容、并发预留互不重叠、release 时校验新增行编号属于本次预留集合。
- 新增 `aibot-queue-append-lock-deferral`：`queue_lock_pending.py` 的锁忙暂存与补录能力——锁占用时暂存不丢弃、按 FIFO 保序补录、补录成功后复用完整 git 同步降级路径、每条记录独立 acquire/release、与 git 层真实失败暂存物理隔离。

**本批不含**：FI2（财务域旗舰）——其唯一实现变更包 `fi2-recon-mvp` 本身代码仍未完工（tasks.md 116[x]/13[ ]，2026-08-07 实测），已由同日队列 #299 行以 `/opsx:sync`（不归档）方式单独处理，spec 已进入 `openspec/specs/`，不属于本批范围。

## Capabilities

### New Capabilities
- `editlock-queue-number-reservation`：共享文档编辑锁的原子取号能力，杜绝多方各自算出同一新编号的撞号问题。
- `aibot-queue-append-lock-deferral`：企微机器人在编辑锁占用期间的队列行登记推迟与补录能力。

### Modified Capabilities
（无——两项均为全新能力命名，不修改任何既有 capability 的既有 Requirement。）

## 知识资产三问（强制，全景规划 §1.4 第 2 条）

1. **本流程哪些判断是人脑默会经验？**
   - "候选模块是否已稳定、可以补写"这一判断此前只存在于 #195 行的一句建议与本行的复核推理里，未形成可复用的检查清单——本变更把它显性化为"近 N 天有无改变对外行为契约的提交"这一可核验判据（见 design.md D1）。
   - `--reserve` 的"预留前核对高水位线是否已滞后于文件实际内容"（竞态防护）与"release 时校验编号属于预留集合"两条行为此前只存在于代码注释与函数文档字符串里，未显性成 spec 判据。
2. **由谁显性化？**
   - 持有人 CC（本变更执笔，逐项对照现有代码/测试写成 SHALL/MUST 语句）；Shao Peishen 后续经队列行审阅（非实时会话内拍板，遵本项目"CC 自主执行、队列行留痕供事后审阅"的既有惯例，与 `retroactive-mechanism-specs`/fix-a/b/c 等历史批次同构）。
3. **用什么方法提取？**
   - 逐模块通读现有实现代码（`_reserve_ids`/`cmd_acquire`/`_parse_reserve_multi`/`_validate_release_structure` 编号校验段；`queue_lock_pending.py` 全文）与既有测试断言，把已验证的行为原样转写为 spec 语言，不新增未经代码/测试验证的行为承诺。

## 验收与晋档条件（强制，四档口径）

- **本变更包交付后档位**：**档3（内部服务）不变**——两个模块均已在真实生产链路运行（跨桌任务队列 §一/§四 编号分配、企微机器人队列写入），本变更不改变其运行档位，只补齐其应有的 spec 记录。
- **晋档条件**：不适用——本变更不含新功能，无需晋档判定。
- **价值指标**：`openspec validate --all --strict` 覆盖率——队列 #195 原始 8 候选，补写前 0，`retroactive-mechanism-specs` 批补 5，本批补齐最后 2（FI2 走 #299 独立 sync 路径，不计入本批），累计 7/8（FI2 视为"随其自身变更包正常归档流程产出"，非本轮遗漏）。
- **LLM 判据黄金集**：不适用（两个模块均为确定性规则代码，不含 LLM 判断）。

## Impact

- **受影响代码**：无（纯 spec 补写，零代码改动）。
- **受影响文档**：仅新增 `openspec/specs/` 下 2 个新 capability 目录；不改动任何既有 spec。
- **原始实现出处**（供交叉核实，非本次改动）：
  - `editlock-queue-number-reservation` ← `0-学习与工具/工具-共享文档编辑锁.py`（`_reserve_ids`/`cmd_acquire`/`_parse_reserve_multi`/`_validate_release_structure`，队列 #163/#185）
  - `aibot-queue-append-lock-deferral` ← `5-平台底座/wecom-aibot-service/aibot_service/queue_lock_pending.py`（队列 #168，#286 内部复用 `pending_jsonl.py` 不改变对外契约）
- **合规红线核对**：不涉及 mock/真实库切换、不改 audit 契约、不涉及 OEM 隔离、不涉及 L2 门禁、不涉及 ISO 26262——纯文档补写。
