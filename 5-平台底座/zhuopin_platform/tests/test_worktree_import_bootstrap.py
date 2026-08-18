"""队列 #300 引导的行为回归测试；#345 第二步收拢后同步更新抽取锚点与合成 worktree。

做法不变、也不该变：**从本仓库真实的 `conftest.py`（本文件的同目录邻居）原样抽取那段
stub 文本**，拼进合成的临时 worktree 目录树里用真实子进程执行——而不是在测试里手打一份
会与生产代码悄悄漂移的副本。#345 收拢之后 stub 里已经没有判断分支了，但"被执行的到底是
不是生产里那一份"这个问题反而更要紧：判断都搬进了 `bootstrap.ensure_paths()`，所以合成
worktree 里放的也是**真实的 `bootstrap.py`**，端到端测的是生产实现本身。

抽取边界（两个稳定的文本锚点，均在生产 `conftest.py` 中真实存在）：
  起点 —— "# —— 平台底座路径引导（队列 #345 收拢" 注释首行
  终点 —— 对应的 `ensure_paths(__file__, ...)` 调用行（含）
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

_THIS_CONFTEST = Path(__file__).resolve().parent / "conftest.py"
_REAL_BOOTSTRAP = Path(__file__).resolve().parents[1] / "zhuopin_platform" / "bootstrap.py"
_START_MARKER = "# —— 平台底座路径引导（队列 #345 收拢"
_END_MARKER = "ensure_paths(__file__"


def _extract_bootstrap_snippet() -> str:
    """从真实 conftest.py 原样抽取 stub 文本（含起止两行）。"""
    lines = _THIS_CONFTEST.read_text(encoding="utf-8").splitlines()
    start = next(i for i, ln in enumerate(lines) if _START_MARKER in ln)
    end = next(i for i in range(start, len(lines)) if _END_MARKER in lines[i])
    return "\n".join(lines[start : end + 1])


BOOTSTRAP_SNIPPET = _extract_bootstrap_snippet()
# 批一（非测试入口）的 stub 与批二只差一个 strict 参数，这里由同一份真实文本派生出
# 非 strict 形态，避免为了测 `.51` 那条分支再手打第二份副本。
BOOTSTRAP_SNIPPET_NON_STRICT = BOOTSTRAP_SNIPPET.replace(", strict=True", "")
_PREAMBLE = "import sys\nfrom pathlib import Path\n\n"


def _write_platform(root: Path, sentinel: str) -> Path:
    """在 root 下写出一份带哨兵常量的 zhuopin_platform 包（含真实的 bootstrap.py）。"""
    pkg = root / "zhuopin_platform"
    pkg.mkdir(parents=True, exist_ok=True)
    (pkg / "__init__.py").write_text(f'WORKTREE_SENTINEL = "{sentinel}"\n', encoding="utf-8")
    shutil.copy2(_REAL_BOOTSTRAP, pkg / "bootstrap.py")
    return root


def _make_fake_worktree(root: Path, sentinel: str) -> Path:
    """构造一棵最小 monorepo worktree，返回其中 tests/conftest.py 的路径。

    <root>/5-平台底座/zhuopin_platform/zhuopin_platform/{__init__,bootstrap}.py
    <root>/4-数字员工/测试域/测试场景/tests/conftest.py（真实抽取的 stub + 自检 import）
    """
    _write_platform(root / "5-平台底座" / "zhuopin_platform", sentinel)
    scenario_tests = root / "4-数字员工" / "测试域" / "测试场景" / "tests"
    scenario_tests.mkdir(parents=True, exist_ok=True)
    conftest_path = scenario_tests / "conftest.py"
    conftest_path.write_text(
        _PREAMBLE + BOOTSTRAP_SNIPPET + "\n\nimport zhuopin_platform\n"
        "print('SENTINEL=' + zhuopin_platform.WORKTREE_SENTINEL)\n",
        encoding="utf-8",
    )
    return conftest_path


def _clean_env(**overrides) -> dict:
    """不含本机真实 PYTHONPATH 干扰的最小子进程环境。"""
    env = {k: v for k, v in os.environ.items() if k != "PYTHONPATH"}
    env["PYTHONUTF8"] = "1"
    env.update(overrides)
    return env


class TestWorktreeIsolationSurvivesPoisonedGlobalPointer:
    """验收要求①：全局 editable 指针指向别的 worktree 时，本 worktree 仍解析到自己的代码。"""

    def test_local_worktree_wins_over_poisoned_pythonpath(self, tmp_path):
        _make_fake_worktree(tmp_path / "worktree_a", sentinel="A")
        worktree_b = _make_fake_worktree(tmp_path / "worktree_b", sentinel="B")

        # 模拟"全局 editable 指针指向 worktree A"：真实 pip editable 安装的效果等价于往
        # sys.path 加一条路径，用 PYTHONPATH 模拟足以复现该故障前提，且不触碰真实
        # site-packages，安全可重复。
        poisoned = tmp_path / "worktree_a" / "5-平台底座" / "zhuopin_platform"
        result = subprocess.run(
            [sys.executable, str(worktree_b)], capture_output=True, text=True,
            env=_clean_env(PYTHONPATH=str(poisoned)), timeout=30,
        )

        assert result.returncode == 0, result.stderr
        assert "SENTINEL=B" in result.stdout, (
            "应解析到本 worktree（B）的代码，而不是被污染的全局指针（A）指向的代码。"
            f"stdout={result.stdout!r} stderr={result.stderr!r}"
        )

    def test_no_pythonpath_pollution_still_resolves_locally(self, tmp_path):
        """未曾执行过 pip install -e（sys.path 中无任何相关条目）时，仍可正常 import。"""
        worktree = _make_fake_worktree(tmp_path / "worktree_only", sentinel="ONLY")

        result = subprocess.run(
            [sys.executable, str(worktree)], capture_output=True, text=True,
            env=_clean_env(), timeout=30,
        )

        assert result.returncode == 0, result.stderr
        assert "SENTINEL=ONLY" in result.stdout


class TestMissingRepoRootMarkerFailsLoud:
    """验收要求③：`tests/conftest.py`（strict）找不到仓库根标记时必须显式报错。

    🔴 要害在于：这里**故意让环境中存在一份可导入的平台底座**（PYTHONPATH 指向它）。
    若 strict 语义丢失、退化成扁平布局回退，测试就会悄悄跑在那份"别人的代码"上而依然
    全绿——那正是 #345 行内写明"monorepo 内 fail-loud 有价值"要防的事。
    """

    def test_strict_raises_when_marker_absent_in_all_ancestors(self, tmp_path):
        env_platform = _write_platform(tmp_path / "env_site_packages", sentinel="ENV")
        orphan_tests = tmp_path / "somewhere" / "not_a_repo" / "tests"
        orphan_tests.mkdir(parents=True)
        conftest_path = orphan_tests / "conftest.py"
        conftest_path.write_text(_PREAMBLE + BOOTSTRAP_SNIPPET + "\n", encoding="utf-8")

        result = subprocess.run(
            [sys.executable, str(conftest_path)], capture_output=True, text=True,
            env=_clean_env(PYTHONPATH=str(env_platform)), timeout=30,
        )

        assert result.returncode != 0, (
            f"strict 模式下缺标记必须报错，实际却成功了：stdout={result.stdout!r}")
        assert "未找到仓库根标记" in result.stderr
        assert "strict=True" in result.stderr

    def test_non_strict_falls_back_in_flat_deploy_layout(self, tmp_path):
        """对照组：批一那种非 strict 入口在同样缺标记的环境下**必须不报错**。

        这正是 `.51` 扁平布局（`C:/<svc>/{app,zhuopin_platform}`）的形态——2026-08-18
        把 8091／8093 打挂的就是这条路径上原先的无条件 raise。
        """
        env_platform = _write_platform(tmp_path / "env_site_packages", sentinel="ENV")
        app_dir = tmp_path / "svc" / "app" / "scripts"
        app_dir.mkdir(parents=True)
        entry = app_dir / "run_entry.py"
        entry.write_text(
            _PREAMBLE + BOOTSTRAP_SNIPPET_NON_STRICT + "\n\nimport zhuopin_platform\n"
            "print('SENTINEL=' + zhuopin_platform.WORKTREE_SENTINEL)\n",
            encoding="utf-8",
        )

        result = subprocess.run(
            [sys.executable, str(entry)], capture_output=True, text=True,
            env=_clean_env(PYTHONPATH=str(env_platform)), timeout=30,
        )

        assert result.returncode == 0, result.stderr
        assert "SENTINEL=ENV" in result.stdout


class TestBootstrapSnippetSourceOfTruth:
    """确保被测的 stub 文本确实来自真实生产文件，测试不会因为文件改名/内容被清空而
    悄悄退化成"永远通过的空测试"。"""

    def test_snippet_is_non_trivial_and_contains_expected_markers(self):
        assert len(BOOTSTRAP_SNIPPET.splitlines()) >= 8
        assert "sys.path.insert" in BOOTSTRAP_SNIPPET
        assert "5-平台底座" in BOOTSTRAP_SNIPPET
        assert "from zhuopin_platform.bootstrap import ensure_paths" in BOOTSTRAP_SNIPPET
        assert "strict=True" in BOOTSTRAP_SNIPPET

    def test_non_strict_variant_really_differs(self):
        """派生出的非 strict 形态必须真的不同，否则上面那组对照测试是自欺。"""
        assert BOOTSTRAP_SNIPPET_NON_STRICT != BOOTSTRAP_SNIPPET
        assert "strict=True" not in BOOTSTRAP_SNIPPET_NON_STRICT
