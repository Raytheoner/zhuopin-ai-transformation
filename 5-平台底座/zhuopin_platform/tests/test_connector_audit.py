"""连接器审计接入层测试（第 4 组，D2/D5）。

合规要点验证：
  · D2: 连接器只写「轻量访问痕迹」（数据源/动作/目标/时间），不写场景级合规决策记录；
        合规 AuditEvent 由场景层负责。
  · D2: req/resp 全文 debug 日志默认关闭、与合规 audit 物理分开。
  · D5: 审计接入可注入临时 sink，便于测试、避免污染真实日志。
"""
import json
from pathlib import Path

from zhuopin_platform.audit.sinks import JsonlSink
from zhuopin_platform.shared_tools.connector_audit import (
    AccessTrace,
    ConnectorAudit,
    DebugLog,
)


# ── D5：可注入 sink，痕迹可读回 ──────────────────────────────────────────────

def test_trace_writes_lightweight_record(tmp_path):
    sink = JsonlSink(tmp_path / "access_trace.jsonl")
    ca = ConnectorAudit(sink=sink)
    ca.trace(source="SRM", action="get_delivery", target="PO20260519")

    records = sink.read_all()
    assert len(records) == 1
    rec = records[0]
    # 只含轻量字段
    assert set(rec.keys()) == {"timestamp", "source", "action", "target"}
    assert rec["source"] == "SRM"
    assert rec["action"] == "get_delivery"
    assert rec["target"] == "PO20260519"
    assert rec["timestamp"]  # 自动填


def test_trace_has_no_compliance_decision_fields(tmp_path):
    """轻量痕迹绝不含场景级合规决策字段（decision/evaluator/automation_level）。"""
    sink = JsonlSink(tmp_path / "access_trace.jsonl")
    ConnectorAudit(sink=sink).trace(source="zp_ERP", action="get_purchase_orders")
    rec = sink.read_all()[0]
    for forbidden in ("decision", "evaluator", "automation_level", "oem_context"):
        assert forbidden not in rec, f"连接器痕迹不应含合规决策字段：{forbidden}"


def test_disabled_audit_writes_nothing(tmp_path):
    """未注入 sink / 关闭时，连接器不产生任何痕迹文件。"""
    ca = ConnectorAudit(sink=None)  # 无 sink → 静默
    ca.trace(source="CSV", action="get_bom")  # 不应抛错、不写文件
    assert list(tmp_path.iterdir()) == []


# ── D2：debug 日志默认关闭、物理隔离 ────────────────────────────────────────

def test_debug_log_off_by_default(tmp_path):
    log_path = tmp_path / "srm.debug.log"
    dbg = DebugLog(path=log_path)  # 默认 enabled=False
    dbg.record(req={"poErpNo": "X"}, resp={"vExpectedDate": "2026-07-01"})
    assert not log_path.exists(), "debug 日志默认关闭时不应产生文件"


def test_debug_log_when_enabled_writes_to_separate_file(tmp_path):
    log_path = tmp_path / "srm.debug.log"
    dbg = DebugLog(path=log_path, enabled=True)
    dbg.record(req={"poErpNo": "X"}, resp={"vExpectedDate": "2026-07-01"})
    assert log_path.exists()
    content = log_path.read_text(encoding="utf-8")
    assert "vExpectedDate" in content  # 全文进 debug 文件
    # 该文件独立于合规 audit，名称命中 .gitignore 的 *.debug.log
    assert log_path.name.endswith(".debug.log")


def test_access_trace_dataclass_serializes():
    t = AccessTrace(source="U9C", action="get_inventory", target="R01B.0039")
    d = t.to_dict()
    assert d["source"] == "U9C" and d["timestamp"]
