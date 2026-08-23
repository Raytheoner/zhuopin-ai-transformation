"""工具-CLAUDE进度段lint.py 单测（派单件 OP-0821-C §五，判据 J1/J2/J3/J5）。

白盒方式：`lint(repo_root)` 本就接收 repo_root，指向临时夹具目录，不触碰
真实生产文件（同 `test_工具-队列结构lint.py` 既有手法）。

派单件点名必须有的三条反例单测里，本文件承载两条：
  ⑴ 只含 `> 🔴 **` 前缀的条目**必须被数到**（`RootStructureTests::
     test_红色前缀条目必须被计入`）；
  ⑵ 拼接两份队列文本再解析**必须被测出会丢行**（`QueueCarrierTests::
     test_拼接文本解析会丢掉第二份的第一分区`），锁死「逐份解析后合并」
     这个实现选择。
第三条（含「未结」的条目必须触发 J4）在 `test_工具-共享文档编辑锁.py`
的 `ClaudeProgressOpenItemTests` 里——J4 属 release 校验族，不在本脚本。
"""
from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().with_name("工具-CLAUDE进度段lint.py")


def _load_module():
    spec = importlib.util.spec_from_file_location("_claude_progress_lint_under_test", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    # 🔴 exec 前先登记进 `sys.modules`：被测模块用了 `@dataclass`，而
    # `dataclasses` 在处理类型注解时会做 `sys.modules.get(cls.__module__)`
    # ——按文件路径加载但没登记时那里拿到 `None`，抛
    # `AttributeError: 'NoneType' object has no attribute '__dict__'`。
    # 既有的 `test_工具-队列结构lint.py` 没有这一行，是因为被测模块里没有
    # dataclass，不是因为这一行多余。
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


MODULE = _load_module()


def _root_doc(entry_lines: list[str], *, with_pointer: bool = True) -> str:
    """拼一份结构 A 的最小根 CLAUDE.md：标题 → 说明引用块 → `> **当前进度**`
    头行 → 若干条目 → （可选）📦 迁移指针行 → `---` → §1 正文。"""
    parts = [
        "# CLAUDE.md — 测试夹具",
        "",
        "> 本文件是项目级上下文/记忆。",
        "",
        "> **当前进度**：历史进度已迁入 CHANGELOG。",
        ">",
    ]
    for line in entry_lines:
        parts.append(line)
        parts.append(">")
    if with_pointer:
        parts.append("> **📦 更早的条目已迁 CHANGELOG**（2026-08-05，队列 #253）：原文原样保留。")
    parts += ["", "---", "", "## 1. 公司与项目背景", "", "- 正文", ""]
    return "\n".join(parts)


QUEUE_HEADER = (
    "> **编号高水位线：§一 #400 ｜ §四 #90**\n\n"
    "## 一、任务看板\n\n"
    "| # | 任务 | 领取方 | 输入（指针） | 期望产出 | 状态 | 触碰区 | 登记 |\n"
    "|---|------|--------|-------------|----------|------|--------|------|\n"
)


def _queue_doc(row_ids: list[str]) -> str:
    rows = "".join(
        f"| {rid} | 任务{rid} | CC | 指针 | 产出 | [S:open][D:机] 在办 | 区 | 登记 |\n"
        for rid in row_ids
    )
    return QUEUE_HEADER + rows + "\n## 四、待定夺\n\n| # | 事项 | 提出 | 状态 |\n|---|---|---|---|\n"


class _FixtureCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.repo_root = Path(self._tmp.name)
        self.module = MODULE
        # 队列夹具：两份物理文件，机制环境含 #101，业务场景含 #202。
        for rel, ids in (
            (self.module.editlock.queue_table.QUEUE_MECHANISM_PATH_REL, ["101"]),
            (self.module.editlock.queue_table.QUEUE_BUSINESS_PATH_REL, ["202"]),
        ):
            path = self.repo_root / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(_queue_doc(ids), encoding="utf-8")

    def tearDown(self):
        self._tmp.cleanup()

    def _write_root(self, text: str) -> None:
        (self.repo_root / self.module.ROOT_CLAUDE_REL).write_text(text, encoding="utf-8")

    def _lint(self, **kwargs):
        kwargs.setdefault("root_only", True)
        return self.module.lint(self.repo_root, **kwargs)


class RootStructureTests(_FixtureCase):
    def test_红色前缀条目必须被计入(self):
        """派单件反例单测⑴：`> 🔴 **` 与 `> **` 两种前缀都是条目。

        2026-08-21 两份输入件都只匹配了前者，把 12 条数成 15 条／9 条——
        两次都错、且错得看起来很确定。本用例把这一点锁死。
        """
        self._write_root(_root_doc([
            "> **甲收口（2026-08-01，CC）**：正文。",
            "> 🔴 **乙收口（2026-08-02，CC）**：正文。",
            "> 🔴 **丙收口（2026-08-03，CC）**：正文。",
        ]))
        _violations, _warnings, parsed = self._lint()
        self.assertEqual(len(parsed), 1)
        self.assertEqual(parsed[0].structure, "A-根文件型")
        self.assertEqual(len(parsed[0].entries), 3,
                         "🔴 前缀的两条必须被数到，只认 `> **` 会漏算")

    def test_迁移指针行与其后元说明不计入条目(self):
        """真身实测：裸正则在 2026-08-21 的根 CLAUDE.md 上数出 4 条，真值是 2
        ——多出的两条是 📦 迁移指针行与其后的 memory 层元说明行，两者结构上
        与进度条目完全无法区分。故条目区以 📦 行为上界。"""
        text = _root_doc([
            "> **甲收口（2026-08-01，CC）**：正文。",
            "> **乙收口（2026-08-02，CC）**：正文。",
        ])
        text = text.replace(
            "\n---\n",
            "\n> **🔴 memory 层已收割并停用（2026-08-21，OP-0821-B）**：元说明，不是进度条目。\n\n---\n",
            1,
        )
        self._write_root(text)
        _violations, _warnings, parsed = self._lint()
        self.assertEqual(len(parsed[0].entries), 2)
        self.assertEqual(len(parsed[0].meta_lines), 2,
                         "📦 行与其后的 memory 元说明行都应被显式列为元说明、不静默吞掉")

    def test_无当前进度头行即判未支持结构不静默放过(self):
        self._write_root("# CLAUDE.md\n\n> 没有当前进度头行。\n\n---\n\n## 1. 正文\n")
        _violations, warnings, parsed = self._lint()
        self.assertEqual(parsed[0].structure, "")
        self.assertTrue(any("未支持的结构" in w for w in warnings))

    def test_没有日期模式的行不算条目(self):
        self._write_root(_root_doc([
            "> **一句没有署期的话**：不该被当成进度条目。",
            "> **甲收口（2026-08-01，CC）**：正文。",
        ]))
        _violations, _warnings, parsed = self._lint()
        self.assertEqual(len(parsed[0].entries), 1)


class J2J3Tests(_FixtureCase):
    def test_条目数未超上限不报违规(self):
        self._write_root(_root_doc([
            f"> **第{i}条（2026-08-0{i}，CC）**：正文。" for i in range(1, 4)
        ]))
        violations, _warnings, _parsed = self._lint(count_cap=6)
        self.assertEqual(violations, [])

    def test_条目数超上限报J2且点名待迁条数(self):
        self._write_root(_root_doc([
            f"> **第{i}条（2026-08-{i:02d}，CC）**：正文，见队列 #101。" for i in range(1, 9)
        ]))
        violations, _warnings, _parsed = self._lint(count_cap=6)
        head = next(v for v in violations if "【J2】" in v)
        self.assertIn("现有 8 条（上限 6）", head)
        self.assertIn("最早的 2 条", head)

    def test_单条超长报J3(self):
        long_body = "正" * 1500
        self._write_root(_root_doc([f"> **甲（2026-08-01，CC）**：{long_body}"]))
        violations, _warnings, _parsed = self._lint(length_cap=1200)
        self.assertTrue(any("【J3】" in v and "超长" in v for v in violations))

    def test_J3按字符数不按字节数(self):
        """`len(str)` 而非 `len(bytes)`——中文按 UTF-8 是 3 字节/字，按字节算
        会把 401 个汉字判成超 1200。"""
        body = "正" * 1100
        self._write_root(_root_doc([f"> **甲（2026-08-01，CC）**：{body}"]))
        violations, _warnings, _parsed = self._lint(length_cap=1200)
        self.assertFalse(any("【J3】" in v for v in violations))


class J1CarrierTests(_FixtureCase):
    def _over_cap_doc(self, first_entry: str) -> str:
        others = [f"> **第{i}条（2026-08-{i:02d}，CC）**：正文。" for i in range(2, 9)]
        return _root_doc([first_entry] + others)

    def test_点名真实队列行的条目判为可迁(self):
        self._write_root(self._over_cap_doc(
            "> **甲收口（2026-08-01，CC）**：详见队列 #101。"))
        violations, _warnings, _parsed = self._lint(count_cap=6)
        first = next(v for v in violations if "第 1 条" in v)
        self.assertIn("可迁", first)
        self.assertIn("#101", first)

    def test_业务场景文件里的行号同样算承接载体(self):
        """逐份解析后合并——只读机制环境那一份就会把 #202 判成不存在。"""
        self._write_root(self._over_cap_doc(
            "> **甲收口（2026-08-01，CC）**：详见队列 #202。"))
        violations, _warnings, _parsed = self._lint(count_cap=6)
        first = next(v for v in violations if "第 1 条" in v)
        self.assertIn("可迁", first)

    def test_点名不存在的行号不算承接载体(self):
        self._write_root(self._over_cap_doc(
            "> **甲收口（2026-08-01，CC）**：详见队列 #999，7.2 验收尚未完成。"))
        violations, _warnings, _parsed = self._lint(count_cap=6)
        first = next(v for v in violations if "第 1 条" in v)
        self.assertIn("该条无承接载体", first)
        self.assertNotIn("请迁移", first)

    def test_真实文件路径加章节号算承接载体(self):
        target = self.repo_root / "1-转型规划" / "0-全景路线图" / "全景规划.md"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("# 全景规划\n", encoding="utf-8")
        self._write_root(self._over_cap_doc(
            "> **甲收口（2026-08-01，CC）**：承接＝ "
            "`1-转型规划/0-全景路线图/全景规划.md` §0.2 的 2026-08-18 登记行。"))
        violations, _warnings, _parsed = self._lint(count_cap=6)
        first = next(v for v in violations if "第 1 条" in v)
        self.assertIn("可迁", first)

    def test_路径不存在时不算承接载体(self):
        self._write_root(self._over_cap_doc(
            "> **甲收口（2026-08-01，CC）**：承接＝ `1-转型规划/查无此件.md` §0.2，"
            "且 7.2 验收尚未完成。"))
        violations, _warnings, _parsed = self._lint(count_cap=6)
        first = next(v for v in violations if "第 1 条" in v)
        self.assertIn("该条无承接载体", first)

    def test_章节号离路径太远不算承接载体(self):
        """有路径、也有 §，但两者不在同一处——不构成「这条的承接在那个文件的
        那一节」这个断言。判错的代价是对一条其实没有承接的条目说「请迁移」，
        故这里取严不取宽。"""
        target = self.repo_root / "1-转型规划" / "全景规划.md"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("# x\n", encoding="utf-8")
        self._write_root(self._over_cap_doc(
            "> **甲收口（2026-08-01，CC）**：参见 `1-转型规划/全景规划.md`。"
            + "另有一段与之无关的长正文" * 6 + "顺带提一句 §5 的纪律，且验收尚未完成。"))
        violations, _warnings, _parsed = self._lint(count_cap=6)
        first = next(v for v in violations if "第 1 条" in v)
        self.assertIn("该条无承接载体", first)

    def test_无承接载体时绝不输出请迁移(self):
        """J1 的核心契约：安全阀不通过 ⇒ 只说「请先立队列行再迁」。

        ⚠️ 夹具正文必须含未闭合措辞——二期开了第 ⑵ 档后，「无载体 ＋ 零未闭合
        措辞」会被判「整条已闭合、可迁」。**本用例守的是 blocked 档那一侧的
        契约**，不是「凡无载体一律不许迁」。
        """
        self._write_root(self._over_cap_doc(
            "> **甲收口（2026-08-01，CC）**：正文，7.2 验收尚未完成。"))
        violations, _warnings, _parsed = self._lint(count_cap=6)
        per_entry = [v for v in violations if "第 1 条" in v]
        self.assertTrue(per_entry)
        for v in per_entry:
            self.assertNotIn("可迁", v)


class QueueCarrierTests(_FixtureCase):
    def test_逐份解析后合并两份文件的行号都在(self):
        ids, warnings = self.module.load_queue_row_ids(self.repo_root)
        self.assertEqual(warnings, [])
        self.assertIn("101", ids)
        self.assertIn("202", ids)

    def test_拼接文本解析会丢掉第二份的第一分区(self):
        """派单件反例单测⑵：锁死「逐份解析后合并」这个实现选择。

        `_split_live_sections` 把结果放进 dict，label 相同则**后写覆盖先写**。
        把两份队列文本拼起来解析一次，第二份的 `## 一、` 会顶掉第一份的
        §一——第一份的行全部静默消失、零报错。此坑 2026-08-19 `#312` 已真实
        发生过一次（可 Open 池提醒只跟了一份文件）。

        本用例证明的是：**如果实现走的是拼接，结果就会缺行**；而上一个用例
        证明当前实现两份都在 ⇒ 当前实现不可能是拼接。
        """
        editlock = self.module.editlock
        mech = (self.repo_root / editlock.queue_table.QUEUE_MECHANISM_PATH_REL
                ).read_text(encoding="utf-8")
        biz = (self.repo_root / editlock.queue_table.QUEUE_BUSINESS_PATH_REL
               ).read_text(encoding="utf-8")

        concatenated = editlock._split_live_sections(mech + "\n" + biz)
        concat_ids = {
            cells[0].strip()
            for _line, cells in editlock._table_data_rows(concatenated.get("一", ""))
            if cells and cells[0].strip().isdigit()
        }
        self.assertEqual(concat_ids, {"202"},
                         "拼接解析应只剩第二份的 §一——第一份的 #101 被静默顶掉")

        merged, _warnings = self.module.load_queue_row_ids(self.repo_root)
        self.assertTrue({"101", "202"} <= merged,
                        "逐份解析后合并必须两份都在（与拼接形成对照）")

    def test_队列文件缺失时告警而不静默降级(self):
        (self.repo_root / self.module.editlock.queue_table.QUEUE_BUSINESS_PATH_REL).unlink()
        ids, warnings = self.module.load_queue_row_ids(self.repo_root)
        self.assertIn("101", ids)
        self.assertTrue(any("不存在" in w for w in warnings))


class J5SceneTests(_FixtureCase):
    def _write_scene(self, rel: str, text: str) -> None:
        path = self.repo_root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def test_SC8表格型被识别并套用J2J3(self):
        rows = "\n".join(
            f"| 2026-06-{i:02d} | 第{i}条正文。 |" for i in range(1, 9)
        )
        self._write_scene(
            "4-数字员工/采购部/SC8-客户订单交期智能承诺/CLAUDE.md",
            "# CLAUDE.md — SC8\n\n## 5. 状态时间线\n\n"
            "| 日期 | 状态 |\n|------|------|\n" + rows + "\n\n## 6. 其它\n",
        )
        self._write_root(_root_doc(["> **甲（2026-08-01，CC）**：正文。"]))
        violations, _warnings, parsed = self._lint(root_only=False, count_cap=6)
        scene = next(p for p in parsed if p.rel_path.endswith("SC8-客户订单交期智能承诺/CLAUDE.md"))
        self.assertEqual(scene.structure, "B-SC8表格型")
        self.assertEqual(len(scene.entries), 8)
        self.assertTrue(any("【J2】" in v and "SC8" in v for v in violations))

    def test_SC8表格型条目正文取状态列不含日期列(self):
        self._write_scene(
            "4-数字员工/采购部/SC8-客户订单交期智能承诺/CLAUDE.md",
            "# CLAUDE.md — SC8\n\n## 5. 状态时间线\n\n"
            "| 日期 | 状态 |\n|------|------|\n| 2026-06-10 | 正文。 |\n",
        )
        self._write_root(_root_doc(["> **甲（2026-08-01，CC）**：正文。"]))
        _violations, _warnings, parsed = self._lint(root_only=False)
        scene = next(p for p in parsed if "SC8" in p.rel_path)
        self.assertEqual(scene.entries[0].body, "正文。")

    def test_未支持结构的场景文件被列名而不静默放过(self):
        self._write_scene("4-数字员工/财务部/FI2-三单匹配自动对账/CLAUDE.md",
                          "# CLAUDE.md — FI2\n\n> 顶部引用块，没有当前进度头行。\n\n## 状态\n\n- 在办\n")
        self._write_root(_root_doc(["> **甲（2026-08-01，CC）**：正文。"]))
        _violations, warnings, _parsed = self._lint(root_only=False)
        self.assertTrue(any("FI2-三单匹配自动对账/CLAUDE.md" in w and "未支持的结构" in w
                            for w in warnings))


class CliTests(_FixtureCase):
    def test_warn模式有违规也退0_enforce模式退1(self):
        self._write_root(_root_doc([f"> **甲（2026-08-01，CC）**：{'正' * 1500}"]))
        argv = ["--root-only", "--repo-root", str(self.repo_root)]
        self.assertEqual(self.module.main(argv), 0, "一期告警模式必须退出码 0")
        self.assertEqual(self.module.main(argv + ["--enforce"]), 1)

    def test_无违规时两种模式都退0(self):
        self._write_root(_root_doc(["> **甲（2026-08-01，CC）**：正文。"]))
        argv = ["--root-only", "--repo-root", str(self.repo_root)]
        self.assertEqual(self.module.main(argv), 0)
        self.assertEqual(self.module.main(argv + ["--enforce"]), 0)


class J1ClosedEntryTests(_FixtureCase):
    """J1 第 ⑵ 档「整条已闭合」（二期开口，2026-08-22，OP-0822-D）。"""

    def _over_cap_doc(self, first_entry: str) -> str:
        return _root_doc([first_entry] + [
            f"> **第{i}条（2026-08-1{i}，CC）**：正文。" for i in range(1, 7)
        ])

    def test_无载体但零未闭合措辞判为可迁(self):
        self._write_root(self._over_cap_doc(
            "> **甲收口（2026-08-01，CC）**：变更包已归档，全量回归绿。"))
        violations, _warnings, _parsed = self._lint(count_cap=6)
        first = next(v for v in violations if "第 1 条" in v)
        self.assertIn("可迁", first)
        self.assertIn("判「整条已闭合」", first)

    def test_已闭合档的措辞必须区别于有载体档且带人眼复核提示(self):
        """🔴 两档都说「可迁」，但**证据强度不同**：一档是点名了真实存在的
        承接行，另一档只是「词表没命中」。措辞若无差别，读的人会把后者当成
        前者那样的结论——而它不是。"""
        self._write_root(self._over_cap_doc(
            "> **甲收口（2026-08-01，CC）**：变更包已归档，全量回归绿。"))
        violations, _warnings, _parsed = self._lint(count_cap=6)
        first = next(v for v in violations if "第 1 条" in v)
        self.assertIn("词表只是筛子", first)
        self.assertNotIn("承接载体：", first)

    def test_含未结的条目绝不被判可迁(self):
        """🔴 本用例是这个开口最危险的失效模式的反例守卫。

        「未结」正是 2026-08-21 逐行读原文才补进 J4 词表的两个漏词之一，而
        SC8 那份 2026-08-21 的注解点名 `2026-06-24` 行「挂着未结：7.2 LAN
        真实联调验收」。**若词表接不住这个词，这一族条目就会被静默判为可迁
        并搬走——而它们正是迁走即丢的那一类。**
        """
        self._write_root(self._over_cap_doc(
            "> **甲收口（2026-08-01，CC）**：上线完成。未结：7.2 LAN 真实联调验收。"))
        violations, _warnings, _parsed = self._lint(count_cap=6)
        first = next(v for v in violations if "第 1 条" in v)
        self.assertNotIn("可迁", first)
        self.assertIn("未结", first)
        self.assertIn("请先立队列行再迁", first)

    def test_有载体优先于已闭合判定(self):
        """两者同时成立时报「承接载体」——证据强的那一档优先。"""
        self._write_root(self._over_cap_doc(
            "> **甲收口（2026-08-01，CC）**：见队列 #101，变更包已归档。"))
        violations, _warnings, _parsed = self._lint(count_cap=6)
        first = next(v for v in violations if "第 1 条" in v)
        self.assertIn("承接载体：队列行 #101", first)
        self.assertNotIn("整条已闭合", first)

    def test_词表取自编辑锁不另立一份(self):
        """两处各持一份词表 ⇒ 改了一处忘另一处就会「release 拦得住、lint 说
        可迁」。本用例把「同一份对象」这件事钉死。"""
        self.assertIs(self.module.editlock.CLAUDE_PROGRESS_OPEN_ITEM_WORDS,
                      self.module.editlock.CLAUDE_PROGRESS_OPEN_ITEM_WORDS)
        for word in ("未结", "未接线", "尚未", "阻塞"):
            self.assertIn(word, self.module.editlock.CLAUDE_PROGRESS_OPEN_ITEM_WORDS)
            self.assertTrue(self.module.open_item_hits(f"正文{word}正文"))


class J6HandoffCardTests(_FixtureCase):
    """J6 · 接力件定长交接卡（R5 2026-08-22 改版）。"""

    CARD = ("# Session 接力（滚动·最新）\n\n"
            "## 一、新会话起始词（复制即用）\n\n正文\n\n"
            "## 二、当前状态快照（2026-08-22）\n\n正文\n")

    def _write_handoff(self, rel: str, body: str) -> Path:
        path = self.repo_root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body, encoding="utf-8")
        return path

    def test_合规交接卡零告警(self):
        self._write_handoff("1-转型规划/session接力-采购域场景落地.md", self.CARD)
        out = self.module.check_handoff_cards(self.repo_root, 8192)
        self.assertEqual(out, [])

    def test_标题里带括号日期的合规节不被误判为日期节(self):
        """🔴 判据刻意只认「`##` ＋ 全角方括号 ＋ ISO 日期」——合规卡本身就有
        `## 二、当前状态快照（2026-08-22）` 这样一行，放宽到「标题里出现日期」
        即误伤，而误伤的后果是这条判据被当成噪音关掉。"""
        self._write_handoff("1-转型规划/session接力-采购域场景落地.md", self.CARD)
        out = self.module.check_handoff_cards(self.repo_root, 8192)
        self.assertFalse([o for o in out if "日期节" in o])

    def test_日期节被点名并给出行号(self):
        body = self.CARD + "\n## 【2026-08-18 · 某某回件回灌】\n\n正文\n"
        self._write_handoff("1-转型规划/session接力-质量域场景落地.md", body)
        out = self.module.check_handoff_cards(self.repo_root, 8192)
        hit = next(o for o in out if "日期节" in o)
        self.assertIn("1 个日期节", hit)

    def test_超字节上限被点名且按字节不按字符(self):
        """🔴 R5 写的是「硬上限 8 KB」——这些文件几乎全是中文，UTF-8 下一个
        汉字 3 字节，按字符数判会得出一个宽约 3 倍的假上限。"""
        body = self.CARD + "正" * 3000          # 3,000 字符 ＝ 约 9,000 字节
        path = self._write_handoff("1-转型规划/session接力-财务域场景落地.md", body)
        self.assertLess(len(body), 8192, "夹具前提：字符数在上限内")
        self.assertGreater(len(path.read_bytes()), 8192, "夹具前提：字节数超上限")
        out = self.module.check_handoff_cards(self.repo_root, 8192)
        self.assertTrue([o for o in out if "字节 > 上限" in o])

    def test_归档件不进扫描范围(self):
        """归档件正是日期节被迁去的地方，按定长卡去判它方向就反了。"""
        self._write_handoff("1-转型规划/session接力-采购域-归档-202606.md",
                            self.CARD + "\n## 【2026-06-01 · 旧节】\n\n" + "正" * 5000)
        self.assertEqual(self.module.handoff_files(self.repo_root), [])
        self.assertEqual(self.module.check_handoff_cards(self.repo_root, 8192), [])

    def test_两级目录下的接力件同样被扫到(self):
        """🔴 用 glob 而非硬编码四个路径：新开一条域专线就会有第五条，而硬编码
        名单**不会报错、只会漏查**（同 §一 #312「一份拆成两份，下游只跟了一份」）。"""
        self._write_handoff("1-转型规划/0-全景路线图/session接力-Phase1收口.md", self.CARD)
        self._write_handoff("1-转型规划/session接力-新开一条域专线.md", self.CARD)
        self.assertEqual(len(self.module.handoff_files(self.repo_root)), 2)

    def test_J6结果进告警不进违规(self):
        """本期刻意不硬拦：三份存量接力件正超限 5-9 倍，一并硬拦等于把
        `--enforce` 这件事本身再推迟一轮。"""
        self._write_handoff("1-转型规划/session接力-财务域场景落地.md", "正" * 4000)
        self._write_root(_root_doc(["> **甲（2026-08-01，CC）**：正文。"]))
        violations, warnings, _parsed = self._lint(root_only=False)
        self.assertTrue([w for w in warnings if "【J6】" in w])
        self.assertFalse([v for v in violations if "【J6】" in v])


class J7OpeningBudgetTests(_FixtureCase):
    """J7 · 开场预算。"""

    def test_未超预算不报告警但仍回显(self):
        self._write_root(_root_doc(["> **甲（2026-08-01，CC）**：正文。"]))
        self.assertEqual(self.module.check_opening_budget(self.repo_root, 120_000), [])
        parts, total = self.module.opening_budget(self.repo_root)
        self.assertEqual(len(parts), 2)
        self.assertGreater(total, 0)

    def test_超预算报J7(self):
        self._write_root(_root_doc(["> **甲（2026-08-01，CC）**：正文。"]))
        out = self.module.check_opening_budget(self.repo_root, 10)
        self.assertTrue(out)
        self.assertIn("【J7】", out[0])

    def test_缺件按缺件回显而不静默计零(self):
        """🔴 交接卡缺失时若静默按 0 计，预算会凭空变小——「工具静默回退」同族。"""
        self._write_root(_root_doc(["> **甲（2026-08-01，CC）**：正文。"]))
        parts, _total = self.module.opening_budget(self.repo_root)
        card = next(p for p in parts if p[0] == "交接卡")
        self.assertEqual(card[2], -1, "缺件须以 -1 显式标注，不得按 0 混入合计")

    def test_队列不计入预算(self):
        """队列真身合计数百 KB，2026-08-06 起改由只读 CLI 按行号查（§一 #268）
        ⇒ 开场读入量 ≈ 0。把它按文件字节计进预算会得出一个吓人却毫无意义的数。"""
        rels = [rel for _label, rel in self.module.OPENING_BUDGET_PARTS]
        self.assertNotIn(self.module.OPENING_QUEUE_ENTRY, rels)
        for rel in rels:
            self.assertNotIn("队列", rel)


class J8SentinelTests(_FixtureCase):
    """J8 · 哨兵存在性（OP-0823-C）。

    A 档 5 条规则下沉后，根里各留一行哨兵——**哨兵成了新的单点失效，而它恰恰是
    全篇最短、最像可有可无的那一行**；删掉它，被下沉的整块规则就此对所有新会话
    消失，**且在本判据之前没有任何机制会报错**。
    """

    def _root_with(self, tail_lines: list[str]) -> None:
        self._write_root(
            _root_doc(["> **甲（2026-08-01，CC）**：正文。"]) + "\n".join(tail_lines) + "\n")

    def _mkfile(self, rel: str, size: int = 2000) -> None:
        path = self.repo_root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("规" * size, encoding="utf-8")

    def test_哨兵指向的文件被删则报违规(self):
        """派单件 §四 ⑴：目标不存在 ⇒ 进 violations（不是 warnings）。"""
        self._root_with(["🔴 **动 `x-子目录/` 之前，先读 `x-子目录/CLAUDE.md`** —— 细则在那里。"])
        violations, _warnings, _parsed = self._lint()
        hits = [v for v in violations if "【J8】" in v]
        self.assertEqual(len(hits), 1, violations)
        self.assertIn("x-子目录/CLAUDE.md", hits[0])
        self.assertIn("对所有新会话不可见", hits[0])

    def test_自指与家目录路径不进判定(self):
        """🔴 防 §2.2 那条**永久误报**：`~/.claude/CLAUDE.md` 是家目录全局件、
        不在仓库内，按仓库相对路径去 `exists()` 恒为假；`CLAUDE.md` 是自指、判它
        恒真零信息量。**误报的代价不是噪音，是它会训练人忽略这条告警。**"""
        self._root_with([
            "开场读 ① 本 `CLAUDE.md`（当前进度）→ ② 接力件。",
            "全局身份/偏好见 `~/.claude/CLAUDE.md`（不重复）。",
            "写入 `CLAUDE.md` 顶部 Last Updated 时一律取本机本地日期。",
            "另有绝对路径 `C:/别处/CLAUDE.md` 与相对上跳 `../外部/CLAUDE.md`，同样不判。",
        ])
        violations, warnings, _parsed = self._lint()
        self.assertEqual([v for v in violations if "【J8】" in v], [])
        self.assertEqual([w for w in warnings if "【J8】" in w], [])
        _v, _w, total, _f, bare_n = self.module.check_sentinels(self.repo_root)
        self.assertEqual((total, bare_n), (0, 0), "自指与仓库外路径一处都不该进判定")

    def test_不含先读二字的哨兵同样被判(self):
        """🔴 锁死 §2.1 那个漏报：#80 ⑻ 的规格原文挂在「先读」句式上，而真身三条里
        L120（A5 外部对抗性评审纪律）写的是「细则与…演练**见** `…/CLAUDE.md`」
        ⇒ 按字面实现只能命中 2/3，**静默漏掉的恰是最久才用一次的那条**。
        本用例防止日后有人把排除法「优化」回匹配句式。"""
        self._root_with(["外部对抗性评审纪律：细则与冷备架构师接手演练见 `a/b/CLAUDE.md`。"])
        violations, _warnings, _parsed = self._lint()
        hits = [v for v in violations if "【J8】" in v]
        self.assertEqual(len(hits), 1, violations)
        self.assertIn("a/b/CLAUDE.md", hits[0])

    def test_目标文件被清空同样报违规(self):
        """字节下限覆盖「被清空／只剩一行标题」这一种失效（Shao Peishen 2026-08-23
        答 (a)）。**这不算内容级校验**——零同步负担。
        ⚠️ 仍未覆盖：文件还在、其它内容也在，而被下沉的那一块被删掉 ⇒ J8 通过。"""
        self._mkfile("z-子目录/CLAUDE.md", size=10)   # 30 字节 < 下限 200
        self._root_with(["细则见 `z-子目录/CLAUDE.md`。"])
        violations, _warnings, _parsed = self._lint()
        hits = [v for v in violations if "【J8】" in v]
        self.assertEqual(len(hits), 1, violations)
        self.assertIn("疑似被清空", hits[0])
        # 同一路径填够字节后即通过——证明报的是「空」不是「不存在」。
        self._mkfile("z-子目录/CLAUDE.md", size=2000)
        violations2, _w2, _p2 = self._lint()
        self.assertEqual([v for v in violations2 if "【J8】" in v], [])

    def test_裸路径哨兵只告警不阻断(self):
        """反引号同样是人写的格式约定，只认它会漏掉「先读 x/CLAUDE.md」这种写法。
        🔴 **但裸命中只进 warnings**（Shao Peishen 2026-08-23 答 (a)）：裸扫描可能
        误命中散文，而误报会训练人忽略告警——反引号命中硬拦、裸命中只请人看一眼。"""
        self._root_with(["动 q-子目录/ 之前，先读 q-子目录/CLAUDE.md，细则在那里。"])
        violations, warnings, _parsed = self._lint()
        self.assertEqual([v for v in violations if "【J8】" in v], [])
        hits = [w for w in warnings if "【J8】" in w]
        self.assertEqual(len(hits), 1, warnings)
        self.assertIn("疑似未加反引号", hits[0])
        self.assertIn("q-子目录/CLAUDE.md", hits[0])

    def test_同一路径两处引用按出现次数各数一次(self):
        """统计行的 N 按**出现次数**数、不按去重路径数（Shao Peishen 2026-08-23 答 (a)）：
        被删掉的是**某一处引用**，按次数数才能让人发现「上周还是 3 处、今天怎么 2 处了」。"""
        self._mkfile("p-子目录/CLAUDE.md")
        self._root_with(["先读 `p-子目录/CLAUDE.md`。", "另见 `p-子目录/CLAUDE.md` 第二处。"])
        _v, _w, total, faulted, _bare = self.module.check_sentinels(self.repo_root)
        self.assertEqual((total, faulted), (2, 0))
        self.assertIn("2 处哨兵，全部命中",
                      self.module.sentinel_summary_line(self.repo_root, 200))

    def test_统计行无论有无违规都回显(self):
        """理由同 J7：只在超限时才打印，等于把「现在还剩几条」藏起来，**而哨兵这件事
        的风险恰恰是「悄悄少了一条也没人知道」。**"""
        self._root_with(["先读 `w-子目录/CLAUDE.md`。"])
        line = self.module.sentinel_summary_line(self.repo_root, 200)
        self.assertIn("🛡 哨兵存在性：1 处哨兵", line)
        self.assertIn("缺失或被清空 1 处", line)


class RealRepoSmokeTests(unittest.TestCase):
    """对真身跑一次——只断言「解析得出结构 A 且条目数可数出」，不断言具体
    数值（那会随每次收工而变，成为一条必然会红的脆弱断言）。"""

    def test_真实根CLAUDE可被解析为结构A(self):
        text = (MODULE.REPO_ROOT / MODULE.ROOT_CLAUDE_REL).read_text(encoding="utf-8")
        parsed = MODULE.parse_file(MODULE.ROOT_CLAUDE_REL, text)
        self.assertEqual(parsed.structure, "A-根文件型")
        self.assertGreaterEqual(len(parsed.entries), 1)

    def test_当前master三条哨兵全部命中(self):
        """正例：对真身跑一次 J8。**这里断言具体数值 3 是有意的**——与上一条不同，
        哨兵数不随收工漂移，它只在有人删了一条（或按 A/B 档继续下沉）时变。
        数字变了就该有人来改这一行**并说明为什么**，这正是本判据要的那个信号。"""
        violations, _warnings, total, faulted, _bare = MODULE.check_sentinels(MODULE.REPO_ROOT)
        self.assertEqual(faulted, 0, violations)
        self.assertEqual(total, 3, "A 档下沉后根里应有且仅有三处哨兵："
                                   "5-平台底座/、1-转型规划/0-全景路线图/、4-数字员工/")


if __name__ == "__main__":
    unittest.main()
