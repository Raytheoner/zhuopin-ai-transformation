# Q2 离线语义来源实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use `subagent-driven-development` or `executing-plans` to implement this plan task-by-task. Steps use checkbox syntax for tracking. Future Guardian execution must explicitly use `gpt-6-luna`. 派生模型不得 commit/push；由 outer 会话复核并封存。本计划不是实现授权。

**Goal:** 在 Q2 场景目录新增四个离线语义模块及四个聚焦测试模块，使用合成 fixture 和固定 mock 响应形成可追溯、fail-closed 的实验候选与校准结果，不改变线上语义来源。

**Architecture:** 新合同层负责版本化、规则身份、客户隔离、证据定位及双置信校验；离线 source 和校准 runner 只依赖该合同与显式传入的 mock。审计/签认层复用现有 `AuditEvent`、`AuditLogger` 和 Q2 的真实 PENDING 读取路径，先写入并回读验链后才返回可消费输出；不接入 `engine.py`、Web、上传或真实模型。

**Tech Stack:** Python 3.14 隔离环境；dataclasses、enum、hashlib、pytest；`zhuopin_platform.audit.AuditEvent` / `AuditLogger`；Q2 的 `rules_loader.load()` 与实际 `RuleSet`。

**Spec:** [proposal.md](C:/Dev/zhuopin-ai/reports/pc-mvp-1012/v2-review/q2/proposal.md)、[design.md](C:/Dev/zhuopin-ai/reports/pc-mvp-1012/v2-review/q2/design.md)、[tasks.md](C:/Dev/zhuopin-ai/reports/pc-mvp-1012/v2-review/q2/tasks.md)、[spec.md](C:/Dev/zhuopin-ai/reports/pc-mvp-1012/v2-review/q2/specs/q2-semantic-offline-source/spec.md)。获批 Q2 design HEAD=`31270c3dc9ff165eec85553f0e26df6ca8b26b5b`，SHA256=`8fbb2dcc1094f58886c47b7fce12f77b0af0a83cfb1b9638a2450ae1ab86c909`；本计划约束绑定该版本，实施前必须由 outer 会话核实白名单与授权。

## Global Constraints

- 执行目录固定为 `C:/Users/Paul Shao/.codex/worktrees/pc-mvp-1012-v2-q2/zhuopin-ai`；项目根固定为 `C:/Users/Paul Shao/.codex/worktrees/pc-mvp-1012-v2-q2/zhuopin-ai/4-数字员工/质量部/Q2-8D报告AI判定`。
- Python 固定为 `C:/Dev/Codex/runtimes/zhuopin-ai/venv/Scripts/python.exe`；PowerShell 调用形式为 `& 'C:/Dev/Codex/runtimes/zhuopin-ai/venv/Scripts/python.exe' -m pytest`，每个含空格路径均加引号。
- 仅新增八个文件，完整路径在下一条列出；除此之外不改 UI、上传、engine、规则正本/覆盖层、`config.PENDING`、门户、QD-A、旧校准脚本、依赖/配置、文档或共享平台文件。
- 唯一文件白名单（共 8 个）：`C:/Users/Paul Shao/.codex/worktrees/pc-mvp-1012-v2-q2/zhuopin-ai/4-数字员工/质量部/Q2-8D报告AI判定/q2_8d_verdict/semantic_offline_contract.py`、`C:/Users/Paul Shao/.codex/worktrees/pc-mvp-1012-v2-q2/zhuopin-ai/4-数字员工/质量部/Q2-8D报告AI判定/q2_8d_verdict/semantic_offline_source.py`、`C:/Users/Paul Shao/.codex/worktrees/pc-mvp-1012-v2-q2/zhuopin-ai/4-数字员工/质量部/Q2-8D报告AI判定/q2_8d_verdict/semantic_offline_calibration.py`、`C:/Users/Paul Shao/.codex/worktrees/pc-mvp-1012-v2-q2/zhuopin-ai/4-数字员工/质量部/Q2-8D报告AI判定/q2_8d_verdict/semantic_offline_signoff.py`、`C:/Users/Paul Shao/.codex/worktrees/pc-mvp-1012-v2-q2/zhuopin-ai/4-数字员工/质量部/Q2-8D报告AI判定/tests/test_semantic_offline_contract.py`、`C:/Users/Paul Shao/.codex/worktrees/pc-mvp-1012-v2-q2/zhuopin-ai/4-数字员工/质量部/Q2-8D报告AI判定/tests/test_semantic_offline_source.py`、`C:/Users/Paul Shao/.codex/worktrees/pc-mvp-1012-v2-q2/zhuopin-ai/4-数字员工/质量部/Q2-8D报告AI判定/tests/test_semantic_offline_calibration.py`、`C:/Users/Paul Shao/.codex/worktrees/pc-mvp-1012-v2-q2/zhuopin-ai/4-数字员工/质量部/Q2-8D报告AI判定/tests/test_semantic_offline_signoff.py`。除此之外不改 UI、上传、engine、规则正本/覆盖层、`config.PENDING`、门户、QD-A、旧校准脚本、依赖/配置、文档或共享平台文件。
- 实施启动前只读读取实际规则集 `rules_loader.load()` 返回的 `RuleSet`，并从其 `rules`/`redlines` 及版本/hash 建立实验合同；不得抄写或硬编码规则数量。24/25 字面差异不触发规则变更。
- 已只读枚举 Q2 场景目录中的 Python 源码和文件名：当前场景包没有旧校准脚本、`CalibrationCase`/`CalibrationResult` 类型或校准输出 schema。故本计划不定义、不实现 legacy adapter；`CalibrationCase` 只由合成 fixture 显式构造。若未来发现外部旧校准产物，须另行设计与授权，不能假装本计划已确认其 schema，也不读取真实十样本。
- 实际规则集合由现有 `rules_loader.load()` 构造：`RuleSet.rules` 使用 `Rule.is_semantic`（`judge_method` 含 `config.SEMANTIC_MARKERS=('语义','LLM')`），`RuleSet.redlines` 中仍完整保留红线1–6；V3.2 JSON SHA256 与 `config.RULES_JSON_SHA256` 校验，已签覆盖层在筛选前生效。静态逐项核对 loader、config 和 JSON 得到24个 semantic rule IDs：`D2-05`、`D2-06`、`D2-07`、`D2-08`、`D3-01`、`D3-04`、`D3-05`、`D4-03`、`D4-04`、`D4-05`、`D4-06`、`D4-M2`、`D4-R1`、`D4-R2`、`D4-R3`、`D5-01`、`D5-02`、`D5-03`、`D5-M1`、`D5-R1`、`D5-R2`、`D6-01`、`D6-02`、`D6-M1`；semantic redline IDs 是 `1`、`2`、`5`。已签M18将`D7-M3`、`D2-R3`、`D6-R1`降为关键词，并将红线③改为规则引擎，因此不属于运行时semantic集合。RuleSetSnapshot须分别保存所有redline IDs `frozenset({1,2,3,4,5,6})` 与semantic redline IDs `frozenset({1,2,5})`；语义观察只允许后者，校准输入可将实际红线2/3类型化标为待人工排除。实现和测试以`rules_loader.load()`对象为唯一合同，列表仅为核对基准，不硬编码平行规则，也不按24/25字面差异推断。
- `None` 必须不同于数值 `0`；语义置信与证据抽取置信独立。缺失、越界、解析失败、无证据、无定位、未知安全属性都不得被补值、提升为确认或形成等级。
- 候选状态只允许实验态；候选不是 `HumanVerdictSource`，模型候选不能产生 `TRIGGERED`。红线②③排除验收并转人工；安全属性 True/None/非 HIGH 转人工，ASIL C/D 退出 AI 路径。
- 不处理真实 8D/OEM 数据；不得跨客户复用。审计仅保存 opaque ID、hash、版本及定位摘要，不保存原文、客户明文、证据摘录或凭据。OEM 上下文只允许受控隔离标识，具体字段值不得落入通用审计。
- 复用可读同字节审计副本 `reports/pc-mvp-1012/v2-review/technical-sources/2-events.py.txt` 与 `3-logger.py.txt` 的接口：`AuditEvent.decision: dict[str, Any]`、`data_sources: dict[str, str]`，`automation_level` 字段为正式档位字符串；离线 mock 批次事件用 `automation_level='L1'`、`evaluator='MOCK'`。L2 人工 override 只接受调用方显式提供的真实 evaluator 并记 `L2`；不把 mock 伪装成专业签认。`record(event) -> None`，之后只按顶层字段调用 `query_by(**filters)` 并检查 `verify_chain().ok`。不得使用 string 类型 decision。写审、回读及验链成功前不可返回可消费报告；任一步失败即抛明确审计失败异常。平台方法可在 pytest 中用 `monkeypatch` 替换实例方法验证失败关闭，不改平台 API。
- 真实 PENDING 读取路径已由 Q2 `config.py`、`tests/test_engine_mock.py::test_signoffs_are_named_and_pending_fails_loud` 核定：`config.PENDING.value_of('SEMANTIC_LAYER_ACCEPTANCE')` 抛 `zhuopin_platform.criteria_signoff.CriterionNotSignedOffError`；同一测试也核实 `MEASURE_VERIFIABILITY_STANDARD` 抛同类异常。实现必须原样传播该异常，gate 不读取 MEASURE 项，不修改 PENDING。
- 不接真实模型、线上 source、`engine.py`、UI、上传、服务端点；不运行产品测试、真实校准或模型调用。未来逐项目验证仅从 Q2 项目根调用上述隔离解释器；不在仓库根混跑。
- 外层 Guardian 要显式 Luna；子代理不 commit/push；本计划及此前批准的 design 均不代表实现、design 审核、合入、部署或线上启用授权。

## Review Focus

1. **unknown 与 0、双置信值和显式实验等级混淆**：`test_semantic_offline_contract.py::test_none_confidence_stays_unknown_and_zero_is_preserved_with_declared_grade`、`test_confidence_values_and_grades_remain_independent` 覆盖。
2. **输入/客户/规则版本、类型化 rule/redline 身份或证据定位不匹配**：`test_semantic_offline_contract.py::test_rejects_context_digest_and_ruleset_mismatch`、`test_rejects_rule_id_as_redline_and_redline_no_as_rule`、`test_missing_evidence_locator_is_invalid_not_confirmed` 覆盖。
3. **实验候选被误当人工确认或触发红线②③**：`test_semantic_offline_source.py::test_candidate_never_becomes_human_verdict_or_triggered`、`test_redline_two_is_manual_and_three_is_not_semantic_source` 覆盖。
4. **审计写入、回读或 hash-chain 验证失败仍泄出报告，或 override 覆盖旧事件**：`test_semantic_offline_signoff.py::test_audit_failure_returns_no_consumable_output`、`test_override_appends_and_preserves_candidate_event` 覆盖。
5. **PENDING、安全属性及 ASIL 路由被实验结果绕过**：`test_semantic_offline_signoff.py::test_pending_acceptance_propagates_real_pending_exception`、`test_unknown_safety_routes_to_review_and_asil_cd_exits` 覆盖。

---

### Task 1: 定义离线候选合同与 fail-closed 校验

**Files:**
- Create: `C:/Users/Paul Shao/.codex/worktrees/pc-mvp-1012-v2-q2/zhuopin-ai/4-数字员工/质量部/Q2-8D报告AI判定/q2_8d_verdict/semantic_offline_contract.py`
- Test: `C:/Users/Paul Shao/.codex/worktrees/pc-mvp-1012-v2-q2/zhuopin-ai/4-数字员工/质量部/Q2-8D报告AI判定/tests/test_semantic_offline_contract.py`

**实施前置：**使用现有 `ruleset` pytest fixture（`tests/conftest.py` 调用 `rules_loader.load()`）核对运行时 `RuleSet` 与 Global Constraints 所列静态投影基准一致；此处计划只读核验，不在本会话运行测试。旧校准脚本/schema 已核定不存在于当前 Q2 包源码和文件名中，故不定义 adapter，也不阻断合同实现。禁止扫描私有 runtime/state。

**Interfaces:**
- `ConfidenceValue = float | None`；`ConfidenceGrade(str, Enum)` 值为 `HIGH`、`LOW`、`UNKNOWN`，版本固定为 `confidence_grade_version: Literal['q2-experiment-confidence-v1']`。HIGH/LOW/UNKNOWN 是 fixture/mock 显式声明的实验分类，source 原样携带，禁止由数值置信、阈值或未签专业口径计算；两个 numeric confidence 与两个 grade 都独立保存。任一数值为 None、任一 grade 为 LOW/UNKNOWN 均进入人工复核。
- `ObservationSubjectKind(str, Enum)` 值为 `RULE`、`REDLINE`；`CandidateState(str, Enum)` 值为 `CANDIDATE`、`UNKNOWN`、`INVALID`、`NOT_EVALUATED`、`SUSPECTED`、`REVIEW_REQUIRED`。
- `EvidenceLocator` frozen dataclass 字段：`step: str`、`location_key: str`、`source_hash: str`。禁止 `excerpt`/原文字段。
- `RuleSetSnapshot` frozen dataclass 字段：`rule_ids: frozenset[str]`（semantic rules）、`redline_ids: frozenset[int]`（所有实际红线1–6）、`semantic_redline_ids: frozenset[int]`（只含`RuleSet`中`Redline.is_semantic`为真的IDs）、`source_version: str`、`sha256: str`。classmethod `RuleSetSnapshot.from_ruleset(ruleset: RuleSet) -> RuleSetSnapshot`分别投影完整红线ID与语义红线ID。测试核对24条semantic rules、全红线`{1,2,3,4,5,6}`及semantic redlines `{1,2,5}`，实现不得另建规则表。
- `SemanticObservation` frozen dataclass 字段：`subject_kind: ObservationSubjectKind`、`rule_id: str | None`、`redline_no: int | None`、`candidate_ratio: float | None`、`semantic_confidence: ConfidenceValue`、`extraction_confidence: ConfidenceValue`、`semantic_confidence_grade: ConfidenceGrade`、`extraction_confidence_grade: ConfidenceGrade`、`state: CandidateState`、`evidence: EvidenceLocator | None`、`source: Literal['MOCK']`、`review_reason: str | None = None`。RULE 必须只填rule_id且属于`rule_ids`；REDLINE必须只填int redline_no且属于`semantic_redline_ids`；redline不允许candidate_ratio。不得string/int互换，不含人工确认/自动等级字段。
- `SemanticCandidateEnvelope` frozen dataclass 字段：`schema_version: str`、`candidate_id: str`、`batch_id: str`、`created_at: str`、`input_sha256: str`、`report_token: str`、`oem_context_id: str`、`ruleset: RuleSetSnapshot`、`model_id: str`、`model_version: str`、`prompt_version: str`、`confidence_grade_version: Literal['q2-experiment-confidence-v1']`、`observations: tuple[SemanticObservation, ...]`、`offline_only: Literal[True]`。
- `validate_envelope(envelope: SemanticCandidateEnvelope, *, expected_input_sha256: str, expected_oem_context_id: str, expected_ruleset: RuleSetSnapshot) -> SemanticCandidateEnvelope`：不一致时抛 `ValueError`；版本缺失/unsupported、未知subject-kind/typed ID配对、RULE ID不在`rule_ids`、REDLINE int不在`semantic_redline_ids`、非离线标志、非`MOCK` source、无evidence或hash/租户不匹配均拒绝；数值置信/ratio只接受有限`[0.0,1.0]`，None保留unknown，0.0有效；grade只接受ConfidenceGrade且版本固定为`q2-experiment-confidence-v1`。RULE的ratio=None、无evidence或confidence grade任一非双HIGH必须为非候选状态；REDLINE ratio必须None且永不trigger。

- [ ] **Step 1: 写失败测试与完整合成 fixtures**：纯合同fixture构造两个Rule及六条Redline；每条Redline含`redline_no=i, step='D4', description='synthetic redline', judge_method=('LLM语义' if i in (1,2,5) else '规则引擎'), logic='synthetic logic'`；真实规则映射测试另用既有`ruleset` fixture。输入固定`synthetic-only: D3 contains placeholder evidence`并计算SHA；上下文为`tenant-fixture-a`、report token `report-fixture-001`、合同版`fixture-v3`、规则hash 64个`a`、grade version=`q2-experiment-confidence-v1`。真实fixture投影断言24条rule IDs、全红线`{1,2,3,4,5,6}`、semantic红线`{1,2,5}`。测试验证不支持schema、摘要/租户不匹配、RULE/redline身份交叉、REDLINE ID为字符串`'2'`或超出实际集合均拒绝；缺证据、ratio及两个numeric置信越界拒绝；grade `UNKNOWN`仍unknown，numeric 0.0原样保留、HIGH须mock显式声明且不得从数值推导；两数值与两grade独立。测试不含真实规则文本。
- [ ] **Step 2: 建 importable scaffold 并确认行为 RED**：在同一新模块写好全部 enums/dataclass/signature 壳；`from_ruleset` 临时返回空 snapshot，`validate_envelope` 临时原样返回输入。随后从 Q2 项目根运行 `& 'C:/Dev/Codex/runtimes/zhuopin-ai/venv/Scripts/python.exe' -m pytest 'tests/test_semantic_offline_contract.py' -q`；必须成功 import/collect，且失败断言明确指出应有semantic IDs/应拒绝非法类型或应保留grade，而不是模块缺失或collection错误。
- [ ] **Step 3: 实现上述 frozen dataclasses、枚举、RuleSet 投影及校验**：仅实现列出的合同接口；不导入 engine/UI/source，不把业务门限写入合同；验证输入只接 digest，不接原文。
- [ ] **Step 4: 重跑合同测试**：同 Step 2 命令；预期所有合同边界测试通过，且序列化/对象结构中不存在 `excerpt`、原文或客户明文字段。
- [ ] **Step 5: 提交本任务文件给 outer review，不执行 git commit**：由 outer 检查 diff 是否仅本任务两文件，再决定后续；派生执行者不得 commit/push。

### Task 2: 实现仅离线可调用的 SemanticSource

**Files:**
- Create: `C:/Users/Paul Shao/.codex/worktrees/pc-mvp-1012-v2-q2/zhuopin-ai/4-数字员工/质量部/Q2-8D报告AI判定/q2_8d_verdict/semantic_offline_source.py`
- Test: `C:/Users/Paul Shao/.codex/worktrees/pc-mvp-1012-v2-q2/zhuopin-ai/4-数字员工/质量部/Q2-8D报告AI判定/tests/test_semantic_offline_source.py`

**Interfaces:**
- `OfflineExperimentContext` frozen dataclass：`batch_id: str`、`input_sha256: str`、`oem_context_id: str`、`ruleset: RuleSetSnapshot`、`model_id: str`、`model_version: str`、`prompt_version: str`、`confidence_grade_version: Literal['q2-experiment-confidence-v1']`；所有字段非空。每个 context 只绑定一份输入摘要，供一个 case/report 使用。
- `MockSemanticResponse` frozen dataclass：`subject_kind: ObservationSubjectKind`、`rule_id: str | None`、`redline_no: int | None`、`candidate_ratio: float | None`、`semantic_confidence: ConfidenceValue`、`extraction_confidence: ConfidenceValue`、`semantic_confidence_grade: ConfidenceGrade`、`extraction_confidence_grade: ConfidenceGrade`、`evidence: EvidenceLocator | None`、`source: Literal['MOCK']`。grade必须在显式fixture中给出，不由source根据numeric value推断。
- `OfflineSemanticSource(context: OfflineExperimentContext, responses: Mapping[tuple[ObservationSubjectKind, str | int], MockSemanticResponse])`；mapping key必须为 `(RULE, rule_id:str)` 或 `(REDLINE, redline_no:int)`，不可string/int交叉；初始化拒绝非`MOCK`来源、未知对应ID、重复key及key/response身份不匹配。无网络/模型客户端参数。
- `evaluate(*, report_token: str, created_at: str) -> SemanticCandidateEnvelope`：按RuleSet semantic rule IDs与semantic redline IDs分别生成typed observations；红线③不是当前semantic redline ID，必须拒绝其source response。红线②只可 `NOT_EVALUATED` + `REVIEW_REQUIRED`，不入验收、不生成触发状态；红线③只在CalibrationCase层按既定规则排除验收，不能混入候选。RULE的ratio为None、无response/evidence、任一置信数值为None、任一显式grade为LOW/UNKNOWN均转人工；只有证据、ratio、两个numeric置信值均有效且两个grade显式HIGH时，rule产生 `CANDIDATE`。不得在本计划定义ratio阈值，candidate state只记录离线候选。redline observation无ratio，永不产生TRIGGERED。返回对象经Task1 `validate_envelope`校验，永不实现 `HumanVerdictSource`。

- [ ] **Step 1: 写 source 测试与固定 mock fixtures**：输入两条synthetic semantic rules `D2-05`/`D2-06` 与typed REDLINE no.2响应；全部confidence grade/version显式固定，grade版本`q2-experiment-confidence-v1`，无数字阈值推导。断言Rule/Redline observation身份字段只填对应类型；②为`NOT_EVALUATED`/`REVIEW_REQUIRED`且无ratio；source拒绝redline_no=3（它是合法全红线ID但不属于semantic_redline_ids），由Task3校准case处理③排除；missing response、missing evidence、ratio None、数值置信None、任一grade LOW/UNKNOWN转人工；数值0.0与显式HIGH保留原值且不被重分类；Rule ID未知拒绝；candidate不属于`HumanVerdictSource`且没有`TRIGGERED`；AST检查新模块无`engine`/`HumanVerdictSource`导入、无`config.PENDING`写入。
- [ ] **Step 2: 建 importable source scaffold 并确认行为 RED**：在白名单新模块先定义完整类型/构造器/evaluate签名；`evaluate` 暂时返回缺少观察项的空 envelope。运行 `& 'C:/Dev/Codex/runtimes/zhuopin-ai/venv/Scripts/python.exe' -m pytest 'tests/test_semantic_offline_source.py' -q`；必须成功import/collect，失败点是候选观察未生成/typed红线与grade行为断言，不得把ImportError当RED。
- [ ] **Step 3: 实现离线 context、纯数据 mock response 与 evaluate**：只遍历 context 规则 ID；不调用模型，不从环境变量读取数据源，不导入在线 engine。固定拒绝 response 外部输入中的原文型字段；只保留 digest/token/locator。
- [ ] **Step 4: 运行合同与 source 聚焦测试**：`& 'C:/Dev/Codex/runtimes/zhuopin-ai/venv/Scripts/python.exe' -m pytest 'tests/test_semantic_offline_contract.py' 'tests/test_semantic_offline_source.py' -q`；预期均通过。
- [ ] **Step 5: outer review**：确认产品代码仍只有白名单文件变化，不 commit/push。

### Task 3: 实现合成样本校准 runner

**Files:**
- Create: `C:/Users/Paul Shao/.codex/worktrees/pc-mvp-1012-v2-q2/zhuopin-ai/4-数字员工/质量部/Q2-8D报告AI判定/q2_8d_verdict/semantic_offline_calibration.py`
- Test: `C:/Users/Paul Shao/.codex/worktrees/pc-mvp-1012-v2-q2/zhuopin-ai/4-数字员工/质量部/Q2-8D报告AI判定/tests/test_semantic_offline_calibration.py`

**Interfaces:**
- `CalibrationCase` frozen dataclass：`case_id: str`、`input_sha256: str`、`oem_context_id: str`、`subject_kind: ObservationSubjectKind`、`rule_id: str | None`、`redline_no: int | None`、`expected_ratio: float | None`、`semantic_confidence_grade: ConfidenceGrade`、`extraction_confidence_grade: ConfidenceGrade`、`safety_related: bool | None`、`asil_level: str | None`、`sample_number: int | None`、`scene_tag: Literal['制造','研发','通用'] | None`、`trace_tag: str | None`、`synthetic: Literal[True]`。subject_kind/typed ID遵循合同：RULE只填string rule_id，REDLINE只填int redline_no；rule case必须将redline_no和追溯字段设None，redline case必须将rule_id/expected_ratio设None。`redline_no`合法性校验对照全部`RuleSetSnapshot.redline_ids`（实际1–6），但只在Case层保存2/3排除记录；二者confidence grades置`UNKNOWN`，无candidate response。对已知样本3使用synthetic case `sample_number=3, scene_tag='制造', trace_tag='Q2-G-03'`，其余两个追溯字段为None。
- `CalibrationItem` frozen dataclass：`case_id: str`、`input_sha256: str`、`candidate_id: str | None`、`subject_kind: ObservationSubjectKind`、`rule_id: str | None`、`redline_no: int | None`、`candidate_ratio: float | None`、`semantic_confidence: ConfidenceValue`、`extraction_confidence: ConfidenceValue`、`semantic_confidence_grade: ConfidenceGrade`、`extraction_confidence_grade: ConfidenceGrade`、`sample_number: int | None`、`scene_tag: Literal['制造','研发','通用'] | None`、`trace_tag: str | None`、`state: CandidateState`、`review_reason: str | None`、`excluded_from_metrics: bool`。复制Case的input_sha256及sample_number/scene_tag/trace_tag至每个item，确保来源摘要及样本3可审计单列。
- `CalibrationReport` frozen dataclass：`status: Literal['EXPERIMENTAL_ONLY']`、`batch_id: str`、`oem_context_id: str`、`input_sha256s: tuple[str, ...]`、`ruleset_sha256: str`、`model_id: str`、`model_version: str`、`prompt_version: str`、`confidence_grade_version: Literal['q2-experiment-confidence-v1']`、`items: tuple[CalibrationItem, ...]`、`synthetic_case_count: int`、`positive_count: int`、`negative_count: int`、`agreement_rate: float | None`、`redline_false_positive_rate: float | None`、`pending_review_count: int`。一个batch只允许单一tenant、RuleSet version/hash、batch/model/prompt/confidence-grade version；`input_sha256s`按case去重排序，但每item保留自己的原input digest与trace fields。
- `OfflineCalibrationRunner(source_factory: Callable[[CalibrationCase], OfflineSemanticSource], *, expected_oem_context_id: str, expected_ruleset: RuleSetSnapshot)`；私有 `_build_report(cases: Sequence[CalibrationCase], *, created_at: str) -> CalibrationReport` 对每个RULE case调用一次factory，要求返回source.context的`input_sha256 == case.input_sha256`、tenant及RuleSet version/hash与expected快照一致，响应中的两个grade与case显式grade声明一致，且全batch共用相同batch/model/prompt/confidence-grade版本。factory是按`case_id`显式提供的`Mapping[str, OfflineSemanticSource]`闭包；每case一个source和固定mock responses，不共用单digest context。任一非合成、错误subject-ID类型、digest/context不匹配、重复case ID或缺失source均拒绝。REDLINE no.2/3须属于全redline_ids，先标记`NOT_EVALUATED`/`REVIEW_REQUIRED`、exclude metric，不调用semantic source；安全属性None/True/非HIGH或任一显式confidence grade LOW/UNKNOWN转人工，ASIL C/D退出。此私有builder仅用于纯合成指标单测，不是消费接口。V1/V2只报告实验数值，不生成通过布尔值/签认；V3记固定版本，V4低等级转人工，V5沿用既有闸，不生成新阈值。当前Q2源码中没有旧校准脚本或结果类型，故无adapter。

- [ ] **Step 1: 写校准 fixtures 与测试**：以10个合成case（5正/5反）固定版本。case IDs为`syn-case-01`至`syn-case-10`；每个digest用 `hashlib.sha256(f'synthetic-q2-case-{i:02d}'.encode()).hexdigest()`（i=1..10）生成，统一tenant `tenant-fixture-a`，subject为RULE/rule_id=`D2-05`（从fixture `ruleset`验证存在），redline_no=None、synthetic=True；前5个expected_ratio=1.0，后5个=0.0。numeric confidence固定0.0/0.8，显式grades为HIGH/HIGH且grade version=`q2-experiment-confidence-v1`；source不得由0.0推算LOW，候选保留显式grade。另为case 3设置`sample_number=3, scene_tag='制造', trace_tag='Q2-G-03'`；断言输出`CalibrationItem`保留这些字段和对应case digest。source factory fixture以`dict[case_id, OfflineSemanticSource]`建10个source，每个context绑定其case独立input digest；全部共用`batch-fixture-001`、tenant、RuleSet snapshot/version/hash及`fixed-mock/model-v1/prompt-v1/q2-experiment-confidence-v1`；responses的typed subject身份、两个numeric confidence与两grade和对应case一致。额外建typed REDLINE no.2/3 cases（`rule_id=None`、`expected_ratio=None`），二者不调用factory、不入验收分母并转人工；分别增加grade LOW、grade UNKNOWN、numeric None、missing evidence、safety_related None/True/False、ASIL C/D、tenant错、digest/source.context错、RuleSet SHA错、重复case_id用例；断言LOW/UNKNOWN/None均转人工、错误绑定拒绝。报告标`EXPERIMENTAL_ONLY`且无pass/signoff字段，不读取真实校准/客户报告。

```python
import hashlib
from q2_8d_verdict.semantic_offline_contract import ConfidenceGrade, EvidenceLocator, ObservationSubjectKind, RuleSetSnapshot
from q2_8d_verdict.semantic_offline_source import MockSemanticResponse, OfflineExperimentContext, OfflineSemanticSource
from q2_8d_verdict.semantic_offline_calibration import CalibrationCase, OfflineCalibrationRunner

rule_snapshot = RuleSetSnapshot.from_ruleset(ruleset)  # ruleset is the existing conftest fixture
cases = tuple(
    CalibrationCase(
        case_id=f"syn-case-{i:02d}",
        input_sha256=hashlib.sha256(f"synthetic-q2-case-{i:02d}".encode()).hexdigest(),
        oem_context_id="tenant-fixture-a", subject_kind=ObservationSubjectKind.RULE,
        rule_id="D2-05", redline_no=None, expected_ratio=1.0 if i <= 5 else 0.0,
        semantic_confidence_grade=ConfidenceGrade.HIGH,
        extraction_confidence_grade=ConfidenceGrade.HIGH,
        safety_related=False, asil_level="B",
        sample_number=3 if i == 3 else None,
        scene_tag="制造" if i == 3 else None,
        trace_tag="Q2-G-03" if i == 3 else None, synthetic=True,
    )
    for i in range(1, 11)
)
source_by_case: dict[str, OfflineSemanticSource] = {}
for case in cases:
    ctx = OfflineExperimentContext(
        batch_id="batch-fixture-001", input_sha256=case.input_sha256,
        oem_context_id=case.oem_context_id, ruleset=rule_snapshot,
        model_id="fixed-mock", model_version="model-v1", prompt_version="prompt-v1",
        confidence_grade_version="q2-experiment-confidence-v1",
    )
    response = MockSemanticResponse(
        subject_kind=ObservationSubjectKind.RULE, rule_id="D2-05", redline_no=None,
        candidate_ratio=case.expected_ratio, semantic_confidence=0.0,
        extraction_confidence=0.8, semantic_confidence_grade=case.semantic_confidence_grade,
        extraction_confidence_grade=case.extraction_confidence_grade,
        evidence=EvidenceLocator("D3", f"fixture:{case.case_id}:D3", case.input_sha256),
        source="MOCK",
    )
    source_by_case[case.case_id] = OfflineSemanticSource(
        ctx, {(ObservationSubjectKind.RULE, "D2-05"): response}
    )

def source_factory(case: CalibrationCase) -> OfflineSemanticSource:
    return source_by_case[case.case_id]

runner = OfflineCalibrationRunner(
    source_factory, expected_oem_context_id="tenant-fixture-a", expected_ruleset=rule_snapshot
)
```

这里每个case分别构造输入摘要匹配的source context；runner必须逐case再校验摘要、租户、RuleSet及批次版本，不能复用第一条source处理其它输入。REDLINE 2/3用独立case加入`cases`后由规则显式排除，不添加到`source_by_case`。
- [ ] **Step 2: 建 importable runner scaffold 并确认行为 RED**：在模块内定义dataclass及完整构造器；`_build_report` 临时返回结构合法但`items=()`、计数为0的报告。运行 `& 'C:/Dev/Codex/runtimes/zhuopin-ai/venv/Scripts/python.exe' -m pytest 'tests/test_semantic_offline_calibration.py' -q`；必须成功import/collect，失败断言定位于10个case/items、digest对应、case3追溯字段或GRADE路由，不得因缺模块/collection而失败。
- [ ] **Step 3: 实现 dataclasses 与纯合成 runner**：报告字段只有实验指标和待复核计数；无 `passed`、`accepted`、`enabled`、等级或线上 source 切换字段。不增加 legacy adapter；如果后续外部提出旧校准结果接入，需另行 design 与授权。
- [ ] **Step 4: 运行前三个聚焦测试**：`& 'C:/Dev/Codex/runtimes/zhuopin-ai/venv/Scripts/python.exe' -m pytest 'tests/test_semantic_offline_contract.py' 'tests/test_semantic_offline_source.py' 'tests/test_semantic_offline_calibration.py' -q`；预期通过。
- [ ] **Step 5: outer review**：确认报表无法被消费为线上判定/晋档证据，不 commit/push。

### Task 4: 审计、人工 override 与 PENDING 门禁

**Files:**
- Create: `C:/Users/Paul Shao/.codex/worktrees/pc-mvp-1012-v2-q2/zhuopin-ai/4-数字员工/质量部/Q2-8D报告AI判定/q2_8d_verdict/semantic_offline_signoff.py`
- Test: `C:/Users/Paul Shao/.codex/worktrees/pc-mvp-1012-v2-q2/zhuopin-ai/4-数字员工/质量部/Q2-8D报告AI判定/tests/test_semantic_offline_signoff.py`

**已核实接口：**Q2 `config.PENDING.value_of('SEMANTIC_LAYER_ACCEPTANCE')` 抛 `CriterionNotSignedOffError`，由现有 `tests/test_engine_mock.py::test_signoffs_are_named_and_pending_fails_loud` 锁定。本计划实现只传播该异常。审计事实见 Global Constraints：mock 批次 `evaluator='MOCK'`、`automation_level='L1'`；人工 override 需调用方显式传入真实身份并写 `L2`。不存在用于代替专业签认的 evaluator/gate 对象；不得自行造签认类或默认身份。

**Interfaces:**
- `HumanOverrideIdentity(evaluator: str)` frozen dataclass；用于人工 override，必须由调用方显式提供非空真实身份，写入时固定 `automation_level='L2'`。mock 批次不接收该对象，固定使用 `evaluator='MOCK'` 与 `automation_level='L1'`。测试中的 override actor 仅为合成 fixture，写入临时测试 sink，不构成专业签认。
- `AuditReceipt(event_id: str, subject_id: str, audit_record_hash: str, chain_total: int)` frozen dataclass；批次事件 `subject_id` 是 batch_id，override 事件是 candidate_id；其余均为不透明 ID/hash。
- `AuditPersistenceError(RuntimeError)`：所有 record/query/chain 完整性失败统一向上抛；绝不返回 candidate/report。
- `canonical_audit_json(value: Mapping[str, object]) -> str` 使用 `json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False)`；`audit_sha256(value: Mapping[str, object]) -> str` 对其 UTF-8 字节计算 SHA256。`append_batch_audit` 先用 `{scenario:'Q2', action:'semantic_offline_calibration', batch_id, candidate_ids, ruleset_sha256, input_hashes, model_id, model_version, prompt_version, confidence_grade_version, status:'EXPERIMENTAL_ONLY', item_count, pending_review_count}` 构造 dict decision，其中`confidence_grade_version == report.confidence_grade_version`，所有 id/hash 为 opaque 值；计算 `event_id = audit_sha256(decision)`，再写入 decision；`data_sources` 精确使用 `{'input_sha256': audit_sha256({'hashes': sorted(report.input_sha256s)}), 'ruleset_sha256': report.ruleset_sha256, 'contract_version': 'q2-semantic-offline-v1'}`。构造 `AuditEvent(scenario='Q2', action='semantic_offline_calibration', evaluator='MOCK', automation_level='L1', decision=decision, data_sources=data_sources, content_hash=audit_sha256(decision), oem_context=report.oem_context_id)`；报告必须含单一 opaque tenant context id，否则失败关闭。
- `append_batch_audit(logger: AuditLogger, report: CalibrationReport) -> AuditReceipt`：构造 `AuditEvent` 时固定 `evaluator='MOCK'`、`automation_level='L1'`。decision dict还必须记录`confidence_grade_version`，与report版本一致。调用 `record(event)` 后 `query_by(scenario='Q2', action='semantic_offline_calibration')`，按 decision 内 `event_id` 回读并检查 `verify_chain().ok`。若 query 无记录、内容不匹配或 verify false 则失败。所有 audit 字段禁止原文/客户名/证据摘录/凭据。
- `append_override(logger: AuditLogger, candidate: SemanticCandidateEnvelope, *, observation_rule_id: str, decision: Literal['ACCEPTED_BY_HUMAN','REJECTED_BY_HUMAN'], rationale_sha256: str, identity: HumanOverrideIdentity) -> AuditReceipt`：先用 `next((o for o in candidate.observations if o.rule_id == observation_rule_id), None)` 找候选 observation；不存在或 `rationale_sha256` 非64位小写 hex 时抛 `ValueError`。构造 decision dict `{event_id, candidate_id, rule_id, previous_state, human_decision, rationale_sha256, input_sha256, ruleset_sha256, schema_version}`，其中 event_id 由去掉 event_id 的其余 decision 计算 SHA256；以 `AuditEvent(scenario='Q2', action='semantic_offline_override', evaluator=identity.evaluator, automation_level='L2', decision=decision, data_sources={'input_sha256': candidate.input_sha256, 'ruleset_sha256': candidate.ruleset.sha256, 'contract_version': candidate.schema_version}, content_hash=audit_sha256(decision), oem_context=candidate.oem_context_id, override_reason=rationale_sha256)` 追加。理由原文不入 audit。真实人工身份必须调用方显式提供；不得修改 candidate 或前一事件、不得清除 PENDING，也不得把 override 写回模型候选/生成正式语义确认对象。
- `read_semantic_acceptance(config_module=config) -> object`：只执行项目真实的 `config.PENDING.value_of('SEMANTIC_LAYER_ACCEPTANCE')`（若实施前核验现状确认其确切调用签名不同，则严格复用该已核实表达式）；原 PENDING 异常直接传播。不得读取 `MEASURE_VERIFIABILITY_STANDARD`。
- `run_offline_calibration(runner: OfflineCalibrationRunner, cases: Sequence[CalibrationCase], logger: AuditLogger, *, created_at: str) -> tuple[CalibrationReport, AuditReceipt]`：唯一公开消费入口。它先调用私有 `_build_report`，再 `append_batch_audit`；只有指定顶层回读匹配且 `verify_chain().ok` 时返回 `(report, receipt)`，任一错误抛 `AuditPersistenceError` 且不返回报告。`CalibrationReport` 不从 `semantic_offline_calibration.py` 暴露为可消费结果。

- [ ] **Step 1: 写审计与门禁 fixtures 测试**：临时 JSONL sink 建立真实 `AuditLogger.jsonl`；成功 mock 批次检验 `evaluator='MOCK'`、`automation_level='L1'`、query_by 顶层过滤读回、`verify_chain().ok`、`decision` 为 dict、`data_sources` 为 `dict[str,str]`；检查 JSONL 不含 synthetic 输入正文/客户明文/证据 excerpt。用 `pytest` `monkeypatch.setattr` 分别替换 AuditLogger 实例 `record` 为抛 `OSError` 的 callable、`query_by` 为返回 `[]` 的 callable、`query_by` 为抛 `OSError` 的 callable、`verify_chain` 为返回 `SimpleNamespace(ok=False, total=1)` 的 callable；四种场景均断言唯一公开入口 `run_offline_calibration` 抛 `AuditPersistenceError` 且不返回 report。override 成功后事件数增加 1，原 candidate event/hash 未变；override event 用 synthetic fixture actor + L2，仅写 opaque ID/hash，且仍不能改变 `config.PENDING`。PENDING 测试按现有测试确切断言 `CriterionNotSignedOffError` 原样传播；通过 monkeypatch 包装真实 `config.PENDING.value_of` 记录访问键，断言只读取 `SEMANTIC_LAYER_ACCEPTANCE`，不访问 measure standard。安全属性 unknown 转人工、ASIL C/D 退出在校准调用链再断言。

```python
import pytest
import hashlib
from types import SimpleNamespace
from zhuopin_platform.audit import AuditLogger
from zhuopin_platform.criteria_signoff import CriterionNotSignedOffError
from q2_8d_verdict import config
from q2_8d_verdict.semantic_offline_contract import CandidateState, ConfidenceGrade, ObservationSubjectKind
from q2_8d_verdict.semantic_offline_calibration import CalibrationCase, CalibrationItem, CalibrationReport, OfflineCalibrationRunner
from q2_8d_verdict.semantic_offline_signoff import AuditPersistenceError, read_semantic_acceptance, run_offline_calibration


@pytest.fixture
def synthetic_report():
    sample_digest = hashlib.sha256(b"synthetic-q2-case-03").hexdigest()
    return CalibrationReport(
        status="EXPERIMENTAL_ONLY", batch_id="batch-fixture-001",
        oem_context_id="tenant-fixture-a", input_sha256s=(sample_digest,),
        ruleset_sha256="b" * 64, model_id="fixed-mock", model_version="fixture-v1",
        prompt_version="fixture-p1", confidence_grade_version="q2-experiment-confidence-v1",
        items=(CalibrationItem(
            case_id="syn-case-03", input_sha256=sample_digest,
            candidate_id="candidate-fixture-003", subject_kind=ObservationSubjectKind.RULE,
            rule_id="D2-05", redline_no=None, candidate_ratio=1.0,
            semantic_confidence=0.0, extraction_confidence=0.8,
            semantic_confidence_grade=ConfidenceGrade.HIGH,
            extraction_confidence_grade=ConfidenceGrade.HIGH,
            sample_number=3, scene_tag="制造", trace_tag="Q2-G-03",
            state=CandidateState.CANDIDATE, review_reason=None, excluded_from_metrics=False,
        ),),
        synthetic_case_count=1, positive_count=1, negative_count=0,
        agreement_rate=1.0, redline_false_positive_rate=0.0, pending_review_count=0,
    )


@pytest.fixture
def runner(monkeypatch, synthetic_report):
    instance = object.__new__(OfflineCalibrationRunner)
    monkeypatch.setattr(instance, "_build_report", lambda cases, *, created_at: synthetic_report)
    return instance


@pytest.fixture
def synthetic_cases():
    digest = hashlib.sha256(b"synthetic-q2-case-03").hexdigest()
    return (CalibrationCase(
        case_id="syn-case-03", input_sha256=digest, oem_context_id="tenant-fixture-a",
        subject_kind=ObservationSubjectKind.RULE, rule_id="D2-05", redline_no=None,
        expected_ratio=1.0, semantic_confidence_grade=ConfidenceGrade.HIGH,
        extraction_confidence_grade=ConfidenceGrade.HIGH, safety_related=False,
        asil_level="B", sample_number=3, scene_tag="制造", trace_tag="Q2-G-03", synthetic=True,
    ),)


def test_query_miss_fails_closed(monkeypatch, tmp_path, synthetic_report, runner, synthetic_cases):
    logger = AuditLogger.jsonl(tmp_path / "audit.jsonl")
    monkeypatch.setattr(logger, "query_by", lambda **filters: [])
    with pytest.raises(AuditPersistenceError):
        run_offline_calibration(runner, synthetic_cases, logger, created_at="2026-10-12T00:00:00Z")


def test_pending_acceptance_propagates_original_error_and_reads_one_key(monkeypatch):
    registry_type = type(config.PENDING)
    original = registry_type.value_of
    observed: list[str] = []

    def spy(registry, key):
        observed.append(key)
        return original(registry, key)

    monkeypatch.setattr(registry_type, "value_of", spy)
    with pytest.raises(CriterionNotSignedOffError):
        read_semantic_acceptance()
    assert observed == ["SEMANTIC_LAYER_ACCEPTANCE"]
```

上述 `runner` 和 `synthetic_cases` fixture 在签认测试中通过 monkeypatch `runner._build_report` 固定返回 `synthetic_report`，让该任务只测审计边界；`created_at` 固定如上。其余三种审计失败用同一临时 `logger` fixture，分别 monkeypatch `record` 为 `raise OSError('synthetic write failure')`、`query_by` 为 `raise OSError('synthetic read failure')`、`verify_chain` 为 `SimpleNamespace(ok=False, total=1)`；每项单独 test function 并断言 `run_offline_calibration` 抛 `AuditPersistenceError`。所有依赖名均来自既有平台/API及本任务接口，不新增平台 helper。
- [ ] **Step 2: 建 importable signoff scaffold 并确认行为 RED**：在模块内定义完整类型与函数签名；批次入口暂时返回失败或空回执，人工override只做参数校验，PENDING getter直接调用真实注册表。运行 `& 'C:/Dev/Codex/runtimes/zhuopin-ai/venv/Scripts/python.exe' -m pytest 'tests/test_semantic_offline_signoff.py' -q`；必须成功import/collect，审计成功路径或四种失败关闭断言失败于行为，不得因缺模块/collection而失败。
- [ ] **Step 3: 实现审计与 read-through**：只用平台 `AuditEvent`、`AuditLogger`；`record()` 返回 `None` 不作为成功凭证，必须回读指定顶层过滤记录并验链。决策字段保持 dict，来源保持 dict[str,str]；离线 mock event 固定 L1/MOCK，人工 override 只接真实调用方身份并记 L2。没有可信人工身份时拒绝 override，不把它设为专业签认或清除 PENDING 的路径。
- [ ] **Step 4: 运行四文件聚焦测试**：`& 'C:/Dev/Codex/runtimes/zhuopin-ai/venv/Scripts/python.exe' -m pytest 'tests/test_semantic_offline_contract.py' 'tests/test_semantic_offline_source.py' 'tests/test_semantic_offline_calibration.py' 'tests/test_semantic_offline_signoff.py' -q`；预期通过。
- [ ] **Step 5: outer review**：逐条核对无原文/客户明文、无线上集成、PENDING 原异常传播、审计先行、override append-only，不 commit/push。

### Task 5: 逐项目验收与白名单复核

**Files:** 仅复核以上 8 个新增文件；不得扩大路径。

**Interfaces:** 四模块接口与上文保持一致。不得引入共享平台新接口或依赖。

- [ ] **Step 1: 检查工作树产物集合**：在隔离树用 `git status --short` 和 `git diff --name-only` 核对仅有四个 `semantic_offline*.py` 与四个 `test_semantic_offline*.py`；存在额外文件即停止并报告，不自行删除其他工作。
- [ ] **Step 2: 跑逐项目聚焦/正式CI测试**：从Q2项目根先运行四个新增聚焦测试文件；正式全项目CI命令为 `& 'C:/Dev/Codex/runtimes/zhuopin-ai/venv/Scripts/python.exe' -m pytest -q --tb=short --junit-xml=pytest-result.xml`。JUnit报告是测试运行产物，不纳入8文件源码白名单；按outer留证安排保存或清理。不得追加`--maxfail`，不得在仓库根运行，不运行旧真实校准脚本。
- [ ] **Step 3: 检查真实规则集只读一致性**：调用现有 `rules_loader.load()` 并断言 envelope 记录的 source_version/hash 与返回 `RuleSet` 相同；检查合同 IDs 精确来自真实 `RuleSet`，不断言规则总数为 24 或 25。
- [ ] **Step 4: 静态保护边界**：测试或 review 检查新增模块无 `requests`/模型 SDK/上传、无 `engine`/webapp import、无默认 source 赋值、无原文写 audit、无 `TRIGGERED` 输出、无 `HumanVerdictSource` 继承、无启用/晋档字段；同时核对线上默认和两项 PENDING 文件完全未改。
- [ ] **Step 5: 留验收证据给 outer**：汇报实际解释器、项目根、命令、退出码、测试摘要、八文件 diff 路径、运行时规则集版本/hash、旧 schema 是否确认、审计链验证结果及任何未闭合缺口。派生模型不 commit/push；outer 根据单独授权决定是否封存/合入。

## Spec 覆盖自检

- 版本化合同、输入 digest、OEM 隔离、真实 ruleset/model/prompt 来源、逐条定位与无原文：Task 1、Task 2。
- None≠0、双置信、无 evidence、越界、unknown/invalid：Task 1、Review Focus 1–2。
- 离线 source 与线上 Pending 默认隔离、候选不等于人工确认、不触发红线：Task 2、Review Focus 3。
- 合成固定 mock、EXPERIMENTAL_ONLY、V1/V2 实验读数、V3/V4/V5 边界、红线②③排除：Task 3。
- append-only audit、override 身份/理由、写回读验链、失败关闭、PENDING 原异常：Task 4、Review Focus 4–5。
- 安全属性与 ASIL C/D、客户隔离、实际 RuleSet、旧 schema 不猜测：Tasks 1–5。
- 无 UI/上传/engine/真实数据/真实校准/线上启用/规则改动/设计扩权：Global Constraints 与 Task 5。

## 计划自审

- **Spec coverage：** 已逐条将 delta spec 的 7 项 Requirement 和各 Scenario 映射到 Tasks 1–5 与聚焦测试；无未分配 requirement。
- **占位检查：** 每个测试步骤均含具体输入与断言；当前源码未包含旧校准程序/schema，适配明确不在本计划中；PENDING 异常类型已依据现有场景测试核定为 `CriterionNotSignedOffError`。
- **类型一致性：** Task 1 定义 `RuleSetSnapshot`、`CandidateState`、`SemanticObservation`、`SemanticCandidateEnvelope`；Task 2 使用同一类型；Task 3 的 `CalibrationCase`、`CalibrationReport` 供 Task 4 接收；Task 4 的 `AuditReceipt` 是唯一回执类型。所有函数签名与下游参数名保持一致。
- **Review Focus：** 五项各有确切测试函数名及所属测试文件，并在对应 Task 的 Step 1 列出输入 fixture 与预期断言。
- **真实技术缺口：** 当前 Q2 场景源码无旧校准脚本/输出 schema，因此本计划无 legacy adapter；运行时 `RuleSet` 精确对象仍由后续测试中的既有 `ruleset` fixture 调用 `rules_loader.load()` 生成，计划提供了源代码核对基准及投影测试。AuditLogger 的 record/query/verify 接口已核定，可用 pytest monkeypatch 验证失败路径。专业签认仍为 `PENDING`，本计划不读取 MEASURE 项、不签认、不启用语义 source。
