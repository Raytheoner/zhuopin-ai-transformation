## 1. 登记 CLI（D1，`followup-readme-registry`）

- [x] 1.1 新建 `0-学习与工具/工具-跟进信README登记.py`：复用既有 README 表格解析实现（`readme_table`/`followup_gate`），不新造第二份解析器；数字取号复用 `工具-跟进闸查询.py::_next_available_number`（importlib 加载，同目录既定手法）。
- [x] 1.2 实现 `append` 子命令：按部门计数器自动取号（未发出不占号）、走 `工具-共享文档编辑锁.py --file <README>` 单文件锁、写前列数校验（范围收窄为本次触碰行，见下）、写后回读；新增行「发送状态」强制 `⏳ 待你审`（非该值拒绝）；**新增前置串行闸检查**（design 未预见、对真实 README 实测发现补入：release 时既有「跟进信串行原则」结构校验只在写入后拦截，会留下「文件已改、release 被拒、锁未释放」的中间态，故把同一判据前移到写入前，见 spec 新增 Requirement）。
- [x] 1.3 实现 `set-status` 子命令：按编号定位、状态枚举校验（改用 `followup_gate.classify_status != "unknown"`，不是 spec 初稿假设的窄枚举——对真实 README 实测发现生产状态词汇比派单件列的 6 个值丰富，见 spec 修订）；编号未命中主表时查归档件（`_find_in_archives`，归档件尚不存在时天然返回未命中，非特殊分支），命中则报「已归档不可再用本命令改状态」，均未命中报「编号不存在」。
- [x] 1.4 实现字段长度上限校验：`主要事项` ≤600B、`交期要点` ≤400B（按 UTF-8 字节），超限拒绝并提示改用行长外置。
- [x] 1.5 单测（`test_工具-跟进信README登记.py`，18 条全绿）：append 成功/闸锁拒绝/字段超限/历史行列数异常不阻塞/dry-run/release 被拒绝不得报告成功，set-status 合法/自由后缀/非法值/编号不存在/编号已归档/回读失败保留锁/release 被拒绝不得报告成功/dry-run，main 入口 argparse 冒烟——覆盖 `followup-readme-registry` spec 全部 Scenario。
- [x] 1.6 `--dry-run` 模式（两条子命令均支持，供验收条款“真实追加测试信后删除或用 --dry-run”使用）；已对真实 README 做过一次 dry-run + 一次真实 append/set-status 往返验证（陈忱 `质量部#14`，验证后已用 git diff 核对仅新增该行、随即移除，主仓 README 已恢复逐字节一致）。

**2026-09-06 实现过程中对真实 README 实测发现并已修正的 3 项（均已同步回 spec/design，非静默偏离）**：
① 写前列数校验范围从「全表」收窄为「本次触碰的行」——真实主表 `采购部#14` 因历史「发送状态」段内混入未转义 `|` 被朴素分列多出一列，全表校验会让 CLI 对该行存在期间完全不可用；
② `set-status` 状态枚举改用 `followup_gate` 权威判据集合，不用派单件列的窄清单（真实状态含 `✅ 无需回复`／`📨 已确认闭环`／`📨 回件已到，待拆件` 等，窄清单会拒绝这些合法值）；
③ `append` 增加前置串行闸检查（见上）。

## 2. 已闭环归档（D2，`followup-readme-archive`）

- [x] 2.1 产出「12 个读取方基线输出」：`工具-跟进闸查询.py --all --json`／`工具-跟进信README查询.py --digest`／`工具-共享文档编辑锁.py status` 已落盘 `openspec/changes/followup-readme-phase2/baseline-2026-09-06/`（其余读取方的行为基线由 2.7 迁移前后各跑一次全量单测比对，而非逐个只读输出快照）。
- [x] 2.2 把 design.md D2 决策表（9 个具名读取方分类结论）提交 Shao Peishen 书面确认——**已确认（2026-09-06）**：其余 8 个按原判定执行归档，唯一补充＝`followup_readme_bridge.py` 需要归档回退查找。
- [x] 2.4bis（Shao Peishen 唯一补充项，先于 2.3 落地——它是归档动作本身会引入的误配风险，须先堵住再执行迁移）：`followup_readme_bridge.py` stem 匹配活表未命中时查归档件；新增 `followup_gate.PAIR_MISS_ARCHIVED_STEM`＋`_stem_match_in_archives`＋`resolve_letter_number` 判据统一为 `outcome.letter`；5 条新单测全绿（`test_followup_readme_bridge.py::TestArchivedStemMatch`），aibot-service 全量 773 passed／platform 全量 466 passed，零回归。已同步补 `followup-readme-archive` spec 新 Requirement。
- [x] 2.3 新建 `0-学习与工具/工具-跟进信README归档.py`：判据＝终态标记（`📥 已回件并回灌`／`❌ 已作废`）且「日期」列（发送日）距今 >30 天，整行原文原样迁 `README-归档-YYYYMM.md`（表头同，按运行时刻年月归一批），走共享编辑锁，写后回读校验，重复运行按编号去重幂等。15 条单测全绿（`test_工具-跟进信README归档.py`）。**已对真实 README 执行一次真实迁移**（2026-09-06，`--who CC-OP0906A`）：19 行迁出 → `README-归档-202609.md`（30,530 B），主表由 177.7 KB 降至 144.1 KB（147,588 B）。
- [x] 2.3bis（实现过程中发现并修正的第二处真实缺口，先于 2.7 验证前修复）：`工具-跟进闸查询.py::_next_available_number` 此前只扫主表——若某部门历史高编号信已归档、主表仅剩低编号在途信，取号会往回算、与刚归档的编号相撞，直接违反「归档编号不复用」。新增 `_archived_max_number` 同时扫全部归档件，取号算法改为两者取最大值 +1；同步新增 `_archived_recipients`：`build_report`/`all_recipients` 此前把「主表已无该收信人任何行」一律当「这个人不存在」报错——**对真实 README 归档后立即实测坐实**（首个真实归档批次里「销售部 · 泓钦」的唯一一封信被归档后，`--to 泓钦` 从正常返回闸开退化为报错「不存在」）；修正后主表无该收信人时先查归档件，命中则报「无在途、闸开」，未命中才报不存在。均已补充单测（`test_工具-跟进闸查询.py` +3）、同步补 `followup-readme-archive` spec「归档编号不复用」Requirement 新 Scenario。
- [x] 2.4 登记 CLI `set-status` 的编号查找已在 1.3 实现「主表未命中再查归档件」两段式查找（`_find_in_archives`）；已用真实归档件（`README-归档-202609.md`）验证：对已归档编号（如 `采购部#7`）调用 `set-status` 正确报「已归档不可再用本命令改状态」。
- [x] 2.5 `工具-跟进信README查询.py` 新增显式 `--file <归档件>` 用法（同队列查询工具先例），供人工核对历史；默认行为不变，2 条新单测全绿。
- [x] 2.6 单测：归档判据（满足/不满足 30 天、非终态不迁移、已作废也算终态、日期列非法值跳过、历史列数异常行不参与判定不报错）、内容原文原样、编号不复用（含 2.3bis 归档扫描场景）、活行读取方归档后行为不变（含「该收信人主表无任何行视为无在途」边界，2.3bis 已实现并测试）——`followup-readme-archive` spec 全部 Scenario 覆盖完毕。
- [x] 2.7 用 2.1 的基线逐一 diff 归档后各读取方的实际输出：`工具-跟进闸查询.py --all --json`——除「泓钦」一条（其唯一信被归档，表示形态从「主表行」变为「历史信件均已归档」，语义正确、内容不同属预期）外逐字节相同；`工具-跟进信README查询.py --digest`——行数从 63→44（差额 19 正好等于迁移行数，且被移除的行经核对全部是本批迁移的行），「⏳ 待你审／🆕 待发／⏸ 暂缓」三态计数（sweep 待发信盘点唯一消费的字段）迁移前后均为 `0／0／0`、逐字节相同；全量单测重跑：0-学习与工具 1494 passed（另 4 个失败均为与本包无关的既有真实仓库状态类测试，`test_发企微.py`/`test_工具-CLAUDE进度段lint.py`/`test_工具-引导样板lint.py`，与 README/跟进信无关文件）、aibot-service 773 passed 1 skipped、platform 466 passed 1 skipped——**本组完成**。

## 3. 行长口径与外置（D3，`followup-readme-row-length-guard`）

- [x] 3.1 实现 `发送状态` 超阈值外置到 `跟进信行日志/<编号>.md`（原文原样，行内留首段＋末段＋指针），复用队列 K2 外置手法。**阈值口径续棒补充（环境总线拍板，2026-09-06）**：复用队列 `ROW_LENGTH_CAP_BYTES`（4 KB），非派单件原文的 5 KB。
- [x] 3.2 实现 `主要事项` >600B 压缩为摘要、原文写入同一行日志文件。摘要算法＝首句或前 200 字＋指针（确定性截断，不做语义压缩，同批拍板）。
- [x] 3.3 对现存 25 行 `主要事项` >600B（含 1 行 `发送状态` >4KB）的历史行执行一次性外置迁移——**已对生产 README 真实执行**（`--who CC-OP0906D`），主表 144.1KB → 76.8KB。
- [x] 3.4 `工具-共享文档编辑锁.py` release 校验族对 README 加同款行长判据：新增 `_readme_row_length_warnings_and_violations`／`_readme_touched_rows`（README 是单一 flat 表，不复用 `_ROW_LENGTH_CHECK_INDEX` 的 label 映射手法，另写结构并列、判据同源的独立函数）；阻断日期 `2026-09-13`（能力 2026-09-06 上线，满一周，与队列⑪的 `2026-09-11` 独立）。
- [x] 3.5 实现逃生阀 `行长豁免：` 标注识别，标注行不被阻断——直接复用 `_has_genuine_row_length_waiver`/`ROW_LENGTH_WAIVER_MARKER`（同一份判据，不新造）。
- [x] 3.6 单测：`FollowupReadmeRowLengthGuardTests`（6 条，`test_工具-共享文档编辑锁.py`）覆盖告警/阻断/豁免/未触碰行不追溯；`test_工具-跟进信README行长外置.py`（28 条）覆盖摘要算法/压缩算法/计划判定/真实迁移/幂等/串行闸冲突消解。
- **🔴 真实执行中发现的设计缺口（design.md 未预见，已修复并补测）**：压缩「主要事项」列会改变 `_followup_row_identity`，可能触发跟进信串行原则闸误判"纯历史压缩"为"新起草跟进信"（真实撞见 4 行）。修法：外置工具内新增 `_find_serial_gate_conflicts`／`_resolve_serial_gate_conflicts`，复用既有 `串行豁免：` 逃生阀写在「交期要点」列，最终用官方 `_validate_followup_readme_release` 复核兜底。详见派单件"件③④完工"节。

## 4. 门禁（D4，`followup-readme-read-guard`）

- [x] 4.1 `hooks-pretooluse-queue-read-guard.ps1`：`$script:ProtectedExactRel` 追加 README 主表精确路径。
- [x] 4.2 同一 hook：归档件保护改造为 `$script:ProtectedArchivePatterns`（目录＋正则配对数组），追加 README 目录 + `README-归档-.+\.md` 一对（与队列那对目录不同，不共用同一目录变量）。
- [x] 4.3 机制工具白名单加入登记 CLI（`工具-跟进信README登记.py`）、`工具-跟进信README归档.py`、`工具-跟进信README查询.py`、`工具-跟进信README行长外置.py`（件③新增，一并加入）。
- [x] 4.4 单测：`test_hooks-pretooluse-queue-read-guard.py` 新增 11 条用例（README 主表/归档件的 Read／Grep／Bash 三通道拦截 + 四个机制工具白名单放行），全量 36 条通过。
- [x] 4.5 真实验证：对生产 README 发起 Read 请求实测拦截（退出码 2），`reports/hooks-audit.jsonl` 留下对应 `violation` 审计行（`2026-09-06T12:28:35.039+08:00`）。
- [x] 4.6 产出 rules/SKILL 改句建议文本（`.claude/rules/跟进信与专员.md`、`zhuopin-followup-letter`／`zhuopin-send-followup` SKILL）——已写入派单件"改句建议"小节，交 Cowork 落字，本包未自改这两类载体正文。

## 5. 收尾

- [x] 5.1 跑全量：`test_工具-跟进闸查询.py`／`test_工具-跟进信README查询.py`／`test_工具-共享文档编辑锁.py`／`test_hooks-pretooluse-queue-read-guard.py`／`test_工具-跟进信README行长外置.py`／aibot 相关单测——见收工报告，零回归。
- [x] 5.2 核对验收条款：主表 **未达 ≤60KB**（实测 76.8 KB，如实登记，非估算数字——25 行摘要化的实际节省量小于原估算）；`工具-跟进闸查询.py --to 唐燕萍`／`README查询 --digest` 输出与改前基线一致（改前基线已存 `reports/baseline-op0906d/`）；未改表头/列序；未动 `.51`；未发企微。
- [x] 5.3 `openspec validate followup-readme-phase2 --strict` 通过。
- [x] 5.4 队列 §一 `#490` 回写销号（本次续棒完工后回写，见派单件"队列回写"小节）。 —— ✅ 2026-09-06 `OP-0906-W` 核勾：`工具-队列查询.py --row 490` 状态列首段已为 `[S:done][D:机]`（回写销号实已发生、只是本项未勾）
- [x] 5.5 commit + `git push origin HEAD:master`（先 `merge-base --is-ancestor` 核可快进）； —— ✅ 2026-09-06 `OP-0906-W` 核勾：登记 CLI 已合入 master（`#490` 行自陈 commit `5e95bd5`）；sweep 21:17 轮起跑补推后 `git rev-list --count origin/master..master`＝0。**由此 `followup-decision-point-gate` D4(a)「先收尾本包」前提已满足，A2 分支可合。**登记 §二 批次——**README 主表与新增行日志文件已随 `B-0906D_readme行长外置` 批次登记**（主仓共享文件，由 sweep 或本 session 收尾时处理，非本 worktree 分支提交范围）；本 worktree 分支自身的代码/spec/openspec 改动另行 commit+push。
