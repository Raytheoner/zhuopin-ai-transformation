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
# 形态 1 · 判据可关闭（`#422` 护栏失效，`OP-0827-G`）
# ============================================================

class Form1AckTests(RepoFixture):
    """🔴 本类锁的是文件头判据 ⑶ 在形态 1 上的落点。

    原缺陷：形态 1 按字样匹配，而补做方守「历史记录不追改」、只在行尾追加
    结论 ⇒ **11 条逐条核实完，重跑一条没减少**。修法＝带内容指纹的确认。

    🔴 **本类里最不能删的是 `test_new_lan_registration_reopens_the_ack` 与
    `test_unacked_row_still_reported`**：一个「什么都不报」的判据比一个「永远
    报 11 条」的判据更糟——后者只是被人忽略，前者会被人当成干净。
    """

    KEY_MECH_ONE = f"form1:{QUEUE_MECH_REL}#一354"

    def _seg_row(self, row_id: str, *segments: str, registered: str = "2026-08-19") -> str:
        status = "[S:partial] " + " ━━━ ".join(segments)
        return (f"| {row_id} | 任务 | CC | 指针 | 产出 | {status} | 触碰区 "
                f"| {registered} |\n")

    def _write(self, *rows: str) -> None:
        self._write_queue(QUEUE_MECH_REL, _queue_doc(list(rows)))
        self._write_queue(QUEUE_BIZ_REL, _queue_doc([]))

    def _scan(self) -> dict:
        return unclosed_scan.scan_form1(self.main, date(2026, 8, 27))

    def _ack(self, key: str, note: str = "逐条读队列原文核过，补做已落 commit") -> int:
        return unclosed_scan.cmd_ack_form1(self.main, key, note, today=date(2026, 8, 27))

    # ---------- 关得掉 ----------

    def test_ack_silences_the_row(self):
        self._write(self._seg_row("354", "**LAN 留步**：`.51` 真机复验未做"))
        self.assertEqual(len(self._scan()["items"]), 1)

        self.assertEqual(self._ack(self.KEY_MECH_ONE), 0)

        result = self._scan()
        self.assertEqual(result["items"], [], "已确认且指纹未变的行必须完全静默")
        self.assertEqual([i["key"] for i in result["suppressed"]], [self.KEY_MECH_ONE])
        self.assertEqual(result["suppressed"][0]["note"],
                         "逐条读队列原文核过，补做已落 commit")

    def test_unrelated_append_does_not_reopen(self):
        """指纹只盖命中段——这一条决定它会不会退化成噪音。队列行一天被追加
        三五段是常态，若整行入指纹，每追加一句无关的话就把已核实的重新捅红。"""
        self._write(self._seg_row("354", "**LAN 留步**：`.51` 真机复验未做"))
        self._ack(self.KEY_MECH_ONE)

        self._write(self._seg_row(
            "354",
            "**LAN 留步**：`.51` 真机复验未做",
            "📎 回归 300 passed，openspec validate 80/80（与留步无关的进展）"))
        self.assertEqual(self._scan()["items"], [], "无关追加不得让已核实的条目重新告警")

    # ---------- 🔴 关不成「什么都不报」 ----------

    def test_new_lan_registration_reopens_the_ack(self):
        """🔴 **本类最要紧的一条**：确认的语义是「我核过了这一行登记的每一处
        留步」。行里**新登记一处**留步 ⇒ 那句话不再成立 ⇒ 必须自动重新告警。
        没有这一条，一次 ack 就成了永久白名单，判据从「永远报 11 条」退化成
        「永远报 0 条」——后者会被当成干净，更危险。"""
        self._write(self._seg_row("354", "**LAN 留步**：`.51` 真机复验未做"))
        self._ack(self.KEY_MECH_ONE)
        self.assertEqual(self._scan()["items"], [])

        self._write(self._seg_row(
            "354",
            "**LAN 留步**：`.51` 真机复验未做",
            "⚠️ 另**回内网补做**一处：8093 冒烟"))
        result = self._scan()
        self.assertEqual([i["key"] for i in result["items"]], [self.KEY_MECH_ONE],
                         "新登记一处留步必须让旧确认失效")
        self.assertEqual(result["suppressed"], [])

    def test_rewriting_an_acked_segment_reopens(self):
        self._write(self._seg_row("354", "**LAN 留步**：`.51` 真机复验未做"))
        self._ack(self.KEY_MECH_ONE)

        self._write(self._seg_row("354", "**LAN 留步**：改口径了，要复验的是 8091"))
        self.assertEqual([i["key"] for i in self._scan()["items"]], [self.KEY_MECH_ONE],
                         "已核过的那一段被改写，确认必须失效")

    def test_unacked_row_still_reported(self):
        """🔴 只验「关得掉」等于没验：一条真没补做的行（样本＝`#334`，`.51`
        未部署）必须照常命中，且不受别行的确认影响。"""
        self._write(
            self._seg_row("354", "**LAN 留步**：`.51` 真机复验未做"),
            self._seg_row("334", "🔒 **LAN 留步**：`.51` 未部署，本班 off-LAN"),
        )
        self._ack(self.KEY_MECH_ONE)

        result = self._scan()
        self.assertEqual([i["row_id"] for i in result["items"]], ["334"])
        self.assertEqual([i["row_id"] for i in result["suppressed"]], ["354"])

    # ---------- 确认本身立不住时拒绝记录 ----------

    def test_ack_requires_note(self):
        self._write(self._seg_row("354", "**LAN 留步**：未做"))
        self.assertEqual(unclosed_scan.cmd_ack_form1(self.main, self.KEY_MECH_ONE, "   "), 1)
        self.assertFalse((self.main / unclosed_scan.FORM1_ACK_STATE_REL).exists(),
                         "空确认不得落盘——它会伪装成已核")
        self.assertEqual(len(self._scan()["items"]), 1)

    def test_ack_refuses_unknown_key(self):
        """一条确认不该指向一个不存在的命中——算不出指纹的确认永远不会失效。"""
        self._write(self._seg_row("354", "**LAN 留步**：未做"))
        self.assertEqual(self._ack(f"form1:{QUEUE_MECH_REL}#一999"), 1)
        self.assertFalse((self.main / unclosed_scan.FORM1_ACK_STATE_REL).exists())

    def test_ack_refused_when_criterion_unavailable(self):
        """队列读不到时判据本身是瞎的，此刻记下的「零命中」毫无意义。"""
        self.assertEqual(self._ack(self.KEY_MECH_ONE), 1)
        self.assertFalse((self.main / unclosed_scan.FORM1_ACK_STATE_REL).exists())

    def test_stale_ack_is_surfaced_not_silent(self):
        """行归档／编号变之后，那条确认核的是一个已经不存在的东西——留着不说
        话，下次读的人会以为「那一处已经被核过」。"""
        self._write(self._seg_row("354", "**LAN 留步**：未做"))
        self._ack(self.KEY_MECH_ONE)
        self._write(self._seg_row("354", "已整段改写，本行不再有任何留步登记"))

        result = self._scan()
        self.assertEqual(result["items"], [])
        self.assertEqual(result["stale_acks"], [self.KEY_MECH_ONE])

    # ---------- 指纹与状态文件 ----------

    def test_fingerprint_covers_hit_segments_only(self):
        hit = ["**LAN 留步**：未做"]
        self.assertEqual(unclosed_scan.form1_fingerprint(hit),
                         unclosed_scan.form1_fingerprint(list(hit)))
        self.assertNotEqual(unclosed_scan.form1_fingerprint(hit),
                            unclosed_scan.form1_fingerprint(hit + ["**回内网补做**：另一处"]))
        self.assertEqual(
            unclosed_scan._hit_segments(["[S:partial] 无关段 ━━━ 有 **LAN 留步** 的段"],
                                        unclosed_scan.LAN_MARKER_RE),
            ["有 **LAN 留步** 的段"])

    def test_ack_file_is_separate_from_scan_state(self):
        """🔴 `STATE_REL` 每轮被整份重写；确认写进去会当轮即被冲掉。"""
        self._write(self._seg_row("354", "**LAN 留步**：未做"))
        self._ack(self.KEY_MECH_ONE)
        rc = unclosed_scan.main(["--repo-root", str(self.main), "--skip-lan-probe",
                                 "--state", str(self.state)])
        self.assertEqual(rc, 0)
        acks = json.loads((self.main / unclosed_scan.FORM1_ACK_STATE_REL)
                          .read_text(encoding="utf-8"))
        self.assertIn(self.KEY_MECH_ONE, acks)
        self.assertEqual(self._scan()["items"], [])

    def test_report_prints_the_command_that_closes_it(self):
        """关掉一条告警的办法必须印在告警自己身上——否则它又是一条关不掉的
        告警，只是这次关不掉的原因换成了「没人知道怎么关」。"""
        self._write(self._seg_row("354", "**LAN 留步**：未做"))
        findings = unclosed_scan.scan(self.main, lan=False, state_path=self.state,
                                      today=date(2026, 8, 27))
        report = unclosed_scan.format_report(findings)
        self.assertIn("--ack-form1", report)
        self.assertIn(self.KEY_MECH_ONE, report)
        self.assertIn("--note", report)


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


# ============================================================
# 形态 3 · 主工作区那条的错误归因（2026-08-27，`OP-0827-E` D 类）
#
# 原缺陷：报告对主工作区写死一句「**sweep 停用期间**它就是一堆没人收的产出」，
# **而它根本没去查过 sweep 的状态**。实测反例＝`State=Ready`、`LastRun 11:17:02`、
# 3 个脏文件 mtime 全部晚于那一轮 ⇒ 真因是正常时间差。危害是复合的：下游读到
# 那句话后跟着断言「Enable-ScheduledTask 还没跑」，同一个未经验证的因果被当作
# 事实转述了一层。
#
# 🔴 本组锁死的是**两路都要在**：只把「停用期间」四个字删掉，这段话就退化成
# 一句没有诊断力的话；它的价值恰恰在于把 mtime 与 LastRunTime 摆在一起。
# ============================================================

class SweepAttributionTests(RepoFixture):
    """主工作区脏文件的归因：时间差 vs 真漏收 vs 不知道。"""

    def _findings(self, sweep: dict | None, mtimes: list[dict]) -> dict:
        return {
            "today": "2026-08-27", "base_ref": "origin/master", "lan": None,
            "lan_flip": {"flip": None}, "resolved": [], "unavailable": [],
            "sweep_task": sweep,
            "form1": {"items": [], "wide_items": [], "excluded_section_two": 0},
            "form2": {"items": []},
            "form3": {"items": [{
                "worktree": str(self.main), "branch": "master", "is_main": True,
                "tracked_changes": len(mtimes), "untracked": 0, "insertions": 49,
                "files": [r["name"] for r in mtimes], "file_times": mtimes,
                "key": "form3:main",
            }]},
        }

    _LIVE = {"task": "ZhuopinCommitSweep", "available": True, "state": "Ready",
             "last_run": "2026-08-27 11:17:02", "next_run": "2026-08-27 12:17:01",
             "last_result": 0, "detail": "State=Ready｜…"}

    def test_live_sweep_reads_as_time_gap_not_disabled(self):
        """实测那一幕：三个文件全部晚于上一轮 ⇒ 正常时间差，不得说成停用。"""
        report = unclosed_scan.format_report(self._findings(self._LIVE, [
            {"name": "波次收口.md", "mtime": "2026-08-27 11:20:53"},
            {"name": "a.md", "mtime": "2026-08-27 11:26:35"},
            {"name": "b.md", "mtime": "2026-08-27 11:35:14"},
        ]))
        self.assertIn("正常时间差", report)
        self.assertNotIn("sweep 停用期间", report,
                         "sweep 在跑时把它说成停用，正是本组要防的那个错误归因")
        self.assertIn("11:17:02", report, "上一轮时刻必须出现——结论要自带证据")
        self.assertIn("11:20:53", report, "文件 mtime 必须与上一轮并排摆出")
        self.assertIn("12:17:01", report, "下一轮时刻要写出来，读的人才知道等多久")

    def test_file_older_than_last_run_is_flagged_as_real_miss(self):
        """🔴 早于上一轮却还在 ⇒ 那才是真漏收，必须单独标红、不能混进时间差。"""
        report = unclosed_scan.format_report(self._findings(self._LIVE, [
            {"name": "漏收的.md", "mtime": "2026-08-27 09:02:00"},
            {"name": "刚改的.md", "mtime": "2026-08-27 11:40:00"},
        ]))
        self.assertIn("真漏收", report)
        self.assertIn("漏收的.md", report)
        self.assertNotIn("全部晚于上一轮", report,
                         "有一个早于上一轮就不能再说『全部晚于』")

    def test_unknown_mtime_is_neither_gap_nor_miss(self):
        """取不到 mtime 的既不算时间差也不算漏收——**不许回落成任一侧**。"""
        report = unclosed_scan.format_report(self._findings(self._LIVE, [
            {"name": "已删除.md", "mtime": None},
        ]))
        self.assertIn("取不到 mtime", report)
        self.assertNotIn("正常时间差", report)
        self.assertNotIn("真漏收", report)

    def test_disabled_sweep_keeps_original_wording_with_measured_state(self):
        """停用这一路保留原救法文案，但必须写出「我凭什么这么说」。"""
        report = unclosed_scan.format_report(self._findings(
            {"task": "ZhuopinCommitSweep", "available": True, "state": "Disabled",
             "last_run": "2026-08-26 21:17:00", "next_run": None, "last_result": 267009,
             "detail": "…"},
            [{"name": "a.md", "mtime": "2026-08-27 11:20:00"}]))
        self.assertIn("sweep 停用期间", report)
        self.assertIn("State=Disabled", report, "断言停用必须附实测值")

    def test_unavailable_sweep_is_not_asserted_to_be_disabled(self):
        """🔴 「我查了，它是停的」与「我没查到」是两句话 —— 后者不得冒充前者。"""
        report = unclosed_scan.format_report(self._findings(
            {"task": "ZhuopinCommitSweep", "available": False, "state": None,
             "last_run": None, "next_run": None, "last_result": None,
             "detail": "本机找不到 `powershell`（非 Windows 或不在 PATH）"},
            [{"name": "a.md", "mtime": "2026-08-27 11:20:00"}]))
        self.assertIn("无法断言", report)
        self.assertIn("powershell", report, "取不到的原因要写出来，否则没法排查")
        self.assertNotIn("State=None", report, "不得把「取不到」渲染成一个状态值")

    def test_skipped_probe_says_so_instead_of_guessing(self):
        """`--skip-lan-probe` 时压根没查 ⇒ 也不得据此判断它在不在跑。"""
        report = unclosed_scan.format_report(self._findings(None, [
            {"name": "a.md", "mtime": "2026-08-27 11:20:00"}]))
        self.assertIn("本轮未查 sweep 状态", report)

    def test_probe_not_run_when_lan_probe_skipped(self):
        """两者都是「问外部环境」：跳过 LAN 探针即一并跳过 sweep 查询。"""
        (self.main / "脏.md").write_text("未提交\n", encoding="utf-8")
        findings = unclosed_scan.scan(self.main, lan=False, state_path=self.state)
        self.assertIsNone(findings["sweep_task"])

    def test_probe_of_nonexistent_task_is_unavailable_not_a_state(self):
        """真跑一次探针（不 mock）：任务不存在 ⇒ `available=False`、`state=None`。
        非 Windows 上走的是 `FileNotFoundError` 那条，结论相同。"""
        result = unclosed_scan.probe_sweep_task("ZhuopinCommitSweep_不存在_测试用")
        self.assertFalse(result["available"])
        self.assertIsNone(result["state"])
        self.assertTrue(result["detail"], "取不到时必须留下原因，不能是空的")

    def test_mtimes_collected_only_for_main_workspace(self):
        """mtime 只对主工作区采集——只有那一条的救法与 sweep 的轮次有关。"""
        wt = Path(self._tmp.name) / "wt-dirty"
        _git(self.main, "worktree", "add", "-q", str(wt), "-b", "claude/wt-dirty")
        (wt / "脏.md").write_text("linked worktree 的改动\n", encoding="utf-8")
        (self.main / "脏.md").write_text("主工作区的改动\n", encoding="utf-8")
        items = unclosed_scan.scan_form3(self.main)["items"]
        main_item = next(i for i in items if i["is_main"])
        linked = next(i for i in items if not i["is_main"])
        self.assertTrue(main_item["file_times"])
        self.assertTrue(main_item["file_times"][0]["mtime"])
        self.assertEqual(linked["file_times"], [])

    def test_rename_row_takes_the_new_path(self):
        """`R  旧 -> 新`：要 stat 的是新名。取旧名只会得到一个「文件不存在」，
        把一条真改动记成无 mtime。"""
        self.assertEqual(unclosed_scan._status_path("R  旧名.md -> 新名.md"), "新名.md")
        self.assertEqual(unclosed_scan._status_path("?? 未跟踪.md"), "未跟踪.md")


class LanProbeTriStateTests(unittest.TestCase):
    """🔴 队列 §一 `#422` 续（2026-08-28，`OP-0828-Z`）：**探针失败 ≠ off-LAN**。

    本组锁的是一个**只会在回内网那一刻造成危害、平时完全看不出来**的缺陷：
    `probe_lan` 原本两态，`ping` 没跑起来（找不到 `ping`／超时被杀）与「目标
    不可达」都算 `on_lan=False`。于是一次探针故障会被 `write_state` 记成 off，
    下一轮探针恢复即被 `track_lan_flip` 算成 `off→on` —— **在没有任何人回内网
    的情况下推一条「你刚回到内网」**。这类误发两三次之后，那条提醒就再没人
    看了，而它整个存在的理由就是「回内网那一刻真的找到人」。
    """

    def test_探针没跑起来时状态是unknown不是off(self):
        probes = [{"probe": "ping", "ok": False, "error": True, "detail": "探针未能执行"},
                  {"probe": "http", "ok": True, "error": False}]
        orig_ping, orig_http = unclosed_scan._probe_ping, unclosed_scan._probe_http
        unclosed_scan._probe_ping = lambda host: probes[0]
        unclosed_scan._probe_http = lambda host, port, label: probes[1]
        try:
            lan = unclosed_scan.probe_lan("1.2.3.4")
        finally:
            unclosed_scan._probe_ping, unclosed_scan._probe_http = orig_ping, orig_http
        self.assertEqual(lan["status"], "unknown")
        self.assertIsNone(lan["on_lan"], "unknown 时 on_lan 必须是 None，不得是 False")
        self.assertIn("observed_utc", lan)
        self.assertIn("observed_local", lan)

    def test_三态措辞两两不同(self):
        """「它不通」与「我没测成」在报告里长得一样，就会有人拿探针故障当作
        「他还没回内网」的证据。"""
        texts = {unclosed_scan.lan_status_text({"status": s}) for s in ("on", "off", "unknown")}
        self.assertEqual(len(texts), 3, texts)
        self.assertIn("不据此判为 off-LAN", unclosed_scan.lan_status_text({"status": "unknown"}))

    def test_off到on才算翻转_on到on不算(self):
        """防抖那一半：`on→on` 不得重复推。"""
        self.assertEqual(
            unclosed_scan.track_lan_flip({"lan": {"on_lan": False}},
                                         {"status": "on", "on_lan": True})["flip"], "off→on")
        self.assertIsNone(
            unclosed_scan.track_lan_flip({"lan": {"on_lan": True}},
                                         {"status": "on", "on_lan": True})["flip"])

    def test_unknown那一轮任何翻转都不算(self):
        """🔴 两个方向都要挡：不只是防误报 `off→on`，`on→off` 同样不许由一次
        测量失败推出来。"""
        for previous in (True, False, None):
            flip = unclosed_scan.track_lan_flip(
                {"lan": {"on_lan": previous}}, {"status": "unknown", "on_lan": None})
            self.assertIsNone(flip["flip"], previous)
            self.assertEqual(flip["probe_status"], "unknown")
            self.assertEqual(flip["previous"], previous,
                             "unknown 不得把上一轮的结论抹掉")

    def test_首轮没有历史时不把第一次看见on当翻转(self):
        self.assertIsNone(unclosed_scan.track_lan_flip({}, {"status": "on", "on_lan": True})["flip"])

    def test_unknown那一轮不覆盖状态文件里的onlan(self):
        """本组最要紧的一条：**一次探针故障不得把上一轮真的测出来的结论擦掉**。

        擦掉会让下一轮的 `previous` 变成 `None`，于是真正的 `off→on` 被判成
        「首轮」而静默 —— 测量失败伪装成「什么都没发生」。
        """
        with tempfile.TemporaryDirectory() as tmp:
            state = Path(tmp) / "state.json"
            base = {"form1": {"items": []}, "form2": {"items": []}, "form3": {"items": []}}

            unclosed_scan.write_state({**base, "lan": {"status": "off", "on_lan": False}}, state)
            self.assertIs(json.loads(state.read_text(encoding="utf-8"))["lan"]["on_lan"], False)

            unclosed_scan.write_state({**base, "lan": {"status": "unknown", "on_lan": None}}, state)
            after = json.loads(state.read_text(encoding="utf-8"))["lan"]
            self.assertIs(after["on_lan"], False, "unknown 不得覆盖上一轮的 off")
            self.assertEqual(after["last_probe_status"], "unknown")

            # 探针恢复、真的是 on ⇒ 这一次必须仍然算作 off→on。
            flip = unclosed_scan.track_lan_flip(
                json.loads(state.read_text(encoding="utf-8")), {"status": "on", "on_lan": True})
            self.assertEqual(flip["flip"], "off→on",
                             "中间夹了一轮 unknown 之后，真翻转仍必须被认出来")

    def test_要补什么取行内原文摘录不做概括(self):
        """概括就得猜中文，而本文件已两次把「猜中文关键词」判为要根治的那族。"""
        self.assertIn("到期未部署", unclosed_scan.form1_todo_hint({"excerpt": "到期未部署"}))
        self.assertIn("直接读该行", unclosed_scan.form1_todo_hint({"excerpt": ""}))


if __name__ == "__main__":
    unittest.main()
