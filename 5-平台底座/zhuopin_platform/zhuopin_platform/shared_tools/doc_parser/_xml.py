"""docx 的 OOXML 直读原语 —— 命名空间、部件读取、父节点反查、两种文本视图。

本文件不含任何业务判据，只提供"怎么从 zip 里的 XML 拿到东西"这一层；
勾选判据在 `checkbox.py`，四类信号在 `signals.py`，取文在 `text.py`。

## 为什么纯 stdlib（`zipfile` ＋ `xml.etree.ElementTree`）
队列 `#481` design 决策点① 实测：`zhuopin_platform` 的依赖清单里没有
python-docx，而 `#446` 的实现本来就是纯 stdlib —— 迁到底座**零新增第三方
依赖**。同时纯 stdlib 也让"高层文本视图"这条诊断（见 `simulated_*`）不随
python-docx 版本漂移。

## 两种文本视图，是本文件存在的要害
- **XML 视图**（`full_paragraph_text`）＝ `p.iter(w:t)`，递归全部子孙，
  内容控件 `w:sdtContent` 里的 run、超链接／修订包裹里的 run 全都看得见；
- **高层文本视图**（`simulated_paragraph_text`）＝ 只拼 `w:p` 的**直接**
  `w:r` 子节点，即 python-docx 的 `Paragraph.text` 所能看见的范围。

两者的差值就是队列 `#133` ⑴ 那条事故的全部内容：勾选控件位于表格单元格
里时，`Cell.text` 返回空串，而 XML 里确有 `w14:checkbox`。**把这个差值算
出来并报出去**，是 `#481` 期望产出 ② 的实现基础。
"""
from __future__ import annotations

import zipfile
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple, Union
from xml.etree import ElementTree as ET

W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
W14_NS = "http://schemas.microsoft.com/office/word/2010/wordml"

DOCUMENT_PART = "word/document.xml"

# 批注部件命名不止一种（`word/comments.xml` 是主体，Word 新版还会伴生
# `word/commentsExtended.xml`／`word/commentsIds.xml`）——判据是「前缀命中」，
# 不必逐个列举当前 Word 版本用了哪几个（判据沿用队列 #446 原文，未改）。
COMMENTS_PART_PREFIX = "word/comments"

# 决策点④ (b)：正文之外还要看的部件。`word/document.xml` 之外的这些部件里，
# 2026-09-07 现网 69 份语料实测 `w14:checkbox` 命中数 ＝ 0 —— 即今天读数与
# 只看正文完全相同；纳进来是把一条未来的漏读路径提前关掉，不是修今天的数。
_EXTRA_PART_PREFIXES = ("word/header", "word/footer")
_EXTRA_PART_NAMES = ("word/footnotes.xml", "word/endnotes.xml")


def w(tag: str) -> str:
    return f"{{{W_NS}}}{tag}"


def w14(tag: str) -> str:
    return f"{{{W14_NS}}}{tag}"


class DocxReadError(ValueError):
    """docx 读不了 —— 非法 zip／缺 `word/document.xml`／部件 XML 解析失败。

    刻意继承 `ValueError`：既有调用方（`scripts/check_reply_form_signals.py`）
    的 `except (ValueError, OSError)` 因此照旧命中，行为不变。
    🔴 本异常**永远不得**被降级成「一条都没勾」——那正是 `#481` 要根治的那个
    失效（`#133` ⑴：空串与"没勾"逐字节相同）。
    """


def read_parts(
    docx_path: Union[str, Path], include_extra_parts: bool = True
) -> Tuple[List[str], List[Tuple[str, ET.Element]]]:
    """一次打开 zip，返回（全部部件名, [(部件名, 已解析根节点), ...]）。

    `word/document.xml` 必在返回列表首位且必须存在——缺它即 `DocxReadError`。
    `include_extra_parts=True` 时按决策点④ 追加页眉／页脚／脚注／尾注。
    """
    docx_path = Path(docx_path)
    try:
        z = zipfile.ZipFile(docx_path)
    except zipfile.BadZipFile as exc:
        raise DocxReadError(f"不是合法的 zip/docx 容器（{exc}）：{docx_path}") from exc
    with z:
        part_names = z.namelist()
        roots: List[Tuple[str, ET.Element]] = []
        document_root = _parse_part(z, DOCUMENT_PART, docx_path)
        if document_root is None:
            raise DocxReadError(f"docx 缺 {DOCUMENT_PART}，非合法 Word 文档：{docx_path}")
        roots.append((DOCUMENT_PART, document_root))
        if include_extra_parts:
            for name in extra_part_names(part_names):
                root = _parse_part(z, name, docx_path)
                if root is not None:
                    roots.append((name, root))
        return part_names, roots


def extra_part_names(part_names: Iterable[str]) -> List[str]:
    """决策点④ 的部件白名单在这份 docx 里实际存在的那些，按名字排序。"""
    out = [
        n for n in part_names
        if n.endswith(".xml")
        and (n.startswith(_EXTRA_PART_PREFIXES) or n in _EXTRA_PART_NAMES)
    ]
    return sorted(out)


def open_zip(docx_path: Union[str, Path]) -> zipfile.ZipFile:
    """给需要自己读别的部件（如 `word/comments.xml`）的调用方用。"""
    try:
        return zipfile.ZipFile(Path(docx_path))
    except zipfile.BadZipFile as exc:
        raise DocxReadError(f"不是合法的 zip/docx 容器（{exc}）：{docx_path}") from exc


def parse_optional_part(
    z: zipfile.ZipFile, name: str, docx_path: Union[str, Path] = ""
) -> Optional[ET.Element]:
    """部件不存在 ⇒ None（合法结果）；存在但 XML 坏 ⇒ `DocxReadError`。"""
    return _parse_part(z, name, docx_path)


def _parse_part(
    z: zipfile.ZipFile, name: str, docx_path: Union[str, Path]
) -> Optional[ET.Element]:
    try:
        data = z.read(name)
    except KeyError:
        return None
    try:
        return ET.fromstring(data)
    except ET.ParseError as exc:
        raise DocxReadError(f"部件 {name} 的 XML 解析失败（{exc}）：{docx_path}") from exc


# ---------------------------------------------------------------- 节点导航

def build_parent_map(root: ET.Element) -> Dict[ET.Element, ET.Element]:
    """ElementTree 节点没有 parent 指针，一次性建反查表供多个探测器共用。"""
    return {child: parent for parent in root.iter() for child in parent}


def ancestor(
    elem: ET.Element, tag: str, parent_map: Dict[ET.Element, ET.Element]
) -> Optional[ET.Element]:
    node = elem
    while node is not None:
        if node.tag == tag:
            return node
        node = parent_map.get(node)
    return None


def ancestor_paragraph(
    elem: ET.Element, parent_map: Dict[ET.Element, ET.Element]
) -> Optional[ET.Element]:
    return ancestor(elem, w("p"), parent_map)


def row_context(elem: ET.Element, parent_map: Dict[ET.Element, ET.Element]) -> str:
    """载体若位于表格内，取同一行（`w:tr`）里**其余**单元格的文字拼接。

    **按单元格元素身份排除自己那一格**，不按文字内容比对——多个格子巧合
    同文字（如另一列也是 "☒"）不该被一并滤掉（判据沿用 `#446`，未改）。
    """
    row = ancestor(elem, w("tr"), parent_map)
    if row is None:
        return ""
    own_cell = ancestor(elem, w("tc"), parent_map)
    cell_texts = []
    for tc in row.findall(w("tc")):
        if tc is own_cell:
            continue
        cell_texts.append("".join(t.text or "" for t in tc.iter(w("t"))))
    return " ｜ ".join(cell_texts)


# ---------------------------------------------------------------- 两种文本视图

def full_paragraph_text(p: ET.Element) -> str:
    """XML 视图：递归全部子孙 `w:t`——控件内、超链接内、修订内的都算。"""
    return "".join(t.text or "" for t in p.iter(w("t")))


def _simulated_run_text(r: ET.Element) -> str:
    """模拟 python-docx `Run.text`：只看该 run 的直接子节点。

    python-docx 的 `Run.text` 依次拼 `w:t` 文本、`w:tab`→'\\t'、
    `w:br`/`w:cr`→'\\n'，且只看 run 的直接子节点。这里逐条对齐。
    """
    parts: List[str] = []
    for child in r:
        if child.tag == w("t"):
            parts.append(child.text or "")
        elif child.tag == w("tab"):
            parts.append("\t")
        elif child.tag in (w("br"), w("cr")):
            parts.append("\n")
    return "".join(parts)


def simulated_paragraph_text(p: ET.Element) -> str:
    """模拟 python-docx `Paragraph.text`：只拼 `w:p` 的**直接** `w:r` 子节点。

    ⚠️ 这是刻意的"少读"——它复现的正是高层库看得见的那一层。内容控件
    （`w:sdt/w:sdtContent`）里的 run 不是 `w:p` 的直接子节点，故在这个视图
    下**看不见**，于是控件独占的表格格在 `Cell.text` 下就是空串。
    """
    return "".join(_simulated_run_text(r) for r in p.findall(w("r")))


def simulated_cell_text(tc: ET.Element) -> str:
    """模拟 python-docx `_Cell.text`：直接 `w:p` 子节点各自 `Paragraph.text`
    以换行拼接（嵌套表格里的段落不计——与 python-docx 一致）。"""
    return "\n".join(simulated_paragraph_text(p) for p in tc.findall(w("p")))


def iter_cells(root: ET.Element) -> Iterable[ET.Element]:
    return root.iter(w("tc"))
