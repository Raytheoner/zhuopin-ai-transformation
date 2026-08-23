# Tasks — 回件转态改判（`OP-0823-D`）

## 1. 权威判据模块（`zhuopin_platform/shared_tools/followup_gate.py`）

- [x] 1.1 新增 `NOT_YET_SENT_STATUS_PREFIXES` ＋ `is_not_yet_sent` ／ `is_dispatched`（未知写法算已发出，保守方向）
- [x] 1.2 新增 `normalize_department` ／ `recipient_department`（`IT` vs `IT部` 不对齐）
- [x] 1.3 新增 `LetterRow` ＋ 三元组排序键 ＋ `latest_dispatched_letter`
- [x] 1.4 新增 `pair_reply_to_letter`（两级通道）＋ `PairingOutcome`（`matched` 按通道判，不按 `letter is not None` 判）
- [x] 1.5 新增 `unclosed_dispatched_by_department`（只报数的健康检查）
- [x] 1.6 新增 `reply_arrived_cites`，并让 `find_unsynced_letters` 认这条回指通道

## 2. 桥一（`aibot_service/followup_readme_bridge.py`）

- [x] 2.1 `mark_reply_arrived` 增 `department` 入参；`connection.py` 从 `IntakeResult` 透传（`matched=False` 时传 None）
- [x] 2.2 `_locate_letter` → `_pair`（走权威判据）；持锁后重定位同步改造
- [x] 2.3 未命中分三个 action：`supplement_after_closed`（低噪）／`no_dispatched_letter`／`no_department`
- [x] 2.4 审计事件记 `channel`；`_LOG_PREFIX` 表让 `supplement` 走 `·` 而非 `⚠`
- [x] 2.5 §3.1bis 健康检查一行低噪输出
- [x] 2.6 模块 docstring：退休「匹配不上就不动」，写清退休理由与保留 stem 的理由

## 3. 桥二（`0-学习与工具/工具-共享文档编辑锁.py`）

- [x] 3.1 `_followup_readme_rows_indexed`（带物理行号，供写回）
- [x] 3.2 `_build_reply_closed_status`（前缀在前、原状态原样接在后、本机本地日期）
- [x] 3.3 `_machine_write_followup_readme`（自占 README 锁、互斥保护、写后回读、同步 `lastknown`）
- [x] 3.4 `_validate_followup_reply_state_sync` → `_auto_sync_followup_reply_state`，返回 `(violations, notes)`
- [x] 3.5 `cmd_release` 调用点改造，并写清「写入发生在 release 决定之前」的取舍

## 4. 测试

- [x] 4.1 `test_followup_gate.py` ＋38 例：已发出／部门归一化／排序／两级配对／健康检查／回指
- [x] 4.2 `test_followup_readme_bridge.py` 重写 3 例 ＋ 新增 4 组（两级通道／跳过未发出／补充说明低噪／健康检查不阻塞）
- [x] 4.3 `test_工具-共享文档编辑锁.py` 重写 5 例 ＋ 新增 8 例（自动转态／幂等／lastknown/锁被占／回指通道／🔴 陈年入信行不得闭环当天新信）
- [x] 4.4 `scripts/smoke_followup_pairing.py`（生产真身冒烟，只读；含 worktree 副本警示）

## 5. 验收（派单件 §五）

- [x] 5.1 真实回件复现：纯文字回件现在能打上第九态，命中分支进审计
- [x] 5.2 两级通道与四分支各一条
- [x] 5.3 `⏳ 待你审` 跳过验证（三种未发出态各一条）
- [x] 5.4 生产真身冒烟：`IT部#9` 与 `财务部#15` 均被正确定位；20 封历史未闭环信未阻塞任何一次配对
- [x] 5.5 回归零漂移：`wecom-aibot-service` 全量 ／ `0-学习与工具` 全量 ／ `zhuopin_platform` 全量 ／ `openspec validate --all --strict`
- [x] 5.6 补充不影响状态机：已闭环的信再投回件 ⇒ 不改、不锁、不告警
- [x] 5.7 存量不回滚：2026-08-23 人工转态的 12 封未被改写

## 6. 收工回写

- [x] 6.1 队列 §一 `#366` 回填实现结论（含 §四 歧义的最终读法）
- [x] 6.2 派单件 `status:` 改 `已执行归档`
- [x] 6.3 §二 批次登记 ＋ sweep ＋ 台账

## 0. 🔴 归档前置（未决，本包不得归档）

- [ ] 0.1 **与前序变更包 `followup-letter-state-single-source` 对齐**：两包的 delta 落在同一批能力上，本包用 `ADDED` 是因为那两项能力尚未 sync 进主 specs。归档任一包之前，须按 design.md D5 的对照表把被取代的三条 Requirement 处理掉，否则主 specs 里会并存两组措辞相近、结论相反的要求。
- [ ] 0.2 **桥一真实生效待验**：本包合入 master **不等于**桥一在跑——其执行体 worktree 落后 master（§四 #68 未解）。待服务对齐后收到第一条真实纯文字回件、审计出现 `channel=latest` 且经人核对无误，方可勾选。
- [ ] 0.3 **20 封历史未闭环信的处置**：取证清单已出（`1-转型规划/0-全景路线图/取证清单-README历史未闭环信20封-2026-08-23.md`），待 Shao Peishen 判定。本包不动它们。
