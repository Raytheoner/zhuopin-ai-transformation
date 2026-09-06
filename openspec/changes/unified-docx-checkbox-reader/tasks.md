# unified-docx-checkbox-reader Tasks

> 🛑 **design 审未过，§2 起一律不得动手。** 本次（`OP-0907-H`【CC】，分支
> `claude/op0907h-docx-reader-481`，从 master 起）范围止于 **propose ＋ design 起草**：
> 只有 §1 取证是本次实跑并勾掉的，§0 与 §2–§5 是 **apply 期**清单。
> 来源：队列 §一 `#481`（派生自 §四 `#133` ⑴）；激活依据 ＝ Cowork 业务总线 `B-0907_E`。
> 执行环境：**CC**（写生产码、跑测试、自行 commit+push，一任务一 worktree）。

## 0. 前置闸（design 审后、动手前）

- [ ] 0.1 design 审五个决策点全部拍板，结论回填 `design.md` 文首结论表与队列 §一 `#481` 行
- [ ] 0.2 触碰区核对 —— 手段：`git for-each-ref refs/heads/` 遍历全部本地分支，对每个跑
  `git log master..<branch> -- <本包触碰的每个文件>`，逐个判断是"领先 master"还是"落后
  master"（**只看有没有提交不够，落后分支会误报为同碰**）。触碰区 ＝ `md2word.py`／
  `test_md2word.py`／`reply_form_detection.py`／`check_reply_form_signals.py`／
  `test_reply_form_detection.py`／`qda_prefill/doc_reader.py`／`zhuopin_platform/shared_tools/`
- [ ] 0.3 `pip show zhuopin_platform` 核 `Editable project location` 指向何处；若指向主
  checkout 而非本 worktree（`#98` 的静默漂移形态），**因本包要改 `shared_tools/`，MUST 先处理**
  ——不得沿用 `editlock-credential-shape-guard` 那种"本包不改 platform 故可放行"的结论
- [ ] 0.4 `openspec validate unified-docx-checkbox-reader --strict` 通过

## 1. 取证与口径（🔴 propose 期已实跑，本节数字可现取重跑核对）

- [x] 1.1 三份既有实现定位与覆盖面白盒读完 —— `md2word.py:85 read_checkboxes()`（`python-docx`，
  只遍历 `doc.element.body` 的 `w:sdt`）／`reply_form_detection.py`（纯 stdlib `zipfile`+
  `ElementTree`，五类信号，只读 `word/document.xml`）／`qda_prefill/doc_reader.py:93 _read_docx()`
  （`python-docx` 的 `doc.paragraphs`，**不取表格、不取 `w:sdtContent`**）。
  🔴 **排除项已实测**：`qd_b_gate/parser.py` 是 **xlsx/openpyxl** 解析（`self.ws.cell(...)`／
  `self.wb.sheetnames`），与 docx 无关，**不在触碰区**；`sc4_contract/text_source.py` **刻意拒收**
  `.docx`（`PlainTextSource.SUPPORTED = (".txt", ".md")`），无 docx 读取实现
- [x] 1.2 🔴 **现网全量语料只读对照（68 份 docx）** —— 手段：一次性只读脚本，对
  `7-外部文档/` 递归全部 `*.docx`（排除 `~$` 临时件）各跑两遍：① naive `python-docx` 文本视角
  （`doc.paragraphs` ＋ 逐 `cell.text` 拼接后数 ☐☑☒）；② XML 直读视角（`w14:checkbox` 控件
  ＋ 控件外裸字符）。**结果：共 68 份；19 份携带勾选形态；其中 13 份在 naive 视角下勾选数为 0
  而 XML 里确有勾 ⇒ 假阴性；另 1 份（`用友OpenAPI完整文档/创建盘点差异单.docx`）`BadZipFile`
  ＝ 根本不是合法 zip。** ⇒ 「读不了」这条路径在现网**真实存在**，非构造假设
- [x] 1.3 🔴 **逐字复现 `#133` 事实链 ⑴ 的 `tables[1]` 全空串** —— 手段：对
  `采购部-YaoZuYi-回复-2026-08-26-…-272f6c88….docx`（即 `采购部#18` 回件）跑
  `python-docx` 逐表逐格 `cell.text` ＋ 同文件 `w:tbl` 逐个 XML 直读。
  **结果：`tables[0]` 16 格 0 空；`tables[1]` 24 格 9 空（38%）；`tables[2]` 76 格 0 空。
  XML：`w:tbl[1]` 内有 9 个 `w14:checkbox`，勾 3（☒3/☐6），其余两表 0 个。**
  ⇒ **那 9 个空串格正是那 9 个复选框格，一格不多一格不少。**
  ⚠️ **如实记一处更准的措辞**：`#133` 原文写「逐格 `cell.text` 全为空串」，实测是**勾选列**
  全空、其余 15 格有字。**只记在本包内，不回改 `#133` 原文**（历史记录不追改）
- [x] 1.4 🔴 **裸勾选字符的逐段上下文核对（决策点② 的事实依据）** —— 手段：只读脚本对裸字符
  所在 `w:p` 打印全段文字。**结果：`质量部#11`（陈忱 09-01）22 个裸 ☑ 零控件，每个 ☑ 后紧跟
  真实作答文字（「☑ 认可」「☑ (b) 改为两档。」「☑ 按 V3.2（扣分＋红线）」「☑ 以上十三条我方
  建议我都认可，按此改。」等）；`质量部#12`（09-02）7 个裸 ☑ 同形态；`采购部` 07-28 回件 8 个
  裸 ☐ 则各自独占一段、段内仅此一字符 ＝ 未填的作答格。** ⇒ 现网三例**全部支持给语义**，
  **图例/装饰形态一例都没找到**（该反例目前是理论风险，如实标注）
- [x] 1.5 三份实现在同两份真实回件上的读数对照 —— 手段：`importlib` 分别加载三个模块，对同一
  文件各跑一次。**结果（`采购部` 08-26 回件）**：`md2word.read_checkboxes` ＝ 9 个控件勾 3 ✅；
  `reply_form_detection` ＝ `w14:checkbox ☒3/☐6；高亮段×3` ✅；`qda_prefill.read` ＝ 全文
  **3872** 字、☒0 ☑0 ☐0（XML 真相 **5216** 字、☒3 ☐6）⇒ **丢 1344 字＝26%，且勾选计数归零**。
  **结果（`质量部#11`）**：`md2word.read_checkboxes` ＝ **0 个控件、勾 0** ❌（专员实际勾了 22 处）；
  `reply_form_detection` ＝ `裸勾选字符×22（控件外，需人工确认）` ⚠️；`qda_prefill.read` ＝ 全文
  **543** 字、☑3（XML 真相 **1897** 字、☑22）⇒ **丢 1354 字＝71%**
- [x] 1.6 **下游消费者核实（propose 期）** —— 手段：全仓 `grep --include=*.py`。
  `read_checkboxes` 共 4 处引用：定义 1、`test_md2word.py` 2（`TestTableCellCheckbox` 用它做
  **md2word 写侧的验收手段**）、`reply_form_detection.py` 注释 2。**生产调用点 0。**
  `analyze_docx` 消费者 ＝ `scripts/check_reply_form_signals.py` ＋ `tests/test_reply_form_detection.py`，
  CLI 只读 `summary_line()` 与各 list 字段、不解析返回类型内部结构。
  ⚠️ **apply 期须独立重跑，不得引用本条数字**（见 3.1）
- [x] 1.7 落点可行性实测（决策点① 的三条支撑）—— 手段：读两个 `pyproject.toml`。
  `zhuopin_platform` 依赖 ＝ `openai`／`python-dotenv`／`requests`／`chromadb`／`pydantic`，
  **无 python-docx**；`#446` 实现为**纯 stdlib**（`zipfile`＋`ElementTree`）⇒ 落进底座
  **零新增第三方依赖**。`wecom-aibot-service` 的 `dependencies` 首条即 `"zhuopin_platform[aibot]"`
  ⇒ 它**本来就依赖底座**，改为从底座 import 零依赖成本。`5-平台底座/CLAUDE.md` §4 现状表原文
  「`shared_tools/` …… doc_parser 待质量旗舰落地」⇒ **位子是留好的，非本包新划**

## 2. 实现（🔴 design 审通过后才动手）

- [ ] 2.1 按决策点① 的落点新建统一件模块与其包结构
- [ ] 2.2 按决策点③ 定义三态返回类型（读取失败／无载体／有 N 个载体勾 M 个），并**从类型上**
  堵死 `if not result:` 读成"没勾"这条路
- [ ] 2.3 迁入 `#446` 五个探测器（控件／裸字符／高亮／批注／修订）的判据，**逐条比对不改语义**；
  裸字符的 `checked` 语义按决策点② 拍板处置
- [ ] 2.4 🔴 按决策点③ 实现「高层文本视图」交叉校验诊断。**若采用"用同一份 XML 模拟高层视图"
  的折中方案，MUST 先实测证伪**：对 `采购部` 08-26 回件断言模拟视图得出的空串格数与真
  `python-docx` **逐格一致**（1.3 已录得真值 ＝ `tables[1]` 24 格 9 空）。不实测不许用
- [ ] 2.5 按决策点④ 扩展部件覆盖面（`header*`／`footer*`／`footnotes`／`endnotes`）
- [ ] 2.6 模块文档写明：已覆盖形态族、**未覆盖**形态族（`w:fldChar`/`w:checkBox` 旧式表单域）、
  语料范围与实测日期、不做语义判断、OEM 隔离责任在调用方、不缓存被解析内容

## 3. 迁移既有调用点（`#481` 期望产出 ③）

- [ ] 3.1 🔴 **重跑 1.6 的下游消费者核实**，不得引用 propose 期结论
- [ ] 3.2 `reply_form_detection.py` 改委托；**实测 `check_reply_form_signals.py` 对同一份回件
  迁移前后输出逐字相同**（手段：迁移前先存一份输出，迁移后 `diff`）。同时复核未把
  `erp_connector`／`srm_connector` 可选依赖带进 aibot 的门禁清单
- [ ] 3.3 `qda_prefill/doc_reader._read_docx` 改走统一件取文；跑 QD-A 全量测试。
  🔴 **基准漂移必须逐条人工确认**——该模块今天丢 26%–71% 正文，补全后 D1–D8 分段输入必然变化，
  **不得以新结果直接覆盖旧基准**
- [ ] 3.4 `md2word.read_checkboxes` 按决策点⑤ 处置；若选 (a) 删除，则 `test_md2word.py` 的
  `TestTableCellCheckbox` 三个用例改调统一件做写侧验收（**注意：是测试 import 平台包，
  `md2word.py` 本身保持零平台依赖**）
- [ ] 3.5 全仓复查确无第三份 docx 勾选判据残留（手段：`grep -rn "w14:checkbox\|w14:checked"`
  `--include=*.py`，逐个确认只剩统一件与其单测）

## 4. 测试

- [ ] 4.1 🔴 **反例单测（`#481` 期望产出 ②）**：以 `md2word` 当场生成的真实含控件 docx 为夹具
  （沿用 `test_md2word.py::_build`，落 `tmp_path`、不落仓库），断言 ① `python-docx` 的
  `cell.text` 路径**确实**返回空串；② 统一件对同一文件判为「有 N 个载体、勾了 M 个」，
  **不得**判为零勾
- [ ] 4.2 🔴 **非恒真自证**：把统一件的载体探测器换成恒返回空的桩，4.1 的断言必须失败
- [ ] 4.3 三态区分单测：读取失败（非法 zip）／无载体／有载体零勾，三者返回值互不相等，
  且任一 falsy 判断都无法把它们混同
- [ ] 4.4 全量测试绿 ＋ 零回归；跑完用 `git status --porcelain` 实测确认工作区**未出现任何
  新文件名形态**（proposal §伴生文件段的核实手段）。若决策点④ 落地时产生了现网语料回归基线
  文件，须当场跑 `git check-ignore -v` 并把**实际输出**记进本行
- [ ] 4.5 🔴 **现网 68 份语料回归重跑**（apply 期，不引用 1.2 的数字）：统一件读数与 XML 直读
  逐份一致，差异份数写进本行

## 5. 收口与登记

- [ ] 5.1 队列 §一 `#481` 行回填 design 审结论与产出路径
- [ ] 5.2 §四 `#133` 行内追加一句指针，说明 ⑴ 已由本包承接（**只追加、不改历史正文**）；
  🔴 **不碰 §一 `#411`**——`#133` ⑶ 已定：那条错误结论**在行内标注更正、不销号重开**
- [ ] 5.3 `5-平台底座/CLAUDE.md` §4 现状表的 `shared_tools/` 一行更新（「doc_parser 待质量旗舰
  落地」→ 实际状态）
- [ ] 5.4 tasks 全 [x] 后当场 `/opsx:archive unified-docx-checkbox-reader -y`（完工即归档）
