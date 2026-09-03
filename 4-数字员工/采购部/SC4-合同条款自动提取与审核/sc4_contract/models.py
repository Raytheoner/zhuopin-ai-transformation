"""SC4 结构模型 —— 只承载"文档里有什么"，不承载"它算不算风险"。

四类条款（价格 / 交付 / 质保 / 违约责任）**逐字取自全景规划 §2.1.2 SC4 场景块**
的「提取关键条款（价格、交付、质保、违约责任）」一句，不是本工程自拟的分类。
风险等级、偏差判定、缺失条款清单不在本模块——见 `pending.py`。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class ClauseType(str, Enum):
    """全景规划点名的四类关键条款。

    `OTHER` 是**如实兜底**而非扩展位：切不出类别的段落必须留痕，不能悄悄丢弃——
    骨架期最需要知道的恰恰是"有多少内容我们还看不懂"。
    """

    PRICE = "价格"
    DELIVERY = "交付"
    WARRANTY = "质保"
    PENALTY = "违约责任"
    OTHER = "未归类"


@dataclass(frozen=True)
class ClauseSpan:
    """一段被定位到的条款原文及其在源文档中的位置。

    保留 `start`/`end` 是为了可追溯（IATF）：审核摘要里的任何一句都能回指原文偏移量，
    而不是只留一段被模型改写过的转述。
    """

    clause_type: ClauseType
    heading: str
    text: str
    start: int
    end: int

    def __post_init__(self) -> None:
        if self.start < 0 or self.end < self.start:
            raise ValueError(f"非法区间：start={self.start} end={self.end}")


@dataclass
class ContractDocument:
    """一份待审合同的**已取文**形态。

    刻意不含 PDF/Word 字节：取文由 `text_source.py` 负责，本模型之后的一切只与纯文本
    打交道，使解析层可被单独替换（doc_parser 底座件尚未落地，见场景 CLAUDE.md §6）。
    """

    doc_id: str
    title: str
    text: str
    source: str = ""            # 取文来源标识，如 "mock:plaintext" / "srm:<文档号>"
    supplier_name: str = ""

    def __post_init__(self) -> None:
        if not self.doc_id:
            raise ValueError("doc_id 不可为空：审计留痕须可归档到具体合同")


@dataclass
class ExtractionResult:
    """一次抽取的完整产出。"""

    doc_id: str
    spans: list[ClauseSpan] = field(default_factory=list)
    lexicon_id: str = ""        # 用了哪份词表，写进 audit（词表会随法务批改升版）

    def by_type(self, clause_type: ClauseType) -> list[ClauseSpan]:
        return [s for s in self.spans if s.clause_type is clause_type]

    @property
    def covered_types(self) -> set[ClauseType]:
        """本文档**命中**了哪几类。

        🔴 它的补集**不等于**「缺失条款」——「缺哪几类算缺失、缺了算多大风险」属法务
        判据，见 `pending.py::require("risk_clause_criteria")`。此处只陈述命中事实。
        """
        return {s.clause_type for s in self.spans if s.clause_type is not ClauseType.OTHER}
