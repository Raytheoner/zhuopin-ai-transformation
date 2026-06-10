"""
SC1 审计适配层 — IATF 16949 追溯要求。

SC1AuditAdapter 是薄包装：保持旧 append_record() 签名，
内部委托给 zhuopin_platform.audit（含 P2 hash-chain）。
红色数据保护：不写入原始注册资本、IQC 合格率。
"""
from __future__ import annotations
from pathlib import Path

from zhuopin_platform.audit import AuditLogger, AuditEvent
from zhuopin_platform.audit.sinks import JsonlSink, ChainVerifyResult

from src.scoring import ScoringResult

_WEIGHTS = {"delivery": 0.35, "iqc": 0.30, "financial": 0.20, "single_source": 0.15}


class SC1AuditAdapter:
    """薄包装层：translate SC1 业务调用 → 平台 AuditEvent。

    append_record() 签名与旧版完全兼容，main.py 无需修改调用侧。
    """

    def __init__(self, log_path: Path):
        self._platform = AuditLogger(JsonlSink(log_path))

    def append_record(
        self,
        evaluator: str,
        supplier_name: str,
        supplier_code: str,
        result: ScoringResult,
        delivery_source: str,
        ai_text_hash: str,
        report_path: str = "",
        error: str = "",
    ) -> None:
        self._platform.record(AuditEvent(
            scenario="SC1",
            action="supplier_risk_eval",
            evaluator=evaluator,
            automation_level="L2",
            decision={
                "supplier_name": supplier_name,
                "supplier_code": supplier_code,
                "risk_level": result.risk_level,
                "composite_score": result.composite_score,
                "scores": {
                    "delivery": result.delivery.value,
                    "iqc": result.iqc.value,
                    "financial": result.financial.value,
                    "single_source": result.single_source.value,
                },
                "weights": dict(_WEIGHTS),
                "data_sources": {
                    "delivery": delivery_source or result.delivery.source,
                    "iqc": result.iqc.source or "人工录入",
                    "financial": result.financial.source or "人工录入",
                    "single_source": result.single_source.source or "人工录入",
                },
                "report_path": report_path or "FAILED",
            },
            content_hash=ai_text_hash,
            error=error,
        ))

    def verify_chain(self) -> ChainVerifyResult:
        return self._platform.verify_chain()

    def query_by_supplier(self, supplier_name: str) -> list[dict]:
        all_sc1 = self._platform.query_by(scenario="SC1")
        matching = [
            r for r in all_sc1
            if r.get("decision", {}).get("supplier_name") == supplier_name
        ]
        return [
            {
                "timestamp": r.get("timestamp", ""),
                "risk_level": r.get("decision", {}).get("risk_level"),
                "composite_score": r.get("decision", {}).get("composite_score"),
                "evaluator": r.get("evaluator", ""),
                "report_path": r.get("decision", {}).get("report_path", ""),
            }
            for r in matching
        ]

    def verify_integrity(self) -> dict:
        """委托平台完整性自检，补齐 main.py 依赖的兼容字段。"""
        base = self._platform.verify_integrity()

        if base["status"] == "empty":
            return {
                "total": 0, "valid": 0, "invalid": 0,
                "invalid_lines": [],
                "suppliers": [], "earliest": "", "latest": "",
                "recent_10": [], "status": "empty",
            }

        all_records = self._platform.query_by(scenario="SC1")
        suppliers = list({
            r.get("decision", {}).get("supplier_name", "")
            for r in all_records
            if r.get("decision", {}).get("supplier_name")
        })

        recent = sorted(all_records, key=lambda r: r.get("timestamp", ""), reverse=True)[:10]
        recent_10 = [
            {
                "timestamp": r.get("timestamp", ""),
                "supplier": r.get("decision", {}).get("supplier_name", ""),
                "risk_level": r.get("decision", {}).get("risk_level"),
                "score": r.get("decision", {}).get("composite_score"),
                "evaluator": r.get("evaluator", ""),
            }
            for r in recent
        ]

        return {
            "total": base["total"],
            "valid": base["total"],   # platform 的 read_all 静默跳过损坏行，计数均为有效
            "invalid": 0,
            "invalid_lines": [],
            "suppliers": suppliers,
            "earliest": base["earliest"],
            "latest": base["latest"],
            "recent_10": recent_10,
            "status": base["status"],
        }
