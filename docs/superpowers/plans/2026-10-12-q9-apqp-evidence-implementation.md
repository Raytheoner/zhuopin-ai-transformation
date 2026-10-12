# Q9 APQP Evidence Review Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在获准的隔离工作树中为 Q9 建立仅限合成 mock 的 APQP 证据候选追溯、差异呈现、人工追加裁决和可追溯报告，不作专业判定或阶段控制。

**Architecture:** 新建独立 Q9 场景包，以带客户/项目/文档/版本/定位的 typed evidence identity 为边界；解析、候选图、比较和 G01–G06 pending registry 均为纯业务模块，由 service 编排并经平台既有 `AuditLogger.jsonl` / `AuditEvent` 写入 append-only audit。PC MVP 提供 mock 上传、本地 JSON 资料清单、候选追溯/差异、演示人工追加裁决与版本报告，入口只消费明确标记的 mock manifest。若提供 web 入口，复用已设计的 `/quality/q9-apqp-evidence-review` Blueprint，不新开端口；共享门户注册与部署不是 mock 包完成的前置条件。

**Tech Stack:** Python（按执行时项目约定的隔离环境）、pytest、现有 `zhuopin_platform` bootstrap 与 audit API；不得新增依赖，除非实施前核实 CI 闭包确有必要并经范围审查。

**Spec:** `reports/pc-mvp-1012/v2-review/q9/specs/q9-apqp-evidence-review/spec.md`；冻结设计：`reports/pc-mvp-1012/v2-review/q9/design.md`（批准基线 HEAD `1df48365385cf3a2e1c436fbe77466caaae80cd2`，SHA256 `fce1a7c85a7c5414985c36b21fd3b38178c319524084fcfa32f9db2a7f7da3c5`；资料集合 SHA256 `5649280b4fedf389235ef13188bea5d168eee4fabbeaf9595c61485b75226500`）。

## Global Constraints

- 实施工作树：`C:/Users/Paul Shao/.codex/worktrees/pc-mvp-1012-v2-q9/zhuopin-ai/4-数字员工/质量部/Q9-APQP阶段审查`；实际执行前再次核验批准绑定、HEAD、SHA256、`allowed_paths` 与当前工作树，不在本计划所在主工作树直接实施。
- 仅一个明确 `customer_id`、`project_id` 与显式资料版本组合；保留每个 `document_id`、类型、原始版本、来源、内容摘要及稳定定位；拒绝跨客户/缺身份/缺版本/缺定位，不推断“最新”。
- 八份资料均为合成 mock；不读取真实 OEM/客户/项目/生产数据，不将客户明文、原始 8D/OEM 技术原文或原风险数据写入通用 audit。
- 状态仅为 `not_provided`、`provided_not_extracted`、`extracted`、`needs_human_review`；抽取缺失不是业务缺项；差异不派生严重度、通过/失败或阶段处置。
- G01–G06 保持 `PENDING`；不引入 Q2 阈值、黄金答案、专业规则或行业映射。未知安全属性转人工；ASIL C/D 退出 AI 分析、修改、最终判定和 AI 安全证据链。
- 候选边只能由有权人工裁决升级；真实 actor 必须带显式权限来源。合成 demo actor provider 默认 deny，仅显式启用的 mock 演示配置可追加演示事件；它不得签 G01–G06 或代表真实授权。更正追加新事件并指向旧事件；不得覆盖。Audit 写入失败时不得显示裁决已保存。
- Q4/Q9 只共享完整 Control Plan 输入身份；规则、裁决、review/session、signoff、audit 均按场景隔离；不读写 Q4 结论。
- 使用平台 `AuditLogger.jsonl`、`record(AuditEvent)`、`query_by`、`verify_chain().ok`；现有字段包括 `scenario/action/evaluator/automation_level: str`、`decision: dict[str, Any]`、`data_sources: dict[str, str]`。写入 `automation_level="L1"`；mock 来源放在 evaluator synthetic actor 与 data_sources 中，不造 MOCK automation level。audit 投影只用 opaque ID、hash、定位摘要。
- bootstrap 遵照 `zhuopin_platform/bootstrap.py` 唯一 stub 与 `ensure_paths(..., strict=True)`；pytest 引导遵照 `FI3-付款申请自动校验/tests/conftest.py` 标准 block。不得复制其中内部发现算法。
- 只在 Q9 子项目根运行未来 CI；不得仓库根聚合 pytest。mock 验收不等于正式业务验收、部署或发布授权。
- 每个行为必须 TDD：先创建可导入的最小 typed interface skeleton，再写失败的功能断言并运行；必须确认是目标断言失败，不能把 module-not-found/import/collection error 当作有效 RED。然后实现最小行为并重跑 GREEN。所有分阶段命令均从 Q9 子项目根用固定 runtime：`"C:/Dev/Codex/runtimes/zhuopin-ai/venv/Scripts/python.exe" -m pytest -q --tb=short "<Q9相对测试路径>"`。

## Review Focus

1. 缺桥接文件、定位失效或可能一对多/多对一时，仍保留候选并明确待人工；绝不猜行业映射。测试：`test_candidate_graph.py::test_ambiguous_or_missing_bridge_stays_reviewable`。
2. 已提供但抽取器未命中时，结果是 `provided_not_extracted`，不能显示为业务缺项。测试：`test_extraction_status.py::test_supplied_unmatched_source_is_not_business_missing`。
3. Q4 已有 Control Plan 审查结果时，Q9 仍需自己的 review 和裁决且不回写。测试：`test_q4_result_isolation.py::test_shared_identity_does_not_import_or_write_decisions`。
4. G01–G06 未签认、签认 actor 无权或安全属性未知时，路径 fail-closed 并转人工；ASIL C/D 不进 AI 链。测试：`test_criteria_pending.py::test_pending_criteria_never_evaluate`、`test_mock_case_contract.py::test_unknown_safety_routes_to_human` 和 `test_mock_case_contract.py::test_asil_cd_exits_before_extraction`。
5. mock 报告、audit 失败、更正历史及脱敏投影均不伪装成 APQP 业务结论或成功签认。测试：`test_report_contract.py::test_mock_report_has_no_apqp_or_stage_verdict` 与 `test_decision_audit.py::test_audit_failure_leaves_candidate_unresolved`。

---

## File Map and Typed Contracts

Design 的 11 个模块逐项落地：`models.py`、`identity.py`、`ingest.py`、`extraction.py`、`candidate_graph.py`、`comparison.py`、`criteria.py`、`review.py`、`service.py`、`report.py`、`webapp.py`。`audit.py` 是 D6 落到平台 API 的场景内 adapter，不另建 audit 服务/存储；测试与 mock fixture 是 design 指定八测试的组成。`tests/conftest.py` 为新场景 pytest 的本地胶水，按标准 strict bootstrap block。后续 `allowed_paths` 固定为下方恰好 24 个 Q9 子树文件，不增加 `tests/__init__.py` 或共享文件。新场景 `pyproject.toml` 与包 `__init__.py` 属于明确的导入/CI scaffold，允许在白名单内创建。webapp 复用已设计 Blueprint；门户全局注册/CI 矩阵属于后续整合，不是 mock 包停笔前置，也不在本计划中要求修改共享文件。

```text
4-数字员工/质量部/Q9-APQP阶段审查/
  pyproject.toml                                  # Q9隔离子项目/CI元数据
  q9_apqp_evidence/
    __init__.py                                   # 场景包导入入口
    models.py                                     # 所有不可变业务类型与协议
    identity.py                                   # identity 合同验证
    ingest.py                                     # mock manifest 与输入身份绑定
    extraction.py                                 # extractor adapter / 状态
    candidate_graph.py                            # 候选追溯边
    comparison.py                                 # 来源定位差异
    criteria.py                                   # G01–G06 pending registry
    review.py                                     # 人工裁决、更正、权限来源
    audit.py                                      # 平台 AuditLogger 适配与脱敏投影
    service.py                                    # 单次 review 编排
    report.py                                     # mock 结果报告
    webapp.py                                     # 复用已设计的统一门户 Blueprint（若需）
  tests/
    conftest.py                                   # 标准路径引导 block，strict=True
    fixtures/q9_mock_manifest.json                # 八案例索引；数据保持合成
    test_identity_contract.py
    test_candidate_graph.py
    test_extraction_status.py
    test_criteria_pending.py
    test_decision_audit.py
    test_q4_result_isolation.py
    test_mock_case_contract.py
    test_report_contract.py
```

固定 24 路径清单（未来 `allowed_paths` 原样绑定）：场景根 `pyproject.toml`；包内 `q9_apqp_evidence/__init__.py` 与 12 个模块 `models.py`、`identity.py`、`ingest.py`、`extraction.py`、`candidate_graph.py`、`comparison.py`、`criteria.py`、`review.py`、`audit.py`、`service.py`、`report.py`、`webapp.py`；测试侧 `tests/conftest.py`、`tests/fixtures/q9_mock_manifest.json`、`tests/test_identity_contract.py`、`tests/test_candidate_graph.py`、`tests/test_extraction_status.py`、`tests/test_criteria_pending.py`、`tests/test_decision_audit.py`、`tests/test_q4_result_isolation.py`、`tests/test_mock_case_contract.py`、`tests/test_report_contract.py`。不加 `tests/__init__.py`，除此 24 项不新增/修改其他路径。

在 `models.py` 中定义完整、显式类型（不得使用未定义 helper、隐式动态 dict 或省略返回类型）：

```python
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import Any, Literal, Mapping, Protocol, Sequence
import pytest
from zhuopin_platform.audit import AuditEvent, AuditLogger, ChainVerifyResult

class EvidenceState(StrEnum):
    NOT_PROVIDED = "not_provided"
    PROVIDED_NOT_EXTRACTED = "provided_not_extracted"
    EXTRACTED = "extracted"
    NEEDS_HUMAN_REVIEW = "needs_human_review"

class DecisionKind(StrEnum):
    CONFIRM = "confirm"
    REJECT = "reject"
    REQUEST_EVIDENCE = "request_evidence"

@dataclass(frozen=True)
class EvidenceLocator:
    coordinate_type: str
    coordinate: str

@dataclass(frozen=True)
class EvidenceRef:
    customer_id: str
    project_id: str
    document_id: str
    document_type: Literal["DFMEA", "CONTROL_PLAN", "SOP", "BRIDGE"]
    version: str
    content_digest: str
    source_ref: str
    locator: EvidenceLocator

@dataclass(frozen=True)
class ExpectedEvidenceRef:
    customer_id: str
    project_id: str
    document_id: str
    document_type: Literal["DFMEA", "CONTROL_PLAN", "SOP", "BRIDGE"]
    version: str
    # A missing source has no content digest or source locator yet.

@dataclass(frozen=True)
class ReviewContext:
    customer_id: str
    project_id: str
    review_id: str
    package_id: str
    mock: Literal[True]
    evidence: tuple[EvidenceRef, ...]
    # Explicit package metadata only; never inferred by the model or extractor.
    safety_related: bool | None
    asil_level: Literal["A", "B", "C", "D"] | None

@dataclass(frozen=True)
class ExtractionRecord:
    evidence: EvidenceRef | None
    missing_reference: ExpectedEvidenceRef | None
    field_key: str
    state: EvidenceState
    extracted_value: str | None
    extractor_version: str
    model_version: str | None
    prompt_version: str | None
    confidence_source_text: str | None

@dataclass(frozen=True)
class CandidateTraceEdge:
    edge_id: str
    source: EvidenceRef
    target: EvidenceRef
    bridge_evidence: tuple[EvidenceRef, ...]
    rationale: str
    generation_method: str
    generator_version: str
    model_version: str | None
    prompt_version: str | None
    state: EvidenceState

@dataclass(frozen=True)
class EvidenceDifference:
    difference_id: str
    left: ExtractionRecord
    right: ExtractionRecord
    normalized_display_left: str | None
    normalized_display_right: str | None
    comparator_version: str
    state: EvidenceState

@dataclass(frozen=True)
class CriterionRecord:
    criterion_id: Literal["G01", "G02", "G03", "G04", "G05", "G06"]
    version: str
    status: Literal["PENDING", "SIGNED"]
    scope: str | None
    rationale: str | None
    signer_id: str | None
    signer_authority_source: str | None
    signed_at: datetime | None
    evidence_source: str | None

@dataclass(frozen=True)
class ReviewerIdentity:
    actor_id: str
    actor_type: Literal["human"]
    authority_source: str

@dataclass(frozen=True)
class HumanDecision:
    decision_id: str
    subject_id: str
    kind: DecisionKind
    rationale: str
    reviewer: ReviewerIdentity
    decided_at: datetime
    evidence: tuple[EvidenceRef, ...]
    supersedes_decision_id: str | None

@dataclass(frozen=True)
class ReviewResult:
    context: ReviewContext
    extractions: tuple[ExtractionRecord, ...]
    candidate_edges: tuple[CandidateTraceEdge, ...]
    differences: tuple[EvidenceDifference, ...]
    criteria: tuple[CriterionRecord, ...]
    decisions: tuple[HumanDecision, ...]
    limitations: tuple[str, ...]
    mock: Literal[True]
    business_verdict: Literal[None]
    stage_action: Literal[None]

class EvidenceExtractor(Protocol):
    def extract(self, context: ReviewContext) -> Sequence[ExtractionRecord]: ...

class ScriptedExtractor:
    def __init__(self, records: Mapping[tuple[str, str], ExtractionRecord]) -> None: ...
    def extract(self, context: ReviewContext) -> Sequence[ExtractionRecord]: ...

class SyntheticActorProvider(Protocol):
    def get_demo_reviewer(self, enabled: bool) -> ReviewerIdentity | None: ...

class EvidenceContractError(ValueError): ...
class AuditPersistenceError(RuntimeError): ...

@pytest.fixture
def mock_case_ids() -> tuple[str, ...]: ...

@pytest.fixture
def asil_cd_case() -> ReviewContext: ...

class AuditSink(Protocol):
    def record(self, event: "AuditEvent") -> None: ...
    def query_by(self, **filters: str) -> list[dict[str, Any]]: ...
    def verify_chain(self) -> "ChainVerifyResult": ...

# Import AuditEvent and ChainVerifyResult from zhuopin_platform.audit.
# Existing AuditEvent fields are scenario/action/evaluator/automation_level,
# decision: dict[str, Any], data_sources: dict[str, str], content_hash,
# oem_context, override_reason, report_path, error and timestamp. The Q9 adapter
# writes automation_level="L1". MOCK provenance belongs in evaluator/data_sources,
# never in an invented automation level. AuditSink only wraps the existing
# logger; it is not a new ledger or persistence implementation.
```

Additional public functions have complete typed signatures in their owning module: `validate_context(context: ReviewContext) -> tuple[str, ...]`; `load_mock_manifest(path: Path) -> ReviewContext`; `extract_evidence(context: ReviewContext, extractor: EvidenceExtractor) -> tuple[ExtractionRecord, ...]`; `build_candidate_graph(records: Sequence[ExtractionRecord], generator_version: str) -> tuple[CandidateTraceEdge, ...]`; `compare_records(records: Sequence[ExtractionRecord], comparator_version: str) -> tuple[EvidenceDifference, ...]`; `pending_criteria() -> tuple[CriterionRecord, ...]`; `record_decision(subject_id: str, kind: DecisionKind, rationale: str, reviewer: ReviewerIdentity, decided_at: datetime, evidence: Sequence[EvidenceRef], supersedes_decision_id: str | None, audit: AuditSink) -> HumanDecision`; `run_review(context: ReviewContext, extractor: EvidenceExtractor, audit: AuditSink) -> ReviewResult`; `render_report(result: ReviewResult) -> str`. Enforce `ExtractionRecord` has exactly one of `evidence` or `missing_reference`; `NOT_PROVIDED` uses `ExpectedEvidenceRef`, while all extracted states require `EvidenceRef`. Define `SyntheticActorProvider.get_demo_reviewer(enabled: bool) -> ReviewerIdentity | None`: default `None`; only an explicitly enabled mock demo path may return an identity with `authority_source="synthetic_demo_only"`, which cannot sign criteria or serve as an authenticated real reviewer. Raise typed `EvidenceContractError` for invalid identity and `AuditPersistenceError` for failed append; define both in `models.py`. The adapter imports the platform `AuditEvent`, calls existing `AuditLogger.record(event)` (returns `None`), queries the exact scenario/action/content hash and requires `verify_chain().ok`; no second mutable ledger.

## Typed Test Fixtures and Eight Executable Test Contracts

`tests/conftest.py` defines typed fixtures, not `Any`-returning factories: `mock_case_ids() -> tuple[str, ...]`; `mock_context(request: pytest.FixtureRequest) -> ReviewContext`; `valid_evidence_refs() -> tuple[EvidenceRef, ...]`; `expected_missing_reference() -> ExpectedEvidenceRef`; `asil_cd_case() -> ReviewContext`; `scripted_extractor() -> ScriptedExtractor`; `memory_audit(tmp_path: Path) -> AuditLogger`; `synthetic_actor_disabled() -> SyntheticActorProvider`; and `q4_reference_pair() -> tuple[ReviewContext, ReviewContext]`. `ScriptedExtractor` maps explicit `(document_id, field_key)` keys to typed `ExtractionRecord` objects. The audit fixture uses a temp JSONL path and the real platform `AuditLogger.jsonl`, never a hand-rolled mutable audit stub for persistence semantics. Ordinary mock cases explicitly state `safety_related=False, asil_level="B"`; unknown safety case explicitly states both as `None`; the separate ASIL C/D fixture explicitly supplies `safety_related=True, asil_level="C"` and is never inferred. Each test supplies exact input and asserts typed values/status/side effects:

| Test module | Required concrete tests and assertions |
|---|---|
| `test_identity_contract.py` | `test_complete_identity_is_preserved`: returned identity equals customer/project/doc/type/version/digest/locator input. `test_cross_customer_and_missing_identity_rejected`: `EvidenceContractError`, no extractor call and no audit event. `test_versions_are_not_ranked`: v1/v2 both retained in supplied order and neither selected as authoritative. |
| `test_candidate_graph.py` | `test_matching_identifier_stays_candidate`: edge exists with candidate state and exact source refs, no confirmed business status. `test_ambiguous_or_missing_bridge_stays_reviewable`: state is `NEEDS_HUMAN_REVIEW`, bridge refs empty or all explicit alternatives, rationale names missing/ambiguous bridge. `test_cardinality_is_preserved`: two source refs to one target yield two edges, no collapsed one-to-one mapping. |
| `test_extraction_status.py` | `test_supplied_unmatched_source_is_not_business_missing`: evidence is present, state `PROVIDED_NOT_EXTRACTED`, extractor version retained. `test_absent_source_uses_expected_reference`: state `NOT_PROVIDED`, evidence is `None`, expected ref exact. `test_extracted_value_has_source_locator`: value, `EvidenceRef.locator`, extractor/model/prompt versions preserved. |
| `test_criteria_pending.py` | `test_pending_criteria_never_evaluate`: exactly IDs G01–G06 each versioned PENDING, no rule payload, requested evaluation remains manual review. `test_no_q2_fallback`: pending result unchanged when Q2-like values are present in unrelated input. `test_synthetic_actor_cannot_sign_criterion`: synthetic identity rejected, zero signoff audit events. |
| `test_decision_audit.py` | `test_human_decision_appends_and_verifies`: explicit reviewer/authority/rationale/evidence/time persisted; query finds one event and chain is OK. `test_audit_failure_leaves_candidate_unresolved`: separately inject `record`, query, and chain verification failures; each raises `AuditPersistenceError`, returns no saved decision, and leaves prior candidate unchanged. `test_correction_appends_reference`: old event bytes/value unchanged; new event has distinct content hash and supersedes ID. `test_audit_projection_is_redacted`: no customer plaintext/raw OEM text/raw risk appears in any serialized AuditEvent field; data_sources values are opaque/hash/locator/mock labels; automation level is L1, evaluator identifies synthetic actor. |
| `test_q4_result_isolation.py` | `test_shared_identity_does_not_import_or_write_decisions`: Q4/Q9 have equal exact Control Plan identity but distinct review IDs/results/decision lists; Q4 fake repository records zero writes; Q4 verdict/signoff never appears in Q9 output/audit. |
| `test_mock_case_contract.py` | `test_eight_cases_are_synthetic_and_well_formed`: fixture IDs equal the eight named cases; every context is single-customer/project mock with explicit supplied identity and explicit safety metadata. `test_unknown_safety_routes_to_human`: `None` metadata stays unknown and produces a review limitation. `test_asil_cd_exits_before_extraction`: explicit C/D fixture causes zero extractor/AI calls and no safety-chain output. `test_input_rejects_real_material`: non-mock marker or disallowed raw-source fixture is rejected before processing. |
| `test_report_contract.py` | `test_mock_report_has_no_apqp_or_stage_verdict`: report contains mock label, “非 APQP 通过判定”, PENDING and evidence limitations; contains no pass/fail, severity, safety level, stage advance/block. `test_report_distinguishes_missing_from_unextracted`: both statuses and expected refs appear distinctly. `test_demo_actor_is_default_deny`: no explicit enablement gives denied action and no decision/audit; explicit mock enablement appends only labeled synthetic demo decision. |

All fixture functions, protocol methods, dataclasses, test parameters, and assertion helpers must have complete annotations. Helpers are defined in the test module or `conftest.py` before use; avoid implicit fixtures, magic globals, untyped `dict` payloads, and behavior not covered by an explicit assertion above.

## Execution Tasks

### Task 1: Isolated package scaffold and mock contract

**Files:** create the exact 24 Q9 subtree paths in the file map, including package `__init__.py` and scene `pyproject.toml`; create `tests/conftest.py` with the existing standard bootstrap block and `strict=True`. No shared portal or CI file is a prerequisite for this mock package.

- [ ] 1.1 In the approved worktree, verify design and evidence collection hashes, HEAD, allowed paths, isolated Python interpreter `C:/Dev/Codex/runtimes/zhuopin-ai/venv/Scripts/python.exe`, and cleanly record any mismatch before writing code.
- [ ] 1.2 Create the exact 24-path allowlisted skeleton, including Q9 `pyproject.toml`, package `__init__.py`, and the eight test modules; do not add `tests/__init__.py`. `tests/conftest.py` follows the FI3 standard bootstrap block shape and calls platform `ensure_paths(__file__, <Q9 package root>, strict=True)`; do not copy discovery logic.
- [ ] 1.3 Write eight synthetic manifest entries with keys `case_id`, `mock`, `customer_id`, `project_id`, `safety_related`, `asil_level`, `evidence[]`, `expected_references[]`, and optional `q4_reference`: `complete_chain`, `multiple_versions`, `missing_source`, `extraction_miss`, `unclassified_difference`, `bridge_ambiguous`, `unknown_safety`, `shared_q4_control_plan`. Ordinary cases explicitly set False/B; unknown case sets None/None. Add a separate typed ASIL C/D fixture (not a ninth manifest case). Every entry uses `MOCK-OEM-A` / `MOCK-PROJECT-A`; supplied documents have explicit ID/type/version/digest/source/locator, missing refs have no invented digest/locator, and no case asserts professional correctness.
- [ ] 1.4 Write typed manifest contract tests first; run from Q9 root with the fixed interpreter and confirm behavioral assertion failures, not import/collection errors. Implement loader minimally; rerun GREEN for all eight cases, false/missing mock marker, mixed customer/project, missing identity, missing manifest keys, raw-source rejection, and explicit preservation of safety/ASIL fields.

### Task 2: Typed identities, ingest, and extraction state

**Files:** `models.py`, `identity.py`, `ingest.py`, `extraction.py`, `tests/test_identity_contract.py`, `tests/test_extraction_status.py`.

- [ ] 2.1 Define frozen domain types and typed errors in `models.py`; keep model suggestions and human decisions separate.
- [ ] 2.2 For each identity behavior, add a test before implementation, run to a behavioral assertion failure after imports succeed, implement minimal validation, then rerun GREEN: mixed/missing identities, missing version/locator, versions retained without ranking.
- [ ] 2.3 Repeat RED→minimal GREEN for `load_mock_manifest`: explicit mock marker and single-context validation; import/collection errors do not count as RED.
- [ ] 2.4 Repeat RED→minimal GREEN for extraction: supplied-but-unmatched is `PROVIDED_NOT_EXTRACTED`; absent expected source is `NOT_PROVIDED`; extracted values preserve identity, locator and extractor/model/prompt versions.
- [ ] 2.5 From Q9 root run identity/extraction test modules with fixed runtime; assert locator drift and provenance.

### Task 3: Candidate graph and evidence comparison

**Files:** `candidate_graph.py`, `comparison.py`, `tests/test_candidate_graph.py`.

- [ ] 3.1 Write graph assertions first; confirm RED is an assertion failure after imports succeed, then implement deterministic candidate edges with exact source/target refs and generator/model/prompt versions; rerun GREEN.
- [ ] 3.2 Write missing/ambiguous bridge tests first; implement `NEEDS_HUMAN_REVIEW` and explicit bridge alternatives without guessed mappings; rerun GREEN.
- [ ] 3.3 Write comparison assertions first; implement both source values/locators and comparator version only; rerun GREEN and assert no severity/pass/fail/stage property.
- [ ] 3.4 From Q9 root run `test_candidate_graph.py` with fixed runtime; verify matching identifiers remain candidates, cardinality stays split, and differences are unclassified.

### Task 4: Pending criteria and human decision lifecycle

**Files:** `criteria.py`, `review.py`, `tests/test_criteria_pending.py`, `tests/test_decision_audit.py`.

- [ ] 4.1 Write RED tests for exactly G01–G06 pending/no rule payload; implement registry/manual-review response; rerun GREEN, including Q2-like unrelated values not activating any criterion.
- [ ] 4.2 Write RED actor tests; implement explicit real reviewer authority source requirement and synthetic actor rejection for criterion signoff; rerun GREEN without inventing a role mapping.
- [ ] 4.3 Write RED append/correction tests; implement confirm/reject/request-evidence as append-only records; correction references old decision without mutating it; rerun GREEN.
- [ ] 4.4 From Q9 root run criteria/review modules with fixed runtime; assert model/extractor cannot sign and reviewer/time/rationale/case/evidence metadata persists.

### Task 5: Existing platform audit adapter and Q4 isolation

**Files:** `audit.py`, `service.py`, `tests/test_decision_audit.py`, `tests/test_q4_result_isolation.py`.

- [ ] 5.1 Use API source copies `reports/pc-mvp-1012/v2-review/technical-sources/2-events.py.txt` and `3-logger.py.txt` as the reviewed reference: platform `AuditEvent` fields are `scenario`, `action`, `evaluator`, `automation_level: str`, `decision: dict[str, Any]`, `data_sources: dict[str, str]`, `content_hash`, `oem_context`, `override_reason`, `report_path`, `error`, `timestamp`; `AuditLogger.jsonl(path)`, `record(event) -> None`, `query_by(**filters) -> list[dict]`, `verify_chain() -> ChainVerifyResult`. At implementation, check current import/runtime paths; do not change platform code.
- [ ] 5.2 Write audit projection tests first; confirm redaction/L1/mock provenance assertions fail (not import errors), then implement platform `AuditEvent` with `automation_level="L1"`, scenario `Q9`, explicit action, synthetic evaluator only for mock demo events, structured decision dict, and opaque/hash/safe-locator/mock-provenance `data_sources`; rerun GREEN. Keep sensitive source data out of audit and `oem_context` empty for synthetic cases.
- [ ] 5.3 Write RED persistence tests for `record`, query, and chain failures; implement query by scenario/action/content hash after `record(None)` and require one match plus `verify_chain().ok`; rerun GREEN. Any failure raises `AuditPersistenceError`, leaves candidate unresolved, and never shows saved decision.
- [ ] 5.4 Implement `SyntheticActorProvider` default-deny: disabled means no reviewer; explicit mock-only enablement returns a synthetic identity for demo append only. Criteria signoff and authenticated real-review paths reject synthetic identities. Real role/authority mapping remains open and must be sourced authoritatively before real review.
- [ ] 5.5 Write Q4 isolation RED test; implement exact shared `EvidenceRef` identity with distinct Q4/Q9 review IDs and separate result/decision collections; Q9 may display opaque Q4 context ID, never import verdict/signoff/criteria. Rerun GREEN; assert Q4 repository spy receives zero writes.
- [ ] 5.6 From Q9 root run audit and Q4 isolation tests with fixed runtime; verify redaction, L1/mock provenance, query/chain, injected failures, append-only correction, and equal input identity with distinct review states.

### Task 6: Service orchestration and mock report

**Files:** `service.py`, `report.py`, `tests/test_report_contract.py`, `tests/test_mock_case_contract.py`.

- [ ] 6.1 Write RED service ordering/error-propagation assertions; implement typed `run_review`; rerun GREEN and assert no business verdict fields.
- [ ] 6.2 Write RED report assertions; implement mock label, version identities, locators, candidates, differences, status/pending/decision/limitations, “非 APQP 通过判定”, and no pass/fail/severity/safety/stage action; rerun GREEN.
- [ ] 6.3 Write RED assertions for all eight manifest cases, unknown safety, and ASIL C/D zero extractor/AI calls; implement service fail-closed before extractor invocation for explicit C/D, without inferring safety metadata; rerun GREEN.
- [ ] 6.4 From Q9 root run all Review Focus tests with fixed runtime; no placeholder helpers or untyped fixture factories.

### Task 7: PC mock entry and reusable Blueprint

**Files:** `webapp.py`, plus route assertions in `tests/test_report_contract.py`. Do not change shared portal registry or CI matrix in this task.

- [ ] 7.1 Write RED route tests for mock upload and report retrieval; implement importable existing-framework Blueprint `/quality/q9-apqp-evidence-review` using typed service/report, preserving auth hook and opening no port; rerun GREEN.
- [ ] 7.2 Write RED route tests for real-material/malformed/cross-customer rejection and demo actor default deny; implement explicit mock-only synthetic demo append; rerun GREEN and assert no criterion signoff.
- [ ] 7.3 Keep route tests in `tests/test_report_contract.py`; from Q9 root run with fixed runtime and assert route effects via service/audit contracts.
- [ ] 7.4 Complete the mock package independently of shared portal route registration or CI matrix edits. Document those as possible later integration items only; do not block, edit, or assume approval for shared files.

### Task 8: Verification and implementation handoff (future authorized implementation only)

**Files:** the eight test files above; no additional shared changes unless separately authorized.

- [ ] 8.1 From Q9 project root `"C:/Users/Paul Shao/.codex/worktrees/pc-mvp-1012-v2-q9/zhuopin-ai/4-数字员工/质量部/Q9-APQP阶段审查"`, run `"C:/Dev/Codex/runtimes/zhuopin-ai/venv/Scripts/python.exe" -m pytest -q --tb=short --junit-xml=pytest-result.xml`; this is the outer formal project CI contract. Never run root pytest.
- [ ] 8.2 Run the repository's applicable scene bootstrap and CI matrix checks for this Q9 child only, recording exact commands and outputs; do not claim hook trust or business acceptance from passing tests.
- [ ] 8.3 Review all changed paths against approved `allowed_paths`, scan test fixtures for customer/OEM source leakage, verify audit chain and Q4 isolation, and present unresolved platform API or scope mismatches to the outer Guardian.
- [ ] 8.4 Stop before `.51` deployment, real OEM ingestion, external send, stage release, ff merge, or formal signoff; each remains an independent authorization/release gate.

## Remaining Technical Decisions for the Outer Guardian

- Actual role/authority source authorizing Q9 L2 reviewers and G01–G06 signers remains unresolved. The mock demo actor is a distinct, default-deny synthetic actor and cannot answer that real-world question.
- Shared portal registration and shared CI matrix may be considered after the Q9 subtree mock implementation; neither is a prerequisite or implied authorization in this plan.
- No additional files or shared dependency/platform changes are in this plan; the 24-path Q9 allowlist above is fixed.

