"""`run_sc2.py` 的必需凭据键回归守（队列 #354 tasks 2.3.5／2.3.6，OP-0827-B）。

## 这道守卫钉住的那件事

`.51` 真机复验时把四个常驻服务的 `REQUIRED_ENV_KEYS` 从「刻意留空」按实测填实。
本入口是四个里唯一一个**服务入口兼 CLI**，而 `load_env()` 在 argparse **分发之前**跑
（`main()`：`args = build_parser().parse_args(argv)` → `load_env(...)` → `args.func`）。

⇒ 若把 `U9C_*` 六个键**无条件**声明成必需，`--mode mock` 就再也不能在没有凭据的机器上跑，
而 mock 模式存在的意义恰恰是免凭据。故必需键与 `--mode` 绑定。

**这条契约的失败形态是静默的**：把两个常量合并「简化」掉之后，本地全量测试照样全绿
（开发机根 `.env` 里 `U9C_*` 六个都在），只有干净机器上的 mock 跑会炸。下面两条
变异验证就是为此设的——一条锁 mock 不该炸，一条锁 real 该炸。
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

_SC2_ROOT = Path(__file__).resolve().parent.parent
_ENTRY = _SC2_ROOT / "run_sc2.py"


def _load_entry():
    """把 `run_sc2.py` 作为模块载入（它在场景根、不属任何包）。"""
    spec = importlib.util.spec_from_file_location("_run_sc2_under_test", _ENTRY)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture()
def entry():
    mod = _load_entry()
    yield mod
    sys.modules.pop("_run_sc2_under_test", None)


def test_基础必需键不含门禁密码(entry):
    """`ZP_GATE_PASSWORD` 缺失时底座 `simple_gate` 按设计自动跳过门禁（既定默认路径），
    且开发机根 `.env` 里本就没有这个键——声明它等于把一条既定的本地开发路径判死。"""
    assert "ZP_GATE_PASSWORD" not in entry.REQUIRED_ENV_KEYS
    assert "ZP_GATE_PASSWORD" not in entry.REQUIRED_ENV_KEYS_REAL


def test_real键集是基础键集的超集且多出的正是U9C六个(entry):
    base = set(entry.REQUIRED_ENV_KEYS)
    real = set(entry.REQUIRED_ENV_KEYS_REAL)
    assert base <= real
    assert real - base == {
        "U9C_API_BASE", "U9C_USER_CODE", "U9C_ENT_CODE",
        "U9C_ORG_CODE", "U9C_CLIENT_ID", "U9C_CLIENT_SECRET",
    }


def test_mock模式在无凭据环境下不报缺键(entry, tmp_path, monkeypatch, capsys):
    """🔴 变异验证之一：把这条守住，才敢说填实没有把 mock 判死。

    用一个**空的**扁平部署布局当锚点（`.env` 存在但一个键都没有），并清空进程里所有
    `U9C_*`——这正是「干净机器上跑 mock」的形状。
    """
    _make_empty_flat_deploy(tmp_path, monkeypatch)
    entry.load_env(mode="mock")           # 不得抛
    entry.load_env(mode=None)             # `probe` 没有 --mode ⇒ None，同样不得抛
    assert "U9C_CLIENT_SECRET" not in capsys.readouterr().out  # 🔴 绝不回显键值/键名清单


def test_real模式在无凭据环境下报缺键并写明缺哪几个(entry, tmp_path, monkeypatch):
    """🔴 变异验证之二：若有人把两个常量合并/清空，本条会红。"""
    from zhuopin_platform.env_anchor import MissingRequiredKeys

    _make_empty_flat_deploy(tmp_path, monkeypatch)
    with pytest.raises(MissingRequiredKeys) as ei:
        entry.load_env(mode="real")
    msg = str(ei.value)
    for k in ("U9C_API_BASE", "U9C_CLIENT_ID", "U9C_CLIENT_SECRET"):
        assert k in msg


def test_main把子命令的mode透传给load_env(entry, monkeypatch):
    """钉住 `main()` 里那一行 `load_env(getattr(args, "mode", None))`——
    有人改回 `load_env()` 时本条会红（那会让 real 模式不再校验凭据）。"""
    seen: list[str | None] = []
    monkeypatch.setattr(entry, "load_env", lambda mode=None: seen.append(mode))
    monkeypatch.setattr(entry, "cmd_report", lambda args: 0)

    entry.main(["report", "--mode", "real"])
    entry.main(["report", "--mode", "mock"])
    assert seen == ["real", "mock"]


def _make_empty_flat_deploy(tmp_path: Path, monkeypatch) -> None:
    """合成 `.51` 那种扁平部署布局：`<root>/{app,zhuopin_platform,.env}`，`.env` 为空。

    刻意用 `ZP_ENV_FILE` 显式锚定，避免本测试受运行机器上真实 `.env` 的影响
    （否则开发机根 `.env` 里的 `U9C_*` 会让 real 那条用例永远绿）。
    """
    env_file = tmp_path / ".env"
    env_file.write_text("# 空：一个键都没有\n", encoding="utf-8")
    monkeypatch.setenv("ZP_ENV_FILE", str(env_file))
    for k in ("U9C_API_BASE", "U9C_USER_CODE", "U9C_ENT_CODE",
              "U9C_ORG_CODE", "U9C_CLIENT_ID", "U9C_CLIENT_SECRET"):
        monkeypatch.delenv(k, raising=False)
