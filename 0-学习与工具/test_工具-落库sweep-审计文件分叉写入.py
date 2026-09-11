# -*- coding: utf-8 -*-
"""落库 sweep 第 17 类常驻告警 · 企微机器人审计文件在 worktree 里被再次分叉
写入（队列 §一 `#559`）单测。

同族既有先例（`test_hooks-哨兵.py` 第 9 类、`test_工具-落库sweep-未并入分支
告警.py` 第 16 类）：每个常驻告警类独立成一份测试文件，`sweep` 模块通过
`importlib.util.spec_from_file_location` 加载（`工具-落库sweep.py` 文件名
含中文，无法作为标准模块名 import）。
"""
from __future__ import annotations

import importlib.util
import json
import time
from pathlib import Path

import pytest

_SWEEP_SPEC = importlib.util.spec_from_file_location(
    "commit_sweep_for_aibot_audit_orphan", Path(__file__).resolve().parent / "工具-落库sweep.py"
)
sweep = importlib.util.module_from_spec(_SWEEP_SPEC)
_SWEEP_SPEC.loader.exec_module(sweep)


@pytest.fixture()
def repo(tmp_path: Path) -> Path:
    """最小仓库夹具：不放 `.env`，`_load_webhook_url` 读不到真实 webhook——
    本类全部用例走「只留痕、不真发」路径，与 `test_hooks-哨兵.py` 同惯例。"""
    (tmp_path / "reports").mkdir()
    return tmp_path


def _touch_orphan(repo: Path, worktree_name: str, age_hours: float) -> Path:
    candidate = repo / ".claude" / "worktrees" / worktree_name / sweep.AIBOT_AUDIT_ORPHAN_RELATIVE_PATH
    candidate.parent.mkdir(parents=True, exist_ok=True)
    candidate.write_text('{"scenario": "wecom-aibot", "action": "followup_approved"}\n', encoding="utf-8")
    stamp = time.time() - age_hours * 3600
    import os
    os.utime(candidate, (stamp, stamp))
    return candidate


def test_无worktrees目录时不告警(repo: Path):
    log: list[str] = []
    sweep._check_aibot_audit_orphan_writes(repo, log)
    text = "\n".join(log)
    assert "无" in text and "worktree" in text
    state_path = repo / sweep.AIBOT_AUDIT_ORPHAN_STATE_REL
    assert not state_path.exists() or json.loads(state_path.read_text(encoding="utf-8")) == {}


def test_worktree里最近被写的副本即告警(repo: Path):
    _touch_orphan(repo, "wecom-service-home", age_hours=0.5)
    log: list[str] = []
    sweep._check_aibot_audit_orphan_writes(repo, log)
    state = json.loads((repo / sweep.AIBOT_AUDIT_ORPHAN_STATE_REL).read_text(encoding="utf-8"))
    assert "wecom-service-home" in state


def test_worktree里陈旧副本不告警(repo: Path):
    """🔴 只对"最近被写"告警——早已停写的残留 worktree 副本不是"正在分叉"。"""
    _touch_orphan(
        repo, "long-dead-worktree",
        age_hours=sweep.AIBOT_AUDIT_ORPHAN_RECENT_WRITE_HOURS + 5,
    )
    log: list[str] = []
    sweep._check_aibot_audit_orphan_writes(repo, log)
    state = json.loads((repo / sweep.AIBOT_AUDIT_ORPHAN_STATE_REL).read_text(encoding="utf-8"))
    assert "long-dead-worktree" not in state


def test_多个worktree同时命中全部入告警(repo: Path):
    _touch_orphan(repo, "worktree-a", age_hours=0.1)
    _touch_orphan(repo, "worktree-b", age_hours=1.0)
    log: list[str] = []
    sweep._check_aibot_audit_orphan_writes(repo, log)
    state = json.loads((repo / sweep.AIBOT_AUDIT_ORPHAN_STATE_REL).read_text(encoding="utf-8"))
    assert "worktree-a" in state
    assert "worktree-b" in state


def test_主仓自身审计文件不算分叉(repo: Path):
    """权威文件本身（`resolve_audit_path` 落点）不该被误判为"另一份分叉"。"""
    canonical = repo / sweep.AIBOT_AUDIT_ORPHAN_RELATIVE_PATH
    canonical.parent.mkdir(parents=True, exist_ok=True)
    canonical.write_text("{}\n", encoding="utf-8")
    log: list[str] = []
    sweep._check_aibot_audit_orphan_writes(repo, log)
    state_path = repo / sweep.AIBOT_AUDIT_ORPHAN_STATE_REL
    assert not state_path.exists() or json.loads(state_path.read_text(encoding="utf-8")) == {}


def test_分叉停止写入后告警自动解除(repo: Path):
    """🔴 同第 4/6/7/9/10/11/14 类既有纪律：告警必须能被"已恢复"自动关掉。"""
    candidate = _touch_orphan(repo, "wecom-service-home", age_hours=0.5)
    log: list[str] = []
    sweep._check_aibot_audit_orphan_writes(repo, log)
    state = json.loads((repo / sweep.AIBOT_AUDIT_ORPHAN_STATE_REL).read_text(encoding="utf-8"))
    assert "wecom-service-home" in state, "第一轮应留下告警状态"

    # 模拟"这份文件不再被写"：把 mtime 推远（同陈旧副本判据）。
    stamp = time.time() - (sweep.AIBOT_AUDIT_ORPHAN_RECENT_WRITE_HOURS + 1) * 3600
    import os
    os.utime(candidate, (stamp, stamp))
    log2: list[str] = []
    sweep._check_aibot_audit_orphan_writes(repo, log2)
    state2 = json.loads((repo / sweep.AIBOT_AUDIT_ORPHAN_STATE_REL).read_text(encoding="utf-8"))
    assert "wecom-service-home" not in state2
    assert "解除" in "\n".join(log2)


def test_零命中也回显(repo: Path):
    """🔴 同第 4/6/7/9/10/11/14 类既有纪律：零命中也要在 log 里留痕，不能悄无
    声息地什么都不说——一个从来不出声的机制没人能判断它是"没问题"还是"没跑"。"""
    log: list[str] = []
    sweep._check_aibot_audit_orphan_writes(repo, log)
    assert log, "零命中也必须有至少一行回显"
