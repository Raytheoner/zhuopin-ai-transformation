# Design — 机制/工具类模块补写 openspec capability

## 背景

队列 #195 取证已确认七项机制类模块（`simple_gate.py`/`--reserve`/`queue_lock_pending.py`/
`repo_paths.py`/`decision_reminder.py`/`liveness.py`/sweep 分叉告警）与 FI2 共约 8 个
capability 候选全部缺失 spec。#195 行本身建议"可分批"且"建议排序：#160 鉴权边界优先，
其余按'是否仍在演进'排（`--reserve`/`queue_lock_pending` 近期还会改，宜等 #185/#192
落地后一并补，避免补完即过时）"。

## D1：本批范围——五项，非全部八项

**纳入**：`simple_gate.py`（#160）、`repo_paths.py`（#126）、`decision_reminder.py`（#172）、
`liveness.py`（#147）、sweep 分叉告警（#171）。取证确认这五项**均已稳定**——原始队列行
均已收工销行或转入"已完成"状态，近期无计划变更。

**排除·`--reserve`（#163）与 `queue_lock_pending.py`（#168）**：2026-08-04 本 session
开工前收到的防撞提醒明确指出，本批"刻意不含 #200／#185／#229——三者分别改
`工具-共享文档编辑锁.py` 与 `工具-落库sweep.py`"，且 #185 尚在途。`--reserve`
（编辑锁取号能力）与 `queue_lock_pending.py`（机器人写队列语义）正是 #185 系列
在改的对象——#195 行原话"近期还会改，宜等其落地后一并补"在本次 session 时点
依然成立，故延后，不因"可分批"就强行凑数补一份很快要改的 spec。

**排除·FI2**：`specs/` 里 `fi2*` 缺失的根因不是"补写遗漏"，而是其唯一实现变更包
`fi2-recon-mvp` 本身**代码尚未完工**（106[x]/11[ ]，见队列 #196 行）。fix-a/b/c
那批是"代码完工、只差 openspec 手续"，可以直接补；FI2 是"代码本身没做完"，
spec 应该等 `/opsx:archive fi2-recon-mvp` 正常跑时自然产出，本变更包若越俎代庖
提前写一份 FI2 spec，反而可能与该包完工后的真实归档产生冲突或提前锁死尚未定案
的行为（v8 面板与三单匹配口径仍在演进，见根 CLAUDE.md 当前进度段 07-31 FI2 v8
改造记录）。

## D2：编写方法——只转写已验证行为，不新增承诺

每个 capability 的 Requirement 逐条对照：① 现有实现代码（读函数签名与关键分支）；
② 现有测试断言（该行为是否真被测试覆盖）。只有代码与测试同时确认的行为才写入
SHALL/MUST；代码存在但无测试覆盖的边界分支，本次不写入（避免 spec 断言一个
实际未被回归保护的承诺）。本次核对未发现"代码有、测试无"的关键分支需要排除
——五个模块的核心行为均有对应单测覆盖（各自原始队列行的 TDD 记录可查）。

## D3：不做的事

- 不新建 `data_isolation_layer`/OEM 相关接口位——五个模块均不涉及 OEM 技术数据。
- 不因补写 spec 而反向"顺手"修改代码使其更贴合某种理想设计——本变更包对代码
  的定位是**只读取证来源**，代码本身零改动（见 proposal.md Impact 段）。
- 不追加对 `--reserve`/`queue_lock_pending`/FI2 的占位 spec——CLAUDE.md §7 红线
  "不为凑数硬写"同样适用于本变更包自身：宁可留 3 项在途，不写占位后马上作废。

## 验收

`openspec validate --all --strict` 在本变更包归档后应新增 5 个绿色 capability，
且不影响既有 38 项（队列 #209/#210 已使其归零失败）的通过状态。
