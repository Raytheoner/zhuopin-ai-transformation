"""取文层 —— 把「PDF/Word 怎么变成字符串」这件事隔离在一个可替换的接口后面。

## 为什么骨架期只有纯文本实现

平台底座的统一 `doc_parser` **尚未落地**（`5-平台底座/CLAUDE.md` §4 现状表：
`shared_tools/` 已收割连接器与 notifiers，「doc_parser 待质量旗舰落地」）。
SC4 若自己写一份 PDF/Word 解析，就是在底座之外造第二份同职责实现——正是
`4-数字员工/CLAUDE.md` 第 1 步要禁的事（import 底座、不重复造轮子）。

⇒ 骨架期定义接口 + 一个纯文本实现，把真实取文留给底座件到位后接入；
接口一旦定死，接入那天改的是**一个类**，不是抽取层与审核层。
"""
from __future__ import annotations

from pathlib import Path
from typing import Protocol

from .models import ContractDocument


class TextSource(Protocol):
    """任何能把一份合同变成 `ContractDocument` 的东西。"""

    def load(self, ref: str) -> ContractDocument: ...


class PlainTextSource:
    """从 `.txt`/`.md` 读取的 mock 取文实现（红线 §7-1：先 mock 跑通再切真实库）。

    刻意**不**兼容 `.pdf`/`.docx` 后缀：静默把二进制当文本读会产出一堆乱码 span，
    看起来"跑通了"。这里宁可当场报错。
    """

    SUPPORTED = (".txt", ".md")

    def __init__(self, base_dir: Path | str):
        self.base_dir = Path(base_dir)

    def load(self, ref: str) -> ContractDocument:
        path = self.base_dir / ref
        if path.suffix.lower() not in self.SUPPORTED:
            raise ValueError(
                f"PlainTextSource 只支持 {self.SUPPORTED}，收到 {path.suffix!r}。"
                " 真实 PDF/Word 取文须等平台底座 doc_parser 落地后接入，"
                " 不在本场景内自建解析（见本模块 docstring）。"
            )
        text = path.read_text(encoding="utf-8")
        return ContractDocument(
            doc_id=path.stem,
            title=path.stem,
            text=text,
            source=f"mock:plaintext:{path.name}",
        )
