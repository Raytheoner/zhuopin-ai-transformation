"""队列 #300：worktree 隔离引导代码的回归测试。

本变更选定"自包含重复片段"（design.md 决策点 1），故没有一个可以直接 import 的
`bootstrap()` 函数可测——测试改为：从本仓库真实的 `conftest.py`（本文件的同目录
邻居）原样抽取该段引导代码文本（而非在测试里手打一份可能与生产代码悄悄漂移的
副本），拼进合成的临时 worktree 目录树里用真实子进程执行，验证其行为契约。

抽取边界（两个稳定的文本锚点，均已在生产 conftest.py 中真实存在）：
  起点 —— "# —— worktree 隔离引导（队列 #300）"注释首行
  终点 —— 对应的 `raise RuntimeError(...)` 行（含）
"""
from __future__ import annotations

import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

_THIS_CONFTEST = Path(__file__).resolve().parent / "conftest.py"
_START_MARKER = "# —— worktree 隔离引导（队列 #300）"
_END_MARKER = "raise RuntimeError("


def _extract_bootstrap_snippet() -> str:
    """从真实 conftest.py 原样抽取引导代码文本（含起止两行）。"""
    lines = _THIS_CONFTEST.read_text(encoding="utf-8").splitlines()
    start = next(i for i, ln in enumerate(lines) if _START_MARKER in ln)
    end = next(i for i in range(start, len(lines)) if _END_MARKER in lines[i])
    return "\n".join(lines[start : end + 1])


BOOTSTRAP_SNIPPET = _extract_bootstrap_snippet()


def _make_fake_worktree(root: Path, sentinel: str) -> Path:
    """在 root 下构造一棵最小 worktree 目录树：
    <root>/5-平台底座/zhuopin_platform/zhuopin_platform/__init__.py（含哨兵常量）
    <root>/4-数字员工/测试域/测试场景/tests/conftest.py（真实抽取的引导代码 + 自检 import）
    返回 conftest.py 路径。
    """
    platform_pkg = root / "5-平台底座" / "zhuopin_platform" / "zhuopin_platform"
    platform_pkg.mkdir(parents=True, exist_ok=True)
    (platform_pkg / "__init__.py").write_text(
        f'WORKTREE_SENTINEL = "{sentinel}"\n', encoding="utf-8"
    )

    scenario_tests = root / "4-数字员工" / "测试域" / "测试场景" / "tests"
    scenario_tests.mkdir(parents=True, exist_ok=True)
    conftest_path = scenario_tests / "conftest.py"
    conftest_path.write_text(
        BOOTSTRAP_SNIPPET + "\n\nimport zhuopin_platform\n"
        "print('SENTINEL=' + zhuopin_platform.WORKTREE_SENTINEL)\n",
        encoding="utf-8",
    )
    return conftest_path


class TestWorktreeIsolationSurvivesPoisonedGlobalPointer:
    """验收要求①：全局 editable 指针指向别的 worktree 时，本 worktree 仍解析到自己的代码。"""

    def test_local_worktree_wins_over_poisoned_pythonpath(self, tmp_path):
        worktree_a = _make_fake_worktree(tmp_path / "worktree_a", sentinel="A")
        worktree_b = _make_fake_worktree(tmp_path / "worktree_b", sentinel="B")

        # 模拟"全局 editable 指针指向 worktree A"：把 A 的平台底座目录塞进
        # PYTHONPATH（真实 pip editable 安装的效果等价于往 sys.path 加一条路径，
        # 用 PYTHONPATH 模拟这一点足以复现"全局指针指向别处"这个故障前提，且
        # 完全不触碰真实 site-packages，安全可重复）。
        poisoned_platform_dir = tmp_path / "worktree_a" / "5-平台底座" / "zhuopin_platform"
        env = {
            **_clean_env(),
            "PYTHONPATH": str(poisoned_platform_dir),
        }

        result = subprocess.run(
            [sys.executable, str(worktree_b)],
            capture_output=True, text=True, env=env, timeout=30,
        )

        assert result.returncode == 0, result.stderr
        assert "SENTINEL=B" in result.stdout, (
            f"应解析到本 worktree（B）的代码，而不是被污染的全局指针（A）指向的代码。"
            f"stdout={result.stdout!r} stderr={result.stderr!r}"
        )

    def test_no_pythonpath_pollution_still_resolves_locally(self, tmp_path):
        """未曾执行过 pip install -e（sys.path 中无任何相关条目）时，仍可正常 import。"""
        worktree = _make_fake_worktree(tmp_path / "worktree_only", sentinel="ONLY")

        result = subprocess.run(
            [sys.executable, str(worktree)],
            capture_output=True, text=True, env=_clean_env(), timeout=30,
        )

        assert result.returncode == 0, result.stderr
        assert "SENTINEL=ONLY" in result.stdout


class TestMissingRepoRootMarkerFailsLoud:
    """验收要求③：找不到仓库根标记时必须显式报错，不得静默跳过。"""

    def test_raises_when_marker_absent_in_all_ancestors(self, tmp_path):
        # 只造一个孤立的 tests/conftest.py，其任何祖先目录下都没有
        # 5-平台底座/zhuopin_platform，模拟"目录结构被破坏/脚本被挪错位置"。
        orphan_tests = tmp_path / "somewhere" / "not_a_repo" / "tests"
        orphan_tests.mkdir(parents=True)
        conftest_path = orphan_tests / "conftest.py"
        conftest_path.write_text(BOOTSTRAP_SNIPPET + "\n", encoding="utf-8")

        result = subprocess.run(
            [sys.executable, str(conftest_path)],
            capture_output=True, text=True, env=_clean_env(), timeout=30,
        )

        assert result.returncode != 0
        assert "未找到仓库根标记" in result.stderr


class TestBootstrapSnippetSourceOfTruth:
    """确保被测的引导代码文本确实来自真实生产文件，测试不会因为文件改名/内容
    被清空而悄悄退化成"永远通过的空测试"。"""

    def test_snippet_is_non_trivial_and_contains_expected_markers(self):
        assert len(BOOTSTRAP_SNIPPET.splitlines()) >= 8
        assert "sys.path.insert" in BOOTSTRAP_SNIPPET
        assert "5-平台底座" in BOOTSTRAP_SNIPPET
        assert "zhuopin_platform" in BOOTSTRAP_SNIPPET


def _clean_env() -> dict:
    """构造一份不含本机真实 PYTHONPATH/其它 site-packages 干扰的最小子进程环境。"""
    import os

    env = {k: v for k, v in os.environ.items() if k != "PYTHONPATH"}
    return env
