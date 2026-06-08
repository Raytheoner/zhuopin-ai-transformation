"""统一审计入口 —— 业务代码只调 AuditLogger，不关心后端。"""
from __future__ import annotations

from pathlib import Path

from .events import AuditEvent
from .sinks import AuditSink, JsonlSink


class AuditLogger:
    """跨场景统一审计器。

    用法（任意场景）::

        from zhuopin_platform.audit import AuditLogger, AuditEvent
        audit = AuditLogger.jsonl("reports/audit_log.jsonl")
        audit.record(AuditEvent(
            scenario="SC1", action="supplier_risk_eval",
            evaluator="张采购", automation_level="L2",
            decision={"risk_level": 4, "composite_score": 3.6},
            data_sources={"delivery": "SRM", "iqc": "人工录入"},
            content_hash=sha256_hex,
        ))
    """

    def __init__(self, sink: AuditSink):
        self.sink = sink

    @classmethod
    def jsonl(cls, log_path: Path | str) -> "AuditLogger":
        return cls(JsonlSink(log_path))

    def record(self, event: AuditEvent) -> None:
        self.sink.write(event)

    def query_by(self, **filters) -> list[dict]:
        """按任意字段过滤历史记录，如 query_by(scenario='SC1', evaluator='张采购')。"""
        out = []
        for r in self.sink.read_all():
            if all(r.get(k) == v for k, v in filters.items()):
                out.append(r)
        return out

    def verify_integrity(self) -> dict:
        """完整性自检：记录数 / 时间跨度 / 场景分布。供上线前与定期审计使用。"""
        records = self.sink.read_all()
        timestamps = sorted(r.get("timestamp", "") for r in records if r.get("timestamp"))
        scenarios = sorted({r.get("scenario", "") for r in records})
        return {
            "total": len(records),
            "scenarios": scenarios,
            "earliest": timestamps[0] if timestamps else "",
            "latest": timestamps[-1] if timestamps else "",
            "status": "ok" if records else "empty",
        }
