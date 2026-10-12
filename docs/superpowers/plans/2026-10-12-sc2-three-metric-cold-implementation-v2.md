# SC2 三项指标证据合同与周报切片 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` or `superpowers:executing-plans` within the formal Guardian workflow. Every derived model must be explicitly `gpt-6-luna`; the Guardian owns execution, checks, independent review, and audit trail. Checkbox syntax tracks future work. This plan does not itself authorize implementation.

**Goal:** 在 SC2 增加默认关闭、只读且可回退的三项指标证据纵向切片，以不可变 snapshot/audit 保留来源、状态和公式证据，同时完整维持既有周报与明细行为。

**Architecture:** 在既有 `models.py`、`sources.py`、`windows.py`、`metrics.py` 内扩展证据合同与纯计算；在 `detail.py`/`config.py` 中增加隔离 v1 codec 和路径，在 `webapp.py` 接入显式 opt-in、按 snapshot ID 读取的 PC/API，在 `report.py` 只增加兼容呈现适配而不改变旧函数语义。全链使用固定 `MOCK-` fixture、公司权威日历的固定摘录、canonical hash 和 append-only audit；任何未签规则或证据缺口均 fail-closed。

**Tech Stack:** Python 3.14 项目隔离环境；既有 Flask/SC2 数据类与平台 audit 接缝；pytest；JSON fixtures；Windows PowerShell。未来产品文件只能在已批准隔离树 `C:/Users/Paul Shao/.codex/worktrees/pc-mvp-1012-v4-sc2-continuation/zhuopin-ai` 内编辑；所有测试 cwd 固定为 `C:/Users/Paul Shao/.codex/worktrees/pc-mvp-1012-v4-sc2-continuation/zhuopin-ai/4-数字员工/采购部/SC2-采购周报自动生成`，解释器固定为 `C:/Dev/Codex/runtimes/zhuopin-ai/venv/Scripts/python.exe`。

**Spec:** Approved actual design `reports/pc-mvp-1012/v2-review/sc2/design.md` (SHA-256 `9b8b7c9438a7ef309a2cecab10e64781b9f6c31e782699359d13b5e11c70959e`), requirements `reports/pc-mvp-1012/v2-review/sc2/specs/sc2-three-metric-evidence/spec.md`, proposal `reports/pc-mvp-1012/v2-review/sc2/proposal.md`, tasks `reports/pc-mvp-1012/v2-review/sc2/tasks.md`. Actual design HEAD: `b2933132b733756b30b94e309e2066bbd50d6e43`. These identifiers bind the authorized design; this plan requires its own subsequent review.

## Global Constraints

- Future implementation may edit only the 12 design-whitelisted files listed below, and only inside the approved isolated tree; any required expansion requires a revised design and separate approval. This plan-writing stage edits only this plan file.
- All fixtures and vertical-slice business rows use deterministic `MOCK-` data; never connect ERP/SRM or use production, supplier, OEM, or real employee data.
- The three replacement metrics are on-time order completion, on-time schedule confirmation, and on-time arrival; they replace the old six-item scope and are not appended to it.
- Reuse only signed facts: order deadline six working days; schedule confirmation deadline five working days; weekends/statutory holidays excluded and company overtime workdays included; arrival interval endpoints inclusive.
- Arrival planned-quantity denominator is the positive quantity on the second row under schedule date per procurement #23 paragraph 147. Department arrival rate is arithmetic mean of item rates.
- Preserve `value`, `unknown`, and `pending` distinctly. Only a complete signed formula and complete evidence can yield numeric values; valid numeric zero remains `value=0`. Do not turn missing or unsigned evidence into zero, silently exclude it, or invent a candidate.
- G01–G04 remain unsigned and are never adjudicated by code authors. Do not represent any G case as signed in test inputs. If a calculation depends on unresolved G treatment, test its `pending` path; the already signed, unambiguous arrival facts may still be calculated where no G case affects membership or attribution. G professional sign-off is not a hard prerequisite to completing the fully synthetic technical slice.
- Use only `4-数字员工/财务部/FI3-付款申请自动校验/data/holidays/holiday_calendar.csv` as authoritative runtime calendar. Record source MD5, calendar ID/version, coverage, hash, and fixture SHA. Missing/mismatched/out-of-range calendar yields `unknown`; never synthesize or extrapolate.
- New schema is `sc2_three_metric_evidence/v1`; every generation has a new UUID `snapshot_id`, stable canonical JSON/hash (excluding hash field), isolated storage, no overwrite, and ID collision fail-closed.
- New PC/API path is explicit opt-in, default disabled, read-only, and addressed only by `snapshot_id`; no mutable “latest”, source refresh, notification, purchase action, or implicit fallback.
- Append the same snapshot ID/hash and evidence/rule/calendar references to existing append-only audit. Audit append/chain verification failure means no completed result is presented; preserve failed evidence and do not delete/reuse IDs.
- Preserve old report and dataset codecs, routes, outputs, storage, golden samples, and bytes. Legacy report recognition requires `period`, `base_date`, `metrics` and absence of `schema_version`; invalid legacy data fails closed. Existing `DATASET_SCHEMA` stays strict.
- Do not touch shared platform, `notify.py`, `outbox.py`, `review.py`, old tests/goldens, #538/#539 material, BizType=316 material, CLAUDE/OpenSpec source files, deployment/publishing configuration, or any path outside the approved isolated worktree and this plan file.
- No task below is performed yet. For future runs, execute only from the isolated SC2 project cwd above, with the fixed interpreter. PowerShell commands must quote paths and invoke the interpreter explicitly, for example `& "C:/Dev/Codex/runtimes/zhuopin-ai/venv/Scripts/python.exe" -m pytest tests/test_three_metric_evidence.py -q`. CI command is `& "C:/Dev/Codex/runtimes/zhuopin-ai/venv/Scripts/python.exe" -m pytest -q --tb=short --junit-xml=pytest-result.xml` from that isolated cwd, as supplied by the approved CI evidence.
- Formal Guardian executes with explicit Luna routing, owns CI/audit/review, and may submit the sealed work for mechanical Sweep in the main repository. Child models edit only their assigned approved files and never commit or push. No ff, deployment, real-source access, or external send is authorized by this plan.

## Review Focus

1. **A valid zero vs. missing data vs. unresolved decision:** tests `test_zero_is_value_and_unknown_and_pending_have_no_numbers`, `test_missing_source_field_is_unknown`, `test_incomplete_source_is_unknown_not_zero`, `test_history_unavailable_is_unknown`, and `test_unsigned_g_cases_remain_pending` pin each state; no silent row drop.
2. **Arrival denominator and aggregation:** test second-row positive schedule quantity, inclusive arrival dates, and unweighted arithmetic mean; exercise multiple-plan/repeated receipt/return cases as pending when G02/G04 is required. Owner: Task 2 tests `test_arrival_uses_signed_second_row_and_arithmetic_mean` and `test_unresolved_arrival_attribution_is_pending`.
3. **Calendar identity and coverage:** test ordinary workday, weekend, statutory holiday, overtime workday, absent/mismatched version, and out-of-range date; never fall back to host calendar. Owner: Task 1 tests `test_calendar_is_workday_reads_exact_fixture_values` and `test_calendar_missing_version_or_date_returns_none`.
4. **Snapshot and audit fault boundaries:** test UUID collision, canonical hash mismatch, atomic no-overwrite publication, audit append/chain failure, and identical snapshot ID/hash across response and audit. Owner: Task 3 tests `test_snapshot_id_collision_preserves_existing_bytes`, `test_snapshot_hash_mismatch_rejected`, `test_audit_failure_never_publishes_complete_result`, and Task 5 `test_snapshot_id_hash_match_across_api_report_audit`.
5. **Legacy and opt-in isolation:** test new path disabled by default, explicit ID-only read, legacy report key contract, strict old dataset schema, and byte/output preservation when new path fails. Owner: Task 4 tests `test_evidence_view_is_off_by_default`, `test_explicit_snapshot_api_preserves_three_states`, `test_legacy_report_contract_and_fail_closed`, and Task 5 `test_failed_new_path_preserves_legacy_output`.

---

## File Map (fixed 12-file allowlist)

**Modify (8 existing SC2 modules):**

- `4-数字员工/采购部/SC2-采购周报自动生成/sc2/models.py` — immutable evidence/capability dataclasses and literal status/reason-code types; do not reinterpret `FrozenDataset`.
- `4-数字员工/采购部/SC2-采购周报自动生成/sc2/sources.py` — deterministic mock evidence adapter and source capability declarations; do not construct or access real connectors.
- `4-数字员工/采购部/SC2-采购周报自动生成/sc2/windows.py` — exact calendar lookup; do not infer unsigned period boundaries.
- `4-数字员工/采购部/SC2-采购周报自动生成/sc2/metrics.py` — pure derivation of three evidence states and item/dept arrival arithmetic; preserve legacy `compute_metrics` unchanged.
- `4-数字员工/采购部/SC2-采购周报自动生成/sc2/detail.py` — v1 canonical codec, validation, isolated snapshot persistence, immutable ID lookup; keep dataset codec functions unchanged.
- `4-数字员工/采购部/SC2-采购周报自动生成/sc2/config.py` — isolated v1 snapshot directory helper beneath `reports_dir()`; do not change existing report/audit locations.
- `4-数字员工/采购部/SC2-采购周报自动生成/sc2/report.py` — new evidence presentation adapter only; old `report_to_dict`, `snapshot_to_report`, `save_snapshot`, `load_snapshot` stay behaviorally identical.
- `4-数字员工/采购部/SC2-采购周报自动生成/sc2/webapp.py` — default-off opt-in PC view and read-only explicit-ID API; never call real feed, notification, or purchase mutation path.

**Create (4 synthetic verification files):**

- `4-数字员工/采购部/SC2-采购周报自动生成/tests/test_three_metric_evidence.py` — focused unit, persistence, API, compatibility, and fault tests.
- `4-数字员工/采购部/SC2-采购周报自动生成/tests/fixtures/three_metric_evidence/legacy_snapshot.json` — fixed legacy report input.
- `4-数字员工/采购部/SC2-采购周报自动生成/tests/fixtures/three_metric_evidence/new_snapshot.json` — fixed valid v1 synthetic snapshot with stable canonical hash.
- `4-数字员工/采购部/SC2-采购周报自动生成/tests/fixtures/three_metric_evidence/workday_calendar.json` — minimal fixed authoritative-calendar excerpt with provenance metadata and required day kinds.

No other file may be created or modified. The existing `tests/test_caseback_golden.py` and `tests/test_delivery.py` are read-only regressions.

## Interfaces and Shared Contracts

The following exact data types are implementation code. The function list is an API signature table only; its declarations are not implementation steps. Concrete core implementations are given in Tasks 1–4.

```python
# models.py; imports: dataclass, date, Literal, Mapping
EvidenceStatus = Literal["value", "unknown", "pending"]

@dataclass(frozen=True)
class SourceCapability:
    source_id: str
    version: str
    query_start: date | None
    query_end: date | None
    page_set_complete: bool
    history_available: bool
    missing_fields: tuple[str, ...] = ()

@dataclass(frozen=True)
class EvidenceRef:
    source_id: str
    row_id: str
    fact_at: str | None
    state_at: str | None

@dataclass(frozen=True)
class CalendarEvidence:
    calendar_id: str
    version: str
    sha256: str
    source_md5: str
    fixture_sha256: str | None
    coverage_start: date
    coverage_end: date
    days: tuple[tuple[date, bool], ...]

    @property
    def ref(self) -> str:
        return f"{self.calendar_id}@{self.version}:{self.sha256}"

@dataclass(frozen=True)
class MetricEvidence:
    key: str
    status: EvidenceStatus
    value: float | None
    numerator: float | None
    denominator: float | None
    aggregation: str | None
    reason_codes: tuple[str, ...]
    evidence_refs: tuple[EvidenceRef, ...]
    rule_refs: tuple[str, ...]
    calendar_ref: str | None

@dataclass(frozen=True)
class ThreeMetricEvidence:
    period: str
    source_capabilities: tuple[SourceCapability, ...]
    evidence_rows: tuple[Mapping[str, object], ...]
    metrics: tuple[MetricEvidence, ...]
    rule_refs: tuple[str, ...]
    workday_calendar_ref: CalendarEvidence
```

| Module | Exact signature | Behavior |
|---|---|---|
| `sources.py` | `build_synthetic_evidence() -> ThreeMetricEvidence` | Fixed MOCK-only object, same on every call. |
| `windows.py` | `load_authoritative_calendar(path: Path) -> CalendarEvidence`; `calendar_is_workday(day: date, expected_ref: str, calendar: CalendarEvidence) -> bool \| None` | Parse exact Chinese CSV columns and exact ref/date lookup only. |
| `metrics.py` | `compute_three_metric_evidence(evidence: ThreeMetricEvidence, *, signed_formula_refs: Mapping[str, str]) -> tuple[MetricEvidence, ...]` | Pure derivation, no G signed-state input. |
| `detail.py` | `canonical_evidence_bytes(payload: Mapping[str, object]) -> bytes`; `evidence_sha256(payload: Mapping[str, object]) -> str`; `validate_evidence_snapshot(payload: Mapping[str, object]) -> None`; `save_evidence_snapshot(snapshot: Mapping[str, object], *, snapshot_id: str \| None = None) -> Path`; `load_evidence_snapshot(snapshot_id: str) -> dict[str, object]`; `append_evidence_audit(event: Mapping[str, object]) -> bool` | Canonical v1 codec, strict reader/writer, audit append and verification result. |
| `config.py` | `evidence_snapshots_dir() -> Path` | Isolated evidence root below `reports_dir()`. |
| `report.py` | `evidence_to_api(snapshot: Mapping[str, object]) -> dict[str, object]`; `evidence_to_report(snapshot: Mapping[str, object]) -> dict[str, object]`; `recognize_legacy_report(snapshot: Mapping[str, object]) -> dict[str, object]` | Stable API projection; status-preserving display; strict legacy contract. |
| `webapp.py` | `three_metric_evidence_enabled() -> bool`; `get_three_metric_evidence(snapshot_id: str) -> tuple[dict[str, object] \| None, int]` | Default-off explicit ID read; never refresh source. |

**Shared test data lives only in `tests/test_three_metric_evidence.py`; do not add `conftest.py` or another file.** Define all pytest fixtures and builders in that test file using the complete definitions below. Fixture row mappings use the exact listed keys, and every serialized `evidence_refs` item is an `EvidenceRef` mapping (`source_id`, `row_id`, `fact_at`, `state_at`), never a bare string. `MetricEvidence.calendar_ref` is the internal stable identifier `calendar_id@version:sha256`; serialization resolves it against the snapshot-level `workday_calendar_ref` object and emits that complete object in each API metric. That snapshot-level object is generated from typed `CalendarEvidence` fields.

```python
import hashlib
import json
from dataclasses import replace
from datetime import date
from pathlib import Path
import pytest

from sc2.models import (CalendarEvidence, EvidenceRef, MetricEvidence, SourceCapability,
                        ThreeMetricEvidence)
from sc2.sources import build_synthetic_evidence
from sc2.windows import load_authoritative_calendar
from sc2.detail import (append_evidence_audit, canonical_evidence_bytes, evidence_sha256,
                        load_evidence_snapshot, save_evidence_snapshot, validate_evidence_snapshot)
from sc2.metrics import compute_three_metric_evidence
from sc2.report import evidence_to_report
from sc2.report import recognize_legacy_report
from sc2.webapp import create_app


def make_supported_evidence() -> ThreeMetricEvidence:
    base = build_synthetic_evidence()
    calendar = load_calendar_fixture()
    cap = SourceCapability(
        source_id="MOCK-SRM-EVIDENCE", version="fixture-v1",
        query_start=date(2026, 10, 9), query_end=date(2026, 10, 16),
        page_set_complete=True, history_available=True, missing_fields=(),
    )
    row = {
        "metric_key": "on_time_arrival", "row_id": "MOCK-ARRIVAL-001",
        "material_id": "MOCK-MATERIAL-001", "plan_publish_date": "2026-10-10",
        "schedule_date": "2026-10-10", "schedule_row_ordinal": 2,
        "planned_qty": 12, "confirmed_promise_date": "2026-10-12",
        "receipt_date": "2026-10-12", "receipt_qty": 0,
        "relation_proven": True, "history_available": True,
    }
    return replace(
        base, source_capabilities=(cap,), evidence_rows=(row,), metrics=(),
        workday_calendar_ref=calendar,
        rule_refs=("#23 paragraph 147",),
    )


def load_calendar_fixture() -> CalendarEvidence:
    path = Path(__file__).parent / "fixtures" / "three_metric_evidence" / "workday_calendar.json"
    raw = path.read_bytes()
    data = json.loads(raw.decode("utf-8"))
    days = tuple((date.fromisoformat(key), value) for key, value in sorted(data["days"].items()))
    day_bytes = json.dumps(data["days"], sort_keys=True, separators=(",", ":")).encode("utf-8")
    return CalendarEvidence(
        calendar_id=data["calendar_id"], version=data["version"],
        sha256=hashlib.sha256(day_bytes).hexdigest(),
        source_md5=data["source_md5"], fixture_sha256=hashlib.sha256(raw).hexdigest(),
        coverage_start=date.fromisoformat(data["coverage_start"]),
        coverage_end=date.fromisoformat(data["coverage_end"]), days=days,
    )


def make_incomplete_page_evidence() -> ThreeMetricEvidence:
    evidence = make_supported_evidence()
    return replace(
        evidence,
        source_capabilities=tuple(
            replace(cap, page_set_complete=False) for cap in evidence.source_capabilities
        ),
    )


def make_valid_snapshot() -> dict[str, object]:
    calendar = load_calendar_fixture()
    calendar_payload = {
        "calendar_id": calendar.calendar_id, "version": calendar.version,
        "sha256": calendar.sha256, "source_md5": calendar.source_md5,
        "fixture_sha256": calendar.fixture_sha256, "ref": calendar.ref,
        "coverage_start": calendar.coverage_start.isoformat(),
        "coverage_end": calendar.coverage_end.isoformat(),
    }
    payload: dict[str, object] = {
        "snapshot_id": "00000000-0000-4000-8000-000000000001",
        "schema_version": "sc2_three_metric_evidence/v1",
        "period": "2026-W41", "created_at_utc": "2026-10-12T00:00:00Z",
        "mode": "synthetic", "canonical_sha256": "",
        "source_capabilities": [{"source_id": "MOCK-SRM-EVIDENCE", "version": "fixture-v1",
            "query_start": "2026-10-09", "query_end": "2026-10-16",
            "page_set_complete": True, "history_available": True, "missing_fields": []}],
        "workday_calendar_ref": calendar_payload,
        "rule_refs": ["#23 paragraph 147"],
        "evidence_rows": [{
            "metric_key": "on_time_arrival", "row_id": "MOCK-ARRIVAL-001",
            "material_id": "MOCK-MATERIAL-001", "plan_publish_date": "2026-10-10",
            "schedule_date": "2026-10-10", "schedule_row_ordinal": 2,
            "planned_qty": 12, "confirmed_promise_date": "2026-10-12",
            "receipt_date": "2026-10-12", "receipt_qty": 0,
            "relation_proven": True, "history_available": True,
        }],
        "evidence_refs": [{"source_id": "MOCK-SRM-EVIDENCE", "row_id": "MOCK-ARRIVAL-001",
            "fact_at": "2026-10-12T00:00:00Z", "state_at": "2026-10-12T00:00:00Z"}],
        "metrics": [
            {"key": "on_time_order_completion", "status": "pending", "value": None,
             "numerator": None, "denominator": None, "reason_codes": ["SIGNED_FORMULA_NOT_BOUND"],
             "evidence_refs": [], "rule_refs": [], "workday_calendar_ref": None},
            {"key": "on_time_schedule_confirmation", "status": "unknown", "value": None,
             "numerator": None, "denominator": None, "reason_codes": ["HISTORY_UNAVAILABLE"],
             "evidence_refs": [], "rule_refs": [], "workday_calendar_ref": None},
            {"key": "on_time_arrival", "status": "value", "value": 0,
             "numerator": 0, "denominator": 12, "reason_codes": [],
             "evidence_refs": [{"source_id": "MOCK-SRM-EVIDENCE", "row_id": "MOCK-ARRIVAL-001",
                 "fact_at": "2026-10-12T00:00:00Z", "state_at": "2026-10-12T00:00:00Z"}],
             "rule_refs": ["#23 paragraph 147"],
             "workday_calendar_ref": calendar_payload},
        ],
    }
    payload["canonical_sha256"] = evidence_sha256(payload)
    return payload


@pytest.fixture
def supported_evidence() -> ThreeMetricEvidence:
    return make_supported_evidence()


@pytest.fixture
def incomplete_page_evidence() -> ThreeMetricEvidence:
    return make_incomplete_page_evidence()


@pytest.fixture
def valid_snapshot() -> dict[str, object]:
    fixture_path = Path(__file__).parent / "fixtures" / "three_metric_evidence" / "new_snapshot.json"
    loaded = json.loads(fixture_path.read_text(encoding="utf-8"))
    assert loaded == make_valid_snapshot()
    validate_evidence_snapshot(loaded)
    return loaded


@pytest.fixture
def saved_snapshot(tmp_path, monkeypatch, valid_snapshot, audit_events):
    monkeypatch.setattr("sc2.config.evidence_snapshots_dir", lambda: tmp_path)
    save_evidence_snapshot(valid_snapshot)
    return load_evidence_snapshot(valid_snapshot["snapshot_id"])


@pytest.fixture
def audit_events(monkeypatch):
    events = []
    def record_mock_adapter(event):
        events.append({
            "scenario": "SC2",
            "action": "sc2_three_metric_evidence.snapshot_published",
            "evaluator": "MOCK-SC2-three-metric-evidence/v1",
            "automation_level": "L1",
            "decision": {"status": "evidence_snapshot_published"},
            "data_sources": {"snapshot_id": event["snapshot_id"],
                              "schema_version": "sc2_three_metric_evidence/v1"},
            "content_hash": event["canonical_sha256"],
        })
        return True
    monkeypatch.setattr("sc2.detail.append_evidence_audit", record_mock_adapter)
    return events


@pytest.fixture
def legacy_snapshot():
    fixture_path = Path(__file__).parent / "fixtures" / "three_metric_evidence" / "legacy_snapshot.json"
    return json.loads(fixture_path.read_text(encoding="utf-8"))


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("SC2_THREE_METRIC_EVIDENCE_ENABLED", "0")
    monkeypatch.setattr("sc2.webapp.install_flask_gate", lambda *args, **kwargs: None)
    monkeypatch.setattr("sc2.webapp.install_flask_access_log", lambda *args, **kwargs: None)
    app = create_app(base_date=date(2026, 10, 12), mode="mock")
    app.config.update(TESTING=True)
    return app.test_client()
```

The concrete row keys shown above become the internal synthetic row contract. Extend with deterministic `MOCK-` rows for unknown/pending branches. G01–G04 are never supplied as signed. For `saved_snapshot`, patch the actual audit adapter function introduced in Task 3 and persist through `save_evidence_snapshot`; do not add a stub in production code or `conftest.py`. Verify and use the actual adapter name in Task 3 before implementing that fixture.

Serialization contract: API metric object contains `status`, `value`, `numerator`, `denominator`, `reason_codes`, `evidence_refs`, `snapshot_id`, `schema_version`, `rule_refs`, and `workday_calendar_ref`. For `unknown` or `pending`, numeric fields are all JSON `null`. Valid zero is JSON number `0`. For simultaneous unknown and pending causes, preserve all codes and render both labels.

## Tasks

### Task 1: Pin the synthetic source, immutable types, and calendar contract

**Files:**
- Modify: `4-数字员工/采购部/SC2-采购周报自动生成/sc2/models.py`
- Modify: `4-数字员工/采购部/SC2-采购周报自动生成/sc2/sources.py`
- Modify: `4-数字员工/采购部/SC2-采购周报自动生成/sc2/windows.py`
- Create: `4-数字员工/采购部/SC2-采购周报自动生成/tests/fixtures/three_metric_evidence/workday_calendar.json`
- Test: `4-数字员工/采购部/SC2-采购周报自动生成/tests/test_three_metric_evidence.py`

**Interfaces:** consumes existing SC2 model conventions; produces `SourceCapability`, `EvidenceRef`, `CalendarEvidence`, `MetricEvidence`, `ThreeMetricEvidence`, `build_synthetic_evidence()`, and `calendar_is_workday()` exactly as declared above.

- [ ] **Step 1: Add contract tests first.** Add `test_synthetic_source_is_fixed_and_mock_only`, `test_calendar_is_workday_reads_exact_fixture_values`, and `test_calendar_missing_version_or_date_returns_none`. Assert all IDs begin `MOCK-`, repeated factory calls compare equal, source capability does not claim an ERP/SRM endpoint, and calendar lookup returns only its exact supplied `True`/`False` value or `None` when the ref/date is absent. Do not test a deadline date or whether its start day counts; neither is signed.

```python
def test_synthetic_source_is_fixed_and_mock_only():
    first = build_synthetic_evidence()
    second = build_synthetic_evidence()
    assert first == second
    assert first.source_capabilities
    assert all(c.source_id.startswith("MOCK-") for c in first.source_capabilities)
    assert all("endpoint" not in c.source_id.lower() for c in first.source_capabilities)


def test_calendar_is_workday_reads_exact_fixture_values():
    calendar = load_calendar_fixture()
    fixture_path = Path(__file__).parent / "fixtures" / "three_metric_evidence" / "workday_calendar.json"
    fixture_data = json.loads(fixture_path.read_text(encoding="utf-8"))
    assert calendar == load_calendar_fixture()
    assert len(calendar.sha256) == len(calendar.fixture_sha256) == 64
    assert calendar.source_md5 == "8e5295e84d310477722b5bfc353e88be"
    assert calendar_is_workday(date(2026, 10, 1), calendar.ref, calendar) is False
    assert fixture_data["day_kinds"]["2026-10-01"] == "法定节假日"
    assert calendar_is_workday(date(2026, 10, 9), calendar.ref, calendar) is True
    assert calendar_is_workday(date(2026, 10, 10), calendar.ref, calendar) is True
    assert fixture_data["day_kinds"]["2026-10-10"] == "调休上班日"
    assert calendar_is_workday(date(2026, 10, 11), calendar.ref, calendar) is False
    assert fixture_data["day_kinds"]["2026-10-11"] == "周末"
    assert calendar_is_workday(date(2026, 10, 12), calendar.ref, calendar) is True
    assert calendar_is_workday(date(2026, 10, 17), calendar.ref, calendar) is None
    assert calendar_is_workday(date(2026, 10, 10), "MOCK-CALENDAR@wrong:bad", calendar) is None


def test_authoritative_calendar_parser_uses_explicit_boolean_column(tmp_path):
    path = tmp_path / "holiday_calendar.csv"
    path.write_text(
        "日期,星期,节假日名称,日期类型,是否工作日\n"
        "2026-10-10,周六,国庆节调休,调休上班,是\n"
        "2026-10-11,周日,,周末,否\n", encoding="utf-8")
    calendar = load_authoritative_calendar(path)
    assert calendar_is_workday(date(2026, 10, 10), calendar.ref, calendar) is True
    assert calendar_is_workday(date(2026, 10, 11), calendar.ref, calendar) is False
    assert calendar_is_workday(date(2026, 10, 12), calendar.ref, calendar) is None
```

- [ ] **Step 2: Run only the new tests and confirm the contract is absent.** From the isolated SC2 cwd run `& "C:/Dev/Codex/runtimes/zhuopin-ai/venv/Scripts/python.exe" -m pytest tests/test_three_metric_evidence.py -k 'synthetic_source or calendar' -q`; expected initial failure is import/name failure for the not-yet-created contract.
- [ ] **Step 3: Add the fixed calendar fixture and immutable dataclasses.** Fixture records source path, source MD5 `8e5295e84d310477722b5bfc353e88be`, calendar ID/version, coverage, and fixed dates that include ordinary workday, weekend, statutory holiday, and overtime workday. Store `is_workday` booleans; fixture contains no procurement rows. In particular `2026-10-09`, `2026-10-10` (国庆节调休/调休上班/是), and `2026-10-12` through `2026-10-16` are `true`; `2026-10-11` is `false`. Add types with `frozen=True`; keep existing dataclass defaults and old dataset types unchanged.

```json
{
  "calendar_id": "MOCK-CALENDAR",
  "version": "fixture-v1",
  "source_md5": "8e5295e84d310477722b5bfc353e88be",
  "coverage_start": "2026-01-01",
  "coverage_end": "2028-01-15",
  "day_kinds": {
    "2026-10-01": "法定节假日",
    "2026-10-09": "工作日",
    "2026-10-10": "调休上班日",
    "2026-10-11": "周末",
    "2026-10-12": "工作日",
    "2026-10-13": "工作日",
    "2026-10-14": "工作日",
    "2026-10-15": "工作日",
    "2026-10-16": "工作日"
  },
  "days": {
    "2026-10-01": false,
    "2026-10-09": true,
    "2026-10-10": true,
    "2026-10-11": false,
    "2026-10-12": true,
    "2026-10-13": true,
    "2026-10-14": true,
    "2026-10-15": true,
    "2026-10-16": true
  }
}
```

The JSON is the entire contents of `tests/fixtures/three_metric_evidence/workday_calendar.json`; the selected `days` are a sparse test excerpt, so `calendar_is_workday` returns `None` for omitted dates even when within the source file's overall coverage. Compute the excerpt `sha256` from its sorted compact `days` object and `fixture_sha256` from the exact UTF-8 fixture bytes; store both separately in each snapshot. The executable test verifies the computed hashes are stable and 64 lowercase hex characters.
- [ ] **Step 4: Implement the deterministic mock adapter, authoritative CSV reader, and exact calendar lookup.** `build_synthetic_evidence()` returns fixed source IDs, facts, capabilities, and typed `CalendarEvidence` built from the JSON fixture. `load_authoritative_calendar(path)` reads only headers `日期` and `是否工作日`, parses only literal `是`/`否`, records raw-file MD5 and SHA-256, uses the MD5 as calendar version, and records min/max parsed dates as coverage. Any missing header, invalid date, unexpected boolean token, or empty CSV raises `ValueError`; no weekday or holiday inference. Runtime resolves the checked-in file as `<project-root>/4-数字员工/财务部/FI3-付款申请自动校验/data/holidays/holiday_calendar.csv`. `calendar_is_workday(day, expected_ref, calendar)` requires exact `expected_ref == calendar.ref`, checks coverage, then returns mapped boolean or `None` for an omitted date. Do not calculate deadlines or decide whether the start day counts.

```python
import csv
import hashlib
from pathlib import Path

def load_authoritative_calendar(path: Path) -> CalendarEvidence:
    raw = path.read_bytes()
    reader = csv.DictReader(raw.decode("utf-8-sig").splitlines())
    if not {"日期", "是否工作日"} <= set(reader.fieldnames or ()):
        raise ValueError("authoritative calendar headers missing")
    rows = []
    for row in reader:
        day = date.fromisoformat(row["日期"])
        token = row["是否工作日"]
        if token not in {"是", "否"}:
            raise ValueError(f"invalid calendar workday value on {day.isoformat()}")
        rows.append((day, token == "是"))
    if not rows:
        raise ValueError("authoritative calendar is empty")
    source_md5 = hashlib.md5(raw).hexdigest()
    return CalendarEvidence(
        calendar_id="company-holiday-calendar", version=source_md5,
        sha256=hashlib.sha256(raw).hexdigest(), source_md5=source_md5,
        fixture_sha256=None, coverage_start=min(day for day, _ in rows),
        coverage_end=max(day for day, _ in rows), days=tuple(rows),
    )


def calendar_is_workday(day: date, expected_ref: str, calendar: CalendarEvidence) -> bool | None:
    if expected_ref != calendar.ref:
        return None
    if day < calendar.coverage_start or day > calendar.coverage_end:
        return None
    return dict(calendar.days).get(day)
```
- [ ] **Step 5: Re-run focused tests.** Same command; expected PASS. Add assertions for missing fields and `page_set_complete=False` metadata being retained rather than normalized away.
- [ ] **Step 6: Review task boundary.** Confirm diff contains only three assigned files and no calls to connector builders; no commit.

### Task 2: Derive the three statuses and signed arrival arithmetic

**Files:**
- Modify: `4-数字员工/采购部/SC2-采购周报自动生成/sc2/metrics.py`
- Test: `4-数字员工/采购部/SC2-采购周报自动生成/tests/test_three_metric_evidence.py`

**Interfaces:** consumes Task 1 evidence objects; produces `compute_three_metric_evidence(evidence, *, signed_formula_refs)` returning exactly three ordered `MetricEvidence` values keyed `on_time_order_completion`, `on_time_schedule_confirmation`, and `on_time_arrival`. There is deliberately no test input or code parameter that marks G01–G04 as signed. Existing `compute_metrics()` signature and results remain unchanged.

- [ ] **Step 1: Write state-separation tests.** Include a complete synthetic zero under the already signed arrival definition; an absent required field; incomplete page set; unavailable history; an unbound order/schedule formula; and each unsigned G code. Assert values and fractions exist only for `value`, and exact applicable reason codes survive.

```python
def test_zero_is_value_and_unknown_and_pending_have_no_numbers(supported_evidence):
    metrics = compute_three_metric_evidence(
        supported_evidence,
        signed_formula_refs={"on_time_arrival": "#23 paragraph 147"},
    )
    by_key = {m.key: m for m in metrics}
    zero = by_key["on_time_arrival"]
    assert (zero.status, zero.value, zero.numerator, zero.denominator) == ("value", 0, 0, 12)
    assert by_key["on_time_order_completion"].status == "pending"
    assert "SIGNED_FORMULA_NOT_BOUND" in by_key["on_time_order_completion"].reason_codes


def test_incomplete_source_is_unknown_not_zero(incomplete_page_evidence):
    result = compute_three_metric_evidence(incomplete_page_evidence, signed_formula_refs={})
    arrival = next(m for m in result if m.key == "on_time_arrival")
    assert arrival.status == "unknown"
    assert arrival.value is None and arrival.numerator is None and arrival.denominator is None
    assert "PAGE_SET_INCOMPLETE" in arrival.reason_codes


def test_missing_source_field_is_unknown(supported_evidence):
    capability = replace(supported_evidence.source_capabilities[0], missing_fields=("receipt_qty",))
    result = compute_three_metric_evidence(
        replace(supported_evidence, source_capabilities=(capability,)),
        signed_formula_refs={"on_time_arrival": "#23 paragraph 147"})
    arrival = next(item for item in result if item.key == "on_time_arrival")
    assert arrival.status == "unknown"
    assert arrival.reason_codes == ("SOURCE_FIELD_MISSING",)
    assert arrival.value is None and arrival.numerator is None and arrival.denominator is None


def test_history_unavailable_is_unknown(supported_evidence):
    capability = replace(supported_evidence.source_capabilities[0], history_available=False)
    result = compute_three_metric_evidence(
        replace(supported_evidence, source_capabilities=(capability,)),
        signed_formula_refs={"on_time_arrival": "#23 paragraph 147"})
    arrival = next(item for item in result if item.key == "on_time_arrival")
    assert arrival.status == "unknown"
    assert "HISTORY_UNAVAILABLE" in arrival.reason_codes
    assert arrival.value is None


def test_arrival_uses_signed_second_row_and_arithmetic_mean(supported_evidence):
    first = dict(supported_evidence.evidence_rows[0])
    first.update({"planned_qty": 10, "receipt_qty": 5, "receipt_date": "2026-10-10"})
    second = {**first, "row_id": "MOCK-ARRIVAL-002", "material_id": "MOCK-MATERIAL-002",
              "planned_qty": 4, "receipt_qty": 3, "receipt_date": "2026-10-12"}
    evidence = replace(supported_evidence, evidence_rows=(first, second))
    result = compute_three_metric_evidence(
        evidence, signed_formula_refs={"on_time_arrival": "#23 paragraph 147"})
    arrival = next(item for item in result if item.key == "on_time_arrival")
    assert arrival.status == "value"
    assert arrival.aggregation == "arithmetic_mean_of_item_rates"
    assert arrival.value == pytest.approx((5 / 10 + 3 / 4) / 2)


def test_unresolved_arrival_attribution_is_pending(supported_evidence):
    first = dict(supported_evidence.evidence_rows[0])
    duplicate_plan = {**first, "row_id": "MOCK-ARRIVAL-002", "schedule_row_ordinal": 3}
    evidence = replace(supported_evidence, evidence_rows=(first, duplicate_plan))
    result = compute_three_metric_evidence(
        evidence, signed_formula_refs={"on_time_arrival": "#23 paragraph 147"})
    arrival = next(item for item in result if item.key == "on_time_arrival")
    assert arrival.status == "pending"
    assert "G02" in arrival.reason_codes
    assert arrival.value is None and arrival.denominator is None


@pytest.mark.parametrize("case_code", ["G01", "G02", "G03", "G04"])
def test_unsigned_g_cases_remain_pending(supported_evidence, case_code):
    row = dict(supported_evidence.evidence_rows[0])
    if case_code == "G01":
        row["metric_key"] = "on_time_order_completion"
    else:
        row["requires_case"] = case_code
    result = compute_three_metric_evidence(
        replace(supported_evidence, evidence_rows=(row,)),
        signed_formula_refs={"on_time_arrival": "#23 paragraph 147"})
    target = "on_time_order_completion" if case_code == "G01" else "on_time_arrival"
    result_item = next(item for item in result if item.key == target)
    assert result_item.status == "pending"
    expected_reason = "G03_ZERO_DENOMINATOR" if case_code == "G03" else case_code
    assert expected_reason in result_item.reason_codes


def test_zero_denominator_waits_for_g03(supported_evidence):
    row = {**supported_evidence.evidence_rows[0], "planned_qty": 0, "schedule_row_ordinal": 2,
           "requires_case": "G03"}
    result = compute_three_metric_evidence(
        replace(supported_evidence, evidence_rows=(row,)),
        signed_formula_refs={"on_time_arrival": "#23 paragraph 147"})
    arrival = next(item for item in result if item.key == "on_time_arrival")
    assert arrival.status == "pending"
    assert "G03_ZERO_DENOMINATOR" in arrival.reason_codes
    assert arrival.value is None and arrival.denominator is None
```

- [ ] **Step 2: Run the two focused tests and confirm failure.** From the isolated SC2 cwd run `& "C:/Dev/Codex/runtimes/zhuopin-ai/venv/Scripts/python.exe" -m pytest tests/test_three_metric_evidence.py -k 'zero_is_value or incomplete_source' -q`; expected failure is missing new API.
- [ ] **Step 3: Implement pure state derivation.** Required evidence missing, page set incomplete, relation unproven, history unavailable, or calendar invalid → `unknown` plus all applicable source reason codes. Formula not explicitly bound → `pending/SIGNED_FORMULA_NOT_BOUND`. If a result depends on an unsigned G01, G02, G03, or G04 treatment, it is `pending` with that case code; no API argument or test marks any G case signed. A zero denominator dependent on G03 → `pending/G03_ZERO_DENOMINATOR`. Non-value numeric properties are `None`.
- [ ] **Step 4: Implement arrival calculation with the signed denominator.** Match only established same-item attribution, count receipts in inclusive plan-publication-to-positive-confirmed-promise interval, use the positive second schedule-date row as item denominator, and compute department metric as arithmetic mean of eligible item rates. Any unresolved multi-plan/repeated receipt/return/void membership requiring G02/G04, or zero denominator requiring G03, makes the affected item and aggregate pending. Never silently drop an unresolved member. Only perform this calculation when the supporting formula and relevant decisions are bound; otherwise use pending.

```python
from typing import Mapping
from .models import EvidenceRef, MetricEvidence, ThreeMetricEvidence

def _state(key, status, *, value=None, numerator=None, denominator=None,
           aggregation=None, reasons=(), evidence_refs=(), rule_refs=(), calendar_ref=None):
    if status != "value":
        value = numerator = denominator = None
    return MetricEvidence(key, status, value, numerator, denominator, aggregation,
                          tuple(sorted(set(reasons))), tuple(evidence_refs),
                          tuple(rule_refs), calendar_ref)


def _arrival(rows, signed: bool, calendar_ref: str):
    if not signed:
        return _state("on_time_arrival", "pending", reasons=("SIGNED_FORMULA_NOT_BOUND",))
    required = {"material_id", "schedule_row_ordinal", "planned_qty", "receipt_date",
                "plan_publish_date", "confirmed_promise_date", "receipt_qty", "relation_proven"}
    if any(not required <= row.keys() for row in rows):
        return _state("on_time_arrival", "unknown", reasons=("SOURCE_FIELD_MISSING",))
    if any(not row["relation_proven"] for row in rows):
        return _state("on_time_arrival", "unknown", reasons=("RELATION_UNPROVEN",))
    if any(row.get("requires_case") in {"G02", "G04"} for row in rows):
        cases = tuple(row["requires_case"] for row in rows if row.get("requires_case") in {"G02", "G04"})
        return _state("on_time_arrival", "pending", reasons=cases)
    if any(row.get("requires_case") == "G03" for row in rows):
        return _state("on_time_arrival", "pending", reasons=("G03_ZERO_DENOMINATOR",))
    rates = []
    seen_items = set()
    for row in rows:
        item_id = row["material_id"]
        if item_id in seen_items:
            return _state("on_time_arrival", "pending", reasons=("G02",))
        seen_items.add(item_id)
        if row["schedule_row_ordinal"] != 2:
            return _state("on_time_arrival", "pending", reasons=("G02",))
        if row["planned_qty"] <= 0:
            return _state("on_time_arrival", "pending", reasons=("G03_ZERO_DENOMINATOR",))
        if row["receipt_qty"] < 0:
            return _state("on_time_arrival", "pending", reasons=("G04",))
        if row["receipt_date"] < row["plan_publish_date"] or row["receipt_date"] > row["confirmed_promise_date"]:
            on_time_qty = 0
        else:
            on_time_qty = row["receipt_qty"]
        rates.append((on_time_qty, row["planned_qty"], row["row_id"]))
    if not rates:
        return _state("on_time_arrival", "pending", reasons=("G03_ZERO_DENOMINATOR",))
    mean_rate_sum = sum(num / den for num, den, _ in rates)
    value = mean_rate_sum / len(rates)
    refs = tuple(EvidenceRef("MOCK-SRM-EVIDENCE", row_id, None, None) for _, _, row_id in rates)
    return _state("on_time_arrival", "value", value=value,
                  numerator=mean_rate_sum, denominator=len(rates),
                  aggregation="arithmetic_mean_of_item_rates", evidence_refs=refs,
                  rule_refs=("#23 paragraph 147",), calendar_ref=calendar_ref)


def compute_three_metric_evidence(evidence: ThreeMetricEvidence, *, signed_formula_refs: Mapping[str, str]) -> tuple[MetricEvidence, ...]:
    keys = ("on_time_order_completion", "on_time_schedule_confirmation", "on_time_arrival")
    result = []
    for key in keys:
        rows = tuple(row for row in evidence.evidence_rows if row["metric_key"] == key)
        missing = any(cap.missing_fields for cap in evidence.source_capabilities)
        incomplete = any(not cap.page_set_complete for cap in evidence.source_capabilities)
        no_history = any(not cap.history_available for cap in evidence.source_capabilities)
        if missing or incomplete or no_history:
            reasons = []
            if missing:
                reasons.append("SOURCE_FIELD_MISSING")
            if incomplete:
                reasons.append("PAGE_SET_INCOMPLETE")
            if no_history:
                reasons.append("HISTORY_UNAVAILABLE")
            result.append(_state(key, "unknown", reasons=reasons))
            continue
        case_set = {row["requires_case"] for row in rows if row.get("requires_case")}
        cases = tuple(sorted("G03_ZERO_DENOMINATOR" if case == "G03" else case for case in case_set))
        if cases:
            result.append(_state(key, "pending", reasons=cases))
            continue
        if key not in signed_formula_refs:
            result.append(_state(key, "pending", reasons=("SIGNED_FORMULA_NOT_BOUND",)))
            continue
        if key != "on_time_arrival":
            result.append(_state(key, "pending", reasons=("SIGNED_FORMULA_NOT_BOUND",)))
            continue
        result.append(_arrival(rows, True, evidence.workday_calendar_ref.ref))
    return tuple(result)
```

The implementation must first classify missing fields/history/page-set/calendar as `unknown`, and unresolved G cases as `pending`, before calling `_arrival`; the snippet fixes state construction and signed arrival arithmetic. Per-item numerator/denominator remain available in the evidence rows; department `value` is the arithmetic mean, not the quotient of those summed totals.
- [ ] **Step 5: Re-run focused tests and add all reason-code combinations.** From the isolated SC2 cwd run `& "C:/Dev/Codex/runtimes/zhuopin-ai/venv/Scripts/python.exe" -m pytest tests/test_three_metric_evidence.py -k 'zero_is_value or incomplete_source or arrival_' -q`; assert simultaneous unknown+pending retains both code classes.
- [ ] **Step 6: Prove old metric path is intact.** From the isolated SC2 cwd run `& "C:/Dev/Codex/runtimes/zhuopin-ai/venv/Scripts/python.exe" -m pytest tests/test_metrics.py -q`; compare expected existing outputs, and make no edits to that test.

### Task 3: Canonical v1 codec, isolated immutable persistence, and audit evidence

**Files:**
- Modify: `4-数字员工/采购部/SC2-采购周报自动生成/sc2/detail.py`
- Modify: `4-数字员工/采购部/SC2-采购周报自动生成/sc2/config.py`
- Create: `4-数字员工/采购部/SC2-采购周报自动生成/tests/fixtures/three_metric_evidence/new_snapshot.json`
- Test: `4-数字员工/采购部/SC2-采购周报自动生成/tests/test_three_metric_evidence.py`

**Interfaces:** consumes typed evidence and Task 1/2 contracts; produces codec/persistence functions and `config.evidence_snapshots_dir()` as specified. Existing dataset codec functions remain untouched. Audit uses existing `config.audit_path()` only.

- [ ] **Step 1: Pin canonical encoding and validation.** Test UTF-8 stable key ordering, fixed date/number representation, hash excludes `canonical_sha256`, schema literal, UUID format, all three metric objects, and null numeric values for unresolved statuses.

```python
def test_canonical_hash_is_stable_and_excludes_hash_member(valid_snapshot):
    first = evidence_sha256(valid_snapshot)
    with_hash = {**valid_snapshot, "canonical_sha256": first}
    assert evidence_sha256(with_hash) == first
    assert canonical_evidence_bytes(valid_snapshot) == canonical_evidence_bytes(
        dict(reversed(list(valid_snapshot.items())))
    )
    broken = {**with_hash, "schema_version": "sc2_dataset/v1"}
    with pytest.raises(ValueError):
        validate_evidence_snapshot(broken)


def test_snapshot_id_collision_preserves_existing_bytes(tmp_path, monkeypatch, valid_snapshot):
    monkeypatch.setattr("sc2.config.evidence_snapshots_dir", lambda: tmp_path)
    monkeypatch.setattr("sc2.detail.append_evidence_audit", lambda event: True)
    first_path = save_evidence_snapshot(valid_snapshot)
    original = first_path.read_bytes()
    changed = {**valid_snapshot, "created_at_utc": "2026-10-13T00:00:00Z", "canonical_sha256": ""}
    changed["canonical_sha256"] = evidence_sha256(changed)
    with pytest.raises(FileExistsError):
        save_evidence_snapshot(changed, snapshot_id=valid_snapshot["snapshot_id"])
    assert first_path.read_bytes() == original


def test_snapshot_hash_mismatch_rejected(valid_snapshot):
    corrupt = {**valid_snapshot, "period": "2026-W42"}
    with pytest.raises(ValueError, match="hash"):
        validate_evidence_snapshot(corrupt)


def test_audit_failure_never_publishes_complete_result(tmp_path, monkeypatch, valid_snapshot):
    monkeypatch.setattr("sc2.config.evidence_snapshots_dir", lambda: tmp_path)
    monkeypatch.setattr("sc2.detail.append_evidence_audit", lambda event: False)
    with pytest.raises(RuntimeError, match="audit"):
        save_evidence_snapshot(valid_snapshot)
    # Failed evidence is retained for diagnosis; public lookup must reject it.
    path = tmp_path / valid_snapshot["period"] / (valid_snapshot["snapshot_id"] + ".json")
    assert path.exists()
    with pytest.raises(RuntimeError):
        load_evidence_snapshot(valid_snapshot["snapshot_id"])
```

- [ ] **Step 2: Run codec tests and confirm missing implementation.** From the isolated SC2 cwd run `& "C:/Dev/Codex/runtimes/zhuopin-ai/venv/Scripts/python.exe" -m pytest tests/test_three_metric_evidence.py -k 'canonical_hash or evidence_snapshot_schema' -q`; expected failure is missing codec functions.
- [ ] **Step 3: Implement canonical codec and strict validator.** Serialize sorted keys, compact separators, UTF-8, deterministic ISO dates/numeric representation. Compute SHA-256 with hash member omitted. Validate schema, UUID, required provenance, exact three metric keys, legal state, null/non-null numeric contract, reason/evidence arrays, and applicable calendar/rule refs.

```python
from typing import Mapping
import hashlib
import json

def canonical_evidence_bytes(payload: Mapping[str, object]) -> bytes:
    unsigned = {key: value for key, value in payload.items() if key != "canonical_sha256"}
    return json.dumps(unsigned, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")


def evidence_sha256(payload: Mapping[str, object]) -> str:
    return hashlib.sha256(canonical_evidence_bytes(payload)).hexdigest()


def validate_evidence_snapshot(payload: Mapping[str, object]) -> None:
    import re
    import math
    required = {"snapshot_id", "schema_version", "period", "created_at_utc", "mode",
                "canonical_sha256", "source_capabilities", "workday_calendar_ref",
                "rule_refs", "evidence_rows", "evidence_refs", "metrics"}
    if not required <= payload.keys() or payload["schema_version"] != "sc2_three_metric_evidence/v1":
        raise ValueError("schema or required fields invalid")
    if re.fullmatch(r"[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}", str(payload["snapshot_id"])) is None:
        raise ValueError("snapshot_id must be UUID v4")
    if evidence_sha256(payload) != payload["canonical_sha256"]:
        raise ValueError("canonical hash mismatch")
    if payload["mode"] != "synthetic":
        raise ValueError("v1 slice accepts synthetic evidence only")
    if not all(str(capability["source_id"]).startswith("MOCK-")
               for capability in payload["source_capabilities"]):
        raise ValueError("source capability must be MOCK-only")
    calendar = payload["workday_calendar_ref"]
    if not {"calendar_id", "version", "sha256", "source_md5", "fixture_sha256", "ref",
            "coverage_start", "coverage_end"} <= calendar.keys():
        raise ValueError("calendar provenance incomplete")
    metrics = payload["metrics"]
    expected = {"on_time_order_completion", "on_time_schedule_confirmation", "on_time_arrival"}
    if len(metrics) != 3 or {metric["key"] for metric in metrics} != expected:
        raise ValueError("three metric keys required")
    for metric in metrics:
        if not {"status", "value", "numerator", "denominator", "reason_codes",
                "evidence_refs", "rule_refs", "workday_calendar_ref"} <= metric.keys():
            raise ValueError("metric evidence fields incomplete")
        if not isinstance(metric["reason_codes"], list) or not isinstance(metric["evidence_refs"], list):
            raise ValueError("reason_codes and evidence_refs must be arrays")
        numeric = (metric["value"], metric["numerator"], metric["denominator"])
        if metric["status"] not in {"value", "unknown", "pending"}:
            raise ValueError("invalid evidence status")
        if metric["status"] == "value" and any(value is None for value in numeric):
            raise ValueError("value status requires numeric fields")
        if metric["status"] == "value" and (metric["denominator"] <= 0 or
                any(not isinstance(value, (int, float)) or isinstance(value, bool) or not math.isfinite(value)
                    for value in numeric)):
            raise ValueError("value status requires finite numbers and positive denominator")
        if metric["status"] != "value" and any(value is not None for value in numeric):
            raise ValueError("unresolved status must have null numeric fields")
        if metric["status"] != "value" and not metric["reason_codes"]:
            raise ValueError("unresolved status requires a reason code")
```
- [ ] **Step 4: Implement isolated path and no-overwrite atomic persistence.** Path is `reports_dir()/sc2_three_metric_evidence/<period>/<snapshot_id>.json`. Write a unique same-volume temporary file, flush/close, parse and rehash it, then publish with no-overwrite atomic hardlink creation. Existing target ID fails closed; never unlink a collision. Reader validates path-safe UUID, schema, and content hash. Old `save_dataset/load_dataset` remain unchanged.

```python
import json
import os
from collections.abc import Mapping
from pathlib import Path
from uuid import uuid4

def _publish_no_overwrite(target: Path, content: bytes,
                          audit_event: Mapping[str, object]) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        raise FileExistsError(target)
    reservation = target.with_name(f".{target.name}.reserved")
    # Exclusive permanent reservation prevents two writers auditing the same UUID.
    with reservation.open("xb") as stream:
        stream.write(str(audit_event["canonical_sha256"]).encode("ascii"))
        stream.flush()
        os.fsync(stream.fileno())
    temporary = target.with_name(f".{target.name}.{uuid4().hex}.pending")
    with temporary.open("xb") as stream:
        stream.write(content)
        stream.flush()
        os.fsync(stream.fileno())
    readback = json.loads(temporary.read_text(encoding="utf-8"))
    validate_evidence_snapshot(readback)
    if (readback["snapshot_id"] != audit_event["snapshot_id"] or
            readback["canonical_sha256"] != audit_event["canonical_sha256"]):
        raise ValueError("snapshot/audit identity mismatch")
    if not append_evidence_audit(audit_event):
        raise ValueError("audit commit barrier failed")
    os.link(temporary, target)
    # Keep reservations and pending evidence; never overwrite/delete a prior UUID.
```

The writer passes full snapshot JSON bytes including canonical_sha256 and the same bound audit metadata to this private helper. It reserves the UUID, writes and verifies pending bytes, verifies audit, then publishes by no-replace hardlink. Failures retain reservations/pending evidence; a new generation uses a new UUID. The reader verifies schema/hash plus exactly one matching audit event and a valid chain before returning any result, without appending another audit event. `os.link` fails if the target already exists and never overwrites it. If this filesystem does not support same-volume hardlinks, stop and revise the design's publication primitive before implementation; do not silently switch to an overwrite-capable rename.
- [ ] **Step 5: Append, re-read, and verify audit before publishing.** Keep `config.audit_path()` and the existing review/config audit behavior unchanged. In `detail.py`, implement `append_evidence_audit(event: Mapping[str, object]) -> bool` using the verified interface `AuditLogger.jsonl(config.audit_path())`, `logger.verify_chain()`, `logger.record(AuditEvent(...))`, and `logger.query_by(scenario="SC2", action="sc2_three_metric_evidence.snapshot_published")`. The order is strict: verify the pre-write chain is `.ok`; append one event; query by the two supported top-level exact filters; locally select records whose `decision.get("status") == "evidence_snapshot_published"`, whose `content_hash` equals the requested hash, and whose `data_sources` mapping has exact `snapshot_id` and `schema_version` values; require exactly one match; verify the post-write chain is `.ok`; only then return `True`. `AuditEvent` uses named actual fields `scenario`, `action`, `evaluator`, `automation_level`, `decision`, `data_sources`, and `content_hash`. Set `evaluator="MOCK-SC2-three-metric-evidence/v1"` and `automation_level="L1"`; never put a human name or signed G code in either field. `data_sources` is the actual `dict[str, str]` contract; set it to `{"snapshot_id": snapshot_id, "schema_version": "sc2_three_metric_evidence/v1"}`. Use the canonical snapshot hash as `content_hash`; period/status/evidence/rule/calendar references are projected into the decision mapping and retain the same bound snapshot/hash; business row originals stay in the snapshot itself. If pre/post chain verification fails, record/query raises, zero or multiple matching records are found, or ID/hash/decision does not match, return `False`; the snapshot remains unpublished and the reader rejects it. At implementation time Guardian records source hashes and rechecks these methods as a general precondition.

```python
from collections.abc import Mapping
from zhuopin_platform.audit.events import AuditEvent
from zhuopin_platform.audit.logger import AuditLogger
from . import config

def append_evidence_audit(event: Mapping[str, object]) -> bool:
    try:
        logger = AuditLogger.jsonl(config.audit_path())
        before = logger.verify_chain()
        if not before.ok:
            return False
        snapshot_id = str(event["snapshot_id"])
        snapshot_hash = str(event["canonical_sha256"])
        source_markers = {
            "snapshot_id": snapshot_id,
            "schema_version": "sc2_three_metric_evidence/v1",
        }
        audit_event = AuditEvent(
            scenario="SC2",
            action="sc2_three_metric_evidence.snapshot_published",
            evaluator="MOCK-SC2-three-metric-evidence/v1",
            automation_level="L1",
            decision={"status": "evidence_snapshot_published", "snapshot_id": snapshot_id,
                      "period": str(event.get("period", "")),
                      "metric_statuses": list(event.get("metric_statuses", ())),
                      "evidence_refs": list(event.get("evidence_refs", ())),
                      "rule_refs": list(event.get("rule_refs", ())),
                      "calendar_ref": event.get("calendar_ref")},
            data_sources=source_markers,
            content_hash=snapshot_hash,
        )
        logger.record(audit_event)
        candidates = logger.query_by(
            scenario="SC2", action="sc2_three_metric_evidence.snapshot_published"
        )
        matches = [
            row for row in candidates
            if row.get("decision", {}).get("status") == "evidence_snapshot_published"
            and row.get("content_hash") == snapshot_hash
            and row.get("data_sources", {}).get("snapshot_id") == snapshot_id
            and row.get("data_sources", {}).get("schema_version") == "sc2_three_metric_evidence/v1"
        ]
        after = logger.verify_chain()
        return len(matches) == 1 and after.ok
    except Exception:
        return False
```

- [ ] **Step 6: Test persistence, actual adapter call order, and faults.** Add the complete fixture/test definitions below to the sole new test module. The fake logger mirrors only the verified audit methods and returns typed chain verification objects; it does not replace or modify platform code. The failure cases cover an invalid pre-chain, record exception, missing/duplicate readback, hash mismatch, and invalid post-chain. In each case persistence remains unavailable to `load_evidence_snapshot`.

```python
from dataclasses import dataclass

@dataclass(frozen=True)
class FakeChainVerifyResult:
    ok: bool
    total: int
    error: str | None = None


class FakeAuditLogger:
    def __init__(self, *, before_ok=True, after_ok=True, record_error=False,
                 readback_count=1, readback_hash=None):
        self.before_ok = before_ok
        self.after_ok = after_ok
        self.record_error = record_error
        self.readback_count = readback_count
        self.readback_hash = readback_hash
        self.events = []
        self.verify_calls = 0

    def verify_chain(self):
        self.verify_calls += 1
        ok = self.before_ok if self.verify_calls == 1 else self.after_ok
        return FakeChainVerifyResult(ok=ok, total=len(self.events), error=None if ok else "fixture chain failure")

    def record(self, event):
        if self.record_error:
            raise OSError("fixture append failure")
        self.events.append(event.to_dict())

    def query_by(self, **filters):
        assert filters == {"scenario": "SC2", "action": "sc2_three_metric_evidence.snapshot_published"}
        rows = []
        for event in self.events:
            row = dict(event)
            if self.readback_hash is not None:
                row["content_hash"] = self.readback_hash
            rows.append(row)
        return rows * self.readback_count


@pytest.fixture
def audit_logger_factory(monkeypatch):
    instances = []
    class FakeAuditLoggerFactory:
        @staticmethod
        def jsonl(log_path):
            logger = FakeAuditLogger()
            instances.append((log_path, logger))
            return logger
    monkeypatch.setattr("sc2.detail.AuditLogger", FakeAuditLoggerFactory)
    return instances


def test_audit_adapter_records_then_reads_back_unique_id_and_hash(monkeypatch, audit_logger_factory):
    event = {"snapshot_id": "00000000-0000-4000-8000-000000000001",
             "canonical_sha256": "a" * 64, "period": "2026-W42",
             "metric_statuses": ["pending", "unknown", "value"],
             "evidence_refs": ["MOCK-EVIDENCE-1"], "rule_refs": ["arrival-v1"],
             "calendar_ref": "MOCK-CALENDAR@v1:abc"}
    assert append_evidence_audit(event) is True
    _, logger = audit_logger_factory[-1]
    assert logger.verify_calls == 2
    recorded = logger.events[0]
    assert recorded["evaluator"] == "MOCK-SC2-three-metric-evidence/v1"
    assert recorded["automation_level"] == "L1"
    assert recorded["content_hash"] == event["canonical_sha256"]
    assert recorded["data_sources"] == {
        "snapshot_id": event["snapshot_id"],
        "schema_version": "sc2_three_metric_evidence/v1",
    }


@pytest.mark.parametrize("fault", ["before_chain", "after_chain", "record", "missing_readback", "duplicate_readback", "hash_mismatch"])
def test_audit_adapter_fails_closed_for_logger_faults(monkeypatch, audit_logger_factory, fault):
    event = {"snapshot_id": "00000000-0000-4000-8000-000000000001",
             "canonical_sha256": "a" * 64, "period": "2026-W42",
             "metric_statuses": ["pending", "unknown", "value"],
             "evidence_refs": ["MOCK-EVIDENCE-1"], "rule_refs": ["arrival-v1"],
             "calendar_ref": "MOCK-CALENDAR@v1:abc"}
    logger = FakeAuditLogger(
        before_ok=fault != "before_chain", after_ok=fault != "after_chain",
        record_error=fault == "record",
        readback_count=0 if fault == "missing_readback" else 2 if fault == "duplicate_readback" else 1,
        readback_hash="b" * 64 if fault == "hash_mismatch" else None)
    monkeypatch.setattr("sc2.detail.AuditLogger.jsonl", lambda path: logger)
    assert append_evidence_audit(event) is False
```

- [ ] **Step 7: Run focused persistence/audit tests.** From the isolated SC2 cwd run `& "C:/Dev/Codex/runtimes/zhuopin-ai/venv/Scripts/python.exe" -m pytest tests/test_three_metric_evidence.py -k 'snapshot or audit or canonical_hash' -q`; expected PASS.
- [ ] **Step 8: Read-only compatibility regression.** From the isolated SC2 cwd run `& "C:/Dev/Codex/runtimes/zhuopin-ai/venv/Scripts/python.exe" -m pytest tests/test_detail.py -q`; existing fixtures/outputs must remain unchanged.

### Task 4: Legacy-safe report adapter and explicit read-only web path

**Files:**
- Modify: `4-数字员工/采购部/SC2-采购周报自动生成/sc2/report.py`
- Modify: `4-数字员工/采购部/SC2-采购周报自动生成/sc2/webapp.py`
- Create: `4-数字员工/采购部/SC2-采购周报自动生成/tests/fixtures/three_metric_evidence/legacy_snapshot.json`
- Test: `4-数字员工/采购部/SC2-采购周报自动生成/tests/test_three_metric_evidence.py`

**Interfaces:** consumes validated Task 3 snapshots; produces `evidence_to_report(snapshot)`, `three_metric_evidence_enabled()`, and `get_three_metric_evidence(snapshot_id)`; routes stay under existing `/procurement/sc2`. The three accessors/legacy functions listed in Global Constraints remain behaviorally identical.

- [ ] **Step 1: Write route and rendering contract tests.** Default configuration returns disabled; disabled route does not read a snapshot. The fixed routes are GET `/procurement/sc2/three-metric-evidence/<snapshot_id>` and GET `/procurement/sc2/api/three-metric-evidence/<snapshot_id>`; both read only by explicit ID. API reports status, numeric fields, reason codes, refs and hash; no route accepts “latest”, triggers source reads, POST mutation, refresh, or notification.

```python
def test_evidence_view_is_off_by_default(client, monkeypatch):
    monkeypatch.delenv("SC2_THREE_METRIC_EVIDENCE_ENABLED", raising=False)
    def forbidden_load(snapshot_id):
        raise AssertionError("default-off view attempted a snapshot read")
    monkeypatch.setattr("sc2.webapp.detail.load_evidence_snapshot", forbidden_load)
    response = client.get("/procurement/sc2/three-metric-evidence/00000000-0000-4000-8000-000000000001")
    assert response.status_code in (404, 410)


def test_explicit_snapshot_api_preserves_three_states(client, monkeypatch, saved_snapshot):
    monkeypatch.setenv("SC2_THREE_METRIC_EVIDENCE_ENABLED", "1")
    response = client.get(f"/procurement/sc2/api/three-metric-evidence/{saved_snapshot['snapshot_id']}")
    assert response.status_code == 200
    body = response.get_json()
    assert body["snapshot_id"] == saved_snapshot["snapshot_id"]
    assert body["canonical_sha256"] == saved_snapshot["canonical_sha256"]
    assert {m["status"] for m in body["metrics"]} == {"value", "unknown", "pending"}


def test_legacy_report_contract_and_fail_closed(legacy_snapshot):
    normalized = recognize_legacy_report(legacy_snapshot)
    assert normalized["schema_version"] == "legacy_report_v0"
    assert set(("period", "base_date", "metrics")) <= set(normalized)
    invalid = {**legacy_snapshot, "schema_version": "sc2_three_metric_evidence/v1"}
    with pytest.raises(ValueError):
        recognize_legacy_report(invalid)


def test_pending_result_keeps_simultaneous_unknown_reason(valid_snapshot):
    combined = json.loads(json.dumps(valid_snapshot))
    metric = combined["metrics"][0]
    metric["reason_codes"] = ["HISTORY_UNAVAILABLE", "G01"]
    combined["canonical_sha256"] = evidence_sha256(combined)
    report = evidence_to_report(combined)
    label = report["metrics"][0]["display"]
    assert "资料未知" in label and "业务判例待签" in label


def test_api_snapshot_hash_matches_serialized_report(client, monkeypatch, saved_snapshot, audit_events):
    monkeypatch.setenv("SC2_THREE_METRIC_EVIDENCE_ENABLED", "1")
    monkeypatch.setattr("sc2.webapp.detail.load_evidence_snapshot", lambda snapshot_id: saved_snapshot)
    response = client.get(f"/procurement/sc2/api/three-metric-evidence/{saved_snapshot['snapshot_id']}")
    report = evidence_to_report(saved_snapshot)
    assert response.status_code == 200
    body = response.get_json()
    assert body["snapshot_id"] == report["snapshot_id"] == saved_snapshot["snapshot_id"]
    assert body["canonical_sha256"] == report["canonical_sha256"] == saved_snapshot["canonical_sha256"]
    assert audit_events[-1]["content_hash"] == saved_snapshot["canonical_sha256"]
    assert audit_events[-1]["data_sources"]["snapshot_id"] == saved_snapshot["snapshot_id"]
    assert audit_events[-1]["decision"]["status"] == "evidence_snapshot_published"


def test_api_failure_leaves_old_report_readable(client, monkeypatch, saved_snapshot, legacy_snapshot):
    old_output = recognize_legacy_report(legacy_snapshot)
    monkeypatch.setenv("SC2_THREE_METRIC_EVIDENCE_ENABLED", "1")
    def fail_load(snapshot_id):
        raise ValueError("canonical hash mismatch")
    monkeypatch.setattr("sc2.webapp.detail.load_evidence_snapshot", fail_load)
    response = client.get(f"/procurement/sc2/api/three-metric-evidence/{saved_snapshot['snapshot_id']}")
    assert response.status_code >= 400
    assert recognize_legacy_report(legacy_snapshot) == old_output
```

- [ ] **Step 2: Run focused web contract tests and confirm failure.** From the isolated SC2 cwd run `& "C:/Dev/Codex/runtimes/zhuopin-ai/venv/Scripts/python.exe" -m pytest tests/test_three_metric_evidence.py -k 'evidence_view or explicit_snapshot_api' -q`.
- [ ] **Step 3: Add legacy fixture and presentation adapter.** Create `legacy_snapshot.json` with exactly `{"period":"2026-W41","base_date":"2026-10-12","metrics":[]}` (UTF-8, no `schema_version`). Create `new_snapshot.json` as the exact compact, sorted-key UTF-8 JSON produced by `make_valid_snapshot()`; the builder computes canonical and calendar hashes from the fixed fixture inputs, so the checked-in JSON is stable and directly checked by the `valid_snapshot` fixture. `evidence_to_report` renders value `0` as `0%`, unknown as “资料未知” with reasons, pending as “业务判例待签” with G references; simultaneous causes show both. It never converts nulls or removes unresolved rows into a complete department aggregate.
- [ ] **Step 4: Implement strict legacy detection and opt-in handlers.** Legacy recognition is a new helper isolated from old functions; valid legacy data is tagged `legacy_report_v0`, malformed/mixed new schema fails closed. Read only by UUID; missing/invalid ID yields a non-success status without fallback. Opt-in flag defaults false and is explicit. The handler returns 503/404 on audit-unpublished, corrupt, or absent snapshots; no old value or live source fallback.

```python
from typing import Mapping
from .detail import validate_evidence_snapshot

def recognize_legacy_report(snapshot: Mapping[str, object]) -> dict[str, object]:
    if "schema_version" in snapshot or not {"period", "base_date", "metrics"} <= snapshot.keys():
        raise ValueError("invalid legacy report contract")
    return {**snapshot, "schema_version": "legacy_report_v0"}


def evidence_to_report(snapshot: Mapping[str, object]) -> dict[str, object]:
    validate_evidence_snapshot(snapshot)
    rendered = []
    unknown_codes = {"SOURCE_FIELD_MISSING", "HISTORY_UNAVAILABLE", "PAGE_SET_INCOMPLETE",
                     "RELATION_UNPROVEN", "CALENDAR_UNAVAILABLE", "CALENDAR_OUT_OF_RANGE"}
    for metric in snapshot["metrics"]:
        status = metric["status"]
        if status == "value":
            label = f"{metric['value']:.0%}"
        else:
            reasons = set(metric["reason_codes"])
            labels = []
            unknown_reasons = sorted(reasons & unknown_codes)
            pending_reasons = sorted(reasons - unknown_codes)
            if status == "unknown" or unknown_reasons:
                labels.append("资料未知：" + ", ".join(unknown_reasons or sorted(reasons)))
            if status == "pending" or pending_reasons:
                labels.append("业务判例待签：" + ", ".join(pending_reasons))
            label = "；".join(labels)
        calendar_ref = metric["workday_calendar_ref"]
        calendar_payload = snapshot["workday_calendar_ref"] if calendar_ref is not None else None
        rendered.append({**metric, "workday_calendar_ref": calendar_payload, "display": label})
    return {**snapshot, "metrics": rendered}


def evidence_to_api(snapshot: Mapping[str, object]) -> dict[str, object]:
    validate_evidence_snapshot(snapshot)
    return dict(snapshot)
```

Place the preceding three functions in `sc2/report.py`. The following independent code excerpt is for `sc2/webapp.py`:

```python
import os
from . import detail
from .report import evidence_to_api, evidence_to_report
from flask import Response, jsonify
from uuid import UUID


def three_metric_evidence_enabled() -> bool:
    return os.environ.get("SC2_THREE_METRIC_EVIDENCE_ENABLED", "0") == "1"


def get_three_metric_evidence(snapshot_id: str) -> tuple[dict[str, object] | None, int]:
    if not three_metric_evidence_enabled():
        return None, 404
    try:
        UUID(snapshot_id)
        return detail.load_evidence_snapshot(snapshot_id), 200
    except FileNotFoundError:
        return None, 404
    except (ValueError, RuntimeError):
        return None, 503
```

Register exactly `@bp.get("/api/three-metric-evidence/<snapshot_id>")`; the handler transforms a valid snapshot with `evidence_to_api` before `jsonify`, so each metric receives the resolved calendar reference while the payload remains hash-verifiable. Register `@bp.get("/three-metric-evidence/<snapshot_id>")` for the PC HTML page; it uses `evidence_to_report`, escapes display strings, and must not call `_current_report()`.

```python
@bp.get("/api/three-metric-evidence/<snapshot_id>")
def three_metric_evidence_api(snapshot_id: str):
    payload, status = get_three_metric_evidence(snapshot_id)
    if payload is None:
        return jsonify({"error": "evidence unavailable"}), status
    return jsonify(evidence_to_api(payload)), status


@bp.get("/three-metric-evidence/<snapshot_id>")
def three_metric_evidence_page(snapshot_id: str):
    payload, status = get_three_metric_evidence(snapshot_id)
    if payload is None:
        return Response("Evidence unavailable", status=status, mimetype="text/plain")
    report = evidence_to_report(payload)
    rows = "".join(f"<li>{html.escape(str(item['display']))}</li>" for item in report["metrics"])
    body = f"<!doctype html><html lang='zh-CN'><meta charset='utf-8'><title>SC2 三项指标</title><ul>{rows}</ul></html>"
    return Response(body, status=200, mimetype="text/html")
```
- [ ] **Step 5: Run new contract and existing UI/report regressions.** From the isolated SC2 cwd run `& "C:/Dev/Codex/runtimes/zhuopin-ai/venv/Scripts/python.exe" -m pytest tests/test_three_metric_evidence.py -k 'evidence_view or explicit_snapshot_api or legacy or rendering' -q`; then read-only `& "C:/Dev/Codex/runtimes/zhuopin-ai/venv/Scripts/python.exe" -m pytest tests/test_webapp_ui_contract.py tests/test_report.py -q`.

### Task 5: Fixed synthetic vertical slice and compatibility/fault matrix

**Files:**
- Modify only if needed within allowlist: the eight exact module paths in File Map
- Modify: `4-数字员工/采购部/SC2-采购周报自动生成/tests/test_three_metric_evidence.py`
- Use: three new fixture JSON files

**Interfaces:** joins Tasks 1–4; no new public interface beyond the exact contracts above. This task may not expand the allowlist; a necessary extra file stops implementation pending design revision.

- [ ] **Step 1: Build the end-to-end synthetic test.** Read the three fixture files, derive three metric results, construct UUID/hash snapshot, persist and audit it, then call the explicit ID API and render the report. Assert every layer shares the exact `snapshot_id` and `canonical_sha256`; assert no feed/connector was invoked.
- [ ] **Step 2: Pin the vertical-slice and failure contracts with executable tests.** Include the following tests in the sole new test module. They reuse the full fixtures above; no `conftest.py` or existing golden is changed.

```python
def test_snapshot_id_hash_match_across_api_report_audit(client, monkeypatch, saved_snapshot, audit_events):
    monkeypatch.setenv("SC2_THREE_METRIC_EVIDENCE_ENABLED", "1")
    monkeypatch.setattr("sc2.webapp.detail.load_evidence_snapshot", lambda snapshot_id: saved_snapshot)
    response = client.get(f"/procurement/sc2/api/three-metric-evidence/{saved_snapshot['snapshot_id']}")
    report = evidence_to_report(saved_snapshot)
    body = response.get_json()
    assert response.status_code == 200
    assert (body["snapshot_id"], body["canonical_sha256"]) == (
        report["snapshot_id"], report["canonical_sha256"])
    assert body["canonical_sha256"] == audit_events[-1]["content_hash"]
    assert audit_events[-1]["data_sources"]["snapshot_id"] == body["snapshot_id"]
    assert audit_events[-1]["decision"]["status"] == "evidence_snapshot_published"


def test_failed_new_path_preserves_legacy_output(client, monkeypatch, saved_snapshot, legacy_snapshot):
    old_bytes = json.dumps(recognize_legacy_report(legacy_snapshot), sort_keys=True).encode("utf-8")
    monkeypatch.setenv("SC2_THREE_METRIC_EVIDENCE_ENABLED", "1")
    def corrupt_snapshot(snapshot_id):
        raise ValueError("canonical hash mismatch")
    monkeypatch.setattr("sc2.webapp.detail.load_evidence_snapshot", corrupt_snapshot)
    response = client.get(f"/procurement/sc2/api/three-metric-evidence/{saved_snapshot['snapshot_id']}")
    assert response.status_code >= 400
    assert json.dumps(recognize_legacy_report(legacy_snapshot), sort_keys=True).encode("utf-8") == old_bytes


def test_calendar_missing_version_or_date_returns_none():
    calendar = load_calendar_fixture()
    assert calendar_is_workday(date(2026, 10, 10), "MOCK-CALENDAR@other:" + calendar.sha256, calendar) is None
    assert calendar_is_workday(date(2026, 10, 17), calendar.ref, calendar) is None


def test_opt_in_get_has_no_source_or_mutation_side_effect(client, monkeypatch, saved_snapshot):
    monkeypatch.setenv("SC2_THREE_METRIC_EVIDENCE_ENABLED", "1")
    monkeypatch.setattr("sc2.webapp.detail.load_evidence_snapshot", lambda snapshot_id: saved_snapshot)
    def forbidden(*args, **kwargs):
        raise AssertionError("read-only evidence GET called a source or mutation")
    monkeypatch.setattr("sc2.webapp.build_feed", forbidden)
    response = client.get(f"/procurement/sc2/api/three-metric-evidence/{saved_snapshot['snapshot_id']}")
    latest = client.get("/procurement/sc2/api/three-metric-evidence/latest")
    assert response.status_code == 200
    assert latest.status_code >= 400
```
- [ ] **Step 3: Prove opt-in and side-effect boundaries.** Monkeypatch source factory, real connector construction, notification, and purchase mutation entrypoints to fail if called; verify default-off has no reads, opted-in GET performs only local snapshot/audit verification, and no `latest` endpoint exists.
- [ ] **Step 4: Run focused test file.** From the isolated SC2 cwd run `& "C:/Dev/Codex/runtimes/zhuopin-ai/venv/Scripts/python.exe" -m pytest tests/test_three_metric_evidence.py -q`; expected PASS, no external service and no real data access.
- [ ] **Step 5: Run existing regression files read-only.** From the isolated SC2 cwd run `& "C:/Dev/Codex/runtimes/zhuopin-ai/venv/Scripts/python.exe" -m pytest tests/test_sources.py tests/test_windows.py tests/test_metrics.py tests/test_report.py tests/test_detail.py tests/test_webapp_ui_contract.py tests/test_caseback_golden.py tests/test_delivery.py -q`; preserve all golden files and record exact output/exit code.

### Task 6: Project CI, scope audit, and independent review handoff

**Files:** no additional files; test outputs only in normal CI/runtime locations managed by Guardian.

**Interfaces:** consumes completed Tasks 1–5. Guardian captures commands, environment identity, stdout/stderr, exit codes, changed-file manifest, and independent review result.

- [ ] **Step 1: Verify exact project cwd and fixed interpreter.** Guardian records cwd `C:/Users/Paul Shao/.codex/worktrees/pc-mvp-1012-v4-sc2-continuation/zhuopin-ai/4-数字员工/采购部/SC2-采购周报自动生成` and interpreter `C:/Dev/Codex/runtimes/zhuopin-ai/venv/Scripts/python.exe` before test execution.
- [ ] **Step 2: Run project CI command.** From that exact cwd invoke `& "C:/Dev/Codex/runtimes/zhuopin-ai/venv/Scripts/python.exe" -m pytest -q --tb=short --junit-xml=pytest-result.xml`; expected exit code 0 and all project tests pass. Do not invoke from the main repository's product directory.
- [ ] **Step 3: Audit the changed-file manifest.** It must be a subset of the exact 12-file allowlist. Existing `test_caseback_golden.py` and `test_delivery.py` remain unmodified. Any extra changed file stops review and requires scope/design approval.
- [ ] **Step 4: Independent review.** Reviewer checks every spec requirement, state/null semantics, denominator source binding, calendar provenance, immutability/collision/audit order, default-off ID-only API, legacy byte/output stability, fixture synthetic identity, no side effects, and recorded project CI evidence. Findings are fixed only within the 12-file allowlist; then rerun relevant focused tests and project CI.
- [ ] **Step 5: Stop at review-ready implementation.** Report remaining unsigned G01–G04, absent IT/API evidence, and any formula that could not bind as explicit pending/unknown. This plan grants no ff, live source, deployment, external send, or publication authority; those require separate authorization.

## Authorization Boundary and Handoff

This plan is a review artifact only. The earlier 4A approval authorized writing this detailed plan against actual design HEAD `b2933132b733756b30b94e309e2066bbd50d6e43` and design SHA-256 `9b8b7c9438a7ef309a2cecab10e64781b9f6c31e782699359d13b5e11c70959e`; it did not authorize any implementation or tests. A later explicit approval must bind to this plan version and its exact 12-file scope before Tasks 1–6 begin. Any ff, real ERP/SRM access, production deployment, or external publication/send requires a separate gate. Original OpenSpec proposal/design/spec/tasks and CLAUDE/release documents remain sealed and unchanged; completion status is maintained by the outer Guardian workflow, not this plan.

## Plan Self-Review

- Spec coverage: signed scope and bounded facts (Tasks 1–2); three-state semantics and G01–G04 (Task 2); immutable versioned snapshots and audit (Task 3); authoritative calendar (Tasks 1–2, 5); legacy compatibility and reversible opt-in (Task 4); synthetic-only vertical slice (Task 5); project CI/review (Task 6).
- Placeholder scan: all future execution steps identify files, interfaces, commands, and concrete assertions; no implementation step uses TODO/TBD/pass as an instruction.
- Type consistency: shared model names and return types match the interfaces consumed by Tasks 1–5.
- Review Focus coverage: each five failure classes has explicit tests in Tasks 1–5.


## 冷接续 v2 的限定执行说明

原业务设计字节保持SHA256 `9b8b7c9438a7ef309a2cecab10e64781b9f6c31e782699359d13b5e11c70959e`。原7A计划与其实际design保留；本v2仅把未来执行树改为经本次另批的`pc-mvp-1012-v4-sc2-continuation/zhuopin-ai`，使用新task `sc2-three-metric-cold-1012v4` 与新上下文，12产品/测试文件、业务规则、专业PENDING及CI/review合同不扩。新namespace四件先仅同字节搬运已封存原四件，由outer实际strict/commit；不得重新创作design。新实际design仅在字节SHA与原已批准设计完全相等、业务intent不变时按本次明确授权机械绑定新task/design HEAD，否则停止另审。

原SC2的12个现有文件已精确只读复制并逐个SHA留在`reports/pc-mvp-1012/v3/sc2-partial-assets/`与manifest；其中仅10路径有未提交改动，report/webapp为旧基线。它们是未验收的部分输入，不是accepted implementation或通过测试凭证。未来同字节放到新树reports/pc-mvp-input/partial-sc2/，child先阅读原设计/基线与部分内容，先恢复其完整兼容合同再在12白名单内重用/补齐。原树、171658-token旧thread、timeout/9次工具失败、不可读临时目录原位保全；不复用旧thread、不删除/改ACL，不复制其它路径，不安装依赖或写主仓产品。

TDD沿原原始红/绿记录只作历史输入；新功能缺口先确认行为RED，再最小GREEN，ImportError不算RED。未来pytest临时文件及TEMP/TMP/basetemp只进本次限定的ignored UUID验证目录，不把临时目录放进tests/fixtures。每个里程碑报告原生实际context，达到150k时以已写入资产/明确停点收工；不以超时当完成。所有模型显式Luna；正式外层验白名单→commit→项目CI→独立review，成功才报告技术切片完成。
