"""长开服务基准日生命周期回归守（队列 §一 `#506`，OP-0908-U）。

## 这道守卫钉住的那件事

`serve` 是**长开服务**：`.51` 上 `Sc2WebServer` 是 AtStartup 常驻，一个进程活几周。
缺陷形态＝**在进程启动那一刻求值一次「今天」，然后把它冻进 app 对象**——此后每次
页面请求、每次 `POST /api/refresh` 都复用那个冻结值。2026-09-08 实测：PID 9168 自
08-27 起未重启，当天触发的一次真实全量重算返回 `period=2026-W34`（08-24~08-30），
而采购口径本周应为 `2026-W36`；**页面陈旧 12 天**。

🔑 **它不产生任何信号**：页面 200、重算 200、快照 0 秒、进程不崩、两套周号仍各自
自洽——每一项健康判据都恒真，**因为它们问的都不是「这是哪一周」**。故本形态只能由
「同一 app 对象跨日两次请求」这条正面判据钉住，健康检查钉不住。

## 为什么是两条断言、缺一不可

- ⒜ 缺省（不传 `--base`）时，同一 app 对象跨日必须给出**不同**期次 —— 缺陷的正面判据。
- ⒝ 显式传 `--base` 时，同一 app 对象跨日必须给出**相同**期次 —— 防修过头。只写 ⒜
  的话，下一个人会把显式基准日也一并改成动态，而 `--base` 存在的全部意义就是复现
  某一期（判例回灌、对数、历史重算都靠它）。
"""
from __future__ import annotations

import importlib.util
import sys
from datetime import date
from pathlib import Path

import pytest

from sc2 import webapp
from sc2.windows import build_windows

_SC2_ROOT = Path(__file__).resolve().parent.parent
_ENTRY = _SC2_ROOT / "run_sc2.py"
PREFIX = "/procurement/sc2"

#: 两个观测时刻：服务启动那天，与 12 天后的今天（复刻 2026-09-08 实测的跨度）。
_START_DAY = date(2026, 8, 27)
_LATER_DAY = date(2026, 9, 8)


@pytest.fixture(autouse=True)
def _isolated(tmp_path, monkeypatch):
    monkeypatch.setenv("SC2_REPORTS_DIR", str(tmp_path))
    monkeypatch.delenv("ZP_GATE_PASSWORD", raising=False)
    yield


@pytest.fixture()
def entry():
    """把 `run_sc2.py` 作为模块载入（它在场景根、不属任何包）。"""
    spec = importlib.util.spec_from_file_location("_run_sc2_base_date", _ENTRY)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    yield mod
    sys.modules.pop(spec.name, None)


@pytest.fixture()
def clock(monkeypatch):
    """把 `sc2.webapp` 眼里的「今天」置于可控之下，用来模拟长开服务跨日。

    只替换 `webapp` 模块命名空间里的 `date`——该模块对它的唯一用途就是 `date.today()`
    （类型标注因 `from __future__ import annotations` 不在运行期求值）。
    """
    class _Clock:
        now = _START_DAY

        @classmethod
        def today(cls):
            return cls.now

    monkeypatch.setattr(webapp, "date", _Clock)
    return _Clock


def _period_on(client, clock, day: date) -> str:
    """把「今天」拨到 `day`，向同一个 app 对象问一次期次。"""
    clock.now = day
    resp = client.get(f"{PREFIX}/api/report")
    assert resp.status_code == 200, resp.data
    return resp.get_json()["period"]


def _client_for(entry, argv: list[str]):
    """走 `cmd_serve` 同一条装配路径拿到 app —— 缺陷就在这条装配线上。"""
    args = entry.build_parser().parse_args(argv)
    app = entry._build_serve_app(args)
    app.config["TESTING"] = True
    return app.test_client()


def test_缺省基准日的长开服务跨日须给出不同期次(entry, clock):
    """⒜ 正面判据：同一 app 对象活过一天，期次必须跟着走。

    🔴 这条断言在修复前失败、修复后通过。失败形态＝两次问到的是同一个期次，
    即启动那天的那一期被冻住了。
    """
    client = _client_for(entry, ["serve"])

    first = _period_on(client, clock, _START_DAY)
    second = _period_on(client, clock, _LATER_DAY)

    assert first != second, (
        f"同一 app 对象跨日仍给出同一期次 {first} —— 基准日被冻在服务启动日")
    assert first == build_windows(_START_DAY).current.label()
    assert second == build_windows(_LATER_DAY).current.label()


def test_显式传base时同一app跨日仍固定(entry, clock):
    """⒝ 防修过头：`--base` 是「复现某一期」的开关，它必须不受今天影响。"""
    explicit = date(2026, 8, 19)
    client = _client_for(entry, ["serve", "--base", explicit.isoformat()])

    first = _period_on(client, clock, _START_DAY)
    second = _period_on(client, clock, _LATER_DAY)

    expected = build_windows(explicit).current.label()
    assert first == second == expected, (
        f"显式基准日 {explicit} 未被尊重：{first} / {second}，期望 {expected}")


def test_serve装配时不把今天冻进app对象(entry):
    """同一形态的结构判据：`serve` 不传 `--base` 时，装配阶段**不得**把一个具体
    日期传给 `create_app`——传了就等于在启动那一刻把「今天」求值并冻住。

    这条比上面两条更靠上游：它拦的是**写法**，跨日行为测试拦的是**后果**。
    """
    captured = {}
    real_create_app = webapp.create_app

    def _spy(**kwargs):
        captured.update(kwargs)
        return real_create_app(**kwargs)

    webapp.create_app = _spy
    try:
        args = entry.build_parser().parse_args(["serve"])
        entry._build_serve_app(args)
    finally:
        webapp.create_app = real_create_app

    assert captured["base_date"] is None, (
        f"serve 缺省时把 base_date={captured['base_date']!r} 冻进了 app 对象")
