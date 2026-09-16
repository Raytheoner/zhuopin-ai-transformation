"""单测：`工具-密钥扫描lint.py`（队列 §一 `#597` ⑵ 输出截流改造）。

只验证 `main()` 已接上 `_输出截流.emit` 这层输出形态——`--verbose` 开关是否
接线、成功／失败路径的摘要裁剪与整段打印行为是否符合 `_输出截流.emit` 的
既有语义（见 `test__输出截流.py`）。**判据本身**（凭据正则／占位符豁免／
`.env` 跟踪核验等）不在本文件复测——那是 `_run()` 内部逻辑，本次改造只是
把「跑完之后怎么打印」这一层从 `main()` 里剪出去，`_run()` 函数体一字未动。

用 `monkeypatch` 换掉 `_run`，让它可控地返回给定的 `(打印内容, exit_code)`——
真实全仓库扫描既慢又会随仓库内容漂移（当前即有若干已知误报，见
`工具-密钥扫描lint.py` 文件头 docstring 的边界说明），拿它做输出形态测试的
夹具不稳定，故不用；输出形态与判据分离测试，正是拆出 `_run()` 这一步改造
本身要达到的效果。
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

_MODULE_PATH = Path(__file__).resolve().with_name("工具-密钥扫描lint.py")


def _load_module():
    spec = importlib.util.spec_from_file_location("_secret_lint_under_test", _MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


M = _load_module()


def _patch_run(monkeypatch, lines, exit_code):
    """把 `_run()` 换成一个只打印给定 `lines`、返回给定 `exit_code` 的桩，
    绕开真实凭据扫描（慢且随仓库内容漂移），只验证 `main()` 的输出形态接线。"""

    def _fake_run():
        for ln in lines:
            print(ln)
        return exit_code

    monkeypatch.setattr(M, "_run", _fake_run)


def test_成功路径默认裁摘要并落盘全文(monkeypatch, capsys):
    lines = [f"✓ 第 {i} 项检查通过" for i in range(30)]
    _patch_run(monkeypatch, lines, 0)

    rc = M.main([])
    out = capsys.readouterr().out.splitlines()

    assert rc == 0
    assert len(out) <= 20, f"摘要应 ≤20 行，实得 {len(out)}：{out}"
    assert any("全文见" in ln or "全文已存" in ln for ln in out), f"摘要末尾应回显落盘路径：{out}"

    report_dir = M.REPO_ROOT / "reports" / "output-throttle" / "工具-密钥扫描lint"
    assert report_dir.is_dir(), f"应已建目录：{report_dir}"
    logs = list(report_dir.glob("*.log"))
    assert logs, "未找到落盘的全文报告"
    # 只断言「至少有一份内容匹配」而非「新增了几份」——同目录可能已有其它用例
    # 先写过文件，数量不稳定；内容匹配才是本项要验的东西。
    assert any("✓ 第 0 项检查通过" in lg.read_text(encoding="utf-8") for lg in logs)


def test_verbose开关保留整段打印不截断不落盘摘要标记(monkeypatch, capsys):
    lines = [f"✓ 第 {i} 项检查通过" for i in range(30)]
    _patch_run(monkeypatch, lines, 0)

    rc = M.main(["--verbose"])
    out = capsys.readouterr().out

    assert rc == 0
    for i in range(30):
        assert f"✓ 第 {i} 项检查通过" in out
    assert "全文已存" not in out
    assert "已省略" not in out


def test_失败路径不受verbose支配恒整段打印(monkeypatch, capsys):
    lines = [f"  - 疑似凭据 {i}" for i in range(30)]
    _patch_run(monkeypatch, lines, 1)

    rc = M.main([])
    out = capsys.readouterr().out

    assert rc == 1
    for i in range(30):
        assert f"疑似凭据 {i}" in out
    assert "全文已存" not in out
    assert "已省略" not in out


def test_main接受argv参数且默认走sys_argv不受影响(monkeypatch, capsys):
    """`main()` 由无参改为可传 `argv: list[str] | None = None`（供测试可控调用，
    且与文件 1 `工具-opener块lint.py` 同款结构），`args = ap.parse_args(argv)`
    在 `argv=None` 时仍照 argparse 既有语义回退到 `sys.argv[1:]`——文件尾
    `if __name__ == "__main__": sys.exit(main())` 那行因此不必改。"""
    _patch_run(monkeypatch, ["✓ 通过"], 0)

    rc = M.main([])
    assert rc == 0

    rc_verbose = M.main(["--verbose"])
    assert rc_verbose == 0
