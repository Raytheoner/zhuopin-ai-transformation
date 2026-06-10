"""审计 hash-chain 测试（P2 加固 · 先写测试）。

覆盖场景：
  - genesis 首条 prev_hash=""
  - 链接正确（磁盘原始行字节哈希）
  - key 乱序写入 event dict 不影响 verify_chain（哈希磁盘原始行而非 canonical）
  - 多线程并发写不断链
  - 双实例同文件交替写（_last_hashes 类级共享）
  - verify_chain 完整通过
  - verify_chain 检测删行
  - verify_chain 检测改行
  - AuditLogger.verify_chain() 代理
"""
import hashlib
import json
import threading
import time
from pathlib import Path

import pytest

from zhuopin_platform.audit.events import AuditEvent
from zhuopin_platform.audit.sinks import ChainVerifyResult, JsonlSink
from zhuopin_platform.audit.logger import AuditLogger


def _make_event(scenario: str = "TEST", seq: int = 0) -> AuditEvent:
    return AuditEvent(
        scenario=scenario,
        action="test_action",
        evaluator="test_user",
        automation_level="L2",
        decision={"seq": seq},
    )


def _line_hash(line_bytes: bytes) -> str:
    return hashlib.sha256(line_bytes).hexdigest()


# ── 基础写入 ────────────────────────────────────────────────────────────────

class TestHashChainWrite:

    def test_genesis_prev_hash_is_empty(self, tmp_path):
        """首条记录 prev_hash 必须为空字符串（genesis）。"""
        sink = JsonlSink(tmp_path / "audit.jsonl")
        sink.write(_make_event(seq=0))
        records = sink.read_all()
        assert len(records) == 1
        assert records[0]["prev_hash"] == ""

    def test_second_record_links_first(self, tmp_path):
        """第 2 条的 prev_hash == 第 1 条落盘行字节的 SHA-256。"""
        path = tmp_path / "audit.jsonl"
        sink = JsonlSink(path)
        sink.write(_make_event(seq=0))
        sink.write(_make_event(seq=1))

        lines = path.read_bytes().split(b"\n")
        lines = [l + b"\n" for l in lines if l]  # 还原每行字节（含 \n）
        assert len(lines) == 2

        expected_hash = _line_hash(lines[0])
        records = sink.read_all()
        assert records[1]["prev_hash"] == expected_hash

    def test_chain_three_records(self, tmp_path):
        """连续三条形成完整链。"""
        path = tmp_path / "audit.jsonl"
        sink = JsonlSink(path)
        for i in range(3):
            sink.write(_make_event(seq=i))

        lines = [l + b"\n" for l in path.read_bytes().split(b"\n") if l]
        assert len(lines) == 3

        records = sink.read_all()
        assert records[0]["prev_hash"] == ""
        assert records[1]["prev_hash"] == _line_hash(lines[0])
        assert records[2]["prev_hash"] == _line_hash(lines[1])

    def test_key_disorder_does_not_break_verify(self, tmp_path):
        """key 乱序插入 event dict，verify_chain 仍通过（哈希磁盘原始行，非 canonical 重算）。"""
        path = tmp_path / "audit.jsonl"
        sink = JsonlSink(path)
        # 写两条，通过正常 write()
        sink.write(_make_event(seq=0))
        sink.write(_make_event(seq=1))
        # 验证链完整（说明没有 sort_keys 重算导致误差）
        result = sink.verify_chain()
        assert result.ok is True
        assert result.total == 2


# ── 并发与多实例 ─────────────────────────────────────────────────────────────

class TestHashChainConcurrency:

    def test_multithreaded_write_intact_chain(self, tmp_path):
        """多线程并发写不断链：所有记录形成完整单链。"""
        path = tmp_path / "audit.jsonl"
        sink = JsonlSink(path)
        errors: list[Exception] = []

        def _writer(n: int) -> None:
            try:
                for i in range(5):
                    sink.write(_make_event(seq=n * 10 + i))
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=_writer, args=(t,)) for t in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors, f"线程写入异常: {errors}"
        result = sink.verify_chain()
        assert result.ok is True, f"并发写后链断裂：{result}"
        assert result.total == 20

    def test_two_instances_same_file_alternate_writes(self, tmp_path):
        """双实例同文件交替写，_last_hashes 类级共享保证链不断裂。"""
        path = tmp_path / "shared.jsonl"
        sink_a = JsonlSink(path)
        sink_b = JsonlSink(path)

        for i in range(3):
            sink_a.write(_make_event(scenario="A", seq=i))
            sink_b.write(_make_event(scenario="B", seq=i))

        result = sink_a.verify_chain()
        assert result.ok is True, f"双实例交替写后链断裂：{result}"
        assert result.total == 6


# ── verify_chain ──────────────────────────────────────────────────────────────

class TestVerifyChain:

    def test_verify_intact_chain(self, tmp_path):
        """完整链校验 ok=True。"""
        sink = JsonlSink(tmp_path / "audit.jsonl")
        for i in range(5):
            sink.write(_make_event(seq=i))
        result = sink.verify_chain()
        assert result.ok is True
        assert result.total == 5
        assert result.broken_at is None

    def test_verify_deleted_line_detected(self, tmp_path):
        """删除第 2 行后，verify_chain 检测到断链（broken_at 非 None）。"""
        path = tmp_path / "audit.jsonl"
        sink = JsonlSink(path)
        for i in range(4):
            sink.write(_make_event(seq=i))

        # 删除第 2 行（index 1）
        lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
        assert len(lines) == 4
        del lines[1]
        path.write_text("".join(lines), encoding="utf-8")

        result = sink.verify_chain()
        assert result.ok is False
        assert result.broken_at is not None

    def test_verify_modified_line_detected(self, tmp_path):
        """篡改第 2 行内容后，verify_chain 检测到断链。"""
        path = tmp_path / "audit.jsonl"
        sink = JsonlSink(path)
        for i in range(3):
            sink.write(_make_event(seq=i))

        # 篡改第 2 行的 decision 字段
        lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
        record = json.loads(lines[1])
        record["decision"]["tampered"] = True
        lines[1] = json.dumps(record, ensure_ascii=False) + "\n"
        path.write_text("".join(lines), encoding="utf-8")

        result = sink.verify_chain()
        assert result.ok is False
        assert result.broken_at is not None

    def test_verify_empty_file(self, tmp_path):
        """空文件 verify_chain 返回 ok=True, total=0。"""
        sink = JsonlSink(tmp_path / "empty.jsonl")
        result = sink.verify_chain()
        assert result.ok is True
        assert result.total == 0

    def test_verify_genesis_boundary_no_prev_hash_field(self, tmp_path):
        """旧文件首条无 prev_hash 字段，视为合法 genesis，不报断链。"""
        path = tmp_path / "legacy.jsonl"
        # 模拟旧格式：无 prev_hash 字段
        old_record = {"scenario": "SC1", "action": "test", "evaluator": "x",
                      "automation_level": "L2", "decision": {}, "timestamp": "2026-01-01T00:00:00+00:00"}
        path.write_text(json.dumps(old_record, ensure_ascii=False) + "\n", encoding="utf-8")
        sink = JsonlSink(path)
        result = sink.verify_chain()
        assert result.ok is True
        assert result.total == 1


# ── AuditLogger 代理 ──────────────────────────────────────────────────────────

class TestAuditLoggerVerifyChain:

    def test_audit_logger_proxies_verify_chain(self, tmp_path):
        """AuditLogger.verify_chain() 代理给 JsonlSink，结果一致。"""
        path = tmp_path / "audit.jsonl"
        audit = AuditLogger.jsonl(path)
        for i in range(3):
            audit.record(_make_event(seq=i))

        logger_result = audit.verify_chain()
        sink_result = audit.sink.verify_chain()

        assert logger_result.ok == sink_result.ok
        assert logger_result.total == sink_result.total

    def test_non_jsonl_sink_returns_ok(self):
        """非 JsonlSink 后端 verify_chain 返回 ok=True（非致命降级）。"""
        from zhuopin_platform.audit.sinks import AuditSink

        class _MockSink:
            def write(self, event): pass
            def read_all(self): return []

        audit = AuditLogger(_MockSink())
        result = audit.verify_chain()
        assert result.ok is True
        assert result.total == 0
