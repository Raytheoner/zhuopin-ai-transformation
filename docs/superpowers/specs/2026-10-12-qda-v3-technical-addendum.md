# QD-A 七步法技术澄清附录

**绑定对象：** QD-A 七步法 OpenSpec 四件 design，正式封存待审 HEAD `8b129752770c3cc73c4848b8a2937fcccb96d18a`，design SHA256 `e08bb4863ddf21cb994186b7a1a662c3f190d2e7b5276552ef04c551ac7516a6`。

**用途：** 仅澄清该 design 的输入证据、QD-A→Q2 typed 状态传递、分流次序及未来代码/测试落点。此附录不是新的专业判据或实现授权；必须与上述实际 design 一并由 Shao Peishen 单独批准，批准须同时绑定二者版本与未来允许路径。任何冲突以重新审阅后的批准文本为准。

**静态依据：** `reports/pc-mvp-1012/readonly-input-bundles-v2/qda/INPUTS.md` 所列四份源码副本：`02-doc_reader.py.txt` SHA256 `c00da7b2ed4b27987c3a50d89b9fad353dad22d033502d66caa7639330eb0842`；`03-feed_source.py.txt` SHA256 `923636a1965b04e4542a0b2228b47bf218a40f355492f08d5ff586ade8a3a0e9`；`04-engine.py.txt` SHA256 `5b4d521c7c5015860ac217a0a22fbd75b18382260aadb767f8717c2ec4905a47`；`05-config.py.txt` SHA256 `f3d086ee006d505b9376a06be3a4185ae73f6ccf6b14eb98d542d849009e27b7`。本轮只读、未重新散列上述副本，未运行代码/测试/CI/strict，也未改四件、源码、规则、队列或 runtime。

## A. Raw boundary input 与定位合同

### A1. Typed data contract

QD-A `qda_prefill/doc_reader.py` 内的 raw 类型作为调用期数据，不改变既有 `DocumentSections.sections` 和 `SceneCheckbox`：

```python
from dataclasses import dataclass
from typing import Literal

StepToken = Literal["一", "二", "三", "四", "五", "六", "七"]
ChapterState = Literal["extracted", "confirmed_blank", "unreliable", "ambiguous"]
DocumentState = Literal["reliable", "unresolved"]
BoundaryOrigin = Literal["synthetic_fixture", "source_structure_metadata"]

@dataclass(frozen=True)
class TextSpan:
    source_text_sha256: str
    start_offset: int       # zero-based Unicode code-point offset; inclusive
    end_offset: int         # zero-based Unicode code-point offset; exclusive
    start_line: int         # one-based line in normalized full_text
    end_line: int           # one-based line in normalized full_text

@dataclass(frozen=True)
class TopLevelBoundaryCandidate:
    source_text_sha256: str
    step_token: StepToken | None
    heading_kind: Literal["seven_step", "dn_or_other_top_level"]
    title_span: TextSpan
    origin: BoundaryOrigin

@dataclass(frozen=True)
class SevenStepChapter:
    step_token: StepToken
    state: ChapterState
    body_text: str | None
    title_span: TextSpan | None
    body_span: TextSpan | None
    candidate_title_spans: tuple[TextSpan, ...]

@dataclass(frozen=True)
class SevenStepRawExtraction:
    template: Literal["七步法"]
    document_state: DocumentState
    source_text_sha256: str
    normalized_text_length: int
    chapters: tuple[SevenStepChapter, ...]
    unresolved_reasons: tuple[str, ...]
```

`source_text_sha256` 必须是本次 reader 的精确 `DocumentSections.full_text.encode("utf-8")` 的 SHA-256；不把 binary DOCX/PDF/PPTX digest 冒称为规范化文本 digest。offset 针对这一个精确 `full_text` 字符串，起点 0、终点 exclusive；行号针对同一字符串 `splitlines()` 后的 1-based 行。span 内的文本必须等于对应切片，且 span 和候选均绑定同一 hash。不得把这些 locator 表述为物理页码、OOXML 坐标或文件内绝对坐标。

调用合同可保持现有 `read(path)` 兼容，扩展为显式可选参数：

```python
def read(
    path: Path | str,
    *,
    template: str | None = None,
    boundary_candidates: tuple[TopLevelBoundaryCandidate, ...] = (),
    ) -> DocumentSections: ...
```

未传 `template="七步法"` 时 `DocumentSections.raw_seven_step is None`，旧 Dn/短标题和 `SceneCheckbox` 输出不变。显式七步声明时总要返回 raw 结果；缺少可验证边界时返回 `document_state="unresolved"`，不能以 `None` 表示“没有问题”。现有输入调用 `zhuopin_platform.shared_tools.doc_parser.extract_text_lines()` 只给出文本行，未显示 heading-level 元数据；因此调用方没有独立 top-level source evidence 时必须传空候选并得到 unresolved。mock 单测可用 `origin="synthetic_fixture"` 的显式 span 构造可重复输入；该 fixture 证明算法合同，不证明客户模板适用。

### A2. 边界校验与状态判定

1. 在读取异常时继续原样传播异常；不能返回空 `DocumentSections` 或 raw 空白结果。
2. 先核对 explicit template、candidate hash、offset 范围、title span 的实际文本、行号/offset 一致性；hash 不符、越界或无法绑定源文本时结果 unresolved，不猜测修补 offset。
3. `reliable` 只接受恰好一组、唯一、严格按「一→二→三→四→五→六→七」排列的七个可信顶层 step anchors；每章 title span 必须真实落在 normalized text 中，body span 从标题末尾到下一可信顶层边界开始（第七章到文本结尾）。
4. 同一 ordinal 有多个可信候选、顺序冲突、或输入同时给出七步与 Dn/其他顶层 heading 候选：状态为 `ambiguous`，保留所有有效候选 title span，不择一、不覆盖。缺失 ordinal、没有任何可用 top-level evidence、或边界/hash/locator 无法验证：缺章标 `unreliable`，文档 `unresolved`；不为缺章造空 body/span。
5. 只有唯一可信标题和可信结束边界均成立时，才可从对应切片判定：有非空正文为 `extracted`，body_text保留精确切片；切片 `strip()` 后为空为 `confirmed_blank`，用于旧映射的 `body_text=""`，body_span仍定位原切片（可以包含空格/换行）。其hash/offset绑定原文，不把显示用空字符串冒称为原切片；边界不成立时即使切片为空也不是 `confirmed_blank`。
6. 文档仅当七章状态全是 `extracted` 或 `confirmed_blank` 且顺序与所有 locator 校验均通过时为 `reliable`；其余均为 `unresolved`。文本中单独出现「一、二…」不产生 candidate；候选必须来自绑定到 normalized text hash/offset 的显式 top-level evidence。

### A3. 当前数据源限制

四份源码副本显示：`doc_reader.read(path)` 返回 `DocumentSections`；DOCX 经 `extract_text_lines()` 后 join 成 `full_text`；`_parse_sections()` 逐行识别 Dn 分隔及短标题，虽有 `_SECTION_PATTERNS` 常量但并不使用该列表。该 reader 输入没有已证明的标题层级信号。于是当前静态证据能支持的结论是：纯文本正则不能证明 top-level；无单独边界证据时应 unresolved。`source_structure_metadata` 是 raw contract 保留的来源类型，**不表示本次已证明有此生产数据源**。当前 mock-only 正向案例通过显式 fixture anchors 验证；不声称真实文档可产生可靠章节。若未来希望对非 mock 文档启用 positive extraction，必须先找到并审查一个不改共享 parser、不扩大模板面的现存可信 source-structure provider；找不到时保持 unresolved，不把这项技术事实交给专业人员决定。

## B. QD-A → Q2 typed handoff 与兼容语义

### B1. 当前可确认接口与最小场景内扩展

四源码副本能确认以下现有符号：

- QD-A `DocumentSections`（定义在 `qda_prefill/doc_reader.py`）含 `full_text`、`sections: dict[str, str]`、`header_text`、`source_path`、`scene_checkbox`。在该模型末尾加 `raw_seven_step: SevenStepRawExtraction | None = None`；旧构造兼容，`.sections` / `.scene_checkbox` 不重解释。
- Q2 `feed_source.from_qda(report_id, sections, record, *, scene, template="标准8D", oem="") -> EightDInput` 是现有 adapter。新增仅 keyword optional 的 `raw_seven_step` 参数，默认 None；它只把 QD-A raw result 原样传入 `EightDInput`，不得把原文塞进 `sections` 或改造 `SceneCheckbox`。
- 父级定点补核实际 `q2_8d_verdict/models.py`（Get-Content + Get-FileHash，SHA256 `359710656b1323e541b9682c2ed8a774edbc36021a2c2bf70a4ee1753e7536ea`）：`EightDInput`是普通dataclass，前三必需字段report_id/sections/scene；template、安全/ASIL/trace_fields/is_external均有默认，最后meta为`dict[str, Any]`且default_factory=dict。当前无raw字段。最小扩展在末尾追加`raw_seven_step` typed field默认None，所有原构造位置/默认/meta保留。为避免 Q2 import QD-A 运行时包，Q2 `models.py`声明与 `SevenStepRawExtraction` 结构等价的 `Protocol`（文档模板/状态/hash/章节；章节 token/state/body/locator/candidates 类型均显式），让from_qda只接该protocol。未来实现仍复核调用者及序列化兼容，不能保持时停止另审；不新增共享模块。
- Q2 `VerdictEngine.normalize_sections(doc) -> dict[str, str]` 当前从 `config.CRITERIA.value_of("J10_TEMPLATE_MAPPING")` 取映射；七步 `doc.sections.items()` 遍历顺序并将同一目标内容 append。`VerdictEngine.evaluate(doc) -> Verdict` 先对 ASIL C/D 抛 `AsilExcludedError`，后执行 normalize、`structural_empty`，再 redline/scoring。

### B2. 新旧路径与执行顺序

- `raw_seven_step is None`：旧 statusless direct call 继续现有行为；不猜它是可靠新 raw extraction。未声明模板时始终使用现有 Dn/短标题 path。
- 显式七步 QD-A 调用：`read(..., template="七步法")` 总返回 `SevenStepRawExtraction`，即使 unresolved；调用方将该值传给 `feed_source.from_qda(..., raw_seven_step=...)`。Q2 `EightDInput.sections` 保持传入的原 Dn sections，raw payload 独立。
- Q2 engine 首个既有 ASIL C/D guard 原位保持第一。guard 通过后，在 `normalize_sections` / `structural_empty` / score 之前检查：当模板为七步且 raw `document_state == "unresolved"` 时，返回既有 `Verdict` 类型、`Disposition.MANUAL`，不得结构性退回、红线自动退回、评分或级别结论；附状态/原因说明，不保存章节正文。`raw_seven_step is None` 的 statusless 旧调用不触发该新分支。
- 模板为七步且 raw `document_state == "reliable"` 时，`normalize_sections` 依 `chapters` tuple 原序遍历，每章用源头 `step_token` 作为 J10 key，从既有 `config.CRITERIA.value_of("J10_TEMPLATE_MAPPING")` 查目标；按现有 append 语义累加正文。不得在 QD-A、adapter、Q2 engine 增加第二份「一到D2、二到D4…」表。`Two` / `Four` 的原文与 locator 仍由 `raw_seven_step.chapters` 分别保留，归一化 D4 顺序为二后四。
- `confirmed_blank` 作为可信空字符串跟随原映射进入既有结构 gate；不新增逐 raw chapter 的专业空白门槛。J9 判断的是既有归一化 D section 是否空，因此当二/四合并 D4 时，单独一章空白而另一章非空，不得由新技术层自行推导结构退回。
- 不添加/改写 J5、判例10、J10、阈值、红线、`PENDING`/`PendingSemantic`、L2、安全或 OEM 规则。Audit 若确需表达 raw 状态，只投影模板、状态、source hash、locator 摘要和既有必要身份；不得记 `body_text`、真实报告原文或客户/OEM 技术文本。原有 QD-A/Q2 source、confidence、OEM 元数据仍由现有字段传递。

## C. 未来精确文件与验收节点

以下路径均相对仓库根。列出的既有测试目录已存在；Q2 的 `tests/test_feed_source_seven_step.py` 是唯一建议新增测试文件。不得改 `config.py`、专业正本、平台 `doc_parser`、其它 QD-A/Q2 文件、门户、服务、CI 配置或队列；若实施发现必须额外改路径，须先停止并更新批准白名单。

| 未来文件 | 精确测试节点/职责 |
|---|---|
| `4-数字员工/质量部/QD-A-8D不良分析/qda_prefill/doc_reader.py` | `read(path)` 兼容；显式 template 边界输入；hash 与 span/行号绑定；七 ordinal 顺序；缺失、重复、乱序、mixed Dn、hash mismatch；confirmed_blank 与 unreliable 分离；异常继续 fail-loud；`sections` 和 SceneCheckbox 不变。 |
| `4-数字员工/质量部/QD-A-8D不良分析/tests/test_doc_reader.py` | 增加 `test_default_read_keeps_legacy_sections_and_scene_checkbox`、`test_body_numbering_without_top_level_evidence_is_unresolved`、`test_fixture_bound_seven_step_spans_match_hash_and_order`、`test_confirmed_blank_requires_both_boundaries`、`test_missing_duplicate_out_of_order_and_mixed_candidates_fail_closed`、`test_hash_mismatch_does_not_repair_locator`、`test_docx_read_error_still_propagates`。assert exact body/span/hash/status，不只比“有结果”。 |
| `4-数字员工/质量部/Q2-8D报告AI判定/q2_8d_verdict/models.py` | 定义 Q2-local typed Protocol/raw field (`raw_seven_step: ... | None = None`)；其它 `EightDInput` 字段、默认、构造语义兼容；不引入专业映射。 |
| `4-数字员工/质量部/Q2-8D报告AI判定/q2_8d_verdict/feed_source.py` | `from_qda` 的 optional keyword raw handoff；sections/safety/confidence/OEM/template 原字段原样保持；None statusless 旧调用不补 raw。 |
| `4-数字员工/质量部/Q2-8D报告AI判定/tests/test_feed_source_seven_step.py` | 新测试文件：`test_from_qda_preserves_raw_status_and_legacy_metadata`、`test_from_qda_none_keeps_statusless_compatibility`、`test_raw_payload_is_not_folded_into_existing_sections`；断言完整 typed object、元数据和默认值。 |
| `4-数字员工/质量部/Q2-8D报告AI判定/q2_8d_verdict/engine.py` | unresolved 手动分流位于 ASIL guard 后、normalize/structure/score 前；reliable raw 只通过 J10 有序映射；statusless旧路不变；D4 append 保留二后四。 |
| `4-数字员工/质量部/Q2-8D报告AI判定/tests/test_engine_mock.py` | 增加 `test_asil_cd_guard_precedes_unresolved_raw`、`test_unresolved_raw_routes_manual_before_structure_and_score`、`test_reliable_raw_uses_j10_and_preserves_two_four_d4_order`、`test_confirmed_blank_uses_existing_normalized_structure_gate`、`test_statusless_and_dn_short_title_paths_are_unchanged`；以 monkeypatch/spies 断言调用顺序、未运行评分、J10 唯一来源及 SceneCheckbox/Dn 回归。 |

### C1. Future test commands

仅未来获 design+实现授权后，分别从以下子项目根使用同一已指定隔离解释器；不在仓库根运行 pytest。实际实施仍须先按当时 CI 矩阵确认解释器文件存在且与该子项目配置匹配；不安装全局 editable 指针。

```powershell
Set-Location "4-数字员工/质量部/QD-A-8D不良分析"
& "C:/Dev/Codex/runtimes/zhuopin-ai/venv/Scripts/python.exe" -m pytest -q tests/test_doc_reader.py

Set-Location "4-数字员工/质量部/Q2-8D报告AI判定"
& "C:/Dev/Codex/runtimes/zhuopin-ai/venv/Scripts/python.exe" -m pytest -q tests/test_feed_source_seven_step.py tests/test_engine_mock.py
```

## D. 三项审查缺口闭合状态与残余事实

1. **边界输入/locator 合同：已闭合为 mock 技术合同。** hash、offset、line、step order、缺失/歧义/unreliable 与 fail-closed 语义具体化；现实 reader 无层级 metadata 的情况明确 unresolved。四源码未证明有 production top-level structure provider，这是当前技术事实，不通过正则猜测或专业签认补足；本附录不宣称真实文档 positive extraction。
2. **QD-A→Q2 接缝：已闭合为 typed 接口与执行顺序合同。** `DocumentSections` raw sidecar、`from_qda` keyword、Q2 `EightDInput` optional protocol field、ASIL→unresolved MANUAL→其余旧流程顺序已写明。实际 `EightDInput` 定义不在四份源码副本中，因此实现前须对 `q2_8d_verdict/models.py` 只读核实兼容；这不授权改动其它字段或 professional config。
3. **未来路径/验收：已闭合。** 逐项指定 7 个源/测试路径、函数/测试节点、两个项目根和隔离解释器；共享 CI 与专业配置不在白名单。

上述闭合仅指技术设计澄清完整，不代表 strict 通过、实现授权、真实输入支持、产品测试、发布或 MVP 交付。任何超出本文列明文件范围的修改必须先走单独批准。
