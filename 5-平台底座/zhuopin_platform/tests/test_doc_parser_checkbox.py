# -*- coding: utf-8 -*-
"""统一 docx 勾选读取件单测（队列 `#481`，变更包 `unified-docx-checkbox-reader`）。

夹具分两类，**各有各的不可替代性**：
- **真实 docx**（`md2word` 当场生成，落 `tmp_path`、不落仓库）—— 只有它能同时喂给
  python-docx 与本件，从而实测「高层库在这份文件上确实返回空串」这半边。手写的
  最小 OOXML 片段 python-docx 打不开，做不了这件事。
- **手写 OOXML 片段** —— 覆盖真实语料里今天没有、但机器必须答对的形态
  （页眉里的控件、非法 zip、有载体但零勾）。

🔴 真实回件全部落在 gitignore 的 `7-外部文档/`，**一份都不入库、不进夹具**；
现网 69 份语料的回归在变更包 `tasks.md` 4.5 逐条记数，不放这份单测里。
"""
from __future__ import annotations

import io
import os
import sys
import zipfile
from pathlib import Path

import pytest

from zhuopin_platform.shared_tools.doc_parser import (
    SOURCE_CHAR,
    SOURCE_CONTROL,
    CheckboxReading,
    DocxReadError,
    ReadingStatus,
    read_checkboxes,
)
from zhuopin_platform.shared_tools.doc_parser import checkbox as cb_mod

W = 'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"'
W14 = 'xmlns:w14="http://schemas.microsoft.com/office/word/2010/wordml"'


# ---------------------------------------------------------------- 夹具工具

def _md2word_module():
    """向上找到 `0-学习与工具/md转Word工具/md2word.py` 并 import。

    找不到即 skip（`.51` 扁平部署布局下本就没有那层目录），**不静默跳过断言**
    ——skip 会在测试输出里明说，与"测过了"长得不一样。
    """
    here = Path(__file__).resolve()
    for parent in here.parents:
        cand = parent / "0-学习与工具" / "md转Word工具"
        if (cand / "md2word.py").is_file():
            sys.path.insert(0, str(cand))
            import md2word  # type: ignore

            return md2word
    pytest.skip("找不到 0-学习与工具/md转Word工具/md2word.py（扁平部署布局），跳过真实 docx 夹具")


@pytest.fixture
def real_docx_with_cell_checkboxes(tmp_path) -> Path:
    """md2word 当场生成的**真** docx：判例批改表形态，勾选控件都在表格格内。

    沿用 `test_md2word.py::_build` 的做法（写 md → `mw.build`），产物落 tmp_path。
    """
    mw = _md2word_module()
    md = (
        "| # | 真实场景 | 现状判定 | 拟改判定 | ✅对 | ❌错 | ✏️改判理由 |\n"
        "|---|---|---|---|---|---|---|\n"
        "| 1 | 料号A提前期7天 | 齐套 | 齐套 | ☐ | ☐ | |\n"
        "| 2 | 料号B提前期3天 | 缺料 | 齐套 | ☐ | ☑ | 口径应按在途量计 |\n"
    )
    md_path = tmp_path / "case.md"
    md_path.write_text(md, encoding="utf-8")
    out = tmp_path / "case.docx"
    mw.build(str(md_path), str(out), title="测试")
    return out


def _wrap_document(body_xml: str) -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f"<w:document {W} {W14}><w:body>{body_xml}</w:body></w:document>"
    )


def _checkbox_sdt(checked: bool, display_char: str = None) -> str:
    val = "1" if checked else "0"
    char = display_char or ("☒" if checked else "☐")
    return (
        "<w:sdt><w:sdtPr>"
        '<w:id w:val="100000001"/>'
        f'<w14:checkbox><w14:checked w14:val="{val}"/>'
        '<w14:checkedState w14:val="2612" w14:font="MS Gothic"/>'
        '<w14:uncheckedState w14:val="2610" w14:font="MS Gothic"/>'
        "</w14:checkbox>"
        "</w:sdtPr><w:sdtEndPr/>"
        f"<w:sdtContent><w:r><w:t>{char}</w:t></w:r></w:sdtContent>"
        "</w:sdt>"
    )


def _write_docx(tmp_path, name: str, body_xml: str, extra_parts: dict = None) -> Path:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("word/document.xml", _wrap_document(body_xml))
        for part_name, content in (extra_parts or {}).items():
            z.writestr(part_name, content)
    path = tmp_path / name
    path.write_bytes(buf.getvalue())
    return path


# ================================================================ 4.1 反例单测

class TestPythonDocxEmptyStringPathIsNotZeroChecked:
    """`#481` 期望产出 ②：`python-docx` 恒空串那条路径必须被判为「读得到 N 个
    载体」，**不得**被读成「一条都没勾」。"""

    def test_high_level_cell_text_really_returns_empty_string(
        self, real_docx_with_cell_checkboxes
    ):
        """先钉死前提：这不是构造的假设，高层库在这份真 docx 上**确实**返回空串。

        🔑 这份夹具还顺带钉住了 `#133` ⑴ 的要害：21 格里有 **5 个空串**，其中
        **4 个是勾选控件格**（格里明明有 ☐/☑）、**1 个是第 1 行真的没填的
        「改判理由」格**——两类在 `cell.text` 上**逐字节相同**。任何
        `if not cell.text:` 都分不出"读不到"和"真的没填"，这不可能靠判得更严
        防住，只能靠让这两种情况不再是同一个值（design 决策点③ (c)）。
        """
        docx = pytest.importorskip("docx")
        doc = docx.Document(str(real_docx_with_cell_checkboxes))
        table = doc.tables[0]
        cells = [c.text for row in table.rows for c in row.cells]
        assert cells.count("") == 5, f"高层视图空串格数变了：{cells!r}"
        # 4 个控件格 + 1 个真空格，高层视图给出的值一模一样
        checkbox_cells = [table.rows[1].cells[4].text, table.rows[1].cells[5].text,
                          table.rows[2].cells[4].text, table.rows[2].cells[5].text]
        truly_empty_cell = table.rows[1].cells[6].text
        assert checkbox_cells == ["", "", "", ""]
        assert truly_empty_cell == ""

    def test_unified_reader_reports_carriers_not_zero(
        self, real_docx_with_cell_checkboxes
    ):
        """同一份文件，统一件必须报「有 4 个载体、勾了 1 个」。"""
        _assert_reads_four_carriers(read_checkboxes(real_docx_with_cell_checkboxes))

    def test_reader_emits_text_view_diagnostic(self, real_docx_with_cell_checkboxes):
        """漏读诊断必须是**返回结果的一部分**，不是日志里的一行 WARN。"""
        _assert_emits_missing_four_diagnostic(
            read_checkboxes(real_docx_with_cell_checkboxes)
        )


def _assert_reads_four_carriers(reading) -> None:
    assert reading.status is ReadingStatus.HAS_CARRIERS
    assert reading.carrier_total == 4
    assert reading.checked_total == 1
    assert reading.status is not ReadingStatus.NO_CARRIER


def _assert_emits_missing_four_diagnostic(reading) -> None:
    assert reading.diagnostics, "该报的漏读诊断没报出来"
    d = reading.diagnostics[0]
    assert d.xml_view_count == 4
    assert d.text_view_count == 0
    assert d.missing_count == 4
    assert "会漏 4 个" in d.message()


# ================================================================ 4.2 非恒真自证

def test_mutation_blank_detector_makes_4_1_fail(
    real_docx_with_cell_checkboxes, monkeypatch
):
    """把载体探测器换成恒返回空的桩，4.1 的断言 **MUST** 失败。

    🔴 这里**逐字复用 4.1 那两组断言函数**，不另写一套"退化后应该长什么样"
    的期望——否则这条自证只证明了它自己（同 `#355`／`#399` 的变异验证纪律）。
    """
    monkeypatch.setattr(cb_mod, "detect_control_carriers", lambda *a, **k: [])
    monkeypatch.setattr(cb_mod, "detect_char_carriers", lambda *a, **k: [])
    reading = read_checkboxes(real_docx_with_cell_checkboxes)
    with pytest.raises(AssertionError):
        _assert_reads_four_carriers(reading)
    with pytest.raises(AssertionError):
        _assert_emits_missing_four_diagnostic(reading)


# ================================================================ 4.3 三态区分

class TestThreeStatesAreDistinct:
    @pytest.fixture
    def failure(self, tmp_path) -> CheckboxReading:
        bad = tmp_path / "broken.docx"
        bad.write_bytes(b"this is not a zip file at all")
        return read_checkboxes(bad)

    @pytest.fixture
    def no_carrier(self, tmp_path) -> CheckboxReading:
        path = _write_docx(tmp_path, "plain.docx", "<w:p><w:r><w:t>普通正文</w:t></w:r></w:p>")
        return read_checkboxes(path)

    @pytest.fixture
    def zero_checked(self, tmp_path) -> CheckboxReading:
        body = f"<w:p>{_checkbox_sdt(False)}{_checkbox_sdt(False)}</w:p>"
        path = _write_docx(tmp_path, "unchecked.docx", body)
        return read_checkboxes(path)

    def test_三态互不相等(self, failure, no_carrier, zero_checked):
        assert failure.status is ReadingStatus.READ_FAILED
        assert no_carrier.status is ReadingStatus.NO_CARRIER
        assert zero_checked.status is ReadingStatus.HAS_CARRIERS
        assert failure != no_carrier
        assert no_carrier != zero_checked
        assert failure != zero_checked

    def test_falsy_判断根本写不出来(self, failure, no_carrier, zero_checked):
        """🔴 结构性保证：`if not reading:` 直接抛 TypeError，不依赖任何人记得判据。"""
        for reading in (failure, no_carrier, zero_checked):
            with pytest.raises(TypeError, match="三件不同的事"):
                bool(reading)
            with pytest.raises(TypeError):
                if not reading:  # noqa: SIM103  — 这一行正是要被禁掉的写法
                    pass

    def test_读取失败点名原因与路径(self, failure):
        assert "不是合法的 zip" in failure.failure_reason
        assert "broken.docx" in failure.failure_reason
        assert failure.is_failure is True

    def test_读取失败可一行转异常(self, failure, zero_checked):
        with pytest.raises(DocxReadError):
            failure.raise_for_failure()
        assert zero_checked.raise_for_failure() is zero_checked

    def test_零勾与无载体在人读摘要上也分得开(self, no_carrier, zero_checked):
        assert "没有任何勾选载体" in no_carrier.describe()
        assert "控件 2 个（勾 0）" in zero_checked.describe()

    def test_缺_document_xml_判为读取失败(self, tmp_path):
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as z:
            z.writestr("word/settings.xml", "<w:settings/>")
        path = tmp_path / "nodoc.docx"
        path.write_bytes(buf.getvalue())
        reading = read_checkboxes(path)
        assert reading.status is ReadingStatus.READ_FAILED
        assert "word/document.xml" in reading.failure_reason


# ================================================================ 三形态一次覆盖

class TestThreeShapesInOnePass:
    def test_段落内裸勾按决策点2b给语义并与控件分列(self, tmp_path):
        body = (
            "<w:p><w:r><w:t>☑ 认可</w:t></w:r></w:p>"
            "<w:p><w:r><w:t>☐ 待定</w:t></w:r></w:p>"
            f"<w:p>{_checkbox_sdt(True)}</w:p>"
        )
        path = _write_docx(tmp_path, "mixed.docx", body)
        reading = read_checkboxes(path)
        assert reading.control_total == 1 and reading.control_checked_count == 1
        assert reading.char_total == 2 and reading.char_checked_count == 1
        assert {c.source for c in reading.char_carriers} == {SOURCE_CHAR}
        assert {c.source for c in reading.control_carriers} == {SOURCE_CONTROL}
        # 🔴 分列不合并：两列各报各的，不揉成一个"总共勾了 2 个"就完事
        assert reading.carrier_total == 3 and reading.checked_total == 2

    def test_纯裸勾回件不再被读成一条都没勾(self, tmp_path):
        """`质量部#11` 形态（22 个裸 ☑、零控件）的最小复现。"""
        body = "".join(
            f"<w:p><w:r><w:t>☑ 第{i}条认可</w:t></w:r></w:p>" for i in range(22)
        )
        path = _write_docx(tmp_path, "loose22.docx", body)
        reading = read_checkboxes(path)
        assert reading.status is ReadingStatus.HAS_CARRIERS
        assert reading.char_total == 22 and reading.char_checked_count == 22

    def test_控件自身显示字符不被重复计为裸字符(self, tmp_path):
        body = f"<w:p>{_checkbox_sdt(True)}{_checkbox_sdt(False)}</w:p>"
        path = _write_docx(tmp_path, "ctrl.docx", body)
        reading = read_checkboxes(path)
        assert reading.control_total == 2
        assert reading.char_total == 0, "控件自身的 ☒/☐ 被当成「控件之外的裸字符」重复计了"

    def test_表格格内勾带同行其余单元格上下文(self, tmp_path):
        body = (
            "<w:tbl><w:tr>"
            "<w:tc><w:p><w:r><w:t>料号B提前期3天</w:t></w:r></w:p></w:tc>"
            f"<w:tc><w:p>{_checkbox_sdt(True)}</w:p></w:tc>"
            "<w:tc><w:p><w:r><w:t>口径应按在途量计</w:t></w:r></w:p></w:tc>"
            "</w:tr></w:tbl>"
        )
        path = _write_docx(tmp_path, "tbl.docx", body)
        reading = read_checkboxes(path)
        assert reading.control_total == 1
        row = reading.control_carriers[0].row_context
        assert "料号B提前期3天" in row and "口径应按在途量计" in row

    def test_同行多格同文字时不按文字滤掉自己那一格(self, tmp_path):
        """按元素身份排除自身格，不按文字比对——两格都是 ☒ 时不得一并滤掉。"""
        body = (
            "<w:tbl><w:tr>"
            f"<w:tc><w:p>{_checkbox_sdt(True)}</w:p></w:tc>"
            "<w:tc><w:p><w:r><w:t>☒</w:t></w:r></w:p></w:tc>"
            "</w:tr></w:tbl>"
        )
        path = _write_docx(tmp_path, "same.docx", body)
        reading = read_checkboxes(path)
        assert "☒" in reading.control_carriers[0].row_context


# ================================================================ 决策点④ 部件覆盖

class TestExtraParts:
    HEADER = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f"<w:hdr {W} {W14}><w:p><w:r><w:t>☑ 页眉里的勾</w:t></w:r></w:p></w:hdr>"
    )

    def test_页眉里的勾选被读到(self, tmp_path):
        path = _write_docx(
            tmp_path, "hdr.docx", "<w:p/>", extra_parts={"word/header1.xml": self.HEADER}
        )
        reading = read_checkboxes(path)
        assert reading.char_total == 1
        assert reading.char_carriers[0].part == "word/header1.xml"
        assert "word/header1.xml" in reading.parts_scanned

    def test_可关掉扩展部件_读数退回只看正文(self, tmp_path):
        path = _write_docx(
            tmp_path, "hdr2.docx", "<w:p/>", extra_parts={"word/header1.xml": self.HEADER}
        )
        reading = read_checkboxes(path, include_extra_parts=False)
        assert reading.status is ReadingStatus.NO_CARRIER
        assert reading.parts_scanned == ("word/document.xml",)


# ================================================================ 诊断不制造噪音

def test_两个视图一致时不产生噪声诊断(tmp_path):
    body = "<w:p><w:r><w:t>☑ 认可</w:t></w:r></w:p>"
    path = _write_docx(tmp_path, "loose.docx", body)
    reading = read_checkboxes(path)
    assert reading.char_total == 1
    assert reading.diagnostics == (), "裸字符本来就在高层视图里看得见，不该报漏读"


def test_超链接包裹的裸勾会被诊断为高层视图漏读(tmp_path):
    """`w:hyperlink` 会把 `w:r` 降一层 ⇒ python-docx 的 `Paragraph.text` 看不见。"""
    body = "<w:p><w:hyperlink><w:r><w:t>☑ 认可</w:t></w:r></w:hyperlink></w:p>"
    path = _write_docx(tmp_path, "hyper.docx", body)
    reading = read_checkboxes(path)
    assert reading.char_total == 1
    assert reading.diagnostics and reading.diagnostics[0].missing_count == 1
