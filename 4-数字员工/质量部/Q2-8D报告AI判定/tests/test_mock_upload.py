"""Synthetic upload acceptance, independent of expected labels/semantic source."""
import hashlib
import json

import pytest

from q2_8d_verdict.mock_upload import MockUploadError, parse_mock_upload, example_input
from q2_8d_verdict.mock_upload import MockUploadService
from zhuopin_platform.audit import AuditLogger
from zhuopin_platform.audit.sinks import ChainVerifyResult


def body(**changes):
    report = dict(report_id="MOCK-test", sections={}, scene=None, template="标准8D",
                  safety_related=None, safety_confidence="LOW", asil_level="",
                  trace_fields=[], is_external=False)
    data = dict(schema_version="q2_mock_input/v1", mode="MOCK", customer_id="MOCK-OEM-A",
                project_id="MOCK-PROJECT-A", source_version="synthetic-v1", source_ref="mock:test",
                extracted_at_utc=None, report=report)
    data.update(changes)
    return data


def raw(data):
    return json.dumps(data, ensure_ascii=False).encode()


def test_explicit_unknown_and_original_bytes_are_preserved():
    source = raw(body()) + b"\n"
    parsed = parse_mock_upload(source)
    assert parsed.raw_sha256 == hashlib.sha256(source).hexdigest()
    assert parsed.extracted_at_utc is None
    assert parsed.doc.sections == {} and parsed.doc.scene is None
    assert parsed.doc.safety_related is None
    assert parsed.doc.safety_confidence.value == "LOW"
    assert parsed.source_version == "synthetic-v1"


@pytest.mark.parametrize("change", [
    {"mode": "REAL"}, {"customer_id": "OEM-B"}, {"project_id": "project-real"},
    {"source_version": ""}, {"source_ref": "C:/secret"}, {"source_ref": "mock:../secret"},
    {"extracted_at_utc": "2026-10-15T12:00:00"}, {"expected": {}},
    {"schema_version": "v2"}, {"report": None},
])
def test_reject_wrong_scope_or_missing_source_contract(change):
    with pytest.raises(MockUploadError):
        parse_mock_upload(raw(body(**change)))


@pytest.mark.parametrize("key,value", [("sections", []), ("sections", {"D3": None}),
    ("scene", "unknown"), ("template", "Word"), ("safety_related", "false"),
    ("safety_confidence", "HIGH!"), ("asil_level", "E"), ("is_external", 1),
    ("trace_fields", [{"name": "n", "value": "v", "confidence": "low"}]),
    ("meta", {"expected": "A"}), ("report_id", "")])
def test_reject_report_types_enums_and_overrides(key, value):
    data = body()
    data["report"][key] = value
    with pytest.raises(MockUploadError):
        parse_mock_upload(raw(data))


@pytest.mark.parametrize("source", [b"{", b"[]", b"\xff", b'{"mode":"MOCK","mode":"MOCK"}',
    b" " * (2 * 1024 * 1024 + 1), b'{"number":NaN}'],
    ids=["broken", "array", "encoding", "duplicate", "oversize", "nan"])
def test_malformed_duplicate_oversize_never_becomes_empty_sections(source):
    with pytest.raises(MockUploadError):
        parse_mock_upload(source)


def test_example_projects_existing_input_without_expected():
    from q2_8d_verdict.feed_source import load_mock
    for i, (doc, _) in enumerate(load_mock(), 1):
        source = example_input(str(i))
        parsed = parse_mock_upload(source)
        assert parsed.doc.report_id == doc.report_id
        assert parsed.doc.sections == doc.sections
        assert parsed.doc.safety_related == doc.safety_related
        assert "expected" not in json.loads(source)
    with pytest.raises(MockUploadError):
        example_input("../secret")


@pytest.fixture
def service(tmp_path):
    return MockUploadService(tmp_path / "store", AuditLogger.jsonl(tmp_path / "audit.jsonl"))


def test_saved_report_matches_engine_and_exact_audit_and_raw_source(service):
    from q2_8d_verdict.engine import VerdictEngine
    from q2_8d_verdict import config
    source = example_input("1") + b"\n"
    saved = service.submit(source, "synthetic:tester")
    assert saved.verdict.to_dict() == VerdictEngine().evaluate(parse_mock_upload(source).doc).to_dict()
    assert saved.payload["source"]["extracted_at_utc"] is None
    assert saved.payload["rules_version"] == config.RULE_VERSION
    assert (service.root / "sources" / (hashlib.sha256(source).hexdigest() + ".json")).read_bytes() == source
    exported = json.loads(service.export(saved.object_id))
    assert exported["payload"] == saved.payload
    assert exported["receipt"] == saved.receipt
    events = service.audit.query_by(scenario="Q2", action="mock_upload_report")
    assert len(events) == 1 and events[0]["automation_level"] == "L1"
    assert events[0]["content_hash"] == saved.receipt["payload_sha256"]
    assert saved.verdict.automation_level == "L2"
    assert service.audit.verify_chain().ok
    assert service.get(saved.object_id).verdict == saved.verdict


def test_retry_keeps_first_time_actor_object_and_no_duplicate_audit(service):
    source = example_input("1")
    first = service.submit(source, "synthetic:first")
    before = service.export(first.object_id)
    again = MockUploadService(service.root, service.audit).submit(source, "synthetic:second")
    assert again.object_id == first.object_id
    assert service.export(again.object_id) == before
    assert len(service.audit.query_by(action="mock_upload_report")) == 1


@pytest.mark.parametrize("phase", ["record", "query", "chain", "publish"])
def test_failure_never_returns_saved_and_retry_uses_pending(service, monkeypatch, phase):
    source = example_input("1")
    with monkeypatch.context() as m:
        def fail(*a, **kw):
            raise OSError("sensitive path must not leak")
        if phase == "record":
            m.setattr(service.audit, "record", fail)
        elif phase == "query":
            m.setattr(service.audit, "query_by", fail)
        elif phase == "chain":
            m.setattr(service.audit, "verify_chain", lambda: ChainVerifyResult(True, 0, error="unsupported"))
        else:
            m.setattr(service, "_publish_result", fail)
        with pytest.raises(MockUploadError, match="storage_unavailable"):
            service.submit(source, "synthetic:first")
    pending = list((service.root / ".control").glob("*.pending"))
    assert len(pending) == 1
    original = pending[0].read_bytes()
    saved = service.submit(source, "synthetic:retry")
    assert pending[0].read_bytes() == original
    assert len(service.audit.query_by(action="mock_upload_report")) == 1
    assert service.get(saved.object_id).object_id == saved.object_id


def test_source_write_failure_returns_safe_error(service, monkeypatch):
    def fail(*a, **kw):
        raise OSError("private")
    monkeypatch.setattr(service, "_write_immutable", fail)
    with pytest.raises(MockUploadError, match="storage_unavailable"):
        service.submit(example_input("1"), "synthetic:first")
    assert not service.audit.query_by(action="mock_upload_report")


@pytest.mark.parametrize("target", ["source", "result", "audit", "duplicate", "missing_event"])
def test_tamper_or_wrong_event_blocks_view_and_export(service, target):
    saved = service.submit(example_input("1"), "synthetic:tester")
    if target == "source":
        next((service.root / "sources").glob("*.json")).write_bytes(b"changed")
    elif target == "result":
        next((service.root / "objects").glob("*.json")).write_bytes(b"{}")
    elif target == "audit":
        path = service.audit.sink.log_path
        path.write_text(path.read_text(encoding="utf-8") + '{"prev_hash":"bad"}\n', encoding="utf-8")
    elif target == "missing_event":
        service.audit.sink.log_path.write_text("", encoding="utf-8")
    else:
        from zhuopin_platform.audit import AuditEvent
        event = service.audit.query_by(action="mock_upload_report")[0]
        event.pop("prev_hash")
        service.audit.record(AuditEvent(**event))
    with pytest.raises(MockUploadError):
        service.get(saved.object_id)
    with pytest.raises(MockUploadError):
        service.export(saved.object_id)


def test_audit_never_contains_uploaded_words_or_raw_actor(service):
    data = body()
    data["report"]["sections"] = {"D2": "PRIVATE-SYNTHETIC-CONTENT"}
    service.submit(raw(data), "synthetic:tester")
    audit = service.audit.sink.log_path.read_text(encoding="utf-8")
    assert "PRIVATE-SYNTHETIC-CONTENT" not in audit
    assert "MOCK-OEM-A" not in audit and "MOCK-test" not in audit


@pytest.mark.parametrize("asil", ["C", "D"])
def test_asil_exits_without_scoring_object_or_audit(service, asil):
    from q2_8d_verdict.engine import AsilExcludedError
    data = body()
    data["report"]["asil_level"] = asil
    with pytest.raises(AsilExcludedError):
        service.submit(raw(data), "synthetic:tester")
    assert not service.audit.query_by(action="mock_upload_report")
    assert not list(service.root.glob("objects/*.json"))


def test_unknown_low_and_empty_sections_reach_original_manual_gate(service):
    saved = service.submit(raw(body()), "synthetic:tester")
    assert saved.verdict.structural_return
    assert saved.verdict.needs_manual_review
    assert saved.verdict.scene_flags


def test_pending_semantic_still_produces_interval_and_cannot_call_real_source(service, monkeypatch):
    import q2_8d_verdict.feed_source as feed
    source = example_input("1")
    monkeypatch.setattr(feed, "from_qda", lambda *a, **k: pytest.fail("real source called"))
    saved = service.submit(source, "synthetic:tester")
    assert saved.verdict.score_pending_max > 0
    assert saved.verdict.grade is None


def test_invalid_actor_and_traversal_have_no_side_effects(service):
    with pytest.raises(MockUploadError):
        service.submit(example_input("1"), "http-user")
    with pytest.raises(MockUploadError):
        service.get("../other")
    assert not service.audit.query_by(action="mock_upload_report")
