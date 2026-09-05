"""`工具-opener块lint.py` 单测（队列 §一 `#284`／`#381`⑸ⓖ，OP-0828-Y／OP-0904-A）。

白盒方式：直接调 `iter_fenced_blocks` / `check_block` / `classify_carrier` / `scan_single_file`，
喂**真实存在过的原文**（截自 `看护件-2026-08-28-可开工批.md` 修前形态、`看护件-2026-08-28-落地
后批.md` 修后形态、`专线opener模板库.md` §〇.00 骨架、`OP-0828-N` 真实历史 opener），不触碰
真实仓库文件、不跑 git。

🔴 本文件存在的理由与 `test_工具-引导样板lint.py` 同：**一道从不报警的门禁与没有门禁等价**，
而「全库跑一遍」的结果会随文档增删漂移，证明不了判据还认得违规。故这里逐形态钉死，
且**每个形态都配一条「改对之后告警消失」的用例**——「两侧都能关掉」是本件的验收条款，
不是顺带一提。

**2026-09-04 扩三形态（③④⑤）**：既有 `SETTINGS_CC` / `SETTINGS_COWORK` 两个共享夹具原本
只满足形态①②的判据，**在形态④⑤生效后不再是「干净样本」**（原 `SETTINGS_CC` 字段顺序有误、
原 `SETTINGS_COWORK` 字段残缺，且两个共享夹具都没配过合规首行）——已改为六字段齐、顺序对
的标准写法；原始（有缺陷的）真实文本保留为 `SETTINGS_CC_WRONG_ORDER`，专供形态④反例使用，
不丢弃「这是真实撞过的原文」这条既有验收哲学。
"""
from __future__ import annotations

import importlib.util
import tempfile
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
#: §〇.00 骨架原样未填占位符——形态③要抓的正是「照抄了但没替换」。
TITLE_LINE_PLACEHOLDER_NOT_FILLED = (
    '开工第一件事：调 mcp__ccd_session_mgmt__set_session_title（session_id 传字面量 "self"），'
    "标题：[Win]MMDDX-<短名>。🔴 例外：你若是被 Task/Agent 起的子任务，跳过本行不要执行"
    '——子任务没有自己的 session，"self" 会解析到父 session、把调度你的那条会话改名（2026-08-28 实撞）。'
)

#: 六字段齐、顺序对（§〇.00 canonical）——用于「应当干净」的正例。
SETTINGS_CC = (
    "【设置】执行环境：CC ｜ 分支：master（从 master 起 `claude/op0904a-test`）｜ "
    "worktree：☑（test-wt，新 worktree，收工自删）｜ 工作区：无 ｜ session：新开 ｜ 派出线：环境总线"
)
SETTINGS_COWORK = (
    "【设置】执行环境：Cowork ｜ 分支：master ｜ worktree：☐（不建，只产改 `.md`）｜ "
    "工作区：无 ｜ session：新开 ｜ 派出线：环境总线"
)
#: 🔴 `OP-0828-N` 真实历史原文（截自 `看护件-2026-08-28-可开工批.md` 同期实撞）——
#: `分支`/`worktree` 顺序颠倒，且用「CC session」而非骨架标准的「session」。专供形态④反例。
SETTINGS_CC_WRONG_ORDER = (
    "【设置】执行环境：CC ｜ CC session：☑ 新开 ｜ worktree：☑ 新建独立 ｜ 分支：由你新建 "
    "｜ 工作区：C:\\Dev\\zhuopin-ai ｜ 派出线：Cowork 环境总线 OP-0828-N"
)

#: 合规首行（形态⑤）——短名分别为 11 字／6 字，均 ≤12。
TITLE_LINE_CC = "[OP-0828-Y]【CC】opener块lint"
TITLE_LINE_COWORK = "[OP-0828-N]【Cowork】接力文件核对"


def _md(*body_lines: str) -> str:
    return "```\n" + "\n".join(body_lines) + "\n```\n"


def _only_block(md: str):
    blocks = M.iter_fenced_blocks(md)
    assert len(blocks) == 1, f"期望 1 个围栏块，实得 {len(blocks)}"
    return blocks[0]


def _forms(md: str) -> set[str]:
    return {form for form, _detail in M.check_block(_only_block(md))}


def _form_details(md: str) -> dict[str, str]:
    return dict(M.check_block(_only_block(md)))


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
            TITLE_LINE_CC,
            SETTINGS_CC,
            TITLE_LINE_WITH_EXC,
            "读 ① 机制队列 §一 #284。",
        )
        self.assertEqual(_forms(md), set())

    def test_Cowork块结构性排除_不报(self):
        """🔴 Cowork 侧根本没有 `set_session_title` 这个工具（补充一实测），报了才是噪音。"""
        md = _md(
            TITLE_LINE_COWORK,
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
        forms = _forms(md)
        self.assertNotIn("F1", forms)
        self.assertIsNone(M.block_env(_only_block(md)))
        # 🔴 「不猜环境」与「字段不全」是两件独立的事：本行同时暴露六字段骨架下的
        # 真实缺陷（只写两字段），形态四理应命中，不能用同一断言把它一并掩盖。
        self.assertIn("F4", forms)


class 形态二_缺子任务例外句(unittest.TestCase):
    """② 块内有 `set_session_title` 而无子任务例外句 ⇒ 告警（生效日 2026-08-28）。"""

    def test_反例_看护件可开工批修前原文_应命中(self):
        """2026-08-28 实撞那一天，`可开工批` 七处都是这个形态。"""
        md = _md(
            "[OP-0827-B]【CC】LAN留步收尾",
            SETTINGS_CC,
            TITLE_LINE_NO_EXC,
            "🔴 前置：OP-0827-A 必须已收工且本地 master 与 origin 已对齐。",
        )
        self.assertEqual(_forms(md), {"F2"})

    def test_正例_落地后批修后原文_不报(self):
        """🔴 验收条款「两侧都能关掉」的后半：同一份件补上例外句后实测归零。"""
        md = _md(
            "[OP-0828-O]【CC】423切止血",
            SETTINGS_CC,
            TITLE_LINE_WITH_EXC,
            "读 ① 队列 §一 #423。",
        )
        self.assertEqual(_forms(md), set())

    def test_裸标准写法块_无设置行_仍受形态二约束(self):
        """模板库补充三之三的「标准写法」是个只有那一行的裸块——它同样必须自带例外句。

        🔴 无 `【设置】` 行 ⇒ `is_opener=False` ⇒ 形态④⑤（均以 `is_opener` 为门槛）不适用，
        本用例继续只钉死形态二，与新增形态互不干扰。
        """
        self.assertEqual(_forms(_md(TITLE_LINE_NO_EXC)), {"F2"})
        self.assertEqual(_forms(_md(TITLE_LINE_WITH_EXC)), set())

    def test_Cowork块也受形态二约束(self):
        """例外句是给「被原样复制走的那一行」带的，与执行环境无关。"""
        md = _md(TITLE_LINE_COWORK, SETTINGS_COWORK, TITLE_LINE_NO_EXC)
        self.assertEqual(_forms(md), {"F2"})

    def test_两形态可同时不命中_也可各自单独命中(self):
        both_ok = _md(TITLE_LINE_CC, SETTINGS_CC, TITLE_LINE_WITH_EXC)
        self.assertEqual(_forms(both_ok), set())
        self.assertEqual(
            _forms(_md(TITLE_LINE_CC, SETTINGS_CC, "读队列 #284。")), {"F1"})
        self.assertEqual(
            _forms(_md(TITLE_LINE_CC, SETTINGS_CC, TITLE_LINE_NO_EXC)), {"F2"})


class 形态三_标题值格式错(unittest.TestCase):
    """③ CC 侧块有 `set_session_title` 调用，标题值须匹配 `[Win]MMDDX-<短名>`（生效日 2026-09-04）。"""

    def test_骨架占位符未替换_应命中(self):
        """照抄 §〇.00 骨架却忘了把 `MMDDX` 换成真实日期＋字母——本判据要抓的正是这种。"""
        md = _md(TITLE_LINE_CC, SETTINGS_CC, TITLE_LINE_PLACEHOLDER_NOT_FILLED, "读队列。")
        self.assertEqual(_forms(md), {"F3"})

    def test_正例_替换为真实日期字母后告警消失(self):
        md = _md(TITLE_LINE_CC, SETTINGS_CC, TITLE_LINE_WITH_EXC, "读队列。")
        self.assertEqual(_forms(md), set())

    def test_Cowork块不受形态三约束(self):
        """§〇.00 原文明写「CC 块」——Cowork 没有 `set_session_title` 工具，同形态一既有收窄理由。"""
        md = _md(TITLE_LINE_COWORK, SETTINGS_COWORK, TITLE_LINE_PLACEHOLDER_NOT_FILLED)
        self.assertNotIn("F3", _forms(md))

    def test_无set_session_title调用时不判形态三(self):
        """形态一已经在管「压根没调用」这件事，形态三只管「调用了但标题值不对」，避免重复告警。"""
        md = _md(TITLE_LINE_CC, SETTINGS_CC, "读队列 #284。")
        self.assertNotIn("F3", _forms(md))


class 形态四_设置六字段缺失或顺序错(unittest.TestCase):
    """④ `【设置】` 六字段（执行环境｜分支｜worktree｜工作区｜session｜派出线）缺失或顺序错（生效日 2026-09-04）。"""

    def test_历史真实顺序错文本_应命中(self):
        """`OP-0828-N` 真实历史原文——`分支`/`worktree` 颠倒 ＋ 用「CC session」而非「session」。"""
        md = _md(TITLE_LINE_CC, SETTINGS_CC_WRONG_ORDER, TITLE_LINE_WITH_EXC)
        self.assertIn("F4", _forms(md))

    def test_缺字段_应命中且详情列出缺失项(self):
        settings = "【设置】执行环境：CC ｜ 分支：master ｜ worktree：☐"
        md = _md(TITLE_LINE_CC, settings, TITLE_LINE_WITH_EXC)
        detail = _form_details(md).get("F4", "")
        self.assertIn("工作区", detail)
        self.assertIn("session", detail)
        self.assertIn("派出线", detail)

    def test_正例_六字段齐且顺序对_告警消失(self):
        md = _md(TITLE_LINE_CC, SETTINGS_CC, TITLE_LINE_WITH_EXC)
        self.assertNotIn("F4", _forms(md))

    def test_Cowork块同受形态四约束(self):
        """§〇.00 两套骨架六字段顺序相同——本形态不分执行环境，与形态①③刻意不同。"""
        md = _md(TITLE_LINE_COWORK, "【设置】执行环境：Cowork ｜ worktree：☐ ｜ 分支：master")
        self.assertIn("F4", _forms(md))

    def test_非opener块不受形态四约束(self):
        """无 `【设置】` 行 ⇒ 不是 opener 块，形态四不适用（同形态五的门槛）。"""
        self.assertNotIn("F4", _forms(_md(TITLE_LINE_WITH_EXC)))


class 形态五_首行格式错(unittest.TestCase):
    """⑤ opener 块首行须为 `[OP-MMDD-X]【CC／Cowork】<短名，≤12字>`（生效日 2026-09-04）。"""

    def test_无首行_直接以设置行开头_应命中(self):
        md = _md(SETTINGS_CC, TITLE_LINE_WITH_EXC)
        self.assertIn("F5", _forms(md))

    def test_短名超过12字_应命中(self):
        md = _md("[OP-0904-A]【CC】" + "短" * 13, SETTINGS_CC, TITLE_LINE_WITH_EXC)
        self.assertIn("F5", _forms(md))

    def test_短名恰好12字_不命中(self):
        md = _md("[OP-0904-A]【CC】" + "短" * 12, SETTINGS_CC, TITLE_LINE_WITH_EXC)
        self.assertNotIn("F5", _forms(md))

    def test_编号缺连字符_不匹配(self):
        """`OP0823B`（缺连字符）等既往漂移写法——本判据是精确格式判据，不做模糊容错。"""
        md = _md("[OP0904A]【CC】opener块lint", SETTINGS_CC, TITLE_LINE_WITH_EXC)
        self.assertIn("F5", _forms(md))

    def test_Cowork块也受形态五约束(self):
        md_bad = _md(SETTINGS_COWORK, "读接力文件。")
        self.assertIn("F5", _forms(md_bad))
        md_ok = _md(TITLE_LINE_COWORK, SETTINGS_COWORK, "读接力文件。")
        self.assertNotIn("F5", _forms(md_ok))

    def test_非opener块不受形态五约束(self):
        self.assertNotIn("F5", _forms(_md(TITLE_LINE_WITH_EXC)))


class 设置字段顺序判据_settings_field_order_problems(unittest.TestCase):
    """直接钉死 `_settings_field_order_problems` 辅助函数（形态四的核心判据）。"""

    def test_全齐且顺序对(self):
        missing, out_of_order = M._settings_field_order_problems(
            "【设置】执行环境：CC ｜ 分支：master ｜ worktree：☑ ｜ 工作区：无 ｜ session：新开 ｜ 派出线：环境总线"
        )
        self.assertEqual(missing, [])
        self.assertEqual(out_of_order, [])

    def test_顺序颠倒(self):
        _missing, out_of_order = M._settings_field_order_problems(
            "【设置】执行环境：CC ｜ worktree：☑ ｜ 分支：master"
        )
        self.assertIn("分支→worktree", out_of_order)

    def test_缺字段_按骨架顺序列出(self):
        missing, _out_of_order = M._settings_field_order_problems("【设置】执行环境：CC ｜ 分支：master")
        self.assertEqual(missing, ["worktree", "工作区", "session", "派出线"])


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
        md = ("````\n" + TITLE_LINE_CC + "\n" + SETTINGS_CC + "\n```\n内层\n```\n"
              + TITLE_LINE_WITH_EXC + "\n````\n")
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

    def test_三个新形态生效日均为20260904(self):
        """形态③④⑤ 同日生效——早于当日提交的件对三者均判历史，晚于/当日则判当前。"""
        before = date(2026, 9, 3)
        after = date(2026, 9, 4)
        for form in ("F3", "F4", "F5"):
            with self.subTest(form=form):
                self.assertEqual(M.classify_carrier("a/b.md", "在办", form, before)[0], "historical")
                self.assertEqual(M.classify_carrier("a/b.md", "在办", form, after)[0], "current")

    def test_git历史取不到_不静默回退(self):
        """🔴 浅克隆时不得静默当成「很早」（那会把整库判成历史件、门禁静默失效）。"""
        bucket, why = M.classify_carrier("a/b.md", "在办", "F1", None)
        self.assertEqual(bucket, "unknown-history")
        self.assertIn("git 历史取不到", why)


class file自检模式_scan_single_file(unittest.TestCase):
    """`--file` 单文件自检（队列 §一 `#381`⑸ⓖ）：不查 git、不分当前/历史，全部按当前处理。"""

    def test_干净块零命中(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "draft.md"
            p.write_text(_md(TITLE_LINE_CC, SETTINGS_CC, TITLE_LINE_WITH_EXC), encoding="utf-8")
            self.assertEqual(M.scan_single_file(p), [])

    def test_有问题的块全部按当前处理不查git(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "draft.md"
            # 未加入 git 的临时文件——若走主扫描路径的 H3 判据会因「git 历史取不到」
            # 落入 unknown-history 桶；--file 模式必须完全绕开这条路径。
            p.write_text(_md(SETTINGS_CC, TITLE_LINE_WITH_EXC), encoding="utf-8")
            findings = M.scan_single_file(p)
            self.assertTrue(any(f.form == "F5" for f in findings))
            self.assertTrue(all(f.bucket == "current" for f in findings))

    def test_非opener非title块不进入候选(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "draft.md"
            p.write_text("```\n普通代码，无关 opener\n```\n", encoding="utf-8")
            self.assertEqual(M.scan_single_file(p), [])


class 形态六_子任务泳道opener含session标题(unittest.TestCase):
    """⑥ 看护者用 Task/Agent 派发的子任务泳道 opener 含 `set_session_title` ⇒ 告警
    （队列 §一 `#487`，2026-08-28／2026-09-05 两次实撞后 Shao Peishen 拍板 (甲)：
    源头不放，不再指望文本例外句被子 agent 真正遵守）。"""

    #: 截自 B-0905_B 真实结构：§三 一条 `### A1` 泳道 opener（正确写法，无 title）＋
    #: `## 三bis` 看护者自己的开场词（正确写法，含 title＋例外句）。
    _WATCHER_FILE_CLEAN = "\n".join([
        "### A1 · 示例泳道",
        "",
        "粘贴端：CC ｜ 泳道：示例泳道",
        "",
        _md(TITLE_LINE_CC, SETTINGS_CC, "做什么：建造到底，不设 session 标题。"),
        "",
        "## 三bis、看护opener（单次粘贴，Task/Agent 工具起子任务）",
        "",
        _md("[OP-0905-C]【CC】看护示例", SETTINGS_CC, TITLE_LINE_WITH_EXC),
    ])

    #: 同结构，但 `### A1` 泳道 opener 里**错误地**保留了 `set_session_title`。
    _WATCHER_FILE_LANE_HAS_TITLE = "\n".join([
        "### A1 · 示例泳道",
        "",
        "粘贴端：CC ｜ 泳道：示例泳道",
        "",
        _md(TITLE_LINE_CC, SETTINGS_CC, TITLE_LINE_WITH_EXC, "做什么：建造到底。"),
        "",
        "## 三bis、看护opener（单次粘贴，Task/Agent 工具起子任务）",
        "",
        _md("[OP-0905-C]【CC】看护示例", SETTINGS_CC, TITLE_LINE_WITH_EXC),
    ])

    def test_泳道opener正确写法_无title_不报任何形态(self):
        """🔴 验收条款「两侧都能关掉」：§三 泳道 opener 不放 title 是**正确写法**，
        既不该命中形态①（旧判据的镜像），也不该命中形态⑥。"""
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "draft.md"
            p.write_text(self._WATCHER_FILE_CLEAN, encoding="utf-8")
            self.assertEqual(M.scan_single_file(p), [])

    def test_泳道opener错误保留title_命中形态六(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "draft.md"
            p.write_text(self._WATCHER_FILE_LANE_HAS_TITLE, encoding="utf-8")
            findings = M.scan_single_file(p)
            forms = {f.form for f in findings}
            self.assertIn("F6", forms)
            # 看护者自己那个块（§三bis 之后）写法完全合规，不该被错误牵连出任何命中。
            watcher_line = M._watcher_section_line(self._WATCHER_FILE_LANE_HAS_TITLE)
            self.assertFalse(any(f.line >= watcher_line for f in findings))

    def test_看护者自己的开场词不受形态六约束_仍要求title(self):
        """`## 三bis` 之后的块＝看护者真正会被粘贴进新 CC 会话的那一份，
        原形态①②③判据照常生效——缺 title 仍应报 F1，不因为「同文件含三bis」被误伤。"""
        md_no_title = "\n".join([
            "### A1 · 示例泳道",
            "",
            "粘贴端：CC ｜ 泳道：示例泳道",
            "",
            _md(TITLE_LINE_CC, SETTINGS_CC, "做什么：建造到底，不设 session 标题。"),
            "",
            "## 三bis、看护opener（单次粘贴，Task/Agent 工具起子任务）",
            "",
            _md("[OP-0905-C]【CC】看护示例", SETTINGS_CC, "读队列 #487 恢复上下文，按看护件执行。"),
        ])
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "draft.md"
            p.write_text(md_no_title, encoding="utf-8")
            findings = M.scan_single_file(p)
            self.assertTrue(any(f.form == "F1" for f in findings))

    def test_无三bis小节的文件_泳道opener仍按原判据要求title(self):
        """无头单泳道派发批次（如 B-0904_J）没有看护者、`### A<N>` 就是真正的顶层
        `claude -p` 会话——形态⑥判据不适用，缺 title 仍是形态①。"""
        md = "\n".join([
            "### A1 · 存量批次排查",
            "",
            "粘贴端：CC ｜ 泳道：queue-skip13",
            "",
            _md(SETTINGS_CC, "做什么：排查登记。"),
        ])
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "draft.md"
            p.write_text(md, encoding="utf-8")
            findings = M.scan_single_file(p)
            self.assertTrue(any(f.form == "F1" for f in findings))
            self.assertFalse(any(f.form == "F6" for f in findings))

    def test_watcher_section_line与is_subtask_lane_helper(self):
        text = self._WATCHER_FILE_CLEAN
        line = M._watcher_section_line(text)
        self.assertIsNotNone(line)
        blocks = M.iter_fenced_blocks(text)
        self.assertEqual(len(blocks), 2)
        self.assertTrue(M._is_subtask_lane_block(blocks[0], line))
        self.assertFalse(M._is_subtask_lane_block(blocks[1], line))
        self.assertFalse(M._is_subtask_lane_block(blocks[0], None))


if __name__ == "__main__":
    unittest.main()
