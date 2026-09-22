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
must_keep = _mod.must_keep
SUMMARY_LINE_CAP = _mod.SUMMARY_LINE_CAP


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


def test_must_keep行不占信号行名额且无条件保留(tmp_path):
    """队列 §一 #637：不带信号前缀的"零命中也回显"行，一旦被 must_keep()
    标记，即便前面已经堆满普通行也不能被挤掉——这正是本次踩的坑。"""
    padding = [f"普通信息 {i}" for i in range(30)]
    lines = [must_keep("🧭 XX 扫描（每轮回显，零命中亦不省略）：本轮待升格 0 个")] + padding
    report_path = tmp_path / "fake.log"
    summary = summarize(lines, report_path)
    assert "🧭 XX 扫描（每轮回显，零命中亦不省略）：本轮待升格 0 个" in summary
    # 队列 §一 `#637`（Shao Peishen 2026-09-22 答 `1a`：放开原 ≤20 硬上限）：
    # must-keep 行**不占** `SUMMARY_LINE_CAP` 名额，总行数上限＝must-keep 行数
    # ＋ 19 内容行 ＋ 1 行省略指针。原断言写死 `<= 20`，等于要求「保住表头」以
    # 「挤掉正文」为代价——那正是本行要治的病（实撞 `ResidentServiceDeploymentHintTests`
    # 断言的 `ZhuopinAibotDevListener` 正文行被裁，六关④ 2026-09-21 拦下）。
    # 本测试与 `test_must_keep行超过上限时允许摘要超出19行` 从此口径一致、不再自相矛盾。
    must_keep_count = sum(1 for ln in lines if ln.startswith("\x00MUST-KEEP\x00"))
    assert must_keep_count == 1
    assert len(summary) <= must_keep_count + 20


def test_must_keep行超过上限时允许摘要超出19行(tmp_path):
    """must-keep 优先且允许超出 `SUMMARY_LINE_CAP`——须明确写死的分支：
    宁可摘要多打几行，也不能静默丢掉"这一类到底跑没跑"的信号。"""
    must_keep_lines = [must_keep(f"🧭 第{i}类扫描（每轮回显，零命中亦不省略）") for i in range(SUMMARY_LINE_CAP + 5)]
    report_path = tmp_path / "fake.log"
    summary = summarize(must_keep_lines, report_path)
    for i in range(SUMMARY_LINE_CAP + 5):
        assert f"🧭 第{i}类扫描（每轮回显，零命中亦不省略）" in summary
    assert len(summary) > 20


def test_must_keep标记不泄漏进verbose与失败路径输出(tmp_path, capsys):
    lines = [must_keep("🧭 XX 扫描：本轮待升格 0 个")]
    emit("测试工具", lines, 0, verbose=True, repo_root=tmp_path)
    out = capsys.readouterr().out
    assert "🧭 XX 扫描：本轮待升格 0 个" in out
    assert "\x00" not in out

    emit("测试工具", lines, 1, repo_root=tmp_path)
    out = capsys.readouterr().out
    assert "🧭 XX 扫描：本轮待升格 0 个" in out
    assert "\x00" not in out


def test_must_keep标记不泄漏进落盘全文(tmp_path):
    lines = [must_keep("🧭 XX 扫描：本轮待升格 0 个")] + [f"line {i}" for i in range(30)]
    emit("测试工具", lines, 0, repo_root=tmp_path)
    report_dir = tmp_path / "reports" / "output-throttle" / "测试工具"
    files = list(report_dir.glob("*.log"))
    assert len(files) == 1
    content = files[0].read_text(encoding="utf-8")
    assert "🧭 XX 扫描：本轮待升格 0 个" in content
    assert "\x00" not in content
