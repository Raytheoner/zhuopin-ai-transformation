"""QD-B 全链评估入口 —— 解析 → 规则判定 → 评分 → audit 写入。

这是 task 6.5（审计接入）的实现：每次规则判定 + 评分运行后写 AuditEvent，
含规则版本 2026-07-03、样本标识、逐条判定结果，append-only hash-chain。
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from zhuopin_platform.audit import AuditEvent, AuditLogger

from .models import ProposalDocument, RuleResult
from .parser import ProposalParser
from .rules.engine import run_rules
from .scoring import ScoreResult, score

RULE_VERSION = "2026-07-03"
_DEFAULT_AUDIT_PATH = Path(__file__).resolve().parent.parent / "reports" / "qd_b_audit.jsonl"


@dataclass
class EvaluationResult:
    document: ProposalDocument
    rule_results: list[RuleResult]
    score_result: ScoreResult
    audit_event: AuditEvent


def _decision_payload(
    doc: ProposalDocument,
    results: list[RuleResult],
    sr: ScoreResult,
    sample_id: str,
) -> dict[str, Any]:
    return {
        "rule_version": RULE_VERSION,
        "sample_id": sample_id,
        "template_version": doc.template_version,
        "project_type": doc.project_type,
        "tier": sr.tier,
        "total_score": sr.total_score,
        "veto": sr.veto,
        "veto_rules": sr.veto_rules,
        "provisional": sr.provisional,
        "evaluated": sr.evaluated,
        "pending": sr.pending,
        "per_rule": [
            {
                "rule_id": r.rule_id,
                "verdict": r.verdict.value,
                "severity": r.severity_level,
                "evidence": r.evidence,
            }
            for r in results
        ],
    }


def evaluate(
    document_path: str | Path,
    *,
    evaluator: str = "AI预审",
    audit_path: str | Path | None = None,
    sample_id: str = "",
) -> EvaluationResult:
    """解析立项书 → 运行规则 → 评分 → 写 audit，返回完整评估结果。

    Args:
        document_path: 立项书 Excel 文件路径。
        evaluator: 审计责任人标识（L2 可填人名；AI 预审阶段默认 "AI预审"）。
        audit_path: audit JSONL 输出路径；None 则写 reports/qd_b_audit.jsonl。
        sample_id: 可选的样本标识符；不传则用文件名（脱敏后可覆盖）。
    """
    doc_path = Path(document_path)
    sid = sample_id or doc_path.stem

    doc: ProposalDocument = ProposalParser(doc_path).parse()
    results: list[RuleResult] = run_rules(doc)
    sr: ScoreResult = score(results)

    payload = _decision_payload(doc, results, sr, sid)
    content_hash = hashlib.sha256(
        json.dumps(payload, ensure_ascii=False, sort_keys=True).encode()
    ).hexdigest()

    event = AuditEvent(
        scenario="QD-B",
        action="project_gate_review",
        evaluator=evaluator,
        automation_level="L2",
        decision=payload,
        data_sources={
            "document": doc_path.name,
            "rule_registry": "data/rules/registry.json",
        },
        content_hash=content_hash,
    )

    log_path = Path(audit_path) if audit_path else _DEFAULT_AUDIT_PATH
    log_path.parent.mkdir(parents=True, exist_ok=True)
    audit = AuditLogger.jsonl(log_path)
    audit.record(event)

    return EvaluationResult(
        document=doc,
        rule_results=results,
        score_result=sr,
        audit_event=event,
    )
