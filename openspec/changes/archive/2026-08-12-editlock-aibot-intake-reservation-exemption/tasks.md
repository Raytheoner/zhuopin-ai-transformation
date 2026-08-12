## 1. Design 审核（阻塞后续所有任务）

- [x] 1.1 两个决策点均直接取自协议〇.10 ⑶ 已定稿文本，队列 #333 派单件已将其列为②的确定实现方案——2026-08-12 Shao Peishen"当日拍板 (a) 三条一起"构成本变更包的授权，无需另行征询
- [x] 1.2 记录审核结果到 design.md「审批记录」小节

## 2. 编辑锁③预留归属校验豁免分支（决策点 1/2）

- [x] 2.1 `工具-共享文档编辑锁.py`：新增 `AIBOT_LOCK_WHO`（"企微机器人"）/`AIBOT_INTAKE_TASK_PREFIX`（"企微反馈自动归档："）两个常量；`_validate_release_structure` ③预留归属校验新增豁免分支——`lock_data.get("who") == AIBOT_LOCK_WHO` 且新增行任务列（cells[1]）以该前缀开头时，不因"不属于本次预留集合"拒绝 release；仅豁免本项判定，组内重复/归档号重复两项独立校验不受影响；仅 §一 生效
- [x] 2.2 更新 `_validate_release_structure` 函数 docstring ③段与文件头部说明段，记录本次豁免的背景与判据来源
- [x] 2.3 新增单测（`test_工具-共享文档编辑锁.py::ReleaseStructuralValidationTests`）：① `test_aibot_intake_row_without_reserve_passes`——机器人 who + 收件登记前缀新增行未预留仍放行（复现 #333 真实事故场景）；② `test_aibot_non_intake_row_without_reserve_still_blocked`——机器人 who + 非该前缀新增行仍拒绝（防止豁免误伤真实撞号场景）；③ `test_non_aibot_who_with_intake_prefix_text_still_blocked`——非机器人 who + 相同前缀文本仍拒绝（防止豁免被当成绕过口，复现协议〇.10 ⑶ 自带的失效条款场景）

## 3. 相关发现登记（不在本变更包范围内处理）

- [x] 3.1 白盒复现确认"跨文件移动一行被同一条校验误判为新增"与②同一处代码但非同一可修决策（见 design.md「相关但不在本次范围内的发现」），已如实登记进队列 §一 #315 行，不在本变更包内处理

## 4. 验收与收尾

- [x] 4.1 全量回归（`test_工具-共享文档编辑锁.py`）零漂移——160 passed（含 3 条新增），5 subtests passed，无回归
- [x] 4.2 队列 §一 #333 行回填：状态、产出路径、单测清单、跨文件移动发现的登记去向
- [x] 4.3 `/opsx:archive` 归档本变更包——已归档为 `openspec/changes/archive/2026-08-12-editlock-aibot-intake-reservation-exemption`，主 spec `editlock-queue-number-reservation` 已同步新增 1 条 Requirement
- [x] 4.4 收工重跑文档台账

**晋档说明（如实登记，非拖延）**：本次仅完成档1 mock 验证（白盒单测复现 #333 场景），未在真实生产队列文件的一次真实机器人 `acquire`/`release` 循环中端到端验证（下一次机器人收件登记事件约每小时一次自然发生，观察结果回填 #333 行，见 proposal.md「验收与晋档条件」）。
