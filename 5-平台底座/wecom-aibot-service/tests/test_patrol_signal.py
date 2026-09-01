"""队列 #382⑴ 单测：拆件巡逻事件驱动开班——信号文件读写。"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from aibot_service import patrol_signal


T1 = datetime(2026, 9, 1, 2, 0, 0, tzinfo=timezone.utc)
T2 = datetime(2026, 9, 1, 5, 30, 0, tzinfo=timezone.utc)


class TestRoundTrip:
    def test_未曾到达即无信号(self, tmp_path):
        snapshot = patrol_signal.read_signal(tmp_path)
        assert snapshot.present is False
        assert snapshot.pending == []
        assert snapshot.corrupted is False

    def test_到达一次即可探测到(self, tmp_path):
        patrol_signal.raise_signal(
            tmp_path, letter_number="财务部#15",
            archived_filename="财务部-TangYanPing-回复-2026-09-01-x.docx", now=T1,
        )
        snapshot = patrol_signal.read_signal(tmp_path)
        assert snapshot.present is True
        assert len(snapshot.pending) == 1
        assert snapshot.pending[0]["letter_number"] == "财务部#15"
        assert snapshot.pending[0]["at"] == "2026-09-01T02:00:00Z"

    def test_清空后恢复无信号(self, tmp_path):
        patrol_signal.raise_signal(tmp_path, letter_number="财务部#15",
                                    archived_filename="x.docx", now=T1)
        removed = patrol_signal.clear_signal(tmp_path)
        assert removed == 1
        assert patrol_signal.read_signal(tmp_path).present is False

    def test_文件不存在时清空返回0且不报错(self, tmp_path):
        assert patrol_signal.clear_signal(tmp_path) == 0


class TestAccumulation:
    def test_两次到达累积成两条(self, tmp_path):
        patrol_signal.raise_signal(tmp_path, letter_number="财务部#15",
                                    archived_filename="a.docx", now=T1)
        patrol_signal.raise_signal(tmp_path, letter_number="采购部#19",
                                    archived_filename="b.docx", now=T2)
        snapshot = patrol_signal.read_signal(tmp_path)
        assert len(snapshot.pending) == 2

    def test_按checkpoint清空只移走截止时间以内的条目(self, tmp_path):
        """扫描期间又来一条不得被整份清空吞掉——同 outbox_relay 的乐观并发思路。"""
        patrol_signal.raise_signal(tmp_path, letter_number="财务部#15",
                                    archived_filename="a.docx", now=T1)
        removed = patrol_signal.clear_signal(tmp_path, before="2026-09-01T02:00:00Z")
        assert removed == 1
        assert patrol_signal.read_signal(tmp_path).present is False

        patrol_signal.raise_signal(tmp_path, letter_number="财务部#15",
                                    archived_filename="a.docx", now=T1)
        patrol_signal.raise_signal(tmp_path, letter_number="采购部#19",
                                    archived_filename="b.docx", now=T2)
        removed = patrol_signal.clear_signal(tmp_path, before="2026-09-01T02:00:00Z")
        assert removed == 1, "只应移走 T1 那条，T2 是扫描期间新到的，应保留"
        remaining = patrol_signal.read_signal(tmp_path)
        assert remaining.present is True
        assert len(remaining.pending) == 1
        assert remaining.pending[0]["letter_number"] == "采购部#19"


class TestFailOpen:
    def test_信号文件损坏时读取按有信号处理(self, tmp_path):
        from aibot_service.repo_paths import resolve_patrol_signal_path

        path = resolve_patrol_signal_path(tmp_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("这不是合法 JSON {{{", encoding="utf-8")

        snapshot = patrol_signal.read_signal(tmp_path)
        assert snapshot.present is True, "fail-open：宁可多扫一次空跑，不可漏判真实回件"
        assert snapshot.corrupted is True

    def test_损坏文件被新信号覆盖不阻塞后续到达(self, tmp_path):
        from aibot_service.repo_paths import resolve_patrol_signal_path

        path = resolve_patrol_signal_path(tmp_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("坏掉的内容", encoding="utf-8")

        patrol_signal.raise_signal(tmp_path, letter_number="财务部#15",
                                    archived_filename="a.docx", now=T1)
        snapshot = patrol_signal.read_signal(tmp_path)
        assert snapshot.corrupted is False
        assert len(snapshot.pending) == 1

    def test_清空损坏文件直接整份删除(self, tmp_path):
        from aibot_service.repo_paths import resolve_patrol_signal_path

        path = resolve_patrol_signal_path(tmp_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("坏掉的内容", encoding="utf-8")

        removed = patrol_signal.clear_signal(tmp_path, before="2026-09-01T00:00:00Z")
        assert removed == 0
        assert patrol_signal.read_signal(tmp_path).present is False


class TestNeverThrows:
    def test_写入失败不抛异常只记日志(self, tmp_path, monkeypatch):
        """`mark_reply_arrived` 依赖本函数绝不向上抛——见模块文首设计取舍 3。"""
        def _boom(*args, **kwargs):
            raise OSError("模拟磁盘写入失败")

        monkeypatch.setattr(Path, "write_text", _boom)
        logs = []
        patrol_signal.raise_signal(
            tmp_path, letter_number="财务部#15", archived_filename="a.docx",
            now=T1, log=logs.append,
        )
        assert any("写入失败" in line for line in logs)

    def test_日志函数本身抛出也不向上传播(self, tmp_path, monkeypatch):
        monkeypatch.setattr(Path, "write_text",
                             lambda *a, **k: (_ for _ in ()).throw(OSError("坏")))
        # log 回调本身也抛——不得反过来打断调用方
        patrol_signal.raise_signal(
            tmp_path, letter_number="财务部#15", archived_filename="a.docx",
            now=T1, log=lambda _m: (_ for _ in ()).throw(RuntimeError("日志也坏了")),
        )
