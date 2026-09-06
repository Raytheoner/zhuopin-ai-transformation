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

- [ ] 2.1 产出「12 个读取方基线输出」：对 `工具-跟进闸查询.py`（逐收信人）、`工具-跟进信README查询.py --digest`、`工具-共享文档编辑锁.py status`、`工具-落库sweep.py`（待发信盘点相关输出）、`followup_readme_bridge.py`、`approve_followup_letter.py`／`dispatch_followup_letters.py`／`draft_gap_check.py`／`push_followup_letter.py`（各自只读/dry-run 路径）及其单测，在归档前跑一遍并落盘基线文件。
- [ ] 2.2 把 design.md D2 决策表（9 个具名读取方分类结论）连同基线文件提交 Shao Peishen 书面确认——**本步是后续归档迁移的前置门禁，未确认不得执行 2.3**。
- [ ] 2.3 实现归档迁移脚本：判据＝终态标记（`📥 已回件并回灌`／`❌ 已作废`）且状态写入距今 >30 天，整行原文原样迁 `README-归档-YYYYMM.md`（表头同），编号不复用。
- [ ] 2.4 登记 CLI `set-status` 的编号查找补齐「主表未命中再查归档件」两段式查找（对应 D2 决策：唯一需要跨归档查找的地方）。
- [ ] 2.5 `工具-跟进信README查询.py` 新增显式 `--file <归档件>` 用法（同队列查询工具先例），供人工核对历史；默认行为不变。
- [ ] 2.6 单测：归档判据（满足/不满足 30 天、非终态不迁移）、内容原文原样、编号不复用、活行读取方归档后行为不变（含「该收信人主表无任何行视为无在途」边界）、`set-status` 两段式查找命中归档件——覆盖 `followup-readme-archive` spec 全部 Scenario。
- [ ] 2.7 用 2.1 的基线逐一 diff 归档后各读取方的实际输出，零差异方可判定本组完成。

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
