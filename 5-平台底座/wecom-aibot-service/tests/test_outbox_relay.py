"""outbox → aibot 通用中继（队列 `#394`）。

**判据分三档，刻意分开写**：

- **契约档**：路径解析 / 扫描 / 目标解析 —— 纯函数，逐条钉死跳过原因。
- **投递档**：`#394` 硬约束②「投递成功才置 `delivered:true`」的**正反两面**
  —— 成功要标上、失败与企微拒收都**不许**标。
- **结构档**：硬约束①「不得在中继里再抄一份 chatid」与 O-10「场景无关」
  —— 这两条不是用例能覆盖的，用**对源码本身的断言**钉住。
"""
from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

from zhuopin_platform.audit import AuditLogger
from zhuopin_platform.shared_tools.notifiers.wecom_aibot import AibotConnector

from aibot_service import outbox_relay
from aibot_service.outbox_relay import (
    CHANNEL_DIRECT,
    CHANNEL_GROUP,
    REASON_CORRUPT_LINE,
    REASON_DEPARTMENT_MISSING,
    REASON_DEPARTMENT_NOT_IN_MAPPING,
    REASON_DIRECT_USERID_MISSING,
    REASON_EMPTY_TEXT,
    REASON_GROUP_CHATID_NOT_CONFIGURED,
    REASON_UNKNOWN_CHANNEL,
    REASON_UNSUPPORTED_MSGTYPE,
    OutboxReadError,
    iter_pending,
    mark_delivered,
    relay_once,
    resolve_outbox_paths,
    resolve_target,
    run_outbox_relay,
)

from fakes import fake_client_factory

MAPPING = {
    "采购部": "CHATID_PURCHASE",
    "财务部": "CHATID_FINANCE",
    "占位部": "",  # 在表里但值为空——真实值尚未采集的占位状态
}


# ------------------------------------------------------------------ 辅助 --


def _record(**overrides) -> dict:
    """一条 SC2 群通报记录（字段与 `sc2/outbox.py::enqueue` 逐字对齐）。"""
    base = {
        "ts_utc": "2026-08-28T12:00:00+00:00",
        "ts_local": "2026-08-28T20:00:00+08:00",
        "scenario": "SC2",
        "period": "2026-W35",
        "channel": CHANNEL_GROUP,
        "department": "采购部",
        "msgtype": "markdown",
        "text": "## 采购周报 2026-W35",
        "delivered": False,
    }
    base.update(overrides)
    return base


def _write_outbox(path: Path, records: list[dict]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in records), encoding="utf-8"
    )
    return path


def _read_records(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


class _Conn:
    """最小 connector 替身——只需 `send_markdown` 协程（同 group_notify 的隐式契约）。"""

    def __init__(self, ack=None, fail_times: int = 0):
        self.sent: list[tuple[str, str]] = []
        self.ack = ack if ack is not None else {"errcode": 0}
        self.fail_times = fail_times

    async def send_markdown(self, target: str, content: str):
        if self.fail_times > 0:
            self.fail_times -= 1
            raise RuntimeError("模拟传输失败")
        self.sent.append((target, content))
        return self.ack


def _audit(tmp_path: Path) -> AuditLogger:
    return AuditLogger.jsonl(tmp_path / "audit.jsonl")


def _actions(audit: AuditLogger) -> list[str]:
    return [r["action"] for r in audit.query_by(scenario="wecom-aibot")]


# ============================================================ 契约档：路径 --


def test_resolve_outbox_paths_empty_means_relay_off():
    assert resolve_outbox_paths(None) == []
    assert resolve_outbox_paths("   ") == []


def test_resolve_outbox_paths_accepts_pathsep_and_newline_and_quotes(tmp_path):
    import os

    a, b = tmp_path / "a.jsonl", tmp_path / "b.jsonl"
    raw = f'"{a}"{os.pathsep}\n{b}'
    assert resolve_outbox_paths(raw) == [a, b]


def test_resolve_outbox_paths_dedupes_so_a_record_is_not_sent_twice(tmp_path):
    import os

    a = tmp_path / "a.jsonl"
    assert resolve_outbox_paths(f"{a}{os.pathsep}{a}") == [a]


def test_resolve_outbox_paths_expands_glob(tmp_path):
    (tmp_path / "sc2_group_outbox.jsonl").write_text("", encoding="utf-8")
    (tmp_path / "fi2_group_outbox.jsonl").write_text("", encoding="utf-8")
    resolved = resolve_outbox_paths(str(tmp_path / "*_group_outbox.jsonl"))
    assert {p.name for p in resolved} == {"sc2_group_outbox.jsonl", "fi2_group_outbox.jsonl"}


def test_glob_matching_nothing_is_kept_so_it_fails_loud_later(tmp_path):
    """🔴 配了却没匹配到的通配符 MUST NOT 在解析阶段静默蒸发。

    蒸发掉之后的症状（中继一条也不发）与"根本没配"完全一致，而后者已有
    专门的关闭提示——两件事必须能被区分开。
    """
    pattern = str(tmp_path / "nothing-here-*.jsonl")
    assert resolve_outbox_paths(pattern) == [Path(pattern)]


# ============================================================ 契约档：扫描 --


def test_iter_pending_skips_delivered_and_blank_lines(tmp_path):
    path = tmp_path / "outbox.jsonl"
    _write_outbox(path, [
        _record(period="W34", delivered=True),
        _record(period="W35"),
    ])
    path.write_text(path.read_text(encoding="utf-8") + "\n\n", encoding="utf-8")

    pending, corrupt = iter_pending(path)
    assert corrupt == []
    assert [e.period for e in pending] == ["W35"]
    assert pending[0].index == 1  # 物理行号保住了，回写要靠它


def test_iter_pending_reports_corrupt_lines_without_dropping_them(tmp_path):
    path = tmp_path / "outbox.jsonl"
    path.write_text(
        json.dumps(_record(), ensure_ascii=False) + "\n" + "{半行截断\n" + "[1,2,3]\n",
        encoding="utf-8",
    )
    pending, corrupt = iter_pending(path)
    assert len(pending) == 1
    assert [i for i, _ in corrupt] == [1, 2]      # 非法 JSON ＋ JSON 但不是对象
    assert "半行截断" in path.read_text(encoding="utf-8")   # 原样留在文件里


def test_missing_outbox_raises_instead_of_looking_like_nothing_to_send(tmp_path):
    """🔴 读不到 MUST NOT 等同于「没有待发」。

    `.51` → 笔记本那条文件通路断掉时的表象就是"文件不见了"；若在这里回落成
    空列表，中继会安静地一条不发，与一切正常长得一模一样（同 §四 #59 那次
    断供 5 个工作日无人察觉的形态）。
    """
    with pytest.raises(OutboxReadError):
        iter_pending(tmp_path / "never-existed.jsonl")


# ======================================================== 契约档：目标解析 --


def test_group_channel_resolves_chatid_from_authoritative_mapping():
    target, reason = resolve_target(_record(), MAPPING)
    assert reason == ""
    assert target.kind == "group"
    assert target.target == "CHATID_PURCHASE"


def test_direct_channel_uses_userid_verbatim():
    target, reason = resolve_target(
        _record(channel=CHANNEL_DIRECT, to_userid="YaoZuYi", department=None), MAPPING
    )
    assert reason == ""
    assert target.kind == "direct"
    assert target.target == "YaoZuYi"


@pytest.mark.parametrize("overrides,expected", [
    ({"department": "PMC部"}, REASON_DEPARTMENT_NOT_IN_MAPPING),
    ({"department": "IT部"}, REASON_DEPARTMENT_NOT_IN_MAPPING),   # 键名须是 `IT`，#387 同形
    ({"department": "占位部"}, REASON_GROUP_CHATID_NOT_CONFIGURED),
    ({"department": ""}, REASON_DEPARTMENT_MISSING),
    ({"department": None}, REASON_DEPARTMENT_MISSING),
    ({"channel": CHANNEL_DIRECT, "to_userid": ""}, REASON_DIRECT_USERID_MISSING),
    ({"channel": CHANNEL_DIRECT}, REASON_DIRECT_USERID_MISSING),
    ({"channel": "webhook"}, REASON_UNKNOWN_CHANNEL),
    ({"channel": None}, REASON_UNKNOWN_CHANNEL),
    ({"msgtype": "file"}, REASON_UNSUPPORTED_MSGTYPE),
    ({"text": ""}, REASON_EMPTY_TEXT),
    ({"text": "   "}, REASON_EMPTY_TEXT),
])
def test_undeliverable_records_are_named_not_guessed(overrides, expected):
    """每一种投不出去的情形都有**自己的**原因码——不合并、不猜目标。"""
    target, reason = resolve_target(_record(**overrides), MAPPING)
    assert target is None
    assert reason == expected


# ============================================================ 投递档：正面 --


def test_relay_delivers_and_marks_delivered(tmp_path):
    path = _write_outbox(tmp_path / "sc2.jsonl", [
        _record(),
        _record(channel=CHANNEL_DIRECT, to_userid="YaoZuYi", department=None),
    ])
    conn, audit = _Conn(), _audit(tmp_path)

    outcome = asyncio.run(relay_once(
        connector=conn, audit=audit, paths=[path], mapping=MAPPING
    ))

    assert outcome.delivered == 2
    assert outcome.pending_left == 0
    assert [t for t, _ in conn.sent] == ["CHATID_PURCHASE", "YaoZuYi"]

    records = _read_records(path)
    assert all(r["delivered"] for r in records)
    # 硬约束③：实际发到哪个 chatid 必须留在记录里，人眼反查时才有据可对。
    assert records[0]["delivered_to"] == "CHATID_PURCHASE"
    assert records[1]["delivered_to"] == "YaoZuYi"
    assert records[0]["delivered_ack"] == {"errcode": 0, "errmsg": None}
    # 原有字段一个不许丢
    assert records[0]["period"] == "2026-W35" and records[0]["scenario"] == "SC2"
    assert _actions(audit).count("outbox_relay_delivered") == 2


def test_second_round_does_not_resend_what_was_delivered(tmp_path):
    path = _write_outbox(tmp_path / "sc2.jsonl", [_record()])
    conn, audit = _Conn(), _audit(tmp_path)

    asyncio.run(relay_once(connector=conn, audit=audit, paths=[path], mapping=MAPPING))
    second = asyncio.run(relay_once(connector=conn, audit=audit, paths=[path], mapping=MAPPING))

    assert len(conn.sent) == 1
    assert second.scanned == 0


# ============================================================ 投递档：反面 --


def test_send_failure_leaves_record_pending_for_next_round(tmp_path):
    """硬约束②：失败留在 outbox 等下一轮——落盘即持久，关机只是延迟不是丢。"""
    path = _write_outbox(tmp_path / "sc2.jsonl", [_record()])
    conn, audit = _Conn(fail_times=1), _audit(tmp_path)

    first = asyncio.run(relay_once(connector=conn, audit=audit, paths=[path], mapping=MAPPING))
    assert first.delivered == 0 and len(first.failed) == 1
    assert _read_records(path)[0]["delivered"] is False
    assert "outbox_relay_send_failed" in _actions(audit)

    second = asyncio.run(relay_once(connector=conn, audit=audit, paths=[path], mapping=MAPPING))
    assert second.delivered == 1
    assert _read_records(path)[0]["delivered"] is True


def test_nonzero_errcode_must_not_be_marked_delivered(tmp_path):
    """🔴 企微回了非零 errcode ＝ 这条**没被接受**，绝不许置 `delivered:true`。

    判据复用 `delivery._assert_ack_accepted`（队列 #326 那条纵深防御），**不
    在本模块另写一套**——「一次发送算不算被接受」全仓只应有一个答案。这里
    走真实 `AibotConnector` ＋ 假客户端，把 SDK 不抛异常、只把帧回给调用方
    的那种情形也覆盖掉。
    """
    path = _write_outbox(tmp_path / "sc2.jsonl", [_record()])
    store: dict = {}
    connector = AibotConnector("bot", "secret", client_factory=fake_client_factory(store))
    asyncio.run(connector.connect())
    store["client"].send_ack_by_chatid["CHATID_PURCHASE"] = {
        "errcode": 40058, "errmsg": "invalid chatid"
    }
    audit = _audit(tmp_path)

    outcome = asyncio.run(relay_once(
        connector=connector, audit=audit, paths=[path], mapping=MAPPING
    ))

    assert outcome.delivered == 0 and len(outcome.failed) == 1
    assert _read_records(path)[0]["delivered"] is False
    failed = [r for r in audit.query_by(scenario="wecom-aibot")
              if r["action"] == "outbox_relay_send_failed"]
    assert failed[0]["decision"]["rejected_by_wecom"] is True


def test_undeliverable_record_stays_in_outbox_and_alerts_once(tmp_path):
    """结构性投不出去 ⇒ **留着**（`pending()` 下不去正是那条外部信号），
    但同一 `(文件, 行, 原因)` 只告警一次，免得 5 分钟一条把告警做成噪音。"""
    path = _write_outbox(tmp_path / "sc2.jsonl", [_record(department="PMC部")])
    conn, audit = _Conn(), _audit(tmp_path)
    alerts: list[str] = []
    alerted: set = set()

    for _ in range(3):
        outcome = asyncio.run(relay_once(
            connector=conn, audit=audit, paths=[path], mapping=MAPPING,
            alert_send=alerts.append, alerted=alerted,
        ))

    assert conn.sent == []
    assert outcome.skipped[0][1] == REASON_DEPARTMENT_NOT_IN_MAPPING
    assert _read_records(path)[0]["delivered"] is False       # 没有被丢弃
    assert len(alerts) == 1                                    # 三轮只响一次
    assert _actions(audit).count("outbox_relay_skipped") == 3  # 但审计每轮都留痕


def test_corrupt_line_is_skipped_and_alerted(tmp_path):
    path = tmp_path / "sc2.jsonl"
    path.write_text("{坏行\n" + json.dumps(_record(), ensure_ascii=False) + "\n", encoding="utf-8")
    conn, audit = _Conn(), _audit(tmp_path)
    alerts: list[str] = []

    outcome = asyncio.run(relay_once(
        connector=conn, audit=audit, paths=[path], mapping=MAPPING, alert_send=alerts.append
    ))

    assert outcome.delivered == 1                       # 坏行不影响同文件其余行
    assert outcome.skipped[0][1] == REASON_CORRUPT_LINE
    assert len(alerts) == 1
    assert path.read_text(encoding="utf-8").splitlines()[0] == "{坏行"


def test_unreadable_outbox_is_never_read_as_empty(tmp_path):
    """绝不能被读成「没有待发」——不论告警节流与否，扫描结果都必须诚实
    报告「这份 outbox 本轮读不到」。"""
    missing = tmp_path / "gone.jsonl"
    conn, audit = _Conn(), _audit(tmp_path)

    outcome = asyncio.run(relay_once(connector=conn, audit=audit, paths=[missing], mapping=MAPPING))

    assert outcome.scanned == 0 and len(outcome.unreadable) == 1


# ======================================== 决策点 9：读失败告警节流（`#556`）--


def test_unreadable_scan_audit_fires_every_round_regardless_of_throttle(tmp_path):
    """🔴 审计通道不受决策点 9 影响——`outbox_relay_scan_failed` 仍每轮都记
    （怕漏不怕多），只有「活人告警」这一条通道被节流。"""
    missing = tmp_path / "gone.jsonl"
    conn, audit = _Conn(), _audit(tmp_path)
    state: dict = {}

    for _ in range(3):
        asyncio.run(relay_once(
            connector=conn, audit=audit, paths=[missing], mapping=MAPPING,
            unreadable_state=state,
        ))

    assert _actions(audit).count("outbox_relay_scan_failed") == 3


def test_unreadable_scan_alerts_immediately_on_first_transition(tmp_path):
    """转入失败：不受阈值影响，立即响。"""
    missing = tmp_path / "gone.jsonl"
    conn, audit = _Conn(), _audit(tmp_path)
    alerts: list[str] = []

    outcome = asyncio.run(relay_once(
        connector=conn, audit=audit, paths=[missing], mapping=MAPPING,
        alert_send=alerts.append, unreadable_state={},
    ))

    assert outcome.scanned == 0 and len(outcome.unreadable) == 1
    assert len(alerts) == 1
    assert "不等于" in alerts[0]
    assert "outbox_relay_scan_unreadable_started" in _actions(audit)


def test_unreadable_scan_does_not_realert_within_threshold(tmp_path):
    """持续失败、未到复报点：不告警（但审计已由上一条用例钉死每轮照记）。"""
    import datetime as dt

    missing = tmp_path / "gone.jsonl"
    conn, audit = _Conn(), _audit(tmp_path)
    alerts: list[str] = []
    state: dict = {}
    t0 = dt.datetime(2026, 9, 12, 0, 0, tzinfo=dt.timezone.utc)

    asyncio.run(relay_once(
        connector=conn, audit=audit, paths=[missing], mapping=MAPPING,
        alert_send=alerts.append, unreadable_state=state, now=t0,
    ))
    asyncio.run(relay_once(
        connector=conn, audit=audit, paths=[missing], mapping=MAPPING,
        alert_send=alerts.append, unreadable_state=state,
        now=t0 + dt.timedelta(hours=5, minutes=59),
    ))

    assert len(alerts) == 1  # 只有首次转入那一次
    assert _actions(audit).count("outbox_relay_scan_failed") == 2


def test_unreadable_scan_realerts_after_threshold_with_duration_in_text(tmp_path):
    """到复报点：复报，文案含「已连续不可读 X 天 Y 小时」。"""
    import datetime as dt

    missing = tmp_path / "gone.jsonl"
    conn, audit = _Conn(), _audit(tmp_path)
    alerts: list[str] = []
    state: dict = {}
    t0 = dt.datetime(2026, 9, 12, 0, 0, tzinfo=dt.timezone.utc)

    asyncio.run(relay_once(
        connector=conn, audit=audit, paths=[missing], mapping=MAPPING,
        alert_send=alerts.append, unreadable_state=state, now=t0,
    ))
    asyncio.run(relay_once(
        connector=conn, audit=audit, paths=[missing], mapping=MAPPING,
        alert_send=alerts.append, unreadable_state=state,
        now=t0 + dt.timedelta(hours=6, seconds=1),
    ))

    assert len(alerts) == 2
    assert "已连续不可读" in alerts[1]
    assert "6 小时" in alerts[1] or "0 天 6 小时" in alerts[1]
    assert "outbox_relay_scan_unreadable_persisting" in _actions(audit)


def test_unreadable_scan_custom_threshold_is_respected(tmp_path):
    """阈值可调（`WECOM_AIBOT_OUTBOX_UNREADABLE_REALERT_SECONDS`）——直接
    传参验证，不依赖环境变量读取（那是 `run_aibot_service.py` 的活）。"""
    import datetime as dt

    missing = tmp_path / "gone.jsonl"
    conn, audit = _Conn(), _audit(tmp_path)
    alerts: list[str] = []
    state: dict = {}
    t0 = dt.datetime(2026, 9, 12, 0, 0, tzinfo=dt.timezone.utc)

    asyncio.run(relay_once(
        connector=conn, audit=audit, paths=[missing], mapping=MAPPING,
        alert_send=alerts.append, unreadable_state=state, now=t0,
        unreadable_realert_seconds=60,
    ))
    asyncio.run(relay_once(
        connector=conn, audit=audit, paths=[missing], mapping=MAPPING,
        alert_send=alerts.append, unreadable_state=state,
        now=t0 + dt.timedelta(seconds=61), unreadable_realert_seconds=60,
    ))

    assert len(alerts) == 2


def test_unreadable_scan_recovers_and_clears_state(tmp_path):
    """恢复：告警一次并**删除**该路径的状态条目——下次再失败按「转入」
    重新起算，不接着上一轮的复报节奏。"""
    path = tmp_path / "sc2.jsonl"
    conn, audit = _Conn(), _audit(tmp_path)
    alerts: list[str] = []
    state: dict = {}

    # 第一轮：文件不存在，转入失败。
    asyncio.run(relay_once(
        connector=conn, audit=audit, paths=[path], mapping=MAPPING,
        alert_send=alerts.append, unreadable_state=state,
    ))
    assert str(path) in state

    # 第二轮：文件出现了，读成功 ⇒ 恢复。
    _write_outbox(path, [_record()])
    asyncio.run(relay_once(
        connector=conn, audit=audit, paths=[path], mapping=MAPPING,
        alert_send=alerts.append, unreadable_state=state,
    ))

    assert state == {}
    assert len(alerts) == 2
    assert "已恢复" in alerts[1]
    assert "outbox_relay_scan_recovered" in _actions(audit)


def test_unreadable_scan_recovery_is_silent_when_path_never_failed(tmp_path):
    """从未失败过的路径读成功——没有多余的「恢复」告警。"""
    path = _write_outbox(tmp_path / "sc2.jsonl", [_record()])
    conn, audit = _Conn(), _audit(tmp_path)
    alerts: list[str] = []

    asyncio.run(relay_once(
        connector=conn, audit=audit, paths=[path], mapping=MAPPING,
        alert_send=alerts.append, unreadable_state={},
    ))

    assert "outbox_relay_scan_recovered" not in _actions(audit)
    assert not any("已恢复" in a for a in alerts)


def test_unreadable_state_round_trips_through_disk(tmp_path):
    from aibot_service.outbox_relay import load_unreadable_state, save_unreadable_state

    path = tmp_path / "sub" / "outbox_relay_unreadable_state.json"
    state = {"a.jsonl": {"first_failed_at": "2026-09-12T00:00:00+00:00",
                          "last_alert_at": "2026-09-12T00:00:00+00:00"}}

    save_unreadable_state(path, state)

    assert load_unreadable_state(path) == state


def test_unreadable_state_missing_or_corrupt_file_falls_back_to_empty(tmp_path):
    from aibot_service.outbox_relay import load_unreadable_state

    assert load_unreadable_state(tmp_path / "never-existed.json") == {}

    corrupt = tmp_path / "corrupt.json"
    corrupt.write_text("{not json", encoding="utf-8")
    assert load_unreadable_state(corrupt) == {}

    not_a_dict = tmp_path / "list.json"
    not_a_dict.write_text("[1, 2, 3]", encoding="utf-8")
    assert load_unreadable_state(not_a_dict) == {}


def test_list_persistently_unreadable_is_a_pure_function_over_the_state_dict():
    """决策点 9.3（可见化）：`list_persistently_unreadable` 只读状态字典、不
    做任何 I/O——给未来接进值周巡检/sweep 的调用方一个可独立测试的判定。
    范式同队列 `#312` 陈化催办：按状态文件里的时间戳判「多久没好」。"""
    import datetime as dt

    from aibot_service.outbox_relay import list_persistently_unreadable

    now = dt.datetime(2026, 9, 12, 12, 0, tzinfo=dt.timezone.utc)
    state = {
        "old.jsonl": {"first_failed_at": (now - dt.timedelta(hours=30)).isoformat()},
        "recent.jsonl": {"first_failed_at": (now - dt.timedelta(hours=2)).isoformat()},
        "malformed.jsonl": {"first_failed_at": "not-a-date"},
        "not-a-dict": "oops",
    }

    result = list_persistently_unreadable(state, now, threshold_seconds=86400)

    assert [key for key, _, _ in result] == ["old.jsonl"]
    assert result[0][2] == pytest.approx(30.0, abs=0.01)


def test_unreadable_state_survives_process_restart_simulation(tmp_path):
    """🔴 本条是决策点 9 要修的核心缺陷本体：跨进程重启持久化。

    模拟真实场景——服务起来、读失败、把状态落盘（`save_unreadable_state`）；
    进程"重启"（本测试里就是丢掉内存里的 dict，从磁盘重新 `load_unreadable_
    state`）；重启后立刻又扫到同一个失败，**不得**把它重新判成"首次转入"
    再响一次（那正是 11 天里 20 余次重启从未让节流生效的根因）。
    """
    import datetime as dt

    from aibot_service.outbox_relay import load_unreadable_state, save_unreadable_state

    missing = tmp_path / "gone.jsonl"
    state_path = tmp_path / "unreadable_state.json"
    conn, audit = _Conn(), _audit(tmp_path)
    alerts: list[str] = []
    t0 = dt.datetime(2026, 9, 12, 0, 0, tzinfo=dt.timezone.utc)

    # 第一次"进程生命周期"：转入失败，落盘。
    state = {}
    asyncio.run(relay_once(
        connector=conn, audit=audit, paths=[missing], mapping=MAPPING,
        alert_send=alerts.append, unreadable_state=state, now=t0,
    ))
    save_unreadable_state(state_path, state)
    assert len(alerts) == 1

    # "重启"：内存状态丢弃，从磁盘重新加载——10 分钟后立刻再扫一次。
    reloaded_state = load_unreadable_state(state_path)
    asyncio.run(relay_once(
        connector=conn, audit=audit, paths=[missing], mapping=MAPPING,
        alert_send=alerts.append, unreadable_state=reloaded_state,
        now=t0 + dt.timedelta(minutes=10),
    ))

    assert len(alerts) == 1  # 没有因为"重启"而被误判成首次转入、再响一次
    assert _actions(audit).count("outbox_relay_scan_failed") == 2  # 审计仍每轮照记


def test_one_unreadable_outbox_does_not_block_the_others(tmp_path):
    good = _write_outbox(tmp_path / "sc2.jsonl", [_record()])
    conn, audit = _Conn(), _audit(tmp_path)

    outcome = asyncio.run(relay_once(
        connector=conn, audit=audit, paths=[tmp_path / "gone.jsonl", good], mapping=MAPPING
    ))

    assert outcome.delivered == 1 and len(outcome.unreadable) == 1


# ================================================== 投递档：与写侧的并发 --


def test_line_appended_by_the_writer_mid_round_is_not_lost(tmp_path):
    """🔴 本条是整个中继最容易悄悄丢东西的地方。

    写侧（`.51` 上的 SC2/FI2）随时可能在本轮"读"与"写"之间往同一文件追加
    新行。回写若整份覆盖，那条刚落盘的消息就没了——**而且没有任何信号**。
    """
    path = _write_outbox(tmp_path / "sc2.jsonl", [_record(period="W35")])
    late = _record(period="W36")
    audit = _audit(tmp_path)

    class _AppendingConn(_Conn):
        async def send_markdown(self, target, content):
            # 模拟：正在发这一条的同时，写侧追加了下一期
            with path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(late, ensure_ascii=False) + "\n")
            return await super().send_markdown(target, content)

    conn = _AppendingConn()
    outcome = asyncio.run(relay_once(
        connector=conn, audit=audit, paths=[path], mapping=MAPPING
    ))

    records = _read_records(path)
    assert outcome.delivered == 1
    assert len(records) == 2                       # 后追加的那条还在
    assert records[0]["delivered"] is True
    assert records[1]["period"] == "W36" and records[1]["delivered"] is False


def test_mutated_line_is_not_overwritten_and_is_reported_loudly(tmp_path):
    """位置校验不过 ⇒ 记 `mark_failed` ＋ 告警，**绝不强行覆盖**。

    强行覆盖会把写侧刚改过的内容抹掉；假装标成功则会让这条消息此后再也不会
    被重发 —— 两者都是静默的丢。选择"重发一次、并且说出来"。
    """
    path = _write_outbox(tmp_path / "sc2.jsonl", [_record(period="W35")])
    audit = _audit(tmp_path)
    alerts: list[str] = []

    class _MutatingConn(_Conn):
        async def send_markdown(self, target, content):
            _write_outbox(path, [_record(period="W35", text="正文被写侧改过了")])
            return await super().send_markdown(target, content)

    outcome = asyncio.run(relay_once(
        connector=_MutatingConn(), audit=audit, paths=[path], mapping=MAPPING,
        alert_send=alerts.append,
    ))

    assert outcome.delivered == 0 and len(outcome.mark_failed) == 1
    assert _read_records(path)[0]["text"] == "正文被写侧改过了"   # 没被抹掉
    assert "outbox_relay_mark_failed" in _actions(audit)
    assert len(alerts) == 1 and "重发" in alerts[0]


def test_mark_delivered_refuses_when_line_no_longer_matches(tmp_path):
    path = _write_outbox(tmp_path / "sc2.jsonl", [_record()])
    entry = iter_pending(path)[0][0]
    _write_outbox(path, [_record(text="换了")])

    assert mark_delivered(entry, {**entry.record, "delivered": True}) is False
    assert _read_records(path)[0]["text"] == "换了"


def test_mark_delivered_leaves_no_temp_file_behind(tmp_path):
    path = _write_outbox(tmp_path / "sc2.jsonl", [_record()])
    entry = iter_pending(path)[0][0]

    assert mark_delivered(entry, {**entry.record, "delivered": True}) is True
    assert list(tmp_path.glob("*.relaytmp")) == []


# ================================================ 结构档：O-10「合建一份」--


def test_fi2_records_take_the_exact_same_path_as_sc2(tmp_path):
    """🔴 O-10 的证据：合建之后**根本不需要按 scenario 分流**。

    同一份中继、同一段代码，SC2 与 FI2 的记录走的是逐字节相同的路径；
    `scenario` 只被留痕消费。⇒ 新场景接入不改中继一行代码。
    """
    sc2 = _write_outbox(tmp_path / "sc2.jsonl", [_record(scenario="SC2", department="采购部")])
    fi2 = _write_outbox(tmp_path / "fi2.jsonl", [
        _record(scenario="FI2", department="财务部", period="2026-08-28",
                text="今日三单待核对明细表已拉取完成"),
    ])
    conn, audit = _Conn(), _audit(tmp_path)

    outcome = asyncio.run(relay_once(
        connector=conn, audit=audit, paths=[sc2, fi2], mapping=MAPPING
    ))

    assert outcome.delivered == 2
    assert [t for t, _ in conn.sent] == ["CHATID_PURCHASE", "CHATID_FINANCE"]
    scenarios = {r["decision"]["scenario"] for r in audit.query_by(scenario="wecom-aibot")
                 if r["action"] == "outbox_relay_delivered"}
    assert scenarios == {"SC2", "FI2"}


def test_relay_source_contains_no_chatid_literal_and_no_scenario_branch():
    """🔴 硬约束①「不得在中继里再抄一份 chatid」是**结构性**的，用例覆盖不到。

    钉两条：⑴ 源码里不得出现任何真实 chatid 形态的字面量；⑵ 必须 import 那张
    权威 yaml 的加载函数。第二条防的是「把 chatid 从别处传进来、绕开映射表」。

    顺带把 O-10 也钉住：源码里不得出现按 `scenario` 取值分支的判断——一旦有人
    写了 `if scenario == "SC2"`，"合建一份"就名存实亡了。
    """
    source = Path(outbox_relay.__file__).read_text(encoding="utf-8")
    assert "wrvDL_" not in source, "中继里出现了真实 chatid 字面量——第二份真相"
    assert "load_department_group_chatid_mapping" in source
    for forbidden in ('== "SC2"', "== 'SC2'", '== "FI2"', "== 'FI2'"):
        assert forbidden not in source, f"出现按场景分支的判断：{forbidden}"


def test_relay_source_contains_no_network_self_check():
    """🔴 决策点 9.1 已否掉的方案：中继不得自己判断"现在是不是在 LAN 里"。

    `#556` 2026-09-11 实测证伪了本机唯一可用的量具（`Test-NetConnection` 在
    Clash/Mihomo TUN 环境下对任意 `IP:port` 恒真、零信息量）——复用它会把
    「真正 off-LAN」读成「在网」，把一个本该响的真故障静默掉，比现在的
    「太吵」更危险。此断言钉住"有人哪天悄悄加回来"这一类回归。
    """
    source = Path(outbox_relay.__file__).read_text(encoding="utf-8")
    for forbidden in (
        "import socket", "socket.socket(", "socket.create_connection",
        "Test-NetConnection", "TcpTestSucceeded", "subprocess.run",
    ):
        assert forbidden not in source, f"中继里出现了网络自检代码：{forbidden}"


# ==================================================== 常驻任务：循环与取消 --


def test_relay_loop_runs_immediately_then_sleeps(tmp_path):
    """进程刚起来时先把关机期间的积压送出去，不必等满一个周期。"""
    path = _write_outbox(tmp_path / "sc2.jsonl", [_record()])
    conn, audit = _Conn(), _audit(tmp_path)
    sleeps: list[float] = []

    async def _fake_sleep(seconds):
        sleeps.append(seconds)
        raise asyncio.CancelledError

    with pytest.raises(asyncio.CancelledError):
        asyncio.run(run_outbox_relay(
            connector=conn, audit=audit, paths=[path], mapping=MAPPING,
            interval_seconds=42, _sleep=_fake_sleep,
        ))

    assert len(conn.sent) == 1
    assert sleeps == [42]


def test_relay_loop_persists_unreadable_state_across_rounds_and_restarts(tmp_path):
    """`run_outbox_relay` 是真正落盘持久化发生的地方——`relay_once` 本身不
    碰磁盘。第二轮（模拟"重启后又跑了一轮"）从磁盘重新加载状态，不应该
    把仍在失败的路径重新判成"首次转入"再告警一次。"""
    missing = tmp_path / "gone.jsonl"
    state_path = tmp_path / "state.json"
    conn, audit = _Conn(), _audit(tmp_path)
    alerts: list[str] = []
    rounds = {"n": 0}

    async def _fake_sleep(seconds):
        rounds["n"] += 1
        if rounds["n"] >= 1:
            raise asyncio.CancelledError

    with pytest.raises(asyncio.CancelledError):
        asyncio.run(run_outbox_relay(
            connector=conn, audit=audit, paths=[missing], mapping=MAPPING,
            interval_seconds=1, _sleep=_fake_sleep, alert_send=alerts.append,
            unreadable_state_path=state_path,
        ))

    assert len(alerts) == 1
    saved = outbox_relay.load_unreadable_state(state_path)
    assert str(missing) in saved

    # "重启"：新的一次 run_outbox_relay 调用，从磁盘加载已有状态。
    rounds["n"] = 0
    with pytest.raises(asyncio.CancelledError):
        asyncio.run(run_outbox_relay(
            connector=conn, audit=audit, paths=[missing], mapping=MAPPING,
            interval_seconds=1, _sleep=_fake_sleep, alert_send=alerts.append,
            unreadable_state_path=state_path,
        ))

    assert len(alerts) == 1  # 没有因"重启"重新判成首次转入


def test_relay_loop_survives_a_bad_round(tmp_path):
    """中继是旁路——它自己炸了绝不能把常驻服务的主链路带下水。"""
    audit = _audit(tmp_path)
    rounds = {"n": 0}

    class _Exploding:
        async def send_markdown(self, target, content):  # pragma: no cover - 到不了
            raise AssertionError

    async def _fake_sleep(seconds):
        rounds["n"] += 1
        if rounds["n"] >= 2:
            raise asyncio.CancelledError

    def _boom(**kwargs):
        raise RuntimeError("本轮整体炸了")

    original = outbox_relay.relay_once
    outbox_relay.relay_once = _boom
    try:
        with pytest.raises(asyncio.CancelledError):
            asyncio.run(run_outbox_relay(
                connector=_Exploding(), audit=audit, paths=[], mapping=MAPPING,
                interval_seconds=1, _sleep=_fake_sleep,
            ))
    finally:
        outbox_relay.relay_once = original

    assert rounds["n"] == 2                                     # 炸了照样进下一轮
    assert _actions(audit).count("outbox_relay_round_failed") == 2
