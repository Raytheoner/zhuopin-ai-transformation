"""审计 hash-chain 测试（P2 加固 · 先写测试）。

覆盖场景：
  - genesis 首条 prev_hash=""
  - 链接正确（磁盘原始行字节哈希）
  - key 乱序写入 event dict 不影响 verify_chain（哈希磁盘原始行而非 canonical）
  - 多线程并发写不断链
  - 双实例同文件交替写（跨进程锁下现读磁盘，不依赖任何进程内缓存）
  - verify_chain 完整通过
  - verify_chain 检测删行
  - verify_chain 检测改行
  - AuditLogger.verify_chain() 代理
  - `#564`：跨进程互斥（多进程并发写不分叉）
  - `#564`：verify_chain 报出全部断点，不止第一个
  - `#564`：与哈希定义无关的旁证判据（相邻两行同一 prev_hash）
"""
import hashlib
import json
import multiprocessing
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


def _mp_writer_worker(path_str: str, tag: str, n: int) -> None:
    """独立 OS 进程里的写入 worker（供 multiprocessing.Process 调用）。

    与 `threading.Thread` 版本的关键区别：这是**全新的 Python 解释器**，
    `JsonlSink._locks`（类级 dict）与本进程完全无关——intra-process
    `threading.Lock` 对跨进程并发毫无作用，唯一能防分叉的只有
    `_CrossProcessFileLock`（文件级 OS 锁）。这就是 `#564` 要修的场景：
    实际生产环境至少 5 个独立 OS 进程（常驻 listener ＋ 若干计划任务）
    并发写同一份 `wecom_aibot_audit.jsonl`。
    """
    sink = JsonlSink(Path(path_str))
    for i in range(n):
        sink.write(_make_event(scenario=tag, seq=i))


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
        """双实例同文件交替写，链不断裂（每次写入在跨进程锁内现读磁盘末行，
        不依赖任何进程内缓存——`#564` 修复后两个实例甚至不需要共享任何
        Python 对象）。"""
        path = tmp_path / "shared.jsonl"
        sink_a = JsonlSink(path)
        sink_b = JsonlSink(path)

        for i in range(3):
            sink_a.write(_make_event(scenario="A", seq=i))
            sink_b.write(_make_event(scenario="B", seq=i))

        result = sink_a.verify_chain()
        assert result.ok is True, f"双实例交替写后链断裂：{result}"
        assert result.total == 6


# ── `#564` 跨进程互斥 ─────────────────────────────────────────────────────────

class TestCrossProcessMutex:

    def test_two_processes_concurrent_write_no_fork(self, tmp_path):
        """两个独立 OS 进程并发写同一审计文件，链不断、无 prev_hash 分叉。

        这是 `#564` 的核心回归用例：`threading.Lock`（进程内）救不了这个
        场景，因为两个 `multiprocessing.Process` 是完全独立的 Python 解释器，
        各自的 `JsonlSink._locks` 类级字典互不相干。只有跨进程文件锁
        `_CrossProcessFileLock` 能保证"现读磁盘末行 → 落盘新行"这段操作
        在全机范围内对同一文件串行化。
        """
        path = tmp_path / "audit.jsonl"
        n_per_proc = 25
        procs = [
            multiprocessing.Process(target=_mp_writer_worker, args=(str(path), tag, n_per_proc))
            for tag in ("PROC_A", "PROC_B")
        ]
        for p in procs:
            p.start()
        for p in procs:
            p.join(timeout=90)

        assert all(p.exitcode == 0 for p in procs), \
            f"子进程异常退出：{[p.exitcode for p in procs]}"

        sink = JsonlSink(path)
        result = sink.verify_chain()
        assert result.ok is True, f"跨进程并发写后链断裂或分叉：{result}"
        assert result.total == n_per_proc * 2
        assert result.breaks == []
        assert result.duplicate_prev_hash_pairs == []


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
        """旧文件首条无 prev_hash 字段，视为合法 genesis，不报断链。

        注意（A3）：genesis 豁免**仅对第 1 行**生效；第 2 行起缺 prev_hash 即判篡改
        （见 test_verify_stripped_prev_hash_attack_detected）。
        """
        path = tmp_path / "legacy.jsonl"
        # 模拟旧格式：无 prev_hash 字段
        old_record = {"scenario": "SC1", "action": "test", "evaluator": "x",
                      "automation_level": "L2", "decision": {}, "timestamp": "2026-01-01T00:00:00+00:00"}
        path.write_text(json.dumps(old_record, ensure_ascii=False) + "\n", encoding="utf-8")
        sink = JsonlSink(path)
        result = sink.verify_chain()
        assert result.ok is True
        assert result.total == 1

    def test_verify_stripped_prev_hash_attack_detected(self, tmp_path):
        """A3 修复：删光全文件 prev_hash 字段重写 → 不再被整链当 genesis 放行。

        攻击者删掉所有行的 prev_hash 字段（旧 genesis 兼容逻辑会把每行都当合法
        genesis → ok=True）。修复后豁免仅限第 1 行，第 2 行起缺字段即判断链。
        """
        path = tmp_path / "audit.jsonl"
        sink = JsonlSink(path)
        for i in range(3):
            sink.write(_make_event(seq=i))

        # 删除每一行的 prev_hash 字段后重写（模拟无痕篡改企图）
        lines = path.read_text(encoding="utf-8").splitlines()
        rewritten = []
        for line in lines:
            record = json.loads(line)
            record.pop("prev_hash", None)
            rewritten.append(json.dumps(record, ensure_ascii=False))
        path.write_text("\n".join(rewritten) + "\n", encoding="utf-8")

        result = sink.verify_chain()
        assert result.ok is False
        assert result.broken_at == 2   # 第 1 行豁免，第 2 行起缺字段即判篡改


# ── `#564` verify_chain 报全部断点 ─────────────────────────────────────────────

class TestVerifyChainAllBreaks:

    def test_reports_all_breaks_not_only_first(self, tmp_path):
        """多断点 fixture：verify_chain 报出**全部**断点，不是只报第一个。

        正本修复前的行为（`#564` 原始缺陷）：一撞见第一个 broken_at 就
        `return`，本用例构造的两个独立断点中只有第一个会被看到，第二个完全
        不可见——正是队列 `#564` 描述的「broken_at=685 就停手，后面 206 处
        全部被遮住」的缩小复现。

        构造方式：篡改第 2、4 行的内容（不碰它们自己的 `prev_hash` 字段）。
        哈希链的"断"体现在**下一行**——第 3 行的 `prev_hash` 仍指向"原始"第
        2 行的哈希，但磁盘上第 2 行已变；第 5 行同理指向第 4 行——所以两处
        独立断点分别落在第 3、5 行。🔴 重写文件必须显式 `newline=""`：
        `Path.write_text` 默认文本模式在 Windows 上会把 `\\n` 全部转写成
        `\\r\\n`（连未改动的行也会被换行符污染），那样会把每一行的原始字节
        都改掉，制造出与本测试意图无关的额外断点。
        """
        path = tmp_path / "audit.jsonl"
        sink = JsonlSink(path)
        for i in range(6):
            sink.write(_make_event(seq=i))

        lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
        assert len(lines) == 6

        def _tamper(line: str) -> str:
            record = json.loads(line)
            record["decision"] = {"tampered": True}
            return json.dumps(record, ensure_ascii=False) + "\n"

        # 篡改第 2 行（index 1）与第 4 行（index 3）——各自独立触发下一行的断点
        lines[1] = _tamper(lines[1])
        lines[3] = _tamper(lines[3])
        path.write_text("".join(lines), encoding="utf-8", newline="")

        result = sink.verify_chain()
        assert result.ok is False
        assert result.total == 6
        broken_line_numbers = {b["line"] for b in result.breaks}
        assert broken_line_numbers == {3, 5}, \
            f"应报出全部 2 个断点，实际：{result.breaks}"
        # 向后兼容镜像字段：broken_at/error 指向第一个断点
        assert result.broken_at == 3
        assert result.error == result.breaks[0]["error"]

    def test_break_does_not_cascade_to_every_following_line(self, tmp_path):
        """一处断点之后，链若重新自洽，不应把后面每一行都级联误判为断点。

        断点之后的哈希游标续接用"当前行原始字节的真实哈希"（而非"本应匹配
        的哈希"），所以断点后新写入、彼此自洽的记录不会被误伤。
        """
        path = tmp_path / "audit.jsonl"
        sink = JsonlSink(path)
        for i in range(3):
            sink.write(_make_event(seq=i))

        # 篡改第 2 行内容制造一个断点——断点会体现在第 3 行（它的 prev_hash
        # 仍指向"原始"第 2 行，而磁盘上第 2 行已变）；第 2 行自身的 prev_hash
        # 字段（指向第 1 行）未被触碰，依旧自洽，不会在第 2 行报断点。
        lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
        record = json.loads(lines[1])
        record["decision"] = {"tampered": True}
        lines[1] = json.dumps(record, ensure_ascii=False) + "\n"
        path.write_text("".join(lines), encoding="utf-8", newline="")

        # 断点之后继续正常写入（新记录的 prev_hash 会基于磁盘上第 3 行的真实
        # 字节重算——第 3 行本身内容未被篡改，只是它「声称」的上一条已经对不
        # 上——所以第 4 行起应重新自洽，不应被连累）
        for i in range(3, 6):
            sink.write(_make_event(seq=i))

        result = sink.verify_chain()
        assert result.ok is False
        assert result.total == 6
        # 只应有第 3 行这一个断点，第 2 行与后面 3 条新写入都不应被连累
        assert {b["line"] for b in result.breaks} == {3}


# ── `#564` 与哈希定义无关的旁证判据 ────────────────────────────────────────────

class TestDuplicatePrevHashPairs:

    def test_find_prev_hash_forks_detects_adjacent_duplicate(self, tmp_path):
        """相邻两行携带同一个 prev_hash 字面值 ⇒ 判定为一对分叉痕迹。

        直接手工构造两条记录、都把 `prev_hash` 写成同一个值（模拟两个独立
        写入方各自读到同一条"上一行"、各自算出同一个 prev_hash 后先后落盘）
        ——`find_prev_hash_forks` 全程不重算任何 SHA-256，只比较字段字面值。
        """
        path = tmp_path / "audit.jsonl"
        shared_prev = "deadbeef" * 8   # 任意固定值，不需要是真实哈希
        rec_a = {"scenario": "A", "action": "x", "evaluator": "u",
                  "automation_level": "L2", "decision": {}, "prev_hash": ""}
        rec_b = {"scenario": "B", "action": "x", "evaluator": "u",
                  "automation_level": "L2", "decision": {}, "prev_hash": shared_prev}
        rec_c = {"scenario": "C", "action": "x", "evaluator": "u",
                  "automation_level": "L2", "decision": {}, "prev_hash": shared_prev}
        path.write_text(
            "\n".join(json.dumps(r, ensure_ascii=False) for r in (rec_a, rec_b, rec_c)) + "\n",
            encoding="utf-8",
        )

        sink = JsonlSink(path)
        pairs = sink.find_prev_hash_forks()
        assert pairs == [(2, 3)]

    def test_find_prev_hash_forks_empty_when_no_duplicates(self, tmp_path):
        """正常写入（每行 prev_hash 各不相同）不应产生任何旁证分叉记录。"""
        path = tmp_path / "audit.jsonl"
        sink = JsonlSink(path)
        for i in range(5):
            sink.write(_make_event(seq=i))

        assert sink.find_prev_hash_forks() == []

    def test_verify_chain_surfaces_duplicate_pairs_and_fails_ok(self, tmp_path):
        """verify_chain() 的 duplicate_prev_hash_pairs 字段与 find_prev_hash_forks
        结果一致，且发现分叉旁证时 ok 必须为 False（即便哈希链本身恰好没有在
        同一处报出 broken_at）。"""
        path = tmp_path / "audit.jsonl"
        shared_prev = "cafebabe" * 8
        rec_a = {"scenario": "A", "action": "x", "evaluator": "u",
                  "automation_level": "L2", "decision": {}, "prev_hash": ""}
        rec_b = {"scenario": "B", "action": "x", "evaluator": "u",
                  "automation_level": "L2", "decision": {}, "prev_hash": shared_prev}
        rec_c = {"scenario": "C", "action": "x", "evaluator": "u",
                  "automation_level": "L2", "decision": {}, "prev_hash": shared_prev}
        path.write_text(
            "\n".join(json.dumps(r, ensure_ascii=False) for r in (rec_a, rec_b, rec_c)) + "\n",
            encoding="utf-8",
        )

        sink = JsonlSink(path)
        result = sink.verify_chain()
        assert result.duplicate_prev_hash_pairs == [(2, 3)]
        assert result.ok is False


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
