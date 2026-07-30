import asyncio
from datetime import datetime, timezone
from pathlib import Path

import pytest

from zhuopin_platform.audit import AuditLogger

from aibot_service.liveness import (
    write_liveness,
    read_liveness,
    run_liveness_heartbeat,
)


def test_write_and_read_liveness_round_trip(tmp_path: Path) -> None:
    path = tmp_path / "aibot_liveness.json"
    now = datetime.now(timezone.utc)

    write_liveness(path, now)

    assert read_liveness(path) == now


def test_write_liveness_overwrites_not_appends(tmp_path: Path) -> None:
    """单文件覆写，非追加——体积恒定，无清理负担。"""
    path = tmp_path / "aibot_liveness.json"
    first = datetime.now(timezone.utc)
    second = first.replace(microsecond=0)

    write_liveness(path, first)
    write_liveness(path, second)

    assert read_liveness(path) == second
    # 文件只有一份 JSON 对象，不是逐行追加的 JSONL。
    import json
    json.loads(path.read_text(encoding="utf-8"))


def test_read_liveness_missing_file_returns_none(tmp_path: Path) -> None:
    assert read_liveness(tmp_path / "no_such.json") is None


def test_read_liveness_corrupt_json_returns_none(tmp_path: Path) -> None:
    path = tmp_path / "aibot_liveness.json"
    path.write_text("not json at all", encoding="utf-8")
    assert read_liveness(path) is None


def test_read_liveness_missing_field_returns_none(tmp_path: Path) -> None:
    path = tmp_path / "aibot_liveness.json"
    path.write_text('{"something_else": 1}', encoding="utf-8")
    assert read_liveness(path) is None


def test_read_liveness_malformed_timestamp_returns_none(tmp_path: Path) -> None:
    path = tmp_path / "aibot_liveness.json"
    path.write_text('{"alive_at": "不是一个时间戳"}', encoding="utf-8")
    assert read_liveness(path) is None


def test_heartbeat_writes_immediately_then_on_each_interval(tmp_path: Path) -> None:
    """立即写一次（新进程启动即确立基准），随后每个周期覆写一次；用假
    `_sleep` 在第 3 次调用后抛出以自然终止无限循环（模拟被取消）。"""
    path = tmp_path / "aibot_liveness.json"
    sleep_calls = []

    class _StopLoop(Exception):
        pass

    async def _fake_sleep(seconds):
        sleep_calls.append(seconds)
        if len(sleep_calls) >= 2:
            raise _StopLoop

    with pytest.raises(_StopLoop):
        asyncio.run(run_liveness_heartbeat(path, interval_seconds=300, _sleep=_fake_sleep))

    assert read_liveness(path) is not None
    assert sleep_calls == [300, 300]  # 每轮循环都按同一间隔 sleep


def test_heartbeat_write_failure_is_audited_and_loop_continues(tmp_path: Path, monkeypatch) -> None:
    """心跳写入失败（磁盘满/权限）——服务继续运行（循环不中断/不抛出），
    留痕一条审计事件。"""
    import aibot_service.liveness as liveness_mod

    path = tmp_path / "aibot_liveness.json"
    audit = AuditLogger.jsonl(tmp_path / "audit.jsonl")

    def _boom(path_, now_):
        raise OSError("模拟磁盘写入失败")

    monkeypatch.setattr(liveness_mod, "write_liveness", _boom)

    class _StopLoop(Exception):
        pass

    call_count = {"n": 0}

    async def _fake_sleep(seconds):
        call_count["n"] += 1
        if call_count["n"] >= 2:
            raise _StopLoop

    with pytest.raises(_StopLoop):
        asyncio.run(
            run_liveness_heartbeat(path, interval_seconds=1, audit=audit, _sleep=_fake_sleep)
        )

    actions = [r["action"] for r in audit.query_by(scenario="wecom-aibot")]
    assert actions.count("liveness_heartbeat_write_failed") == 2  # 每次失败都留痕，循环未中断


def test_heartbeat_does_not_pollute_audit_jsonl(tmp_path: Path) -> None:
    """审计 JSONL 未被心跳污染：心跳写的是独立文件，不追加进审计链，
    `verify_chain()` 应保持完整。"""
    liveness_path = tmp_path / "aibot_liveness.json"
    audit_path = tmp_path / "audit.jsonl"
    audit = AuditLogger.jsonl(audit_path)
    from zhuopin_platform.audit import AuditEvent

    audit.record(AuditEvent(
        scenario="wecom-aibot", action="connection_established", evaluator="system",
        automation_level="L1", decision={}, data_sources={},
    ))
    lines_before = audit_path.read_text(encoding="utf-8").splitlines()

    class _StopLoop(Exception):
        pass

    async def _fake_sleep(seconds):
        raise _StopLoop

    with pytest.raises(_StopLoop):
        asyncio.run(run_liveness_heartbeat(liveness_path, interval_seconds=300, _sleep=_fake_sleep))

    lines_after = audit_path.read_text(encoding="utf-8").splitlines()
    assert lines_after == lines_before  # 心跳运行期间审计文件行数/内容不变
    verification = audit.verify_chain()
    assert verification.ok is True
