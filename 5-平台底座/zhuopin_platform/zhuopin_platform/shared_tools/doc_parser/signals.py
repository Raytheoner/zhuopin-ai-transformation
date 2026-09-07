"""回件形态识别 —— 四类信号一次探测（判据自队列 `#446` 原样迁入，语义未改）。

## 本模块的位置（队列 `#481`）
判据原先住在 `5-平台底座/wecom-aibot-service/aibot_service/reply_form_detection.py`
——那是**企微机器人服务包**，`4-数字员工/` 各场景 import 不到它。场景要读
docx，除了自己写一份别无选择，这才是三份重复实现长期并存的**结构性成因**。
`#481` design 决策点① (a) 拍板：判据迁到平台底座 `shared_tools/doc_parser/`，
即场景侧 import 的唯一正门。原模块改为薄壳委托，对外 API 与输出逐字不变。

## 缺陷成因（队列 #446 原文实测，只留本模块要治的那一句）
读回件形态这一步人已至少错 4 次，每次都把"对方其实答了"读成"对方什么都没答"：
唐燕萍用高亮段作答被当成空、姚祖怡 9 格实际勾了 3 个被读成全空、段落里的勾选
被漏读。🔴 **经交叉核实曾更正过一处队列 #446 原文的误引**——原文把"高亮段作答"
那两封（`财务部#14`／`#15`）写成了"陈忱 质量部 #9／#10"；`README-跟进机制与命名
约定.md` L133 原话是"她 `财务部#14`／`#15` 连续两封都没勾控件、而是在正文插
高亮段作答"，指的是唐燕萍，与 `质量部#9`（陈忱）经实测＝14 个复选框、零高亮，
形态正好相反。根因不是工具缺失——根因是**读形态这一步在拆件流程里压根没有必然
会被执行的位置**，全凭人凭习惯扫一眼。本模块把"扫一眼"换成"每次都跑全部四类
信号探测"，堵的是这一个漏洞。

## 四类信号，一次性探测，不做取舍、不猜"这封信应该是哪种形态"
`w14:checkbox`（真复选框内容控件）／`w:ins`·`w:del`（修订标记）／
`word/comments*`（批注部件）／`w:highlight`（高亮）——四类互不排斥，现实中的
回件常混用：`采购部#19` 同一份 docx 里复选框与高亮同时出现；`质量部#9` 用了
14 个复选框（☒6/☐8）、零高亮零批注零修订；`财务部#14`／`#15` 反过来只用高亮
——README 记的"55~78 处"是对 `<w:highlight` 做裸字符串计数的结果，本模块实测
这两个数字里各混了 4／7 个不含任何文字、纯属"段落标记"的高亮残留，按实际承载
文字的 run 数数分别是 51／71（见 `HighlightSpan.run_count`，两个口径都保留）。

## 裸勾选字符的语义：`#481` 决策点② 已改判
`#446` 当时定「裸字符不给 checked 语义」。`#481` design 决策点② 经现网逐段
上下文实测后由 Shao Peishen 拍板改判为 **(b) 给语义**，判据与依据写在
`checkbox.py` 模块文档。**本模块对外的 `LooseCheckboxChar` 与 `summary_line()`
措辞保持不变**（拆件班次看到的东西不因这次重构改变）；新增的 `checked` 字段
是附加信息，要用机器可判的勾选语义请走 `checkbox.read_checkboxes()`。

## 只做识别与结构化提取，不做语义判断（队列 #446 明写的边界）
本模块输出止于"这份 docx 里有什么、原文写了什么"，不产生任何"建议"或"结论"
字段——语义判断仍须人工，防止本模块的输出被误当成可以直接回灌权威载体的判定。
"""
from __future__ import annotations

import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Union
from xml.etree import ElementTree as ET

from . import _xml
from ._xml import COMMENTS_PART_PREFIX, DOCUMENT_PART, DocxReadError, w
from .checkbox import (
    CHECKBOX_LIKE_CHARS,
    CHECKED_CHARS,
    CheckboxReading,
    detect_char_carriers,
    detect_control_carriers,
    read_checkboxes,
)


# ---------------------------------------------------------------- 数据结构

@dataclass
class CheckboxItem:
    """一个 `w14:checkbox` 内容控件。

    `context` 只是控件自身所在段落/单元格的文字——真实回件里控件常常独占一个
    表格单元格（判例批改表的常见排版：一列放选项文字、隔壁一列放对应的 ☒/☐
    控件），此时 `context` 会只剩一个孤零零的 ☒/☐，看不出"勾的是哪一项"。
    `row_context` 补这一环：控件若位于表格内，给出**同一行**其余单元格拼接的
    文字——这正是队列 #446 point ⑶「9 格实际勾了 3 个被读成全空」的根因所在的
    那类排版，不带行上下文就等于没解决那个真实事故。
    """
    checked: bool
    context: str  # 所在段落/单元格完整文字（含控件自身显示的 ☒/☐ 字符）
    row_context: str = ""  # 控件若在表格内，同一行其余单元格拼接的文字；不在表格内则为空串


@dataclass
class LooseCheckboxChar:
    """不在任何 `w14:checkbox` 控件里、单独出现的 ☐/☑/☒ 字符。

    `#446` 建造期只报字符与上下文、不给勾选语义；`#481` 决策点② 拍板给语义后，
    这里附上 `checked` 供需要的调用方读，**但本类的既有字段与用它的
    `summary_line()` 措辞一字未改**——拆件 CLI 的输出因此逐字不变。
    """
    char: str
    context: str
    checked: bool = False  # `#481` 决策点② (b)：☑/☒ ＝ True，☐ ＝ False


@dataclass
class HighlightSpan:
    """一段连续同色高亮的原文全文（跨多个 `w:r` 已按颜色合并）。

    `run_count` 记这一段合并前原本是几个 `w:r`——**不是为了展示**，是为了跟
    README 里已经写死的历史口径对账：`财务部#14`/`#15` 的"55~78 处高亮"来自对
    `<w:highlight` 做裸字符串计数（78／55）。实测两份文件各自的 78／55 里都混了
    7／4 个不含任何可读文字的"段落标记"高亮（`w:pPr/w:rPr/w:highlight`——Word
    给整段连同其结尾的隐藏换行符一起高亮时的副产物，本身没有 `w:t` 可读）；本
    模块只对承载实际文字的 run 计数，得到的是 71／51。差额不是缺陷，是历史数字
    本身把「有内容的高亮」和「段落标记的格式残留」混在一起数了。两个数字统计
    口径不同、都如实保留，不用一个去覆盖另一个。
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
    # `#481`：同一次解析顺带带出的三态勾选读数。旧字段一个没动，本字段是**附加**
    # ——需要「读取失败 / 无载体 / 有 N 勾 M」三态区分的调用方读它，不必再解析一遍。
    checkbox_reading: Optional[CheckboxReading] = None

    @property
    def checkbox_checked_count(self) -> int:
        return sum(1 for c in self.checkboxes if c.checked)

    @property
    def checkbox_unchecked_count(self) -> int:
        return sum(1 for c in self.checkboxes if not c.checked)

    @property
    def highlight_run_count_total(self) -> int:
        """未合并的原始高亮 run 总数——对得上 README 里"55~78 处高亮"这类历史
        口径的统计粒度（`highlights` 列表长度是合并后的段数，两者刻意不是同一个
        数字，见 `HighlightSpan.run_count`）。"""
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
        四类信号均未命中时**不得**默认为"对方什么都没答"——那正是本模块要根治
        的错误结论，只能如实报告"机器没读到形态信号"，转人工判断。
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

    部件清单本身就是第一手事实：`word/comments*.xml` 存不存在，比"用某个库
    解析出来的对象有没有这个属性"更直接、更不会被库版本差异带偏（队列 #446
    原文明写的方法＝`zipfile` 直读部件清单）。
    """
    with _xml.open_zip(docx_path) as z:
        return z.namelist()


# ---------------------------------------------------------------- ② 复选框

def detect_checkboxes(
    root: ET.Element, parent_map: Dict[ET.Element, ET.Element]
) -> List[CheckboxItem]:
    """逐格 ☒☐：找出全部 `w14:checkbox` 内容控件，报告勾了几个哪几个。

    判据正本在 `checkbox.detect_control_carriers()`——本函数只把载体换成本模块
    的展示型 `CheckboxItem`，**不含第二份判据**（`#481` 期望产出 ③）。
    """
    return [
        CheckboxItem(checked=c.checked, context=c.context, row_context=c.row_context)
        for c in detect_control_carriers(root, parent_map)
    ]


def detect_loose_checkbox_chars(
    root: ET.Element, parent_map: Dict[ET.Element, ET.Element]
) -> List[LooseCheckboxChar]:
    """结构化控件之外单独出现的 ☐/☑/☒ 字符。判据正本同样在 `checkbox.py`。"""
    return [
        LooseCheckboxChar(char=c.char, context=c.context, checked=c.checked)
        for c in detect_char_carriers(root, parent_map)
    ]


# ---------------------------------------------------------------- ② 高亮

def detect_highlights(root: ET.Element) -> List[HighlightSpan]:
    """高亮段全文：同段落内连续同色的 `w:highlight` 运行合并成一段
    （`run_count` 保留合并前的原始 run 数，用于跟 README 按未合并 run 数记的
    历史口径对账）。"""
    spans: List[HighlightSpan] = []
    for p_idx, p in enumerate(root.iter(w("p"))):
        current_color: Optional[str] = None
        buffer: List[str] = []
        run_count = 0

        def flush():
            if current_color is not None and buffer:
                spans.append(HighlightSpan(
                    color=current_color,
                    text="".join(buffer),
                    paragraph_index=p_idx,
                    paragraph_text=_xml.full_paragraph_text(p),
                    run_count=run_count,
                ))

        # `p.iter(...)`（非 `findall`，即递归全部子孙）—— 高亮的 run 不一定是
        # 段落的直接子元素：修订态包裹（`w:ins`/`w:del`）、超链接包裹
        # （`w:hyperlink`）都会把 `w:r` 降一层，`findall` 只看直接子节点会漏数
        # （财务部#14 实测：直接子节点计 71 处，含超链接/修订包裹后递归计 78 处，
        # 与 README 历史口径逐字对上）。
        for r in p.iter(w("r")):
            rpr = r.find(w("rPr"))
            hl = rpr.find(w("highlight")) if rpr is not None else None
            color = hl.get(w("val")) if hl is not None else None
            run_text = "".join(t.text or "" for t in r.findall(w("t")))
            for tab in r.findall(w("tab")):
                run_text += "\t"
            for br in r.findall(w("br")):
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
    """批注内容 ＋ 圈住的原文（`commentRangeStart`/`commentRangeEnd` 之间的
    文字）。`word/comments.xml` 缺失（无批注）时返回空列表，不报错——"没有批注"
    本身就是一条合法的形态识别结果。"""
    comments_root = _xml.parse_optional_part(z, "word/comments.xml")
    if comments_root is None:
        return []

    meta: Dict[str, Dict[str, str]] = {}
    for c in comments_root.findall(w("comment")):
        cid = c.get(w("id")) or ""
        text = "\n".join(_xml.full_paragraph_text(p) for p in c.findall(w("p")))
        meta[cid] = {
            "author": c.get(w("author")) or "",
            "date": c.get(w("date")) or "",
            "text": text,
        }

    anchors: Dict[str, List[str]] = {cid: [] for cid in meta}
    active: set = set()
    for elem in document_root.iter():
        if elem.tag == w("commentRangeStart"):
            cid = elem.get(w("id")) or ""
            if cid in anchors:
                active.add(cid)
        elif elem.tag == w("commentRangeEnd"):
            cid = elem.get(w("id")) or ""
            active.discard(cid)
        elif elem.tag == w("t") and active:
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
    """`w:ins`（插入）／`w:del`（删除）——插入的文字仍在 `w:t`，删除的文字改落
    在 `w:delText`，两者取字段不同，不能共用同一段落取文字逻辑。"""
    out: List[TrackedChange] = []
    for ins in root.iter(w("ins")):
        text = "".join(t.text or "" for t in ins.iter(w("t")))
        out.append(TrackedChange(
            kind="ins", author=ins.get(w("author")) or "",
            date=ins.get(w("date")) or "", text=text,
        ))
    for delete in root.iter(w("del")):
        text = "".join(t.text or "" for t in delete.iter(w("delText")))
        out.append(TrackedChange(
            kind="del", author=delete.get(w("author")) or "",
            date=delete.get(w("date")) or "", text=text,
        ))
    return out


# ---------------------------------------------------------------- ③ 一次性总入口

def analyze_docx(docx_path: Union[str, Path]) -> FormSignals:
    """①②③ 一次性识别四类信号 ＋ 结构化提取原文片段。

    不做语义判断（见模块文首边界）；某一类信号缺失是合法结果，不代表"分析失败"
    ——只有 docx 本身读不了（非法 zip / 缺 `word/document.xml`）才会向上抛
    `DocxReadError`（`ValueError` 子类，既有调用方的 `except (ValueError, OSError)`
    照旧命中），异常处理留给调用方（拆件班次遇到损坏文件时应如实记"读不了"，
    不应静默当成"零信号＝对方未答"）。

    ⚠️ **四类信号的探测范围仍是 `word/document.xml`**，与 `#446` 逐字一致——
    拆件 CLI 的输出因此不因本次重构改变。`#481` 决策点④ 扩到页眉/页脚/脚注/
    尾注的是**勾选读取**那条路（`checkbox_reading` 字段，及
    `checkbox.read_checkboxes()`），2026-09-07 现网 69 份语料实测这些部件里的
    勾选载体命中数 ＝ 0，两条路今天读数完全相同。
    """
    docx_path = Path(docx_path)
    with _xml.open_zip(docx_path) as z:
        part_names = z.namelist()
        document_root = _xml.parse_optional_part(z, DOCUMENT_PART, docx_path)
        if document_root is None:
            raise DocxReadError(f"docx 缺 {DOCUMENT_PART}，非合法 Word 文档：{docx_path}")
        parent_map = _xml.build_parent_map(document_root)
        signals = FormSignals(
            docx_path=str(docx_path),
            part_names=part_names,
            checkboxes=detect_checkboxes(document_root, parent_map),
            loose_checkbox_chars=detect_loose_checkbox_chars(document_root, parent_map),
            highlights=detect_highlights(document_root),
            comments=detect_comments(z, document_root),
            tracked_changes=detect_tracked_changes(document_root),
        )
    signals.checkbox_reading = read_checkboxes(docx_path)
    return signals
