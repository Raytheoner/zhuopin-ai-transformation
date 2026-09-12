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
import re
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
#: 收工哨兵行（形态⑨，队列 §一 `#550`，2026-09-10）——子任务泳道块的「干净样本」自此必须带它，
#: 同 2026-09-04 扩形态时把 `SETTINGS_CC` 改为六字段齐的做法：**共享夹具必须满足全部现行判据**。
SENTINEL_LINE = (
    "🔴 收工以顶格一行 `OPENER_DONE` 收尾；命中 🟡/🔴 决策点则以 "
    "`OPENER_PARTIAL: 停在<档位>决策点——<在等什么>` 收尾（批处理器判成败双指标之一）。"
)
#: 心跳约定行（形态⑩，队列 §一 `#565`，2026-09-12）——子任务泳道块的「干净样本」自此
#: 也必须带它，同 `SENTINEL_LINE` 那条注释的既有纪律：**共享夹具必须满足全部现行判据**。
HEARTBEAT_LINE = (
    "🔴 心跳跑命令写 `heartbeat --lane <泳道标识> --text \"...\"`"
    "（收工带 `--done --batch <批次>`）。"
)
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
        _md(TITLE_LINE_CC, SETTINGS_CC, "做什么：建造到底，不设 session 标题。",
            HEARTBEAT_LINE, SENTINEL_LINE),
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
        _md(TITLE_LINE_CC, SETTINGS_CC, TITLE_LINE_WITH_EXC, "做什么：建造到底。", SENTINEL_LINE),
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


class 形态七_有做什么段却缺不做什么段(unittest.TestCase):
    """⑦ opener 块有「做什么：」段标题独立行却无「不做什么：」段标题独立行 ⇒ 告警
    （队列 §一 `#487` 子项／`OP-0906-I`，2026-09-06 实撞「`--dont` 静默丢弃」后定）。

    🔴 成因不是「少写一段」这种美观问题：【Cowork】骨架此前根本没有这一段，
    `工具-opener生成.py --env Cowork --dont "…"` 传进来的硬约束**既不出现在成品里、
    也不报错**——参数被接受却不生效，比被拒绝更危险。
    """

    def test_反例_Cowork骨架修前形态_命中F7(self):
        """`opener骨架.md`【Cowork】骨架 2026-09-06 修前原文：只有做什么／收工两段。"""
        md = _md(
            TITLE_LINE_COWORK,
            SETTINGS_COWORK,
            "读 ① `1-转型规划/0-全景路线图/示例件.md` → ② `CLAUDE.md` 恢复上下文。本件为 A 类。",
            "",
            "做什么：",
            "1. 拆件回灌。",
            "",
            "收工：产出登记 §二 待 commit 批次，由落库 sweep 取活。",
        )
        self.assertIn("F7", _forms(md))

    def test_正例_补上不做什么段后告警消失(self):
        """🔴 验收条款「两侧都能关掉」：补段之后 F7 必须自动消失。"""
        md = _md(
            TITLE_LINE_COWORK,
            SETTINGS_COWORK,
            "读 ① `1-转型规划/0-全景路线图/示例件.md` → ② `CLAUDE.md` 恢复上下文。本件为 A 类。",
            "",
            "做什么：",
            "1. 拆件回灌。",
            "",
            "不做什么：",
            "- 不动销售域。",
            "",
            "收工：产出登记 §二 待 commit 批次，由落库 sweep 取活。",
        )
        self.assertNotIn("F7", _forms(md))

    def test_CC侧同受约束_不做环境分流(self):
        """判据对 CC／Cowork 一视同仁——CC 骨架本来就有这一段，只是此前从未被机器守过。"""
        md = _md(
            TITLE_LINE_CC,
            SETTINGS_CC,
            TITLE_LINE_WITH_EXC,
            "读 ① `1-转型规划/0-全景路线图/示例件.md` → ② `CLAUDE.md` 恢复上下文。本件为 A 类。",
            "",
            "做什么：",
            "1. 建造到底。",
        )
        self.assertIn("F7", _forms(md))

    def test_无分段结构的裸块不受约束(self):
        """🔴 假阳性防线：库里大量 opener 把「做什么：建造到底。」写成一整行散文
        （非段标题）——那类块没有分段结构，补一个空的「不做什么：」段毫无意义。
        判据要求段标题**独占一行且行尾无正文**，故这类块结构性排除。"""
        md = _md(
            TITLE_LINE_COWORK,
            SETTINGS_COWORK,
            "做什么：拆件回灌，收工登记 §二。",
        )
        self.assertNotIn("F7", _forms(md))

    def test_不做什么这一行不得被误判成做什么段(self):
        """🔴 子串陷阱：`"做什么："` 天然是 `"不做什么："` 的子串。若判据用裸 `in`，
        一个**只有**「不做什么：」段的块会被误判成「有做什么段」而命中 F7。"""
        md = _md(
            TITLE_LINE_COWORK,
            SETTINGS_COWORK,
            "读 ① `1-转型规划/0-全景路线图/示例件.md` → ② `CLAUDE.md` 恢复上下文。本件为 A 类。",
            "",
            "不做什么：",
            "- 不动销售域。",
        )
        self.assertNotIn("F7", _forms(md))
        self.assertFalse(M.DO_SECTION_RE.match("不做什么："))
        self.assertTrue(M.DONT_SECTION_RE.match("不做什么："))
        self.assertTrue(M.DO_SECTION_RE.match("做什么："))

    def test_加粗写法同样认得(self):
        md = _md(
            TITLE_LINE_COWORK,
            SETTINGS_COWORK,
            "",
            "**做什么：**",
            "1. 拆件回灌。",
        )
        self.assertIn("F7", _forms(md))

    def test_非opener块不受形态七约束(self):
        """无 `【设置】` 行 ⇒ 不是 opener 块，形态⑦不适用（同 F4/F5 既有边界）。"""
        md = _md("做什么：", "1. 随手记的清单，不是 opener。")
        self.assertNotIn("F7", _forms(md))

    def test_生效日为20260906(self):
        self.assertEqual(M.RULE_EFFECTIVE_BY_FORM["F7"], date(2026, 9, 6))
        self.assertIn("F7", M.FORM_TITLE)


class 格式正本自身被判成违规(unittest.TestCase):
    """队列 §一 `#493`：判据把**自己的格式正本** `opener骨架.md` 判成 8 处违规。

    2026-09-06 15:53 UTC 主仓实跑坐实（`OP-0906-AA`）：只要骨架件处于脏改动中，
    release 侧 opener 守卫就拿 `check_block` 去判它，它自己的占位符（`MMDDX`／
    `[OP-MMDD-X]`）当场命中 ⇒ release 被拒、锁保持占用，这正是 `#398` ⑺「sweep
    自撞锁」当天四轮的触发源。

    🔴 **本类的验收哲学是「换判据，不是关掉」**——所以每一条「正本内不报 FN」的
    用例，都配一条「正本漂了就报 CN」的用例；只写前一半 ＝ 把守卫关掉了事，那正是
    `#493` 期望产出明确禁止的。
    """

    #: 骨架件里那三个真实占位符块的最小复刻（截自 `opener骨架.md` §【CC】骨架）。
    CANON_FIRST_LINE = "[OP-MMDD-X]【CC】<短名，≤12字>"
    CANON_SETTINGS = (
        "【设置】执行环境：CC ｜ 分支：master（从 master 起 `claude/opMMDDx-<短横线名>`）｜ "
        "worktree：☑（<worktree名>，新 worktree，收工自删）｜ 工作区：无 ｜ session：新开 ｜ "
        "派出线：<线名 OP-MMDD-X>"
    )
    CANON_TITLE_LINE = TITLE_LINE_PLACEHOLDER_NOT_FILLED

    #: 陪衬块：一个**中性**的 Cowork opener 块，只为把 opener 块数顶到 `C0` 的
    #: 门槛（≥2）——正本按定义是多份范例的集合，见 `#489` ⑴ 防外溢条。
    #: 🔴 **必须中性**：不含 `set_session_title`、不含例外句 ⇒ 对 C1/C2 的判定
    #: （「有没有**任何一个**块在教这两件事」）零影响，各条用例的断言不被它篡改；
    #: 首行与六字段都用占位符原形 ⇒ 自身不触发 C5/F4/F7。
    CANON_FILLER_BLOCK = (
        "[OP-MMDD-X]【Cowork】<短名，≤12字>\n"
        "【设置】执行环境：Cowork ｜ 分支：master ｜ worktree：☐ ｜ 工作区：无 ｜ "
        "session：新开 ｜ 派出线：<线名 OP-MMDD-X>\n"
        "读 CLAUDE.md。"
    )

    def _canon(self, *body_lines: str) -> Path:
        """把内容写进一份**自称格式正本**的临时件。

        🔴 **判据 2026-09-08（`#489` ⑴）起改为件自己的 frontmatter 声明**
        （`opener正本: 骨架`），不再是路径——原因是按路径就得维护一张文件名清单，
        而 `#489` 期望产出明写「不得写死文件名清单」（`opener骨架.md` 在清单里、
        `专线opener模板库.md` 不在，后者因此恒报 13 处）。
        路径仍按正本落，用来同时守住 `is_format_canon` 那条「不做 basename 匹配」
        的旧结论；但**生效的判据是 frontmatter**。
        """
        d = tempfile.TemporaryDirectory()
        self.addCleanup(d.cleanup)
        p = Path(d.name) / M.SKELETON_CANON_REL
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(
            "---\ntitle: \"骨架夹具\"\nstatus: 生效\n"
            f"{M.CANON_ROLE_KEY}: {M.CANON_ROLE_SKELETON}\n---\n\n"
            + _md(*body_lines) + "\n" + _md(self.CANON_FILLER_BLOCK),
            encoding="utf-8")
        return p

    # ── 判据识别 ────────────────────────────────────────────────
    def test_is_format_canon认相对路径与绝对路径(self):
        self.assertTrue(M.is_format_canon(M.SKELETON_CANON_REL))
        self.assertTrue(M.is_format_canon(M.SKELETON_CANON_REL.replace("/", "\\")))
        self.assertTrue(M.is_format_canon("C:/x/" + M.SKELETON_CANON_REL))

    def test_is_format_canon不做basename匹配(self):
        """🔴 归档目录里另有同名历史副本，basename 匹配会把它们一并静默排除。"""
        self.assertFalse(M.is_format_canon("z-已执行归档/opener骨架.md"))
        self.assertFalse(M.is_format_canon("opener骨架.md"))

    # ── 真身回归：仓库里那份格式正本必须零违规 ────────────────
    def test_仓库真身的格式正本零违规(self):
        """🔴 用**仓库里那份真文件**跑，不用夹具——`#493` 要根治的就是它。
        它一旦再被判成违规，release 又会被自己的格式正本卡住。"""
        canon = M.REPO_ROOT / M.SKELETON_CANON_REL
        self.assertTrue(canon.is_file(), f"格式正本不在了：{canon}")
        self.assertEqual([f.render() for f in M.scan_single_file(canon)], [])

    # ── 形态①②③⑤ 在正本内换判据（不是关掉，见下方 C 系用例）──
    def test_正本内不报形态三与形态五(self):
        p = self._canon(self.CANON_FIRST_LINE, self.CANON_SETTINGS, self.CANON_TITLE_LINE,
                        "做什么：", "1. …", "不做什么：", "- …")
        self.assertEqual([f.form for f in M.scan_single_file(p)], [])

    def test_同样内容在普通件里照报形态三与形态五(self):
        """🔴 排除不得外溢：换个路径，同一段文本必须照样命中 F3/F5——否则
        「照抄骨架却漏填占位符」这个形态③本来要抓的东西就被一起放掉了。"""
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "派单件-x.md"
            p.write_text(_md(self.CANON_FIRST_LINE, self.CANON_SETTINGS,
                             self.CANON_TITLE_LINE), encoding="utf-8")
            forms = {f.form for f in M.scan_single_file(p)}
            self.assertIn("F3", forms)
            self.assertIn("F5", forms)

    def test_正本内不报形态一(self):
        """【CC · 子任务泳道】骨架**刻意不放** `set_session_title`（源头不放，
        `#487`(甲)），正本里这个块不该被形态①点亮。"""
        p = self._canon(self.CANON_FIRST_LINE, self.CANON_SETTINGS, "读队列 §一 `#N`。")
        # 只断言 F1 不再出现：这份只含一个泳道块的夹具**同时**会命中 C1/C2
        # （正本里再没有别的块教 title 与例外句了），而那正是「换判据」的另一半、
        # 由本类下方两条用例各自钉死 —— 此处不把两件事搅在一个断言里。
        self.assertNotIn("F1", {f.form for f in M.scan_single_file(p)})

    # ── 与占位符无关的形态④⑦ 在正本内**照常生效** ────────────
    def test_正本内形态四照常生效(self):
        p = self._canon(self.CANON_FIRST_LINE, "【设置】执行环境：CC ｜ worktree：☑ ｜ 分支：master",
                        self.CANON_TITLE_LINE)
        self.assertIn("F4", {f.form for f in M.scan_single_file(p)})

    def test_正本内形态七照常生效(self):
        p = self._canon(self.CANON_FIRST_LINE, self.CANON_SETTINGS, self.CANON_TITLE_LINE,
                        "做什么：", "1. …")
        self.assertIn("F7", {f.form for f in M.scan_single_file(p)})

    # ── 换上去的那半：正本漂了就发信号 ────────────────────────
    def test_正本首行占位符漂了报C5(self):
        p = self._canon("[OP-0907-Z]【CC】随手写的", self.CANON_SETTINGS, self.CANON_TITLE_LINE)
        self.assertIn("C5", {f.form for f in M.scan_single_file(p)})

    def test_正本标题占位符漂了报C3(self):
        drifted = self.CANON_TITLE_LINE.replace("[Win]MMDDX-<短名>", "[Win]0907V-随手写的")
        p = self._canon(self.CANON_FIRST_LINE, self.CANON_SETTINGS, drifted)
        self.assertIn("C3", {f.form for f in M.scan_single_file(p)})

    def test_正本不再教set_session_title报C1(self):
        """正本若不再包含任何带 title 的【CC】块，此后每个照抄者都会漏写那一行——
        而形态①只在成品上一个一个报，报不到源头。"""
        p = self._canon(self.CANON_FIRST_LINE, self.CANON_SETTINGS, "读队列 §一 `#N`。")
        self.assertIn("C1", {f.form for f in M.scan_single_file(p)})

    def test_正本不再教子任务例外句报C2(self):
        no_exc = TITLE_LINE_NO_EXC.replace("[Win]0827B-LAN留步收尾-354与401", "[Win]MMDDX-<短名>")
        p = self._canon(self.CANON_FIRST_LINE, self.CANON_SETTINGS, no_exc)
        self.assertIn("C2", {f.form for f in M.scan_single_file(p)})

    def test_正本自检不外溢到普通件(self):
        """C1/C2 是**正本专属**的文件级判据——普通派单件不含 title 是常态
        （子任务泳道 opener 就该不含），不得被 C1/C2 点亮。"""
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "看护件-x.md"
            p.write_text(_md(TITLE_LINE_CC, SETTINGS_CC, "读队列 §一 `#N`。"),
                         encoding="utf-8")
            forms = {f.form for f in M.scan_single_file(p)}
            self.assertNotIn("C1", forms)
            self.assertNotIn("C2", forms)

    def test_生效日与标题表齐备(self):
        for code in ("C1", "C2", "C3", "C5"):
            self.assertEqual(M.RULE_EFFECTIVE_BY_FORM[code], date(2026, 9, 7))
            self.assertIn(code, M.FORM_TITLE)


class 判据正本识别改为声明式(unittest.TestCase):
    """队列 §一 `#489` ⑴：把「哪些件是判据正本」从**写死路径**改为**件自己声明**。

    立项形态：`#493` 只把 `opener骨架.md` 一条路径挖了出去，`专线opener模板库.md`
    不在名单里 ⇒ 它的 5 个填空模板恒报 13 处（F3×3 ＋ F4×5 ＋ F5×5），
    **每次触碰这两份文件都被迫写一次 `opener豁免：`，而豁免用滥则守卫失效**。
    按路径续加第二条、第三条，就是在建那份 `#489` 期望产出明令禁止的文件名清单。

    🔴 **本类同样守「换判据、不是关掉」**：每条「声明后不报 FN」都配一条
    「声明立不住 / 正本漂了就报 CN」。
    """

    FILLER = 格式正本自身被判成违规.CANON_FILLER_BLOCK

    def _write(self, body: str, role: str | None, name: str = "件-x.md") -> Path:
        d = tempfile.TemporaryDirectory()
        self.addCleanup(d.cleanup)
        p = Path(d.name) / name
        head = "---\ntitle: \"夹具\"\nstatus: 生效\n"
        if role is not None:
            head += f"{M.CANON_ROLE_KEY}: {role}\n"
        p.write_text(head + "---\n\n" + body, encoding="utf-8")
        return p

    # ── 仓库真身回归：两份判据正本都必须零违规 ────────────────
    def test_仓库真身的模板库零违规(self):
        """🔴 用**仓库里那份真文件**跑——`#489` ⑴ 要根治的就是它那 13 处。"""
        lib = M.REPO_ROOT / "1-转型规划/0-全景路线图/专线opener模板库.md"
        self.assertTrue(lib.is_file(), f"模板库不在了：{lib}")
        self.assertEqual([f.render() for f in M.scan_single_file(lib)], [])

    def test_两份真身都自带角色声明(self):
        """判据既然改成声明式，两份正本就必须真的声明了——否则本项白改。"""
        for rel, role in (
            (M.SKELETON_CANON_REL, M.CANON_ROLE_SKELETON),
            ("1-转型规划/0-全景路线图/专线opener模板库.md", M.CANON_ROLE_LIBRARY),
        ):
            text = (M.REPO_ROOT / rel).read_text(encoding="utf-8")
            self.assertEqual(M.canon_role(text), role, rel)

    # ── 模板库角色：换掉版式三条（F3/F4/F5）────────────────────
    def test_模板库角色内不报形态三四五(self):
        """模板库的块是**「说什么」的内容草稿**，不是「长什么样」的版式范例
        （根 `CLAUDE.md` §3：出 opener 一律照抄骨架、**不凭模板库重建**）。
        拿版式判据判内容草稿，与 `#493` 修掉的「拿成品判据判定义本身」同一类型错误。"""
        body = _md("【设置】执行环境：**CC** ｜ 分支：master ｜ worktree：☐",
                   "开工第一件事：调 set_session_title，标题：[Win]MMDDX-〔主题短名〕。"
                   "🔴 例外：你若是被 Task/Agent 起的子任务，跳过本行不要执行。",
                   "读队列 §二 取批次。") + "\n" + _md(self.FILLER)
        forms = {f.form for f in M.scan_single_file(self._write(body, M.CANON_ROLE_LIBRARY))}
        for code in ("F3", "F4", "F5"):
            self.assertNotIn(code, forms)

    def test_模板库角色内形态一形态二照常生效(self):
        """🔴 F1/F2 **刻意不换**：它俩问的是「这份模板还教不教 `set_session_title`
        与子任务例外句」——那正是 2026-08-27 一天 17 次违反的源头，是模板库最该
        守住的东西。把它俩也一起放掉，等于把最该报的那一处永久隐身。"""
        body = _md("【设置】执行环境：**CC** ｜ 分支：master ｜ worktree：☐",
                   "读队列 §二 取批次。") + "\n" + _md(self.FILLER)
        forms = {f.form for f in M.scan_single_file(self._write(body, M.CANON_ROLE_LIBRARY))}
        self.assertIn("F1", forms)

    def test_模板库不再教例外句报C2(self):
        """换上去的那半：模板库丢了例外句照样发信号（比骨架丢了更直接——
        骨架还有人逐字读，模板库是照单抓药）。"""
        body = _md("【设置】执行环境：**CC** ｜ 分支：master ｜ worktree：☐",
                   "开工第一件事：调 set_session_title，标题：[Win]MMDDX-〔主题短名〕。",
                   "读队列 §二 取批次。") + "\n" + _md(self.FILLER)
        forms = {f.form for f in M.scan_single_file(self._write(body, M.CANON_ROLE_LIBRARY))}
        self.assertIn("C2", forms)

    # ── C0 防外溢：声明不是免死金牌 ────────────────────────────
    def test_单块件声明角色不予承认并报C0(self):
        """🔴 防「随手加一行 frontmatter 就能躲开 F3/F4/F5」：正本/模板库按定义是
        多份范例的集合，一份成品 opener 只有 1 块 ⇒ 声明不成立、按普通件全判。"""
        body = _md("[OP-MMDD-X]【CC】某个活",
                   SETTINGS_CC,
                   TITLE_LINE_PLACEHOLDER_NOT_FILLED)
        forms = {f.form for f in M.scan_single_file(
            self._write(body, M.CANON_ROLE_LIBRARY, "派单件-x.md"))}
        self.assertIn("C0", forms)
        self.assertIn("F3", forms)     # 声明什么也没换来

    def test_角色值写错不予承认并报C0(self):
        """写错一个字就静默变成「以为豁免了其实没有」——同族＝参数被接受却不生效。"""
        body = _md("【设置】执行环境：**CC** ｜ 分支：master ｜ worktree：☐",
                   TITLE_LINE_PLACEHOLDER_NOT_FILLED) + "\n" + _md(self.FILLER)
        forms = {f.form for f in M.scan_single_file(self._write(body, "模版库"))}
        self.assertIn("C0", forms)
        self.assertIn("F3", forms)

    def test_未声明的普通件一切照旧(self):
        """判据面来自被判对象的声明 ⇒ 没声明的件行为与本项引入前逐字一致。"""
        body = _md("[OP-MMDD-X]【CC】某个活", SETTINGS_CC,
                   TITLE_LINE_PLACEHOLDER_NOT_FILLED)
        forms = {f.form for f in M.scan_single_file(self._write(body, None))}
        self.assertNotIn("C0", forms)
        self.assertIn("F3", forms)
        self.assertIn("F5", forms)

    def test_生效日与标题表齐备(self):
        self.assertEqual(M.RULE_EFFECTIVE_BY_FORM["C0"], date(2026, 9, 8))
        self.assertIn("C0", M.FORM_TITLE)


class 骨架三bis样例照抄后不得撞F2(unittest.TestCase):
    """队列 §一 `#489` 步骤 3（Shao Peishen 2026-09-08 答 1a）：骨架 §三bis 的看护者
    开场词样例句原本含「子任务」而**无**「例外/跳过本行」⇒ **照抄它的看护件必撞 F2**，
    作者随手写一个 `opener豁免：`，而「豁免用滥则守卫失效」正是 `#489` 要根治的事。

    🔴 **它在骨架内不报、只在照抄者身上报**——骨架是判据正本，F2 已被换成 C2（文件级
    「还教不教例外句」，别的块教了就过），所以这个洞在正本自检里天然看不见。
    同族＝「同一内容两份、只有一份有机器守」（`#503`）：生成器
    `--variant guardian` 早已输出该句，骨架样例却没有，两份分叉且无人发现。
    """

    def _sample_block(self):
        text = (M.REPO_ROOT / M.SKELETON_CANON_REL).read_text(encoding="utf-8")
        lines = text.splitlines()
        hdr = next(i for i, l in enumerate(lines, 1) if l.startswith("## §三bis"))
        return next(b for b in M.iter_fenced_blocks(text) if b.start_line > hdr)

    def test_样例块自带子任务例外句(self):
        """判据用 lint 自己那两个 token 正则，不另写一套字面量匹配。"""
        t = self._sample_block().text
        self.assertTrue(M.SUBTASK_TOKEN_RE.search(t), "样例块已不含「子任务」类 token")
        self.assertTrue(M.EXCEPTION_TOKEN_RE.search(t),
                        "样例块含「子任务」却不含「例外/跳过本行」⇒ 照抄者必撞 F2")

    def test_照抄进看护件不报F2(self):
        """端到端：把样例块原样抄进一份看护件（标题按骨架要求不带 §）⇒ 不得出现 F2。

        F3/F5 仍会命中且**那是对的**——占位符没替换正是形态③要抓的（`#493`
        「排除不外溢」），本用例只钉死 F2。
        """
        block = self._sample_block()
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "看护件-照抄骨架三bis.md"
            p.write_text("## 三bis · 看护opener\n\n```\n" + block.text + "\n```\n",
                         encoding="utf-8")
            self.assertNotIn("F2", {f.form for f in M.scan_single_file(p)})


class 明细分组不得漏掉形态(unittest.TestCase):
    """2026-09-08 本会话实测发现的第三处缺陷（`#489` 顺带修）：`main()` 里的明细
    分组循环写死了一份形态清单，**漏了 F3/F4/F5** ⇒ 这三个形态的命中**计入
    「N 处待修【阻断】」却一行明细都不打印**。

    实证：全量 `--enforce` 报「49 处待修」，而输出里逐条数得出来的只有 36 条，
    差的 13 条正是模板库那批 F3/F4/F5——`#489` ⑵ 记的「验收命令拿不到结论」有本条一份。
    同族＝模块开头那句「连回显都没有时，无法区分『没问题』与『没跑』」的变体：
    **回显有，但少了一截，而少的那截不会报错。**
    根因是「同一份形态清单存在两处、只有一处会被新增形态改到」⇒ 已取消第二处。
    """

    def test_每个形态都有标题条目(self):
        """🔴 判据表与标题表必须同域——少一条，那个形态的明细就会静默消失。"""
        self.assertEqual(set(M.RULE_EFFECTIVE_BY_FORM), set(M.FORM_TITLE))

    def test_明细条数与待修数一致(self):
        """端到端：`--enforce` 声称的「N 处待修」必须与逐条打印出来的明细条数相等。"""
        import io as _io
        import contextlib as _ctx
        buf = _io.StringIO()
        with _ctx.redirect_stdout(buf):
            M.main(["--enforce"])
        out = buf.getvalue()
        claimed = re.search(r"当前在用件 (\d+) 处待修", out)
        self.assertIsNotNone(claimed, out[-400:])
        # 🔴 形态码不再保证单位数（`#565` 起有 F10）——`\d` 曾漏计双位数形态码，改 `\d+`（队列 §一 `#565`）。
        printed = len(re.findall(r"^  - .*\[[FC]\d+\] ", out, re.MULTILINE))
        self.assertEqual(int(claimed.group(1)), printed,
                         "声称的待修数与实际打印的明细条数不一致——又漏形态了")


class 全量取提交日期批量化(unittest.TestCase):
    """队列 §一 `#489` ⑵：全量 `--enforce` 的墙钟从「逐文件 git log」降到「一次全历史」。

    立项实证：`--enforce` 起于 22:05、至 07:24 进程消失、输出文件始终 0 字节。
    本会话逐段计时定位到**两件事，不是一件**：
      ① 89% 墙钟耗在 `_last_commit_date` 逐文件调用（1613 个文件实测 1057.3s，
         均值 1.32s；纯解析只要 19.4s）；
      ② **0 字节不等于挂死**——此前全部输出攒到最后一次性打印，`> out.txt`
         期间那个文件本来就是 0 字节，「跑得慢」与「卡死了」在观测上同形。
    """

    def test_批量与逐文件口径一致(self):
        """🔴 换实现必须先证明等价——本项在全库 1613 个 `.md` 上逐个比对过
        （不一致 0、批量取不到 0）；单测取前 40 个做常驻回归。"""
        files = M._tracked_md_files()[:40]
        batch = M._last_commit_dates_batch(files)
        if not batch:
            self.skipTest("批量取数不可用（非 git 仓库／git 不可用）")
        for rel in files:
            if rel in batch:
                self.assertEqual(batch[rel], M._last_commit_date(rel), rel)

    def test_批量取不到时不静默当成没有历史(self):
        """🔴 fail-safe 方向：取不到返回空字典 ⇒ 调用方逐个回落到 `_last_commit_date`，
        **不是**把全库打成 `unknown-history` 然后全部按「当前在用」阻断。"""
        self.assertEqual(M._last_commit_dates_batch([]), {})

    def test_单次git调用有超时上限(self):
        """一个卡住的 git 调用不许把整轮全量拖死。"""
        self.assertIsInstance(M.GIT_TIMEOUT_SECONDS, int)
        self.assertGreater(M.GIT_TIMEOUT_SECONDS, 0)


class 形态八_子任务泳道块含未替换占位条目(unittest.TestCase):
    """⑧ 子任务泳道 opener 块里仍有 `1. …／- …` 这类**未替换的正文占位条目** ⇒ 告警
    （队列 §一 `#487` 追记⑴，2026-09-09 apply／`OP-0909-X`）。

    🔑 **它是形态⑦的镜像**：⑦ ＝「一个参数被接受却不生效」（`--dont` 静默丢弃），
    ⑧ ＝「**一个参数没传却仍产出内容**」（`工具-opener生成.py --variant subtask_lane`
    未传 `--do`／`--dont` 时仍硬塞两段占位）。两者根因同一条：**格式正本
    `opener骨架.md` 与生成器之间此前没有机器守**，全靠人每次肉眼比对。
    """

    _LANE_WITH_PLACEHOLDER = "\n".join([
        "### A1 · 示例泳道",
        "",
        _md(TITLE_LINE_CC, SETTINGS_CC,
            "读 ① 队列 §一 `#487` → ② `CLAUDE.md` 恢复上下文。本件为 A 类，直接开工。",
            "",
            "做什么：",
            "1. …",
            "",
            "不做什么：",
            "- …"),
        "",
        "## 三bis、看护opener（单次粘贴，Task/Agent 工具起子任务）",
        "",
        _md("[OP-0909-X]【CC】看护示例", SETTINGS_CC, TITLE_LINE_WITH_EXC),
    ])

    _LANE_THREE_LINE = "\n".join([
        "### A1 · 示例泳道",
        "",
        _md(TITLE_LINE_CC, SETTINGS_CC,
            "读 ① 队列 §一 `#487` → ② `CLAUDE.md` 恢复上下文。本件为 A 类，直接开工。",
            HEARTBEAT_LINE, SENTINEL_LINE),
        "",
        "## 三bis、看护opener（单次粘贴，Task/Agent 工具起子任务）",
        "",
        _md("[OP-0909-X]【CC】看护示例", SETTINGS_CC, TITLE_LINE_WITH_EXC),
    ])

    _LANE_FILLED = "\n".join([
        "### A1 · 示例泳道",
        "",
        _md(TITLE_LINE_CC, SETTINGS_CC,
            "读 ① 队列 §一 `#487` → ② `CLAUDE.md` 恢复上下文。本件为 A 类，直接开工。",
            "",
            "做什么：",
            "1. 落地两处缺陷 ＋ 一道闸。",
            "",
            "不做什么：",
            "- 不碰 `#522`。",
            SENTINEL_LINE),
        "",
        "## 三bis、看护opener（单次粘贴，Task/Agent 工具起子任务）",
        "",
        _md("[OP-0909-X]【CC】看护示例", SETTINGS_CC, TITLE_LINE_WITH_EXC),
    ])

    @staticmethod
    def _scan(text: str) -> set[str]:
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "看护件.md"
            p.write_text(text, encoding="utf-8")
            return {f.form for f in M.scan_single_file(p)}

    def test_反例_泳道块留占位条目_命中F8(self):
        """本批看护件 §三 的真实现场形态：生成器产物直接落进看护件，两段占位没填。"""
        self.assertIn("F8", self._scan(self._LANE_WITH_PLACEHOLDER))

    def test_正例_骨架三行写法_不命中任何形态(self):
        """🔴 验收条款「两侧都能关掉」：按骨架写成三行 ⇒ F8 必须消失，
        且不得因此触发形态①（子任务泳道不放 title 是正确写法）。"""
        self.assertEqual(self._scan(self._LANE_THREE_LINE), set())

    def test_正例_两段都填了真内容_不命中(self):
        """占位符被替换成真内容 ⇒ 判据管的是「没填」，不是「有没有这两段」。"""
        self.assertNotIn("F8", self._scan(self._LANE_FILLED))

    def test_非子任务泳道块不受约束(self):
        """🔴 收窄的正面实证（`FORM8_SCOPE_NOTE`）：没有 `## 三bis` 小节的普通派单件，
        其【Cowork】块留占位段是 2026-09-06 `OP-0906-M` 的明示设计，本形态不判。"""
        md = _md(TITLE_LINE_COWORK, SETTINGS_COWORK,
                 "做什么：", "1. …", "", "不做什么：", "- …")
        self.assertNotIn("F8", _forms(md))

    def test_占位符后面写了真内容的行不误伤(self):
        """整行锚定：`1. …（细节见队列行）` 已经是填过的内容，不该命中。"""
        block = _md(TITLE_LINE_CC, SETTINGS_CC, "做什么：", "1. …（细节见队列行 `#487`）")
        forms = {f for f, _ in M.check_block(_only_block(block), is_subtask_lane=True)}
        self.assertNotIn("F8", forms)

    def test_半角三点与多种列表记号皆认(self):
        """骨架写全角 `…`，人手抄常写半角 `...`；列表记号三种写法都见过。"""
        for item in ("1. …", "2、…", "3) …", "- …", "* …", "+ ..."):
            with self.subTest(item=item):
                self.assertTrue(M.PLACEHOLDER_ITEM_RE.match(item), item)

    def test_有真内容的条目不得命中占位判据(self):
        """反向用例：证明上一条的「命中」来自省略号本身，不是列表记号。"""
        for item in ("1. 落地两处缺陷", "- 不碰 `#522`", "* 收工只 push 本泳道分支"):
            with self.subTest(item=item):
                self.assertIsNone(M.PLACEHOLDER_ITEM_RE.match(item), item)

    def test_明细里报出条数与首条原文(self):
        block = _md(TITLE_LINE_CC, SETTINGS_CC, "做什么：", "1. …", "不做什么：", "- …")
        detail = dict(M.check_block(_only_block(block), is_subtask_lane=True))["F8"]
        self.assertIn("2 条", detail)
        self.assertIn("1. …", detail)

    def test_生效日与明细分组均已登记(self):
        """同 F7 的登记验收：漏登生效日 ⇒ H3 判不了历史件；漏登 `FORM_TITLE` ⇒
        `--enforce` 报了数却不打印明细（队列 §一 `#489` 2026-09-08 实撞过一次）。"""
        self.assertEqual(M.RULE_EFFECTIVE_BY_FORM["F8"], date(2026, 9, 9))
        self.assertIn("F8", M.FORM_TITLE)

    def test_格式正本自身不命中F8(self):
        """骨架的 `## §三bis` 标题带 `§`、锚不上 `WATCHER_SECTION_RE` ⇒ 其块一律不是
        子任务泳道块，F8 天然不覆盖它——与 F6 同一条既有性质，此处钉死防回归。"""
        self.assertNotIn(
            "F8", {f.form for f in M.scan_single_file(M.REPO_ROOT / M.SKELETON_CANON_REL)})


class 形态九_子任务泳道块缺收工哨兵(unittest.TestCase):
    """⑨ 子任务泳道 opener 块**缺收工哨兵行**（`OPENER_DONE`／`OPENER_PARTIAL`）⇒ 告警
    （队列 §一 `#550`，2026-09-10）。

    🔑 **成因不是活没做完，是收工协议没走完**：`工具-opener批处理执行v2.ps1` 判成败靠
    `claude` 退出码 ＋ 顶格哨兵两个指标，2026-09-10 四条泳道（`507`／`529`／`544`／
    `k2-externalize`）活全做了、无一 `OPENER_DONE`——因为【CC · 子任务泳道】变体此前
    一个字没提哨兵。**一个把成功报成失败的判据比没有判据更糟**。修法主体在生成器
    （强制注入），本形态是它的机器守：正本改了而生成器没跟、或起草人手抄漏了，当场红。
    """

    _LANE_WITH_SENTINEL = "\n".join([
        "### A1 · 示例泳道", "",
        _md(TITLE_LINE_CC, SETTINGS_CC,
            "读 ① 队列 §一 `#550` → ② `CLAUDE.md` 恢复上下文。本件为 A 类，直接开工。",
            HEARTBEAT_LINE, SENTINEL_LINE),
        "",
        "## 三bis、看护opener（单次粘贴，Task/Agent 工具起子任务）", "",
        _md("[OP-0910-R]【CC】看护示例", SETTINGS_CC, TITLE_LINE_WITH_EXC),
    ])

    _LANE_WITHOUT_SENTINEL = "\n".join([
        "### A1 · 示例泳道", "",
        _md(TITLE_LINE_CC, SETTINGS_CC,
            "读 ① 队列 §一 `#550` → ② `CLAUDE.md` 恢复上下文。本件为 A 类，直接开工。",
            "🔴 并行上限 4，超出排下一波，错峰 ≥90 秒（构建环境瘦身第三轮方案 P4）。"),
        "",
        "## 三bis、看护opener（单次粘贴，Task/Agent 工具起子任务）", "",
        _md("[OP-0910-R]【CC】看护示例", SETTINGS_CC, TITLE_LINE_WITH_EXC),
    ])

    @staticmethod
    def _scan(text: str) -> set[str]:
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "看护件.md"
            p.write_text(text, encoding="utf-8")
            return {f.form for f in M.scan_single_file(p)}

    def test_反例_泳道块缺哨兵行_命中F9(self):
        """2026-09-10 `B-0910_三泳道续排` 看护件 §三 的真实现场形态。"""
        self.assertIn("F9", self._scan(self._LANE_WITHOUT_SENTINEL))

    def test_正例_带哨兵行_不命中任何形态(self):
        """🔴 验收条款「两侧都能关掉」：补上哨兵行 ⇒ F9 消失，且不牵连出别的形态。"""
        self.assertEqual(self._scan(self._LANE_WITH_SENTINEL), set())

    def test_只有一半哨兵不算(self):
        """判据要求 DONE 与 PARTIAL 同现于一行——只写「以 OPENER_DONE 收尾」等于没告诉
        子任务停在决策点时该怎么收，批处理仍会判 NO-SENTINEL。"""
        half = _md(TITLE_LINE_CC, SETTINGS_CC, "读 ① 队列 §一 `#550`。", "🔴 收工以 `OPENER_DONE` 收尾。")
        forms = {f for f, _ in M.check_block(_only_block(half), is_subtask_lane=True)}
        self.assertIn("F9", forms)

    def test_非子任务泳道块不受约束(self):
        """收窄：没有 `## 三bis` 的普通派单件／【Cowork】块不判——它们不经批处理器的
        哨兵判据（看护者开场词是人粘贴的交互会话，Cowork 桌根本没有批处理器）。"""
        md = _md(TITLE_LINE_COWORK, SETTINGS_COWORK, "读 ① 队列 §一 `#550`。")
        self.assertNotIn("F9", _forms(md))
        cc_top = _md(TITLE_LINE_CC, SETTINGS_CC, TITLE_LINE_WITH_EXC, "读 ① 队列 §一 `#550`。")
        self.assertNotIn("F9", _forms(cc_top))

    def test_看护者自己的开场词不受约束(self):
        """`## 三bis` 之后的块＝看护者（交互会话），不判 F9。"""
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "看护件.md"
            p.write_text(self._LANE_WITHOUT_SENTINEL, encoding="utf-8")
            findings = M.scan_single_file(p)
            watcher_line = M._watcher_section_line(self._LANE_WITHOUT_SENTINEL)
            self.assertFalse(any(f.form == "F9" and f.line >= watcher_line for f in findings))

    def test_明细指向生成器与批处理器(self):
        detail = dict(M.check_block(_only_block(_md(TITLE_LINE_CC, SETTINGS_CC, "读。")),
                                    is_subtask_lane=True))["F9"]
        self.assertIn("OPENER_DONE", detail)
        self.assertIn("工具-opener生成.py", detail)
        self.assertIn("NO-SENTINEL", detail)

    def test_生效日与明细分组均已登记(self):
        self.assertEqual(M.RULE_EFFECTIVE_BY_FORM["F9"], date(2026, 9, 10))
        self.assertIn("F9", M.FORM_TITLE)

    def test_格式正本自身不命中F9(self):
        """骨架的 `## §三bis` 标题带 `§`、锚不上 ⇒ 其块不是子任务泳道块，F9 不覆盖它（同 F6／F8）。"""
        self.assertNotIn(
            "F9", {f.form for f in M.scan_single_file(M.REPO_ROOT / M.SKELETON_CANON_REL)})

    def test_骨架子任务泳道节自带哨兵行(self):
        """正本必须教这一行——否则照抄者的成品会缺它，F9 只能在成品上报、报不到源头。"""
        text = (M.REPO_ROOT / M.SKELETON_CANON_REL).read_text(encoding="utf-8")
        start = text.index("## 【CC · 子任务泳道】骨架")
        section = text[start:text.index("\n## ", start + 1)]
        block = M.iter_fenced_blocks(section)[0]
        self.assertTrue(any(M.SENTINEL_LINE_RE.search(ln) for ln in block.lines),
                        "骨架【CC · 子任务泳道】块缺收工哨兵行")


class 形态十_子任务泳道块缺心跳约定(unittest.TestCase):
    """⑩ 子任务泳道 opener 块缺心跳约定行 ⇒ 告警（队列 §一 `#565`，2026-09-12：看护批
    `B-0911_机制收口` 5 条泳道全做完全 ff、心跳两小时零新增——同 F9 一样，「正文里写一句」
    拦不住起草人漏写；本形态是生成器强制注入（`SUBTASK_HEARTBEAT_NOTE`）的机器守。"""

    _LANE_WITHOUT_HEARTBEAT = "\n".join([
        "### A1 · 示例泳道", "",
        _md(TITLE_LINE_CC, SETTINGS_CC,
            "读 ① 队列 §一 `#565` → ② `CLAUDE.md` 恢复上下文。本件为 A 类，直接开工。",
            SENTINEL_LINE),
        "",
        "## 三bis、看护opener（单次粘贴，Task/Agent 工具起子任务）", "",
        _md("[OP-0912-B]【CC】看护示例", SETTINGS_CC, TITLE_LINE_WITH_EXC),
    ])

    _LANE_WITH_HEARTBEAT = "\n".join([
        "### A1 · 示例泳道", "",
        _md(TITLE_LINE_CC, SETTINGS_CC,
            "读 ① 队列 §一 `#565` → ② `CLAUDE.md` 恢复上下文。本件为 A 类，直接开工。",
            HEARTBEAT_LINE, SENTINEL_LINE),
        "",
        "## 三bis、看护opener（单次粘贴，Task/Agent 工具起子任务）", "",
        _md("[OP-0912-B]【CC】看护示例", SETTINGS_CC, TITLE_LINE_WITH_EXC),
    ])

    @staticmethod
    def _scan(text: str) -> set[str]:
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "看护件.md"
            p.write_text(text, encoding="utf-8")
            return {f.form for f in M.scan_single_file(p)}

    def test_反例_泳道块缺心跳行_命中F10(self):
        """2026-09-12 看护批 `B-0911_机制收口` §三 的真实现场形态。"""
        self.assertIn("F10", self._scan(self._LANE_WITHOUT_HEARTBEAT))

    def test_正例_带心跳行_不命中任何形态(self):
        """🔴 验收条款「两侧都能关掉」：补上心跳行 ⇒ F10 消失，且不牵连出别的形态。"""
        self.assertEqual(self._scan(self._LANE_WITH_HEARTBEAT), set())

    def test_非子任务泳道块不受约束(self):
        """收窄：没有 `## 三bis` 的普通派单件／【Cowork】块不判——它们不经批处理器的
        看门狗（看护者开场词是人粘贴的交互会话，Cowork 桌根本没有批处理器）。"""
        md = _md(TITLE_LINE_COWORK, SETTINGS_COWORK, "读 ① 队列 §一 `#565`。")
        self.assertNotIn("F10", _forms(md))
        cc_top = _md(TITLE_LINE_CC, SETTINGS_CC, TITLE_LINE_WITH_EXC, "读 ① 队列 §一 `#565`。")
        self.assertNotIn("F10", _forms(cc_top))

    def test_看护者自己的开场词不受约束(self):
        """`## 三bis` 之后的块＝看护者（交互会话），不判 F10。"""
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "看护件.md"
            p.write_text(self._LANE_WITHOUT_HEARTBEAT, encoding="utf-8")
            findings = M.scan_single_file(p)
            watcher_line = M._watcher_section_line(self._LANE_WITHOUT_HEARTBEAT)
            self.assertFalse(any(f.form == "F10" and f.line >= watcher_line for f in findings))

    def test_明细指向生成器(self):
        detail = dict(M.check_block(_only_block(_md(TITLE_LINE_CC, SETTINGS_CC, "读。")),
                                    is_subtask_lane=True))["F10"]
        self.assertIn("heartbeat", detail)
        self.assertIn("工具-opener生成.py", detail)

    def test_生效日与明细分组均已登记(self):
        self.assertEqual(M.RULE_EFFECTIVE_BY_FORM["F10"], date(2026, 9, 12))
        self.assertIn("F10", M.FORM_TITLE)

    def test_格式正本自身不命中F10(self):
        """骨架的 `## §三bis` 标题带 `§`、锚不上 ⇒ 其块不是子任务泳道块，F10 不覆盖它（同 F6／F8／F9）。"""
        self.assertNotIn(
            "F10", {f.form for f in M.scan_single_file(M.REPO_ROOT / M.SKELETON_CANON_REL)})

    def test_骨架子任务泳道节自带心跳行(self):
        """正本必须教这一行——否则照抄者的成品会缺它，F10 只能在成品上报、报不到源头。"""
        text = (M.REPO_ROOT / M.SKELETON_CANON_REL).read_text(encoding="utf-8")
        start = text.index("## 【CC · 子任务泳道】骨架")
        section = text[start:text.index("\n## ", start + 1)]
        block = M.iter_fenced_blocks(section)[0]
        self.assertTrue(any(M.HEARTBEAT_LINE_RE.search(ln) for ln in block.lines),
                        "骨架【CC · 子任务泳道】块缺心跳约定行")


if __name__ == "__main__":
    unittest.main()
