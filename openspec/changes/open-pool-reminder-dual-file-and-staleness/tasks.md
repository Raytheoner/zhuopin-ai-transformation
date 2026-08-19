# open-pool-reminder-dual-file-and-staleness Tasks

## 1. 前置核实

- [x] 1.1 `git check-ignore -v` 实测状态文件 `5-平台底座/wecom-aibot-service/reports/open_pool_reminder_state.json` 的忽略覆盖情况，把实际输出贴回 proposal.md 对应节（不是写"应该被覆盖"）
- [x] 1.2 实测确认 `queue_table.iter_queue_paths()` 返回的两份路径在生产真身上都存在且各自含合法 `## 一、` 标题

## 2. 缺口一 · 双文件取数

- [x] 2.1 `open_pool_reminder.py` 新增 `build_pool_items_from_repo(repo_root)`：按 `iter_queue_paths()` 逐份读取解析、合并成池；`build_pool_items(queue_text, repo_root)` 原样保留不改签名
- [x] 2.2 缺失/读取失败的文件跳过并发 `RuntimeWarning`（非静默降级），其余文件照常处理
- [x] 2.3 `decision_reminder_check.py` 的 ② 段改用 `build_pool_items_from_repo`；① 决策提醒段不动（另一条链路）
- [x] 2.4 单测：业务场景文件的 open 行进池／两份合并／一份缺失时告警且不静默／**拼接文本会丢第二份 §一** 的反例断言（锁死"逐份解析"这个选择）

## 3. 缺口二 · 陈化催办

- [x] 3.1 新增 `last_touched_at(repo_root, queue_rel, row_id)`：`git log -1 --format=%cI -G'^\| *<行号> *\|' -- <文件>`，返回带时区的 `datetime` 或 `None`
- [x] 3.2 `OpenPoolItem` 增加"所属队列文件相对路径"字段（陈化查询需要知道去哪个文件上查）
- [x] 3.3 新增 `compute_stale_ids(items, state, now, ...)`：两条合取条件（末次触碰 > 阈值；距上次催办 ≥ 间隔）；`None` 时间视为"刚触碰、不催"
- [x] 3.4 新增 `format_stale_reminder_message(...)`：自带下一步动作（opener 路径或"尚未出 opener"），显示已滞留天数
- [x] 3.5 状态 schema 增加 `stale_notified_at`；`default_state`/`load_state`/`save_state` 兼容旧文件；新增 `new_stale_state(...)` 每轮裁剪为仅当前池中行号
- [x] 3.6 `send_open_pool_reminder` 支持独立 audit action 前缀，陈化催办用 `open_pool_stale_reminder_*`
- [x] 3.7 `decision_reminder_check.py` 接入陈化催办：独立判定、独立消息、与新增即推互不覆盖
- [x] 3.8 单测：陈化触发／未满间隔静默／满间隔再催／`None` 时间不催且不静默／行离开池后记录被裁剪／旧状态文件平滑加载／新增与陈化互不覆盖

## 4. 回归与验收

- [x] 4.1 `wecom-aibot-service` 全量回归零漂移
- [x] 4.2 `zhuopin_platform` 平台全量回归零漂移
- [x] 4.3 `openspec validate --all --strict`
- [x] 4.4 **档 2 验收（不接受只跑单测）**：对生产队列真身跑 `--dry-run`，确认业务场景文件里的行（`#334`／`#344` 即现成样本）真的出现在池里
- [ ] 4.5 **真实推送**：真实执行一次 `decision_reminder_check.py`，确认企微收到；Shao Peishen 确认看到
- [x] 4.6 如实登记本包**无法在交付时闭合**的验收项：完整 7 天周期轨迹（满 7 天推 → 一周内不重复 → 满 14 天再推）须等自然发生

## 5. 收口

- [ ] 5.1 队列 `#312` 行回写：两个缺口的处置结论、实测数据、未闭合项
- [ ] 5.2 场景/服务 `CLAUDE.md` 更新（`5-平台底座/wecom-aibot-service/CLAUDE.md`）
- [ ] 5.3 tasks 全 [x] 后当场 `/opsx:archive`；未全 [x] 则**不 archive、如实登记**


## 6. 如实登记 · 本包交付时**未闭合**的项（不假装完工）

- **4.6 完整 7 天周期轨迹未验证**：2026-08-19 实测池中最久的 `#240` 只滞留 6 天，**全部 9 条都 < 7 天阈值 ⇒ 陈化候选为空**，今天推不出真实的陈化催办消息。Shao Peishen 当日答「接受，真推『新增』那条即可」。**`#240` 明天即跨过 7 天**，最快 2026-08-20 08:30 的 `ZhuopinDecisionReminderDaily` 会推出第一条真实陈化催办——**那一次才是本判据的真实首验，须回本行确认**。
- **5.3 `archive` 不做**：4.5 与 4.6 未全 [x]，tasks 未全勾，按「完工即归档纪律」的反面——**不假装完工**。
