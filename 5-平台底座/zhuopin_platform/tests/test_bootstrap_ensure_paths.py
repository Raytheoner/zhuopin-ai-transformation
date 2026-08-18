"""`zhuopin_platform.bootstrap.ensure_paths()` 行为契约测试。

对应 spec `platform-path-bootstrap`（变更包 `platform-bootstrap-ensure-paths`）。
覆盖四种情形：monorepo 命中 / 扁平命中 / 两者皆无但环境可导入 / 全无（须 raise），
外加 strict 模式与"不重复插入"两条。

🔴 全部用**真实构造的临时目录**做布局，不 mock 文件系统——这个 bug 的全部特征就是
"本地看不出来"，用假的目录结构测它等于什么都没测（队列 #345）。
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

from zhuopin_platform import bootstrap
from zhuopin_platform.bootstrap import ensure_paths


@pytest.fixture(autouse=True)
def _restore_sys_path():
    """每个用例还原 sys.path，避免测试之间互相污染。"""
    saved = list(sys.path)
    yield
    sys.path[:] = saved


def _make_monorepo(tmp_path: Path) -> tuple[Path, Path, Path]:
    """构造 <repo>/5-平台底座/zhuopin_platform ＋ <repo>/4-数字员工/X/场景/pkg/run.py。"""
    platform = tmp_path / "5-平台底座" / "zhuopin_platform"
    platform.mkdir(parents=True)
    scene = tmp_path / "4-数字员工" / "采购部" / "SCX-演示场景"
    caller = scene / "pkg" / "run.py"
    caller.parent.mkdir(parents=True)
    caller.write_text("# demo\n", encoding="utf-8")
    return platform, scene, caller


def _make_flat(tmp_path: Path) -> tuple[Path, Path, Path]:
    """构造 `.51` 扁平布局 C:/<svc>/{zhuopin_platform,app}，caller 在 app/scripts/ 下。"""
    base = tmp_path / "svc"
    platform = base / "zhuopin_platform"
    platform.mkdir(parents=True)
    app = base / "app"
    caller = app / "scripts" / "run_web.py"
    caller.parent.mkdir(parents=True)
    caller.write_text("# demo\n", encoding="utf-8")
    return platform, app, caller


# ── 情形 1：monorepo 命中标记 ────────────────────────────────────────────────

def test_monorepo命中_平台底座与自身包根均前插且顺序正确(tmp_path):
    platform, scene, caller = _make_monorepo(tmp_path)

    inserted = ensure_paths(caller, scene)

    assert str(platform) in sys.path
    assert str(scene) in sys.path
    # 与替换前的内联块一致：先插平台底座、再插自身包根 ⇒ 自身包根最终排在更前
    assert sys.path.index(str(scene)) < sys.path.index(str(platform))
    assert inserted == [str(platform), str(scene)]


def test_monorepo命中时不查环境_即便环境无平台底座也不报错(tmp_path, monkeypatch):
    """命中标记即认定为开发机，此时 find_spec 结果与结论无关，不该被查。"""
    _, scene, caller = _make_monorepo(tmp_path)
    monkeypatch.setattr(bootstrap, "find_spec", lambda name: pytest.fail(
        "monorepo 分支不应查询环境"))

    ensure_paths(caller, scene)


# ── 情形 2／3：未命中标记，交由环境解析（`.51` 扁平部署布局） ────────────────

def test_扁平布局未命中标记_不抛错且自身包根被插入(tmp_path):
    """`.51` 真实布局：平台底座是 app 的兄弟目录、已 pip install -e 进该服务 venv。

    这正是 2026-08-18 打挂 8091／8093 的那条路径——原实现在此无条件 raise。
    """
    _, app, caller = _make_flat(tmp_path)

    inserted = ensure_paths(caller, app)

    assert str(app) in sys.path
    assert inserted == [str(app)]


def test_两种布局皆不成立但环境可导入_仍不抛错(tmp_path):
    """无标记、也无兄弟目录，但环境里装着平台底座（本测试进程自身即如此）。"""
    caller = tmp_path / "lonely" / "run.py"
    caller.parent.mkdir(parents=True)
    caller.write_text("# demo\n", encoding="utf-8")

    inserted = ensure_paths(caller, caller.parent)

    assert inserted == [str(caller.parent)]


# ── 情形 4：全无 —— 必须明确 raise，不得静默 ────────────────────────────────

def test_全无时抛RuntimeError且消息含调用方真实路径(tmp_path, monkeypatch):
    caller = tmp_path / "lonely" / "run.py"
    caller.parent.mkdir(parents=True)
    caller.write_text("# demo\n", encoding="utf-8")
    monkeypatch.setattr(bootstrap, "find_spec", lambda name: None)

    with pytest.raises(RuntimeError) as exc:
        ensure_paths(caller, caller.parent)

    message = str(exc.value)
    # 两层事实都要在，缺一则读者无法判断该修布局还是该装包
    assert "5-平台底座/zhuopin_platform" in message
    assert "环境中也没有可导入的 zhuopin_platform" in message
    # 路径须被真实插值，不得是未求值的字面量占位符
    assert str(caller.resolve()) in message
    assert "{" not in message


def test_平台底座存在但子模块缺失_不被拦截(tmp_path):
    """ensure_paths 只管路径，调用方随后 import 不存在的子模块应收到原生错误。"""
    _, scene, caller = _make_monorepo(tmp_path)
    ensure_paths(caller, scene)

    with pytest.raises(ModuleNotFoundError):
        __import__("zhuopin_platform.根本不存在的子模块")


# ── strict 模式 ────────────────────────────────────────────────────────────

def test_strict未命中标记时必然抛错_即便环境可导入(tmp_path):
    """conftest.py 的语义：测试必须跑在仓库内，回退会让测试悄悄测了别人的代码。"""
    _, app, caller = _make_flat(tmp_path)
    # 不 mock find_spec —— 本进程里 zhuopin_platform 确实可导入，正是该场景的要害
    assert bootstrap.find_spec("zhuopin_platform") is not None

    with pytest.raises(RuntimeError) as exc:
        ensure_paths(caller, app, strict=True)

    assert "strict=True" in str(exc.value)
    assert str(caller.resolve()) in str(exc.value)
    assert str(app) not in sys.path


def test_strict在monorepo内行为与非strict完全一致(tmp_path):
    platform, scene, caller = _make_monorepo(tmp_path)

    strict_inserted = ensure_paths(caller, scene, strict=True)
    sys.path.remove(str(scene))
    sys.path.remove(str(platform))
    plain_inserted = ensure_paths(caller, scene, strict=False)

    assert strict_inserted == plain_inserted == [str(platform), str(scene)]


# ── 过渡期共存：不重复插入 ─────────────────────────────────────────────────

def test_已在sys_path中的路径不重复插入(tmp_path):
    """过渡期内联块与 ensure_paths 会在同一进程共存，不得堆出同一路径多份条目。"""
    platform, scene, caller = _make_monorepo(tmp_path)
    sys.path.insert(0, str(platform))

    inserted = ensure_paths(caller, scene)

    assert sys.path.count(str(platform)) == 1
    assert inserted == [str(scene)]


def test_重复调用幂等(tmp_path):
    platform, scene, caller = _make_monorepo(tmp_path)

    ensure_paths(caller, scene)
    second = ensure_paths(caller, scene)

    assert second == []
    assert sys.path.count(str(platform)) == 1
    assert sys.path.count(str(scene)) == 1
