## 0. 状态：出件即停（派单件硬约束③）→ **已获批准，2026-08-26 apply 完成**

- [x] 0.1 命中 CLAUDE.md §5 openspec 门槛第③条判定完成——同一接口、同一输入，`release` 结果由拒绝变放行；直接先例＝ `2026-08-12-editlock-aibot-intake-reservation-exemption`
- [x] 0.2 真因取证：**受控复现**（非相关性推断），并与 `SWEEP_LOCK_WHO` 做对照，见 design.md「取证」节
- [x] 0.3 propose 与 design 出件完毕
- [x] 0.4 ✅ **Shao Peishen 2026-08-26 拍板（⟨就地答⟩，原文在队列 §一 #416 行内）**：⑴ 取「窄修法·身份豁免」，不动校验⑹ 度量范围；⑵ 宽修法**本次不取、但不否决**，日后单独立项时先回答「`dirty_at_acquire` 差集判据当初为何被推翻」再议。见 design.md「审批记录」。

## 1. 实现（`OP-0826-D`，2026-08-26 完成）

- [x] 1.1 `_registration_completeness_violations` 豁免分支扩至企微机器人；判据落成常量 `SELF_COMMITTING_LOCK_HOLDERS`，旁边写清它表达的是**"自行提交自身改动的持锁者"**，供下一个自动化路径挂靠
- [x] 1.2 仅豁免本项；**不豁免 `dirty_now is None` 的 fail-closed 分支**——实现上体现为**代码位置**：身份豁免写在 `dirty_now is None` 之后、`uncovered` 判定之处，不是函数开头
- [x] 1.3 代码注释指向"宽修法"候选（度量范围收窄为持锁者自身改动），并写明本次不取的三条理由，避免止血后无人再根治
- [x] 1.4 ⚠️ **`SWEEP_LOCK_WHO` 那一支刻意未动**：它抢在 fail-closed 之前返回（2026-08-23 既有行为），挪过来等于**收紧 sweep 的既有判定**，属本包范围外的对外行为改变，须单独立项——已在常量注释里如实登记，未顺手扩范围

## 2. 单测（2026-08-26 完成，全绿）

- [x] 2.1 机器人 ＋ 他人脏文件 → 放行（`test_aibot_identity_is_exempt_from_others_dirty_files`，复现 #416 ⑶ 真实事故场景）
- [x] 2.2 🔴 **反例**：人类会话 ＋ 未覆盖脏文件 → 仍拒绝（`test_human_session_still_blocked_by_uncovered_dirty_file`）
- [x] 2.3 反例：机器人 ＋ 其它校验违规 → 仍拒绝（`test_aibot_registration_exemption_does_not_cover_other_checks`，真 git 仓库 ＋ 真 acquire/release，场景刻意做成"⑹ 本会放行、①列数会拦"）
- [x] 2.4 反例：机器人 ＋ 取数失败 → 仍 fail-closed 拒绝（`test_aibot_still_fail_closed_when_status_unavailable`）
- [x] 2.5 判据锚定：`test_exemption_criterion_is_self_committing_not_being_a_bot`——常量被删空/改名时变红
- [x] 2.6 **反向对照已实测**：把 `工具-共享文档编辑锁.py` 换回 master 版跑这 5 条，2.1 与 2.5 当场变红、2.2/2.3/2.4 保持绿 ⇒ 证明新增用例真的咬住了本次改动，且三条反例不是靠本次改动才通过的

## 3. 验收与收尾

- [x] 3.1 全量回归零漂移——`0-学习与工具` 全套 **748 passed ＋ 63 subtests passed，0 失败**（含邻居工具 `工具-落库sweep.py` 测试套；"跑邻居测试"这条是 2026-08-23 sweep 断链的教训）
- [x] 3.2 **真实场景验证（不只跑单测）**：把打过补丁的**真脚本**复制进一个真 git 仓库，用**真 CLI** 跑 `acquire --who 企微机器人` → 另一会话的脏文件先于 acquire 存在 → 追加一行「企微反馈自动归档：」→ `release`。**实验组 returncode=0**（输出：`ℹ 持锁者「企微机器人」自行提交自身改动，⑹ 登记完整性校验的适用前提对它不成立，已放行 2 个未登记脏文件`）；**对照组**同一套动作换成人类会话 **returncode=1**，拒绝文案与线上 #416 ⑶ 事故逐字一致（含「acquire 之前就已经脏（可能来自并发 session）」那一栏）。
- [x] 3.3 只读自验：`status` 三态可用（当刻无锁）；`工具-队列结构lint.py` 对两份真实队列文件 **rc=0** 通过
- [x] 3.4 🔴 **顺手核 #416 ⑹（行头断裂自愈死锁）本次是否被一并覆盖**——**结论：已覆盖，但不是被本变更包覆盖**，而是被 master 上既有的 **队列 #414 A3-2**（commit `f1ad578`，2026-08-26 15:20）覆盖：`_head_row_numbers` ＋ `is_repair_of_existing`（编号已存在于 HEAD 即豁免预留归属校验）＋ 行内 `预留豁免：` 逃生阀——**恰好就是 #416 ⑹ 行内建议的那两条**。已用真 CLI 真 git 仓库复核：HEAD 里是好行、现场是坏行、acquire 取到坏快照、持锁期间修好 → **release returncode=0**。⇒ **本包未扩范围去碰它，如实登记。**
- [ ] 3.5 ⏳ **观察窗未闭合**：下一次真实专员回件事件观察 `queue_edit_lock_release_rejected` 不再出现（需真实回件到达，本次无法自证），结果回填队列 §一 #416 行
- [ ] 3.6 归档本变更包（`openspec archive`）——**按 `工具-变更包自动归档.py` 判据，3.5 是真未完项、非 archive 动作类 ⇒ 本包判定为 `incomplete`，本次不归档**，待观察窗闭合后再归
