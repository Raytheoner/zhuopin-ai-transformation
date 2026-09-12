# orchestration-guards Tasks

> 执行环境：**CC**（写生产码、跑测试、自行 commit+push，本 worktree
> `interesting-rhodes-0da260`，分支 `claude/op0905q-orchestration-guards-791046`）。
> 派单件 `OP-0905-Q`：P2/P4/P7① 明标 A 类，判据已写死，无需再问澄清。

## 0. 前置闸

- [x] 0.1 队列 `--digest --grep opener生成` / `--grep 泳道看护状态机` 核触碰区无在办
      重叠——`#461` 已 done；`#452` open 但仅剩三条泳道 ff-merge 待派（不碰本包触碰区）；
      `#478` open 但 🛑 排队中·暂非可动（机制类可动 WIP 顶格），且其范围是
      `TRANSFER_ACTIONS` 语义扩展，与本包 P2/P4 触碰区不重叠。
- [x] 0.2 openspec propose `orchestration-guards`（本包）

## 1. P7① 撞号查重

- [x] 1.1 `工具-opener生成.py` 新增 `_scan_used_suffixes`／`_next_free_suffix`／
      `_check_op_id_not_reused`，接入 `generate_opener()` 前置校验
- [x] 1.2 单测 `UsedSuffixDedupTests`（6 例）：撞号拒＋给空号／空号放行／短形
      `[Win]MMDDX-` 也算已用／裸数字巧合不算已用（反例，钉住 D1 判据不过度扩大）／
      跨日不冲突／`_next_free_suffix` 多字母已用时正确跳过
- [x] 1.3 现场实测（不落盘）：对真实仓库 `1-转型规划/` 树跑一次，`OP-0905-K` 命中
      真实存在的短形 `[Win]0905K-看护四泳道C`（`看护件-泳道看护批B-0905_C-
      2026-09-05.md`），`OP-0905-A` 当时未命中——与仓库当日实际内容一致，非构造夹具

## 2. P2 §三泳道 dry-run 解析

- [x] 2.1 `工具-泳道看护状态机.py` 新增 `parse_section_three_lanes`（只依赖
      `### A<N>` 标题 ＋ `【设置】` 行两个锚点）＋ CLI `dry-run --file`
- [x] 2.2 现场实测：对真实看护件 `看护件-泳道看护批B-0905_C-2026-09-05.md`
      （旧长版本，4 条泳道）跑 `dry-run`，输出「§三 解出泳道 4／4 条」
- [x] 2.3 现场实测：对构造的 3 行精简版样例（2 条泳道 + §三bis 块）跑 `dry-run`，
      输出「§三 解出泳道 2／2 条」——**结论：解析器无需为识别 3 行版另做改动**
      （方案原文「不识别再改解析器」的条件分支未触发，如实记录，未做即未做）
- [x] 2.4 单测 `LaneParsingDryRunTests`（9 例）：3 行版双泳道识别／§三bis 不算
      第三条泳道／旧长版本向后兼容／缺 `【设置】` 行报未识别／标题后无围栏块报未
      识别／零标题返回空列表／CLI 正反两个退出码用例

## 3. P4 生成器默认口径 ＋ 状态机撞锁计数

- [x] 3.1 `工具-opener生成.py` 新增 `variant`（`standard`／`subtask_lane`／
      `guardian`）＋ `_title_call_line_guardian`／guardian 分支的 `_settings_line`
      特殊处理（分支字段固定字面量，不套用 slug 拼装模板）
- [x] 3.2 `subtask_lane` 收尾无条件追加 `SUBTASK_PARALLEL_NOTE`／`SUBTASK_PUSH_NOTE`；
      `guardian` 正文追加 `GUARDIAN_PARALLEL_NOTE`
- [x] 3.3 `generate_opener` 自校验调用改为按变体传 `is_subtask_lane`，避免
      subtask_lane 变体被形态①误判缺 `set_session_title`
- [x] 3.4 单测 `VariantSubtaskLaneTests`（5 例）／`VariantGuardianTests`（6 例）：
      无 session_title 行／默认口径存在／过 lint 自检／反向用例证明"不报 F1"确实
      来自 `is_subtask_lane=True`／Cowork 环境拒绝该 variant／guardian 首行标签／
      guardian session 标题／guardian 分支字面量不被套模板／短名+"看护"前缀超
      12 字拒绝
- [x] 3.5 `工具-泳道看护状态机.py` 新增 `record_lock_hit`／`count_lock_hits`／
      `format_lock_hit_line`／CLI `record-lock-hit`；`_cmd_summary` 输出新增第三行
- [x] 3.6 单测（5 例）：记录后计数正确／按 batch 过滤／格式化零与非零／CLI
      record-lock-hit 后 summary 报数／零撞击时 summary 报 0 次

## 4. 回归与收口

- [x] 4.1 `test_工具-opener生成.py` 新增 `setUpModule`/`tearDownModule` 把
      `REPO_ROOT` 钉死到空临时目录——避免撞号查重扫真实仓库树导致既有用例受仓库
      当日实际内容影响而漂移（测试基础设施调整，非业务判据改动）
- [x] 4.2 `test_工具-opener生成.py` + `test_工具-泳道看护状态机.py` 全绿：
      102 passed, 10 subtests passed（含全部既有用例，零改动、零回归）
- [x] 4.1b commit `f0b590d` 已 `git push origin HEAD:master`（ff-only，`merge-base
      --is-ancestor` 核过可快进，无冲突）
- [x] 4.3 `0-学习与工具/` 全量回归：`4 failed, 1459 passed, 109 subtests passed
      in 1457.37s`。4 处失败逐一核对——均在本包未触碰的文件内（`test_发企微.py`／
      `test_工具-CLAUDE进度段lint.py`（2 处）／`test_工具-引导样板lint.py`），
      与 `#452` 记录的"真实仓库现状随内容演进而漂移"同族既有模式一致（`#452` 那次
      的 4 例文件名不同，因两次运行相隔数日、仓库内容已变化，但同属"对真身断言
      具体数值/存量"这一类真实仓库状态哨兵，非本包引入）；本包触碰的两个文件与
      其单测未出现在失败清单内，零回归确认。
- [ ] 4.4 队列 §一 新行登记本包完成结论（走编辑锁）——**两次 acquire 均被拒**：
      `--reserve` 报「即将分配的编号 [487] 已存在于当前文件 §一 可见行中（高水位线
      =486，落后于文件实际内容）」，判定为队列 #200/#233 同族的高水位线滞后于文件
      实际内容问题（环境线在办域，非本包触碰区，不擅自手改队列文件绕过锁）。
      待高水位线问题解决或另一会话把它顶正后由下一位持锁者补登记，本任务的代码
      交付（commit/push）不受影响。
- [ ] 4.5 §二 批次登记，触发 sweep（同受 4.4 同一锁况阻塞）
- [ ] 4.6 `/opsx:archive orchestration-guards -y`（登记未完成前暂不归档）
