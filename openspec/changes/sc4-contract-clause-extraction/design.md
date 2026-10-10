---
status: 原变更包正式 design 供审稿；design 未获批准，未授权实现
date: 2026-10-10
scenario: SC4 合同条款自动提取与审核
scope: 单供应商/单合同合成材料的六项条款证据对照设计；不作真实法律判断
---

# SC4 技术 design

## 0. 决策状态与依据

Shao Peishen 已明确确认 SC4 完整意图与首项范围：单供应商/单合同、带版本的合成文本与合成 DOCX，按六项用例核对条款证据；先暴露定位、取文、结构、版本与审计缺口，不作法律判断。该答复确认业务意图和首项，不等同于本 design 已批准，也不授权实现、测试、接真实合同/SRM、修改法务前置或发布。

本稿已补入 `openspec/changes/sc4-contract-clause-extraction/design.md` 供审，复用原proposal/tasks/spec与现有骨架。原tasks第2组前置仍未闭；本次只补design，不修改规范、任务依赖/勾选或产品。完整intent批准原答见《五项定夺答复消费-2026-10-10.md/.json》。

本稿依据已读的 SC4 intent、场景 `CLAUDE.md`、根场景建造规则、`4-数字员工/CLAUDE.md`、`5-平台底座/CLAUDE.md`、原 package proposal/tasks/change spec/main spec、SC4 核验报告与六项 mock 对照目录，以及本轮定点读取的 SC4 代码和 `doc_parser` 门面。SC4 intent 与 M2 明确记录：未跑本轮测试，历史 19 tests/59 断言不作为现时通过证据。

规则加载限制：尝试读取 `4-数字员工/采购部/CLAUDE.md` 时被 K3 拦截；随后 Root 以普通 `Get-Item` 确认该文件不存在（exit 1）。未通过其他方式读取。当前适用规则由已读取的根 `.claude/rules/场景建造与合规.md`、根 `CLAUDE.md`、`4-数字员工/CLAUDE.md` 和 SC4 场景自身 `CLAUDE.md` 覆盖，不把缺失的部门文件当作待业务补齐事项。

## 1. 目标、非目标与成功条件

### 1.1 目标

对一份合成供应商采购合同，能够从 `.txt`/`.md` 或 `.docx` 得到可复核的抽取文本；使用显式传入、明确标为 mock 的定位词表，按既有编号标题规则切分与分类；每项结果能回指到**本次输入所用的明确文本视图**；审计记录足以区分输入文件、取文器/文本视图和词表版本；结构或取文证据不足时明确报告不足，不将“未抽出”转换为“法律上缺失”或“无风险”。

### 1.2 非目标

- 不实现或模拟标准条款比对、语义等价、偏差认定、风险级别、缺失条款清单、审核摘要或自动处置；`review.py` 三个函数继续 fail-loud。
- 不引入真实合同、供应商商业秘密、OEM 附件、真实 SRM 文档或线上连接。
- 不构建 PDF、旧 `.doc`、扫描件、OCR 或第二套 DOCX 解析器；不改平台 `doc_parser`。
- 不提供自然语言检索、服务端点、门户/UI、部署、FI2/FI3 财务衔接或发布能力。
- 不把五项专业待办、法务负责人或 backup 的未知实名转成技术片的前置。姓名未知时保持空白；技术片只需要明确标识的合成执行者/测试 actor，不伪造业务负责人或审批人。

### 1.3 完成判据

1. 六个合成证据用例逐格核对输入 ID/版本/源 hash、提取状态、文本视图、原文区间、显示文本、mock 定位类别/未归类理由、词表 ID、审计版本证据。
2. 同一输入定义下，`text[start:end]` 与保存的原文片段严格相等；任何 trim/显示格式只发生在单独的 display view。
3. 一份合成 DOCX 经共享 `doc_parser` 后的位置坐标清楚说明是“解析后规范文本坐标”，不伪称 OOXML 字节、Word 页码或物理段落坐标。
4. 空文本、无标题、解析失败、多类词表命中分别保留不同状态/错误，不产生法律缺失/风险结论。
5. `run_extraction` 路径必写 audit；audit 写失败时不得返回一个看似成功的抽取结果。
6. 所有证据均使用合成通用采购合同，测试和输出无真实专业判据、姓名或合同正文。

## 2. 设计决策及备选

### 决策 A：拆出不依赖法务知识资产的合成证据窄片

**推荐：** 在完整产品架构中区分 A 阶段“合成取文/证据与留痕”和 B 阶段“法务标准比对/判据判断”。A 阶段须经本 design 审与 tasks 明确拆分后才能实现；B 阶段仍由既有知识前置和专业签认硬闸控制。

| 方案 | 做法 | 代价/风险 | 结论 |
|---|---|---|---|
| A. 保持整个第 2 组全完成后才允许任何后续工作 | 标准库与风险判据先到位，之后才做 DOCX/来源证据片 | 法务前置与纯取文/追溯能力无接口依赖；会把已确认的窄片与专业闸不必要地绑在一起 | 可行但不推荐 |
| **B. 仅拆分合成证据窄片** | design 通过后，只做合成 `.txt/.md`/`.docx`、定位和审计追溯；真实源和判断能力仍等各自闸 | 需要原 tasks 明确改写阶段边界，防止把“可做”误读成已授权或前置失效 | **推荐** |
| C. 全链路用 mock 标准/风险判据先行 | 给 mock 风险级、缺失清单或伪标准并跑 end-to-end | 会把虚构专业值固化进测试/演示，违反现有 `pending.require`、proposal 与 spec 边界 | 拒绝 |

### 决策 B：复用现有共享 DOCX 文本门面，限制输入形态

M2 与源码定点核验显示，平台 `zhuopin_platform.shared_tools.doc_parser` 已导出 `extract_text`/`extract_text_lines`，以 ZIP/XML 读取 OOXML `.docx`，覆盖段落、表格与块级内容控件；`extract_text` 按文档顺序以换行连接非空行，表格行以 ` | ` 合并。解析错误通过 `DocxReadError` fail-loud。它不提供 PDF、旧 `.doc`、OCR，也不输出 SC4 需要的合同版本、源 hash、lexicon 或条款语义判断。

**推荐：** 新增独立 `DocxTextSource` 实现既有 `TextSource` protocol，调用该公开门面；不让 `PlainTextSource` 兼收 DOCX，保持现有纯文本实现及其拒绝二进制格式的行为。调用 `extract_text(path, include_extra_parts=False)`，将主体文档规范文本作为本场景唯一 offset 视图；不读取页眉/页脚等 extra parts。本决策不代表 SC4 已实现或接通 DOCX。

**备选：** 先只验证解析器输出而不接 SC4 source adapter，降低代码改动但不能核对 SC4 的 hash、offset、audit 端到端契约。故建议 adapter 作为 Stage A 的一项实现工作；仍须 design 审和后续任务授权。

### 决策 C：原文区间保存精确切片，展示文本独立规范化

当前 `ClauseSpan` 记录 `start/end`，`segment()` 用原区间生成 `text[start:end].strip()`；已有测试只断言 `source[start:end].strip() == span.text`。该契约不满足“区间严格回指片段”的要求。

**推荐：** `start`/`end` 均为 0 基、左闭右开、Python Unicode code point 索引，坐标基准写明为本次 `ContractDocument.text`。令 `ClauseSpan.text == ContractDocument.text[start:end]`，原始切片保留首尾空格/换行；展示/导出使用单独的 `display_text = text.strip()`（或在 presenter 临时计算），不得覆盖原文片段。`heading` 仍可用 trim 后标题用于定位类别。

- `.txt/.md` 的坐标基于 UTF-8 解码所得完整源文本，不先 `strip()`/换行标准化。
- `.docx` 的坐标基于 `doc_parser.extract_text()` 返回的规范文本；每个 span 的 offset **不是** DOCX zip 字节 offset、XML 节点路径、Word 页码或版面位置。源 DOCX 原件由源 hash 识别，片段由规范文本 hash + offset 识别。
- 有效 DOCX 但抽不到正文/条款标题时不能报告“无缺失”。解析失败与成功但结构不足必须分开；不能 catch 后返回空文本。

**备选：** 保留目前 `.strip()` 语义并仅附 offset 原文，可兼容旧断言，但每个使用者都要猜两个文本版本的关系，且 range 本身不能精确还原 `span.text`。不推荐。

### 决策 D：源文件、规范文本、取文实现与词表分别版本化

新增单一不可变 `SourceEvidence`（可置于 `models.py`）并由 source adapter 创建，至少包括：

- `artifact_id` 与 `source_version`：合成输入使用稳定测试 ID 与显式 `r1/r2`，不得只用文件 basename 猜版本；未来真实源再由获准接入设计映射 SRM 文档 ID/版本。
- `source_sha256`：读取前对**源文件原始字节**计算 SHA-256；TXT/DOCX 都适用。
- `canonical_text_sha256`：对 adapter 最终交给 `ContractDocument.text` 的 UTF-8 字节计算 SHA-256。
- `text_view_id`/`text_view_version`：TXT 解码规则或共享 DOCX 门面/调用选项的标识；运行构建的不可变版本由部署/build metadata 提供。不得假设当前 facade 有 `__version__`（已读公开门面没有展示该字段）。
- `offset_scheme`：固定为类似 `sc4-canonical-text-u32-half-open-v1` 的稳定名称，明确单位与来源视图。

词表沿用显式 `ClauseLexicon.lexicon_id`，必须自带版本语义（本期为 `mock-v0`）；没有默认词表。不要在本期引入第二个互相可能漂移的 `lexicon_version` 字段。今后真实法务定位词表由专业签认和独立变更定义版本格式。

每次审计同时记录源 hash、规范文本 hash、取文视图及其版本、offset scheme、lexicon ID、`doc_id`、`source`、抽取状态和统计。`AuditEvent.content_hash` 应改为绑定这些稳定 provenance/evidence 字段的 manifest hash，而不是仅 hash 覆盖概览；不把整份合同正文写进 audit。相同覆盖数量/类别但正文已变的两个版本必须产生可区分的 hash/来源记录。

### 决策 E：审计是 orchestration 运行路径的必需依赖

当前 `run_extraction(..., audit=None)` 可无审计返回结果；`main()` 也不传 audit。**推荐：** `run_extraction` 的 `AuditLogger` 改为必需参数，并对成功抽取、无结构结果和可捕获的取文失败写一条结果状态明确的 audit；audit 不能写时 fail-closed，不返回成功结果。纯函数 `segment()` 可继续只负责解析/切分，不做 IO；不得把直接调用低层纯函数冒称完整 L2 run。

mock tests 使用 `tmp_path` 下的 JSONL audit 与清楚标记为 synthetic/test 的 evaluator ID（仅测试，不是某个法务/采购专员），验证可归责字段非空和数据链闭合。生产/真实合同入口未来须由受控运行上下文提供真实 actor ID；本 design 不指定或臆造姓名、Owner、backup，也不把实名未知当作合成测试阻塞。

`data_sources` 携带 contract artifact/version/hash、canonical text hash、text-view/parser build、offset scheme、lexicon ID；`decision` 携带抽取状态、coverage 与 `review_status="待前置到位"`、`blocked_by=["standard_clause_library", "risk_clause_criteria"]`。不得在 audit 中出现模拟风险级、偏差结论或缺失条款补集。无合法 actor、缺 provenance、adapter 失败或 audit 持久化失败均不可生成正常成功记录。

## 3. 组件与数据流

```text
合成 TXT/MD ── PlainTextSource ─┐
                               ├─ ContractDocument(text + SourceEvidence)
合成 DOCX ── DocxTextSource ───┘       │
  shared doc_parser.extract_text       ▼
  include_extra_parts=False     segment(doc, explicit mock lexicon)
                                       │
                         spans: exact raw slice + coordinate scheme
                                       │
                       summarize_coverage (事实字段，无 missing_types)
                                       │
                       run_extraction + mandatory audit record
                                       │
                       六项 synthetic evidence comparison

review.compare_with_standard / grade_risk / detect_missing_clauses
                 └── 继续由 pending.require 阻断，绝不连接到上面输出
```

建议实现接口形态（签名供 design 讨论，不是已落库代码）：

```python
@dataclass(frozen=True)
class SourceEvidence:
    artifact_id: str
    source_version: str
    source_sha256: str
    canonical_text_sha256: str
    text_view_id: str
    text_view_version: str
    offset_scheme: str

class DocxTextSource:
    def load(self, ref: str) -> ContractDocument: ...

def run_extraction(
    doc: ContractDocument,
    lexicon: ClauseLexicon,
    *,
    evaluator: str,
    audit: AuditLogger,
) -> ExtractionResult: ...
```

精确 `DocxTextSource` 文件访问/引用根、安全检查与 source hash 生成留给实现 plan；不允许仅拼路径从不受控输入读取。Stage A 的测试源来自包内 `tests/mock_data`，路径在 tests 内固定；不会开启任意目录或 SRM 取文。

## 4. 六项证据对照与未来验证方向

以下是批准意图中的六项 synthetic evidence comparison；不是本轮已运行测试、已产出的产品 fixture 或已签认标准。未来实施后每项均保存稳定 `case_id`、输入版本/sha、lexicon ID、parser/text-view 版本、offset scheme 与 audit event 关联 ID。设计通过前不创建 fixture、不跑测试。

| Case | 合成输入/对照 | 必须可验证的证据 | 明确不得推断 |
|---|---|---|---|
| SC4-M01 | 同一份四类条款合同分别以 TXT 与 DOCX 表达；正文均含四个可靠编号标题 | DOCX 取文与 TXT 的规范文本/条款顺序对照；四类各一段；每段源/文本/词表版本与精确切片 | 不判断标准一致、法律有效、完整或风险 |
| SC4-M02 | 一条编号标题同时命中两类 mock 词 | 该段保留、命中原因可解释、归为 `OTHER`/未归类 | 不择一猜类别，不判偏差 |
| SC4-M03 | 一条编号标题不命中四类 mock 词 | 段落不丢；原文位置、显示文本和“未归类”明确 | 未归类不等于无风险/无缺项 |
| SC4-M04 | 一份无任何行首编号标题的纯文本；正文另含被引用的“第三条”字样 | 空 spans + `no_clause_headings`/结构不足状态；行中引用不被误识别成新标题 | 不把空集合或结构不足解释成“合同没有必备条款” |
| SC4-M05 | 标题前缩进、标题行与末尾含空格/空行的合同 | 半开区间严格连续；原切片等于 `span.text`；`display_text` 才可 trim；覆盖 UTF-8 中文和 LF/CRLF 输入约束 | 不把展示字符串位置伪装为原文 offset |
| SC4-M06 | 同一逻辑合同 ID、相同覆盖类别/数量，正文分别为 r1/r2 | 原件 SHA、规范文本 SHA、版本、audit manifest hash 均可区分，旧记录不被新版本覆盖 | 相同 summary 不意味着同一合同内容或相同法律结论 |

另设边界断言，不扩成新的业务用例：非法 DOCX/缺 `word/document.xml` 或 XML 坏时保留 `DocxReadError`；有效但零文本与合法文本无标题可区分；`.pdf`、`.doc` 仍明确拒绝且无 OCR/纯文本回退；缺 evaluator/provenance/audit 时不成功；audit I/O 错误不生成正常结果；三项 `review.py` 调用仍抛 `PendingPrerequisiteError`。

未来验证顺序（不在本轮执行）：source adapter 行为 → exact-range/offset 属性 → 六个 case 输出逐格与人工核 → audit manifest/hash/必填/失败路径 → review 三闸回归。只在合成数据上运行定向 tests；design 审批之前不执行实现/TDD/测试。

## 5. 任务顺序与原 tasks 的精确修订建议

### 5.1 阶段建议

原 tasks 头部写明“第 2 组之后不得在 design 审通过前开工”；第 2 组 2.1/2.2 是知识前置，第 2.4 是 design 审；第 3 组为“取文层接真”，第 4 组为审核层。建议**保留所有专业闸的实质效力，但把无依赖的 Stage A 明确拆成一个有自己审批闸的独立子阶段**：

1. Stage A：design 审通过 + 明确批准具体实施计划 + Root 将获批拆分正式登记到 tasks + 明确领取具体触碰区之后，才实现合成 `.txt/.md`/`.docx` evidence slice。它不依赖 2.1/2.2 的专业内容，不接真实数据、不做 review 能力。
2. Stage B：公司标准库、风险判据工作坊、backup实名、实际适用条件到位并回填后，按独立 design/change 处理真实比对、风险、缺失能力；现有 `pending.require` 在此之前保持原样。
3. Stage C：SRM read-only、真实合同、检索、摘要和外部/部署能力各自等待数据授权、专业审批及对应设计，不由 Stage A 晋档。

这是供审的 task split 建议，不是本稿替 Shao Peishen 批准的绕闸。若设计审认为 section 2 知识闸必须整体先满足，则 Stage A 也停在设计/证据表准备，tasks 不作例外；任何实现仍等新任务授权。

### 5.2 建议对原 `openspec/changes/sc4-contract-clause-extraction/tasks.md` 的具体改动

- **头部两处闸语句：** 保留 `design.md` 未获审不得实现；把“第 2 组之后全部不得开工”改成“所有实现必须先过 design 审；仅新增明确标注的 Stage A 合成证据任务可在 2.1/2.2 未完时运行；任何比对/风险/缺失、真实合同/SRM、摘要和检索任务仍受原前置闸控制”。必须同时写明这是例外白名单，只有 Stage A 的明确任务号可用，不是整组解锁。
- **2.1 公司标准条款库与 2.2 风险判据工作坊/backup：** 原条目和未勾状态不改；补上它们分别阻断的功能（比对/缺失；风险分级）与 Stage B，未知的真实姓名保持空白。技术 mock 不得被 2.1/2.2 的实名状态误挡，也不得从 mock 结果把它们勾成完成。
- **2.3 排期对齐：** 原文所记“已拍定 2026-11、权威重排尚未执行”与当前来源之间的具体现况由全景路线图线维护；设计不自行改目标月或重排九文档。该行政任务不构成合成材料技术依赖，但在正式包收口前按排期权威处置。
- **2.4 design：** 改为“形成包含 Stage A 证据层、Stage B 专业闸后审核层、Stage C 数据/发布边界的完整技术 design 并经 Shao Peishen 审批”。标注本审只准核 design，不自动开实现；review 结果和任务拆分变更另记。
- **新增一个独立 Stage A 小节（建议接在 2.4 后、原 3 前）：** 明列六项 Case M01–M06、exact raw-slice/coordinate contract、source/text/parser/lexicon version+hash、audit 必填和失败闭合、对 `.doc`/PDF/OCR/SRM/真实判断的拒绝条件。每个子任务列明确文件和 synthetic fixture，要求由 Root 另行分派；实现无真实名 Owner 依赖。
- **原 3.1：** 将“平台底座 `doc_parser` 落地后”改成现状事实“复用已在 2026-09-07 落地的共享 `doc_parser.extract_text`，仅实现 SC4 DOCX source adapter；不改底座、不宣称 PDF/.doc/OCR”。Stage A 仅可用合成 DOCX；SRM 仍由独立项阻断。
- **原 3.2：** 保留 SRM 文档库 read-only 接入项，明确依赖数据访问授权和字段/版本映射设计；不因共享 parser 存在而提前接源。
- **原 3.3：** 改写为对不支持的 PDF/旧 `.doc` 明确拒绝、解析失败 fail-loud 的合成边界测试；不承诺扫描 PDF 取文或 OCR。若原测试意图是“扫描 PDF fail-loud”，应归到该边界，不得令 Stage A 变成 OCR 项。
- **原 4.1–4.6：** 原样保持知识/专业闸，不移入 Stage A，不用 mock 标准、风险等级或缺失清单完成这些任务；不因专业 signoff 未实名而要求 Shao Peishen 代填专业答案。
- **原 5.1–5.2、6.1–6.3：** 不提前启动。摘要/提示、条款检索、真实数据验证、归档发布、门户与部署继续在各自验收与审批后进行。

### 5.3 建议的实施触碰面（仅供 review 讨论）

若未来 Stage A 获正式批准，预期最小产品面为：

- 修改 `4-数字员工/采购部/SC4-合同条款自动提取与审核/sc4_contract/models.py`（来源证据与抽取状态）。
- 修改 `.../sc4_contract/text_source.py`（新增 DOCX adapter，保留 PlainTextSource 当前边界）。
- 修改 `.../sc4_contract/clause_extract.py`（精确 raw slice 与结构不足状态/概览）。
- 修改 `.../sc4_contract/agent.py`（必需 audit、manifest hash 与 provenance payload）。
- 修改/新增 `.../tests/test_text_source.py`、`test_clause_extract.py`、`test_agent_audit.py` 和固定合成 fixture（TXT/DOCX 仅存 `tests/mock_data/`）。
- 对原 delta/main spec、tasks、README/SC4 `CLAUDE.md` 的窄幅同步按正式 package 流程另行审阅；尤其删除“doc_parser 尚未落地”的过时描述。不改 `zhuopin_platform`，不增第三方包，不建服务/UI。

这是候选实现文件集合，**不是已批准修改白名单**；本轮没有触碰上述任何源文件。

## 6. 对原 OpenSpec spec 的建议修订

原 change spec 与已同步 main spec 写“在统一 `doc_parser` 落地前，不自建 PDF/Word解析；收到 `.pdf`/`.docx` 即拒绝”。当前平台 CLAUDE 与门面源码证明 `.docx` parser 已存在；这两句在时间/格式上已经过时，不能原样成为 Stage A 实现目标。建议在正式 design 审批后同步更新两份 spec，保留“不自建 parser”红线并区分格式：

> 系统 SHALL 通过可替换的 `TextSource` 取文。`.txt`/`.md` 使用既有纯文本 source；在 Stage A 的合成数据范围内，`.docx` 只调用 `zhuopin_platform.shared_tools.doc_parser.extract_text`，并把解析器返回的规范文本作为 SC4 offset 坐标视图。系统 MUST NOT 自建 DOCX/旧 `.doc`/PDF/OCR 解析器。`.doc`、`.pdf` 与不支持的输入 SHALL fail-loud；DOCX 解析异常 MUST NOT 转成空文档或成功的零片段。

建议新增/明确两个 requirement：

1. **抽取位置与文本呈现：** `ClauseSpan.start/end` 在声明的 `ContractDocument.text` 坐标中为 0-based half-open 区间；`doc.text[start:end] == span.text`；展示归一化不得改变留痕片段；对 DOCX 明示坐标属于 parser canonical text，不是原始 XML/页面坐标。
2. **来源证据和审计：** 每次 `run_extraction` 必须审计，必填 actor、source artifact/version/sha、canonical-text sha、parser/text-view version、offset scheme、lexicon id 与 extraction status；审计失败 fail-closed。结构不足/解析失败不产生缺失或风险判断。原件内容不写入 audit；审计只留受控标识与 hash。

是否更新所有原 requirements 与 scenarios、同步 main spec，由正式 design 审/openspec review 决定；这份供审稿不改变 normatively active spec。

## 7. 专业五项与 Owner/backup 分离

SC4-G-01 到 G-05 是 intent 当前的五个**专业占位**，没有 M2 台账记录/CriteriaRegistry 状态，也未 signoff。它们不构成技术 Stage A 的实名前置，但始终挡住相应专业能力：

| ID | 专员需要提供的专业材料 | 不能由技术 mock 代替 |
|---|---|---|
| SC4-G-01 | 真实定位词表、同义表达、多类/未归类时的人工归属 | `mock-v0` 只定位，不构成公司词表 |
| SC4-G-02 | 受控标准合同条款库、适用合同对象与版本 | Mock 四类命中不是标准比对 |
| SC4-G-03 | 措辞差异与权责差异边界、语义等价/偏差规则 | 不自拟法律解释/阈值 |
| SC4-G-04 | 风险分级尺度、边界与人工处置确认 | 不输出 mock 风险级别 |
| SC4-G-05 | 必备条款清单、例外适用、缺失判定 | 规划中的例子不成为标准清单 |

标准库当前归因法务+采购；风险判据持有人法务，backup “采购合同岗”仍待实名点名。任何实名均保持空白直到权威人事/业务记录给出，不在 design 中猜姓名。业务 Owner/backup 只阻断 Stage B 及相应真实判断任务；Stage A synthetic executor/evaluator 由执行记录显式给出测试 actor，不要求其具备法务专业身份，也不写成业务验收 signoff。

## 8. 未决技术点与处理界面

以下问题可由设计审阅者确认或要求小修；没有一项需要 Shao Peishen 代答专业判据：

1. **SourceEvidence schema/API 位置**：建议在 `models.py` 加 frozen record；若审阅要求独立模块，保持字段合同不变。实现前由写 tasks 的 Root 锁定。
2. **构建版本值的来源**：当前公开 doc_parser 门面未展示 `__version__`。设计要求 runtime 从不可变 build metadata 注入 parser revision；Stage A synthetic tests 可显式固定 fixture parser profile。若执行环境无法提供 build id，不可谎报版本；该次正式 audit 必须 fail-closed 或明确标记仅 test。
3. **UTF-8 文本换行**：TXT/MD 保留读入字符内容，不由 source adapter 规范换行；DOCX 使用现有 facade 输出的 `\n` canonical join。M05 覆盖 LF/CRLF 原文回指。不要宣称两个载体字节级相同，只比较各自的已定义文本视图与条款证据。
4. **有效 DOCX 的零文本**：区分 `empty_text` 与 `no_clause_headings`，两个都是“证据不足”，不会返回 review 缺失项。Malformed ZIP/XML 是失败，不是空文。
5. **审计 actor**：测试允许专用 synthetic actor 标识；真实运行的身份来源/权限在真实接入前置中设计，不以未知实名阻断 synthetic test。

## 9. 审阅边界

设计审阅可批准/修订技术 design 与 Stage A/Stage B 的任务拆分；它不会自动批准代码、测试、真实数据、法务规则、SRM 权限、黄金集、外发、ff、部署或 stage promotion。原 OpenSpec 第 2 组前置、`pending.require`、L2 人工确认和真实数据闸在正式变更包更新并分别审批之前均保持有效。

本轮只补design供审；未运行产品测试、未读取真实合同/访问SRM、未改源码/tasks/spec/运行时或创建产品fixture。Root 已串行补入本design供审；tasks/spec仍等设计批准后按明确范围修订；只有design与具体实施计划均获批、拆分依赖正式登记后，才能进入实现阶段。

## 10. Root 收敛的实现合同、风险与迁移

### 10.1 当前设计中已定的技术点

1. `SourceEvidence` 固定放在场景 `models.py`；不再把模块位置作为待用户裁决项。source adapter接收受控合成资料根和显式artifact/revision映射；resolve后的路径必须落在该根内，拒绝绝对外来引用、逃逸路径和不支持扩展名。具体函数签名在后续实施计划锁定。
2. 源资料按一次捕获的原始bytes计算source SHA；TXT/MD以UTF-8直接解码该bytes，保留LF/CRLF而非默认text open换行转换。DOCX把这份已捕获bytes写成仅本次使用的隔离合成快照，再调用既有共享门面，保证取文和source hash针对同一份bytes；不从变化中的原路径再次读入。快照目录/定向清理在具体计划中列明，不触碰真实合同。
3. `text_view_version`来自显式注入的受控build/profile引用（必须可对应共享parser与include_extra_parts=False）；合成测试引用显著带MOCK，不能冒充运行构建签认。正式版本来源未证时相应运行失败关闭，不猜`__version__`。
4. raw slice和display string是两个视图。现有依赖strip的测试/消费者须按获批计划迁移到display view；旧记录不重写，解析异常保持失败，不能转成空成功。
5. Root已核平台`audit/events.py`：`decision: dict[str, Any]`、`data_sources: dict[str,str]`、`to_dict()`为asdict且timestamp缺省UTC。证据元数据放现有decision，data_sources只放字符串ID/版本/hash，不改平台schema或保存合同正文。

### 10.2 Risks / Trade-offs

- [原件与文本来自不同读次] → 捕获一次bytes并用隔离快照解析，manifest绑定同一内容。
- [raw文本语义改变影响旧展示] → 实施计划列明所有旧调用/断言迁移，保留display view，旧审计不重算。
- [词表命中被误当法律审核] → 三review函数继续pending.require；任何输出保持“证据定位/专业前置未到位”。
- [parser坐标被当Word页码] → 每例声明canonical text视图、offset scheme和两个hash。

### 10.3 Migration Plan

本轮只补design。批准A–E及上述收敛后，先正式修订Stage A白名单依赖和delta spec建议，再写具体实施计划供审；任何mock实现仍等计划批准并在获准隔离环境进行。保留原专业/真实/发布任务未勾。main spec只在对应规范批准、实现及正式同步阶段处理，不提前同步。失败时保留原骨架及审计记录，不回写/替换历史合同或旧成果；本设计不部署。

### 10.4 当前供审决策

请审A–E、Stage A窄片依赖拆分与10.1技术合同；本次若批准，仅推进正式任务/规范映射和具体实施计划，不授权产品改码/产品测试、专业判据或发布。

