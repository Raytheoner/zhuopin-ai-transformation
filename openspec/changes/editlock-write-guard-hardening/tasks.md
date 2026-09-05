# editlock-write-guard-hardening Tasks

> ✅ **design 审已过**（Shao Peishen 2026-09-05 现场逐条拍板五个决策点，结论表见 `design.md` 文首）。apply 由 `OP-0905-P` 在分支 `claude/op0905n-editrow-guard-455` 执行。
> 执行环境：**CC**（写生产码、跑测试、自行 commit+push，一任务一 worktree）。

## 0. 前置闸（design 审后、动手前）

- [x] 0.1 确认 design 审结论已回填队列 §一 `#455` 行 —— 五条拍板结论已白纸黑字随派单件下达并照录进 `design.md` 文首结论表；队列 §一 `#455` 行回填见 5.1
- [x] 0.2 触碰区核对 —— 手段：`git for-each-ref` 遍历全部本地分支跑 `git log master..<branch> -- 0-学习与工具/工具-共享文档编辑锁.py`。命中 2 条（`claude/queue-315-apply-9f2c1a`、`claude/unified-portal-design-8a2ce3`），再用 `git diff master...<branch> -- <该文件>` 三点比对**均为空**（两点比对 3353 行）⇒ 二者对该文件的内容**落后于 master、非领先**，无在途冲突。**结论：无其它在途 openspec 变更包同时改动 `cmd_edit_row`/`cmd_append_row`。**
- [x] 0.3 `pip show zhuopin_platform` 的 `Editable project location` = `C:\Dev\zhuopin-ai\5-平台底座\zhuopin_platform`（**指向主 checkout，不是本 worktree**——#98 记的静默漂移陷阱现形）。已按 #300 既有对策核实实际生效的是哪一份：取证脚本显式 `sys.path.insert` 本 worktree 路径后打印 `queue_table.__file__`，确认为本 worktree；单测经被测模块自身的路径引导取 `queue_table`（新增 `_queue_table()` 辅助函数，docstring 已写明理由），不另写第二份引导。

## 1. 取证与口径（🔴 必须先于实现）

- [x] 1.1 白盒读 `queue_table.py::_mask_backtick_spans`／`split_row_cells`／`has_bare_pipe` 与 `工具-共享文档编辑锁.py::cmd_edit_row`／`cmd_append_row`，挂载点已确认（落点表见 `design.md` 末「apply 期落地清单」）
- [x] 1.2 🔴 **现网全量实测** —— 手段：一次性扫描脚本，逐行跑游程配对＋按分区核列数。结果：
  - **两份现网队列共 349 条表格行，未闭合游程 0 条**（机制环境 237 行／业务场景 112 行）。
  - **塌列行 0 条**（机制环境 §一 101／§二 36／§四 91；业务场景 §一 44／§二 64）⇒ `#337`／`#422` 已被此前工作修复，**现网无遗留塌列行**。
  - **另发现（超出本项原定范围，如实登记）**：归档件 `跨桌任务队列-归档-202608.md` 7 行、`-202609.md` 1 行含未闭合游程；且 `-归档-202607.md` 行166（§二，5 列/表头 4 列）与 `-归档-202608.md` 行395（§一 #232，3 列/表头 8 列）**两条已塌列的归档历史行**。归档件不是 `edit-row`／`append-row` 的写入目标，本次不追改，处置见 4.2。
  - **意外收获（已转为 3.3 的夹具）**：机制环境 §一 #414 行是全网**唯一**一条「反引号总数为奇数（83 个）却游程全闭合」的真实合法内容 ⇒ 坐实 design 决策点①(b)「总数奇偶」简化判据会误判真实生产行。
- [x] 1.3 🔴 「故意写孤立反引号」核实 —— **现网两份队列零命中**（如实记录为"零命中"，非"不存在"）⇒ design 决策点②「先不加逃生阀」的前提成立。归档件那 8 行已逐条定性：**5 行**＝§二「建议 message」格开头一个反引号包裹整段 commit message、**漏了闭合**；**3 行**＝同行前面反引号为奇数造成配对级联错位后剩下的孤立**闭合侧**。两类均非「故意为之的孤立反引号」，正是本包要拦的形态。
- [x] 1.4 消费者核实（proposal Impact 的"未核"项销账）—— 手段：对 `工具-队列结构lint.py`／`工具-落库sweep.py`／`工具-队列查询.py` 三份文件 grep `edit-row`／`append-row`／`returncode`。**结论：无一处消费 `edit-row`/`append-row` 的返回码或 stdout 格式。** 三处对编辑锁的引用分别是：sweep `L4852` 解析的是 `status` 子命令的 stdout（不是本包改动的两个子命令）；lint `L68` 是 import 模块取解析函数；query `L68` 只是注释里的路径引导指针。⇒ 新增的拒绝路径（返回 1 ＋ 新文案）**不破坏任何下游**。

## 2. 实现

- [x] 2.1 `queue_table.has_unbalanced_backtick_run(text) -> bool`（＋私有 `_first_unbalanced_backtick_run` 供诊断定位）；docstring 已显式对比 `_mask_backtick_spans` 的"未闭合视为普通文本"这一相反选择，并写明"同一形态，读侧宽容是对的、写侧宽容是错的"的理由
- [x] 2.2 `cmd_edit_row`（对 `sets`/`appends` 归一后的 `changed_values` 逐个）与 `_build_append_row_line`（对每个内容格）各跑一次奇偶校验，不通过即拒绝并指出字段名／第几个 `--cell`。**按决策点② 不加逃生阀**
- [x] 2.3 `cmd_edit_row` 拼出 `new_line` 后、写盘前新增回读校验（`split_row_cells` × `SECTION_COLUMN_COUNTS`），不符拒绝
- [x] 2.4 `cmd_append_row` 原裸 `new_line.strip("|").split("|")` 已替换为 `queue_table.split_row_cells`，与 2.3 口径统一
- [x] 2.5 `cmd_edit_row --repair` —— 仅滤掉 `validate_row_cells` 的「旧行列数」那一条 problem（前缀按 `queue_table` 的构造原样重建，另有单测钉住该耦合，避免文案漂移后静默失效）。🔴 **apply 期补齐 design 未覆盖的一处空缺**：`--repair` 另需在缺列时把单元格补白到预期列数（**只补短、不裁长**），否则缺失列下标越界、② 回读恒不过，`--repair` 将是永远不可能成功的开关——详见 `cmd_edit_row` 内长注释与 `design.md` 末的登记
- [x] 2.6 移除 `cmd_edit_row`／`_build_append_row_line` 内 `has_bare_pipe` 的前置准入拒绝；`_build_append_row_line` 的 `validate_row_cells` 由 `source="write"` 改传 `"parsed"`（该参数**只影响竖线一项**，`validate_row_cells` 本身未改）。`has_bare_pipe`／`_cell_has_bare_pipe` 函数保留，现存唯一用途＝`_arity_failure_message` 的**成因诊断**（#351 打磨过的文案，非准入判据），docstring 已补记
- [x] 2.7 `cmd_append_row` 显式拒绝 `--repair`（刻意登记该参数只为能带去向地拒绝，而非让 argparse 报 "unrecognized arguments"），并指向 `edit-row --repair`
- [x] 2.8 模块文件头新增 #455 段（①②③ 三条判据的成因、判据、代价与边界）；`_cell_has_bare_pipe` docstring 补记"不再承担准入判定"；两个子命令的 `--repair` help 文本写全前置条件

## 3. 测试

新增测试类 `WriteGuardHardeningTests`（`0-学习与工具/test_工具-共享文档编辑锁.py`），22 条全绿。

- [x] 3.1 `test_31_unbalanced_backtick_in_new_value_rejected_without_writing` ＋ `test_31b_append_row_unbalanced_backtick_rejected`（两个入口各一条，证明判据不是只装了一半）
- [x] 3.2 `test_32_closed_backtick_span_containing_pipe_is_accepted` ＋ `test_32b_locked_row_status_prefix_can_now_be_flipped`（后者复现 #324 的真正伤害形态：含合法反引号竖线的行，其 `[S:]` 前缀此前无法翻转）
- [x] 3.3 `test_33_odd_backtick_count_but_balanced_runs_is_accepted` —— 夹具取自 1.2 实测到的生产队列 §一 #414 真实写法；用例先断言"夹具确为奇数个反引号"再断言放行，非恒真
- [x] 3.4 `test_34_readback_column_mismatch_rejected_without_writing`
- [x] 3.5 `test_35_append_row_with_legal_backtick_pipe_reads_back_correctly`
- [x] 3.6 `test_36_collapsed_row_rejected_without_repair`（`--append` 亦拒）
- [x] 3.7 `test_37_repair_with_reason_restores_row` ＋ `test_37b_repair_padding_does_not_bypass_key_cell_sentinels`（补白不等于放宽）＋ `test_37c_repair_leaves_over_long_rows_to_human_judgement`（只补短不裁长）
- [x] 3.8 `test_38a_repair_does_not_relax_backtick_parity` ＋ `test_38b_repair_does_not_relax_readback_column_count`
- [x] 3.9 `test_39_append_row_rejects_repair_and_points_to_edit_row`（并断言拒绝**带去向**）
- [x] 3.10 🔴 **反向用例（非恒真自证）三条**：
  - `test_reverse_31_passes_once_the_new_parity_judge_is_disabled` —— 把 ① mock 成恒 `False`（＝本包实现前的状态），3.1 的同一输入由"拒绝"变为"放行"并真的落盘 ⇒ 拒绝确实来自 ① 本身。（顺带证明 ② 不会替 ① 兜底：未闭合游程被读侧当普通文本，回读列数不变。）
  - `test_reverse_35_old_naive_split_gives_a_different_verdict` —— 在 #324 夹具上直接比出旧裸 `str.split("|")` 得 9 列、新 `split_row_cells` 得 8 列，**同一输入结论相反** ⇒ 3.5 的放行确来自这次替换。
  - `test_reverse_34_bare_pipe_now_rejected_by_readback_not_has_bare_pipe` —— 把 `has_bare_pipe` 换成"一被调用就炸"，3.4 的同一输入仍被正常拒绝 ⇒ 旧前置检查**确已移除**，且拒绝来自 ② 而非它。
  - 另有 `test_repair_filter_stays_pinned_to_queue_table_message` 钉住 `--repair` 滤除前缀与 `queue_table` 文案的耦合；`test_fixtures_are_what_they_claim` 先自证两条历史夹具确是它们声称的形态（8 列含合法反引号竖线／7 列已塌列），避免后续断言测在假场景上。
- [x] 3.11 `0-学习与工具` 全量回归绿、零漂移（结果见 5.x 收口记录）
- [x] 3.x **行为反转的既有用例（proposal 明写的 BREAKING，非回归）**：`test_backtick_wrapped_pipe_also_rejected` → `test_backtick_wrapped_pipe_now_accepted`，docstring 已写明反转依据（其前提「本项目表格解析对反引号无感知」早在 #314 就失效，写侧一直没跟上）。`test_bare_pipe_still_rejected_on_write_side` 断言保留不变、docstring 更新（#455 后拒绝它的是 ② 而非 `has_bare_pipe`），并加断言 `回读列数` 以钉住"由谁拒绝"这件事。

## 4. 现网验证（不落盘）

- [x] 4.1 用本包**已实现**的判据（`queue_table.has_unbalanced_backtick_run` 与 `split_row_cells`）对现网两份队列做只读全量跑，命中集与 1.2/1.3 一致：未闭合游程 0、塌列 0。⇒ 实现与取证未脱节。
- [x] 4.2 现网**无**遗留塌列行（`#337`/`#422` 已修复），故本次**无需**用 `--repair` 修任何现网行 ⇒ proposal 晋档条件第 3 条（真实用一次 `--repair`）**本次未被检验**，如实标注为"未被检验"，不得表述为"已具备"。归档件那 2 条塌列行（`-202607.md` 行166、`-202608.md` 行395）**选择不追改**，理由：① 归档件不是两个写入子命令的目标文件，不构成本包判据的作用面；② 追改归档件与「历史记录不追改」直接冲突；③ 它们不影响任何现网读写路径。已在 5.1 回填队列 `#455` 行内如实登记。

## 5. 收口

- [x] 5.1 队列 §一 `#455` 行回填（走编辑锁协议 `acquire` → `edit-row` → `release`）
- [ ] 5.2 `#324`／`#454` 行内各追加一段指针 —— **本次不做**：`#324`/`#454` 是他人触碰区的队列行，按「决策路由」属"改他人触碰区"⇒ 不就地改，随 5.1 一并登记待总线派发
- [ ] 5.3 §二 批次登记，触发 sweep，核 `reports/sweep-commit.log`
- [ ] 5.4 `/opsx:archive editlock-write-guard-hardening -y` —— **暂不归档**：本包停在「合并决策点」等 Shao Peishen 拍板是否 ff 进 master（泳道 `455-apply` 已 `pause`），未合入前不归档
