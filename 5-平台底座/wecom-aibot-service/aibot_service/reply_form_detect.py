"""队列 #446：回件形态识别 —— 把拆件巡逻章程 §二 三条硬约束机器化。

**背景（成因，勿删——决定了本模块为什么长这样）**：拆件巡逻实践里，"读回件
文档"这一步已至少错 4 次，且每次都得出"对方什么都没答"这个**反向**结论：
- 质量部/财务部专员连续多封用"正文插高亮段"作答（0 批注 0 修订 0 勾选、
  数十处高亮），按"找批注或勾选"的老习惯读即全空；
- 采购部一封回件 9 个 `w14:checkbox` 真复选框实际勾了 3 个，被读成全空，
  致使已回复的专员又多回一封本不必回的信；
- 同一批回件里，专员把勾选写在段落文字里（不在表格内），只扫表格的读法
  把它整个漏掉。

根因不是"工具读不出来"——`0-学习与工具/md转Word工具/md2word.py:85` 的
`read_checkboxes()` 早已存在且实现正确（用 `element.iter()` 做整树遍历，
天然覆盖表格内外）。真正缺的是"流程里有没有一处必然会调用它的位置"。本模块
把"数清楚回件文档里有什么"做成一个独立、可被单测钉住的步骤；**语义判断
（这算不算已作答、该不该据此改判）不在本模块范围内，仍然留给人**——见
`5-平台底座/CLAUDE.md`／队列 `#446` 状态列「边界：语义判断与回灌仍留人」。

三条硬约束（拆件巡逻章程 §二）与本模块设计的对应关系：
1. 必须通读整份文档全部段落，禁止只解析表格
   → 全部计数函数一律走 `Element.iter()` 做整棵树的深度优先遍历，从不先
     `find('.//w:tbl')` 再局部处理；`extract_full_paragraphs()` 输出的顺序
     天然覆盖正文段落与表格单元格段落，不能只选其一。
2. ✏️ 列非空 ≠ 改判，必须核对 ✅/❌ 列的实际字符
   → `extract_tables()` 按行读出每个单元格的**原始字符**（含 Unicode 符号
     如 ✅❌✏️☒☐），不按列名/列位置猜语义，交由人核对实际字符。
3. 同批多行到件必须合并读取
   → 本模块只负责把单份文档读透；"同批多份要合并看"是巡逻上层（跨文档）
     的职责，不下沉到本模块。

用法：
    from aibot_service.reply_form_detect import detect_reply_form
    report = detect_reply_form(path)
    print(report.summary())
    print(report.forms_present)       # ["checkbox", "highlight", ...]
"""
from __future__ import annotations

import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from xml.etree import ElementTree as ET

W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
W14_NS = "http://schemas.microsoft.com/office/word/2010/wordml"
_NS_BY_PREFIX = {"w": W_NS, "w14": W14_NS}

DOCUMENT_PART = "word/document.xml"
COMMENTS_PART = "word/comments.xml"
# 队列 #446 原文点名 `word/comments*`——除主内容件 comments.xml 外，
# commentsExtended.xml/commentsIds.xml/commentsExtensible.xml 等衍生部件
# 不含批注正文，但它们存在本身就是"这份文档曾经有批注"的信号，一并记入
# 部件清单扫描结果，供人判读，不因为暂不解析其内容就假装没看见。
COMMENTS_PART_PREFIX = "word/comments"

# 本模块识别为"纯文本回件"的扩展名——企微文本消息按 R6 归档落这两类文件，
# 结构性上不存在 w14:checkbox/w:highlight 等 docx 专属形态,必须整份通读。
PLAIN_TEXT_SUFFIXES = {".md", ".txt"}


def qn(tag: str) -> str:
    """`"w:p"` → 带命名空间花括号的 Clark 记法标签，供 ElementTree 查找用。"""
    prefix, local = tag.split(":")
    return f"{{{_NS_BY_PREFIX[prefix]}}}{local}"


def _local(tag: str) -> str:
    """去掉命名空间前缀，取标签本名（`"{ns}p"` → `"p"`）。"""
    return tag.rsplit("}", 1)[-1] if "}" in tag else tag


def _text_of(el: ET.Element) -> str:
    """取一个元素子树内全部 `w:t`（含 `w:delText`）文字，按文档顺序拼接。

    不用 `"".join(el.itertext())`——那会把 `w:t` 的 `xml:space="preserve"`
    之外的元素属性值、以及非文本节点的杂散字符一并吃进来；只认 `w:t`／
    `w:delText` 两种"这就是可见文字"的标签，读到的字符与人在 Word 里看到
    的一致，这正是硬约束 2（"看字符，不看列名"）成立的前提。
    """
    parts: list[str] = []
    for node in el.iter():
        tag = _local(node.tag)
        if tag in ("t", "delText") and node.text:
            parts.append(node.text)
        elif tag == "tab":
            parts.append("\t")
        elif tag == "br" or tag == "cr":
            parts.append("\n")
    return "".join(parts)


@dataclass
class CheckboxItem:
    index: int
    checked: bool
    context: str
    in_table: bool


@dataclass
class HighlightSpan:
    paragraph_index: int
    text: str
    color: str | None = None


@dataclass
class RevisionItem:
    kind: str  # "ins" | "del"
    author: str | None
    date: str | None
    text: str


@dataclass
class CommentItem:
    comment_id: str
    author: str | None
    date: str | None
    comment_text: str
    anchor_text: str  # 批注锚定的原文片段（w:commentRangeStart~End 之间的文字）


@dataclass
class TableSnapshot:
    table_index: int
    rows: list[list[str]]


@dataclass
class ReplyFormReport:
    source_path: str
    doc_type: str  # "docx" | "plain_text"
    full_paragraphs: list[str] = field(default_factory=list)
    tables: list[TableSnapshot] = field(default_factory=list)
    checkboxes: list[CheckboxItem] = field(default_factory=list)
    highlights: list[HighlightSpan] = field(default_factory=list)
    comments: list[CommentItem] = field(default_factory=list)
    revisions: list[RevisionItem] = field(default_factory=list)
    comment_part_names: list[str] = field(default_factory=list)
    plain_text: str | None = None
    # 🔴 与 `highlights`（合并后的可读高亮段）刻意分开维护——真实回归对照时
    # 发现，历史"N 处高亮"数字（如财务部#14 的 78、#15 的 55）是"文档里任意
    # 位置出现过多少个 <w:highlight> 元素"的**原始计数**，其中包含段落标记
    # 自身（`w:pPr/w:rPr/w:highlight`，Word 对整段落加高亮时连结尾符都会带
    # 上这个属性、但它不对应任何可见文字）而非只数 run 级高亮；`highlights`
    # 合并连续高亮 run 成段落级可读片段后数字会小得多且更有用（同一份
    # 财务部#14 文档：78 处原始元素 ⇒ 7 段有意义的高亮叙事），两个数字回答
    # 的是不同问题，都保留、不能只留一个。
    raw_highlight_element_count: int = 0

    @property
    def checked_count(self) -> int:
        return sum(1 for c in self.checkboxes if c.checked)

    @property
    def unchecked_count(self) -> int:
        return sum(1 for c in self.checkboxes if not c.checked)

    @property
    def insert_count(self) -> int:
        return sum(1 for r in self.revisions if r.kind == "ins")

    @property
    def delete_count(self) -> int:
        return sum(1 for r in self.revisions if r.kind == "del")

    @property
    def forms_present(self) -> list[str]:
        """本文档里**实际出现过**的形态（可能不止一种）。

        🔴 只报"有没有"，不越界替人下"这算不算已作答"的判断——那是队列
        `#446` 状态列写明必须留人的边界。没有任何结构化形态、但确有正文
        （docx 全靠自由文本作答）时归为 `plain_narrative`，提醒读的人：
        这份文档必须整份通读，机器在这里没有能替你省的步骤。
        """
        forms: list[str] = []
        if self.checkboxes:
            forms.append("checkbox")
        if self.highlights:
            forms.append("highlight")
        if self.comments:
            forms.append("comment")
        if self.revisions:
            forms.append("revision")
        if self.doc_type == "plain_text":
            forms.append("plain_text_reply")
        elif not forms:
            forms.append("plain_narrative")
        return forms

    def summary(self) -> str:
        if self.doc_type == "plain_text":
            n = len(self.plain_text or "")
            return f"纯文本回件（.md/.txt），{n} 字符，须整份通读"
        return (
            f"{len(self.comments)} 批注 / "
            f"{self.insert_count} 处插入+{self.delete_count} 处删除(修订) / "
            f"{len(self.checkboxes)} 勾选({self.checked_count} 已勾/"
            f"{self.unchecked_count} 未勾) / "
            f"{len(self.highlights)} 段高亮叙事(原始 <w:highlight> 元素 "
            f"{self.raw_highlight_element_count} 处) / "
            f"{len(self.full_paragraphs)} 个段落(含表格单元格)"
        )


def _build_parent_map(root: ET.Element) -> dict[ET.Element, ET.Element]:
    return {child: parent for parent in root.iter() for child in parent}


def _ancestor_paragraph(
    el: ET.Element, parent_map: dict[ET.Element, ET.Element]
) -> ET.Element | None:
    cur = el
    while cur is not None:
        if _local(cur.tag) == "p":
            return cur
        cur = parent_map.get(cur)
    return None


def _is_inside_table(
    el: ET.Element, parent_map: dict[ET.Element, ET.Element]
) -> bool:
    cur = parent_map.get(el)
    while cur is not None:
        if _local(cur.tag) == "tbl":
            return True
        cur = parent_map.get(cur)
    return False


def extract_full_paragraphs(root: ET.Element) -> list[str]:
    """按文档真实顺序取出**全部**段落文字，正文段落与表格单元格段落一视同仁。

    硬约束 1 的直接落点：`root.iter(qn("w:p"))` 是深度优先前序遍历，天然按
    文档出现顺序穿过 `w:tbl/w:tr/w:tc` 内部——**不需要、也不应该**先摘出
    `w:tbl` 单独处理再摘正文段落单独处理，那正是"只解析表格"或者反过来
    "只扫正文漏了表格"两类历史误判共同的根。
    """
    return [_text_of(p) for p in root.iter(qn("w:p"))]


def extract_tables(root: ET.Element) -> list[TableSnapshot]:
    """逐表逐行逐格取出**原始字符**，不对列名/列位置做任何语义解释。

    硬约束 2 的直接落点：调用方要判断"✅/❌/✏️ 哪一列被打了勾"，必须自己
    比对表头文字与本函数给出的单元格原始字符——本函数不做这一步，避免把
    "列在哪" 和 "列写了什么" 这两件事混为一谈（真实事故：✏️ 列非空不等于
    改判，✅/❌ 列的字符才是准确答案）。
    """
    snapshots: list[TableSnapshot] = []
    for idx, tbl in enumerate(root.iter(qn("w:tbl"))):
        rows: list[list[str]] = []
        for tr in tbl.findall(qn("w:tr")):
            cells = [_text_of(tc) for tc in tr.findall(qn("w:tc"))]
            rows.append(cells)
        snapshots.append(TableSnapshot(table_index=idx, rows=rows))
    return snapshots


def extract_checkboxes(
    root: ET.Element, parent_map: dict[ET.Element, ET.Element] | None = None
) -> list[CheckboxItem]:
    """取出全部 `w14:checkbox` 内容控件的勾选状态，按文档顺序、不限表格内外。

    与 `md转Word工具/md2word.py::read_checkboxes()` 同一判据（`w14:checked`
    的 `w14:val`），额外补上 `in_table` 标记——真实事故里，专员把勾选写在
    段落文字里（不在表格内）曾被"只扫表格"的读法整个漏掉，这里显式把每个
    勾选控件在不在表格内标出来，供调用方自查是否漏了某一类。
    """
    parent_map = parent_map or _build_parent_map(root)
    items: list[CheckboxItem] = []
    for idx, sdt in enumerate(root.iter(qn("w:sdt"))):
        cb = sdt.find(f".//{qn('w14:checkbox')}")
        if cb is None:
            continue
        checked_el = cb.find(qn("w14:checked"))
        checked = checked_el is not None and checked_el.get(qn("w14:val")) == "1"
        para = _ancestor_paragraph(sdt, parent_map)
        context = _text_of(para) if para is not None else ""
        items.append(
            CheckboxItem(
                index=idx,
                checked=checked,
                context=context,
                in_table=_is_inside_table(sdt, parent_map),
            )
        )
    return items


def count_raw_highlight_elements(root: ET.Element) -> int:
    """数文档里**任意位置**出现过多少个 `<w:highlight>` 元素（含段落标记自身）。

    与真实历史事故对照坐实的口径：财务部#14/#15 队列行分别记「w:highlight
    78 处」「55 处高亮」，实测均为本函数这个原始计数，而非 `extract_highlights`
    合并连续 run 后的段落数（同一份文档分别是 7 段、4 段）——两个数字回答
    不同问题都有用，本函数专为对齐历史记录/做回归比对而存在。
    """
    return sum(1 for _ in root.iter(qn("w:highlight")))


def extract_highlights(root: ET.Element) -> list[HighlightSpan]:
    """按段落合并**连续**高亮 run，取出高亮段落全文。

    真实事故（财务部#14/#15、质量部同族多封）：专员不勾复选框、不加批注、
    不用修订，直接在回信正文里把答复用"高亮"标出——旧读法照抄"找批注/
    找勾选"的老习惯会得到"她什么都没答"这个反向结论。本函数按段落顺序把
    相邻的高亮 run 拼接成一段，返回每段的完整文字，供人直接读到她写了
    什么，而不是只报"有 N 处高亮"这个数字。
    """
    spans: list[HighlightSpan] = []
    paragraphs = list(root.iter(qn("w:p")))
    for p_idx, p in enumerate(paragraphs):
        buffer: list[str] = []
        buffer_color: str | None = None
        for run in p.iter(qn("w:r")):
            rpr = run.find(qn("w:rPr"))
            highlight_el = rpr.find(qn("w:highlight")) if rpr is not None else None
            color = highlight_el.get(qn("w:val")) if highlight_el is not None else None
            is_highlighted = bool(color) and color != "none"
            run_text = "".join(
                t.text or "" for t in run.findall(qn("w:t"))
            )
            if is_highlighted and run_text:
                buffer.append(run_text)
                buffer_color = buffer_color or color
            else:
                if buffer:
                    spans.append(
                        HighlightSpan(
                            paragraph_index=p_idx,
                            text="".join(buffer),
                            color=buffer_color,
                        )
                    )
                    buffer = []
                    buffer_color = None
        if buffer:
            spans.append(
                HighlightSpan(
                    paragraph_index=p_idx, text="".join(buffer), color=buffer_color
                )
            )
    return spans


def extract_revisions(root: ET.Element) -> list[RevisionItem]:
    """取出全部 `w:ins`（插入）/`w:del`（删除）修订，按文档顺序。"""
    revisions: list[RevisionItem] = []
    for node in root.iter():
        tag = _local(node.tag)
        if tag not in ("ins", "del"):
            continue
        author = node.get(qn("w:author"))
        date = node.get(qn("w:date"))
        text = _text_of(node)
        revisions.append(RevisionItem(kind=tag, author=author, date=date, text=text))
    return revisions


def extract_comments(
    root: ET.Element, comments_root: ET.Element | None
) -> list[CommentItem]:
    """合并 `word/comments.xml` 的批注正文与 `document.xml` 里的锚定原文。

    锚定原文＝`w:commentRangeStart`（某 id）到对应 `w:commentRangeEnd` 之间
    的可见文字——即"专员这句批注是针对原文哪一段说的"，与批注正文一并
    返回,免得读的人还要自己去 docx 里对着找。
    """
    if comments_root is None:
        return []
    comment_text_by_id: dict[str, tuple[str | None, str | None, str]] = {}
    for c in comments_root.iter(qn("w:comment")):
        cid = c.get(qn("w:id")) or ""
        author = c.get(qn("w:author"))
        date = c.get(qn("w:date"))
        comment_text_by_id[cid] = (author, date, _text_of(c))

    anchor_text_by_id: dict[str, str] = {}
    open_ids: dict[str, list[str]] = {}
    for node in root.iter():
        tag = _local(node.tag)
        if tag == "commentRangeStart":
            cid = node.get(qn("w:id")) or ""
            open_ids[cid] = []
        elif tag == "commentRangeEnd":
            cid = node.get(qn("w:id")) or ""
            if cid in open_ids:
                anchor_text_by_id[cid] = "".join(open_ids.pop(cid))
        elif tag == "t" and node.text:
            for buf in open_ids.values():
                buf.append(node.text)

    items: list[CommentItem] = []
    for cid, (author, date, text) in comment_text_by_id.items():
        items.append(
            CommentItem(
                comment_id=cid,
                author=author,
                date=date,
                comment_text=text,
                anchor_text=anchor_text_by_id.get(cid, ""),
            )
        )
    return items


def _parse_docx_xml_part(zf: zipfile.ZipFile, part_name: str) -> ET.Element | None:
    try:
        data = zf.read(part_name)
    except KeyError:
        return None
    return ET.fromstring(data)


def detect_docx_form(path: str | Path) -> ReplyFormReport:
    """对一份 `.docx` 回件做形态识别：`zipfile` 直读部件清单 + 解析正文/批注 XML。

    🔴 刻意不经 `python-docx` 的高层对象模型——`python-docx` 不暴露批注
    （comments）与高亮（highlight）读取能力，且高层模型会把"这个复选框
    在不在表格里"这类结构信息抽象掉；直接读 `word/document.xml` 的原始
    XML 树，是唯一能同时满足三条硬约束的路径。
    """
    path = Path(path)
    with zipfile.ZipFile(path) as zf:
        namelist = zf.namelist()
        comment_parts = [n for n in namelist if n.startswith(COMMENTS_PART_PREFIX)]

        document_root = _parse_docx_xml_part(zf, DOCUMENT_PART)
        if document_root is None:
            raise ValueError(f"{path}：不是合法的 .docx（缺 {DOCUMENT_PART}）")
        comments_root = _parse_docx_xml_part(zf, COMMENTS_PART)

    parent_map = _build_parent_map(document_root)
    return ReplyFormReport(
        source_path=str(path),
        doc_type="docx",
        full_paragraphs=extract_full_paragraphs(document_root),
        tables=extract_tables(document_root),
        checkboxes=extract_checkboxes(document_root, parent_map),
        highlights=extract_highlights(document_root),
        comments=extract_comments(document_root, comments_root),
        revisions=extract_revisions(document_root),
        comment_part_names=comment_parts,
        raw_highlight_element_count=count_raw_highlight_elements(document_root),
    )


def detect_plain_text_form(path: str | Path) -> ReplyFormReport:
    """`.md`/`.txt` 纯文本回件：没有 docx 结构化形态，整份原文即"形态"。"""
    path = Path(path)
    text = path.read_text(encoding="utf-8", errors="replace")
    return ReplyFormReport(source_path=str(path), doc_type="plain_text", plain_text=text)


def detect_reply_form(path: str | Path) -> ReplyFormReport:
    """按扩展名分派：`.docx` 走结构化识别，`.md`/`.txt` 走纯文本整份读出。"""
    path = Path(path)
    if path.suffix.lower() == ".docx":
        return detect_docx_form(path)
    if path.suffix.lower() in PLAIN_TEXT_SUFFIXES:
        return detect_plain_text_form(path)
    raise ValueError(
        f"{path}：不认得的回件文件类型（仅支持 .docx／{sorted(PLAIN_TEXT_SUFFIXES)}）"
    )
