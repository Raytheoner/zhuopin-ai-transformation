"""queue_edit_lock.SubprocessQueueEditLock 单测（队列 #333③）。

`try_acquire` 的既有行为（占用中抛 QueueLockBusy）不在本文件覆盖范围——
本文件只补 #333③ 新增的"release 被拒绝时的可观测性"这一层，用
`unittest.mock.patch` 拦截 `subprocess.run`，不依赖真实 CLI 工具/真实
锁文件，聚焦纯逻辑分支。
"""
from __future__ import annotations

import subprocess
from unittest.mock import Mock, patch

from zhuopin_platform.audit import AuditLogger

from aibot_service.queue_edit_lock import SubprocessQueueEditLock


def _completed(returncode: int, stdout: str = "", stderr: str = "") -> subprocess.CompletedProcess:
    return subprocess.CompletedProcess(args=["x"], returncode=returncode, stdout=stdout, stderr=stderr)


def _lock(tmp_path, **kwargs) -> SubprocessQueueEditLock:
    tool = tmp_path / "0-学习与工具" / "工具-共享文档编辑锁.py"
    tool.parent.mkdir(parents=True, exist_ok=True)
    tool.write_text("", encoding="utf-8")  # release() 只检查 exists()，内容不重要
    return SubprocessQueueEditLock(tmp_path, tmp_path / "queue.md", **kwargs)


def test_release_success_no_audit_no_alert(tmp_path):
    audit = Mock(spec=AuditLogger)
    alert = Mock()
    lock = _lock(tmp_path, audit=audit, alert_send=alert)
    with patch("aibot_service.queue_edit_lock.subprocess.run", return_value=_completed(0)):
        lock.release()
    audit.record.assert_not_called()
    alert.assert_not_called()


def test_release_rejected_records_audit_event(tmp_path):
    audit_path = tmp_path / "audit.jsonl"
    audit = AuditLogger.jsonl(audit_path)
    lock = _lock(tmp_path, audit=audit)
    rejection_stdout = "✗ release 被拒绝（1 项结构问题，锁保持占用）：§一 #201 不属于本次持锁期间 --reserve 预留的编号集合"
    with patch("aibot_service.queue_edit_lock.subprocess.run", return_value=_completed(1, stdout=rejection_stdout)):
        lock.release()  # 不得抛出

    records = audit.query_by(action="queue_edit_lock_release_rejected")
    assert len(records) == 1
    assert records[0]["decision"]["returncode"] == 1
    assert records[0]["decision"]["who"] == lock._who
    assert "预留的编号集合" in records[0]["data_sources"]["detail"]


def test_release_rejected_calls_alert_send_with_detail(tmp_path):
    alert = Mock()
    lock = _lock(tmp_path, alert_send=alert)
    with patch(
        "aibot_service.queue_edit_lock.subprocess.run",
        return_value=_completed(1, stdout="§一 #201 不属于本次持锁期间 --reserve 预留的编号集合"),
    ):
        lock.release()

    alert.assert_called_once()
    (text,), _ = alert.call_args
    assert "returncode=1" in text
    assert "预留的编号集合" in text


def test_release_rejected_without_audit_or_alert_does_not_raise(tmp_path):
    """向后兼容：既有调用方不传 audit/alert_send（本次改动前的唯一形态），
    release() 仍不得抛出——`SubprocessQueueEditLock` 的默认构造行为不变。"""
    lock = _lock(tmp_path)
    with patch("aibot_service.queue_edit_lock.subprocess.run", return_value=_completed(1, stdout="拒绝")):
        lock.release()  # 不抛即通过


def test_release_rejected_audit_failure_swallowed(tmp_path):
    """release() 的"不向上抛出"契约不能被本次新增的可观测性代码自己打破——
    即便 audit.record 本身抛异常，也必须被吞掉，不影响 release() 的返回。"""
    audit = Mock(spec=AuditLogger)
    audit.record.side_effect = RuntimeError("磁盘写满")
    alert = Mock()
    lock = _lock(tmp_path, audit=audit, alert_send=alert)
    with patch("aibot_service.queue_edit_lock.subprocess.run", return_value=_completed(1, stdout="拒绝")):
        lock.release()  # 不得抛出

    alert.assert_called_once()  # audit 失败不应连带跳过 alert


def test_release_rejected_alert_failure_swallowed(tmp_path):
    """同上，反过来：alert_send 本身抛异常也不得向上传播，且不影响 audit 已
    完成的记录。"""
    audit_path = tmp_path / "audit.jsonl"
    audit = AuditLogger.jsonl(audit_path)
    alert = Mock(side_effect=RuntimeError("webhook 超时"))
    lock = _lock(tmp_path, audit=audit, alert_send=alert)
    with patch("aibot_service.queue_edit_lock.subprocess.run", return_value=_completed(1, stdout="拒绝")):
        lock.release()  # 不得抛出

    assert len(audit.query_by(action="queue_edit_lock_release_rejected")) == 1
