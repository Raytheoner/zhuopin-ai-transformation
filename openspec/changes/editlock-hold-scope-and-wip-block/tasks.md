# editlock-hold-scope-and-wip-block Tasks

> 🔴 **1.x 全部完成、且 Shao Peishen 已批准 design.md 六个决策点之后，才可开工 2.x 起的实现项。**
> 派单指令：design 停审等批准后再 apply。

## 1. Propose ＋ Design（本次已完成）

- [x] 1.1 现网全量取证：对两份队列文件 §一/§四 全 170 行只读跑现判据与三个候选判据，产出命中集对照表（design 决策点 1）
- [x] 1.2 §四 #52 误报复现：内存内补回被去掉的反引号，确认现判据命中、首段判据不命中（未落盘、未改生产文件）
- [x] 1.3 回答 #324 的前置问题「⑥ 自 #258 落地以来是否真拦下过一次真实的暂缓不一致」——查得真阳性 0 次，且曾被记错的那次归属（#285 行 2026-08-07）当时即已更正为校验①
- [x] 1.4 ⑨ 的白盒核实：确认提示只在 `new_mechanism_row_added` 为真时触发（＝6 次都响了、6 次都被越过）
- [x] 1.5 proposal.md（含知识资产三问／四档晋档条件／守卫退休问答／`.gitignore` 覆盖问答四个强制节）
- [x] 1.6 design.md 六个决策点，均带推荐与默认项
- [x] 1.7 两份 spec delta（`editlock-followup-hold-consistency-guard` MODIFIED+REMOVED／`editlock-mechanism-wip-guard` MODIFIED+ADDED）
- [x] 1.8 `openspec validate editlock-hold-scope-and-wip-block --strict` 通过
- [x] 1.9 **Shao Peishen 审 design.md 六个决策点**——2026-08-17 答《本周计划-2026-08-17》A4：**六点全按默认**，另附一条 design 原文没有的补充（⑥ 观察窗口有效性判据，见 2.6）

## 2. Apply — ⑥ 收窄（决策点 1/2/3）

- [x] 2.1 新增 `_leading_conclusion_segment()`（按 `━━━` 取首段，无分隔符时返回整格）
- [x] 2.2 `_row_hold_language_status()` 改用首段做关键词扫描；§四 文件名提取同步取首段，§一 文件名来源保持 `cells[3]`/`cells[6]`（两处不对称是刻意的，理由已写进函数 docstring）
- [x] 2.3 删除反向告警分支（退休项）；`FOLLOWUP_NON_TERMINAL_STATUSES` 全库 grep 确认无其它消费者，已一并删除
- [x] 2.4 单测 —— ⚠️ **前提被证伪，范围相应调整（如实登记）**：propose 期「⑥ 0 覆盖」的判断不成立，实测已有 `HoldConsistencyValidationTests` **9 个端到端用例**。误判成因＝那次 grep 搜的是实现符号 `_row_hold_language_status`，而这些用例全走 `cmd_release`、正文不出现该符号，**0 命中被读成了 0 覆盖**——**与本包要治的「扫描面与判定对象不一致」正是同形**。故本项＝**增量补测 ＋ 改写退休相关断言**，非从零补齐：
  - [x] 2.4.1 **真阳性**——既有 `test_hold_row_with_readme_still_pending_blocks_release` 已覆盖；本次另加 `test_hold_keyword_in_leading_segment_still_blocks`（首段有暂缓结论、该格另有大量历史沉积 ⇒ 仍拒绝，钉住「收窄不得削掉正向拦截力」）
  - [x] 2.4.2 **#52 误报回归**——`test_hold_keyword_only_in_history_segment_passes`。**并已单独实测新旧两套判据对同一段文本的分歧真实存在**（旧命中 True／新命中 False），避免写出一个「本来就会通过」的假用例
  - [x] 2.4.3 `test_cell_without_separator_behaves_exactly_as_before` ＋ `test_leading_conclusion_segment_splits_on_separator`（函数级）
  - [x] 2.4.4 既有 `test_hold_keyword_without_filename_reference_does_not_trigger` 已覆盖；另加 §四 `test_section_four_filename_in_history_segment_not_paired`（首段有关键词、文件名落在历史段 ⇒ 提取不到文件名，不触发）
  - [x] 2.4.5 两个既有反向用例已改写为退休后的断言：`test_reverse_readme_already_sent_neither_blocks_nor_warns`（断言 stdout 不含该告警）／`test_150_real_incident_row_recreated_passes_silently`。**退休本身也要被钉住**，否则下次有人凭印象加回来没有任何东西拦得下
- [x] 2.5 现网全量回归复核（2026-08-17 apply 当日重跑，**未采信 propose 期旧表**）：两份队列真身 §一 140 行 ＋ §四 30 行 ＝ **170 行**；**旧判据触发 10 行**（propose 期为 9 —— 期间队列内容已变，按 2.5 自己的要求以新数据为准）、**新判据触发 2 行**（#294／#299），与 design (甲) 列的 2 一致。两行经 README 结构化映射查证**均无匹配 ⇒ 判不出、不拦**；被丢掉的 8 行逐条核对**全部是「判不出」或反向告警（#150）**，⇒ **现网没有任何一行因本次收窄由「拒绝」变「放行」**

- [x] 2.6 **批准时附加项落地（Shao Peishen 2026-08-17，design 原文没有）——⑥ 的观察窗口必须能得出结论**：窗口须至少覆盖 **N＝3 段**「README 确有 `🆕 待发` 数据行」的时期，其"真阳性 0 次"才算有效样本；待发行恒为 0 的窗口判为无效，**既不得据此判 ⑥ 无用、也不得判它有用**。已写进 **proposal.md「验收与晋档条件」第 4 条**（非只写在队列行里），design.md 另附「批准时附加项」一节留痕。
  - **N＝3 的实测依据**：还原 README 全部 **78 个历史版本**、逐版按表格块取「发送状态」列计数，2026-07-04→08-17 共 45 天内出现 **7 段**待发时期（均值 ~6.4 天／段，**3/7 段只持续单个快照日**）⇒ N＝1 几乎不构成检验；N＝3 ≈ 19 天 ≈ 3 个值周巡检节拍，与既有「口径冻结观察期」量级一致。
  - **边界如实声明**：本判据是**必要非充分条件**——⑥ 真正被检验还需同时发生「某队列行点名了那封待发信、且该行在持锁窗口内被改动」。**刻意不加运行时埋点**（与决策点 5 拒绝自动写盘同一理由）。
- [x] 2.7 **计数纪律同批落地**：凡引用 README 状态计数，一律按表格块切分取「发送状态」列，**不得整文件 grep**。2026-08-17 实测同一份 README：`grep "🆕 待发"` 得 **13**（全在讲解正文里），**表格数据行 ＝ 0**（数据行共 42，全处于终态）——**同一个数字两种读法、结论相反**。已写进 proposal.md 计数纪律段，本包所有 README 计数均按表格块口径取数。

## 3. Apply — ⑨ 阻断化（决策点 4/5/6）

- [x] 3.1 `--force-mechanism-wip`（`action="store_true"`，不携带理由文本）
- [x] 3.2 `MECHANISM_WIP_WAIVER_MARKER = "WIP豁免："`，复用 `FOLLOWUP_SERIAL_WAIVER_MARKER` 既有范式，零新增写盘路径
- [x] 3.3 ⑨ 段超限改为进 `violations`；**触发条件逐字未动**（`new_mechanism_row_added` 布尔改为 `new_mechanism_rows` 清单，只为逐行核对豁免标记、并在文案里点名行号，判定时机不变）
- [x] 3.4 `_mechanism_wip_over_cap_violations()` 双条件判定，缺开关／缺标记两种提示各不相同。**一次新增多条机制行时要求每条各自写明理由**——spec 按单条表述，此为其在多行输入下的显式取舍（每条新行都是一次独立的 WIP 增量），已写进函数 docstring
- [x] 3.5 文案含「当前 N／M」＋新增行编号＋两条出路确切写法（`[S:done]` 关行 ／ `WIP豁免：` ＋ 开关），由 `test_mechanism_wip_rejection_message_is_actionable` 逐项钉住
- [x] 3.6 单测全覆盖：超限拒绝（并断言**锁保持占用**）／文案可行动／未超限放行／业务类行不触发／**存量超限但本次未新增机制行仍放行**（决策点 4 关键回归，已在既有用例上补写红字说明其为「防把自己锁在门外」）／逃生阀齐备放行（并断言理由**确实留在队列文本里**）／只给开关拒绝／只写标记拒绝／多条新行各需自带理由
- [x] 3.7 `MECHANISM_WIP_CAP_DEFAULT` 仍为 **16，未动**（§四 #58 ⑴）；两个参数的 help 文案均已改写（`--mechanism-wip-cap` 由「仅提示不阻断」改为「拒绝」，新增 `--force-mechanism-wip` 说明双条件）

## 4. 收尾

- [x] 4.1 模块头部说明段新增「队列 #324 ＋ §四 #58 ⑶」小节；`_validate_release_structure` docstring ⑥／⑨ 两段同步改写（含决策点 4「规则会把自己的解法锁死」的红字、⑥ 的残余风险声明与退休说明）
- [x] 4.2 队列协议〇.9 措施 C 正文已追加 2026-08-17 段：⑵ 由「提示不阻断」改为「阻断＋逃生阀」，写明理由须落行内、开关与标记缺一即拒
- [x] 4.3 全量回归零漂移：`0-学习与工具` 全套 **428 passed ＋ 26 subtests**（其中编辑锁 170 ＋ 5 subtests，含本次新增 13 个用例）／`工具-队列结构lint.py` 对两份真身通过／`openspec validate --all --strict` **80/80**／`git status --porcelain` 无任何新形态未跟踪文件（兑现 proposal 的 `.gitignore` 问答）
- [ ] 4.4 **真实 dogfooding**：本包 apply 自身的 `release` 即会撞上 ⑨（存量 24／16）——如实记录当次是走了关行还是走了逃生阀，作为晋档条件①②的第一份真实样本
- [ ] 4.5 队列 #324 与 §四 #58 第⑶条回填实现结果
- [ ] 4.6 值周巡检 prompt／派单件模板知悉：apply 当天起新建机制行会被真的挡住（`1-转型规划/0-全景路线图/专线opener模板库.md`）
- [ ] 4.7 `/opsx:archive editlock-hold-scope-and-wip-block -y`（全部 tasks 勾完才做）
