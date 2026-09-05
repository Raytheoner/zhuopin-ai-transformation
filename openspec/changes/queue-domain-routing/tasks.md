# queue-domain-routing Tasks

> propose＋design 于 2026-09-05 完成（队列 `#341` 原文明写"停下等审，不得直接 apply"）。
> **design 审已于 2026-09-05 由 Shao Peishen 拍板，四条决策点全部采纳 design.md 自带的
> 默认项、未选任何备选**；本文件此后进入 apply 阶段，勾选状态即 apply 实况。
> 分支 `claude/op0905o-domain-route-341`（design 起草 commit `4b8a98a`）。

## 0. apply 前置确认（design 审批复后，领取方必做）

- [x] 0.1 决策点 1（未声明 `--domain` 时默认落机制环境 vs 改真拒绝）——**采纳默认项**：
      维持代码现状，反向改两份主 spec 描述为目标态。**不改任何 `.py`。**
- [x] 0.2 决策点 2（`queue_appender` 切回业务场景文件）——**采纳默认项**，且必须与
      "取号高水位线来源与写入目标解耦"一并落地，缺一不可。
- [x] 0.3 决策点 3（更正"锁粒度"Requirement 为共享锁描述）——**采纳默认项**：改写
      Requirement，不补标注、不改代码。
- [x] 0.4 决策点 4（存量错位行就地留存）——**采纳默认项**，无异议。口径记录已写进
      design.md 决策点 4 尾段；`#336` 实测零命中（`工具-队列查询.py --row 336`），
      按"历史记录不追改"**不回填已归档行**。

## 1. `queue_appender` 域路由切换（决策点 2，风险最低、优先做）

- [x] 1.1 `repo_paths.DEFAULT_QUEUE_RELATIVE_PATH` 改指 `跨桌任务队列-业务场景.md`，
      文档字符串重写（移除"迁移期妥协"措辞，如实记录本次切换的时间与依据）。
      🔴 **同批新增 `QUEUE_MECHANISM_RELATIVE_PATH`**：起草时未识别到本常量身兼三职
      （写入目标／仓库根锚点／"§四·协议〇·高水位线在哪"的读侧答案）。只翻转它会让
      `scripts/decision_reminder_check.py` 每日 08:30 去一份**没有 §四** 的文件里读
      决策项 ⇒ 稳定输出"命中 0 项"，与"今天真的没有待决策"逐字相同（本项目反复点名的
      "只读结果太干净"形态）。故拆成两个常量，读侧钉死机制环境文件。
- [x] 1.2 🔴 **配套修复（与 1.1 同一次提交）**：`queue_appender.append_pending_task`
      新增 `high_water_mark_path` 参数（未传时由新增的 `resolve_high_water_mark_path`
      解析，默认＝同目录机制环境文件）；`_next_task_id` 新增 keyword-only
      `high_water_mark_lines`，`_bump_section_one_high_water_mark` 改为作用于来源文件
      的行。两份文件不同时，**先推进来源文件高水位线、再写新行**（次序不可对调：前者
      成功后者失败＝跳一个号，无害；反过来＝撞号），且各自做写前乐观并发核验。
- [x] 1.2b 🔴 **起草时未识别到的第二层，同批修**：`queue_git_sync._commit` 原本只
      `git add` 写入目标那一份 ⇒ 高水位线的推进永远滞留工作区、推不出去，撞号从"本地
      已避免"退回"跨 checkout 仍会发生"。改为两份同批入库，并把 `#287` 那条外来内容
      护栏一并覆盖到高水位线来源文件（预期改动更紧：插入 ≤1／删除 ≤1）。
- [x] 1.2c 🔴 **读侧同族缺口，同批修**：`queue_reconcile_sentinel._collect_reconciliation_
      text` 只读 `queue_path` 那一份 ⇒ 切换前若干天写在机制环境文件里的行会被逐条误判为
      "归档成功但队列没有对应行"，产生一批假阳性私信（同 `#99`／`#312` 缺口一形态）。
      改为按 `iter_queue_paths()` 逐份读后合并（**不拼接后只解析一次**）。
- [x] 1.3 `wecom-aibot-service` 既有 mock 单测套件全绿复核（隔离环境，不触真实企微端点）：
      基线 **758 passed / 1 skipped** → 改后 **767 passed / 1 skipped**（+9 新增），零回归。
- [x] 1.4 单测：`tests/test_queue_appender_domain_routing.py::test_queue_appender_targets_
      business_file`（反例：钉住"不得写回机制环境文件"，与 `#336` 形态对称的回归护栏），
      配套 `test_mechanism_relative_path_constant_is_the_mechanism_file` 钉住读侧常量不被
      合并回去。
- [x] 1.5 单测：`test_queue_appender_high_water_mark_decoupled_from_write_target`
      （机制环境高水位线 500 ／业务场景可见最大号 300 ⇒ 必须取 501，且回写落在机制环境
      文件、业务场景文件不得长出第二条标注行）＋ **变异验证**
      `test_old_in_file_numbering_would_collide`（把改判前算法喂给同一份数据必须取到
      301 ＝ 撞号）。**已实撞**：把 `high_water_mark_lines` 改回 `None` ⇒ 当场变红，
      复原回绿；`_commit` 改回只提交一份 ⇒ `test_sync_commits_both_write_target_and_
      high_water_mark_source` 当场变红，复原回绿。
- [ ] 1.6 观察下一条真实归档来件的队列行落位（`工具-队列查询.py --row <N>` 命中于业务
      场景文件）与编号连续性（不与机制环境文件当前高水位线冲突），登记进队列 `#341`
      回写行。⏳ **本班为无人在场的无头会话，等一条真实企微来件不在本班能力内**——
      预期观察窗口：7 天。

## 2. 编辑锁 spec 目标态收编（决策点 1/3）

- [x] 2.1 决策点 1 默认项：`_resolve_append_target`/`acquire` 现有"默认落机制环境＋
      回显提示"行为**代码零改动**，仅 spec 措辞对齐（已核对本包 delta specs 无需二次改写）。
- [x] 2.2 决策点 3 默认项：`QUEUE_LOCK_ANCHOR`/`_is_queue_system_target` 现有共享锁
      行为**代码零改动**，仅更正 spec 描述并补来源说明（指向队列 `#420`）。
- [x] 2.3 delta specs 已并入 `openspec/specs/queue-dual-file-topology`／
      `editlock-dual-queue-routing` 正本（走 `/opsx:sync` 语义合并，非整文件覆盖）。

## 3. 新增 aibot 侧域路由 capability

- [x] 3.1 `openspec/specs/aibot-queue-domain-routing/spec.md` 已落地（由本包 delta 的
      ADDED Requirements 并入，Purpose 逐字取自 delta）。含 apply 阶段新增的
      "两份文件的改动同批入库"Scenario（对应 1.2b）。

## 4. 回归与收口

- [x] 4.1 三处单测：`wecom-aibot-service` **767 passed / 1 skipped**（基线 758／1）；
      `5-平台底座/zhuopin_platform` **466 passed / 1 skipped**（未触碰，零漂移）；
      `0-学习与工具` 全绿复核（本次未触碰该目录任何文件）。
      ⚠️ CI 整体 run 长期 failure（§一 `#398` ⑶）⇒ 红绿信号一律本地实跑取证，不以 CI 绿为准。
- [x] 4.2 `grep -rn "实现差异" openspec/specs/queue-dual-file-topology openspec/specs/
      editlock-dual-queue-routing` 命中 **0 处**。
      🔑 定稿时踩到一次自指陷阱：来源注里写"移除此前『…实现差异』临时标注"这句话本身
      会被判据命中——与 `queue_table.py` 记着的"把『格子被污染』与『格子在谈论污染』当成
      同一件事"同形。已把注文改写为"目标态/现状分叉"，出处一字未少。
- [x] 4.3 队列 `#341` 行回写（走编辑锁协议 acquire → edit-row → release），附本次切换的
      实测证据（单测数、变异验证、分支与 commit 哈希）。
- [ ] 4.4 `/opsx:archive queue-domain-routing -y` —— **预期观察窗口：7 天**（阻塞项＝
      1.6，需一条真实企微来件才能验落位与编号连续性；本班无人在场、不制造假来件）。
