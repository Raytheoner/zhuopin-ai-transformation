# queue-domain-routing Tasks

> 本包本次止步于 propose＋design（队列 `#341` 原文明写"停下等审，不得直接 apply"）。
> 以下全部为 apply 阶段的规划任务，**均未执行**，供 design 获批后的领取方直接使用；
> 领取前须先完成 §0 前置确认。

## 0. apply 前置确认（design 审批复后，领取方必做，非本次执行）

- [ ] 0.1 确认决策点 1（未声明 `--domain` 时默认落机制环境 vs 改真拒绝）采纳哪一项——
      若采纳备选（改拒绝），需先另立调用点普查行，本包 delta specs 需重写方向。
- [ ] 0.2 确认决策点 2（`queue_appender` 切回业务场景文件）是否采纳默认项。
- [ ] 0.3 确认决策点 3（更正"锁粒度"Requirement 为共享锁描述）是否采纳默认项——若
      Shao Peishen 判断"独立锁"仍是长期目标态，本条改为"补标注"而非"改写 Requirement"。
- [ ] 0.4 确认决策点 4（存量错位行就地留存）无异议。

## 1. `queue_appender` 域路由切换（决策点 2，风险最低、优先做）

- [ ] 1.1 `wecom-aibot-service/aibot_service/repo_paths.py::DEFAULT_QUEUE_RELATIVE_PATH`
      改指 `跨桌任务队列-业务场景.md`，更新其文档字符串（移除"迁移期妥协"措辞，改为
      如实记录本次切换的时间与依据）。
- [ ] 1.2 🔴 **配套修复（与 1.1 同一次提交，不得分两次落地）**：`queue_appender.py::
      append_pending_task` 新增独立的"高水位线来源文件"参数（默认机制环境文件），
      `_next_task_id`／`_bump_section_one_high_water_mark` 改为对该来源读写高水位线
      标注行，不再依赖 `queue_path`（新行写入目标）自身是否含该标注行——见 design.md
      决策点 2「配套修复」与新增 capability `aibot-queue-domain-routing`。
- [ ] 1.3 `wecom-aibot-service` 既有 mock 单测套件全绿复核（隔离环境，不触真实企微端点）。
- [ ] 1.4 单测：`test_queue_appender_targets_business_file`（反例：钉住"不得写回机制环境
      文件"，与 `#336` 形态对称的回归护栏）。
- [ ] 1.5 单测：`test_queue_appender_high_water_mark_decoupled_from_write_target`
      （变异验证：若 1.2 未落地、取号仍读 `queue_path` 自身，构造"机制环境高水位线
      已推进到 N、业务场景文件可见最大号仍是旧值 M<N"的场景，断言此时若不修复会取到
      一个 ≤N 的重复编号；修复后必须取到 `max(N,M)+1`）。
- [ ] 1.6 观察下一条真实归档来件的队列行落位（`工具-队列查询.py --row <N>` 命中于业务
      场景文件）与编号连续性（不与机制环境文件当前高水位线冲突），登记进队列 `#341`
      回写行，作为 proposal.md「验收与晋档条件」第 1 条的实测依据。

## 2. 编辑锁 spec 目标态收编（决策点 1/3）

- [ ] 2.1 若采纳决策点 1 默认项：确认 `_resolve_append_target`/`acquire` 现有"默认落
      机制环境＋回显提示"行为**代码不改动**，仅 spec 措辞对齐（本包 delta specs 已按
      此撰写，apply 阶段核对无需二次改写）。
- [ ] 2.2 若采纳决策点 3 默认项：确认 `QUEUE_LOCK_ANCHOR`/`_is_queue_system_target`
      现有共享锁行为**代码不改动**，仅补充/更正 spec 描述与来源注释（指向队列 `#420`）。
- [ ] 2.3 `openspec sync-specs`（或等价的 `/opsx:sync`）把本包 delta specs 并入
      `openspec/specs/queue-dual-file-topology`／`editlock-dual-queue-routing` 正本。

## 3. 新增 aibot 侧域路由 capability

- [ ] 3.1 `openspec/specs/aibot-queue-domain-routing/spec.md` 落地（由本包
      `specs/aibot-queue-domain-routing/spec.md` 的 ADDED Requirements 并入）。

## 4. 回归与收口

- [ ] 4.1 `wecom-aibot-service`／`5-平台底座/zhuopin_platform`／`0-学习与工具` 三处
      单测全绿，零回归（对照本次起草时的基线数）。
- [ ] 4.2 `grep -rn "实现差异" openspec/specs/queue-dual-file-topology openspec/specs/
      editlock-dual-queue-routing` 命中 0 处（对照 proposal.md「验收与晋档条件」第 3 条）。
- [ ] 4.3 队列 `#341` 行回写：状态转 `[S:done]`，附本次切换的实测证据链接（单测结果、
      真实来件落位截图/查询结果）。
- [ ] 4.4 `/opsx:archive queue-domain-routing -y`（全部任务勾完后当场归档，
      不得跨 1 个 session）。
