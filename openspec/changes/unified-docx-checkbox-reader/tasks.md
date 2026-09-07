# unified-docx-checkbox-reader Tasks

> ✅ **design 审已过（Shao Peishen 2026-09-07，合审 §3 ＝ 五点全部按起草方推荐）**，apply 已执行。
> propose 期 ＝ `OP-0907-H`【CC】；**apply 期 ＝ `OP-0907-AB`【CC】，2026-09-07，批 `B-0907_Y`**，
> 同一分支 `claude/op0907h-docx-reader-481`（rebase 到 master `3ff92a6` 后续建，未新建分支）。
> 来源：队列 §一 `#481`（派生自 §四 `#133` ⑴）；激活依据 ＝ Cowork 业务总线 `B-0907_E`。
> 执行环境：**CC**（写生产码、跑测试、自行 commit+push，一任务一 worktree）。
> 🔴 §1 是 propose 期数字，**apply 期已按 3.1／4.5 独立重跑，未引用**。

## 0. 前置闸（design 审后、动手前）

- [x] 0.1 design 审五个决策点全部拍板 —— 结论 ＝ **①(a) ②(b) ③(c)含(b) ④(b) ⑤(a)**（他答
  合审材料 §3 (a)＝全部按起草方推荐，**含决策点② 那个「本项无默认」的点**）。已回填
  `design.md` 文首（**正文一字未改**，拍板结论只落在文首审过行与本文件勾选状态）；
  队列 §一 `#481` 行的回写留给看护者，见 §5.1
- [x] 0.2 触碰区核对 —— 手段：`git for-each-ref --format='%(refname:short)' refs/heads/` 遍历
  **全部 152 条本地分支**，对每条跑 `git log --oneline master..<branch> -- <触碰区七项>`
  （`master..` 只算**领先** master 的提交，落后分支不会误报）。**结果：仅 3 条命中，
  且全部落在 `shared_tools/` 下的另外两个文件、与本包实改文件零交集**：
  `claude/a22-closure-form-apply`→`followup_gate.py`；`claude/op0905n-editrow-guard-455`
  与 `claude/queue-315-apply-9f2c1a`→`queue_table.py`。**本包在 `shared_tools/` 下只新增
  `doc_parser/` 子包并改 `__init__.py` 一处 docstring ⇒ 无同碰。**
- [x] 0.3 `pip show zhuopin_platform` 实测 `Editable project location` ＝
  `C:\Dev\zhuopin-ai\5-平台底座\zhuopin_platform`（**主 checkout，正是 `#98` 的静默漂移形态**）。
  **处置：不动那个全局指针**（改它会顶替其余 40 余个 worktree），改为确认本包所有入口都走
  `#345` 的 `ensure_paths` 引导。实测证据：`python -c` 复现 `tests/conftest.py` 的引导 stub，
  `zhuopin_platform.__file__` 解析到
  `…\.claude\worktrees\agent-a3c904bed098e1d35\5-平台底座\zhuopin_platform\…\__init__.py`
  ＝ **本 worktree**，非主 checkout。
  🔴 **本包因此新增三处引导**（原先它们不 import 平台包、现在要）：`QD-A/tests/conftest.py`
  （`strict=True`）、`QD-A/scripts/run_prefill.py`、`QD-A/scripts/run_calibration.py`；
  `0-学习与工具/md转Word工具/test_md2word.py` 同样补上。四处**一律用 `#345` 的唯一样板**
  （`工具-引导样板lint.py` 守的那一份），不手抄第 36 份
- [x] 0.4 `npx openspec validate unified-docx-checkbox-reader --strict` ⇒
  `Change 'unified-docx-checkbox-reader' is valid`（exit 0）

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

- [x] 2.1 落点 ＝ `5-平台底座/zhuopin_platform/zhuopin_platform/shared_tools/doc_parser/`
  （决策点①(a)）。四个模块：`_xml.py`（OOXML 直读原语 ＋ **两种文本视图**）／`checkbox.py`
  （勾选三态入口，**判据正本**）／`signals.py`（四类回件形态信号，判据自 `#446` 迁入）／
  `text.py`（取文）＋ `__init__.py` 公开面。**零新增第三方依赖**（纯 stdlib；
  `zhuopin_platform/pyproject.toml` 一行未改，`[tool.setuptools.packages.find]` 的
  `zhuopin_platform*` 自动收录新子包）
- [x] 2.2 三态 ＝ `ReadingStatus.READ_FAILED` / `NO_CARRIER` / `HAS_CARRIERS`，各自是
  `CheckboxReading` 上互不相等的取值。🔴 **从类型上堵死的做法 ＝ `__bool__` 直接抛
  `TypeError`** —— `if not reading:` 这行代码在本件上**写不出来**，不依赖任何人记得判据
  （单测 `test_falsy_判断根本写不出来` 钉死）。读取失败另有 `failure_reason`（点名原因与
  文件路径）与 `raise_for_failure()`
- [x] 2.3 五个探测器判据逐条迁入、**语义未改**：控件（`w14:checked/@w14:val=="1"`）／裸字符
  （排除控件自身显示 `w:t`）／高亮（同段同色合并、`p.iter` 递归取 run）／批注
  （`commentRange*` 圈原文）／修订（`w:ins` 取 `w:t`、`w:del` 取 `w:delText`）。
  裸字符按决策点②(b) **给 `checked` 语义**（☑/☒＝True、☐＝False）、标 `source="char"`、
  **与控件分列不合并**（`control_carriers` / `char_carriers` 两列各自计数）。
  ⚠️ `signals.LooseCheckboxChar` 的既有字段与 `summary_line()` 措辞**一字未改**，新增的
  `checked` 是附加字段 ⇒ 拆件 CLI 输出不受影响（3.2 已 SHA256 证）
- [x] 2.4 🔴 **模拟高层视图已实测证伪，方可使用** —— 判据 ＝ `_xml.simulated_paragraph_text()`
  只拼 `w:p` 的**直接** `w:r` 子节点（再由 `simulated_cell_text()` 按 `_Cell.text` 规则以
  `\n` 拼接）。**对 `采购部` 08-26 回件与真 python-docx 逐格对照，三张表 116 格逐字相等**：
  `tables[0]` 真 16 格 0 空／模拟 16 格 0 空；**`tables[1]` 真 24 格 9 空／模拟 24 格 9 空**；
  `tables[2]` 真 76 格 0 空／模拟 76 格 0 空 —— 与 1.3 录得的真值一格不差。
  统一件对该件读数 ＝「控件 9 个（勾 3）」＋ 一条漏读诊断「高层文本视图只看得见 0 个载体、
  XML 里实有 9 个 —— 会漏 9 个」。
  🔴 **诊断按载体计、不按字符计**：载体是否可见由祖先链判定（`w:t`→`w:r`→`w:p` 两级都必须
  是直接父子，见 `_visible_in_text_view`），**否则一个 `w:t` 里有两个 ☑ 就会误报漏读**
- [x] 2.5 部件覆盖面已扩到 `word/header*.xml`／`footer*.xml`／`footnotes.xml`／`endnotes.xml`
  （`include_extra_parts=True` 为默认；`parts_scanned` 如实回报扫了哪些）。
  **今天读数零差异**（4.5：现网 69 份语料这些部件里勾选载体命中 0），单测另用手写页眉夹具
  钉住该路径确实生效
- [x] 2.6 模块文档已写明：已覆盖形态族／**未覆盖**（`w:fldChar`·`w:checkBox` 旧式表单域、
  非标准命名正文部件）／语料范围（`7-外部文档/` 69 份）与实测日期 2026-09-07／不做语义判断／
  OEM 隔离责任在调用方／不缓存被解析内容／**不保证「此后不会再误判对方是否作答」**
  （只保证凡经本件读取的，读不到会说读不到）

## 3. 迁移既有调用点（`#481` 期望产出 ③）

- [x] 3.1 **apply 期独立重跑**（`grep -rn --include=*.py`，未引用 1.6）：`read_checkboxes`
  在改动前的**生产调用点仍为 0**（定义 1 ＋ `test_md2word.py` 2 ＋ `reply_form_detection.py`
  注释 2）；`analyze_docx` 的消费者仍只有 `scripts/check_reply_form_signals.py` 与
  `tests/test_reply_form_detection.py`，后者用到的 `rfd.*` 面**只有三个**
  （`analyze_docx`／`list_part_names`／`FormSignals`）⇒ 薄壳委托足以保住契约
- [x] 3.2 `reply_form_detection.py` 已改薄壳委托（只剩 docstring ＋ re-export，零判据）。
  🔴 **CLI 输出逐字相同已用哈希证死**：对 `7-外部文档/` **68 份**合法 docx（排除下述那份非法
  zip）一次性跑 `check_reply_form_signals.py`，迁移前后落盘各 **129,694 字节**，
  **SHA256 同为 `F3FCE3AECE78D00A0471EF66431295A251A765341D3221F6D157EA074A60826F`**，exit 0。
  ⚠️ **如实登记一处刻意的行为变化（改善，非退步）**：第 69 份 `创建盘点差异单.docx`（非法
  zip）**迁移前会让整批崩掉** —— `zipfile.BadZipFile` 继承自 `Exception`、**不是**
  `ValueError`／`OSError`，CLI 那句 `except (ValueError, OSError)` 根本接不住，于是抛
  traceback、退出码 1、**其后按字典序排在它之后的文件一份都没被分析**。这与该 CLI docstring
  自己写的「退出码 2 ＝ 至少一个路径不是合法 docx，这类失败不得被静默吞掉」正相反。
  迁移后 `DocxReadError` **刻意继承 `ValueError`** ⇒ 同一份文件输出
  `[读取失败] 不是合法的 zip/docx 容器（File is not a zip file）：<全路径>`、退出码 **2**，
  与 docstring 一致。**CLI 源码一行未改。**
  ✅ 门禁复核：`wecom-aibot-service/pyproject.toml` **一行未改**，未引入
  `erp_connector`／`srm_connector` 可选依赖；`doc_parser` 是 `shared_tools` 下的纯解析件、
  不触达任何 ERP/SRM/CRM 系统，与该门禁要拦的东西不同类
- [x] 3.3 `qda_prefill/doc_reader._read_docx` 已改走 `doc_parser.extract_text_lines()`
  （覆盖表格格与 `w:sdtContent`）。**读不了刻意不接异常**，让 `DocxReadError` 抛到调用方
  ——把读取失败降级成"空文档"正是 `#133` ⑴ 的形状。
  🔴 **基准漂移逐条确认结果 ＝ 本场景无黄金基准可漂**：`data/golden/` 实测**只有一个
  `.gitkeep`、零基准文件**（真实 8D 样本按本场景红线① 不入库）；`tests/` 六个文件里没有任何
  黄金比对，`test_doc_reader.py::test_read_docx_extracts_sections` 用的是 `conftest.py` 现造的
  纯段落合成 docx（无表格、无控件）⇒ 新旧取法在该夹具上**逐字同结果**。
  **QD-A 全量：41 passed（与改动前同为 41 collected，零漂移）。**
  ⚠️ **连带改动、如实登记**：QD-A 原先**完全不依赖平台底座**，本次起要 import ⇒
  `pyproject.toml` 加 `zhuopin_platform` 依赖，并按 0.3 给 `tests/conftest.py` ＋
  `scripts/run_prefill.py` ＋ `scripts/run_calibration.py` 补 `#345` 引导样板
  （不补则 41 例里有 15 例 `ModuleNotFoundError`，本次已实撞过一次）
- [x] 3.4 `md2word.read_checkboxes()` **已删除**（决策点⑤(a)），原位留一段注明去处的注释。
  `test_md2word.py` 的 `TestTableCellCheckbox` 三个用例改调
  `doc_parser.read_checkboxes()` 验收 md2word **写出来的** docx，并**补强了一条**：
  `test_read_checkboxes_context_matches_row` 原先只断言"第 4 个被勾上"（没真的验行上下文），
  现改为断言 `row_context` 里同时含「料号B提前期3天」与「口径应按在途量计」——那才是
  `#446` point ⑶「9 格实际勾了 3 个被读成全空」要的答案。
  ✅ **`md2word.py` 本身保持零平台依赖**：它 `import` 的仍只有 stdlib ＋ `docx`，
  引导样板加在 `test_md2word.py` 里。**md2word 单测 16 passed。**
- [x] 3.5 全仓复查（`grep -rn "w14:checkbox\|w14:checked" --include=*.py`）：
  **生产码里的「读勾选」判据只剩 `doc_parser/checkbox.py` 一处。** 其余命中逐条判明：
  ⑴ `md2word.py` 4 处 ＝ **写侧** `OxmlElement('w14:checkbox')` 造控件，不是读判据；
  ⑵ `test_md2word.py` 10 处 ＝ 对 md2word **写出来的 XML** 做保真断言（字体/`2612`/`w14:val`），
  验的是"写对没写对"，与"对方勾没勾"不同族，**刻意保留**；
  ⑶ `test_reply_form_detection.py` / `test_doc_parser_checkbox.py` ＝ 手写 OOXML **夹具**；
  ⑷ FI2 三处 ＝ **注释与 docstring** 里的取证记录，零代码。
  `read_checkboxes` 的全仓引用现已全部指向平台底座那一个

## 4. 测试

测试文件两份，均落平台底座：`5-平台底座/zhuopin_platform/tests/test_doc_parser_checkbox.py`
（19 例）与 `test_doc_parser_text.py`（4 例）。
🔴 **真实回件一份都没进夹具**（全部落 gitignore 的 `7-外部文档/`）：真实 docx 夹具由
`md2word` 当场生成落 `tmp_path`，其余用手写最小 OOXML 片段。

- [x] 4.1 🔴 **反例单测（`#481` 期望产出 ②）** ＝ `TestPythonDocxEmptyStringPathIsNotZeroChecked`
  三例，夹具为 `md2word.build()` 当场生成的判例批改表 docx（沿用 `test_md2word.py::_build` 的
  做法，落 `tmp_path`）。
  ① `python-docx` 的 `cell.text` **确实**返回空串 —— 21 格里 **5 个空串**；
  🔑 **这份夹具还顺带钉住了 `#133` ⑴ 的要害**：那 5 格里 **4 格是勾选控件格**（格里明明有
  ☐/☑）、**1 格是第 1 行真的没填的「改判理由」格**，两类在 `cell.text` 上**逐字节相同**
  ⇒ 任何 `if not cell.text:` 都分不出"读不到"与"真的没填"；
  ② 统一件对同一文件判为「有 **4** 个载体、勾了 **1** 个」，`status is HAS_CARRIERS`，
  **不是** `NO_CARRIER`；
  ③ 漏读诊断作为**返回值的一部分**给出（`xml_view_count=4 / text_view_count=0 /
  missing_count=4`），不是日志里的一行 WARN
- [x] 4.2 🔴 **非恒真自证**：`monkeypatch` 把 `detect_control_carriers` 与 `detect_char_carriers`
  换成恒返回空的桩，**逐字复用 4.1 那两组断言函数**（`_assert_reads_four_carriers` /
  `_assert_emits_missing_four_diagnostic`）并断言它们 `raises(AssertionError)`。
  🔴 **刻意不另写一套"退化后应该长什么样"的期望** —— 那样这条自证只证明它自己
- [x] 4.3 三态区分 ＝ `TestThreeStatesAreDistinct` 六例：非法 zip／无载体普通 docx／两个未勾
  控件，三者 `status` 互不相同、对象互不相等；`bool(reading)` 与 `if not reading:` **均抛
  `TypeError`**；失败原因点名「不是合法的 zip」＋文件名；`raise_for_failure()` 只对失败态抛；
  人读摘要上「没有任何勾选载体」与「控件 2 个（勾 0）」也分得开；缺 `word/document.xml`
  同样判为读取失败
- [x] 4.4 **全量测试绿 ＋ 零回归**（本地实跑，不以 CI 为准 —— CI 整体 run 长期 failure，
  见 §一 `#398` ⑶）：
  | 套件 | 改动前基线 | 改动后 |
  |---|---|---|
  | `5-平台底座/zhuopin_platform` | **528 passed / 1 skipped**（`--ignore` 本包两份新测实测） | **551 passed / 1 skipped**（＝528 ＋ 新增 23） |
  | `5-平台底座/wecom-aibot-service` | 795 passed / 1 skipped | **795 passed / 1 skipped**（本包未加服务侧用例，数目应相等，实测相等） |
  | `4-数字员工/质量部/QD-A-8D不良分析` | 41 passed | **41 passed** |
  | `0-学习与工具/md转Word工具` | 16 passed | **16 passed** |
  `git status --porcelain` 实测：**12 M ＋ 3 ??**，三个 `??` 全是本包有意新增的
  （两份单测 ＋ `doc_parser/` 子包目录），**未出现任何新文件名形态**（无回归基线文件、
  无报告件、无临时产物）。`git check-ignore -v` 对新增源码与单测**无输出、退出码 1**
  ＝ 一条都没被忽略。
  ➕ `python 0-学习与工具/工具-引导样板lint.py`：本包新增的**四处引导样板零违规**；
  全仓仅剩 1 处**存量**违规（`tests/_coverage_point_ledger_helpers.py`，非本包触碰区）
- [x] 4.5 🔴 **现网语料回归重跑（apply 期实跑，未引用 1.2 的数字）** —— 手段：一次性只读脚本，
  对 `7-外部文档/` 递归全部 `*.docx`（排除 `~$`）跑统一件，再与**本脚本自带、不 import 统一件
  任何探测器**的独立 XML 直读逐份对账（否则"逐份一致"会退化成"它跟它自己一致"）。
  **结果：语料 69 份（比 propose 期多 1 份）；读取失败 1 份（`创建盘点差异单.docx`，非法 zip）；
  带勾选载体 19 份；统一件 vs 独立 XML 直读读数不一致 ＝ 0 份。**
  naive `python-docx` 视角的假阴性（它读到勾 0、XML 里确有勾）复算 ＝ **11 份**
  （propose 期 1.2 记 13 份 —— ⚠️ 两个数字口径不同：本次只数「naive 读到 **勾** 0 而 XML 有勾」，
  1.2 数的是「naive 视角勾选数为 0」，含未勾的 ☐ 也被漏读的那几份；**如实并记，不回改 1.2**）

## 5. 收口与登记

- [ ] 5.1 队列 §一 `#481` 行回填 —— 🔴 **本 apply 会话不写队列**：本件派单明写「不碰主仓工作区、
  不在主仓 commit」，而队列真身在主 checkout。回写文本已按既有暂存约定备好，**交看护者**：
  `1-转型规划/0-全景路线图/队列回写待补/B-0907_Y-481.json`（`{"append": {"状态": …}}`），
  内容与本文件 §0–§4 逐条对应
- [ ] 5.2 §四 `#133` 行内追加指针（⑴ 已由本包承接，**只追加、不改历史正文**）—— 同 5.1，
  一并放在那份暂存 JSON 里交看护者。🔴 **本会话未碰 §一 `#411`**（`#133` ⑶ 已定：那条错误
  结论在行内标注更正、不销号重开）；**亦未回改 `#133` 正文**（1.3 的更准措辞、4.5 与 1.2 的
  口径差，都只记在本包内）
- [x] 5.3 `5-平台底座/CLAUDE.md` §4 现状表的 `shared_tools/` 一行已更新（「doc_parser 待质量
  旗舰落地」→「已落地（2026-09-07，队列 `#481`）＝ 全项目 docx 勾选/取文判据正本，纯 stdlib、
  零新增依赖」）；`shared_tools/__init__.py` 的模块 docstring 同步从「待建」移到「已收割」，
  并**如实标注未覆盖 SC4 合同 PDF 取文与 `ContractDocument` 装配**（那是另一份工作，
  本件落地不等于「平台 doc_parser 全量交付」）
- [ ] 5.4 `/opsx:archive unified-docx-checkbox-reader -y` —— **待 5.1／5.2 队列回写落地后由看护者
  执行**。本包不自行归档：`暂不归档`（理由 ＝ 队列回写与 ff 合入 master 均属 🟡，须看护者/总线
  处置；本会话按派单件停手不越线）
