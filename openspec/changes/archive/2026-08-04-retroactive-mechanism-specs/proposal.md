# 机制/工具类模块补写 openspec capability Proposal

## Why

2026-07-31 Shao Peishen 追问"整个 workflow 好像没看到 openspec 先行更新 Spec 再引导 coding 的环节？我们的 Spec 是否 up to date？"——队列 #195 取证结论：他没弄错。openspec 全库 182 个 `.md` 递归扫描证实：业务场景类走得全（`specs/` 31 个 capability），但**平台底座/机制类完全没走 openspec**——`simple_gate.py`（#160 四服务鉴权门禁）、`repo_paths.py`（#126 仓库根解析）、`decision_reminder.py`（#172）、`liveness.py`（#147）、sweep 分叉告警（#171）等模块均已实现、测试、部署，却从未产出对应 capability spec。

CLAUDE.md §5 已于 2026-08-02 补一条判据：机制/工具类模块命中"改变全项目口径／涉鉴权与数据可见性／改变既有模块对外语义"三类之一即必走 openspec。本变更包是对该判据的**回溯性补课**——五个已实现模块逐项复核后确认均命中（#160 涉数据可见性、#126 改变全项目仓库根解析口径、#172/#147/#171 均改变既有巡检/sweep 机制的对外行为契约），补写 capability spec，使这些已生产运行的机制纳入"单一可信源"审计范围。

## What Changes

本变更**不改动任何代码**——五个模块均已在 master 上线运行（#160/#126/#172/#147/#171 各自的原始队列行与提交记录见 Impact 段），本变更只是把它们现有的、已通过测试验证的行为，补写成 openspec capability spec。

- 新增 `platform-service-auth-gate`：`simple_gate.py` 共享口令门禁的判据（双通道鉴权）、程序化访问豁免清单、已知残余风险三段。
- 新增 `platform-repo-root-resolution`：`repo_paths.py` 跨 checkout 仓库根解析优先级与统一落点。
- 新增 `aibot-decision-reminder`：`decision_reminder.py` 新增/超期判据、去重升级间隔、主备通道降级。
- 新增 `aibot-liveness-heartbeat`：`liveness.py` 独立存活戳周期、审计隔离、失败降级。
- 新增 `sweep-fork-alert`：`工具-落库sweep.py` 的 `SweepAbort.is_fork` 分叉告警机制——检测标记、连续轮次持久化、告警失败不阻塞。

**本批不含**（有意排除，理由见 design.md）：
- `--reserve` 取号能力（#163）与 `queue_lock_pending.py`（#168）——两者近期仍在演进（#185/#200/#229 在途），补写后大概率立即过时，队列 #195 行本身建议"等其落地后一并补"。
- FI2（财务域旗舰）——其唯一未归档的实现变更包 `fi2-recon-mvp` 本身尚未完工（106[x]/11[ ]），spec 应随该包正常归档流程自然产出，不属于"补写遗漏"，而是"还没做完"（与 #196 处理的 fix-a/b/c 情形不同：那三个包代码已完工只差 openspec 手续，FI2 是代码本身未完工）。

## Capabilities

### New Capabilities
- `platform-service-auth-gate`：四个内网 Flask 服务共享口令门禁（临时止血，非正式鉴权）的判据、豁免清单、残余风险。
- `platform-repo-root-resolution`：跨 checkout（独立 worktree/主工作区）动态解析真实仓库根，替代不可靠的 `__file__` 反推。
- `aibot-decision-reminder`：企微机器人"需 Shao Peishen 决策项"新增/超期主动提醒，1/3/7 天递减去重。
- `aibot-liveness-heartbeat`：企微机器人独立存活戳心跳，与审计事件流物理隔离。
- `sweep-fork-alert`：落库 sweep 起跑前置分叉检测告警与连续轮次持久化。

### Modified Capabilities
（无——五项均为全新能力命名，不修改任何既有 capability 的既有 Requirement。）

## 知识资产三问（强制，全景规划 §1.4 第 2 条）

1. **本流程哪些判断是人脑默会经验？**
   - "机制/工具类模块何时够格走 openspec"这一判据本身，此前只存在于 CLAUDE.md §5 一段新增文字与队列 #195 一次性取证里，尚未通过"回溯补写"这个动作验证其可操作性——本变更是该判据落地后的第一次实践检验。
   - #160 门禁的"豁免清单"（哪些路径不需要鉴权）此前只在代码注释与 `install_flask_gate` 默认参数里，未显性成文档化的判据。
2. **由谁显性化？**
   - 持有人 CC（本变更执笔，逐项对照现有代码/测试写成 SHALL/MUST 语句）；Shao Peishen 后续经队列行审阅（非实时会话内拍板，遵本项目"CC 自主执行、队列行留痕供事后审阅"的既有惯例，与 fix-a/b/c 等历史批次同构）。
3. **用什么方法提取？**
   - 逐模块通读现有实现代码与既有测试断言，把已验证的行为原样转写为 spec 语言（不新增未经代码/测试验证的行为承诺）——凡代码未覆盖或测试未断言的行为，一律不写入 SHALL/MUST。

## 验收与晋档条件（强制，四档口径）

- **本变更包交付后档位**：**档3（内部服务）不变**——五个模块均已在真实生产链路运行（`.51` 四服务鉴权/企微机器人服务），本变更不改变其运行档位，只补齐其应有的 spec 记录。
- **晋档条件**：不适用——本变更不含新功能，无需晋档判定。
- **价值指标**：`openspec validate --all --strict` 覆盖率——补写前平台底座/机制类 0 capability，补写后 5 个（`--reserve`/`queue_lock_pending`/FI2 三项有意延后，见 What Changes）。
- **LLM 判据黄金集**：不适用（五个模块均为确定性规则代码，不含 LLM 判断）。

## Impact

- **受影响代码**：无（纯 spec 补写，零代码改动）。
- **受影响文档**：仅新增 `openspec/specs/` 下 5 个新 capability 目录；不改动任何既有 spec。
- **原始实现出处**（供交叉核实，非本次改动）：
  - `platform-service-auth-gate` ← `5-平台底座/zhuopin_platform/zhuopin_platform/shared_tools/simple_gate.py`（队列 #160，`four-services-temp-auth` 批次）
  - `platform-repo-root-resolution` ← `5-平台底座/wecom-aibot-service/aibot_service/repo_paths.py`（队列 #126）
  - `aibot-decision-reminder` ← `5-平台底座/wecom-aibot-service/aibot_service/decision_reminder.py`（队列 #172）
  - `aibot-liveness-heartbeat` ← `5-平台底座/wecom-aibot-service/aibot_service/liveness.py`（队列 #147）
  - `sweep-fork-alert` ← `0-学习与工具/工具-落库sweep.py` 的 `SweepAbort`/`_handle_fork_detected`（队列 #171）
- **合规红线核对**：不涉及 mock/真实库切换、不改 audit 契约、不涉及 OEM 隔离、不涉及 L2 门禁、不涉及 ISO 26262——纯文档补写。
