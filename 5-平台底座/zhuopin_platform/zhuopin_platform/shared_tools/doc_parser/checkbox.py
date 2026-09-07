"""docx 勾选读取 —— 全项目**唯一**的勾选判据正本（队列 `#481`）。

## 这个件在治什么（`#133` ⑴ 的事实链，一句话）
`采购部#18` 的回件里，姚祖怡在 9 个复选框中勾了 3 个；用 python-docx 的
`cell.text` 去读那张表，24 格里有 9 格返回**空字符串**——一格不多一格不少，
正是那 9 个复选框格。而 `""` 是 python-docx 的**合法返回值、不是异常**，于是
「读不到」和「一条都没勾」**逐字节相同**，任何 `if not cell.text:` 都必然给出
同一个答案。⇒ 这条不可能靠"判得更严"防住，只能靠**让这两种情况不再是同一个
值**（design 决策点③ (c)）。

## 三态，各有其表示，且不可用 falsy 混同
`ReadingStatus.READ_FAILED`（读不了）／`NO_CARRIER`（读得动、但没有任何勾选
载体）／`HAS_CARRIERS`（有 N 个载体、勾了 M 个）。`CheckboxReading.__bool__`
**直接抛 TypeError** —— `if not reading:` 这行代码在本件上写不出来，这是三态
区分的结构性保证，不依赖任何人记得判据。

## 两类载体分列不合并（design 决策点② (b)）
- `source="control"` ＝ `w14:checkbox` 内容控件，`checked` 读自
  `w14:checked/@w14:val == "1"`，**机器可判**；
- `source="char"` ＝ 控件之外正文里的裸 ☑/☒/☐ 字符。**决策点② 拍板给语义**：
  ☑/☒ ＝ checked、☐ ＝ unchecked。

  🔴 **这是对 `#446` 口径的一次有依据的改判，不是随手放宽。** `#446` 当时定
  「裸字符不给 checked 语义」，而 `#481` 期望产出 ① 明写要覆盖"段落内勾"，
  两者正面相撞。改判依据 ＝ 2026-09-07 现网逐段上下文实测：`质量部#11` 22 个
  裸 ☑ 每个后面都紧跟真实作答文字（「☑ 认可」「☑ 按 V3.2（扣分＋红线）」），
  `质量部#12` 7 个同形态，`采购部` 07-28 回件 8 个裸 ☐ 各自独占一段 ＝ 未填的
  作答格——三例全部支持给语义，图例/装饰形态（如正文印一行「☒＝不适用」）
  **一例都没找到**，该反例目前是理论风险，如实标注在此。
  代价对称性见 `design.md` 决策点②：给语义的错（说人家勾了没勾的）对方会当场
  反驳、一轮纠正；不给语义的错（说人家没答）**看不见**，已实证会变成对专员的
  不实指摘。
  ⚠️ 两类载体**分开报、不合并成一个总数**（`control_carriers` /
  `char_carriers` 分列），需要更谨慎时调用方可只采信控件那一列。

## 覆盖面（design 决策点④ (b)）
`word/document.xml` ＋ `word/header*.xml`／`footer*.xml`／`footnotes.xml`／
`endnotes.xml`。表格格内勾与文本框（`w:txbxContent`）本就落在这些部件内，
递归遍历天然覆盖。

**未覆盖**：Word 97-2003 旧式表单域（`w:fldChar`／`w:checkBox`）；非标准命名
的正文部件（如 `word/document2.xml`）。语料范围 ＝ `7-外部文档/` 69 份 docx，
实测日期 2026-09-07。

## 边界
本件不做语义判断，不输出"对方同意/反对"这类结论字段；不缓存任何被解析内容；
被涉 OEM 技术数据的场景调用时，OEM 隔离责任在调用方。
本件**不**保证"此后不会再误判对方是否作答"——它只保证**凡经本件读取的**，
读不到会说读不到；"读这一步有没有被执行"不在本件覆盖范围。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union
from xml.etree import ElementTree as ET

from . import _xml
from ._xml import DocxReadError, w, w14

CHECKBOX_LIKE_CHARS = ("☐", "☑", "☒")
CHECKED_CHARS = ("☑", "☒")

SOURCE_CONTROL = "control"
SOURCE_CHAR = "char"


class ReadingStatus(str, Enum):
    """三态。字符串枚举，便于落审计/日志时不丢语义。"""

    READ_FAILED = "read_failed"
    NO_CARRIER = "no_carrier"
    HAS_CARRIERS = "has_carriers"


@dataclass(frozen=True)
class CheckboxCarrier:
    """一个勾选载体 —— 控件或裸字符，二者同构，用 `source` 区分。"""

    checked: bool
    source: str  # SOURCE_CONTROL | SOURCE_CHAR
    char: str  # 载体显示/承载的字符（控件为其 sdtContent 内的显示字符）
    context: str = ""  # 所在段落/单元格完整文字（XML 视图，含控件内字符）
    row_context: str = ""  # 位于表格内时，同一行其余单元格拼接的文字
    part: str = _xml.DOCUMENT_PART  # 载体所在部件名
    # 这个载体在**高层文本视图**（python-docx 的 Paragraph.text／Cell.text）
    # 下看不看得见。控件载体恒为 False（其 run 挂在 `w:sdtContent` 下，不是
    # `w:p` 的直接 `w:r` 子节点）——这正是 `#133` ⑴ 那 9 个空串格的成因。
    visible_in_text_view: bool = True

    @property
    def is_control(self) -> bool:
        return self.source == SOURCE_CONTROL


@dataclass(frozen=True)
class TextViewDiagnostic:
    """高层文本视图漏读诊断（design 决策点③ (b)）。

    🔴 **它是返回结果的一部分，不是日志**——本项目已有实证教训（`#416`：
    答案 60 毫秒就到了、只是打在没人看的 WARN 里）。
    """

    part: str
    xml_view_count: int  # XML 视图看得见的勾选载体数
    text_view_count: int  # 同一批载体里，高层文本视图看得见的个数

    @property
    def missing_count(self) -> int:
        return self.xml_view_count - self.text_view_count

    def message(self) -> str:
        return (
            f"{self.part}：高层文本视图（python-docx 的 Paragraph.text／Cell.text）"
            f"只看得见 {self.text_view_count} 个勾选载体，XML 里实有 {self.xml_view_count} 个"
            f"——用高层库直接读这份文件会漏 {self.missing_count} 个"
        )


@dataclass(frozen=True)
class CheckboxReading:
    """勾选读取结果（三态）。

    🔴 **禁用 falsy 判断**：`__bool__` 抛 TypeError。这不是洁癖——
    `if not result:` 把「读取失败」「没有载体」「有载体但一个没勾」三件事
    读成同一个答案，正是 `#133` ⑴ 那条事故的形状。
    """

    docx_path: str
    status: ReadingStatus
    control_carriers: Tuple[CheckboxCarrier, ...] = ()
    char_carriers: Tuple[CheckboxCarrier, ...] = ()
    diagnostics: Tuple[TextViewDiagnostic, ...] = ()
    part_names: Tuple[str, ...] = ()
    parts_scanned: Tuple[str, ...] = ()
    failure_reason: str = ""

    # -------------------------------------------------- 禁用 falsy
    def __bool__(self) -> bool:
        raise TypeError(
            "CheckboxReading 刻意不可作真假判断：「读取失败」「无勾选载体」"
            "「有载体但零勾」是三件不同的事，用 falsy 判断会把它们读成同一个答案"
            "（队列 #133 ⑴ 的事故形状）。请显式判 `reading.status`，"
            "或用 `reading.is_failure` / `reading.has_carriers`。"
        )

    # -------------------------------------------------- 状态
    @property
    def is_failure(self) -> bool:
        return self.status is ReadingStatus.READ_FAILED

    @property
    def has_carriers(self) -> bool:
        return self.status is ReadingStatus.HAS_CARRIERS

    def raise_for_failure(self) -> "CheckboxReading":
        """读取失败即抛，供"读不了就该炸"的调用方一行接上。"""
        if self.is_failure:
            raise DocxReadError(self.failure_reason)
        return self

    # -------------------------------------------------- 计数（分列，不合并）
    @property
    def carriers(self) -> Tuple[CheckboxCarrier, ...]:
        """两列载体按"控件在前"拼出的只读全量视图，供遍历用；
        计数请用下面的分列属性，别在这里 len() 出一个混合总数当结论。"""
        return self.control_carriers + self.char_carriers

    @property
    def control_total(self) -> int:
        return len(self.control_carriers)

    @property
    def control_checked_count(self) -> int:
        return sum(1 for c in self.control_carriers if c.checked)

    @property
    def control_unchecked_count(self) -> int:
        return self.control_total - self.control_checked_count

    @property
    def char_total(self) -> int:
        return len(self.char_carriers)

    @property
    def char_checked_count(self) -> int:
        return sum(1 for c in self.char_carriers if c.checked)

    @property
    def char_unchecked_count(self) -> int:
        return self.char_total - self.char_checked_count

    @property
    def carrier_total(self) -> int:
        return self.control_total + self.char_total

    @property
    def checked_total(self) -> int:
        return self.control_checked_count + self.char_checked_count

    def describe(self) -> str:
        """一行人读摘要 —— 三态各自说人话，不把前两态说成"零勾"。"""
        if self.is_failure:
            return f"读取失败：{self.failure_reason}"
        if not self.has_carriers:
            return "读取正常，但这份 docx 里没有任何勾选载体（≠「对方一条都没勾」）"
        bits = []
        if self.control_total:
            bits.append(
                f"控件 {self.control_total} 个（勾 {self.control_checked_count}）"
            )
        if self.char_total:
            bits.append(
                f"裸字符 {self.char_total} 个（勾 {self.char_checked_count}）"
            )
        line = "；".join(bits)
        if self.diagnostics:
            line += f"；⚠️ 高层文本视图漏读诊断 {len(self.diagnostics)} 条"
        return line


# ---------------------------------------------------------------- 探测器

def _control_display_text_elements(root: ET.Element) -> set:
    """`w14:checkbox` 控件内部用于显示 ☒/☐ 的那些 `w:t` 元素。

    裸字符探测要排除它们，否则每个结构化控件都会被误报成"控件外还有一个
    裸字符"——控件自身的显示字符不属于"控件之外"（判据沿用 `#446`）。
    """
    out = set()
    for sdt in root.iter(w("sdt")):
        if sdt.find(f".//{w14('checkbox')}") is None:
            continue
        content = sdt.find(w("sdtContent"))
        if content is None:
            continue
        for t in content.iter(w("t")):
            out.add(t)
    return out


def _visible_in_text_view(
    t: ET.Element, parent_map: Dict[ET.Element, ET.Element]
) -> bool:
    """这个 `w:t` 在 python-docx 的 `Paragraph.text` 下看不看得见。

    判据 ＝ 祖先链恰为 `w:t` → `w:r` → `w:p`（两级都必须是**直接**父子）。
    这正是 python-docx 的取文范围：`Paragraph.runs` ＝ `w:p` 的直接 `w:r`
    子节点，`Run.text` ＝ 该 run 的直接 `w:t`/`w:tab`/`w:br` 子节点。
    包在 `w:sdtContent`／`w:hyperlink`／`w:ins` 里的 run 因此都看不见。
    """
    r = parent_map.get(t)
    if r is None or r.tag != w("r"):
        return False
    p = parent_map.get(r)
    return p is not None and p.tag == w("p")


def detect_control_carriers(
    root: ET.Element,
    parent_map: Dict[ET.Element, ET.Element],
    part: str = _xml.DOCUMENT_PART,
) -> List[CheckboxCarrier]:
    """`w14:checkbox` 内容控件 —— 判据 ＝ `w14:checked/@w14:val == "1"`，
    **不是**高层库返回的单元格/段落文本。"""
    items: List[CheckboxCarrier] = []
    for sdt in root.iter(w("sdt")):
        cb = sdt.find(f".//{w14('checkbox')}")
        if cb is None:
            continue
        checked_el = cb.find(w14("checked"))
        checked = checked_el is not None and checked_el.get(w14("val")) == "1"
        p = _xml.ancestor_paragraph(sdt, parent_map)
        context = _xml.full_paragraph_text(p) if p is not None else ""
        content = sdt.find(w("sdtContent"))
        display_ts = list(content.iter(w("t"))) if content is not None else []
        char = "".join(t.text or "" for t in display_ts)
        items.append(CheckboxCarrier(
            checked=checked,
            source=SOURCE_CONTROL,
            char=char.strip(),
            context=context,
            row_context=_xml.row_context(sdt, parent_map),
            part=part,
            visible_in_text_view=any(
                _visible_in_text_view(t, parent_map) for t in display_ts
            ),
        ))
    return items


def detect_char_carriers(
    root: ET.Element,
    parent_map: Dict[ET.Element, ET.Element],
    part: str = _xml.DOCUMENT_PART,
) -> List[CheckboxCarrier]:
    """控件之外单独出现的 ☐/☑/☒ 字符 —— 决策点② (b)：给 `checked` 语义，
    标 `source="char"`，与控件分列不合并。"""
    excluded = _control_display_text_elements(root)
    out: List[CheckboxCarrier] = []
    for t in root.iter(w("t")):
        if t in excluded or not t.text:
            continue
        for ch in CHECKBOX_LIKE_CHARS:
            if ch in t.text:
                p = _xml.ancestor_paragraph(t, parent_map)
                context = _xml.full_paragraph_text(p) if p is not None else (t.text or "")
                out.append(CheckboxCarrier(
                    checked=ch in CHECKED_CHARS,
                    source=SOURCE_CHAR,
                    char=ch,
                    context=context,
                    row_context=_xml.row_context(t, parent_map),
                    part=part,
                    visible_in_text_view=_visible_in_text_view(t, parent_map),
                ))
    return out


# ---------------------------------------------------------------- 总入口

def read_checkboxes(
    docx_path: Union[str, Path], include_extra_parts: bool = True
) -> CheckboxReading:
    """**单一入口**：一次调用覆盖勾选控件／段落内勾／表格格内勾三种形态。

    调用方**不需要**事先知道"这份回件用的是哪种形态"——预设形态正是本件要
    根治的失效模式本身。

    读不了时返回 `status=READ_FAILED` 的结果（不抛异常），失败原因与文件
    路径写在 `failure_reason`；要"读不了就炸"请接 `.raise_for_failure()`。
    """
    docx_path = Path(docx_path)
    try:
        part_names, roots = _xml.read_parts(docx_path, include_extra_parts=include_extra_parts)
    except DocxReadError as exc:
        return CheckboxReading(
            docx_path=str(docx_path),
            status=ReadingStatus.READ_FAILED,
            failure_reason=str(exc),
        )
    except OSError as exc:
        return CheckboxReading(
            docx_path=str(docx_path),
            status=ReadingStatus.READ_FAILED,
            failure_reason=f"文件读不了（{exc}）：{docx_path}",
        )

    controls: List[CheckboxCarrier] = []
    chars: List[CheckboxCarrier] = []
    diagnostics: List[TextViewDiagnostic] = []
    for part, root in roots:
        parent_map = _xml.build_parent_map(root)
        part_controls = detect_control_carriers(root, parent_map, part=part)
        part_chars = detect_char_carriers(root, parent_map, part=part)
        controls.extend(part_controls)
        chars.extend(part_chars)
        part_carriers = part_controls + part_chars
        xml_view = len(part_carriers)
        text_view = sum(1 for c in part_carriers if c.visible_in_text_view)
        if xml_view != text_view:
            diagnostics.append(TextViewDiagnostic(
                part=part, xml_view_count=xml_view, text_view_count=text_view,
            ))

    status = (
        ReadingStatus.HAS_CARRIERS if (controls or chars) else ReadingStatus.NO_CARRIER
    )
    return CheckboxReading(
        docx_path=str(docx_path),
        status=status,
        control_carriers=tuple(controls),
        char_carriers=tuple(chars),
        diagnostics=tuple(diagnostics),
        part_names=tuple(part_names),
        parts_scanned=tuple(name for name, _ in roots),
    )
