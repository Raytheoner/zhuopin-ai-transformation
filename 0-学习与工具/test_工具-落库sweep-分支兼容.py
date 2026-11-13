"""sweep 分支兼容性回归：真 Git／本地远端，通知仅在边界捕获。"""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import time

import pytest

TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))
spec = importlib.util.spec_from_file_location("sweep_compat_sut", TOOLS / "工具-落库sweep.py")
sweep = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = sweep
spec.loader.exec_module(sweep)
STANDING_RUNNER = getattr(sweep, '_observe_standing_checks', None)
QUEUES = (sweep.QUEUE_MECHANISM_PATH_REL, sweep.QUEUE_BUSINESS_PATH_REL)


def git(root, *args):
    return subprocess.run(["git", "-c", "core.quotepath=false", *args], cwd=root,
                          check=True, capture_output=True, text=True, encoding="utf-8").stdout.strip()


@pytest.fixture
def case(tmp_path, monkeypatch):
    if STANDING_RUNNER is not None:
        monkeypatch.setattr(sweep, '_observe_standing_checks', lambda *args: None)
    origin = tmp_path / "origin.git"
    root = tmp_path / "main"
    git(tmp_path, "init", "--bare", "-q", "-b", "master", str(origin))
    git(tmp_path, "init", "-q", "-b", "master", str(root))
    git(root, "config", "user.name", "Isolated Test")
    git(root, "config", "user.email", "test@example.invalid")
    tools = root / "0-学习与工具"
    tools.mkdir()
    (root / ".gitignore").write_text("reports/\n.lock-status\n", encoding="utf-8")
    (root / "business.txt").write_text("committed business\n", encoding="utf-8")
    for rel in QUEUES:
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("# 队列\n\n## 一、在办\n\n## 二、待 commit 批次\n", encoding="utf-8")
    (root / sweep.EDIT_LOCK_SCRIPT_REL).write_text(
        "from pathlib import Path\nimport sys\nr=Path(__file__).resolve().parents[1]\n"
        "s=(r/'.lock-status').read_text() if (r/'.lock-status').exists() else 'free'\n"
        "assert sys.argv[1]=='status', 'observer must not acquire/release'\n"
        "print('占用方：OTHER\\n已持锁：2 分钟（有效）' if s=='busy' else '（无锁，可直接编辑）')\n"
        "raise SystemExit(2 if s=='error' else 0)\n", encoding="utf-8")
    # 边界替身只读指定主仓当前事实；从脚本位置猜根或读旧队列会读错。
    (root / sweep.PLAN_BACKPRESSURE_SCRIPT_REL).write_text(
        "import argparse,json\nfrom pathlib import Path\n"
        "p=argparse.ArgumentParser();p.add_argument('--json',action='store_true');"
        "p.add_argument('--root',required=True);a=p.parse_args();r=Path(a.root)\n"
        "q=r/" + repr(sweep.QUEUE_BUSINESS_PATH_REL) + "\n"
        "v=q.read_text(encoding='utf-8')\n"
        "assert 'live-uncommitted' in v, 'not the live main queue'\n"
        "print(json.dumps({'scope':'isolated','total':1,'counts':{'三处皆无':1,"
        "'疑似已承接·待人确认':0,'已承接':0},'unaccepted':[{'code':'X1',"
        "'title':'隔离场景','domain':'测试','planned_month':'2026-10','suspended':'',"
        "'prereq':'合成前置'}],'suspected':[],'accepted':[],'queue_row_drafts':[]}))\n",
        encoding="utf-8")
    git(root, "add", "-A")
    git(root, "commit", "-qm", "initial")
    git(root, "remote", "add", "origin", str(origin))
    git(root, "push", "-q", "-u", "origin", "master")
    peer = tmp_path / "peer"
    git(tmp_path, "clone", "-q", str(origin), str(peer))
    git(peer, "config", "user.name", "Remote Test")
    git(peer, "config", "user.email", "remote@example.invalid")
    git(root, "checkout", "-q", "-b", "business")
    (root / "business.txt").write_text("another session staged\n", encoding="utf-8")
    git(root, "add", "--", "business.txt")
    (root / "business.txt").write_text("another session unstaged\n", encoding="utf-8")
    (root / "untracked.txt").write_text("another session untracked\n", encoding="utf-8")
    with (root / sweep.QUEUE_BUSINESS_PATH_REL).open("a", encoding="utf-8") as stream:
        stream.write("live-uncommitted\n")
    sent = []
    monkeypatch.setattr(sweep, "MAIN_WORKSPACE", root)
    monkeypatch.setattr(sweep, "_load_webhook_url", lambda _: "https://example.invalid/captured")
    monkeypatch.setattr(sweep, "_send_wecom_markdown",
                        lambda url, text: (sent.append(text), _accepted_test_receipt(url, text))[1])
    monkeypatch.setattr(sys, "argv", ["sweep", "--verbose"])
    return root, origin, peer, sent


def state(root, rel):
    path = root / rel
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def seed(root, rel, payload):
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def assert_missing_health_is_reported(root, sent, log, category_count):
    """Account for every delivery, including both independent missing-source alerts."""
    assert sent.count("isolated candidate") == category_count
    assert len(sent) == category_count + 2
    for label, category in (("提醒源健康", "reminder-source"),
                            ("本地提醒outbox健康", "reminder-outbox")):
        messages = [text for text in sent if label in text]
        assert len(messages) == 1
        assert "UNKNOWN" in messages[0]
        assert any(f"class={category} status=unavailable" in line and "candidate_count=1" in line for line in log)


def protected_snapshot(root, origin):
    return (git(root, "rev-parse", "HEAD", "master"), git(origin, "rev-parse", "master"),
            (root / ".git/index").read_bytes(),
            {rel: (root / rel).read_bytes() for rel in (*QUEUES, "business.txt", "untracked.txt")})


def advance_remote(peer):
    (peer / "remote.txt").write_text("remote progress\n", encoding="utf-8")
    git(peer, "add", "remote.txt")
    git(peer, "commit", "-qm", "remote progress")
    git(peer, "push", "-q", "origin", "master")
    return git(peer, "rev-parse", "HEAD")


class TestNonMasterObservation:
    @pytest.mark.parametrize("suspension", ["", "域级暂缓，待业务确认"])
    def test_native_planner_payload_preserves_suspension_and_recovers_scan(self, case, suspension):
        root, origin, peer, sent = case
        native_spec = importlib.util.spec_from_file_location(
            "sweep_native_planner_contract", TOOLS / sweep.PLAN_BACKPRESSURE_SCRIPT_REL.split("/")[-1])
        native = importlib.util.module_from_spec(native_spec)
        sys.modules[native_spec.name] = native
        native_spec.loader.exec_module(native)
        scenario = native.Scenario("X1", "测试", "隔离场景", "2026-10", (), (), suspension)
        payload = native.to_payload([native.ScenarioVerdict(scenario)])
        (root / sweep.PLAN_BACKPRESSURE_SCRIPT_REL).write_text(
            "print(" + repr(json.dumps(payload, ensure_ascii=False)) + ")\n", encoding="utf-8")
        old = "2026-10-16T00:00:00+00:00"
        seed(root, sweep.PLAN_BACKPRESSURE_UNSCANNED_STATE_REL,
             {sweep.PLAN_BACKPRESSURE_UNSCANNED_KEY: old})
        before = protected_snapshot(root, origin)
        assert sweep.main() == 0
        assert state(root, sweep.PLAN_BACKPRESSURE_SCAN_MARKER_REL)["last_round_status"] == "scanned"
        assert not state(root, sweep.PLAN_BACKPRESSURE_UNSCANNED_STATE_REL)
        assert ("X1" in state(root, sweep.PLAN_BACKPRESSURE_STATE_REL)) is (not suspension)
        assert not state(root, sweep.PLAN_BACKPRESSURE_UNAVAILABLE_STATE_REL)
        assert not [text for text in sent if "判据不可用" in text]
        assert protected_snapshot(root, origin) == before

    def test_plan_read_failure_uses_existing_unavailable_alert_manager_once(self, case):
        root, origin, peer, sent = case
        (root / sweep.PLAN_BACKPRESSURE_SCRIPT_REL).write_text(
            "raise SystemExit('isolated read failure')\n", encoding="utf-8")
        assert sweep.main() == 0
        assert sweep.PLAN_BACKPRESSURE_UNAVAILABLE_KEY in state(root, sweep.PLAN_BACKPRESSURE_UNAVAILABLE_STATE_REL)
        first = list(sent)
        assert len(first) == 1 and "判据不可用" in first[0]
        assert sweep.main() == 0
        assert sent == first

    def test_master_write_gate_rejects_unreadable_edit_lock_status(self, case):
        root, origin, peer, sent = case
        git(root, "checkout", "-q", "master")
        (root / ".lock-status").write_text("error", encoding="utf-8")
        before = protected_snapshot(root, origin)
        with pytest.raises(sweep.SweepAbort, match="锁.*(读取|核实)"):
            sweep._abort_if_edit_lock_held(root, [])
        assert protected_snapshot(root, origin) == before

    def test_successful_fetch_with_stale_tracking_ref_is_still_unknown(self, case):
        root, origin, peer, sent = case
        advance_remote(peer)
        cached = git(root, "rev-parse", "origin/master")
        git(root, "config", "--unset-all", "remote.origin.fetch")
        seed(root, sweep.LOCAL_ONLY_COMMIT_STATE_REL,
             {sweep.LOCAL_ONLY_AHEAD_KEY: "2026-10-16T00:00:00+00:00"})
        assert sweep.main() == 0
        assert git(root, "rev-parse", "origin/master") == cached
        assert git(root, "rev-parse", "FETCH_HEAD") != cached
        assert state(root, sweep.LOCAL_ONLY_SCAN_MARKER_REL)["last_round_status"] == "unavailable"
        assert sweep.LOCAL_ONLY_AHEAD_KEY in state(root, sweep.LOCAL_ONLY_COMMIT_STATE_REL)

    def test_queue_changed_during_scan_is_unknown_and_does_not_resolve(self, case):
        root, origin, peer, sent = case
        seed(root, sweep.PLAN_BACKPRESSURE_STATE_REL, {"X1": "2026-10-16T00:00:00+00:00"})
        script = root / sweep.PLAN_BACKPRESSURE_SCRIPT_REL
        with script.open("a", encoding="utf-8") as stream:
            stream.write("q.write_text(v+'concurrent queue change\\n',encoding='utf-8')\n")
        assert sweep.main() == 0
        assert state(root, sweep.PLAN_BACKPRESSURE_SCAN_MARKER_REL)["last_round_status"] == "unavailable"
        assert "X1" in state(root, sweep.PLAN_BACKPRESSURE_STATE_REL)

    def test_untrusted_repo_override_does_not_enable_main_repository_observation(self, case, monkeypatch):
        root, origin, peer, sent = case
        cached = git(root, "rev-parse", "origin/master")
        advance_remote(peer)
        monkeypatch.setattr(sweep, "MAIN_WORKSPACE", root / "not-the-main-repository")
        monkeypatch.setattr(sys, "argv", ["sweep", "--repo-root", str(root), "--verbose"])
        assert sweep.main() == 0
        assert git(root, "rev-parse", "origin/master") == cached
        assert state(root, sweep.LOCAL_ONLY_SCAN_MARKER_REL)["last_round_status"] == "skipped"

    def test_pure_collection_never_refreshes_refs_index_or_states(self, case):
        root, origin, peer, sent = case
        tree = git(root, "rev-parse", "master^{tree}")
        commit = git(root, "commit-tree", tree, "-p", "master", "-m", "local master only")
        git(root, "update-ref", "refs/heads/master", commit)
        # 内容不变、mtime 改变：普通 git status 会刷新 index 的 stat 缓存。
        changed_time = time.time() + 3
        os.utime(root / ".gitignore", (changed_time, changed_time))
        advance_remote(peer)
        before = protected_snapshot(root, origin)
        cached = git(root, "rev-parse", "origin/master")
        observation, reason = sweep._collect_local_only_commits(root)
        assert reason is None and observation["ahead"] == 1 and observation["behind"] == 0
        assert git(root, "rev-parse", "origin/master") == cached
        assert protected_snapshot(root, origin) == before
        assert not (root / "reports").exists()
        assert sent == []

    @pytest.mark.parametrize("kind", ["local", "plan"])
    def test_scan_marker_write_failure_never_resolves_stoppage(self, case, monkeypatch, kind):
        root, origin, peer, sent = case
        marker = sweep.LOCAL_ONLY_SCAN_MARKER_REL if kind == "local" else sweep.PLAN_BACKPRESSURE_SCAN_MARKER_REL
        alerts = sweep.LOCAL_ONLY_UNSCANNED_STATE_REL if kind == "local" else sweep.PLAN_BACKPRESSURE_UNSCANNED_STATE_REL
        key = sweep.LOCAL_ONLY_UNSCANNED_KEY if kind == "local" else sweep.PLAN_BACKPRESSURE_UNSCANNED_KEY
        seed(root, alerts, {key: "2026-10-16T00:00:00+00:00"})
        original = sweep._write_json_state
        def fail_marker(path, value):
            if path == root / marker:
                raise OSError("marker write denied")
            return original(path, value)
        monkeypatch.setattr(sweep, "_write_json_state", fail_marker)
        assert sweep.main() == 0
        assert key in state(root, alerts)
        label = "第 8 类" if kind == "local" else "第 13 类"
        assert not [text for text in sent if text.startswith("✅") and label in text]

    def test_missing_master_ref_is_unknown_but_plan_still_runs(self, case):
        root, origin, peer, sent = case
        git(root, "update-ref", "-d", "refs/heads/master")
        assert sweep.main() == 0
        assert state(root, sweep.LOCAL_ONLY_SCAN_MARKER_REL)["last_round_status"] == "unavailable"
        assert state(root, sweep.PLAN_BACKPRESSURE_SCAN_MARKER_REL)["last_round_status"] == "scanned"

    @pytest.mark.parametrize("operation", ["MERGE_HEAD", "CHERRY_PICK_HEAD", "rebase-merge"])
    def test_unfinished_operation_stays_protected(self, case, operation):
        root, origin, peer, sent = case
        advance_remote(peer)
        cached = git(root, "rev-parse", "origin/master")
        marker = root / ".git" / operation
        marker.write_text(git(root, "rev-parse", "master"), encoding="utf-8")
        before = protected_snapshot(root, origin)
        assert sweep.main() == 0
        assert marker.exists()
        assert protected_snapshot(root, origin) == before
        assert git(root, "rev-parse", "origin/master") == cached
        assert state(root, sweep.LOCAL_ONLY_SCAN_MARKER_REL)["last_round_status"] == "unavailable"

    def test_checks_run_and_refresh_remote_without_committing_other_sessions(self, case):
        root, origin, peer, sent = case
        remote_head = advance_remote(peer)
        before = protected_snapshot(root, origin)
        assert sweep.main() == 0
        assert state(root, sweep.LOCAL_ONLY_SCAN_MARKER_REL)["last_round_status"] == "scanned"
        assert state(root, sweep.PLAN_BACKPRESSURE_SCAN_MARKER_REL)["last_round_status"] == "scanned"
        assert git(root, "rev-parse", "origin/master") == remote_head
        assert state(root, sweep.PLAN_BACKPRESSURE_STATE_REL).keys() == {"X1"}
        assert protected_snapshot(root, origin) == before
        assert git(root, "branch", "--show-current") == "business"

    def test_same_manager_recovers_once_and_deduplicates(self, case):
        root, origin, peer, sent = case
        old = "2026-10-16T00:00:00+00:00"
        seed(root, sweep.LOCAL_ONLY_UNSCANNED_STATE_REL, {sweep.LOCAL_ONLY_UNSCANNED_KEY: old})
        seed(root, sweep.PLAN_BACKPRESSURE_UNSCANNED_STATE_REL, {sweep.PLAN_BACKPRESSURE_UNSCANNED_KEY: old})
        assert sweep.main() == 0
        assert state(root, sweep.LOCAL_ONLY_UNSCANNED_STATE_REL) == {}
        assert state(root, sweep.PLAN_BACKPRESSURE_UNSCANNED_STATE_REL) == {}
        first = list(sent)
        assert len([text for text in first if text.startswith("✅")]) == 2
        assert sweep.main() == 0
        assert sent == first

    @pytest.mark.parametrize("lock", ["busy", "error", "index"])
    def test_lock_or_unreadable_lock_preserves_other_work_and_marks_unknown(self, case, lock):
        root, origin, peer, sent = case
        remote_head = advance_remote(peer)
        cached = git(root, "rev-parse", "origin/master")
        if lock == "index":
            path = root / ".git/index.lock"
            path.write_text("owned by another process", encoding="utf-8")
            old = time.time() - 3600
            os.utime(path, (old, old))
        else:
            (root / ".lock-status").write_text(lock, encoding="utf-8")
        before = protected_snapshot(root, origin)
        assert sweep.main() == 0
        assert git(root, "rev-parse", "origin/master") == cached != remote_head
        assert protected_snapshot(root, origin) == before
        if lock == "index":
            assert path.read_text(encoding="utf-8") == "owned by another process"
        assert state(root, sweep.LOCAL_ONLY_SCAN_MARKER_REL)["last_round_status"] == "unavailable"
        assert state(root, sweep.PLAN_BACKPRESSURE_SCAN_MARKER_REL)["last_round_status"] == "unavailable"
        assert not [text for text in sent if text.startswith("✅")]

    def test_failed_fetch_does_not_clear_existing_alert_from_cached_zero_counts(self, case):
        root, origin, peer, sent = case
        seed(root, sweep.LOCAL_ONLY_COMMIT_STATE_REL, {sweep.LOCAL_ONLY_AHEAD_KEY: "2026-10-16T00:00:00+00:00"})
        seed(root, sweep.LOCAL_ONLY_UNSCANNED_STATE_REL, {sweep.LOCAL_ONLY_UNSCANNED_KEY: "2026-10-16T00:00:00+00:00"})
        git(root, "remote", "set-url", "origin", str(root / "missing.git"))
        assert sweep.main() == 0
        assert state(root, sweep.LOCAL_ONLY_SCAN_MARKER_REL)["last_round_status"] == "unavailable"
        assert sweep.LOCAL_ONLY_AHEAD_KEY in state(root, sweep.LOCAL_ONLY_COMMIT_STATE_REL)
        assert sweep.LOCAL_ONLY_UNSCANNED_KEY in state(root, sweep.LOCAL_ONLY_UNSCANNED_STATE_REL)
        assert not [text for text in sent if text.startswith("✅") and "第 8 类" in text]

    @pytest.mark.parametrize("failure", ["missing_queue", "scanner_error", "bad_payload"])
    def test_failed_plan_read_does_not_report_zero_or_resolve(self, case, failure):
        root, origin, peer, sent = case
        old = "2026-10-16T00:00:00+00:00"
        seed(root, sweep.PLAN_BACKPRESSURE_STATE_REL, {"X1": old})
        seed(root, sweep.PLAN_BACKPRESSURE_UNSCANNED_STATE_REL, {sweep.PLAN_BACKPRESSURE_UNSCANNED_KEY: old})
        if failure == "missing_queue":
            (root / sweep.QUEUE_BUSINESS_PATH_REL).rename(root / "queue-preserved.md")
        else:
            content = "raise SystemExit('read denied')\n" if failure == "scanner_error" else "print('{\"unaccepted\":null}')\n"
            (root / sweep.PLAN_BACKPRESSURE_SCRIPT_REL).write_text(content, encoding="utf-8")
        assert sweep.main() == 0
        assert state(root, sweep.PLAN_BACKPRESSURE_SCAN_MARKER_REL)["last_round_status"] == "unavailable"
        assert "X1" in state(root, sweep.PLAN_BACKPRESSURE_STATE_REL)
        assert sweep.PLAN_BACKPRESSURE_UNSCANNED_KEY in state(root, sweep.PLAN_BACKPRESSURE_UNSCANNED_STATE_REL)
        assert not [text for text in sent if text.startswith("✅") and "规划倒逼" in text]

    def test_dry_run_reads_but_never_fetches_persists_or_notifies(self, case, monkeypatch, capsys):
        root, origin, peer, sent = case
        advance_remote(peer)
        before = protected_snapshot(root, origin)
        cached = git(root, "rev-parse", "origin/master")
        monkeypatch.setattr(sys, "argv", ["sweep", "--dry-run", "--verbose"])
        assert sweep.main() == 0
        text = capsys.readouterr().out
        assert "未 fetch" in text and "未核实" in text
        assert "X1" in text or "三处皆无 1" in text
        assert not (root / "reports").exists()
        assert git(root, "rev-parse", "origin/master") == cached
        assert protected_snapshot(root, origin) == before
        assert sent == []


class TestStandingObservationCoverage:
    def prepare(self, case, monkeypatch):
        root, origin, peer, sent = case
        if STANDING_RUNNER is not None:
            monkeypatch.setattr(sweep, '_observe_standing_checks', STANDING_RUNNER)
        # 只隔离取数边界，原状态机与发送边界捕获保持真实。
        safe = ["_check_claude_md_carrier_size", "_check_global_memory_files",
                "_check_editable_install_targets", "_check_unclosed_outputs",
                "_check_hooks_heartbeat", "_check_followup_pending_inventory",
                "_check_draft_gap_inventory", "_check_status_triage_and_ledger",
                "_check_scheduled_task_coverage", "_check_intake_gap_rows",
                "_check_unmerged_branch_backlog", "_check_aibot_audit_orphan_writes",
                "_check_outbox_relay_unreadable_visibility", "_check_carrier_consistency"]
        entered = []
        for name in safe:
            def check(repo, log, *args, _name=name, **kwargs):
                entered.append(_name)
                sweep._track_and_alert_standing_state(repo, _name, "reports/"+_name+".json",
                    {"real-candidate"}, 24, lambda _: "isolated candidate", lambda _: "resolved", log)
            monkeypatch.setattr(sweep, name, check)
        monkeypatch.setattr(sweep, "_observe_spec_gaps", lambda repo, log: None)
        monkeypatch.setattr(sweep, "_observe_stale_changes", lambda repo, log: None)
        monkeypatch.setattr(sweep, "_observe_carrier_lag", lambda repo, log: None)
        return root, origin, sent, entered, safe

    def test_non_master_enters_safe_checks_preserves_writes_and_deduplicates(self, case, monkeypatch):
        root, origin, sent, entered, safe = self.prepare(case, monkeypatch)
        before = protected_snapshot(root, origin)
        log = []
        monkeypatch.setattr(sweep, "_observe_non_master", lambda *args: None)
        assert sweep.main() == 0
        assert entered == safe
        assert_missing_health_is_reported(root, sent, (root / sweep.LOG_REL).read_text(encoding="utf8").splitlines(), 14)
        assert protected_snapshot(root, origin) == before
        delivered = list(sent)
        sweep._observe_standing_checks(root, "business", log, False)
        assert sent == delivered
        assert any("deduplicated=1" in line for line in log)

    def test_lock_reason_prevents_all_new_checks_and_publication(self, case, monkeypatch):
        root, origin, sent, entered, safe = self.prepare(case, monkeypatch)
        (root / ".lock-status").write_text("busy", encoding="utf-8")
        log = []
        sweep._observe_standing_checks(root, "business", log, False)
        assert entered == [] and sent == []
        assert any("skipped" in line and "共享编辑锁" in line for line in log)

    def test_queue_changes_after_collection_do_not_resolve_or_send(self, case, monkeypatch):
        root, origin, sent, entered, safe = self.prepare(case, monkeypatch)
        rel = "reports/" + safe[0] + ".json"
        seed(root, rel, {"old": "2026-10-16T00:00:00+00:00"})
        def changed(repo, log):
            sweep._track_and_alert_standing_state(repo, "candidate", rel, {"new"}, 24,
                lambda _: "new", lambda _: "old resolved", log)
            with (root / sweep.QUEUE_BUSINESS_PATH_REL).open("a", encoding="utf-8") as f:
                f.write("concurrent writer\n")
        monkeypatch.setattr(sweep, safe[0], changed)
        log = []
        sweep._observe_standing_checks(root, "business", log, False)
        assert state(root, rel) == {"old": "2026-10-16T00:00:00+00:00"}
        assert not [s for s in sent if s in ("new", "old resolved")]
        assert any("unavailable" in line and "队列" in line for line in log)

    def test_one_read_failure_does_not_hide_later_candidates(self, case, monkeypatch):
        root, origin, sent, entered, safe = self.prepare(case, monkeypatch)
        def fail(repo, log):
            raise OSError("isolated read denied")
        monkeypatch.setattr(sweep, safe[0], fail)
        log = []
        sweep._observe_standing_checks(root, "business", log, False)
        assert entered == safe[1:]
        assert_missing_health_is_reported(root, sent, log, 13)
        assert any("unavailable" in s and "isolated read denied" in s for s in log)

    def test_dry_run_never_calls_possible_senders(self, case, monkeypatch):
        root, origin, sent, entered, safe = self.prepare(case, monkeypatch)
        sweep._observe_standing_checks(root, "business", [], True)
        assert entered == [] and sent == []

    def test_partial_read_keeps_old_alerts_but_publishes_known_candidate(self, case, monkeypatch):
        root, origin, sent, entered, safe = self.prepare(case, monkeypatch)
        rel = "reports/"+safe[0]+".json"
        seed(root, rel, {"old": "2026-10-16T00:00:00+00:00"})
        def partial(repo, log):
            log.append("读取失败，不据此判为干净")
            sweep._track_and_alert_standing_state(repo, "partial", rel, {"known"}, 24,
                lambda _: "known candidate", lambda _: "wrong resolution", log)
        monkeypatch.setattr(sweep, safe[0], partial)
        log = []
        sweep._observe_standing_checks(root, "business", log, False)
        assert set(state(root, rel)) == {"old", "known"}
        assert "known candidate" in sent and "wrong resolution" not in sent
        assert any("unavailable" in s for s in log)

    def test_sender_failure_is_visible_beside_candidate_count(self, case, monkeypatch):
        root, origin, sent, entered, safe = self.prepare(case, monkeypatch)
        attempts = []
        def failed_sender(url, text):
            attempts.append(text)
            raise OSError("isolated sender denied")
        monkeypatch.setattr(sweep, "_send_wecom_markdown", failed_sender)
        log = []
        sweep._observe_standing_checks(root, "business", log, False)
        assert any("candidate_count=1" in s for s in log)
        assert any("status=unknown" in s and "isolated sender denied" in s for s in log)
        assert not state(root, "reports/" + safe[0] + ".json")
        progress = state(root, "reports/" + safe[0] + ".delivery.json")["alert"]
        assert progress["status"] == "unknown"
        assert progress["in_flight"] == 0 and progress["acked"] == {}
        first_attempts = list(attempts)
        sweep._observe_standing_checks(root, "business", [], False)
        assert attempts == first_attempts



from _sweep_test_receipts import receipt_sender
_accepted_test_receipt=receipt_sender(sweep)
_rejected_test_receipt=receipt_sender(sweep,40058)


class TestNotificationDelivery:
    @pytest.fixture
    def delivery(self,tmp_path,monkeypatch):
        sent=[]
        now=[sweep.datetime(2026,10,18,0,0,tzinfo=sweep.timezone.utc)]
        class Clock(sweep.datetime):
            @classmethod
            def now(cls,tz=None):return now[0]
        monkeypatch.setattr(sweep,"datetime",Clock)
        monkeypatch.setattr(sweep,"_load_webhook_url",lambda _:"https://example.invalid/mocked")
        monkeypatch.setattr(sweep,"_send_wecom_markdown",lambda url,text:(sent.append(text),_accepted_test_receipt(url,text))[1])
        return tmp_path,sent,now

    def notify(self,root,text,keys={"a","b"}):
        log=[]
        sweep._track_and_alert_standing_state(root,"隔离测试","reports/test-state.json",keys,24,
            lambda _:text,lambda _:"已解除",log)
        return log

    def test_utf8_chinese_links_and_fences_are_preserved_without_oversize(self,delivery):
        root,sent,now=delivery
        content="总数30项\n" + ("风险中文"*150+" [完整链接](https://example.invalid/路径)\n")*10+"```\n命令示例\n```\n"
        self.notify(root,content)
        assert len(sent)>1
        assert all(len(s.encode("utf-8"))<=4096 for s in sent)
        report=(root/"reports/test-state.alert.md").read_text(encoding="utf-8")
        assert report==content
        assert all(s.count("```")%2==0 for s in sent)
        assert sum(s.count("[完整链接](https://example.invalid/路径)") for s in sent)==10
        assert all("总项 2" in s and "test-state.alert.md" in s for s in sent)

    def test_4096_utf8_bytes_pass_and_4097_are_split(self,delivery):
        root,sent,now=delivery
        exact="中"*1365+"x"
        assert len(exact.encode("utf-8"))==4096
        self.notify(root,exact)
        assert sent==[exact]
        sent.clear()
        self.notify(root,exact+"y",{"new"})
        assert len(sent)>1 and all(len(s.encode("utf-8"))<=4096 for s in sent)

    def test_40058_does_not_mark_success_and_retries_after_existing_interval(self,delivery,monkeypatch):
        root,sent,now=delivery
        def rejected(url,text):return _rejected_test_receipt(url,text)
        monkeypatch.setattr(sweep,"_send_wecom_markdown",rejected)
        log=self.notify(root,"真实候选的隔离替身")
        assert state(root,"reports/test-state.json")=={}
        progress=state(root,"reports/test-state.delivery.json")
        assert progress["alert"]["status"]=="failed"
        assert any("40058" in s for s in log)
        monkeypatch.setattr(sweep,"_send_wecom_markdown",lambda url,text:(sent.append(text),_accepted_test_receipt(url,text))[1])
        self.notify(root,"真实候选的隔离替身")
        assert sent==[]
        now[0]+=sweep.timedelta(hours=24,seconds=1)
        self.notify(root,"真实候选的隔离替身")
        assert len(sent)==1 and set(state(root,"reports/test-state.json"))=={"a","b"}
        self.notify(root,"真实候选的隔离替身")
        assert len(sent)==1

    def test_partial_success_does_not_resend_acknowledged_segment(self,delivery,monkeypatch):
        root,sent,now=delivery
        content=("一条完整风险说明"*100+"\n")*10
        def sender(url,text):
            if len(sent)==1:return _rejected_test_receipt(url,text)
            sent.append(text)
            return _accepted_test_receipt(url,text)
        monkeypatch.setattr(sweep,"_send_wecom_markdown",sender)
        self.notify(root,content)
        assert len(sent)==1 and state(root,"reports/test-state.json")=={}
        first=sent[0]
        now[0]+=sweep.timedelta(hours=24,seconds=1)
        monkeypatch.setattr(sweep,"_send_wecom_markdown",lambda url,text:(sent.append(text),_accepted_test_receipt(url,text))[1])
        self.notify(root,content)
        assert sent.count(first)==1
        assert set(state(root,"reports/test-state.json"))=={"a","b"}

    def test_failed_resolution_keeps_old_success_record(self,delivery,monkeypatch):
        root,sent,now=delivery
        self.notify(root,"候选")
        old=state(root,"reports/test-state.json")
        monkeypatch.setattr(sweep,"_send_wecom_markdown",lambda *args:(_ for _ in ()).throw(RuntimeError("errcode=40058")))
        self.notify(root,"候选",set())
        assert state(root,"reports/test-state.json")==old

    def test_zero_unavailable_is_not_a_scan_failure(self):
        assert not sweep._standing_observation_incomplete(["· 映射12条，判据不可用 0 项"],[])
        assert sweep._standing_observation_incomplete(["· 映射11条，判据不可用 1 项"],[])
        assert sweep._standing_observation_incomplete(["读取失败，不据此判为合规"],[])

    def test_raw_sender_requires_explicit_platform_ack(self,monkeypatch):
        class Response:
            def __enter__(self):return self
            def __exit__(self,*args):pass
            def read(self):return b'{}'
        monkeypatch.setattr(sweep.urllib.request,"urlopen",lambda *args,**kwargs:Response())
        with pytest.raises(RuntimeError):
            sweep._send_wecom_markdown("https://example.invalid/mocked","候选")

    def test_retry_uses_original_partial_body_when_only_rendered_detail_changes(self,delivery,monkeypatch):
        root,sent,now=delivery
        content=("同一批风险详情"*100+"\n")*10
        def sender(url,text):
            if len(sent)==1:return _rejected_test_receipt(url,text)
            sent.append(text)
            return _accepted_test_receipt(url,text)
        monkeypatch.setattr(sweep,"_send_wecom_markdown",sender)
        self.notify(root,content)
        first=sent[0]
        now[0]+=sweep.timedelta(hours=24,seconds=1)
        monkeypatch.setattr(sweep,"_send_wecom_markdown",lambda url,text:(sent.append(text),_accepted_test_receipt(url,text))[1])
        self.notify(root,content+"天数变动")
        assert sent.count(first)==1
        assert all("天数变动" not in p for p in sent)
        assert set(state(root,"reports/test-state.json"))=={"a","b"}

    def test_process_interruption_leaves_unknown_without_automatic_duplicate(self,delivery,monkeypatch):
        root,sent,now=delivery
        def interrupted(*args):raise KeyboardInterrupt()
        monkeypatch.setattr(sweep,"_send_wecom_markdown",interrupted)
        with pytest.raises(KeyboardInterrupt):self.notify(root,"候选")
        monkeypatch.setattr(sweep,"_send_wecom_markdown",lambda url,text:(sent.append(text),_accepted_test_receipt(url,text))[1])
        now[0]+=sweep.timedelta(hours=25)
        log=self.notify(root,"候选")
        assert not sent and state(root,"reports/test-state.json")=={}
        assert any("status=unknown" in line for line in log)

    def test_unreadable_delivery_history_never_becomes_empty_success(self,delivery):
        root,sent,now=delivery
        (root/"reports").mkdir()
        (root/"reports/test-state.delivery.json").write_text("broken",encoding="utf-8")
        log=self.notify(root,"候选")
        assert not sent and state(root,"reports/test-state.json")=={}
        assert any("未核实" in line for line in log)

    def test_no_channel_never_records_success(self,delivery,monkeypatch):
        root,sent,now=delivery
        monkeypatch.setattr(sweep,"_load_webhook_url",lambda root:None)
        self.notify(root,"候选")
        assert not sent and state(root,"reports/test-state.json")=={}

    def test_large_command_is_kept_in_report_without_partial_command_send(self,delivery):
        root,sent,now=delivery
        command="python append --value '"+"完整草稿"*500+"'"
        body="总数2项，两个风险仍待处置\n```\n"+command+"\n```\n"
        self.notify(root,body)
        assert (root/"reports/test-state.alert.md").read_text(encoding="utf-8")==body
        assert all(len(part.encode("utf-8"))<=4096 for part in sent)
        assert any("两个风险仍待处置" in part and "完整报告" in part for part in sent)
        assert all("python append" not in part for part in sent)

    def test_raw_sender_rejects_oversize_before_network_and_platform_40058(self,monkeypatch):
        requests=[]
        class Response:
            def __enter__(self):return self
            def __exit__(self,*args):pass
            def read(self):return b'{"errcode":40058,"errmsg":"too long"}'
        monkeypatch.setattr(sweep.urllib.request,"urlopen",lambda *args,**kwargs:requests.append(args) or Response())
        with pytest.raises(ValueError):sweep._send_wecom_markdown("https://example.invalid/mocked","中"*1366)
        assert not requests
        with pytest.raises(RuntimeError,match="40058"):
            sweep._send_wecom_markdown("https://example.invalid/mocked","候选")

    def test_actual_class6_mapping_healthy_and_unavailable_remain_distinct(self,delivery,monkeypatch):
        root,sent,now=delivery
        sp=root/"site-packages"
        sp.mkdir()
        target=root/"5-平台底座/zhuopin_platform/zhuopin_platform"
        target.mkdir(parents=True)
        (sp/"__editable___probe_finder.py").write_text("MAPPING = "+repr({"zhuopin_platform":str(target)})+"\n",encoding="utf-8")
        monkeypatch.setattr(sweep,"_site_packages_dirs",lambda:([sp],None))
        context={"collecting":True,"pending":[]}
        monkeypatch.setattr(sweep,"_STANDING_OBSERVATION",context)
        log=[]
        sweep._check_editable_install_targets(root,log)
        assert any("判据不可用 0 项" in line for line in log)
        assert not sweep._standing_observation_incomplete(log,context["pending"])
        monkeypatch.setattr(sweep,"_site_packages_dirs",lambda:([],"读取失败"))
        context["pending"].clear()
        log=[]
        sweep._check_editable_install_targets(root,log)
        assert sweep._standing_observation_incomplete(log,context["pending"])


def test_review_resolution_never_claims_formal_archive(tmp_path, monkeypatch):
    rendered=[]
    def capture(root,label,state,keys,interval,alert,resolved,log):
        rendered.append(resolved(['reviewed-with-real-tail']))
    monkeypatch.setattr(sweep,'_track_and_alert_standing_state',capture)
    sweep._announce_stale_in_flight_changes(tmp_path,[],[])
    assert len(rendered)==1
    assert '复核确认' in rendered[0]
    assert '不代表正式归档' in rendered[0]
