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


if __name__ == "__main__":
    unittest.main()
