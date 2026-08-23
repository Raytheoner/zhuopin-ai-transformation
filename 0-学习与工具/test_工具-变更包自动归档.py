"""工具-变更包自动归档.py 单测（OP-0823-F，变更包 auto-archive-substantive-complete）。

白盒：直接调 `classify_tasks(text)` / `is_archive_action_line(line)`，喂**生产真身原文**，
不触碰真实仓库。

🔴 本文件存在的首要理由，不是证明判据能命中，**是把 2026-08-23 dry-run 实测到的
「3 命中 3 个都不该动」这个反例集永久钉住**。那一轮的三条 archive 行，作者都在同一行里
写了「本次不做／本轮不做，前置条件未满足」，而判据结构上读不到那半截字——若当时开了自动
执行，会永久移走两到三个未完工的包，**且移完之后没有任何机制会告诉我们移错了**。

⇒ 故本文件的断言分两层：
   L1 判据本身（`is_archive_action_line` / 四态分类）——正反例都要
   L2 **「有人在这行留了话」的形态判别**（`carries_human_note`）——三条真实反例逐条锁死
"""
from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().with_name("工具-变更包自动归档.py")


def _load_module():
    spec = importlib.util.spec_from_file_location("_auto_archive_under_test", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    # 🔴 必须先登记进 sys.modules 再 exec：`@dataclass` 在处理注解时会回查
    # `sys.modules[cls.__module__]`，未登记时拿到 None 而抛
    # `AttributeError: 'NoneType' object has no attribute '__dict__'`。
    # 本项目既有单测多数不含 dataclass，故此前没撞上——不是它们的写法更对。
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


M = _load_module()

# ── 生产真身原文（2026-08-23 从 openspec/changes/*/tasks.md 逐字取，勿改写）──────

# ① editlock-hold-scope-and-wip-block 33/34 —— 判据命中，但作者明写「本次不做」
REAL_EDITLOCK = (
    "- [ ] 4.7 `/opsx:archive editlock-hold-scope-and-wip-block -y`（全部 tasks 勾完才做）"
    "—— 🔴 **本次不做，前置条件未满足，如实登记不假装完工**：4.4 只取到一半样本"
    "（晋档条件①②仍无真实样本），本项须等 ⑨ 真实拒绝过一次、逃生阀真实用过一次之后再评估；"
    "届时若那两次仍未自然发生，须先回 §四 #58 讨论\"要不要人为构造一次\"，而不是直接归档。"
)

# ② sweep-startup-nonblocking 25/26 —— 同上，「本次不执行，如实留置」
REAL_SWEEP_STARTUP = (
    "- [ ] 8.4 `/opsx:archive`——**本次不执行，前置条件未满足，如实留置**。未闭合项："
)

# ③ sweep-ops-webhook-cutover 30/31 —— 派单件称其为「死锁的纯样本」，实测它也带人写说明
REAL_SWEEP_OPS = (
    "- [ ] 6.5 `/opsx:archive` —— **仅当上述全部 `[x]` 时才做**；"
    "3.3 那类\"已改未验证\"项未闭合即不得 archive，不假装完工"
)

# ④ 真实归档过的光秃形态（最近三次真实归档全长这样）
REAL_BARE_1 = "- [x] 9.4 `/opsx:archive editlock-chokepoint-six-fixes -y`"
REAL_BARE_2 = "- [x] 4.2 `openspec archive sweep-resident-service-judge -y`"

# ⑤ queue-status-machine-field 47/48 —— 真未完项，判据**必须不命中**
REAL_REAL_UNDONE = (
    "- [ ] 8.3 真实主工作区验证（真实 `acquire --reserve --domain`、真实触发 WIP 超限提示、"
    "真实触发 F1/F2/G）——**原登记：未做**（本次工作全程在独立 worktree 内完成，"
    "未对共享主工作区做真实触发验证；push 后续观察真实使用场景）。"
)

# ⑥ open-pool-reminder-dual-file-and-staleness 的那条真未完项
REAL_OPEN_POOL = "- [ ] 4.5 **真实推送**：真实执行一次 `decision_reminder_check.py`，确认企微收到；Shao Peishen 确认看到"


class TestArchiveActionLine(unittest.TestCase):
    """L1：`is_archive_action_line` 的正反例。"""

    def test_真实归档过的光秃形态_命中(self):
        for line in (REAL_BARE_1, REAL_BARE_2):
            with self.subTest(line=line[:40]):
                self.assertTrue(M.is_archive_action_line(line))

    def test_三条生产真身的archive行_均命中判据(self):
        """判据本身认得它们——这正是问题所在，故必须断言它确实认得。"""
        for line in (REAL_EDITLOCK, REAL_SWEEP_STARTUP, REAL_SWEEP_OPS):
            with self.subTest(line=line[:40]):
                self.assertTrue(M.is_archive_action_line(line))

    def test_真未完项_不命中(self):
        for line in (REAL_REAL_UNDONE, REAL_OPEN_POOL):
            with self.subTest(line=line[:40]):
                self.assertFalse(M.is_archive_action_line(line))

    def test_只有归档二字而无archive_不命中(self):
        """「归档后回填队列行」是归档的下游工作，不是归档本身——宁严勿宽。"""
        self.assertFalse(M.is_archive_action_line("- [ ] 6.2 归档后回填队列 §一 #361"))

    def test_只有archive而无动作词_不命中(self):
        self.assertFalse(M.is_archive_action_line("- [ ] 3.1 把 archive 目录纳入台账扫描范围"))

    def test_大小写不敏感(self):
        self.assertTrue(M.is_archive_action_line("- [ ] 9.9 run `OpenSpec Archive foo -y` 归档"))


class TestClassify(unittest.TestCase):
    """L1：四态分类。"""

    def test_全勾_判complete(self):
        v = M.classify_tasks("- [x] 1.1 做完\n- [x] 1.2 也做完\n")
        self.assertEqual(v.status, M.COMPLETE)
        self.assertEqual(v.progress, "2/2")

    def test_无复选框_判no_tasks(self):
        v = M.classify_tasks("# tasks\n\n本包无 tasks。\n")
        self.assertEqual(v.status, M.NO_TASKS)

    def test_未勾项全为archive_判实质完工(self):
        v = M.classify_tasks("- [x] 1.1 做完\n" + REAL_SWEEP_OPS + "\n")
        self.assertEqual(v.status, M.SUBSTANTIVE)
        self.assertEqual(v.unchecked, [REAL_SWEEP_OPS])

    def test_47比48那条真未完项_不得判实质完工(self):
        """🔴 按「未勾数 ≤1」判会把它错归档，而 archive 不可逆。这条是判据的存在理由。"""
        v = M.classify_tasks("- [x] a\n" * 47 + REAL_REAL_UNDONE + "\n")
        self.assertEqual(v.status, M.INCOMPLETE)

    def test_混合_有一条非archive即不判实质完工(self):
        v = M.classify_tasks("- [x] 1.1 ok\n" + REAL_OPEN_POOL + "\n- [ ] 5.3 `/opsx:archive` 归档\n")
        self.assertEqual(v.status, M.INCOMPLETE)

    def test_缩进与星号列表也识别(self):
        v = M.classify_tasks("  * [x] 1.1 ok\n    - [ ] 1.2 没做\n")
        self.assertEqual(v.status, M.INCOMPLETE)
        self.assertEqual(v.checked, 1)


class TestSubstantivelyComplete(unittest.TestCase):
    """🔴 派单件 §3.1ter：「实质完工」的完整定义 —— 两条任一命中即成立。

    **第一条（N/N）是本次补的，缺了它整个判据是自相矛盾的**：

    - 派单件 §四 原本要「治本」（新包不再把 archive 写进 tasks）⇒ 治本一生效，新包完工即
      N/N，永远不满足「未勾项全是 archive」⇒ **新包反而没人管了**；
    - 而更要紧的是：**这个洞现在就在漏，与治本无关** —— 实测 `openspec/changes/archive/` 下
      50 个已归档包里 **39 个在归档时是 N/N**。一个包从「勾完最后一条」到「跑完 archive」
      之间必然经过 N/N，**它是最常见的形态，不是治本之后才会出现的未来问题**。
    """

    def test_条件一_NN包判为实质完工(self):
        """§3.1ter 要求的第一条。修复前它落进 incomplete，被说成「尚有 0 条真未完项」。"""
        v = M.classify_tasks("- [x] 1.1 ok\n" * 31, "nn-pkg")
        self.assertEqual(v.status, M.COMPLETE)
        self.assertTrue(M.is_substantively_complete(v))

    def test_条件二_未勾项全为archive判为实质完工(self):
        """§3.1ter 要求的第二条（存量 9 个包走这条）。"""
        v = M.classify_tasks("- [x] a\n" * 30 + REAL_SWEEP_OPS + "\n", "sweep-ops")
        self.assertEqual(v.status, M.SUBSTANTIVE)
        self.assertTrue(M.is_substantively_complete(v))

    def test_含一条非archive未勾项_不判实质完工(self):
        """§3.1ter 要求的第三条：`queue-status-machine-field` 47/48 照旧不得放行。"""
        v = M.classify_tasks("- [x] a\n" * 47 + REAL_REAL_UNDONE + "\n", "queue-status")
        self.assertEqual(v.status, M.INCOMPLETE)
        self.assertFalse(M.is_substantively_complete(v))

    def test_NN包的告警措辞是只差归档而非尚有0条(self):
        """🔴 修复前的真实输出是「尚有 0 条真未完项 —— 它没完工」，31/31 却说没完工。"""
        v = M.classify_tasks("- [x] 1.1 ok\n" * 31, "nn-pkg")
        self.assertEqual(M.alert_class(v), M.ALERT_FORGOTTEN)
        phrase = M.alert_phrase(v, 4.2)
        self.assertIn("只差归档这一步", phrase)
        self.assertIn("N/N", phrase)
        self.assertNotIn("尚有 0 条", phrase)
        self.assertNotIn("它没完工", phrase)

    def test_无tasks包不落进未完工类(self):
        """`no-tasks` 曾与 incomplete 共用一条分支，同样会印出「尚有 0 条真未完项」。"""
        v = M.classify_tasks("# tasks\n\n本包无 tasks。\n", "sc2-weekly-report-mvp")
        self.assertEqual(M.alert_class(v), M.ALERT_UNJUDGEABLE)
        self.assertNotIn("尚有 0 条", M.alert_phrase(v, 4.2))


class TestCarriesHumanNote(unittest.TestCase):
    """L2：🔴 本文件最要紧的一组——「这行里有没有人留了话」。

    判据不解析那些字是什么意思（队列 §四 #87 明确否掉了认自然语言那条路：
    「『本次不做』这种话随手就能写，模糊匹配会让降噪变成默认」），
    **只认形态**：一条光秃的 archive 行 vs 一条挂着说明文字的 archive 行。
    """

    def test_三条生产真身_全部判为有人留了话(self):
        """2026-08-23 dry-run 的 3 个命中，一个都不该被自动归档。"""
        for line in (REAL_EDITLOCK, REAL_SWEEP_STARTUP, REAL_SWEEP_OPS):
            with self.subTest(line=line[:40]):
                self.assertTrue(M.carries_human_note(line), f"应判为有人留了话：{line[:60]}")

    def test_真实归档过的光秃形态_判为无人留话(self):
        for line in (REAL_BARE_1, REAL_BARE_2):
            with self.subTest(line=line[:40]):
                self.assertFalse(M.carries_human_note(line))

    def test_带子项的archive行_判为有人留了话(self):
        """sweep-ops 的说明写在**下一行的子项**里，不在本行——须一并看见。"""
        block = (
            "- [ ] 6.5 `/opsx:archive`\n"
            "  - 🔴 **本轮不做，前置条件确实不满足**：3.3 与 5.2 的人眼半边均未闭合\n"
        )
        v = M.classify_tasks(block)
        self.assertEqual(v.status, M.SUBSTANTIVE)
        self.assertTrue(v.unchecked_carry_notes, "带子项说明的 archive 行必须被判为有人留了话")

    def test_光秃行的包_不带留话标记(self):
        v = M.classify_tasks("- [x] 1.1 ok\n" + REAL_BARE_1.replace("[x]", "[ ]") + "\n")
        self.assertEqual(v.status, M.SUBSTANTIVE)
        self.assertFalse(v.unchecked_carry_notes)


class TestRefuseOutsideMainWorkspace(unittest.TestCase):
    """L3：非主工作区一律拒绝执行（派单件 §3.3bis）。

    ⚠️ 这里只覆盖「路径不符」这一半。**「真建一个 linked worktree」那条验收
    （§五-5，明写不许用 mock 代替）尚未做** —— 它属执行路径的验收，而执行路径
    等定夺 4 才建；届时须补，不得因本文件已有 L3 就认为已覆盖。
    """

    def test_路径不是主工作区_拒绝执行(self):
        with self.assertRaises(M.RefuseToRun):
            M.assert_main_workspace(Path(__file__).resolve().parent)

    def test_异常文案说明了为什么拒绝(self):
        try:
            M.assert_main_workspace(Path(__file__).resolve().parent)
        except M.RefuseToRun as exc:
            self.assertIn("不可逆", str(exc))
        else:
            self.fail("应当抛 RefuseToRun")


class TestSweepAlertWording(unittest.TestCase):
    """L4：sweep 滞留告警的三类措辞（端到端，用 2026-08-23 那 4 个被报的包做夹具）。

    🔴 本组的核心断言是**否定式的**：那一轮 4 报 3 误，故断言「疑似遗忘归档」这个措辞
    对它们**一个都不成立**。正向断言（三类各自命中对的对象）是配套，不能替代它——
    只验「新话说对了」而不验「旧话不再说」，旧措辞完全可能仍并存在同一封告警里。
    """

    #: 四个包的 tasks.md 关键内容（未勾项部分逐字取自生产真身）
    FIXTURES = {
        "sweep-startup-nonblocking": ("- [x] x\n" * 25) + REAL_SWEEP_STARTUP + "\n",
        "editlock-hold-scope-and-wip-block": ("- [x] x\n" * 33) + REAL_EDITLOCK + "\n",
        "sweep-ops-webhook-cutover": ("- [x] x\n" * 30) + REAL_SWEEP_OPS + "\n"
                                     + "  - 🔴 **本轮不做，前置条件确实不满足**：3.3 与 5.2 均未闭合\n",
        # 21/23：一条真未完项 ＋ 一条 archive
        "open-pool-reminder-dual-file-and-staleness":
            ("- [x] x\n" * 21) + REAL_OPEN_POOL + "\n- [ ] 5.3 `/opsx:archive`\n",
    }

    def setUp(self):
        import tempfile
        self._tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self._tmp.name)
        (self.repo / "reports").mkdir(parents=True, exist_ok=True)
        for name, body in self.FIXTURES.items():
            d = self.repo / "openspec" / "changes" / name
            d.mkdir(parents=True, exist_ok=True)
            (d / "tasks.md").write_text(body, encoding="utf-8")
        self.sweep = _load_sweep_module()

    def tearDown(self):
        self._tmp.cleanup()

    def _run(self, names=None):
        import unittest.mock as mock
        names = names or list(self.FIXTURES)
        hits = []
        for n in names:
            text = self.FIXTURES[n]
            done = text.count("- [x]")
            todo = text.count("- [ ]")
            hits.append({"change": n, "done": done, "total": done + todo,
                         "rate": done / (done + todo), "days_idle": 4.2,
                         "observation_window_days": None})
        log, sent = [], []
        with mock.patch.object(self.sweep, "_load_webhook_url", return_value=None), \
             mock.patch.object(self.sweep, "_track_and_alert_standing_state",
                               side_effect=lambda *a, **k: sent.append(a)):
            self.sweep._announce_stale_in_flight_changes(self.repo, hits, log)
        return "\n".join(log), sent

    def test_旧措辞对那四个包全部不再成立(self):
        joined, _ = self._run()
        self.assertNotIn("疑似遗忘归档", joined)

    def test_三个实质完工包判为未用机器入口(self):
        joined, _ = self._run()
        for n in ("sweep-startup-nonblocking", "editlock-hold-scope-and-wip-block",
                  "sweep-ops-webhook-cutover"):
            with self.subTest(pkg=n):
                self.assertRegex(joined, rf"`{n}`.*未用机器认得的入口")

    def test_真未完项包不被称为遗忘归档(self):
        joined, _ = self._run()
        self.assertRegex(joined, r"`open-pool-reminder-dual-file-and-staleness`.*尚有 1 条真未完项")

    def test_光秃归档行仍判为真遗忘并沿用原告警路径(self):
        """反向对照：判据没有变成「一律不报」——无人留话时它照样喊。"""
        self.FIXTURES = dict(self.FIXTURES)
        self.FIXTURES["bare-pkg"] = ("- [x] x\n" * 9) + REAL_BARE_1.replace("[x]", "[ ]") + "\n"
        d = self.repo / "openspec" / "changes" / "bare-pkg"
        d.mkdir(parents=True, exist_ok=True)
        (d / "tasks.md").write_text(self.FIXTURES["bare-pkg"], encoding="utf-8")
        joined, _ = self._run(["bare-pkg"])
        self.assertIn("只差归档这一步", joined)
        self.assertIn("疑似遗忘归档", joined)

    def test_NN包端到端走真遗忘路径(self):
        """§3.1ter 的告警侧对照：一个 N/N 的在途包必须被喊「只差归档这一步」。"""
        self.FIXTURES = dict(self.FIXTURES)
        self.FIXTURES["nn-pkg"] = "- [x] x\n" * 31
        d = self.repo / "openspec" / "changes" / "nn-pkg"
        d.mkdir(parents=True, exist_ok=True)
        (d / "tasks.md").write_text(self.FIXTURES["nn-pkg"], encoding="utf-8")
        joined, _ = self._run(["nn-pkg"])
        self.assertIn("只差归档这一步", joined)
        self.assertNotIn("尚有 0 条真未完项", joined)

    def test_告警正文含三条声明入口(self):
        """🔴 告警若只说「你没声明」而不给出声明方式，等于把缺口原样留在那里。"""
        _, sent = self._run()
        self.assertTrue(sent, "应当调用过 _track_and_alert_standing_state")
        render_alert = sent[0][5]
        body = render_alert(sorted(self.FIXTURES))
        for entry in ("暂不归档", "预期观察窗口", "--ack-stale-change"):
            with self.subTest(entry=entry):
                self.assertIn(entry, body)

    def test_判定器不可用时退回原措辞且不中断(self):
        """从低取值：加载失败只降级 + 记日志，不抛、不拖垮 sweep。"""
        import unittest.mock as mock
        with mock.patch.object(self.sweep, "_load_change_classifier", return_value=None):
            joined, _ = self._run()
        self.assertIn("疑似遗忘归档", joined)  # 退回原措辞
        self.assertNotIn("未用机器认得的入口", joined)

    def test_加载失败原因写进日志(self):
        log = []
        import unittest.mock as mock
        with mock.patch.object(self.sweep.importlib.util, "spec_from_file_location",
                               side_effect=RuntimeError("boom")):
            self.assertIsNone(self.sweep._load_change_classifier(log))
        self.assertRegex("\n".join(log), r"完工形态判定器加载失败.*boom")


def _load_sweep_module():
    spec = importlib.util.spec_from_file_location(
        "_sweep_for_alert_test", SCRIPT.with_name("工具-落库sweep.py"))
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


if __name__ == "__main__":
    unittest.main()
