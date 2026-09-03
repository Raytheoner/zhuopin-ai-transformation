"""条款切分与定位 —— SC4 骨架期唯一真正跑得动的一层。

它做的是纯结构性的事：按编号标题把合同正文切成段，按词表给每段定类，保留原文偏移量。
**不做**比对、不打风险等级、不判缺失——那三件事全在 `pending.py` 后面。
"""
from __future__ import annotations

import re

from .clause_lexicon import ClauseLexicon
from .models import ClauseSpan, ClauseType, ContractDocument, ExtractionResult

#: 中文合同常见的条款标题行：`第三条 交付与验收` / `3. 交付与验收` / `三、交付`。
#: 只认**行首**，避免把正文里引用的"第三条"当成新段落开头。
_HEADING = re.compile(
    r"^[ \t]*(?:第\s*[一二三四五六七八九十百零〇\d]+\s*条|[一二三四五六七八九十]+\s*、|\d+(?:\.\d+)*[.、])\s*(?P<title>.*\S)?[ \t]*$",
    re.MULTILINE,
)


def segment(doc: ContractDocument, lexicon: ClauseLexicon) -> ExtractionResult:
    """把 `doc.text` 切成条款 span 并定类。

    `lexicon` **无默认值**，见 `clause_lexicon` 模块 docstring。

    切分口径（骨架期，可被后续 openspec 改，但改了要写进变更包）：
    - 一个 span ＝ 从某个标题行行首，到**下一个**标题行行首之前；末段到文末。
    - 标题行之前的引言部分不成 span（合同抬头、甲乙方信息不是条款）。
    - 整篇没有任何标题行时返回**空结果**，而不是把全文塞成一个 `OTHER` span——
      后者会让"这份文档我们根本没解析出结构"这件事消失在一条看似正常的记录里。
    """
    matches = list(_HEADING.finditer(doc.text))
    spans: list[ClauseSpan] = []
    for i, m in enumerate(matches):
        start = m.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(doc.text)
        heading = (m.group("title") or m.group(0)).strip()
        spans.append(
            ClauseSpan(
                clause_type=lexicon.classify(heading),
                heading=heading,
                text=doc.text[start:end].strip(),
                start=start,
                end=end,
            )
        )
    return ExtractionResult(doc_id=doc.doc_id, spans=spans, lexicon_id=lexicon.lexicon_id)


def summarize_coverage(result: ExtractionResult) -> dict[str, object]:
    """一份**只陈述事实、不下判断**的抽取概览，用于审计 payload 与人工复核。

    🔴 `missing_types` 这个字段刻意**不存在**：命中集合的补集在业务上不等于"缺失条款"
    （标准条款库尚未产出，谁也不知道这份合同本该有哪几类）。此处只给 `covered`。
    """
    return {
        "doc_id": result.doc_id,
        "lexicon_id": result.lexicon_id,
        "span_count": len(result.spans),
        "covered_types": sorted(t.value for t in result.covered_types),
        "unclassified_count": len(result.by_type(ClauseType.OTHER)),
    }
