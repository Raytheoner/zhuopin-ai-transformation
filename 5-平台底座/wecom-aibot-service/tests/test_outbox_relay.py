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


def test_unreadable_outbox_alerts_every_round_and_is_never_read_as_empty(tmp_path):
    """🔴 通路断了要**每轮都响**（它不属于"结构性、等人处理"那一类，
    它是"东西现在坏了"），且绝不能被读成「没有待发」。"""
    missing = tmp_path / "gone.jsonl"
    conn, audit = _Conn(), _audit(tmp_path)
    alerts: list[str] = []
    alerted: set = set()

    for _ in range(2):
        outcome = asyncio.run(relay_once(
            connector=conn, audit=audit, paths=[missing], mapping=MAPPING,
            alert_send=alerts.append, alerted=alerted,
        ))

    assert outcome.scanned == 0 and len(outcome.unreadable) == 1
    assert len(alerts) == 2
    assert "不等于" in alerts[0]
    assert _actions(audit).count("outbox_relay_scan_failed") == 2


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
