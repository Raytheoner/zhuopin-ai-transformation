# -*- coding: utf-8 -*-
"""落库 sweep 第 18 类常驻告警 · outbox → aibot 中继「持续不可读 > 24 小时」
可见化（队列 §一 `#556` ⑨3 残余，design 9.3 第 ③ 处）单测。

同族既有先例（第 16 类 `test_工具-落库sweep-未并入分支告警.py`、第 17 类
`test_工具-落库sweep-审计文件分叉写入.py`）：每个常驻告警类独立成一份测试
文件，`sweep` 模块通过 `importlib.util.spec_from_file_location` 加载。

🔴 判据正本在 `aibot_service/outbox_relay.py::list_persistently_unreadable`
（子进程调用）——本文件**不**在 sweep 侧另断言一份「距今多久算持续」，只
断言 sweep 把纯函数的结果原样排进了清单／状态文件；判据本身的边界由
`5-平台底座/wecom-aibot-service/tests/test_outbox_relay.py` 钉住。
"""
from __future__ import annotations

import importlib.util
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

_HERE = Path(__file__).resolve().parent
_SWEEP_SPEC = importlib.util.spec_from_file_location(
    "commit_sweep_for_outbox_relay_unreadable", _HERE / "工具-落库sweep.py"
)
sweep = importlib.util.module_from_spec(_SWEEP_SPEC)
_SWEEP_SPEC.loader.exec_module(sweep)

REAL_REPO_ROOT = _HERE.parent
REAL_SERVICE_DIR = REAL_REPO_ROOT / sweep.OUTBOX_RELAY_SERVICE_DIR_REL
SAMPLE_PATH = r"\\192.168.100.51\C$\sc2\app\reports\sc2_group_outbox.jsonl"


@pytest.fixture()
def repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """最小仓库夹具：不放 `.env`，`_load_webhook_url` 读不到真实 webhook——
    本类全部用例走「只留痕、不真发」路径。子进程 cwd 指向**真实**服务目录
    （夹具里没有 `aibot_service` 包），这样跑的就是正本纯函数、不是桩。"""
    (tmp_path / "reports").mkdir()
    monkeypatch.setattr(sweep, "_outbox_relay_service_dir", lambda _root: REAL_SERVICE_DIR)
    return tmp_path


def _write_state(repo: Path, entries: dict[str, float]) -> Path:
    """`entries`＝{路径: 已不可读小时数}，按中继 `save_unreadable_state` 的形状落盘。"""
    now = datetime.now(timezone.utc)
    state = {
        path: {
            "first_failed_at": (now - timedelta(hours=hours)).isoformat(),
            "last_alert_at": now.isoformat(),
        }
        for path, hours in entries.items()
    }
    target = repo / sweep.OUTBOX_RELAY_UNREADABLE_STATE_REL
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    return target


def _sweep_state(repo: Path) -> dict:
    path = repo / sweep.OUTBOX_RELAY_UNREADABLE_SWEEP_STATE_REL
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


# ---------------------------------------------------------------- 落点对齐 --


def test_状态文件落点与aibot_service正本一致():
    """🔴 sweep 侧的字面副本必须与 `repo_paths.OUTBOX_RELAY_UNREADABLE_STATE_RELATIVE_PATH`
    相等——两边一漂，本类就会永远读一个不存在的文件、永远「零命中」。"""
    sys.path.insert(0, str(REAL_SERVICE_DIR))
    try:
        from aibot_service import repo_paths  # noqa: WPS433 —— 只在单测里 import，sweep 本体零依赖
    finally:
        sys.path.remove(str(REAL_SERVICE_DIR))
    assert Path(sweep.OUTBOX_RELAY_UNREADABLE_STATE_REL) == repo_paths.OUTBOX_RELAY_UNREADABLE_STATE_RELATIVE_PATH


def test_子进程片段不含判定逻辑_只调正本纯函数():
    """判据只此一份：子进程里只能出现「调用 list_persistently_unreadable」，
    不得出现任何比较时长的算术。"""
    snippet = sweep.OUTBOX_RELAY_JUDGE_SNIPPET
    assert "list_persistently_unreadable" in snippet
    assert "threshold_seconds" in snippet
    for forbidden in ("total_seconds", ">=", "<=", "3600", "86400"):
        assert forbidden not in snippet, f"子进程片段不得自带判定：{forbidden!r}"


# ---------------------------------------------------------------- 主路径 --


def test_状态文件不存在时零命中且回显(repo: Path):
    log: list[str] = []
    sweep._check_outbox_relay_unreadable_visibility(repo, log)
    text = "\n".join(log)
    assert "第 18 类" in text and "不存在" in text
    assert _sweep_state(repo) == {}
    assert not (repo / sweep.OUTBOX_RELAY_UNREADABLE_UNAVAILABLE_STATE_REL).exists() or \
        json.loads((repo / sweep.OUTBOX_RELAY_UNREADABLE_UNAVAILABLE_STATE_REL).read_text(encoding="utf-8")) == {}


def test_持续不可读超过24小时的路径点名进清单(repo: Path):
    _write_state(repo, {SAMPLE_PATH: 30.0})
    log: list[str] = []
    sweep._check_outbox_relay_unreadable_visibility(repo, log)
    text = "\n".join(log)
    assert "1 条已持续不可读" in text
    assert SAMPLE_PATH in text
    assert "1 天 6 小时" in text
    assert SAMPLE_PATH in _sweep_state(repo)


def test_不足24小时的读失败不进清单(repo: Path):
    """短于一天的由中继自己的「转入即报／6 小时复报」覆盖，本类不重复它。"""
    _write_state(repo, {SAMPLE_PATH: 5.0})
    log: list[str] = []
    sweep._check_outbox_relay_unreadable_visibility(repo, log)
    text = "\n".join(log)
    assert "记 1 条读失败路径，其中 0 条已持续不可读" in text
    assert _sweep_state(repo) == {}


def test_多路径只点名超阈的那些(repo: Path):
    _write_state(repo, {SAMPLE_PATH: 72.0, r"\\host\share\other_outbox.jsonl": 1.0})
    log: list[str] = []
    sweep._check_outbox_relay_unreadable_visibility(repo, log)
    state = _sweep_state(repo)
    assert set(state) == {SAMPLE_PATH}
    assert "记 2 条读失败路径，其中 1 条已持续不可读" in "\n".join(log)


def test_中继删掉状态条目后告警自动解除(repo: Path):
    """🔴 同第 4/6/7/9/10/11/14/17 类既有纪律：告警必须能被「已恢复」自动关掉。
    恢复的信号＝中继 `_handle_recovered_scan` 删掉该路径条目（状态文件变空）。"""
    target = _write_state(repo, {SAMPLE_PATH: 48.0})
    log: list[str] = []
    sweep._check_outbox_relay_unreadable_visibility(repo, log)
    assert SAMPLE_PATH in _sweep_state(repo), "第一轮应留下告警状态"

    target.write_text("{}", encoding="utf-8")
    log2: list[str] = []
    sweep._check_outbox_relay_unreadable_visibility(repo, log2)
    assert _sweep_state(repo) == {}
    assert "解除" in "\n".join(log2)


def test_用状态文件时间戳判_不用mtime(repo: Path):
    """🔴 派单件硬判据：mtime 会被任何一次写盘刷新。把一个「刚写盘」但
    `first_failed_at` 已是 3 天前的状态文件交给本类，必须仍判为持续不可读。"""
    target = _write_state(repo, {SAMPLE_PATH: 72.0})
    import os, time
    os.utime(target, (time.time(), time.time()))  # mtime＝现在
    log: list[str] = []
    sweep._check_outbox_relay_unreadable_visibility(repo, log)
    assert SAMPLE_PATH in _sweep_state(repo)
    assert "3 天 0 小时" in "\n".join(log)


# ---------------------------------------------------------------- 退化路径 --


def test_状态文件损坏时判据不可用_不判为读得通(repo: Path):
    target = repo / sweep.OUTBOX_RELAY_UNREADABLE_STATE_REL
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("{not json", encoding="utf-8")
    log: list[str] = []
    sweep._check_outbox_relay_unreadable_visibility(repo, log)
    text = "\n".join(log)
    assert "判据不可用" in text
    unavailable = json.loads(
        (repo / sweep.OUTBOX_RELAY_UNREADABLE_UNAVAILABLE_STATE_REL).read_text(encoding="utf-8"))
    assert sweep.OUTBOX_RELAY_UNREADABLE_UNAVAILABLE_KEY in unavailable
    assert _sweep_state(repo) == {}


def test_服务目录不在时判据不可用(repo: Path, monkeypatch: pytest.MonkeyPatch):
    _write_state(repo, {SAMPLE_PATH: 48.0})
    monkeypatch.setattr(sweep, "_outbox_relay_service_dir", lambda _root: repo / "no-such-service")
    log: list[str] = []
    sweep._check_outbox_relay_unreadable_visibility(repo, log)
    assert "判据不可用" in "\n".join(log)
    assert _sweep_state(repo) == {}


def test_判据恢复后不可用告警自动解除(repo: Path, monkeypatch: pytest.MonkeyPatch):
    _write_state(repo, {SAMPLE_PATH: 48.0})
    monkeypatch.setattr(sweep, "_outbox_relay_service_dir", lambda _root: repo / "no-such-service")
    sweep._check_outbox_relay_unreadable_visibility(repo, [])
    monkeypatch.setattr(sweep, "_outbox_relay_service_dir", lambda _root: REAL_SERVICE_DIR)
    log: list[str] = []
    sweep._check_outbox_relay_unreadable_visibility(repo, log)
    unavailable = json.loads(
        (repo / sweep.OUTBOX_RELAY_UNREADABLE_UNAVAILABLE_STATE_REL).read_text(encoding="utf-8"))
    assert unavailable == {}
    assert SAMPLE_PATH in _sweep_state(repo)


# ---------------------------------------------------------------- dry-run --


def test_dry_run只回显不写状态不推送(repo: Path):
    _write_state(repo, {SAMPLE_PATH: 48.0})
    log: list[str] = []
    sweep._check_outbox_relay_unreadable_visibility(repo, log, dry_run=True)
    text = "\n".join(log)
    assert "dry-run" in text and "第 18 类常驻告警" in text
    assert not (repo / sweep.OUTBOX_RELAY_UNREADABLE_SWEEP_STATE_REL).exists()
    assert not (repo / sweep.OUTBOX_RELAY_UNREADABLE_UNAVAILABLE_STATE_REL).exists()


def test_零命中也回显(repo: Path):
    """🔴 一个从来不出声的机制，没人能判断它是「没问题」还是「没跑」。"""
    _write_state(repo, {})
    log: list[str] = []
    sweep._check_outbox_relay_unreadable_visibility(repo, log)
    assert log and "记 0 条读失败路径" in "\n".join(log)


# ---------------------------------------------------------------- 告警正文 --


def test_告警正文不含traceback只含路径与时长():
    """`#73`／`#282` 教训：机制告警正文不得是 Python traceback。"""
    text = sweep._render_outbox_relay_unreadable_alert([(SAMPLE_PATH, "2026-09-12T19:27:15+00:00", 30.5)])
    assert "Traceback" not in text
    assert SAMPLE_PATH in text and "1 天 6 小时" in text
    assert "读不到 ≠ 没有待发消息" in text
    assert "check_outbox_relay.py" in text
