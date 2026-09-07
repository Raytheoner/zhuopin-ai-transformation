# queue-reserve-unfilled-release Tasks

> 🛑 **design 审未过，本包不得 apply。** 本 `tasks.md` 由起草期（`OP-0907-AE`【CC】，分支
> `claude/op0907ae-reserve-draft-487`，看护批 `B-0907_Y`）一并写出，供 design 审后直接照做；
> 起草期**一项都不勾**，编辑锁代码一行不改。
> 来源：队列 §一 `#487` 第三子项（`OP-0906-B` 并入）。执行环境：**CC**（写生产码、跑测试、
> 自行 commit+push，一任务一 worktree）。

## 0. 前置闸（design 审后、动手前）

- [ ] 0.1 `design.md` 七个决策点已全部拍板，结论已回填 `design.md` 文首结论表；队列 §一 `#487` 行的回填见 6.1
- [ ] 0.2 **若 ② 选 (b) 台账**：落点已限定在 `reports/` 或 `*.editlock*` 之内，并用 `git check-ignore -v <实际文件名>` 实跑确认命中（不是引用 proposal 里的候选名，是实际要生成的那个名）
- [ ] 0.3 **若 ① 选 (b)**：改协议〇.8 正文属 🟡，须 Shao Peishen 本人点头后才动，且改动登记 CHANGELOG
- [ ] 0.4 触碰区核对 —— 手段：遍历 `git for-each-ref refs/heads/`，对每个分支跑
  `git log master..<branch> -- 0-学习与工具/工具-共享文档编辑锁.py`，逐个记录**领先 master** 的分支
  （落后的不算冲突）。结果逐条写进本行，不写"已核对"三个字了事
- [ ] 0.5 `pip show zhuopin_platform` 确认 editable 落点，并对本 worktree 与该落点的 `queue_table` 做
  SHA-256 比对（`#98` 静默漂移形态；本包不改 `queue_table`，但须留证）

## 1. 取证与口径（🔴 必须先于实现）

- [ ] 1.1 **重跑现网空洞取证**（propose 期结果：`1..498` 缺 `187/215/216/303/348/356/367/409/496`，9 个，全部 >166）——apply 期高水位线可能已推进，须以当日实际值重取，写进本行
- [ ] 1.2 **`预留豁免：` 使用次数基线**：`git log -S "<RESERVE_WAIVER_MARKER 的字面值>" --oneline` 实测计数，作为 proposal 质量型价值指标的基线写死（不得凭印象填）
- [ ] 1.3 **下游消费者核实（独立重跑，不得引用 `#480` 那一包的结论）**——本包变的是 `release` 的**文件副作用**，不是返回码/stdout，消费者面不同。至少覆盖：
  - [ ] 1.3a `工具-落库sweep.py::_edit_lock()` 全部调用点：是否解析 release 的 stdout 或依赖"release 不改文件"
  - [ ] 1.3b `工具-队列结构lint.py`：是否对高水位线做过"只增不减"的假设
  - [ ] 1.3c `工具-队列查询.py --digest`：是否假设编号连续
  - [ ] 1.3d 全仓补充 grep（`*.py`／`*.ps1`／`*.sh`，排除测试与编辑锁本体）找新增消费者
- [ ] 1.4 确认 `HIGH_WATER_MARK_LINE_PATTERN`／`SECTION_NUMBER_PATTERNS`／`_split_live_sections`／`_table_data_rows`／`_iter_queue_paths` 五处均可直接复用，**不需要新写任何解析**；若发现需要新写，停手回报（判据只此一份）

## 2. 测试先行（🔴 先写、先红，再动实现）

- [ ] 2.1 新增测试类，覆盖回收正常路径：预留后一行未写即 release ⇒ 高水位线回退
- [ ] 2.2 预留三个只用第一个 ⇒ 尾部两个被回收
- [ ] 2.3 **中间空洞不被回收**（`L={169,171}` ⇒ 高水位线保持 171）
- [ ] 2.4 **回收后下一次 `--reserve` 取到被回收的号**
- [ ] 2.5 **落盘判定覆盖两份物理队列文件**（一个号落业务场景文件、一个落机制环境文件）
- [ ] 2.6 等值核对不通过 ⇒ 跳过回收、打告警、**release 仍返回 0**
- [ ] 2.7 一个分区跳过不阻止另一个分区回收
- [ ] 2.8 `--keep-reserved` 保号；部分留用；**不依据仓库文本推断留用**（号出现在别的行正文里仍被回收）
- [ ] 2.9 `--reserve-multi` 部分失败回滚 ⇒ 已推进分区一并回退
- [ ] 2.10 陈旧锁接管 ⇒ 点名前一位未落盘预留号但**不回收**
- [ ] 2.11 留痕：回显 ＋ 锁 `history` 各一条；**工作区不出现任何新文件**（`git status --porcelain` 实跑，不是推断）
- [ ] 2.12 **挂载顺序钉**：回收发生在 lastknown 写入之前 ⇒ 下一次 acquire **不**把本次回收报成绕锁写入（`#200`）
- [ ] 2.13 **非恒真自证**：关掉回收后，同一序列的下一次 `--reserve` 取到的是另一个号
- [ ] 2.14 确认 2.1–2.13 全部**红**（实现尚未写），把失败条数记进本行

## 3. 实现

- [ ] 3.1 `_unfilled_reserved_numbers(...)`：`reserved_map` 与两份队列文件该分区可见行编号取差集
- [ ] 3.2 `_rollback_high_water_mark(...)`：带等值核对的回退，逐字复用 `_reserve_ids` 的两个解析常量
- [ ] 3.3 挂载点一 —— `cmd_release`：`if violations: return 1` **之后**、`_write_lastknown(...)` **之前**（顺序理由写进代码注释，防后人挪位）
- [ ] 3.4 挂载点二 —— `cmd_acquire` 的 `--reserve-multi` 部分失败回滚分支（决策⑥）
- [ ] 3.5 `--keep-reserved` CLI 参数 ＋ 落锁文件 ＋ 回显点名 ＋ 回显交代「后续持锁写行仍需预留豁免」
- [ ] 3.6 陈旧锁接管回显点名未落盘预留号（决策⑤，只报不收）
- [ ] 3.7 留痕：回显 ＋ 写锁 `history`（决策⑦）
- [ ] 3.8 **回显措辞审查**：只写「回收未落盘的**尾段**编号 N 个」，不得写成「不再产生空洞」
- [ ] 3.9 代码注释写清「回收是省号、不是防错，故等值核对失败取跳过而非 fail-closed」——**防后人顺手对齐成 fail-closed**

## 4. 既有断言反转（🔴 放在最后，2.x 全绿之后）

- [ ] 4.1 `test_reserve_then_release_without_using_leaves_gap_and_keeps_high_water_mark` ⇒ 断言反转 ＋ **改名** ＋ 改 docstring
- [ ] 4.2 `test_reserve_multi_partial_failure_rolls_back_and_keeps_first_section_advance` ⇒ 同上
- [ ] 4.3 `_reserve_ids` docstring 那句「本函数不做任何『释放未用编号』的操作，调用方也不需要」按决策① 改写
- [ ] 4.4 `cmd_acquire` 回显「即使本次未写满，编号不复用、留空即可」按决策① 改写
- [ ] 4.5 `--reserve-multi` 部分失败分支注释「已成功预留的分区其高水位线不回退，允许留空洞」按决策⑥ 改写

## 5. 回归与验收

- [ ] 5.1 `test_工具-共享文档编辑锁.py` 全量绿、零回归（跑前基线条数与跑后条数都写进本行）
- [ ] 5.2 opener 两套单测 ＋ 队列相关 lint 全量跑，确认无连带回归
- [ ] 5.3 **mock 先行**：全部回收路径先在临时队列上跑通，再碰真实队列
- [ ] 5.4 `git status --porcelain` 实跑，确认工作区不出现任何新文件名形态
- [ ] 5.5 档位自评：交付后 ＝ **档1 mock 验证**；晋档2 的四条条件（含「零回收不得读成已生效」）抄进队列 `#487` 回填

## 6. 落档与销号

- [ ] 6.1 队列 §一 `#487` 行回填 design 审结论 ＋ apply 结论；第三子项是本行 open 的唯一剩余原因，闭合后**方可销号**
- [ ] 6.2 `1-转型规划/0-全景路线图/队列行日志/#487.md` 追加落地段（只追加、不改历史正文）
- [ ] 6.3 **包外残项交代**：op-id 侧那句纪律「未派出的号当场作废、不预留」的载体，按 design 审时 Shao Peishen 的答复处置（另立行 or 并入 `#487` 收尾）——**本包不代他决定，但也不得让它无声消失**
- [ ] 6.4 §二 批次登记（commit 由 `ZhuopinCommitSweep` 自动取活）
- [ ] 6.5 tasks 全 [x] 后当场 `/opsx:archive queue-reserve-unfilled-release -y`
