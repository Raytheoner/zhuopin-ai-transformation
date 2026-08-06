"""JsonlAppendStore 测试（队列 #110 Feature A/B 共用骨架）。"""
from __future__ import annotations

import json

from sc8.feedback_store import JsonlAppendStore


def test_append_returns_id_and_writes_line(tmp_path):
    store = JsonlAppendStore(tmp_path / "fb.jsonl")
    item_id = store.append({"product_id": "S02Y.0188", "verdict": "correct"})
    assert item_id
    lines = (tmp_path / "fb.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    rec = json.loads(lines[0])
    assert rec["id"] == item_id
    assert rec["product_id"] == "S02Y.0188"
    assert "created_at" in rec


def test_append_ignores_caller_supplied_id_and_created_at(tmp_path):
    """id/created_at 由存储自己生成，调用方传入的同名字段应被覆盖（保证唯一且可信）。"""
    store = JsonlAppendStore(tmp_path / "fb.jsonl")
    store.append({"id": "forged", "created_at": "2000-01-01T00:00:00+00:00", "x": 1})
    rec = store.read_all()[0]
    assert rec["id"] != "forged"
    assert rec["created_at"] != "2000-01-01T00:00:00+00:00"


def test_read_all_empty_when_file_absent(tmp_path):
    store = JsonlAppendStore(tmp_path / "missing.jsonl")
    assert store.read_all() == []


def test_read_all_skips_corrupt_lines(tmp_path):
    path = tmp_path / "fb.jsonl"
    path.write_text('{"id":"a"}\nnot json\n{"id":"b"}\n', encoding="utf-8")
    store = JsonlAppendStore(path)
    ids = [r["id"] for r in store.read_all()]
    assert ids == ["a", "b"]


def test_creates_parent_directory(tmp_path):
    path = tmp_path / "nested" / "dir" / "fb.jsonl"
    JsonlAppendStore(path).append({"x": 1})
    assert path.exists()
