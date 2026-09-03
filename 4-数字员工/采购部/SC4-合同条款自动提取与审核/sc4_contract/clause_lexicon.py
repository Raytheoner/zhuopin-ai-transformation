"""条款定位词表 —— 骨架期的 mock 词表，**不是法务判据**。

## 这份词表和「合同风险条款判据」的区别（本文件存在的唯一理由）

- 本词表回答的是「这一段**在讲**价格/交付/质保/违约吗」——一个**定位**问题，
  错了就是段落归错类，看一眼原文即可发现。
- `pending.py` 挡住的是「这一段**算不算**偏离标准、风险多高」——一个**判定**问题，
  错了会得出一个法务从未认可、却写进审核摘要的结论。

两者刻意分开，是为了让「骨架期能跑」不至于顺带把判定也一起默认掉。

🔴 **词表必须由调用方显式传入**（`clause_extract.segment` 无默认参数）：留一个默认值，
下一个人就会在真实合同上直接调用它并相信结果。词条本身取自全景规划 SC4 场景块点名的
四类，**未做任何扩充**；真实词表待法务标注 ≥20 份历史合同后由前置产出（前置总表 §一.2
「案例反推」方法）。
"""
from __future__ import annotations

from dataclasses import dataclass

from .models import ClauseType


@dataclass(frozen=True)
class ClauseLexicon:
    """`lexicon_id` 会写进 audit —— 词表升版后，旧结论仍能被认出是旧词表产的。"""

    lexicon_id: str
    keywords: dict[ClauseType, tuple[str, ...]]

    def classify(self, heading: str) -> ClauseType:
        """按标题命中定类；多类命中时**不猜**，退回 `OTHER` 交人判。"""
        hits = [t for t, kws in self.keywords.items() if any(k in heading for k in kws)]
        return hits[0] if len(hits) == 1 else ClauseType.OTHER


#: 骨架期 mock 词表。命名里带 `mock` 是刻意的：它会原样进 audit，
#: 任何一条用它产出的记录都自带"这不是法务口径"的标记。
MOCK_LEXICON = ClauseLexicon(
    lexicon_id="mock-v0",
    keywords={
        ClauseType.PRICE: ("价格", "单价", "价款", "结算"),
        ClauseType.DELIVERY: ("交付", "交货", "供货", "到货"),
        ClauseType.WARRANTY: ("质保", "保修", "质量保证"),
        ClauseType.PENALTY: ("违约", "赔偿", "罚则"),
    },
)
