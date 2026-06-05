"""
审计日志模块 — IATF 16949 追溯要求。

日志格式：JSON Lines（每条评估一行），存储在 audit_log.jsonl。
红色数据保护：不存储原始注册资本数值和 IQC 合格率原始数值。
"""
from __future__ import annotations
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from src.scoring import ScoringResult


class AuditLogger:
    """JSON Lines 格式审计日志，原子追加写入。"""

    WEIGHTS = {"delivery": 0.35, "iqc": 0.30, "financial": 0.20, "single_source": 0.15}

    def __init__(self, log_path: Path):
        self.log_path = log_path

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
        """原子追加一条审计记录（open append mode — 单进程安全）。"""
        record = {
            "timestamp": datetime.now(tz=timezone.utc).isoformat(),
            "evaluator": evaluator,
            "supplier_name": supplier_name,
            "supplier_code": supplier_code,
            "scores": {
                "delivery": result.delivery.value,
                "iqc": result.iqc.value,
                "financial": result.financial.value,
                "single_source": result.single_source.value,
            },
            "weights": dict(self.WEIGHTS),
            "composite_score": result.composite_score,
            "risk_level": result.risk_level,
            "data_sources": {
                "delivery": delivery_source or result.delivery.source,
                "iqc": result.iqc.source or "人工录入",
                "financial": result.financial.source or "人工录入",
                "single_source": result.single_source.source or "人工录入",
            },
            "report_path": report_path or "FAILED",
            "ai_text_hash": ai_text_hash,
        }
        if error:
            record["error"] = error

        # 注意：原始财务数字（注册资本、IQC 合格率）不写入此记录
        line = json.dumps(record, ensure_ascii=False) + "\n"
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.log_path, "a", encoding="utf-8") as f:
            f.write(line)

    def query_by_supplier(self, supplier_name: str) -> list[dict]:
        """返回指定供应商的所有历史评估摘要（时间、风险等级、评估人）。"""
        results = []
        for record, _ in self._iter_valid_records():
            if record.get("supplier_name") == supplier_name:
                results.append({
                    "timestamp": record.get("timestamp", ""),
                    "risk_level": record.get("risk_level"),
                    "composite_score": record.get("composite_score"),
                    "evaluator": record.get("evaluator", ""),
                    "report_path": record.get("report_path", ""),
                })
        return results

    def verify_integrity(self) -> dict:
        """
        完整性自检：统计记录数、时间跨度、供应商数、异常行。
        返回 dict 供 main.py 格式化输出。
        """
        if not self.log_path.exists():
            return {
                "total": 0, "valid": 0, "invalid": 0,
                "suppliers": [], "earliest": "", "latest": "",
                "recent_10": [], "status": "empty",
            }

        valid_records = []
        invalid_lines: list[tuple[int, str]] = []

        with open(self.log_path, encoding="utf-8") as f:
            for lineno, line in enumerate(f, 1):
                line = line.rstrip("\n")
                if not line:
                    continue
                try:
                    record = json.loads(line)
                    valid_records.append(record)
                except json.JSONDecodeError:
                    invalid_lines.append((lineno, line[:80]))

        timestamps = [r.get("timestamp", "") for r in valid_records if r.get("timestamp")]
        timestamps.sort()
        suppliers = list({r.get("supplier_name", "") for r in valid_records})

        recent = sorted(valid_records, key=lambda r: r.get("timestamp", ""), reverse=True)[:10]
        recent_10 = [
            {
                "timestamp": r.get("timestamp", ""),
                "supplier": r.get("supplier_name", ""),
                "risk_level": r.get("risk_level"),
                "score": r.get("composite_score"),
                "evaluator": r.get("evaluator", ""),
            }
            for r in recent
        ]

        return {
            "total": len(valid_records) + len(invalid_lines),
            "valid": len(valid_records),
            "invalid": len(invalid_lines),
            "invalid_lines": invalid_lines,
            "suppliers": suppliers,
            "earliest": timestamps[0] if timestamps else "",
            "latest": timestamps[-1] if timestamps else "",
            "recent_10": recent_10,
            "status": "ok" if not invalid_lines else "warn",
        }

    def _iter_valid_records(self):
        """迭代日志文件中的有效 JSON 记录，跳过损坏行。"""
        if not self.log_path.exists():
            return
        with open(self.log_path, encoding="utf-8") as f:
            for lineno, line in enumerate(f, 1):
                line = line.rstrip("\n")
                if not line:
                    continue
                try:
                    yield json.loads(line), lineno
                except json.JSONDecodeError:
                    pass
