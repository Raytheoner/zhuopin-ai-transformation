"""工具-Token用量度量.py 单测（队列 §一 `#580`，`OP-0916-T`）。

mock 先行：本文件不读任何真实 `~/.claude/projects` 日志，全部用 `_write_jsonl()`
在 `tmp_path` 里按真实观察到的字段形态（`type`/`timestamp`/`requestId`/
`message.model`/`message.usage`/`message.content`）当场造夹具。

🔴 本文件最要紧的一条：`test_同一requestId多行去重取末条`——工具要治的病就是
「同一 requestId 的多个 content block 各占一行、每行都重复整条 usage」，
去重逻辑一旦退化成「按行计数」，请求数与 token 汇总会被内容块数放大好几倍。
"""
from __future__ import annotations

import importlib.util
import json
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

SCRIPT = Path(__file__).resolve().with_name("工具-Token用量度量.py")
_spec = importlib.util.spec_from_file_location("token_usage_meter", SCRIPT)
token_usage_meter = importlib.util.module_from_spec(_spec)
sys.modules["token_usage_meter"] = token_usage_meter
_spec.loader.exec_module(token_usage_meter)


def _assistant(ts, request_id, message_id, model, content_block, usage):
    return {
        "type": "assistant",
        "timestamp": ts,
        "sessionId": "sess-1",
        "requestId": request_id,
        "message": {
            "id": message_id,
            "model": model,
            "role": "assistant",
            "content": [content_block],
            "usage": usage,
        },
    }


def _user(ts, text):
    return {"type": "user", "timestamp": ts, "sessionId": "sess-1",
            "message": {"role": "user", "content": text}}


def _tool_result_user(ts):
    return {"type": "user", "timestamp": ts, "sessionId": "sess-1",
            "message": {"role": "user", "content": [
                {"type": "tool_result", "tool_use_id": "x", "content": "ok"}]}}


def _write_jsonl(path: Path, records: list) -> None:
    with open(path, "w", encoding="utf-8") as fh:
        for rec in records:
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")


class TokenUsageMeterTests(unittest.TestCase):
    def setUp(self):
        self._tmp = TemporaryDirectory()
        self.root = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def _scan_one(self, records, basis="utc"):
        gaps: dict = {}
        gap_samples: dict = {}
        from collections import defaultdict
        gaps = defaultdict(int)
        gap_samples = defaultdict(list)
        f = self.root / "sess-1.jsonl"
        _write_jsonl(f, records)
        sess = token_usage_meter.scan_file(f, basis, gaps, gap_samples)
        return sess, gaps

    # ---------------- 🔴 核心：同一 requestId 去重取末条 ----------------

    def test_同一requestId多行去重取末条(self):
        usage_1 = {"input_tokens": 2, "cache_creation_input_tokens": 100,
                   "cache_read_input_tokens": 50, "output_tokens": 171}
        records = [
            _user("2026-09-10T01:00:00Z", "第一条用户消息，用于取标题"),
            _assistant("2026-09-10T01:00:01Z", "req-A", "msg-A", "claude-opus-5",
                       {"type": "thinking", "thinking": "..."}, usage_1),
            _assistant("2026-09-10T01:00:02Z", "req-A", "msg-A", "claude-opus-5",
                       {"type": "tool_use", "id": "t1", "name": "Bash",
                        "input": {"command": "ls"}}, usage_1),
        ]
        sess, gaps = self._scan_one(records)
        reqs = sess.ordered_requests()
        # 两行共享 req-A —— 去重后只应有 1 条请求，而不是 2 条
        self.assertEqual(len(reqs), 1)
        self.assertEqual(reqs[0].input_tokens, 2)
        self.assertEqual(reqs[0].cache_read, 50)
        # 但 tool_use 块本身要如实计数（1 次 Bash 调用），不能被去重掉
        self.assertEqual(len(sess.tool_calls), 1)
        self.assertEqual(sess.tool_calls[0].name, "Bash")

    def test_同一requestId三行不同usage仅末条生效(self):
        """人为构造 usage 递增的三行，验证生效的是最后一行而非第一行或求和。"""
        records = [
            _assistant("2026-09-10T01:00:00Z", "req-B", "msg-B", "claude-sonnet-5",
                       {"type": "thinking", "thinking": "a"},
                       {"input_tokens": 1, "cache_creation_input_tokens": 1,
                        "cache_read_input_tokens": 1, "output_tokens": 1}),
            _assistant("2026-09-10T01:00:01Z", "req-B", "msg-B", "claude-sonnet-5",
                       {"type": "text", "text": "b"},
                       {"input_tokens": 1, "cache_creation_input_tokens": 1,
                        "cache_read_input_tokens": 1, "output_tokens": 50}),
            _assistant("2026-09-10T01:00:02Z", "req-B", "msg-B", "claude-sonnet-5",
                       {"type": "text", "text": "c"},
                       {"input_tokens": 1, "cache_creation_input_tokens": 1,
                        "cache_read_input_tokens": 1, "output_tokens": 999}),
        ]
        sess, _ = self._scan_one(records)
        reqs = sess.ordered_requests()
        self.assertEqual(len(reqs), 1)
        self.assertEqual(reqs[0].output_tokens, 999)  # 末条，不是求和(1050)也不是首条(1)

    def test_requestId缺失时用messageId兜底(self):
        rec = _assistant("2026-09-10T01:00:00Z", None, "msg-only-id", "claude-opus-5",
                         {"type": "text", "text": "x"},
                         {"input_tokens": 5, "cache_creation_input_tokens": 0,
                          "cache_read_input_tokens": 0, "output_tokens": 5})
        del rec["requestId"]
        sess, _ = self._scan_one([rec])
        reqs = sess.ordered_requests()
        self.assertEqual(len(reqs), 1)
        self.assertEqual(reqs[0].input_tokens, 5)

    # ---------------- 首条用户消息（跳过 tool_result 形态） ----------------

    def test_首条用户消息跳过tool_result取真实文本(self):
        records = [
            _tool_result_user("2026-09-10T00:59:00Z"),
            _user("2026-09-10T01:00:00Z", "这是真正的第一条人类输入" * 5),
            _assistant("2026-09-10T01:00:01Z", "req-C", "msg-C", "claude-opus-5",
                       {"type": "text", "text": "ok"},
                       {"input_tokens": 1, "cache_creation_input_tokens": 0,
                        "cache_read_input_tokens": 0, "output_tokens": 1}),
        ]
        sess, _ = self._scan_one(records)
        self.assertTrue(sess.first_user_text.startswith("这是真正的第一条人类输入"))

    # ---------------- 窗口聚合：开场底噪只认窗口内新起会话 ----------------

    def test_开场底噪只计入窗口内新起会话(self):
        usage = {"input_tokens": 10, "cache_creation_input_tokens": 20,
                 "cache_read_input_tokens": 30, "output_tokens": 5}
        # 会话真实首条请求在窗口之前 -> 不应计入开场底噪
        records = [
            _assistant("2026-09-05T01:00:00Z", "req-old", "msg-old", "claude-opus-5",
                       {"type": "text", "text": "old"}, usage),
            _assistant("2026-09-10T01:00:00Z", "req-new", "msg-new", "claude-opus-5",
                       {"type": "text", "text": "new"}, usage),
        ]
        sess, _ = self._scan_one(records)
        agg = token_usage_meter.Aggregate(
            since=token_usage_meter.date(2026, 9, 6), until=token_usage_meter.date(2026, 9, 13))
        token_usage_meter.aggregate_session(sess, agg)
        self.assertEqual(len(agg.opening_noise), 0)
        # 但窗口内的那条请求仍应计入按日按模型汇总
        self.assertEqual(agg.daily_model[(token_usage_meter.date(2026, 9, 10), "claude-opus-5")]["requests"], 1)

    def test_开场底噪计入窗口内新起会话(self):
        usage = {"input_tokens": 10, "cache_creation_input_tokens": 20,
                 "cache_read_input_tokens": 30, "output_tokens": 5}
        records = [
            _assistant("2026-09-10T01:00:00Z", "req-new2", "msg-new2", "claude-opus-5",
                       {"type": "text", "text": "new"}, usage),
        ]
        sess, _ = self._scan_one(records)
        agg = token_usage_meter.Aggregate(
            since=token_usage_meter.date(2026, 9, 6), until=token_usage_meter.date(2026, 9, 13))
        token_usage_meter.aggregate_session(sess, agg)
        self.assertEqual(agg.opening_noise, [60])  # 10+20+30

    # ---------------- 机制税与看护会话识别 ----------------

    def test_机制税命中白名单脚本(self):
        usage = {"input_tokens": 1, "cache_creation_input_tokens": 0,
                 "cache_read_input_tokens": 0, "output_tokens": 1}
        records = [
            _assistant("2026-09-10T01:00:00Z", "req-1", "m1", "claude-opus-5",
                       {"type": "tool_use", "id": "t1", "name": "Bash",
                        "input": {"command": "python 0-学习与工具/工具-队列查询.py --row 1"}},
                       usage),
            _assistant("2026-09-10T01:00:01Z", "req-2", "m2", "claude-opus-5",
                       {"type": "tool_use", "id": "t2", "name": "Bash",
                        "input": {"command": "pytest -q"}}, usage),
        ]
        sess, _ = self._scan_one(records)
        agg = token_usage_meter.Aggregate(
            since=token_usage_meter.date(2026, 9, 6), until=token_usage_meter.date(2026, 9, 13))
        token_usage_meter.aggregate_session(sess, agg)
        self.assertEqual(agg.bash_total, 2)
        self.assertEqual(agg.bash_mechanism_hits, 1)

    def test_看护会话超阈值被识别(self):
        usage = {"input_tokens": 1, "cache_creation_input_tokens": 0,
                 "cache_read_input_tokens": 0, "output_tokens": 1}
        records = []
        # 4 次 Bash 调用，3 次命中看护关键词 -> 75% > 30% 阈值
        for i, cmd in enumerate(["check-heartbeat foo", "check-timeout bar",
                                  "summary baz", "ls -la"]):
            records.append(_assistant(
                f"2026-09-10T01:00:0{i}Z", f"req-{i}", f"m{i}", "claude-opus-5",
                {"type": "tool_use", "id": f"t{i}", "name": "Bash",
                 "input": {"command": cmd}}, usage))
        sess, _ = self._scan_one(records)
        agg = token_usage_meter.Aggregate(
            since=token_usage_meter.date(2026, 9, 6), until=token_usage_meter.date(2026, 9, 13))
        token_usage_meter.aggregate_session(sess, agg)
        self.assertEqual(len(agg.watcher_sessions), 1)
        self.assertAlmostEqual(agg.watcher_sessions[0]["ratio"], 0.75)

    # ---------------- 子泳道拆链（`#580` 合入前修复 ⑴） ----------------

    def test_子泳道文件与主会话不再撞session_id(self):
        """子泳道 jsonl（`<父会话>/subagents/*.jsonl`）行内 `sessionId` 字段
        与主会话共享同一个值——若直接拿它当链标识，主链与子泳道会在报告里
        挤成同一行（`#580` 实撞：45649529 一个 session_id 下混进 11 行，实为
        1 条主链 + 10 条子泳道）。链标识须改按文件路径算，二者不能相等。"""
        main_file = self.root / "PARENTID.jsonl"
        sub_dir = self.root / "PARENTID" / "subagents"
        sub_dir.mkdir(parents=True)
        sub_file = sub_dir / "agent-xyz.jsonl"
        usage = {"input_tokens": 1, "cache_creation_input_tokens": 0,
                 "cache_read_input_tokens": 0, "output_tokens": 1}
        main_rec = _assistant("2026-09-10T01:00:00Z", "req-main", "m-main", "claude-opus-5",
                              {"type": "text", "text": "x"}, usage)
        main_rec["sessionId"] = "PARENTID"
        _write_jsonl(main_file, [main_rec])
        sub_rec = _assistant("2026-09-10T01:00:00Z", "req-sub", "m-sub", "claude-opus-5",
                             {"type": "text", "text": "y"}, usage)
        sub_rec["sessionId"] = "PARENTID"  # 子泳道行内 sessionId 与主会话相同
        _write_jsonl(sub_file, [sub_rec])

        from collections import defaultdict
        gaps, gap_samples = defaultdict(int), defaultdict(list)
        main_sess = token_usage_meter.scan_file(main_file, "utc", gaps, gap_samples)
        sub_sess = token_usage_meter.scan_file(sub_file, "utc", gaps, gap_samples)

        self.assertNotEqual(main_sess.session_id, sub_sess.session_id)
        self.assertEqual(main_sess.chain_type, "主链")
        self.assertEqual(sub_sess.chain_type, "子泳道")
        self.assertEqual(main_sess.parent_session_id, "PARENTID")
        self.assertEqual(sub_sess.parent_session_id, "PARENTID")

    def test_按父会话合计主链与子泳道相加(self):
        main_file = self.root / "PID2.jsonl"
        sub_dir = self.root / "PID2" / "subagents"
        sub_dir.mkdir(parents=True)
        sub_file = sub_dir / "agent-abc.jsonl"
        usage_main = {"input_tokens": 10, "cache_creation_input_tokens": 0,
                      "cache_read_input_tokens": 0, "output_tokens": 0}
        usage_sub = {"input_tokens": 20, "cache_creation_input_tokens": 0,
                     "cache_read_input_tokens": 0, "output_tokens": 0}
        _write_jsonl(main_file, [_assistant("2026-09-10T01:00:00Z", "req-m", "m-m",
                                            "claude-opus-5", {"type": "text", "text": "m"}, usage_main)])
        _write_jsonl(sub_file, [_assistant("2026-09-10T01:00:00Z", "req-s", "m-s",
                                           "claude-opus-5", {"type": "text", "text": "s"}, usage_sub)])
        from collections import defaultdict
        gaps, gap_samples = defaultdict(int), defaultdict(list)
        main_sess = token_usage_meter.scan_file(main_file, "utc", gaps, gap_samples)
        sub_sess = token_usage_meter.scan_file(sub_file, "utc", gaps, gap_samples)
        agg = token_usage_meter.Aggregate(
            since=token_usage_meter.date(2026, 9, 6), until=token_usage_meter.date(2026, 9, 13))
        token_usage_meter.aggregate_session(main_sess, agg)
        token_usage_meter.aggregate_session(sub_sess, agg)
        self.assertEqual(len(agg.session_rows), 2)  # 两条链分开列，不塌成一行
        parent_bucket = agg.parent_totals["PID2"]
        self.assertEqual(parent_bucket["chains"], 2)
        self.assertEqual(parent_bucket["total_tokens"], 30)  # 10 + 20 合计

    # ---------------- 看护识别判据改法（`#580` 合入前修复 ⑵） ----------------
    # 原判据只认「Bash 命中 check-heartbeat|check-timeout|summary 占比 >
    # 30%」，路线图 §〇 实测标题含「看护」的 24 条链（cache_read 占比
    # 14.4%）被工具识别为 0——以下用 OP-0909-Q／OP-0907-Y／OP-0907-R 三条真实
    # 看护链的典型形态做夹具式断言（只断言识别结果，不入库真实日志内容）。

    def test_看护识别_标题含看护即命中(self):
        usage = {"input_tokens": 1, "cache_creation_input_tokens": 0,
                 "cache_read_input_tokens": 0, "output_tokens": 1}
        records = [
            _user("2026-09-10T00:59:00Z", "[OP-0907-Y]【CC】看护 OP-0907-X 泳道进度"),
            _assistant("2026-09-10T01:00:00Z", "req-1", "m1", "claude-sonnet-5",
                       {"type": "tool_use", "id": "t1", "name": "Bash",
                        "input": {"command": "ls"}}, usage),
        ]
        sess, _ = self._scan_one(records)
        agg = token_usage_meter.Aggregate(
            since=token_usage_meter.date(2026, 9, 6), until=token_usage_meter.date(2026, 9, 13))
        token_usage_meter.aggregate_session(sess, agg)
        self.assertEqual(len(agg.watcher_sessions), 1)
        self.assertEqual(agg.watcher_sessions[0]["reason"], "标题含看护")

    def test_看护识别_泳道看护状态机脚本命中(self):
        usage = {"input_tokens": 1, "cache_creation_input_tokens": 0,
                 "cache_read_input_tokens": 0, "output_tokens": 1}
        records = []
        cmds = ["python 0-学习与工具/工具-泳道看护状态机.py heartbeat --lane op0907r --text a",
                "python 0-学习与工具/工具-泳道看护状态机.py heartbeat --lane op0907r --text b",
                "ls -la", "pytest -q"]
        for i, cmd in enumerate(cmds):
            records.append(_assistant(
                f"2026-09-10T01:00:0{i}Z", f"req-{i}", f"m{i}", "claude-sonnet-5",
                {"type": "tool_use", "id": f"t{i}", "name": "Bash",
                 "input": {"command": cmd}}, usage))
        sess, _ = self._scan_one(records)
        agg = token_usage_meter.Aggregate(
            since=token_usage_meter.date(2026, 9, 6), until=token_usage_meter.date(2026, 9, 13))
        token_usage_meter.aggregate_session(sess, agg)
        self.assertEqual(len(agg.watcher_sessions), 1)
        self.assertEqual(agg.watcher_sessions[0]["reason"], "Bash占比")

    def test_看护识别_laneheartbeat轮询命令命中(self):
        """`Get-Content …lane-heartbeat…` 轮询命令靠 `heartbeat` 子串命中，
        覆盖原正则漏掉的 `lane-heartbeat` 变体。"""
        usage = {"input_tokens": 1, "cache_creation_input_tokens": 0,
                 "cache_read_input_tokens": 0, "output_tokens": 1}
        records = []
        cmds = ["Get-Content reports/lane-heartbeat/op0907r.md -Tail 5",
                "Get-Content reports/lane-heartbeat/op0907r.md -Tail 5",
                "Get-Content reports/lane-heartbeat/op0907r.md -Tail 5",
                "git status"]
        for i, cmd in enumerate(cmds):
            records.append(_assistant(
                f"2026-09-10T01:00:0{i}Z", f"req-{i}", f"m{i}", "claude-sonnet-5",
                {"type": "tool_use", "id": f"t{i}", "name": "Bash",
                 "input": {"command": cmd}}, usage))
        sess, _ = self._scan_one(records)
        agg = token_usage_meter.Aggregate(
            since=token_usage_meter.date(2026, 9, 6), until=token_usage_meter.date(2026, 9, 13))
        token_usage_meter.aggregate_session(sess, agg)
        self.assertEqual(len(agg.watcher_sessions), 1)

    def test_看护识别_标题判据只看前60字不搜全文(self):
        """派单 opener 正文里普遍带「派出线：… ｜ 看护者 OP-xxx」溯源尾注——
        若标题判据搜索首条用户消息全文，会把绝大多数建造类主链也误判成看护
        链（曾实测：命中 123／177 条、cache_read 占比 67.3%，与 §〇 人工基线
        「24 条／14.4%」严重不符）。判据须只看前 60 字（同 §二 展示口径）。"""
        usage = {"input_tokens": 1, "cache_creation_input_tokens": 0,
                 "cache_read_input_tokens": 0, "output_tokens": 1}
        padding = "填充字符占位到六十字之外" * 6  # 纯填充，把「看护」挤出前 60 字窗口
        long_body = f"[OP-0916-X]【CC】某建造任务标题 {padding} 派出线：Cowork 环境总线 OP-0916-T ／ 看护者 OP-0916-W"
        self.assertNotIn("看护", long_body[:60])
        self.assertIn("看护", long_body)
        records = [
            _user("2026-09-10T00:59:00Z", long_body),
            _assistant("2026-09-10T01:00:00Z", "req-1", "m1", "claude-sonnet-5",
                       {"type": "tool_use", "id": "t1", "name": "Bash",
                        "input": {"command": "ls"}}, usage),
        ]
        sess, _ = self._scan_one(records)
        agg = token_usage_meter.Aggregate(
            since=token_usage_meter.date(2026, 9, 6), until=token_usage_meter.date(2026, 9, 13))
        token_usage_meter.aggregate_session(sess, agg)
        self.assertEqual(len(agg.watcher_sessions), 0)

    def test_看护会话未超阈值不识别(self):
        usage = {"input_tokens": 1, "cache_creation_input_tokens": 0,
                 "cache_read_input_tokens": 0, "output_tokens": 1}
        records = []
        for i, cmd in enumerate(["check-heartbeat foo", "ls", "pytest", "grep x"]):
            records.append(_assistant(
                f"2026-09-10T01:00:0{i}Z", f"req-{i}", f"m{i}", "claude-opus-5",
                {"type": "tool_use", "id": f"t{i}", "name": "Bash",
                 "input": {"command": cmd}}, usage))
        sess, _ = self._scan_one(records)
        agg = token_usage_meter.Aggregate(
            since=token_usage_meter.date(2026, 9, 6), until=token_usage_meter.date(2026, 9, 13))
        token_usage_meter.aggregate_session(sess, agg)
        self.assertEqual(len(agg.watcher_sessions), 0)

    # ---------------- 缺口：非法 JSON 行如实计数、不崩溃 ----------------

    def test_非法json行计入缺口且不中断扫描(self):
        f = self.root / "sess-bad.jsonl"
        good = _assistant("2026-09-10T01:00:00Z", "req-x", "m-x", "claude-opus-5",
                          {"type": "text", "text": "x"},
                          {"input_tokens": 1, "cache_creation_input_tokens": 0,
                           "cache_read_input_tokens": 0, "output_tokens": 1})
        with open(f, "w", encoding="utf-8") as fh:
            fh.write("{this is not json\n")
            fh.write(json.dumps(good, ensure_ascii=False) + "\n")
        from collections import defaultdict
        gaps = defaultdict(int)
        gap_samples = defaultdict(list)
        sess = token_usage_meter.scan_file(f, "utc", gaps, gap_samples)
        self.assertEqual(gaps["bad_json"], 1)
        self.assertEqual(len(sess.ordered_requests()), 1)

    # ---------------- 百分位 ----------------

    def test_percentile_p50_p95(self):
        vals = list(range(1, 101))  # 1..100
        self.assertAlmostEqual(token_usage_meter.percentile(vals, 0.50), 50.5, delta=1)
        self.assertGreaterEqual(token_usage_meter.percentile(vals, 0.95), 95)

    def test_percentile_空列表返回零(self):
        self.assertEqual(token_usage_meter.percentile([], 0.50), 0.0)


class FindRepoRootTests(unittest.TestCase):
    """`#580` 合入前修复 ⑶：`--out` 缺省须解到主工作区 `reports/`，不能解到
    当前 worktree 自己那份 checkout（worktree 收工被删时报告会随之丢失，
    2026-09-16 09:14 实撞）。"""

    def test_解析到git_common_dir的父目录(self):
        import subprocess
        result = subprocess.run(
            ["git", "rev-parse", "--path-format=absolute", "--git-common-dir"],
            cwd=SCRIPT.parent, capture_output=True, text=True, check=True)
        expected = Path(result.stdout.strip()).parent
        got = token_usage_meter.find_repo_root(SCRIPT)
        self.assertEqual(got.resolve(), expected.resolve())


class TokenUsageMeterCLITests(unittest.TestCase):
    """走 main() 全流程，验证报告与 JSON 落盘、CLI 参数校验。"""

    def setUp(self):
        self._tmp = TemporaryDirectory()
        self.root = Path(self._tmp.name) / "projects"
        self.root.mkdir(parents=True)
        self.repo_root = Path(self._tmp.name) / "repo"
        (self.repo_root / "0-学习与工具").mkdir(parents=True)
        (self.repo_root / "CLAUDE.md").write_text("x", encoding="utf-8")
        usage = {"input_tokens": 10, "cache_creation_input_tokens": 5,
                 "cache_read_input_tokens": 1, "output_tokens": 2}
        records = [
            _user("2026-09-10T01:00:00Z", "opener 正文，用于标题截取测试用例长度超过六十字这是补足长度的填充文字"),
            _assistant("2026-09-10T01:00:01Z", "req-1", "m1", "claude-opus-5",
                       {"type": "tool_use", "id": "t1", "name": "Bash",
                        "input": {"command": "python 0-学习与工具/工具-落库sweep.py"}}, usage),
            _assistant("2026-09-10T01:00:02Z", "req-1", "m1", "claude-opus-5",
                       {"type": "text", "text": "done"}, usage),
        ]
        _write_jsonl(self.root / "sess-cli.jsonl", records)

    def tearDown(self):
        self._tmp.cleanup()

    def test_main_写出报告与json(self):
        out_md = self.repo_root / "reports" / "token-usage-test.md"
        rc = token_usage_meter.main([
            "--root", str(self.root), "--since", "2026-09-06", "--until", "2026-09-13",
            "--repo-root", str(self.repo_root), "--out", str(out_md),
            "--antigravity-requests", "100", "--antigravity-cache-read", "1000",
        ])
        self.assertEqual(rc, 0)
        self.assertTrue(out_md.exists())
        text = out_md.read_text(encoding="utf-8")
        self.assertIn("Token 用量零度量基线报告", text)
        self.assertIn("Antigravity", text)
        json_path = out_md.with_suffix(".json")
        self.assertTrue(json_path.exists())
        payload = json.loads(json_path.read_text(encoding="utf-8"))
        self.assertEqual(len(payload["sessions"]), 1)
        self.assertEqual(payload["sessions"][0]["requests"], 1)
        self.assertEqual(payload["mechanism_tax"]["bash_total"], 1)
        self.assertEqual(payload["mechanism_tax"]["bash_mechanism_hits"], 1)

    def test_since晚于until报错(self):
        rc = token_usage_meter.main([
            "--root", str(self.root), "--since", "2026-09-13", "--until", "2026-09-06",
            "--repo-root", str(self.repo_root),
        ])
        self.assertEqual(rc, 2)

    def test_非法日期报错(self):
        rc = token_usage_meter.main([
            "--root", str(self.root), "--since", "not-a-date", "--until", "2026-09-13",
            "--repo-root", str(self.repo_root),
        ])
        self.assertEqual(rc, 2)

    def test_root不存在报错(self):
        rc = token_usage_meter.main([
            "--root", str(self.root / "nope"), "--since", "2026-09-06", "--until", "2026-09-13",
            "--repo-root", str(self.repo_root),
        ])
        self.assertEqual(rc, 2)


if __name__ == "__main__":
    unittest.main()
