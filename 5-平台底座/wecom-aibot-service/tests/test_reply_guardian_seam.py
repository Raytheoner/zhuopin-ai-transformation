"""Isolated reply-to-guardian seam; the model split itself is a deterministic fixture.

The separate native patrol consumer acceptance covers Codex model execution. This test
keeps all queue writes, signals, and guardian state in tmp_path.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from aibot_service import followup_readme_bridge as bridge
from aibot_service import patrol_dispatch, patrol_signal
from aibot_service.queue_appender import append_pending_task
from aibot_service.repo_paths import resolve_patrol_charter_path
from zhuopin_platform.shared_tools.followup_gate import REPLY_ARRIVED_STATUS

ROOT = Path(__file__).resolve().parents[3]
QUERY_SOURCE = ROOT / "0-学习与工具" / "工具-队列查询.py"
ENTRY_SOURCE = ROOT / "0-学习与工具" / "codex-handoff" / "guardian_entry.py"
NOW = datetime(2026, 9, 26, 4, 0, tzinfo=timezone.utc)
LETTER = "采购部-姚祖怡-跟进-2026-08-20-SC2采购周报口径判例批改.md"
ARCHIVED = (
    "采购部-YaoZuYi-回复-2026-08-21-采购部-姚祖怡-跟进-2026-08-20-"
    "SC2采购周报口径判例批改-0d6acc8a6238e6155c6e91f874246213.docx"
)
QUEUE_REL = Path("1-转型规划/0-全景路线图/跨桌任务队列-机制环境.md")


class Lock:
    def try_acquire(self):
        pass

    def release(self):
        pass


def _load_entry():
    spec = importlib.util.spec_from_file_location("reply_guardian_entry", ENTRY_SOURCE)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_mock_reply_signal_dispatch_queue_row_is_selectable_by_human_guardian(
        tmp_path, monkeypatch):
    repo = tmp_path / "fixture-repo"
    repo.mkdir()
    monkeypatch.setenv("ZHUOPIN_CODEX_STATE", str(tmp_path / "guardian-state"))
    readme = repo / bridge.FOLLOWUP_README_REL
    readme.parent.mkdir(parents=True)
    readme.write_text(
        "## 现有跟进信清单\n\n"
        "| 编号 | 日期 | 收信人 | 主要事项 | 交期要点 | 发送状态（2026-07-06） |\n"
        "|--------|------|--------|---------|---------|---------|\n"
        f"| 采购部#17 | 2026-08-20 | 采购部 · 姚祖怡 | SC2 判例批改 → 目标文件：`{LETTER}` | 尽快 | ✅ 已推送 2026-08-20 12:20 UTC |\n",
        encoding="utf8")
    queue = repo / QUEUE_REL
    queue.parent.mkdir(parents=True)
    queue.write_text(
        "> **编号高水位线：§一 #649 ｜ §四 #36**\n\n"
        "## 一、任务看板\n\n"
        "| # | 任务 | 领取方 | 输入（指针） | 期望产出 | 状态 | 触碰区 | 登记 |\n"
        "|---|------|--------|-------------|----------|------|--------|------|\n\n"
        "## 二、待 commit 批次\n",
        encoding="utf8")
    business = repo / "1-转型规划/0-全景路线图/跨桌任务队列-业务场景.md"
    business.write_text(
        "## 一、任务看板\n\n"
        "| # | 任务 | 领取方 | 输入（指针） | 期望产出 | 状态 | 触碰区 | 登记 |\n"
        "|---|------|--------|-------------|----------|------|--------|------|\n",
        encoding="utf8")
    query = repo / "0-学习与工具/工具-队列查询.py"
    query.parent.mkdir(parents=True)
    shutil.copy2(QUERY_SOURCE, query)
    charter = resolve_patrol_charter_path(repo)
    charter.parent.mkdir(parents=True)
    charter.write_text("脱敏拆件夹具章程", encoding="utf8")
    config = repo / ".codex"
    config.mkdir()
    (config / "runtime.local.json").write_text(
        json.dumps({"python": sys.executable}), encoding="utf8")
    (config / "consumers.local.json").write_text(
        json.dumps({"patrol": {"enabled": True, "timeout_seconds": 60}}),
        encoding="utf8")
    provider = repo / "0-学习与工具/codex-handoff/model_provider.py"
    provider.parent.mkdir(parents=True)
    provider.write_text("# isolated model seam only", encoding="utf8")
    calls = []

    class Process:
        pid = 81001

        class Input:
            def write(self, prompt):
                assert "脱敏拆件夹具章程" in prompt
            def close(self):
                pass
        stdin = Input()

        def wait(self):
            snapshot = patrol_signal.read_signal(repo)
            assert snapshot.present and snapshot.pending[0]["archived_filename"] == ARCHIVED
            append_pending_task(
                queue, description="脱敏回件拆件：本地草拟跟进事实",
                owner="Codex", input_pointer="fixture/reply.docx",
                expected_output="本地草拟，不发布", date_str="09-26",
                touch_zone="fixture/service", high_water_mark_path=queue)
            patrol_signal.clear_signal(repo, before=snapshot.pending[-1]["at"])
            return 0

    def dispatch(repo_root, **kwargs):
        assert repo_root == repo
        result = patrol_dispatch.dispatch_headless_patrol(
            repo_root, popen=lambda argv, **kw: calls.append(argv) or Process(),
            pid_alive=lambda _pid: False, run_in_thread=lambda fn: fn(),
            monotonic=iter((0, 100)).__next__, sleep=lambda _seconds: None,
            **kwargs)
        assert result.action == "started"

    marked = bridge.mark_reply_arrived(
        archived_filename=ARCHIVED, repo_root=repo, audit=None,
        lock_factory=Lock, department="采购部", now=NOW,
        sleep=lambda _seconds: None, log=lambda _line: None,
        dispatch_patrol=dispatch)
    assert marked.action == bridge.ACTION_MARKED
    assert len(calls) == 1
    assert not patrol_signal.read_signal(repo).present
    assert REPLY_ARRIVED_STATUS in readme.read_text(encoding="utf8")

    def run_query(*args):
        result = subprocess.run(
            [sys.executable, str(query), *args], cwd=repo,
            capture_output=True, text=True, timeout=30)
        assert result.returncode == 0, result.stderr + result.stdout
        return result.stdout

    digest = run_query("--digest")
    assert "650" in digest and "脱敏回件拆件" in digest
    full = run_query("--row", "650", "--section", "一", "--field", "all")
    status = json.loads(run_query(
        "--row", "650", "--section", "一", "--format", "json"))
    assert status["carrier"] == "live" and status["done"] is False

    entry = _load_entry()
    monkeypatch.setattr(entry, "ROOT", repo)
    monkeypatch.setattr(entry, "QUERY", query)
    external = tmp_path / "external"
    external.mkdir()
    decision = external / "lan-decision.json"
    candidate = {
        "task_id": "reply-fixture-650", "row": 650, "section": "一",
        "task_excerpt": "脱敏回件拆件", "next_action": "本地草拟",
        "opener_id": "A1", "lane": "alpha",
        "touches": ["fixture/service"],
        "action_key": "worktree_local_build", "lan_required": False}
    decision.write_text(json.dumps({
        "task_id": candidate["task_id"], "row": 650, "section": "一",
        "action_key": candidate["action_key"],
        "queue_full_sha256": hashlib.sha256(full.encode("utf8")).hexdigest(),
        "lan_required": False, "next_action": "本地草拟",
        "lane": "alpha", "touches": ["fixture/service"],
        "text": "The fixture needs no LAN connection."}), encoding="utf8")
    candidate["lan_decision"] = str(decision)
    watch = external / "watch.md"
    watch.write_text("controlled fixture watch", encoding="utf8")

    def execute(argv, **_kwargs):
        if Path(str(argv[1])) == query:
            completed = subprocess.run(
                argv, cwd=repo, capture_output=True, text=True, timeout=30)
            return {"exit": completed.returncode, "stdout": completed.stdout,
                    "stderr": completed.stderr}
        if "-DryRun" in argv:
            return {"exit": 0, "stdout": "泳道 1 条：\n  ◆ alpha ：A1（泳道内串行）",
                    "stderr": ""}
        return {"exit": 0, "stdout": "lint clean", "stderr": ""}

    planned = entry.start({
        "batch_id": "reply-fixture-batch", "watch_piece": str(watch),
        "candidates": [candidate]}, executor=execute,
        lan_prober=lambda: {"status": "off", "effective": "off"}, run=False)
    assert planned["status"] == "planned", planned
    assert planned["plan"]["dispatchable_ids"] == ["reply-fixture-650"]
    assert planned["delivery_accepted"] is False
