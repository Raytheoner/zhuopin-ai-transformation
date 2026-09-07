# followup-status-metadata-gates Tasks

> 🔴 **1／2／3 已在分支 `claude/op0907ad-followup-metadata-447` 完成（worktree 内建造，未合入 master）；4 起全部卡在 design 审之后。**

## 0. design 审（🟡 档，须 Shao Peishen 拍板）

- [ ] 0.1 **D1** 第九态 `📨 回件已到，待拆件` 要不要进 `--status` 闭集（推荐 (a) 纳入＝当前实现）
- [ ] 0.2 **D2** S4 桥自动转态写不写尾标（推荐 (a) 本包不改桥，另立队列一行交 `#366`／`#446` 实现方）
- [ ] 0.3 **D3** `✅ 无需回复`／`❌ 已作废` 要不要也强制事实日（推荐 (a) 维持不强制）
- [ ] 0.4 **D4** 与 `followup-readme-phase2`／`followup-decision-point-gate` 的合入排序复核
- [ ] 0.5 复核 D5 与「已落定的取舍」八条

## 1. 写侧实现（已完成，待 design 审后方可合入）

- [x] 1.1 复用 `zhuopin_platform.coverage_point_ledger.models.FACT_DATE_UNKNOWN`——**不自持第二份字面量**（单测 `assertIs` 断言同一对象）。
- [x] 1.2 `--fact-date` 参数 ＋ `_assert_fact_date`：必填判定（四个承载事实日的状态）、`YYYY-MM-DD` 真实存在性、不晚于本机当天、`事实日未知` 字面量放行。
- [x] 1.3 `_today()` 独立成函数（仅为可注入；生产路径恒走 `date.today()`，**补记日不接受传参**）。
- [x] 1.4 `FACT_MARK_RE`／`_parse_fact_mark`／`_render_fact_mark`／`_apply_fact_mark`：规范尾标 `〔事实日 X ／ 补记日 Y〕` 的写与读；已有尾标先摘再写，不叠加两枚。
- [x] 1.5 `_resolve_fact_mark`：同状态不可覆盖（逃生阀 `事实日更正：`）／换状态即换事实／`事实日未知` 可升级为具体日期（找回信息，非销毁）／不承载事实日的状态原样带过旧尾标。
- [x] 1.6 `[PLAN]` 三分支回显（不承载／`事实日未知` 单列提示／滞后天数）＋ 滞后 ≥14 天的 `[NOTE]`。
- [x] 1.7 **O1** `CANONICAL_EIGHT_STATUS_PREFIXES`／`CLI_STATUS_CLOSED_SET`／`_assert_status_in_closed_set`，拒绝文案区分「认得但已退役」与「完全不认得」。
- [x] 1.8 **O2** `_roster_names`（复用 `editlock.PERSON_GENDER_ROSTER` ＋ 规模下限守卫）／`_assert_recipient_cell`（分隔符／在册／部门一致）。
- [x] 1.9 **O3** `LEGACY_DECISION_FIELDS`／`_assert_no_legacy_decision_fields`，挂在 `_assert_decision_points` 末尾。
- [x] 1.10 模块 docstring 新增「O1–O3 与事实日／补记日」一节 ＋ 用法示例补 `--fact-date`。

## 2. 读侧实现（已完成）

- [x] 2.1 新建 `0-学习与工具/工具-跟进信往返度量.py`：四桶分类、往返天数、补记滞后。
- [x] 2.2 importlib 复用写侧的尾标正则、`FACT_DATE_UNKNOWN`、`FACT_DATE_REQUIRED_PREFIXES`——**不自持第二份判据**。
- [x] 2.3 `MIN_SAMPLES_FOR_MEDIAN = 5`：样本不足即拒报中位数、说明原因，不报 0、不拿另两桶凑数。
- [x] 2.4 渲染文本显式写「各自单列」「不许合并」，并在可算为 0 时说明「属当下的正常输出，不是脚本坏了」。
- [x] 2.5 `--json`／`--file`（可指向归档件）；主表无数据行即报错，不返回空报告。

## 3. 单测与回归（已完成）

- [x] 3.1 `test_工具-跟进信README登记.py`：新增 `LegacyDecisionFieldTests`(3)／`RecipientCellTests`(6)／`StatusClosedSetTests`(4，含 8 subtests)／`FactDateTests`(14)／`FactMarkParseTests`(3)；`_FakeArgs` 增 `fact_date` 默认值；1 条既有用例按新语义补 `fact_date`。全绿 **61 passed ＋ 8 subtests**（改前 30）。
- [x] 3.2 `test_工具-跟进信往返度量.py`（新）：分桶 5 条／中位数 3 条／判据同源 1 条（含写侧渲染→读侧解析的端到端）／坏输入 2 条／渲染与 CLI 3 条。**14 passed**。
- [x] 3.3 度量脚本对**生产 README 只读实跑**：45 行 ⇒ 可算 0 ／ 事实日未知 0 ／ 无标注 36 ／ 不适用 9，四桶之和 ＝ 45，拒报中位数并说明原因。
- [ ] 3.4 `0-学习与工具/` 全量回归（后台执行中，结果补记于本行）。

## 4. 合入（🟡 档，design 审通过后）

- [ ] 4.1 `git merge-base --is-ancestor` 核可快进后 ff 合入 master（须在 D4 排序之后）。
- [ ] 4.2 `git status --porcelain` 核实无任何新形态未跟踪文件。
- [ ] 4.3 `openspec validate followup-status-metadata-gates --strict` 通过。

## 5. 文档落字（🔴 前置条件：先真实验活，后改文字）

- [x] 5.1 `6-人才与组织/部门AI专员跟进/跟进机制-判据版.md` §二 增 O1 一条 ＋ 新增 §二bis「状态列的日期语义」（**这一步不依赖验活**——它只是把新的正确用法写对，不是把人守降成机器守）。
- [ ] 5.2 🔴 **前置条件：本闸已在真实转态流程里至少拒绝过一次并留痕。** 满足后才把 §二 末条「配套义务」里「写 `<日期>`」那一段降为指向 §二bis 的一行。⚠️ 「必须手工转态」半句**不退休**——机器守的是「日期写什么」，不是「有没有人去转态」。
- [ ] 5.3 `.claude/rules/跟进信与专员.md` 的 `set-status` 示例句补 `--fact-date`（可随 4 一起做）。

## 6. 观察窗口（交付后）

- [ ] 6.1 ≥5 次真实转态，逐次核实事实日**不等于当天**的比例。
- [ ] 6.2 🔴 若出现「为过闸而一律填当天」⇒ **重评判据而非放宽**（该假数据形态恰好就是 2026-08-23 那次事故本身）。
- [ ] 6.3 🔴 窗口内零命中 ⇒ 正确表述是「未被检验」，**不得**表述为「事实日销毁问题已解决」，且不得据此改 5.2 的文字。
- [ ] 6.4 盯度量脚本「可算」桶是否长期为 0（若是 ⇒ 说明转态都走了桥或没走 CLI，回到 D2）。
