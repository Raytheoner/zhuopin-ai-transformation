"""SC4 场景入口 —— 骨架期只跑「取文 → 切分 → 留痕」，审核层整段留步。

自动化等级 L2（全景规划 §2.1.2 SC4：AI 初步审核 + 风险标记，法务/采购经理确认）。
骨架期连"初步审核"都还产不出（判据未到位），故本入口输出的是**抽取结果**，
并在 audit 里如实标 `review_status="待前置到位"`，不冒充一次审核。
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from zhuopin_platform.audit import AuditEvent, AuditLogger

from .clause_extract import summarize_coverage
from .clause_lexicon import ClauseLexicon
from .models import ContractDocument, ExtractionResult
from . import clause_extract

SCENARIO = "SC4"
ACTION = "contract_clause_extract"


def _content_hash(payload: dict[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()


def run_extraction(
    doc: ContractDocument,
    lexicon: ClauseLexicon,
    *,
    evaluator: str,
    audit: AuditLogger | None = None,
) -> ExtractionResult:
    """抽取一份合同的条款并写审计。

    `evaluator` 必填且非空 —— L2 场景的可归责人是 IATF 审计的硬要求（AuditEvent 注释
    已写明"L2 场景必填"，但该字段本身不校验，故在此处守）。
    """
    if not evaluator.strip():
        raise ValueError("evaluator 不可为空：L2 场景须留可归责人（IATF 16949）")

    result = clause_extract.segment(doc, lexicon)
    coverage = summarize_coverage(result)

    if audit is not None:
        audit.record(
            AuditEvent(
                scenario=SCENARIO,
                action=ACTION,
                evaluator=evaluator,
                automation_level="L2",
                decision={
                    **coverage,
                    # 骨架期的诚实标注：抽取已完成、审核未开始，两者不可混为一谈
                    "review_status": "待前置到位",
                    "blocked_by": ["standard_clause_library", "risk_clause_criteria"],
                },
                data_sources={"contract": doc.source or "unknown", "lexicon": lexicon.lexicon_id},
                content_hash=_content_hash(coverage),
            )
        )
    return result


def main(sample_dir: Path | str, ref: str, evaluator: str = "骨架期自测") -> ExtractionResult:
    """mock 模式手跑入口：`python -m sc4_contract.agent`（见 README）。"""
    from .clause_lexicon import MOCK_LEXICON
    from .text_source import PlainTextSource

    doc = PlainTextSource(sample_dir).load(ref)
    return run_extraction(doc, MOCK_LEXICON, evaluator=evaluator)


if __name__ == "__main__":  # pragma: no cover - 手跑入口
    here = Path(__file__).resolve().parent.parent
    res = main(here / "tests" / "mock_data", "sample_contract.md")
    print(json.dumps(summarize_coverage(res), ensure_ascii=False, indent=2))
