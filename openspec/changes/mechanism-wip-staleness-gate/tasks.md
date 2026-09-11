# mechanism-wip-staleness-gate Tasks

> 🔴 **1.x 全部完成、且 Shao Peishen 已批准 design.md 六个决策点（D-A～D-F）之后，才可开工 2.x 起的实现项。** 派单指令（`OP-0911-D`）：本棒只做 propose＋design，不 apply、不改 `工具-共享文档编辑锁.py` 任何一行；apply 另派。
> 🔴 **apply 棒开工第一件事＝重跑 1.1 的探针（现取表过期守，同 `#522`）**，与本文 1.1 记录的分布对照，计入行偏差 >3 条即停手回报，不得拿过期基数写进实现。

## 1. Propose ＋ Design（本棒已完成，2026-09-11）

- [x] 1.1 前置实测复跑：`git blame --incremental` 取 23 条计入行末次 `author-time`，计入集直接调 `_count_mechanism_wip`（不复制判据）。结果：计入 23／22（行号集合与方案件 §D2 完全一致）、🛑 认两列后 20、最老 6.96 天（`#240` `#312` `#381` `#382`）、`STALE(7)=0`／`STALE(5)=4`／`STALE(3)=7`／`STALE(2)=9`，与方案件零偏差 ⇒ N＝7／K＝3 沿用。附带实测：blame 主 checkout 耗时 6.9–8.0 s（文件 644 KB、941 commit 触碰）。探针脚本只读、未落盘、未 acquire（脚本位于本棒 scratchpad，手段已全文写进 proposal「前置实测复跑」表，可按表复算）
- [x] 1.2 proposal.md（含「退休哪个守卫」／`.gitignore` 覆盖／知识资产三问／验收与晋档条件四个强制节；晋档条件 2 为切阻断硬前置）
- [x] 1.3 design.md 六个决策点（D-A 取龄定义与乐观偏差、D-B 🛑 两列 (甲)＋写侧告警、D-C `#58` ⑸ 修法⑴、D-D 迁移期与退休判据、D-E 取龄失败非静默、D-F 模式切换载体），均带推荐与默认项
- [x] 1.4 spec delta `editlock-mechanism-wip-guard`（MODIFIED「超限时拒绝 release」／REMOVED「上限值可配置」／ADDED 五条）
- [x] 1.5 `openspec validate mechanism-wip-staleness-gate --strict` 通过（回显见本棒收工汇总）
- [ ] 1.6 **Shao Peishen 审 design.md 六个决策点**（🟡，泳道无权自行通过）——答复模板见本棒收工汇总；批准后本行改 [x] 并记日期与答复字母

## 2. 单测先写（apply 棒；红→绿，实现前先写红）

> 用例落 `0-学习与工具/test_工具-共享文档编辑锁.py`，沿用既有 `cmd_release` 端到端范式（`#58` 包 2.4 的教训：不要按实现符号 grep 判覆盖）。取龄的 git 依赖用 monkeypatch 注入假 blame 输出，**不在单测里真跑 git**（8 s × N 条用例不可接受）。

- [ ] 2.1 `STALE` 计数三态：⑴ 全部行有 blame 记录 ⇒ 按 `author-time` 计龄；⑵ 某行无 blame 记录（全零哈希＝工作区未提交）⇒ 按今天计、不计陈旧；⑶ 行号漂移（编号在文件里映射不到 `|<编号>|` 起首行）⇒ 该行不参与计数、降级告警点名该编号、其余行照常判定（spec「取龄失败非静默降级」第三 Scenario）
- [ ] 2.2 🛑 两列写法各自被正确排除：⑴ 🛑 只在状态列 ⇒ 不计入（回归）；⑵ 🛑 只在任务列 ⇒ 不计入（**新**，用 `#381` 形态的真实行文本构造）；⑶ 两列都无 🛑 ⇒ 计入；⑷ 🛑 出现在任务列非起首位置 ⇒ 仍计入（防判据过宽）
- [ ] 2.3 写侧告警：`append-row` 写 `[D:机]` 行且 🛑 只落任务列 ⇒ 写入成功、stdout 含引导文案；🛑 落状态列 ⇒ 不响；`[D:业]` 行 ⇒ 不响；`edit-row` 改既有行但本次写入值不触发 ⇒ 不响
- [ ] 2.4 D-C：新增行不计入时不阻断：⑴ 新增 🛑 起首行＋存量超限 ⇒ 放行、回显注明「不计入、与超限无关」、不要求豁免；⑵ 新增 `[S:blocked]` 行 ⇒ 不触发；⑶ 一次新增计入行 `#A`＋不计入行 `#B`＋超限＋无逃生阀 ⇒ 拒绝且文案只点名 `#A`；逃生阀齐备时只要求 `#A` 有 `WIP豁免：`
- [ ] 2.5 告警模式（`MECHANISM_WIP_GATE_MODE="warn"`）：⑴ 行数 23／22、`STALE=0` ⇒ 按行数拒绝、文案同时回显 `STALE(7)=0／3`；⑵ 行数 20／22、`STALE=5／3` ⇒ 放行、回显两个数＋最老 4 条陈旧行（编号＋天数）＋「告警期，未阻断」字样
- [ ] 2.6 阻断模式（常量改 `"block"` 由 monkeypatch 注入）：⑴ 行数 25、`STALE=1／3` ⇒ 放行、不回显行数上限；⑵ `STALE=4／3`＋无逃生阀 ⇒ 拒绝、锁保持占用、文案含 `STALE`／K／N、新增行编号、最老 K＋1 条清单、两条出路；⑶ 逃生阀齐备 ⇒ 放行且理由留在队列文本里；⑷ 只给开关／只写标记 ⇒ 各自拒绝（`#58` 决策点 5 回归）
- [ ] 2.7 🔴 **存量超限时来关行的 session 照旧放行（`#58` 决策点 4 的关键回归，不许丢）**：⑴ `STALE=4／3`＋本次未新增任何 `[D:机]` §一 行（本次编辑正是把最老一行改 `[S:done]`）⇒ 不取龄、不判定、放行；⑵ 同上但本次编辑是推进最老一行（改状态格正文）⇒ 放行；⑶ 本次只新增 `[D:业]` 行 ⇒ 不取龄、放行。三条在告警／阻断两种模式下各跑一遍
- [ ] 2.8 取龄失败非静默：⑴ 子进程启动失败（`FileNotFoundError`）⇒ 放行＋降级告警含原因；⑵ 超时（注入 `TimeoutExpired`）⇒ 子进程被终止、放行＋告警含耗时与超时值；⑶ 输出不可解析 ⇒ 放行＋告警；三者 stdout 均含「本次未判陈旧」且 **不含**「STALE=0」（防把降级伪装成合规）
- [ ] 2.9 行内日期不作数：状态格内写着「截止 2026-12-31」但 blame 显示 30 天前 ⇒ 计陈旧（spec 第五 Scenario）
- [ ] 2.10 `--stale-days`／`--stale-cap`／`--stale-probe-timeout` 三个参数生效；`--mechanism-wip-cap` 告警模式下仍生效（阻断模式下的「未知参数」用例留到 apply 批 2）

## 3. 实现（apply 批 1，告警模式）

- [ ] 3.1 先 grep `_count_mechanism_wip` 全部调用方（`_validate_release_structure`／`cmd_status`／`cmd_triage_candidates`／`_collect_triage_candidates`／单测），返回值增第三项「计入行号清单」时逐一核对解包处；签名兼容（既有两项不变）
- [ ] 3.2 `_count_mechanism_wip`：🛑 排除加任务列 `cells[1]` 判（D-B 甲），docstring 记 `#381`／`#382`／`#448` 三行实测与 23→20
- [ ] 3.3 新增 `_mechanism_wip_stale_rows(section_one_text, counted_numbers, *, days, timeout, repo_root, queue_path) -> tuple[list[tuple[str, float]], list[str]]`：`git blame --incremental -- <queue_path>` 子进程（`subprocess.run`，`timeout=`，`encoding="utf-8", errors="replace"`），解析 `<sha> <src> <start> <n>` 头与 `author-time`，全零哈希按今天计；按行首 `|<编号>|` 映射；返回（陈旧行 [编号, 天数] 按天数降序，降级日志）。**只读，不写任何文件**（D-E 丁已否）
- [ ] 3.4 `_validate_release_structure` ⑨ 段：`new_mechanism_rows` 收窄为「本次新增且计入」（D-C）；空 ⇒ 只回显；非空 ⇒ 告警模式按行数判＋回显 `STALE`；`MECHANISM_WIP_GATE_MODE = "warn"` 模块常量（D-F）＋ `MECHANISM_WIP_STALE_DAYS_DEFAULT = 7`／`MECHANISM_WIP_STALE_CAP_DEFAULT = 3`／`MECHANISM_WIP_STALE_PROBE_TIMEOUT_DEFAULT = 30`
- [ ] 3.5 `_mechanism_wip_over_cap_violations` 文案改写：陈旧行清单（最老 K＋1 条，编号＋天数）放在行数之前；告警期明写「7 天后此项将阻断」；出路①改为「推进或关闭上列最老行」
- [ ] 3.6 写侧告警：`cmd_append_row`／`cmd_edit_row` 对 `[D:机]` 可动行、🛑 只落任务列时打印引导文案（非阻断，D-B）
- [ ] 3.7 `cmd_release` 参数：新增 `--stale-days`／`--stale-cap`／`--stale-probe-timeout`；`--mechanism-wip-cap` help 追加「迁移期保留，切阻断时删除」
- [ ] 3.8 模块头部说明段新增「措施 C 换量具（`#58`＋`OP-0911-D`）」小节；⑨ 段 docstring 改写（含 D-A 乐观偏差红字、D-E fail-open 出声的理由）
- [ ] 3.9 全量回归零回归判据（rules/两桌同步与取证 §二）：同一组失败用例在纯 master 同命令复跑逐条复现才算零回归；`openspec validate --all --strict`；`工具-队列结构lint.py` 对两份真身通过；`git status --porcelain` 无新形态未跟踪文件（兑现 proposal `.gitignore` 问答）

## 4. 告警期（7 天，值周巡检承接）

- [ ] 4.1 协议〇.9 措施 C 正文追加「2026-09 陈旧度闸告警期」段（走锁）；`#58` 回填一段指向本包；`#454` 追一行「D-B 已修 🛑 两列」
- [ ] 4.2 值周巡检对行龄榜首 3 条人工抽查一次，逐条记「末次改动是实质推进／机械触碰」（D-A 缓解；D-D 前置②）
- [ ] 4.3 🔴 至少一次取龄在**非主 checkout 环境**（沙箱挂载盘或 worktree）真实跑过并记录耗时（D-D 前置③）；若 >30 s ⇒ 回 design D-E 议默认超时或缓存，不得静默调大
- [ ] 4.4 记录告警期内 `release` 回显次数、`WIP豁免：` 新增条数、`STALE` 每次取值（三个数进 `#58` 行日志）

## 5. 复评与 apply 批 2（阻断模式）——🟡 Shao Peishen 一字母

- [ ] 5.1 复评先答 D-D 三条前置：①「这 7 天里新闸的告警有没有被任何人当回事」②榜首 3 条抽查已做 ③非主 checkout 耗时已记；**任一为否 ⇒ 不切、不默认续期、回 design 重议**
- [ ] 5.2 `MECHANISM_WIP_GATE_MODE = "block"`；删 `--mechanism-wip-cap`／`MECHANISM_WIP_CAP_DEFAULT`（一进一出）；补 2.10 留下的「未知参数」用例
- [ ] 5.3 改写协议〇.9 措施 C 正文（行数上限沿革 8→16→24→22 迁入 `#58` 行日志留痕）、`专线opener模板库.md` §〇.9 ⑵、docstring
- [ ] 5.4 切阻断后真实发生一次 `STALE > K` 拒绝并核文案可行动（晋档条件 3）；未自然发生则回 `#58` 讨论是否人为构造，不直接归档
- [ ] 5.5 `/opsx:archive mechanism-wip-staleness-gate -y`（全部勾完才做；5.4 未满足时按「完工即归档」纪律写 `预期观察窗口：N 天` 而不是沉默）
