"""单测：`_输出截流.py`（队列 §一 #597 ⑸）。"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_MODULE_PATH = Path(__file__).resolve().parent / "_输出截流.py"
_spec = importlib.util.spec_from_file_location("_输出截流", _MODULE_PATH)
_mod = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = _mod
_spec.loader.exec_module(_mod)  # type: ignore[union-attr]

emit = _mod.emit
summarize = _mod.summarize
write_full_report = _mod.write_full_report


def test_成功路径默认只出摘要且不超20行(tmp_path, capsys):
    lines = [f"line {i}" for i in range(100)]
    code = emit("测试工具", lines, 0, repo_root=tmp_path)
    out = capsys.readouterr().out.rstrip("\n").splitlines()
    assert code == 0
    assert len(out) <= 20
    assert any("全文见" in ln or "全文已存" in ln for ln in out)


def test_成功路径全文写入reports且内容完整(tmp_path, capsys):
    lines = [f"line {i}" for i in range(50)]
    emit("测试工具", lines, 0, repo_root=tmp_path)
    report_dir = tmp_path / "reports" / "output-throttle" / "测试工具"
    files = list(report_dir.glob("*.log"))
    assert len(files) == 1
    content = files[0].read_text(encoding="utf-8")
    for i in range(50):
        assert f"line {i}" in content


def test_verbose时保留旧行为整段打印不写报告(tmp_path, capsys):
    lines = [f"line {i}" for i in range(50)]
    code = emit("测试工具", lines, 0, verbose=True, repo_root=tmp_path)
    out = capsys.readouterr().out
    assert code == 0
    for i in range(50):
        assert f"line {i}" in out
    report_dir = tmp_path / "reports" / "output-throttle" / "测试工具"
    assert not report_dir.exists()


def test_失败路径整段打印不截断(tmp_path, capsys):
    lines = [f"✗ 问题 {i}" for i in range(50)]
    code = emit("测试工具", lines, 1, repo_root=tmp_path)
    out = capsys.readouterr().out
    assert code == 1
    for i in range(50):
        assert f"✗ 问题 {i}" in out
    report_dir = tmp_path / "reports" / "output-throttle" / "测试工具"
    assert not report_dir.exists()


def test_摘要优先保留告警信号行(tmp_path):
    lines = [f"普通信息 {i}" for i in range(30)] + ["⚠ 警告A", "✗ 失败B"]
    report_path = tmp_path / "fake.log"
    summary = summarize(lines, report_path)
    assert "⚠ 警告A" in summary
    assert "✗ 失败B" in summary
    assert len(summary) <= 20


def test_不足20行时不省略也不丢内容(tmp_path):
    lines = ["a", "b", "c"]
    report_path = tmp_path / "fake.log"
    summary = summarize(lines, report_path)
    assert "a" in summary and "b" in summary and "c" in summary
    assert "已省略" not in "\n".join(summary)
    assert str(report_path) in "\n".join(summary)
