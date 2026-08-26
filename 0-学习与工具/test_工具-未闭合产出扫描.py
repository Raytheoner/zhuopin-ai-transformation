"""工具-未闭合产出扫描.py 单测（队列 §一 `#398` 第 ⑷ 处，`OP-0826-U`）。

用真实 `git worktree add` 建最小仓库拓扑、用真实 HTTP 桩答探针——三个形态
与 LAN 判据都不用 mock 掉被测的那一层，因为**本工具要防的病正是「判据看起来
过了、其实没在判」**，而 mock 掉真实交互恰好会把这种病一起 mock 掉。

🔴 本文件最要紧的一条是 `test_rebase_landed_branch_not_reported`：它锁死
「ancestry 判『未合入』会对每个 rebase 落地的分支永久误报」这个反例。删掉
它，工具会退回到那个永远红着、一周内所有人都学会忽略的告警。
"""
from __future__ import annotations

import http.server
import importlib.util
import json
import subprocess
import tempfile
import threading
import unittest
from datetime import date
from pathlib import Path

SCRIPT = Path(__file__).resolve().with_name("工具-未闭合产出扫描.py")

_spec = importlib.util.spec_from_file_location("unclosed_scan", SCRIPT)
unclosed_scan = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(unclosed_scan)


def _git(cwd: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-c", "core.quotepath=false", *args], cwd=cwd,
                          capture_output=True, text=True, encoding="utf-8", check=check)


QUEUE_MECH_REL = "1-转型规划/0-全景路线图/跨桌任务队列-机制环境.md"
QUEUE_BIZ_REL = "1-转型规划/0-全景路线图/跨桌任务队列-业务场景.md"


def _queue_doc(section_one_rows: list[str], section_two_rows: list[str] = ()) -> str:
    """拼一份最小队列文件：§一 八列、§二 四列。"""
    head_one = "| # | 任务 | 领取方 | 输入（指针） | 期望产出 | 状态 | 触碰区 | 登记 |\n" \
               "|---|---|---|---|---|---|---|---|\n"
    head_two = "| 批次 | 文件清单 | 建议 message | 状态 |\n|---|---|---|---|\n"
    text = "# 跨桌任务队列\n\n## 一、任务看板\n\n" + head_one + "".join(section_one_rows)
    text += "\n## 二、待 commit 批次\n\n" + head_two + "".join(section_two_rows)
    text += "\n## 三、口径冻结标\n\n（无）\n"
    return text


class RepoFixture(unittest.TestCase):
    """bare origin + 主工作区，供各形态测试复用。"""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        base = Path(self._tmp.name)
        self.origin = base / "origin.git"
        self.main = base / "main"
        _git(base, "init", "--bare", "-q", str(self.origin))
        _git(base, "init", "-q", str(self.main))
        _git(self.main, "config", "user.email", "test@example.com")
        _git(self.main, "config", "user.name", "Test")
        _git(self.main, "remote", "add", "origin", str(self.origin))
        (self.main / "README.md").write_text("init\n", encoding="utf-8")
        _git(self.main, "add", "-A")
        _git(self.main, "commit", "-q", "-m", "init")
        _git(self.main, "branch", "-M", "master")
        _git(self.main, "push", "-q", "-u", "origin", "master")
        self.state = base / "state.json"

    def tearDown(self):
        self._tmp.cleanup()

    def _write_queue(self, rel: str, text: str) -> None:
        path = self.main / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def _commit(self, cwd: Path, name: str, body: str, message: str) -> str:
        (cwd / name).write_text(body, encoding="utf-8")
        _git(cwd, "add", "-A")
        _git(cwd, "commit", "-q", "-m", message)
        return _git(cwd, "rev-parse", "HEAD").stdout.strip()


# ============================================================
# 形态 2：patch 等价 vs 真·未上游
# ============================================================

class Form2Tests(RepoFixture):
    def test_rebase_landed_branch_not_reported(self):
        """🔴 反例锁死：内容已被 rebase 落到 master 的分支**不得**报未合入。

        构造的正是 2026-08-26 的真实场景——`#398` 的 `fb0d185` 与 master 上的
        `e024ead` patch-id 相同、SHA 不同，ancestry 判定「未合入」而实际已上游。
        """
        _git(self.main, "checkout", "-q", "-b", "feature")
        self._commit(self.main, "tool.py", "print('新功能')\n", "feat: 新功能")
        _git(self.main, "checkout", "-q", "master")
        # 🔴 先让 master 往前走一步再 cherry-pick。否则父提交相同 ⇒ 摘下来的
        # 提交与原提交**连 SHA 都一样**，构造不出「同内容、不同 SHA」这个
        # 前提，反例就退化成了一次普通的快进。
        self._commit(self.main, "别的.md", "master 自己的改动\n", "docs: master 先走一步")
        _git(self.main, "cherry-pick", "feature")
        _git(self.main, "push", "-q", "origin", "master")

        head_feature = _git(self.main, "rev-parse", "feature").stdout.strip()
        head_master = _git(self.main, "rev-parse", "master").stdout.strip()
        self.assertNotEqual(head_feature, head_master, "前提：两者 SHA 必须不同")
        ancestry = subprocess.run(
            ["git", "merge-base", "--is-ancestor", head_feature, "origin/master"],
            cwd=self.main, capture_output=True)
        self.assertNotEqual(ancestry.returncode, 0,
                            "前提：ancestry 判据必须仍认为它『未合入』，否则本反例失效")

        result = unclosed_scan.scan_form2(self.main, "origin/master")
        branches = [item["branch"] for item in result["items"]]
        self.assertNotIn("feature", branches,
                         f"patch 等价已上游的分支被误报为未合入：{result}")

    def test_genuinely_unmerged_branch_reported(self):
        _git(self.main, "checkout", "-q", "-b", "claude/real-work")
        self._commit(self.main, "output.md", "真的还没合入\n", "feat: 未合入产出")
        _git(self.main, "checkout", "-q", "master")

        result = unclosed_scan.scan_form2(self.main, "origin/master")
        item = next(i for i in result["items"] if i["branch"] == "claude/real-work")
        self.assertEqual(item["unmerged"], 1)
        self.assertIn("未合入产出", " ".join(item["subjects"]))
        self.assertEqual(item["key"], "form2:claude/real-work")

    def test_local_master_fork_is_flagged(self):
        """本地 master 双向都有独有提交 ⇒ 必须报，且标成分叉。

        初版把 `master` 排除在扫描之外，第一次真实运行就漏掉了当天最要紧的
        一条（`367b883` 提交了没 push、两边已分叉）。本例锁死那个排除不得回来。
        """
        _git(self.main, "checkout", "-q", "-b", "other")
        self._commit(self.main, "远端独有.md", "远端\n", "feat: 远端独有")
        _git(self.main, "push", "-q", "origin", "other:master")
        _git(self.main, "checkout", "-q", "master")
        self._commit(self.main, "本地独有.md", "本地\n", "feat: 本地独有未推送")
        _git(self.main, "fetch", "-q", "origin")

        result = unclosed_scan.scan_form2(self.main, "origin/master")
        item = next(i for i in result["items"] if i["branch"] == "master")
        self.assertTrue(item["is_local_master"])
        self.assertTrue(item["forked"], "双向独有必须判为分叉")
        self.assertEqual(item["unmerged"], 1)
        self.assertGreaterEqual(item["behind"], 1)
        report = unclosed_scan.format_report({
            "today": "2026-08-27", "base_ref": "origin/master", "lan": None,
            "lan_flip": {"flip": None}, "resolved": [], "unavailable": [],
            "form1": {"items": [], "wide_items": [], "excluded_section_two": 0},
            "form2": result, "form3": {"items": []},
        })
        self.assertIn("本地 master 已分叉", report)
        self.assertIn("不得 `git pull`", report, "分叉的救法必须写明不能 pull")

    def test_missing_base_is_unavailable_not_clean(self):
        """取不到基准时报「判据不可用」，**不得**返回空清单冒充干净。"""
        result = unclosed_scan.scan_form2(self.main, None)
        self.assertEqual(result["items"], [])
        self.assertIsNotNone(result["unavailable"])


# ============================================================
# 形态 3：worktree 里未 commit 的产出
# ============================================================

class Form3Tests(RepoFixture):
    def test_uncommitted_worktree_changes_reported(self):
        wt = Path(self._tmp.name) / "queue-410-editable-guard"
        _git(self.main, "worktree", "add", "-q", str(wt), "-b", "claude/queue-410")
        (wt / "工具.py").write_text("第一行\n第二行\n第三行\n", encoding="utf-8")
        _git(wt, "add", "-A")
        _git(wt, "commit", "-q", "-m", "基线")
        (wt / "工具.py").write_text("第一行\n第二行\n第三行\n新增一行\n", encoding="utf-8")
        (wt / "没跟踪.md").write_text("未跟踪产出\n", encoding="utf-8")

        result = unclosed_scan.scan_form3(self.main)
        item = next(i for i in result["items"] if Path(i["worktree"]).name == wt.name)
        self.assertEqual(item["tracked_changes"], 1)
        self.assertEqual(item["untracked"], 1)
        self.assertEqual(item["insertions"], 1)
        self.assertFalse(item["is_main"])
        self.assertEqual(item["key"], "form3:queue-410-editable-guard")

    def test_key_excludes_volatile_counts(self):
        """🔴 key 不含行数——否则每改一行就是一个「新问题」，旧 key 还会被
        误判为已解除（判据 ⑶）。"""
        wt = Path(self._tmp.name) / "wt-a"
        _git(self.main, "worktree", "add", "-q", str(wt), "-b", "claude/wt-a")
        (wt / "a.txt").write_text("1\n", encoding="utf-8")
        first = next(i for i in unclosed_scan.scan_form3(self.main)["items"]
                     if Path(i["worktree"]).name == "wt-a")
        (wt / "a.txt").write_text("1\n2\n3\n4\n", encoding="utf-8")
        second = next(i for i in unclosed_scan.scan_form3(self.main)["items"]
                      if Path(i["worktree"]).name == "wt-a")
        self.assertEqual(first["key"], second["key"])

    def test_clean_worktree_not_reported(self):
        wt = Path(self._tmp.name) / "wt-clean"
        _git(self.main, "worktree", "add", "-q", str(wt), "-b", "claude/wt-clean")
        paths = [Path(i["worktree"]).name for i in unclosed_scan.scan_form3(self.main)["items"]]
        self.assertNotIn("wt-clean", paths)

    def test_main_workspace_flagged_separately(self):
        (self.main / "未提交.md").write_text("主工作区的改动\n", encoding="utf-8")
        result = unclosed_scan.scan_form3(self.main)
        item = next(i for i in result["items"] if i["is_main"])
        self.assertEqual(Path(item["worktree"]).resolve(), self.main.resolve())
        report = unclosed_scan.format_report({
            "today": "2026-08-27", "base_ref": "origin/master", "lan": None,
            "lan_flip": {"flip": None}, "resolved": [], "unavailable": [],
            "form1": {"items": [], "wide_items": [], "excluded_section_two": 0},
            "form2": {"items": []}, "form3": result,
        })
        self.assertIn("主工作区", report)
        self.assertIn("落库 sweep", report, "主工作区的救法与 worktree 不同，须分开写")


# ============================================================
# 形态 1：队列里的 LAN 留步登记
# ============================================================

class Form1Tests(RepoFixture):
    def _row(self, row_id: str, task: str, registered: str) -> str:
        return (f"| {row_id} | {task} | CC | 指针 | 产出 | [S:partial] | 触碰区 "
                f"| {registered} |\n")

    def test_section_one_hit_reported_with_age_bucket(self):
        self._write_queue(QUEUE_MECH_REL, _queue_doc([
            self._row("354", "真机复验 **LAN 留步**，等回内网", "2026-08-19"),
        ]))
        self._write_queue(QUEUE_BIZ_REL, _queue_doc([]))

        result = unclosed_scan.scan_form1(self.main, date(2026, 8, 27))
        self.assertEqual(len(result["items"]), 1, result)
        item = result["items"][0]
        self.assertEqual(item["row_id"], "354")
        self.assertEqual(item["age_days"], 8)
        self.assertEqual(item["bucket"], "≥7 天")
        self.assertEqual(item["key"], f"form1:{QUEUE_MECH_REL}#一354")

    def test_section_two_batch_rows_excluded_but_counted(self):
        """🔴 §二 是已完成批次的历史叙述——算进存量会长期虚高（14 处里有 5 处
        属此类）。但**剔了几处要能被看见**，否则没人知道判据在剔什么。"""
        self._write_queue(QUEUE_MECH_REL, _queue_doc(
            [self._row("400", "正常在办，无留步", "2026-08-26")],
            ["| B-0826_21_历史批次 | 文件 | msg | ✅ 已落库（含 LAN 留步 记述） |\n"],
        ))
        self._write_queue(QUEUE_BIZ_REL, _queue_doc([]))

        result = unclosed_scan.scan_form1(self.main, date(2026, 8, 27))
        self.assertEqual(result["items"], [])
        self.assertEqual(result["excluded_section_two"], 1)

    def test_negated_mention_not_reported(self):
        """实测反例 `#418`：「故这不是 LAN 留步，是…」——纯字面匹配会误报。"""
        self._write_queue(QUEUE_MECH_REL, _queue_doc([
            self._row("418", "服务健康、SSH 通，故这不是 LAN 留步，是无人在场", "2026-08-26"),
        ]))
        self._write_queue(QUEUE_BIZ_REL, _queue_doc([]))
        result = unclosed_scan.scan_form1(self.main, date(2026, 8, 27))
        self.assertEqual(result["items"], [], "被否定的提及不得进清单")

    def test_affirmative_hit_survives_a_negation_elsewhere_in_row(self):
        """同一行里既有否定又有真登记时，**真的那处仍要报**——否则一句
        「这不是 LAN 留步」就能把同行真正的留步一起吞掉。"""
        self._write_queue(QUEUE_MECH_REL, _queue_doc([
            self._row("419", "⑴ 这不是 LAN 留步；⑵ 另有一处 **LAN 留步**：取不到值", "2026-08-26"),
        ]))
        self._write_queue(QUEUE_BIZ_REL, _queue_doc([]))
        result = unclosed_scan.scan_form1(self.main, date(2026, 8, 27))
        self.assertEqual([i["row_id"] for i in result["items"]], ["419"])

    def test_both_queue_files_are_parsed(self):
        """🔴 两份逐份解析后合并——只读第一份会静默丢掉另一份的整个 §一。"""
        self._write_queue(QUEUE_MECH_REL, _queue_doc([
            self._row("354", "机制侧 LAN 留步", "2026-08-19")]))
        self._write_queue(QUEUE_BIZ_REL, _queue_doc([
            self._row("340", "业务侧 LAN 留步", "2026-08-17")]))
        result = unclosed_scan.scan_form1(self.main, date(2026, 8, 27))
        self.assertEqual({i["row_id"] for i in result["items"]}, {"354", "340"})

    def test_unreadable_queue_is_unavailable_not_clean(self):
        result = unclosed_scan.scan_form1(self.main, date(2026, 8, 27))
        self.assertEqual(result["items"], [])
        self.assertIsNotNone(result["unavailable"],
                             "队列读不到必须报判据不可用，不得静默当成没有留步项")


# ============================================================
# 回 LAN 感知：三项判据 + 翻转
# ============================================================

class _StubHandler(http.server.BaseHTTPRequestHandler):
    server_header = "waitress"
    extra_headers: tuple[tuple[str, str], ...] = ()
    status = 200

    def do_GET(self):  # noqa: N802 —— BaseHTTPRequestHandler 约定
        self.send_response(self.status)
        for key, value in self.extra_headers:
            self.send_header(key, value)
        self.end_headers()
        self.wfile.write(b'{"status":"ok"}')

    def version_string(self):
        return self.server_header

    def log_message(self, *args):  # 静音，免得污染测试输出
        return


class LanProbeTests(unittest.TestCase):
    def _serve(self, handler_cls) -> int:
        server = http.server.HTTPServer(("127.0.0.1", 0), handler_cls)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(server.shutdown)
        return server.server_port

    def test_real_service_answer_passes(self):
        port = self._serve(_StubHandler)
        probe = unclosed_scan._probe_http("127.0.0.1", port, "桩")
        self.assertTrue(probe["ok"], probe)
        self.assertEqual(probe["status"], 200)

    def test_proxy_answer_rejected_even_with_200(self):
        """🔴 判据 ⑵ 的核心：**有状态码不等于服务答了**。带
        `Proxy-Connection` 的 200 也必须判否——08-25 那个骗人的 502 就是
        代理给的，只是它当时给的是 502 而不是 200。"""
        class Proxied(_StubHandler):
            extra_headers = (("Proxy-Connection", "keep-alive"),)
        port = self._serve(Proxied)
        probe = unclosed_scan._probe_http("127.0.0.1", port, "桩")
        self.assertFalse(probe["ok"], probe)
        self.assertEqual(probe["proxy_header"], "keep-alive")

    def test_502_with_proxy_header_is_read_not_swallowed(self):
        """HTTPError 也要拆开看——把异常一律译成「不可达」等于把证据扔了。"""
        class Bad(_StubHandler):
            status = 502
            extra_headers = (("Proxy-Connection", "keep-alive"),)
        port = self._serve(Bad)
        probe = unclosed_scan._probe_http("127.0.0.1", port, "桩")
        self.assertFalse(probe["ok"])
        self.assertEqual(probe["status"], 502, "502 的状态码必须被记下来，不能丢")
        self.assertEqual(probe["proxy_header"], "keep-alive")

    def test_wrong_server_header_rejected(self):
        class Nginx(_StubHandler):
            server_header = "nginx"
        port = self._serve(Nginx)
        self.assertFalse(unclosed_scan._probe_http("127.0.0.1", port, "桩")["ok"])

    def test_unreachable_port_reports_reason(self):
        probe = unclosed_scan._probe_http("127.0.0.1", 1, "桩")
        self.assertFalse(probe["ok"])
        self.assertIn("请求失败", probe["detail"])


class LanFlipTests(unittest.TestCase):
    def test_off_to_on_is_the_only_alerting_flip(self):
        state = {"lan": {"on_lan": False}}
        self.assertEqual(unclosed_scan.track_lan_flip(state, {"on_lan": True})["flip"], "off→on")

    def test_first_round_is_not_a_flip(self):
        """首轮没有历史 ⇒ 不把「第一次看见 on」当成翻转，否则装上当天就会
        凭空发一条提醒，而什么都没发生。"""
        self.assertIsNone(unclosed_scan.track_lan_flip({}, {"on_lan": True})["flip"])

    def test_steady_state_is_not_a_flip(self):
        state = {"lan": {"on_lan": True}}
        self.assertIsNone(unclosed_scan.track_lan_flip(state, {"on_lan": True})["flip"])

    def test_on_to_off_recorded_but_distinct(self):
        state = {"lan": {"on_lan": True}}
        self.assertEqual(unclosed_scan.track_lan_flip(state, {"on_lan": False})["flip"], "on→off")

    def test_skipped_probe_yields_no_flip(self):
        state = {"lan": {"on_lan": False}}
        self.assertIsNone(unclosed_scan.track_lan_flip(state, None)["flip"])


# ============================================================
# 护栏：判据能被「已补做」关掉
# ============================================================

class GuardrailTests(RepoFixture):
    def test_resolved_key_reported_once_then_silent(self):
        """🔴 判据 ⑶：做完了就不再报。否则一周之内所有人都学会忽略它。"""
        self.state.write_text(json.dumps(
            {"alerted": {"form3:已经救好的": {"first_seen_utc": "2026-08-26T00:00:00Z"}},
             "lan": {}}), encoding="utf-8")

        first = unclosed_scan.scan(self.main, lan=False, state_path=self.state)
        self.assertEqual(first["resolved"], ["form3:已经救好的"])
        unclosed_scan.write_state(first, self.state)

        second = unclosed_scan.scan(self.main, lan=False, state_path=self.state)
        self.assertEqual(second["resolved"], [], "已解除只报一次，报完即静音")

    def test_first_seen_preserved_across_rounds(self):
        wt = Path(self._tmp.name) / "wt-keep"
        _git(self.main, "worktree", "add", "-q", str(wt), "-b", "claude/wt-keep")
        (wt / "a.txt").write_text("1\n", encoding="utf-8")

        first = unclosed_scan.scan(self.main, lan=False, state_path=self.state)
        unclosed_scan.write_state(first, self.state)
        stamp = json.loads(self.state.read_text(encoding="utf-8"))["alerted"]["form3:wt-keep"]
        second = unclosed_scan.scan(self.main, lan=False, state_path=self.state)
        unclosed_scan.write_state(second, self.state)
        again = json.loads(self.state.read_text(encoding="utf-8"))["alerted"]["form3:wt-keep"]
        self.assertEqual(stamp["first_seen_utc"], again["first_seen_utc"],
                         "首次发现时间必须跨轮保留，否则「躺了多久」永远是 0")


class ExitCodeTests(RepoFixture):
    def _run(self, *extra: str) -> int:
        return unclosed_scan.main([
            "--repo-root", str(self.main), "--skip-lan-probe", "--no-write-state",
            "--state", str(self.state), *extra])

    def _with_queues(self) -> None:
        """备齐队列文件——否则「判据不可用」（2）会盖过「有发现」（1），
        测到的就不是想测的那条路径了。"""
        self._write_queue(QUEUE_MECH_REL, _queue_doc([]))
        self._write_queue(QUEUE_BIZ_REL, _queue_doc([]))
        # 提交掉——否则这两份文件自己就是「主工作区里未提交的产出」，
        # 形态 3 会照实报出来（那是对的，只是会把本例想测的东西盖住）。
        _git(self.main, "add", "-A")
        _git(self.main, "commit", "-q", "-m", "test: 备齐队列文件")
        # 并且推上去——commit 了没 push 本身就是形态 2（这正是真实世界里
        # `367b883` 那条），不推的话本例仍然不是「干净」。
        _git(self.main, "push", "-q", "origin", "master")
        _git(self.main, "fetch", "-q", "origin")

    def test_no_enforce_always_zero(self):
        self._with_queues()
        (self.main / "脏.md").write_text("有未提交产出\n", encoding="utf-8")
        self.assertEqual(self._run(), 0, "报告工具不带 --enforce 时不该拦住调用它的那一轮")

    def test_enforce_returns_one_on_findings(self):
        self._with_queues()
        (self.main / "脏.md").write_text("有未提交产出\n", encoding="utf-8")
        self.assertEqual(self._run("--enforce"), 1)

    def test_enforce_zero_when_truly_clean(self):
        """干净时必须是 0——否则这个守卫从上线第一天起就永远非零，等于常红。"""
        self._with_queues()
        self.assertEqual(self._run("--enforce"), 0)

    def test_enforce_returns_two_when_criterion_blind(self):
        """🔴 2 ≠ 1：1 是「发现了问题」，2 是「这个守卫自己瞎了」。合并成
        同一个码，则守卫失明这件事永远不会被单独看见。"""
        self.assertEqual(self._run("--enforce"), 2,
                         "队列文件不存在 ⇒ 判据不可用 ⇒ 必须是 2")


if __name__ == "__main__":
    unittest.main()
