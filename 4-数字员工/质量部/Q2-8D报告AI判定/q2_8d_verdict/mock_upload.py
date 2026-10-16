"""Explicit synthetic input boundary; existing Q2 engine remains the authority."""
from __future__ import annotations

import hashlib
import json
import os
import re
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

from zhuopin_platform.audit import AuditEvent, AuditLogger

from . import config, feed_source
from .engine import VerdictEngine
from .semantic import PendingSemantic
from .models import (Confidence, EightDInput, TraceField, Verdict, RuleFinding, RuleStatus,
                     RedlineFinding, RedlineStatus, Disposition)

SCHEMA = "q2_mock_input/v1"
MAX_BYTES = 2 * 1024 * 1024

class MockUploadError(RuntimeError):
    def __init__(self, code="invalid_input"):
        self.code = code
        super().__init__(code)

@dataclass(frozen=True)
class MockUploadInput:
    doc: EightDInput
    source_version: str
    source_ref: str
    extracted_at_utc: str | None
    raw_sha256: str


def _keys(data, names):
    if type(data) is not dict or set(data) != set(names.split()):
        raise MockUploadError()


def _string(value, *, nonempty=False, limit=MAX_BYTES):
    if type(value) is not str or len(value) > limit or (nonempty and not value.strip()):
        raise MockUploadError()
    return value


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise MockUploadError()
        result[key] = value
    return result


def parse_mock_upload(raw: bytes) -> MockUploadInput:
    if type(raw) is not bytes or len(raw) > MAX_BYTES:
        raise MockUploadError("input_too_large" if type(raw) is bytes else "invalid_input")
    try:
        data = json.loads(raw.decode("utf-8"), object_pairs_hook=_pairs,
                          parse_constant=lambda _: (_ for _ in ()).throw(MockUploadError()))
        _keys(data, "schema_version mode customer_id project_id source_version source_ref extracted_at_utc report")
        for key, expected in dict(schema_version=SCHEMA, mode="MOCK", customer_id="MOCK-OEM-A",
                                  project_id="MOCK-PROJECT-A").items():
            if data[key] != expected:
                raise MockUploadError()
        _string(data["source_version"], nonempty=True, limit=160)
        ref = _string(data["source_ref"], nonempty=True, limit=256)
        if not re.fullmatch(r"mock:[A-Za-z0-9_:-]+(?:\.[A-Za-z0-9_:-]+)*", ref):
            raise MockUploadError()
        timestamp = data["extracted_at_utc"]
        if timestamp is not None:
            _string(timestamp, nonempty=True, limit=64)
            if "T" not in timestamp or datetime.fromisoformat(timestamp).utcoffset() is None:
                raise MockUploadError()
        report = data["report"]
        _keys(report, "report_id sections scene template safety_related safety_confidence asil_level trace_fields is_external")
        _string(report["report_id"], nonempty=True, limit=160)
        if type(report["sections"]) is not dict:
            raise MockUploadError()
        for key, value in report["sections"].items():
            _string(key, nonempty=True, limit=160)
            _string(value)
        if report["scene"] not in (None, "制造", "研发") or report["template"] not in ("标准8D", "七步法", "客户模板"):
            raise MockUploadError()
        if report["safety_related"] is not None and type(report["safety_related"]) is not bool:
            raise MockUploadError()
        if report["asil_level"] not in ("", "QM", "A", "B", "C", "D") or type(report["is_external"]) is not bool:
            raise MockUploadError()
        if type(report["trace_fields"]) is not list:
            raise MockUploadError()
        trace = []
        for t in report["trace_fields"]:
            _keys(t, "name value confidence")
            trace.append(TraceField(_string(t["name"], nonempty=True, limit=160),
                                    _string(t["value"]), Confidence(t["confidence"])))
        doc = EightDInput(**{**report, "safety_confidence": Confidence(report["safety_confidence"]),
                              "trace_fields": tuple(trace), "meta": {"source": "mock"}})
        return MockUploadInput(doc, data["source_version"], ref, timestamp, hashlib.sha256(raw).hexdigest())
    except (ValueError, TypeError, KeyError, RecursionError) as exc:
        raise MockUploadError() from exc

def example_input(token: str) -> bytes:
    samples = feed_source.load_mock()
    if not re.fullmatch(r"[1-9][0-9]*", token) or len(token) > 3 or int(token) > len(samples):
        raise MockUploadError("unknown_example")
    doc = asdict(samples[int(token) - 1][0])
    doc.pop("meta")
    return json.dumps(dict(schema_version=SCHEMA, mode="MOCK", customer_id="MOCK-OEM-A",
        project_id="MOCK-PROJECT-A", source_version="existing-synthetic-samples-v1", source_ref=f"mock:sample-{token}",
        extracted_at_utc=None, report=doc), ensure_ascii=False, indent=2).encode("utf-8")


def _json(data) -> bytes:
    return json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _restore_verdict(data) -> Verdict:
    value = dict(data)
    value["rules"] = tuple(RuleFinding(**{**r, "status": RuleStatus(r["status"])}) for r in value["rules"])
    value["redlines"] = tuple(RedlineFinding(**{**r, "status": RedlineStatus(r["status"])}) for r in value["redlines"])
    value["disposition"] = Disposition(value["disposition"])
    for key in ("scene_flags", "structural_empty_sections", "grade_range", "notes"):
        value[key] = tuple(value[key])
    return Verdict(**value)


@dataclass(frozen=True)
class SavedMockReport:
    object_id: str
    payload: dict
    receipt: dict

    @property
    def verdict(self) -> Verdict:
        return _restore_verdict(self.payload["verdict_detail"])


class MockUploadService:
    """Immutable local candidate store. Pending fixes the first payload before audit.

    Publication uses a hard link (atomic create without replacement). An operation's
    own short-lived busy marker excludes concurrent submitters; a process crash is
    fail-closed and leaves that marker for explicit recovery, never stale-lock cleanup.
    """
    def __init__(self, root: Path, audit: AuditLogger):
        self.root, self.audit = Path(root), audit

    def _write_immutable(self, path: Path, raw: bytes):
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists():
            if path.read_bytes() != raw:
                raise MockUploadError("storage_unavailable")
            return
        scratch = self.root / ".control" / (uuid.uuid4().hex + ".staged")
        scratch.parent.mkdir(parents=True, exist_ok=True)
        with scratch.open("xb") as handle:
            handle.write(raw)
            handle.flush()
            os.fsync(handle.fileno())
        if scratch.read_bytes() != raw:
            raise MockUploadError("storage_unavailable")
        try:
            os.link(scratch, path)
        except FileExistsError:
            pass
        if path.read_bytes() != raw:
            raise MockUploadError("storage_unavailable")

    def _publish_result(self, object_id: str, envelope: bytes):
        self._write_immutable(self.root / "objects" / (object_id + ".json"), envelope)

    def _event(self, payload: dict) -> AuditEvent:
        return AuditEvent(scenario="Q2", action="mock_upload_report", evaluator=payload["actor"],
            automation_level="L1", timestamp=payload["saved_at_utc"],
            content_hash=_sha(_json(payload)), data_sources={"input": "MOCK"},
            decision={key: payload[key] for key in ("operation_id", "object_id", "input_sha256", "rules_sha256", "rules_version")})

    def _receipt(self, payload: dict, *, create=False) -> dict:
        expected = self._event(payload).to_dict()
        records = self.audit.query_by(scenario="Q2", action="mock_upload_report")
        matching = [r for r in records if r.get("decision", {}).get("operation_id") == payload["operation_id"]]
        if not matching and create:
            self.audit.record(self._event(payload))
            # Some sinks cannot support verification. These never produce a saved report.
            records = self.audit.query_by(scenario="Q2", action="mock_upload_report")
            matching = [r for r in records if r.get("decision", {}).get("operation_id") == payload["operation_id"]]
        chain = self.audit.verify_chain()
        if not chain.ok or not chain.total or chain.error or len(matching) != 1:
            raise MockUploadError("storage_unavailable")
        actual = {k: v for k, v in matching[0].items() if k != "prev_hash"}
        if actual != expected:
            raise MockUploadError("storage_unavailable")
        return {"event_sha256": _sha(_json(actual)), "payload_sha256": expected["content_hash"],
                "action": "mock_upload_report", "chain_verified": True, "automation_level": "L1"}

    def submit(self, raw: bytes, actor: str) -> SavedMockReport:
        parsed = parse_mock_upload(raw)
        if type(actor) is not str or not re.fullmatch(r"synthetic:[A-Za-z0-9_-]{1,64}", actor):
            raise MockUploadError("access_denied")
        engine = VerdictEngine(semantic=PendingSemantic(), audit=None)
        # C/D exits in the authoritative engine before writing source, pending or audit.
        verdict = engine.evaluate(parsed.doc)
        rules = engine.ruleset
        effective_hash = _sha(_json(asdict(rules)))
        operation = _sha(_json([SCHEMA, parsed.raw_sha256, rules.sha256, config.RULE_VERSION, effective_hash]))
        object_id = operation[:32]
        busy = self.root / ".control" / (operation + ".busy")
        owned = False
        try:
            busy.parent.mkdir(parents=True, exist_ok=True)
            with busy.open("xb") as handle:
                owned = True
                handle.write(str(os.getpid()).encode())
            if (self.root / "objects" / (object_id + ".json")).exists():
                return self.get(object_id)
            self._write_immutable(self.root / "sources" / (parsed.raw_sha256 + ".json"), raw)
            pending_path = self.root / ".control" / (operation + ".pending")
            if pending_path.exists():
                pending = json.loads(pending_path.read_bytes())
            else:
                payload = dict(schema_version="q2_mock_report/v1", mode="MOCK", operation_id=operation,
                    object_id=object_id, input_sha256=parsed.raw_sha256, rules_sha256=rules.sha256,
                    rules_effective_sha256=effective_hash, rules_version=config.RULE_VERSION,
                    rules_source_version=rules.source_version,
                    actor=actor, saved_at_utc=datetime.now(timezone.utc).isoformat(),
                    source=dict(source_version=parsed.source_version, source_ref=parsed.source_ref,
                        extracted_at_utc=parsed.extracted_at_utc, customer_id="MOCK-OEM-A", project_id="MOCK-PROJECT-A"),
                    verdict=verdict.to_dict(), verdict_detail=asdict(verdict))
                pending = {"payload": payload, "payload_sha256": _sha(_json(payload))}
                self._write_immutable(pending_path, _json(pending))
            payload = pending["payload"]
            if (pending["payload_sha256"] != _sha(_json(payload)) or payload["operation_id"] != operation
                    or payload["input_sha256"] != parsed.raw_sha256 or payload["object_id"] != object_id
                    or payload["rules_effective_sha256"] != effective_hash):
                raise MockUploadError("storage_unavailable")
            receipt = self._receipt(payload, create=True)
            self._publish_result(object_id, _json({"payload": payload, "receipt": receipt}))
            return self.get(object_id)
        except MockUploadError:
            raise
        except Exception as exc:
            raise MockUploadError("storage_unavailable") from exc
        finally:
            if owned:
                try:
                    busy.unlink()  # only this call's newly-created marker, never an old claim
                except OSError as exc:
                    raise MockUploadError("storage_unavailable") from exc

    def get(self, object_id: str) -> SavedMockReport:
        if type(object_id) is not str or not re.fullmatch(r"[a-f0-9]{32}", object_id):
            raise MockUploadError("not_found")
        path = self.root / "objects" / (object_id + ".json")
        try:
            if not path.exists():
                raise MockUploadError("not_found")
            data = json.loads(path.read_bytes())
            payload, receipt = data["payload"], data["receipt"]
            if (payload["object_id"] != object_id or payload["operation_id"][:32] != object_id
                    or receipt != self._receipt(payload)):
                raise MockUploadError("storage_unavailable")
            source = self.root / "sources" / (payload["input_sha256"] + ".json")
            if _sha(source.read_bytes()) != payload["input_sha256"]:
                raise MockUploadError("storage_unavailable")
            saved = SavedMockReport(object_id, payload, receipt)
            if saved.verdict.to_dict() != payload["verdict"]:
                raise MockUploadError("storage_unavailable")
            return saved
        except MockUploadError:
            raise
        except Exception as exc:
            raise MockUploadError("storage_unavailable") from exc

    def export(self, object_id: str) -> bytes:
        saved = self.get(object_id)
        return _json({"payload": saved.payload, "receipt": saved.receipt})
