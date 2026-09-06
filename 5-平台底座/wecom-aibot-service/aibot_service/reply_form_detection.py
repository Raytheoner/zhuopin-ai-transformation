"""回件形态识别 —— 队列 #446：把拆件巡逻章程 §二 三条硬约束机器化。

## 缺陷成因（队列 #446 原文实测，不在此复述全文，只留本模块要治的那一句）
读回件形态这一步人已至少错 4 次，每次都把"对方其实答了"读成"对方什么都
没答"：唐燕萍用高亮段作答被当成空、姚祖怡 9 格实际勾了 3 个被读成全空、
段落里的勾选被漏读。🔴 **本行经交叉核实已更正一处队列 #446 原文的误引**
——原文把"高亮段作答"那两封（`财务部#14`／`#15`）写成了"陈忱 质量部
#9／#10"；`README-跟进机制与命名约定.md` L133 原话是"她 `财务部#14`／
`#15` 连续两封都没勾控件、而是在正文插高亮段作答"，指的是唐燕萍，与
`质量部#9`（陈忱）经本模块对真实归档 docx 实测＝14 个复选框、零高亮，
形态正好相反——同一批次派单件里的转述已出过一次"张冠李戴"，如实登记、
不代队列 #446 改判（该行由总线维护）。根因不是工具缺失——`0-学习与
工具/md转Word工具/md2word.py:85` 的 `read_checkboxes()` 早已能读复选框
——根因是**读形态这一步在拆件流程里压根没有必然会被执行的位置**，全凭
人凭习惯扫一眼。本模块把"扫一眼"换成"每次都跑全部四类信号探测"，堵的
是这一个漏洞，不是重新发明一个更聪明的阅读器。

## 四类信号，一次性探测，不做取舍、不猜"这封信应该是哪种形态"
`w14:checkbox`（真复选框内容控件）／`w:ins`·`w:del`（修订标记）／
`word/comments*`（批注部件）／`w:highlight`（高亮）——四类互不排斥，现实
中的回件常混用：`采购部#19` 同一份 docx 里复选框与高亮同时出现；
`质量部#9` 用了 14 个复选框（☒6/☐8，README 已用 XML 取证核对过，见
`test_reply_form_detection.py` 同口径回归用例）、零高亮零批注零修订；
`财务部#14`／`#15` 反过来只用高亮、零复选框零批注零修订——README 记的
"55~78 处"是对 `<w:highlight` 做裸字符串计数的结果，本模块实测这两个
数字里各混了 4／7 个不含任何文字、纯属"段落标记"的高亮残留（`w:pPr/
w:rPr/w:highlight`，Word 给整段连同结尾隐藏换行符一起高亮时的副产物），
按实际承载文字的 run 数数分别是 51／71（见 `HighlightSpan.run_count`
文档字符串，两个口径都保留、不用一个覆盖另一个）。**先四类各自计数，
逐一報告，不预设"这类回件通常用哪种"**——预设正是本模块要根治的那个
错误模式本身。

## 一处刻意的宽松：结构化控件之外的裸字符也报，但不冒充语义
`w14:checkbox` 是结构化控件，但真人编辑 docx 时完全可能不点控件、直接在
段落文字里敲一个 ☒/☐/☑ 字符（尤其是把控件复制粘贴走样、或用别的软件
打开另存之后）。若只认结构化控件，这类"人以为自己表达了勾选意图、机器
看不到控件"的情况会被静默略过——这与本模块要堵的失效同构。故控件范围
之外单独出现的裸字符另计一类（`loose_checkbox_chars`），**不并入
`checkbox_total`，也不假装知道它的勾选语义**（裸字符没有"checked"这个
布尔状态可读，只有"这里有一个字符，长得像勾选，人工看一眼"）。

## 只做识别与结构化提取，不做语义判断（队列 #446 明写的边界）
本模块输出止于"这份 docx 里有什么、原文写了什么"，不产生任何"建议"或
"结论"字段——语义判断（这段高亮是不是反对、这个批注要不要采纳）仍须
人工，防止本模块的输出被误当成可以直接回灌权威载体的判定结果。
"""
from __future__ import annotations

import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Union
from xml.etree import ElementTree as ET

W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
W14_NS = "http://schemas.microsoft.com/office/word/2010/wordml"

DOCUMENT_PART = "word/document.xml"

# 批注部件命名不止一种（`word/comments.xml` 是主体，Word 新版还会伴生
# `word/commentsExtended.xml`／`word/commentsIds.xml`），队列 #446 原文写的
# 判据是「`word/comments*` 命中」——只要仓库里出现任一以此为前缀的部件，
# 就代表这份 docx 携带批注功能，不必逐个列举当前 Word 版本用了哪几个。
COMMENTS_PART_PREFIX = "word/comments"

CHECKBOX_LIKE_CHARS = ("☐", "☑", "☒")
CHECKED_CHARS = ("☑", "☒")


def _w(tag: str) -> str:
    return f"{{{W_NS}}}{tag}"


def _w14(tag: str) -> str:
    return f"{{{W14_NS}}}{tag}"


# ---------------------------------------------------------------- 数据结构

@dataclass
class CheckboxItem:
    """一个 `w14:checkbox` 内容控件。

    `context` 只是控件自身所在段落/单元格的文字——真实回件里控件常常
    独占一个表格单元格（判例批改表的常见排版：一列放选项文字、隔壁一列
    放对应的 ☒/☐ 控件），此时 `context` 会只剩一个孤零零的 ☒/☐，看不出
    "勾的是哪一项"。`row_context` 补这一环：控件若位于表格内，给出**同一
    行**其余单元格拼接的文字（判例批改法的行标签／题干通常就在同一行的
    其他列）——这正是队列 #446 point ⑶「9 格实际勾了 3 个被读成全空」
    的根因所在的那类排版，不带行上下文就等于没解决那个真实事故。
    """
    checked: bool
    context: str  # 所在段落/单元格完整文字（含控件自身显示的 ☒/☐ 字符）
    row_context: str = ""  # 控件若在表格内，同一行其余单元格拼接的文字；不在表格内则为空串


@dataclass
class LooseCheckboxChar:
    """不在任何 `w14:checkbox` 控件里、单独出现的 ☐/☑/☒ 字符——结构化
    控件之外的"裸字符"，勾选语义无法机器判定，只报字符与上下文供人工看。
    """
    char: str
    context: str


@dataclass
class HighlightSpan:
    """一段连续同色高亮的原文全文（跨多个 `w:r` 已按颜色合并）。

    `run_count` 记这一段合并前原本是几个 `w:r`——**不是为了展示**，是为了
    跟 README 里已经写死的历史口径对账：`财务部#14`/`#15` 的"55~78 处
    高亮"来自对 `<w:highlight` 做裸字符串计数（78／55）。**实测两份文件
    各自的 78／55 里都混了 7／4 个不含任何可读文字的"段落标记"高亮
    （`w:pPr/w:rPr/w:highlight`——Word 给整段连同其结尾的隐藏换行符一起
    高亮时，会单独给这个不可见的段落标记也记一条 `w:highlight`，本身没
    有 `w:t` 可读）**；本模块只对承载实际文字的 run 计数，得到的是
    71／51——与历史口径的差额（7／4）不是缺陷，是历史数字本身把
    「有内容的高亮」和「段落标记的格式残留」混在一起数了。两个数字统计
    口径不同、都如实保留在下面 `FormSignals.highlight_run_count_total`
    与本字段里，不用一个去覆盖另一个。
    """
    color: str
    text: str
    paragraph_index: int
    paragraph_text: str  # 高亮所在整段原文，供人核对语境
    run_count: int = 1  # 合并前原始 run 数（≥1）


@dataclass
class CommentItem:
    comment_id: str
    author: str
    date: str
    text: str
    anchor_text: str  # 批注圈住的原文片段；圈不到（无 commentRange 标记）时为空串


@dataclass
class TrackedChange:
    kind: str  # "ins" | "del"
    author: str
    date: str
    text: str


@dataclass
class FormSignals:
    """①②③ 一次探测的结构化产出，供拆件班次材料直接消费。"""
    docx_path: str
    part_names: List[str] = field(default_factory=list)
    checkboxes: List[CheckboxItem] = field(default_factory=list)
    loose_checkbox_chars: List[LooseCheckboxChar] = field(default_factory=list)
    highlights: List[HighlightSpan] = field(default_factory=list)
    comments: List[CommentItem] = field(default_factory=list)
    tracked_changes: List[TrackedChange] = field(default_factory=list)

    @property
    def checkbox_checked_count(self) -> int:
        return sum(1 for c in self.checkboxes if c.checked)

    @property
    def checkbox_unchecked_count(self) -> int:
        return sum(1 for c in self.checkboxes if not c.checked)

    @property
    def highlight_run_count_total(self) -> int:
        """未合并的原始高亮 run 总数——对得上 README 里"55~78 处高亮"这
        类历史口径的统计粒度（`highlights` 列表长度是合并后的段数，两者
        刻意不是同一个数字，见 `HighlightSpan.run_count` 文档字符串）。"""
        return sum(h.run_count for h in self.highlights)

    @property
    def has_comments_part(self) -> bool:
        return any(n.startswith(COMMENTS_PART_PREFIX) for n in self.part_names)

    @property
    def has_any_signal(self) -> bool:
        return bool(
            self.checkboxes or self.highlights or self.comments
            or self.tracked_changes or self.loose_checkbox_chars
        )

    def summary_line(self) -> str:
        """拆件班次材料用的一行摘要，口径对齐 README 已验证过的写法
        （`质量部#9` 行原话："w14:checkbox XML 取证 ☒6/☐8 无预勾选"）。
        四类信号均未命中时**不得**默认为"对方什么都没答"——那正是本模块
        要根治的错误结论，只能如实报告"机器没读到形态信号"，转人工判断。
        """
        parts = []
        if self.checkboxes:
            parts.append(
                f"w14:checkbox ☒{self.checkbox_checked_count}/"
                f"☐{self.checkbox_unchecked_count}"
            )
        if self.loose_checkbox_chars:
            parts.append(f"裸勾选字符×{len(self.loose_checkbox_chars)}（控件外，需人工确认）")
        if self.highlights:
            parts.append(
                f"高亮段×{len(self.highlights)}"
                f"（未合并 run 计 {self.highlight_run_count_total} 处）"
            )
        if self.comments:
            parts.append(f"批注×{len(self.comments)}")
        if self.tracked_changes:
            ins = sum(1 for t in self.tracked_changes if t.kind == "ins")
            dele = sum(1 for t in self.tracked_changes if t.kind == "del")
            parts.append(f"修订 w:ins×{ins}/w:del×{dele}")
        if not parts:
            return "四类信号（复选框/高亮/批注/修订）均未命中——不得据此判定「对方未作答」，须人工确认"
        return "；".join(parts)


# ---------------------------------------------------------------- ① 部件清单

def list_part_names(docx_path: Union[str, Path]) -> List[str]:
    """直读 docx 部件清单——不经 python-docx 的 `Document()` 高层封装。

    部件清单本身就是第一手事实：`word/comments*.xml` 存不存在，比"用某个
    库解析出来的对象有没有这个属性"更直接、更不会被库版本差异带偏
    （队列 #446 原文明写的方法＝`zipfile` 直读部件清单）。
    """
    with zipfile.ZipFile(docx_path) as z:
        return z.namelist()


def _read_xml_part(z: zipfile.ZipFile, name: str) -> Optional[ET.Element]:
    try:
        data = z.read(name)
    except KeyError:
        return None
    return ET.fromstring(data)


def _paragraph_text(p: ET.Element) -> str:
    return "".join(t.text or "" for t in p.iter(_w("t")))


def _build_parent_map(root: ET.Element) -> Dict[ET.Element, ET.Element]:
    """ElementTree 节点没有 parent 指针，一次性建反查表供多个探测器共用
    （避免每探测一类信号都重新遍历一次整棵树）。"""
    return {child: parent for parent in root.iter() for child in parent}


def _ancestor(
    elem: ET.Element, tag: str, parent_map: Dict[ET.Element, ET.Element]
) -> Optional[ET.Element]:
    node = elem
    while node is not None:
        if node.tag == tag:
            return node
        node = parent_map.get(node)
    return None


def _ancestor_paragraph(elem: ET.Element, parent_map: Dict[ET.Element, ET.Element]) -> Optional[ET.Element]:
    return _ancestor(elem, _w("p"), parent_map)


def _row_context(elem: ET.Element, parent_map: Dict[ET.Element, ET.Element]) -> str:
    """控件若位于表格内，取同一行（`w:tr`）里**其余**单元格的文字拼接；
    不在表格内（或找不到 `w:tr` 祖先）时返回空串。**按单元格元素身份排除
    自己那一格**，不按文字内容比对——多个格子巧合同文字（如另一列也是
    "☒"）不该被一并滤掉。"""
    row = _ancestor(elem, _w("tr"), parent_map)
    if row is None:
        return ""
    own_cell = _ancestor(elem, _w("tc"), parent_map)
    cell_texts = []
    for tc in row.findall(_w("tc")):
        if tc is own_cell:
            continue
        text = "".join(t.text or "" for t in tc.iter(_w("t")))
        cell_texts.append(text)
    return " ｜ ".join(cell_texts)


# ---------------------------------------------------------------- ② 复选框

def detect_checkboxes(
    root: ET.Element, parent_map: Dict[ET.Element, ET.Element]
) -> List[CheckboxItem]:
    """逐格 ☒☐：找出全部 `w14:checkbox` 内容控件，报告勾了几个哪几个。

    判据与 `md转Word工具/md2word.py::read_checkboxes()` 同源（同一份
    `w14:checked/@w14:val` 语义），差别只是本函数走纯 `zipfile`+
    `ElementTree`，不依赖 `python-docx`（本服务门禁①刻意保持依赖清单
    极简，见 pyproject.toml 注释）。
    """
    items: List[CheckboxItem] = []
    for sdt in root.iter(_w("sdt")):
        cb = sdt.find(f".//{_w14('checkbox')}")
        if cb is None:
            continue
        checked_el = cb.find(_w14("checked"))
        checked = checked_el is not None and checked_el.get(_w14("val")) == "1"
        p = _ancestor_paragraph(sdt, parent_map)
        context = _paragraph_text(p) if p is not None else ""
        row_context = _row_context(sdt, parent_map)
        items.append(CheckboxItem(checked=checked, context=context, row_context=row_context))
    return items


def _checkbox_text_elements(root: ET.Element) -> set:
    """`w14:checkbox` 控件内部用于显示 ☒/☐ 的那个 `w:t` 元素集合——裸字符
    探测要排除它们，否则每个结构化控件都会被误报成"控件外还有一个裸字符"
    （控件自身的显示字符不是"控件之外"）。"""
    out = set()
    for sdt in root.iter(_w("sdt")):
        if sdt.find(f".//{_w14('checkbox')}") is None:
            continue
        content = sdt.find(_w("sdtContent"))
        if content is None:
            continue
        for t in content.iter(_w("t")):
            out.add(t)
    return out


def detect_loose_checkbox_chars(
    root: ET.Element, parent_map: Dict[ET.Element, ET.Element]
) -> List[LooseCheckboxChar]:
    """结构化控件之外单独出现的 ☐/☑/☒ 字符——見文首"一处刻意的宽松"。"""
    excluded = _checkbox_text_elements(root)
    out: List[LooseCheckboxChar] = []
    for t in root.iter(_w("t")):
        if t in excluded or not t.text:
            continue
        for ch in CHECKBOX_LIKE_CHARS:
            if ch in t.text:
                p = _ancestor_paragraph(t, parent_map)
                context = _paragraph_text(p) if p is not None else (t.text or "")
                out.append(LooseCheckboxChar(char=ch, context=context))
    return out


# ---------------------------------------------------------------- ② 高亮

def detect_highlights(root: ET.Element) -> List[HighlightSpan]:
    """高亮段全文：同段落内连续同色的 `w:highlight` 运行合并成一段
    （`run_count` 保留合并前的原始 run 数，见 `HighlightSpan` 文档字符串
    ——用于跟 README 里按未合并 run 数记的历史口径对账）。"""
    spans: List[HighlightSpan] = []
    for p_idx, p in enumerate(root.iter(_w("p"))):
        current_color: Optional[str] = None
        buffer: List[str] = []
        run_count = 0

        def flush():
            if current_color is not None and buffer:
                spans.append(HighlightSpan(
                    color=current_color,
                    text="".join(buffer),
                    paragraph_index=p_idx,
                    paragraph_text=_paragraph_text(p),
                    run_count=run_count,
                ))

        # `p.iter(...)`（非 `findall`，即递归全部子孙）—— 高亮的 run 不一定
        # 是段落的直接子元素：修订态包裹（`w:ins`/`w:del`）、超链接包裹
        # （`w:hyperlink`）都会把 `w:r` 降一层，`findall` 只看直接子节点会
        # 漏数（财务部#14 实测：直接子节点计 71 处，含超链接/修订包裹后
        # 递归计 78 处，与 README 历史口径逐字对上）。
        for r in p.iter(_w("r")):
            rpr = r.find(_w("rPr"))
            hl = rpr.find(_w("highlight")) if rpr is not None else None
            color = hl.get(_w("val")) if hl is not None else None
            run_text = "".join(t.text or "" for t in r.findall(_w("t")))
            for tab in r.findall(_w("tab")):
                run_text += "\t"
            for br in r.findall(_w("br")):
                run_text += "\n"
            if color:
                if color != current_color:
                    flush()
                    current_color = color
                    buffer = [run_text]
                    run_count = 1
                else:
                    buffer.append(run_text)
                    run_count += 1
            else:
                flush()
                current_color = None
                buffer = []
                run_count = 0
        flush()
    return spans


# ---------------------------------------------------------------- ② 批注

def detect_comments(
    z: zipfile.ZipFile, document_root: ET.Element
) -> List[CommentItem]:
    """批注内容 ＋ 圈住的原文（`commentRangeStart`/`commentRangeEnd` 之间
    的文字）。`word/comments.xml` 缺失（无批注）时返回空列表，不报错——
    "没有批注"本身就是一条合法的形态识别结果。"""
    comments_root = _read_xml_part(z, "word/comments.xml")
    if comments_root is None:
        return []

    meta: Dict[str, Dict[str, str]] = {}
    for c in comments_root.findall(_w("comment")):
        cid = c.get(_w("id")) or ""
        text = "\n".join(_paragraph_text(p) for p in c.findall(_w("p")))
        meta[cid] = {
            "author": c.get(_w("author")) or "",
            "date": c.get(_w("date")) or "",
            "text": text,
        }

    anchors: Dict[str, List[str]] = {cid: [] for cid in meta}
    active: set = set()
    for elem in document_root.iter():
        if elem.tag == _w("commentRangeStart"):
            cid = elem.get(_w("id")) or ""
            if cid in anchors:
                active.add(cid)
        elif elem.tag == _w("commentRangeEnd"):
            cid = elem.get(_w("id")) or ""
            active.discard(cid)
        elif elem.tag == _w("t") and active:
            for cid in active:
                anchors[cid].append(elem.text or "")

    return [
        CommentItem(
            comment_id=cid,
            author=data["author"],
            date=data["date"],
            text=data["text"],
            anchor_text="".join(anchors.get(cid, [])),
        )
        for cid, data in meta.items()
    ]


# ---------------------------------------------------------------- ② 修订标记

def detect_tracked_changes(root: ET.Element) -> List[TrackedChange]:
    """`w:ins`（插入）／`w:del`（删除）——插入的文字仍在 `w:t`，删除的文字
    改落在 `w:delText`，两者取字段不同，不能共用同一段落取文字逻辑。"""
    out: List[TrackedChange] = []
    for ins in root.iter(_w("ins")):
        text = "".join(t.text or "" for t in ins.iter(_w("t")))
        out.append(TrackedChange(
            kind="ins", author=ins.get(_w("author")) or "",
            date=ins.get(_w("date")) or "", text=text,
        ))
    for delete in root.iter(_w("del")):
        text = "".join(t.text or "" for t in delete.iter(_w("delText")))
        out.append(TrackedChange(
            kind="del", author=delete.get(_w("author")) or "",
            date=delete.get(_w("date")) or "", text=text,
        ))
    return out


# ---------------------------------------------------------------- ③ 一次性总入口

def analyze_docx(docx_path: Union[str, Path]) -> FormSignals:
    """①②③ 一次性识别四类信号 ＋ 结构化提取原文片段。

    不做语义判断（见模块文首边界）；某一类信号缺失是合法结果，不代表
    "分析失败"——只有 docx 本身读不了（非法 zip / 缺 `word/document.xml`）
    才会向上抛异常，异常处理留给调用方（拆件班次遇到损坏文件时应如实
    记"读不了"，不应静默当成"零信号＝对方未答"）。
    """
    docx_path = Path(docx_path)
    with zipfile.ZipFile(docx_path) as z:
        part_names = z.namelist()
        document_root = _read_xml_part(z, DOCUMENT_PART)
        if document_root is None:
            raise ValueError(f"docx 缺 {DOCUMENT_PART}，非合法 Word 文档：{docx_path}")
        parent_map = _build_parent_map(document_root)
        return FormSignals(
            docx_path=str(docx_path),
            part_names=part_names,
            checkboxes=detect_checkboxes(document_root, parent_map),
            loose_checkbox_chars=detect_loose_checkbox_chars(document_root, parent_map),
            highlights=detect_highlights(document_root),
            comments=detect_comments(z, document_root),
            tracked_changes=detect_tracked_changes(document_root),
        )
