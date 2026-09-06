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

- [ ] 3.1 实现 `发送状态` >5KB 外置到 `跟进信行日志/<部门#N>.md`（原文原样，行内留首段＋末段＋指针），复用队列 K2 外置手法。
- [ ] 3.2 实现 `主要事项` >600B 压缩为摘要、原文写入同一行日志文件。
- [ ] 3.3 对现存 12 行 >5KB 的历史行执行一次性外置迁移。
- [ ] 3.4 `工具-共享文档编辑锁.py` release 校验族对 README 加同款行长判据：复用队列行长校验⑪代码路径，扩展保护目标；先接入告警模式。
- [ ] 3.5 实现逃生阀 `行长豁免：` 标注识别，标注行不被阻断。
- [ ] 3.6 单测：>5KB/>600B 触发外置、告警模式不阻断、豁免标注不阻断——覆盖 `followup-readme-row-length-guard` spec 全部 Scenario（阻断模式的单测先写好、暂标注为「满一周后启用」，与队列⑪先例的两阶段上线节奏一致）。

## 4. 门禁（D4，`followup-readme-read-guard`）

- [ ] 4.1 `hooks-pretooluse-queue-read-guard.ps1`：`$script:ProtectedExactPaths` 追加 README 主表精确路径。
- [ ] 4.2 同一 hook：`$script:ProtectedArchiveNameRegex` 同款正则形式追加 `README-归档-.+\.md` 匹配。
- [ ] 4.3 机制工具白名单加入登记 CLI（`工具-跟进信README登记.py`）与 `工具-跟进信README查询.py`。
- [ ] 4.4 单测：`test_hooks-pretooluse-queue-read-guard.py` 补 README 主表/归档件命中拦截、机制工具白名单放行两类用例。
- [ ] 4.5 真实验证：一次尝试 Read README 主表被拦截，确认 `reports/hooks-audit.jsonl` 留痕。
- [ ] 4.6 产出 rules/SKILL 改句建议文本（`.claude/rules/跟进信与专员.md`、`zhuopin-followup-letter`／`zhuopin-send-followup` SKILL）交 Cowork，本包不自改这两类载体正文。

## 5. 收尾

- [ ] 5.1 跑全量：`test_工具-跟进闸查询.py`／`test_工具-跟进信README查询.py`／`test_工具-共享文档编辑锁.py`／`test_hooks-pretooluse-queue-read-guard.py`／aibot 相关单测，零回归。
- [ ] 5.2 核对验收条款：主表 ≤60KB；`工具-跟进闸查询.py --to 唐燕萍`／`README查询 --digest` 输出与改前基线一致；不改表头/列序；不动 `.51`；不发企微。
- [ ] 5.3 `openspec validate followup-readme-phase2 --strict` 通过。
- [ ] 5.4 队列 §一 `#490` 回写销号（产出路径、测试结果、rules/SKILL 改句建议文本已移交 Cowork）。
- [ ] 5.5 commit + `git push origin HEAD:master`（先 `merge-base --is-ancestor` 核可快进）；登记 §二 批次（清单只写真实脏改动路径）。
