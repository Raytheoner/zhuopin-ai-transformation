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
            "> **甲收口（2026-08-01，CC）**：详见队列 #999。"))
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
            "> **甲收口（2026-08-01，CC）**：承接＝ `1-转型规划/查无此件.md` §0.2。"))
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
            + "另有一段与之无关的长正文" * 6 + "顺带提一句 §5 的纪律。"))
        violations, _warnings, _parsed = self._lint(count_cap=6)
        first = next(v for v in violations if "第 1 条" in v)
        self.assertIn("该条无承接载体", first)

    def test_无承接载体时绝不输出请迁移(self):
        """J1 的核心契约：安全阀不通过 ⇒ 只说「请先立队列行再迁」。"""
        self._write_root(self._over_cap_doc("> **甲收口（2026-08-01，CC）**：正文。"))
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


class RealRepoSmokeTests(unittest.TestCase):
    """对真身跑一次——只断言「解析得出结构 A 且条目数可数出」，不断言具体
    数值（那会随每次收工而变，成为一条必然会红的脆弱断言）。"""

    def test_真实根CLAUDE可被解析为结构A(self):
        text = (MODULE.REPO_ROOT / MODULE.ROOT_CLAUDE_REL).read_text(encoding="utf-8")
        parsed = MODULE.parse_file(MODULE.ROOT_CLAUDE_REL, text)
        self.assertEqual(parsed.structure, "A-根文件型")
        self.assertGreaterEqual(len(parsed.entries), 1)


if __name__ == "__main__":
    unittest.main()
