"""`工具-opener块lint.py` 单测（队列 §一 `#284`，OP-0828-Y）。

白盒方式：直接调 `iter_fenced_blocks` / `check_block` / `classify_carrier`，喂**真实存在过的
原文**（截自 `看护件-2026-08-28-可开工批.md` 修前形态、`看护件-2026-08-28-落地后批.md` 修后
形态、`专线opener模板库.md` 二/五节模板），不触碰真实仓库文件、不跑 git。

🔴 本文件存在的理由与 `test_工具-引导样板lint.py` 同：**一道从不报警的门禁与没有门禁等价**，
而「全库跑一遍」的结果会随文档增删漂移，证明不了判据还认得违规。故这里逐形态钉死，
且**每个形态都配一条「改对之后告警消失」的用例**——「两侧都能关掉」是本件的验收条款，
不是顺带一提。
"""
from __future__ import annotations

import importlib.util
import unittest
from datetime import date
from pathlib import Path

SCRIPT = Path(__file__).resolve().with_name("工具-opener块lint.py")


def _load_module():
    spec = importlib.util.spec_from_file_location("_opener_lint_under_test", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


M = _load_module()

TITLE_LINE_NO_EXC = (
    '开工第一件事：调 mcp__ccd_session_mgmt__set_session_title（session_id 传字面量 "self"），'
    "标题：[Win]0827B-LAN留步收尾-354与401"
)
TITLE_LINE_WITH_EXC = (
    '开工第一件事：调 mcp__ccd_session_mgmt__set_session_title（session_id 传字面量 "self"），'
    "标题：[Win]0828O-423切a档与部署。🔴 例外：你若是被 Task/Agent 起的子任务，跳过本行不要执行"
    '——子任务没有自己的 session，"self" 会解析到父 session、把调度你的那条会话改名（2026-08-28 实撞）。'
)
SETTINGS_CC = (
    "【设置】执行环境：CC ｜ CC session：☑ 新开 ｜ worktree：☑ 新建独立 ｜ 分支：由你新建 "
    "｜ 工作区：C:\\Dev\\zhuopin-ai ｜ 派出线：Cowork 环境总线 OP-0828-N"
)
SETTINGS_COWORK = "【设置】执行环境：**Cowork** ｜ 分支：master ｜ worktree：☐"


def _md(*body_lines: str) -> str:
    return "```\n" + "\n".join(body_lines) + "\n```\n"


def _only_block(md: str):
    blocks = M.iter_fenced_blocks(md)
    assert len(blocks) == 1, f"期望 1 个围栏块，实得 {len(blocks)}"
    return blocks[0]


def _forms(md: str) -> set[str]:
    return {form for form, _detail in M.check_block(_only_block(md))}


class 形态一_缺set_session_title(unittest.TestCase):
    """① CC opener 块含 `【设置】` 而无 `set_session_title` ⇒ 告警（生效日 2026-08-26）。"""

    def test_反例_CC模板库二节原文_应命中(self):
        """`专线opener模板库.md` §二「【CC】落库」模板原文——17 次违反的源头之一。"""
        md = _md(
            "【设置】执行环境：**CC** ｜ 分支：master ｜ worktree：☐",
            "读跨桌任务队列 §二，取 〔批次名,如 B-0723XX〕 批次 commit+push+收工重跑台账。",
        )
        self.assertIn("F1", _forms(md))

    def test_正例_补齐那一行后告警消失(self):
        """🔴 验收条款「两侧都能关掉」的前半：把报警的块改对，告警必须自动消失。"""
        md = _md(
            "[OP-0828-Y]【CC】opener 块 lint",
            SETTINGS_CC,
            TITLE_LINE_WITH_EXC,
            "读 ① 机制队列 §一 #284。",
        )
        self.assertEqual(_forms(md), set())

    def test_Cowork块结构性排除_不报(self):
        """🔴 Cowork 侧根本没有 `set_session_title` 这个工具（补充一实测），报了才是噪音。"""
        md = _md(
            SETTINGS_COWORK,
            "读接力文件 + CLAUDE.md 继续。先用 zhuopin-queue-audit 对账并修正队列。",
        )
        self.assertEqual(_forms(md), set())

    def test_执行环境未标_不猜_不判形态一(self):
        """`本周计划-2026-08-03.md` 真实形态：`【设置】` 行早于四字段规则，无执行环境字段。"""
        md = _md(
            "【设置】分支：master ｜ worktree：☐（本线只产改 .md，不写生产码）",
            "读 CLAUDE.md 与跨桌任务队列.md，按队列 #127／#79／#156 三行开工。",
        )
        self.assertEqual(_forms(md), set())
        self.assertIsNone(M.block_env(_only_block(md)))


class 形态二_缺子任务例外句(unittest.TestCase):
    """② 块内有 `set_session_title` 而无子任务例外句 ⇒ 告警（生效日 2026-08-28）。"""

    def test_反例_看护件可开工批修前原文_应命中(self):
        """2026-08-28 实撞那一天，`可开工批` 七处都是这个形态。"""
        md = _md(
            "[OP-0827-B]【CC】LAN 留步收尾",
            SETTINGS_CC,
            TITLE_LINE_NO_EXC,
            "🔴 前置：OP-0827-A 必须已收工且本地 master 与 origin 已对齐。",
        )
        self.assertEqual(_forms(md), {"F2"})

    def test_正例_落地后批修后原文_不报(self):
        """🔴 验收条款「两侧都能关掉」的后半：同一份件补上例外句后实测归零。"""
        md = _md(
            "[OP-0828-O]【CC】#423 切 ⒜ 止血 ＋ 按发布四关部署 .51",
            SETTINGS_CC,
            TITLE_LINE_WITH_EXC,
            "读 ① 队列 §一 #423。",
        )
        self.assertEqual(_forms(md), set())

    def test_裸标准写法块_无设置行_仍受形态二约束(self):
        """模板库补充三之三的「标准写法」是个只有那一行的裸块——它同样必须自带例外句。"""
        self.assertEqual(_forms(_md(TITLE_LINE_NO_EXC)), {"F2"})
        self.assertEqual(_forms(_md(TITLE_LINE_WITH_EXC)), set())

    def test_Cowork块也受形态二约束(self):
        """例外句是给「被原样复制走的那一行」带的，与执行环境无关。"""
        md = _md(SETTINGS_COWORK, TITLE_LINE_NO_EXC)
        self.assertEqual(_forms(md), {"F2"})

    def test_两形态可同时不命中_也可各自单独命中(self):
        both_ok = _md(SETTINGS_CC, TITLE_LINE_WITH_EXC)
        self.assertEqual(_forms(both_ok), set())
        self.assertEqual(_forms(_md(SETTINGS_CC, "读队列 #284。")), {"F1"})
        self.assertEqual(_forms(_md(SETTINGS_CC, TITLE_LINE_NO_EXC)), {"F2"})


class 块识别的假阳性防线(unittest.TestCase):
    def test_散文提及设置二字不算opener块(self):
        """`memory索引收割对账-2026-08-21.md:30` 真实形态：```markdown 块里一行散文提到【设置】。

        裸子串判据会把它点亮；行首锚定不会。同族＝引导样板 lint「讲解反范式的散文不命中」。
        """
        md = "```markdown\n- [CC 开场词带【设置】行](cc-opener-include-worktree-choice.md) — 由出口令方判定\n```\n"
        block = _only_block(md)
        self.assertIsNone(M.settings_line(block))
        self.assertEqual(M.check_block(block), [])

    def test_围栏外的散文不进入扫描面(self):
        md = ("正文里写着 【设置】 行标准四字段 = 执行环境 ｜ 分支 ｜ worktree ｜ 工作区，"
              "以及一句「请调 set_session_title」。\n")
        self.assertEqual(M.iter_fenced_blocks(md), [])

    def test_四反引号围栏内嵌三反引号(self):
        md = "````\n" + SETTINGS_CC + "\n```\n内层\n```\n" + TITLE_LINE_WITH_EXC + "\n````\n"
        blocks = M.iter_fenced_blocks(md)
        self.assertEqual(len(blocks), 1)
        self.assertEqual({f for f, _ in M.check_block(blocks[0])}, set())

    def test_起始行号指向块首行正文(self):
        md = "前言\n\n" + _md(SETTINGS_CC, "读队列。")
        self.assertEqual(_only_block(md).start_line, 4)


class 当前在用件与历史件的区分(unittest.TestCase):
    """🔴 三层判据缺一不可——每层各配一条实测反例。"""

    def test_H1_归档目录段(self):
        bucket, why = M.classify_carrier(
            "1-转型规划/z-已执行归档/开场prompt-旧件.md", "在办", "F1", date(2026, 8, 28))
        self.assertEqual(bucket, "historical")
        self.assertIn("H1", why)

    def test_H2_状态头归桶(self):
        for st in ("已执行归档", "已作废", "历史快照"):
            with self.subTest(st=st):
                bucket, why = M.classify_carrier("a/b.md", st, "F1", date(2026, 8, 28))
                self.assertEqual(bucket, "historical")
                self.assertIn("H2", why)

    def test_H3_规则生效后未再编辑_判历史(self):
        """`本周计划-2026-08-03.md` 实测：状态头至今写 `在办`（季度回填滞后），

        最后提交 2026-08-04 —— **只有 H3 能把它判成历史件**，H2 单独用会误判成当前在用。
        """
        bucket, why = M.classify_carrier(
            "1-转型规划/0-全景路线图/本周计划-2026-08-03.md", "在办", "F1", date(2026, 8, 4))
        self.assertEqual(bucket, "historical")
        self.assertIn("H3", why)

    def test_规则生效后仍在改的生效件_判当前在用(self):
        """`专线opener模板库.md` 实测：`status: 生效`、2026-08-28 仍在改 ⇒ 三层都不命中。

        它里面那三个缺 `set_session_title` 的 CC 模板正是 17 次违反的源头，**必须报出来**。
        """
        bucket, _ = M.classify_carrier(
            "1-转型规划/0-全景路线图/专线opener模板库.md", "生效", "F1", date(2026, 8, 28))
        self.assertEqual(bucket, "current")

    def test_两形态生效日不同(self):
        """08-27 提交的件：对形态①（08-26 生效）算当前在用，对形态②（08-28 生效）算历史。"""
        d = date(2026, 8, 27)
        self.assertEqual(M.classify_carrier("a/b.md", "在办", "F1", d)[0], "current")
        self.assertEqual(M.classify_carrier("a/b.md", "在办", "F2", d)[0], "historical")

    def test_git历史取不到_不静默回退(self):
        """🔴 浅克隆时不得静默当成「很早」（那会把整库判成历史件、门禁静默失效）。"""
        bucket, why = M.classify_carrier("a/b.md", "在办", "F1", None)
        self.assertEqual(bucket, "unknown-history")
        self.assertIn("git 历史取不到", why)


if __name__ == "__main__":
    unittest.main()
