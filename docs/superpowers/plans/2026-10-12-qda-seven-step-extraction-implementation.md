# QD-A 七步法原始章节提取实施计划

> **For agentic workers:** 按任务顺序逐项执行；所有测试先写 RED、核对为功能断言失败，再作最小 GREEN。只实现下列七路径，不自行提交或推送。

**Goal:** 在 mock-only 范围内，为显式七步声明建立可核验的 raw 章节与定位合同，并将可信状态通过 Q2 接缝传递；无法核验的输入进入既有人工裁决路径。

**Architecture:** QD-A 在不改变 `DocumentSections.sections` 和 `SceneCheckbox` 的前提下附加独立 raw 七步对象；只有调用期显式提供、与规范化全文 hash/offset 匹配的顶层候选才能构成可靠章节。Q2 通过 optional typed 字段接收该对象，保留旧 statusless 调用；ASIL C/D 原排除最先执行，之后 unresolved 走既有 `MANUAL`，reliable 章节只按既有 J10 映射归一化。

**Tech Stack:** Python dataclasses、typing `Literal` / `Protocol`、pytest、项目隔离 Python 环境。

**Spec:** `reports/pc-mvp-1012/v3/qda-four-pieces/design.md`；绑定技术合同 `docs/superpowers/specs/2026-10-12-qda-v3-technical-addendum.md`。design HEAD `8b129752770c3cc73c4848b8a2937fcccb96d18a` / SHA256 `e08bb4863ddf21cb994186b7a1a662c3f190d2e7b5276552ef04c551ac7516a6`；附录 SHA256 `C0195F8A74B3729174EC5EAEBFE6E94F84D4EA6235FC500EBCE41BC1F2002460`。本计划绑定 Shao Peishen 对 design 与附录的 10A 批准；执行时须核对工作树仍对应该绑定版本。

## Global Constraints

- 唯一允许写入路径为以下七个，全部相对仓库根：
  1. `4-数字员工/质量部/QD-A-8D不良分析/qda_prefill/doc_reader.py`
  2. `4-数字员工/质量部/QD-A-8D不良分析/tests/test_doc_reader.py`
  3. `4-数字员工/质量部/Q2-8D报告AI判定/q2_8d_verdict/models.py`
  4. `4-数字员工/质量部/Q2-8D报告AI判定/q2_8d_verdict/feed_source.py`
  5. `4-数字员工/质量部/Q2-8D报告AI判定/q2_8d_verdict/engine.py`
  6. `4-数字员工/质量部/Q2-8D报告AI判定/tests/test_feed_source_seven_step.py`（新增）
  7. `4-数字员工/质量部/Q2-8D报告AI判定/tests/test_engine_mock.py`
- 输入仅使用测试内合成文本/合成 DOCX 与显式 `synthetic_fixture` anchors；不读、复制或记录真实 8D、OEM、客户或供应商原文，不产生真实模板 positive-extraction 声明。
- `doc_parser` 当前无已核实的层级 metadata provider；没有独立 top-level evidence 时，显式七步结果必须 unresolved。禁止放宽正文序号正则来制造标题证据。
- `source_text_sha256` 固定为规范化 `full_text.encode("utf-8")` 的 SHA256；offset 是该字符串的 0-based Unicode code-point 半开区间，行号是该字符串 `splitlines()` 的 1-based 行号。空白章显示/映射 `body_text=""`，locator 仍保留原始空白切片范围。
- raw 合同字段、步骤序列和状态以技术附录 A1/A2 为准；旧 `read(path)` 调用保持原义。Q2 `EightDInput` 末尾添加 `raw_seven_step` 默认 `None`，不能移动现有字段或改变默认值、`meta`。
- `from_qda(..., raw_seven_step=...)` 仅传递 typed 状态；不得把 raw 正文并入现有 Dn `sections`。statusless 旧调用不推断 raw。
- Q2 顺序固定：ASIL C/D 先按现有 `AsilExcludedError` 排除；其后显式七步且 raw unresolved 直接返回现有 `Verdict` 的人工裁决结果；之后才允许 normalize、结构闸、红线及评分。该 MANUAL 结果无结构性退回、红线结果、评分、等级结论；无等级时用既有 `Verdict` 类型 `grade=None`、`grade_range=(config.GRADE_D, config.GRADE_A)`、分数为 0 表示无分数结论，并保留 L2 人工属性。
- reliable raw 只通过 `config.CRITERIA.value_of("J10_TEMPLATE_MAPPING")` 映射；二、四原始章节和 locator 分别保留，D4 按二后四累加。`config.py`、J5、判例10、J10、阈值、红线、`PENDING` / `PendingSemantic`、L2 与安全专业口径均不修改。
- Audit 若扩展 extraction 状态，仅投影模板、状态、source hash 和 locator 摘要；不记录 `body_text` 或 OEM 技术原文。审计失败继续沿现有失败路径，不以保存成功作假。
- 除七路径之外不改服务/CLI、客户模板、共享工具、CI、fixtures 文件、规则、审计库、文档或队列；实现发现必须越界时停止并回到批准流程。
- 未来测试只在对应子项目根运行，使用隔离解释器 `C:/Dev/Codex/runtimes/zhuopin-ai/venv/Scripts/python.exe`；本轮计划编写阶段不运行测试、strict 或产品代码。

## Review Focus

1. **无证据的正文序号或错误 locator**：不能因“第一/二”等正文编号、错 hash、越界 offset 得到可靠章节；由 Task 1 的无候选、正文编号、hash mismatch、span/line 一致性测试固定。
2. **缺失、重复、乱序或 Dn 混杂**：不得补空、覆盖、择一或误标可靠；由 Task 1 的完整候选冲突测试固定。
3. **可靠空白与未可靠提取**：`confirmed_blank` 必须有双边界，映射空字符串但保留原始 body span；由 Task 1 空白边界测试和 Task 3 合并结构闸测试固定。
4. **兼容旧 Dn 与 SceneCheckbox**：默认调用以及 `sections`/checkbox 不变；statusless Q2 旧调用不推测 raw；由 Task 1 与 Task 2 回归测试固定。
5. **安全顺序、归一化及审计泄露**：ASIL C/D 先退出，unresolved 不运行结构/评分；reliable 二/四依 J10 顺序进入 D4，audit 不存正文；由 Task 3 顺序、映射、audit 测试固定。

## 文件结构与执行边界

| 文件 | 唯一职责 |
|---|---|
| QD-A `qda_prefill/doc_reader.py` | raw 七步类型、显式 template/candidate 输入、源定位验证和状态生成；现有 parser 路径不变。 |
| QD-A `tests/test_doc_reader.py` | 复用现有 docx/synthetic 测试风格，在文件内构造合成文本与 anchors；不新增 fixture 文件。 |
| Q2 `q2_8d_verdict/models.py` | Q2-local Protocol 与 `EightDInput.raw_seven_step` optional 字段。 |
| Q2 `q2_8d_verdict/feed_source.py` | `from_qda` optional raw keyword 的透明传递。 |
| Q2 `q2_8d_verdict/engine.py` | ASIL 后 unresolved MANUAL 前置闸、reliable raw 的 J10 归一化、必要的 hash/status/locator audit 投影。 |
| Q2 `tests/test_feed_source_seven_step.py` | adapter raw 透传与旧字段/旧调用兼容。 |
| Q2 `tests/test_engine_mock.py` | 安全/分流顺序、J10 二四顺序、结构空白语义与 audit 无原文回归。 |

跨任务接口固定为：

```python
read(
    path: Path | str,
    *,
    template: str | None = None,
    boundary_candidates: tuple[TopLevelBoundaryCandidate, ...] = (),
) -> DocumentSections

DocumentSections.raw_seven_step: SevenStepRawExtraction | None = None

from_qda(
    report_id: str,
    sections: dict[str, str],
    record: Any | None,
    *,
    scene: str | None,
    template: str = "标准8D",
    oem: str = "",
    raw_seven_step: SevenStepRawPayload | None = None,
) -> EightDInput

EightDInput.raw_seven_step: SevenStepRawPayload | None = None
```

Q2 的 `SevenStepRawPayload` 必须定义在 `models.py`，是 QD-A 类型结构等价的 Q2-local `Protocol`；其字段合同明确为：

```python
class SevenStepTextSpan(Protocol):
    source_text_sha256: str
    start_offset: int
    end_offset: int
    start_line: int
    end_line: int

class SevenStepChapterPayload(Protocol):
    step_token: Literal["一", "二", "三", "四", "五", "六", "七"]
    state: Literal["extracted", "confirmed_blank", "unreliable", "ambiguous"]
    body_text: str | None
    title_span: SevenStepTextSpan | None
    body_span: SevenStepTextSpan | None
    candidate_title_spans: tuple[SevenStepTextSpan, ...]

class SevenStepRawPayload(Protocol):
    template: Literal["七步法"]
    document_state: Literal["reliable", "unresolved"]
    source_text_sha256: str
    normalized_text_length: int
    chapters: tuple[SevenStepChapterPayload, ...]
    unresolved_reasons: tuple[str, ...]
```

不从 Q2 导入 QD-A 包，不新增共享类型文件。`models.py` 中已核实 `EightDInput` 是普通 dataclass，前三字段必需，其余现有字段有默认、`meta` 为末字段；追加 optional 默认字段后，原构造次序保持。

---

### Task 1: QD-A Raw 七步证据与 locator

**Files:**
- Modify: `4-数字员工/质量部/QD-A-8D不良分析/tests/test_doc_reader.py`
- Modify: `4-数字员工/质量部/QD-A-8D不良分析/qda_prefill/doc_reader.py`

**Consumes:** 当前 `read(path) -> DocumentSections`、`_parse_sections(full_text, source_path)` 和现有 docx reader。

**Produces:** 附录 A1 的 `TextSpan`、`TopLevelBoundaryCandidate`、`SevenStepChapter`、`SevenStepRawExtraction` 与扩展 `DocumentSections`；显式七步读取始终附 raw 状态，默认读取仍不变。

- [ ] **Step 1: 在既有测试文件写出可收集的 RED tests。** 新增以下测试与文件内 helpers；测试先以 `import qda_prefill.doc_reader as reader` 导入现存模块，通过 `getattr(reader, "TopLevelBoundaryCandidate", None)` / `getattr(reader, "TextSpan", None)` 断言新合同类型存在，再构造候选，避免测试 collection 因未来类型不存在而 ImportError。
  - `test_default_read_keeps_legacy_sections_and_scene_checkbox`：用现有 `synthetic_docx` fixture/现有 `read()` 验证默认 `raw_seven_step is None`、旧 Dn sections 与 checkbox 结果不变。
  - `test_body_numbering_without_top_level_evidence_is_unresolved`：在合成 DOCX 中放入正文“一、二……”编号；显式 `template="七步法"`、空候选，断言 raw 为 unresolved 且没有 extracted/confirmed_blank 章。
  - `test_fixture_bound_seven_step_spans_match_hash_and_order`：构造七个 synthetic anchors，断言 token 原序、source hash、每个 title/body offset 切片及行号与 `full_text` 一致。
  - `test_confirmed_blank_requires_both_boundaries`：含空白正文的章节只有在标题与下一标题均有有效 anchor 时为 `confirmed_blank`；映射 `body_text == ""` 同时 body span 指向原始空白行/换行。
  - `test_missing_duplicate_out_of_order_and_mixed_candidates_fail_closed`：至少覆盖缺步、同 ordinal 重复、错序、七步与 Dn 顶层候选混杂；断言 unresolved、冲突锚保留且不存在静默补空。
  - `test_hash_mismatch_does_not_repair_locator`：断言不修补 hash/offset，结果 unresolved。
  - `test_docx_read_error_still_propagates`：复用 synthetic invalid DOCX，断言原读取异常传播，不返回空 raw。
- [ ] **Step 2: 运行 RED 并检查失败类型。** 从 QD-A 子项目根执行：

  ```powershell
  Set-Location "4-数字员工/质量部/QD-A-8D不良分析"
  & "C:/Dev/Codex/runtimes/zhuopin-ai/venv/Scripts/python.exe" -m pytest -q tests/test_doc_reader.py -k "default_read_keeps_legacy or body_numbering_without_top_level or fixture_bound_seven_step or confirmed_blank_requires or missing_duplicate_out_of_order or hash_mismatch or docx_read_error"
  ```

  Expected RED：测试收集成功，最先由缺少 raw 类型/API 的功能断言失败；若出现导入错误、fixture 导入错误或依赖问题，先修正测试本身（仍只在允许文件中），不可把收集失败记作 feature RED。
- [ ] **Step 3: 在 `doc_reader.py` 实现最小 raw 合同。** 将 dataclasses/types 放在现有 `DocumentSections` 前；在其末尾添加默认 `None` 字段。将 `read()` 扩展为附录签名：未声明七步仍原分支；声明时读取后对规范化 `full_text` 计算 SHA、验证 candidate hash、offset、行号及 title span 实际文本，再按严格一至七顺序生成章节。只在有效终止边界成立时切片；非空为 extracted，strip 后空仅作 `body_text=""` 并保留原 span；缺失标 unreliable、冲突标 ambiguous，文档 unresolved。读取错误继续抛出。不得改变 `_parse_sections`、Dn 标题、SceneCheckbox 或平台 parser。
- [ ] **Step 4: 运行 GREEN 与完整 QD-A 文件测试。** 重跑 Step 2 的选择测试，然后从同一子项目根运行完整 `tests/test_doc_reader.py`；两次均须通过。若 RED 由非功能问题造成，先更正测试并重新记录功能 RED，再实施。
- [ ] **Step 5: 做任务内静态核对。** 对比默认 `read(path)` 与显式模板两条分支；逐字段确认 SHA/offset/line 同源，审查文件 diff 未触碰白名单外文件；不运行额外静态扫描或 CI。

### Task 2: Q2 typed model 与 QD-A adapter

**Files:**
- Create: `4-数字员工/质量部/Q2-8D报告AI判定/tests/test_feed_source_seven_step.py`
- Modify: `4-数字员工/质量部/Q2-8D报告AI判定/q2_8d_verdict/models.py`
- Modify: `4-数字员工/质量部/Q2-8D报告AI判定/q2_8d_verdict/feed_source.py`

**Consumes:** Task 1 raw object；Q2 既有 `EightDInput` dataclass 与 `from_qda(report_id, sections, record, *, scene, template="标准8D", oem="")`。

**Produces:** Q2-local Protocol `SevenStepRawPayload`；`EightDInput.raw_seven_step` 末尾 optional 字段；adapter 的 optional keyword 透明传递。

- [ ] **Step 1: 新建 adapter tests 并先确认 API 缺口。** 用 `inspect.signature(from_qda)` 避免收集期导入不存在类型；先断言 signature 中存在 `raw_seven_step`，再用测试内 `SimpleNamespace` 组装一个具备全部 Protocol 属性的合成 raw payload。测试：
  - `test_from_qda_preserves_raw_status_and_legacy_metadata`：断言 output raw object identity 相同，`report_id/sections/scene/template/safety_related/safety_confidence/trace_fields/meta` 与原行为相同。
  - `test_from_qda_none_keeps_statusless_compatibility`：不传 raw 参数时字段为 None，旧位置参数/原关键字调用仍可工作。
  - `test_raw_payload_is_not_folded_into_existing_sections`：raw 正文仅留在 raw 对象，`sections == dict(input_sections)`，不改造 Dn sections。
- [ ] **Step 2: 运行 RED。** 从 Q2 子项目根执行：

  ```powershell
  Set-Location "4-数字员工/质量部/Q2-8D报告AI判定"
  & "C:/Dev/Codex/runtimes/zhuopin-ai/venv/Scripts/python.exe" -m pytest -q tests/test_feed_source_seven_step.py
  ```

  Expected RED：pytest 收集成功，`inspect.signature` 的字段断言失败；不得把文件未创建、import error 或测试语法错误当成功 RED。
- [ ] **Step 3: 最小 GREEN 修改模型与 adapter。** 在 `models.py` 用 `Protocol` + `Literal` 明确原附录所需 span/candidate/chapter/raw 字段结构；不得 `import qda_prefill`。在现有 `EightDInput` 最后追加 `raw_seven_step: SevenStepRawPayload | None = None`。在 `feed_source.from_qda` 末尾追加 keyword-only optional 参数并原样传给 `EightDInput`；不改变 `record`、OEM、confidence、安全字段、meta 现有构造。
- [ ] **Step 4: 运行 GREEN。** 执行 Step 2 命令并确认三项 adapter assertions 通过；继而运行现有 `tests/test_engine_mock.py` 确认仅新增默认字段没有破坏旧构造（engine 路由仍由 Task 3 实现）。
- [ ] **Step 5: 做任务内兼容核对。** 检视所有现有 `EightDInput` positional/keyword 字段声明和 adapter 返回构造仅在这七路径内；确认 raw None 是默认并且 Protocol 不引入 QD-A 运行时依赖。

### Task 3: Q2 前置人工分流、J10 raw 映射与审计投影

**Files:**
- Modify: `4-数字员工/质量部/Q2-8D报告AI判定/tests/test_engine_mock.py`
- Modify: `4-数字员工/质量部/Q2-8D报告AI判定/q2_8d_verdict/engine.py`

**Consumes:** Task 2 的 `EightDInput.raw_seven_step`；Q2 现有 ASIL guard、J10、结构闸、`Verdict`、`Disposition.MANUAL` 与 `_audit`。

**Produces:** ASIL 后 unresolved MANUAL 闸；reliable raw chapters 通过唯一现有 J10 映射归一化；必要且脱敏的状态/hash/locator audit 字段。

- [ ] **Step 1: 在现有 engine tests 加入 RED cases。** 使用 mock raw payload 与 `ruleset` fixture，不新增真实样本或 fixture 文件。
  - `test_asil_cd_guard_precedes_unresolved_raw`：ASIL C/D + unresolved raw 仍抛 `AsilExcludedError`，并用 monkeypatch 断言 normalize 未调用。
  - `test_unresolved_raw_routes_manual_before_structure_and_score`：合法 scene + unresolved raw；monkeypatch `normalize_sections`/`score_rules` 为调用即失败，断言返回 `Disposition.MANUAL`、`grade is None`、无结构退回、无 redlines/rules、score 为 0、人工/L2 字段保持。
  - `test_reliable_raw_uses_j10_and_preserves_two_four_d4_order`：构造完整七章；断言归一化 D4 精确等于 `"二的合成正文\n四的合成正文"`，其它 step 目标逐项与当前 J10 runtime 值一致，raw 章节/locator 仍分别存在。
  - `test_confirmed_blank_uses_existing_normalized_structure_gate`：二为空、四非空时 D4 保持非空，不能对单章空白触发新的结构退回；二、四都空时只由既有 D4 gate 报空。
  - `test_statusless_and_dn_short_title_paths_are_unchanged`：旧 statusless 与标准 Dn 输入对比既有 mock 期望及 SceneCheckbox 不变。
  - `test_unresolved_audit_projects_state_without_chapter_text`：挂接现有 `AuditLogger(JsonlSink(tmp_path/...))`，断言 audit decision/data_source 可定位 raw 模板/状态/hash/locator 摘要，且序列化行不含任何 synthetic body sentinel。
- [ ] **Step 2: 运行 RED。** 从 Q2 子项目根执行：

  ```powershell
  Set-Location "4-数字员工/质量部/Q2-8D报告AI判定"
  & "C:/Dev/Codex/runtimes/zhuopin-ai/venv/Scripts/python.exe" -m pytest -q tests/test_engine_mock.py -k "asil_cd_guard_precedes_unresolved or unresolved_raw_routes_manual or reliable_raw_uses_j10 or confirmed_blank_uses_existing or statusless_and_dn_short_title or unresolved_audit_projects"
  ```

  Expected RED：测试收集成功，尚无 raw engine seam 导致针对行为的 assertion failure；若是 constructor/import/setup failure，先修测试输入，不记录为功能 RED。
- [ ] **Step 3: 实现最小 engine 改动。** 保留 `evaluate()` 的 ASIL C/D guard 第一位；针对 `template == "七步法"` 且 raw 对象存在，紧接其后处理 unresolved 并构造既有 `Verdict` 的中性无分数 MANUAL（无 structural return、redlines、rules、grade；`grade_range=(config.GRADE_D, config.GRADE_A)`，L2/manual defaults 原样）。任何状态不为 reliable、章节 token/数量/顺序不满足七步合同、或章状态不是 extracted/confirmed_blank 的 payload 都 fail closed 到相同 MANUAL；不得只因 Protocol 注解而信任运行时不合约对象。必须在 normalize、结构闸、红线、score 之前返回，并仍走既有 `_audit`。reliable raw 的章节序列由 `normalize_sections` 遍历，step token 仅作现有 J10 key；将非空 `body_text.strip()` 按现有 Dn 归一化惯例 append，raw 对象保留原始精确切片及 locator；空章映射空字符串，不复制映射。`raw_seven_step is None` 保持旧输入分支。audit 只增加附录允许的模板、状态、hash 与 locator 摘要，严禁 body_text。
- [ ] **Step 4: 运行 GREEN 与 Q2 全目标测试。** 重跑 Step 2 选择测试；再运行 Task 2 adapter 文件与完整 `tests/test_engine_mock.py`。随后执行附录固定命令：

  ```powershell
  & "C:/Dev/Codex/runtimes/zhuopin-ai/venv/Scripts/python.exe" -m pytest -q tests/test_feed_source_seven_step.py tests/test_engine_mock.py
  ```

  所有命令工作目录均为 Q2 子项目根；预期全通过，现有 mock goldens 与 L2/Safety/ASIL tests 不变。
- [ ] **Step 5: 做任务内边界核对。** 审查 audit JSONL 不含 raw body、客户/OEM 文本；确认 `config.py` 与专业规则不变、二/四来源不合并覆盖；检查 diff 仅含列定的七文件。

## Future Verification Commands

实施授权生效后，最终各项目测试命令从对应子项目根运行；本计划撰写阶段没有执行：

```powershell
Set-Location "4-数字员工/质量部/QD-A-8D不良分析"
& "C:/Dev/Codex/runtimes/zhuopin-ai/venv/Scripts/python.exe" -m pytest -q tests/test_doc_reader.py

Set-Location "4-数字员工/质量部/Q2-8D报告AI判定"
& "C:/Dev/Codex/runtimes/zhuopin-ai/venv/Scripts/python.exe" -m pytest -q tests/test_feed_source_seven_step.py tests/test_engine_mock.py
```

## 完工审查条件

- 所有 raw 状态、顺序、source hash、offset、line locator 均由合成 fixture 覆盖；没有 OCR/LLM 或真实文档正向支持承诺。
- 旧 `read(path)`、Dn/短标题、`DocumentSections.sections`、`SceneCheckbox`、statusless `from_qda` 与 Q2 现有 mock 行为维持。
- ASIL C/D 永远优先硬退出；unresolved 七步不进入结构判定或评分；reliable 七步只通过现有 J10 映射，二/四按序累加 D4；audit 仅投影脱敏元数据。
- 测试在两个项目分别通过，且实现 diff 不超七路径；这仅构成授权范围内实现验收，不代表真实客户输入可用、MVP 发布或生产部署。
