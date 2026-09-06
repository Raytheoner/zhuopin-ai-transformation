"""队列 #446：拆件班次 CLI 层单测——只测参数处理/输出路由这一层没接错，
形态识别本身的逻辑已在 `test_reply_form_detection.py` 覆盖，这里不重复。
"""
from __future__ import annotations

import io
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import check_reply_form_signals as cli  # noqa: E402

W = 'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"'


def _write_minimal_docx(path: Path, body_xml: str = "<w:p><w:r><w:t>纯文字</w:t></w:r></w:p>") -> None:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr(
            "word/document.xml",
            f'<?xml version="1.0" encoding="UTF-8"?><w:document {W}><w:body>{body_xml}</w:body></w:document>',
        )
    path.write_bytes(buf.getvalue())


def _run(argv, capsys):
    code = cli.main(argv)
    return code, capsys.readouterr().out


def test_no_args_prints_usage_and_exits_2(capsys):
    code, out = _run([], capsys)
    assert code == 2
    assert "用法" in out


def test_missing_path_reported_not_silently_skipped(capsys, tmp_path):
    missing = tmp_path / "不存在.docx"
    code, out = _run([str(missing)], capsys)
    assert code == 2
    assert "不存在" in out
    assert "零信号" in out  # 明确写出"不得当成零信号"


def test_non_docx_extension_skipped_with_explanation(tmp_path, capsys):
    md = tmp_path / "文本反馈.md"
    md.write_text("纯文字回复", encoding="utf-8")
    code, out = _run([str(md)], capsys)
    assert code == 0
    assert "跳过" in out


def test_valid_docx_prints_summary_line(tmp_path, capsys):
    docx = tmp_path / "回复.docx"
    _write_minimal_docx(docx)
    code, out = _run([str(docx)], capsys)
    assert code == 0
    assert "均未命中" in out  # 纯文字回复无任何结构化信号，须如实报告


def test_broken_docx_reports_failure_not_zero_signal(tmp_path, capsys):
    broken = tmp_path / "损坏.docx"
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("readme.txt", "not a real docx")
    broken.write_bytes(buf.getvalue())
    code, out = _run([str(broken)], capsys)
    assert code == 2
    assert "读取失败" in out
