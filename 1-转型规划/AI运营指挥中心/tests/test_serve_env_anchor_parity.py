"""`serve.py` 内联凭据锚定 与 `zhuopin_platform.env_anchor` 的**等价性**测试（队列 #354）。

## 为什么这个文件必须存在

`env-anchor-collapse` 的整个目的是消灭「同一段逻辑靠复制粘贴分发、每份副本独立漂移」。
而 `serve.py` 是该变更包**唯一刻意保留的内联副本**——它"零三方依赖"是既定设计原则，`.51`
上跑的是裸 `python serve.py`，部署侧没有 venv、也没有 `pip install -e zhuopin_platform`，
`import zhuopin_platform.env_anchor` 会让 8092 命令中心在生产直接起不来（而本地全绿）。

**例外一旦不受任何机制约束，就退化成第 10 种语义。** 本文件就是那个约束：拿同一套夹具同时
喂给两份实现，断言它们**逐个布局给出同一个答案**。改了平台底座那份而忘了改 `serve.py`
（或反过来），这里当场红。

⚠️ **本文件不能用「读源码比对文本」的方式写**——那只能证明两段字符像，证明不了它们**行为**
同。断言必须落在两份实现各自的返回值上。
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

SCENE = Path(__file__).resolve().parent.parent
if str(SCENE) not in sys.path:
    sys.path.insert(0, str(SCENE))

import serve  # noqa: E402

# 平台底座那一份（测试环境是 monorepo，一定找得到；找不到就该红）
_REPO_ROOT = next(
    p for p in Path(__file__).resolve().parents
    if (p / "5-平台底座" / "zhuopin_platform").is_dir()
)
sys.path.insert(0, str(_REPO_ROOT / "5-平台底座" / "zhuopin_platform"))

from zhuopin_platform.env_anchor import (  # noqa: E402
    EnvFileOverrideMissing,
    resolve_env_file,
)

MARKER = Path("5-平台底座") / "zhuopin_platform"


def _make_monorepo(root: Path) -> None:
    (root / MARKER).mkdir(parents=True)
    (root / MARKER / "pyproject.toml").write_text("[project]\n", encoding="utf-8")
    (root / ".env").write_text("ZP_GATE_PASSWORD=x\n", encoding="utf-8")


def _make_flat_deploy(root: Path) -> None:
    dist = root / "zhuopin_platform"
    (dist / "zhuopin_platform").mkdir(parents=True)
    (dist / "zhuopin_platform" / "__init__.py").write_text("", encoding="utf-8")
    (dist / "pyproject.toml").write_text("[project]\n", encoding="utf-8")
    (root / ".env").write_text("ZP_GATE_PASSWORD=x\n", encoding="utf-8")


def _serve_answer(root_dir: Path, monkeypatch, caller: Path) -> Path | None:
    """跑 `serve.py` 那一份。它以模块级 `ROOT` 为解析起点，故 monkeypatch 掉它。"""
    monkeypatch.setattr(serve, "ROOT", str(root_dir))
    hit = serve._find_env()
    return Path(hit).resolve() if hit else None


def _platform_answer(caller: Path) -> Path | None:
    hit = resolve_env_file(caller, env=dict(os.environ)).path
    return Path(hit).resolve() if hit else None


@pytest.fixture(autouse=True)
def _clean_override(monkeypatch):
    monkeypatch.delenv("ZP_ENV_FILE", raising=False)


def test_parity_monorepo_layout(tmp_path, monkeypatch):
    root = tmp_path / "repo"
    _make_monorepo(root)
    app = root / "1-转型规划" / "AI运营指挥中心"
    app.mkdir(parents=True)
    caller = app / "serve.py"
    caller.write_text("# caller\n", encoding="utf-8")

    assert _serve_answer(app, monkeypatch, caller) == _platform_answer(caller)
    assert _serve_answer(app, monkeypatch, caller) == (root / ".env").resolve()


def test_parity_flat_deploy_layout(tmp_path, monkeypatch):
    root = tmp_path / "cc"
    _make_flat_deploy(root)
    app = root / "app"
    app.mkdir()
    caller = app / "serve.py"
    caller.write_text("# caller\n", encoding="utf-8")

    assert _serve_answer(app, monkeypatch, caller) == _platform_answer(caller)
    assert _serve_answer(app, monkeypatch, caller) == (root / ".env").resolve()


def test_parity_flat_layout_does_not_stop_at_distribution_dir(tmp_path, monkeypatch):
    """两份实现都必须锚在 `C:/<svc>/`，不是 `C:/<svc>/zhuopin_platform/`。"""
    root = tmp_path / "cc"
    _make_flat_deploy(root)
    inner = root / "zhuopin_platform" / "scripts"
    inner.mkdir(parents=True)
    caller = inner / "x.py"
    caller.write_text("# caller\n", encoding="utf-8")

    assert _serve_answer(inner, monkeypatch, caller) == _platform_answer(caller)
    assert _serve_answer(inner, monkeypatch, caller) == (root / ".env").resolve()


def test_parity_no_env_anywhere(tmp_path, monkeypatch):
    root = tmp_path / "repo"
    _make_monorepo(root)
    (root / ".env").unlink()
    app = root / "1-转型规划" / "AI运营指挥中心"
    app.mkdir(parents=True)
    caller = app / "serve.py"
    caller.write_text("# caller\n", encoding="utf-8")

    assert _serve_answer(app, monkeypatch, caller) is None
    assert _platform_answer(caller) is None


def test_parity_override_wins(tmp_path, monkeypatch):
    root = tmp_path / "repo"
    _make_monorepo(root)
    app = root / "1-转型规划" / "AI运营指挥中心"
    app.mkdir(parents=True)
    caller = app / "serve.py"
    caller.write_text("# caller\n", encoding="utf-8")
    other = tmp_path / "elsewhere.env"
    other.write_text("ZP_GATE_PASSWORD=y\n", encoding="utf-8")

    monkeypatch.setenv("ZP_ENV_FILE", str(other))
    assert _serve_answer(app, monkeypatch, caller) == other.resolve()
    assert _platform_answer(caller) == other.resolve()


def test_parity_override_missing_file_fails_loud_on_both(tmp_path, monkeypatch):
    root = tmp_path / "repo"
    _make_monorepo(root)
    app = root / "1-转型规划" / "AI运营指挥中心"
    app.mkdir(parents=True)
    caller = app / "serve.py"
    caller.write_text("# caller\n", encoding="utf-8")

    monkeypatch.setenv("ZP_ENV_FILE", str(tmp_path / "nope.env"))
    with pytest.raises(RuntimeError):
        _serve_answer(app, monkeypatch, caller)
    with pytest.raises(EnvFileOverrideMissing):
        _platform_answer(caller)


@pytest.mark.skipif(shutil.which("git") is None, reason="需要 git")
def test_parity_worktree_both_escape_to_main_workspace(tmp_path, monkeypatch):
    """🔴 两份实现都必须逃出 linked worktree，拿到主工作区那份新鲜凭据。

    这是 #354 的病灶本身；`serve.py` 是例外，但**不能是这条判据的例外**。
    """
    main = tmp_path / "main"
    main.mkdir()
    for args in (["init", "-q", "-b", "master"],
                 ["config", "user.email", "t@example.com"],
                 ["config", "user.name", "t"]):
        subprocess.run(["git", *args], cwd=str(main), check=True, capture_output=True)
    _make_monorepo(main)
    app_main = main / "1-转型规划" / "AI运营指挥中心"
    app_main.mkdir(parents=True)
    (app_main / "serve.py").write_text("# caller\n", encoding="utf-8")
    (main / ".gitignore").write_text(".env\n", encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=str(main), check=True, capture_output=True)
    subprocess.run(["git", "commit", "-qm", "init"], cwd=str(main), check=True,
                   capture_output=True)

    wt = main / ".claude" / "worktrees" / "stale"
    subprocess.run(["git", "worktree", "add", "-q", "-b", "wip", str(wt)],
                   cwd=str(main), check=True, capture_output=True)
    (wt / ".env").write_text("ZP_GATE_PASSWORD=stale\n", encoding="utf-8")   # 病灶副本
    app_wt = wt / "1-转型规划" / "AI运营指挥中心"
    caller_wt = app_wt / "serve.py"
    assert caller_wt.is_file()

    expected = (main / ".env").resolve()
    assert _serve_answer(app_wt, monkeypatch, caller_wt) == expected
    assert _platform_answer(caller_wt) == expected


@pytest.mark.skipif(shutil.which("git") is None, reason="需要 git")
def test_mutation_old_serve_writing_would_pick_the_stale_copy(tmp_path):
    """🔴 变异验证：`serve.py` 修复前的写法喂给同一夹具，**必须**解出 worktree 那份。

    判据若不红，说明上面那条「两份都逃出 worktree」的通过是空的。
    """
    main = tmp_path / "main"
    main.mkdir()
    for args in (["init", "-q", "-b", "master"],
                 ["config", "user.email", "t@example.com"],
                 ["config", "user.name", "t"]):
        subprocess.run(["git", *args], cwd=str(main), check=True, capture_output=True)
    _make_monorepo(main)
    (main / ".gitignore").write_text(".env\n", encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=str(main), check=True, capture_output=True)
    subprocess.run(["git", "commit", "-qm", "init"], cwd=str(main), check=True,
                   capture_output=True)
    wt = main / ".claude" / "worktrees" / "stale"
    subprocess.run(["git", "worktree", "add", "-q", "-b", "wip", str(wt)],
                   cwd=str(main), check=True, capture_output=True)
    (wt / ".env").write_text("ZP_GATE_PASSWORD=stale\n", encoding="utf-8")
    app_wt = wt / "1-转型规划" / "AI运营指挥中心"
    app_wt.mkdir(parents=True, exist_ok=True)

    def old_find_env(root: str):
        """`serve.py` 修复前的原文：从 ROOT 向上找**最近的** `.env`。"""
        here = root
        while True:
            cand = os.path.join(here, ".env")
            if os.path.isfile(cand):
                return cand
            parent = os.path.dirname(here)
            if parent == here:
                return None
            here = parent

    stale = old_find_env(str(app_wt))
    assert stale is not None
    assert Path(stale).resolve() == (wt / ".env").resolve(), "夹具没造出病灶，变异验证空转"


# ════════════════════════════════════════════════════════════════════════════
#  🔴 2026-08-27（OP-0827-B，队列 #354 tasks 2.3.4）——`.51` 真机实撞补的两条
#
#  上面那批用例全部通过、8 例全绿，却**漏掉了本服务在生产上的真实形状**：
#  `C:\command-center\{serve.py, index.html, data}` —— **没有 zhuopin_platform 目录**，
#  因为「零三方依赖、不装平台底座」正是本服务的既定设计（见本文件顶部）。
#
#  于是三段锚定②（monorepo marker）与③（`<root>/zhuopin_platform/pyproject.toml`）
#  一段都不命中，`_find_env()` 返回 None，而 `.env` 就躺在 `serve.py` 旁边 ⇒
#  `ZP_GATE_PASSWORD` 读不到 ⇒ **门禁静默失效：服务照起、页面照 200、只有口令没了。**
#
#  🔑 **为什么上面 8 条一条都没红**：它们断言的是「两份实现给出**同一个**答案」，
#     而**两边都答 None 也叫一致**。**一致 ≠ 正确。**
#     等价性测试守的是「两份副本不漂」，守不住「两份副本一起答错」——这是等价性
#     这种测试形态的固有盲区，不是这批用例写得不好。
#
#  生产侧的解＝`start-command-center.ps1` 用第①段 `ZP_ENV_FILE` 显式指名
#  （由 `deploy-server.ps1` 生成）。下面第二条就是把那个解钉住。
# ════════════════════════════════════════════════════════════════════════════

def _make_command_center_deploy(root: Path) -> None:
    """`.51` 上命令中心的真实形状：只有 serve.py / index.html / data / .env。"""
    (root / "data").mkdir(parents=True)
    (root / "index.html").write_text("<html></html>", encoding="utf-8")
    (root / ".env").write_text("ZP_GATE_PASSWORD=x\n", encoding="utf-8")


def test_命令中心部署布局下三段锚定确实一段都不命中(tmp_path, monkeypatch):
    """这条**故意断言 None**——它记录的是一个真实缺口，不是期望行为。

    ⚠️ 若将来有人给三段锚定加了「取自己目录旁边那份 `.env`」之类的第四段，本条会红。
    **那时不要直接把它改绿**：先回答「新加的那一段会不会把 `#354` 要消灭的
    『取最近的 .env』重新引回来」，再决定是改实现还是改本条。
    """
    root = tmp_path / "command-center"
    _make_command_center_deploy(root)
    caller = root / "serve.py"
    caller.write_text("", encoding="utf-8")

    assert _serve_answer(root, monkeypatch, caller) is None
    assert _platform_answer(caller) is None          # 两份实现同样答 None ⇒ 等价性测试拦不住
    assert (root / ".env").is_file()                 # 而它就在那儿


def test_命令中心部署布局下ZP_ENV_FILE能把它救回来(tmp_path, monkeypatch):
    """钉住生产侧的解：`start-command-center.ps1` 设的那个环境变量。

    它同时是**变异验证**——若有人把 `start-command-center.ps1` 里那行删掉、或让
    `deploy-server.ps1` 退回直接调 `python.exe`，门禁就会静默失效，而本条说明了
    为什么那一行不是可有可无的样板。
    """
    root = tmp_path / "command-center"
    _make_command_center_deploy(root)
    caller = root / "serve.py"
    caller.write_text("", encoding="utf-8")

    monkeypatch.setenv("ZP_ENV_FILE", str(root / ".env"))
    assert _serve_answer(root, monkeypatch, caller) == (root / ".env").resolve()
    assert _platform_answer(caller) == (root / ".env").resolve()


def test_deploy脚本确实把ZP_ENV_FILE写进了启动包装(tmp_path):
    """断言落在**生产脚本源码**上：`deploy-server.ps1` 必须生成 start-command-center.ps1
    且其中设了 `ZP_ENV_FILE`，并且计划任务注册的是那个包装、不是裸 python.exe。"""
    ps1 = (SCENE / "deploy-server.ps1").read_text(encoding="utf-8-sig")
    assert "start-command-center.ps1" in ps1
    assert "ZP_ENV_FILE" in ps1
    assert '-Execute "powershell.exe"' in ps1
    assert '-Execute $resolvedPython' not in ps1      # 旧的裸 python 注册方式不得复活
