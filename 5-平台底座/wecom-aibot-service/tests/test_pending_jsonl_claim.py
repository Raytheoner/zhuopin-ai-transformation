"""队列 #586 ⑸：`pending_jsonl` 互斥声明单测（flush 幂等的底层原语）。"""
from __future__ import annotations

from pathlib import Path

from aibot_service.pending_jsonl import release_flush_claim, try_claim_flush


def test_first_claim_succeeds(tmp_path: Path):
    pending_path = tmp_path / "pending.jsonl"
    assert try_claim_flush(pending_path) is True


def test_second_claim_fails_while_first_still_held(tmp_path: Path):
    pending_path = tmp_path / "pending.jsonl"
    assert try_claim_flush(pending_path) is True
    assert try_claim_flush(pending_path) is False, "第一个声明未释放前，第二个必须失败"


def test_claim_succeeds_again_after_release(tmp_path: Path):
    pending_path = tmp_path / "pending.jsonl"
    assert try_claim_flush(pending_path) is True
    release_flush_claim(pending_path)
    assert try_claim_flush(pending_path) is True


def test_release_without_prior_claim_does_not_raise(tmp_path: Path):
    pending_path = tmp_path / "pending.jsonl"
    release_flush_claim(pending_path)  # 不抛异常即通过


def test_claim_creates_parent_directory(tmp_path: Path):
    pending_path = tmp_path / "nested" / "dir" / "pending.jsonl"
    assert try_claim_flush(pending_path) is True
    assert (tmp_path / "nested" / "dir").is_dir()
