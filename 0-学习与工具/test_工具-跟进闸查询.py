"""`工具-跟进闸查询.py` 单测（队列 #366 / S3）。

白盒方式：按文件路径 importlib 加载被测脚本（本目录既定手法），再把
`REPO_ROOT` 指向临时夹具目录——**不触碰真实 README 与真实队列文件**。

⚠️ 加载时必须 `sys.modules[spec.name] = module` 再 `exec_module`：被测脚本
用了 `@dataclass`，而 dataclass 在处理字段时要按 `cls.__module__` 回查
`sys.modules`；不注册就会以 `AttributeError: 'NoneType' object has no
attribute '__dict__'` 报错——这是**加载方式**的坑，不是被测脚本的缺陷。
"""
from __future__ import annotations

import importlib.util
import io
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

SCRIPT = Path(__file__).resolve().with_name("工具-跟进闸查询.py")

README_REL = "6-人才与组织/部门AI专员跟进/README-跟进机制与命名约定.md"
QUEUE_MECHANISM_REL = "1-转型规划/0-全景路线图/跨桌任务队列-机制环境.md"
QUEUE_BUSINESS_REL = "1-转型规划/0-全景路线图/跨桌任务队列-业务场景.md"

README_HEADER = (
    "## 现有跟进信清单\n\n"
    "| 编号 | 日期 | 收信人 | 主要事项 | 交期要点 | 发送状态（2026-07-06） |\n"
    "|--------|------|--------|---------|---------|---------|\n"
)

QUEUE_HEADER = (
    "## 一、任务看板\n\n"
    "| # | 任务 | 领取方 | 输入（指针） | 期望产出 | 状态 | 触碰区 | 登记 |\n"
    "|---|------|--------|-------------|----------|------|--------|------|\n"
)


def _load():
    spec = importlib.util.spec_from_file_location("_followup_gate_cli_under_test", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _readme_row(number, recipient, topic, status):
    return f"| {number} | 2026-08-20 | {recipient} | {topic} | 尽快 | {status} |\n"


def _intake_row(row_id, pointer, status):
    return (
        f"| {row_id} | 企微反馈自动归档：某人 发来文件 x | 采购专线 | `{pointer}` | "
        f"核实内容 | {status} | 队列 | 2026-08-21 |\n"
    )


class GateQueryTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.module = _load()
        self.module.REPO_ROOT = self.root
        for rel in (README_REL, QUEUE_MECHANISM_REL, QUEUE_BUSINESS_REL):
            (self.root / rel).parent.mkdir(parents=True, exist_ok=True)
        self._write_queue(QUEUE_HEADER)
        (self.root / QUEUE_BUSINESS_REL).write_text(QUEUE_HEADER, encoding="utf-8")

    def tearDown(self):
        self._tmp.cleanup()

    def _write_readme(self, rows: str):
        (self.root / README_REL).write_text(README_HEADER + rows, encoding="utf-8")

    def _write_queue(self, text: str):
        (self.root / QUEUE_MECHANISM_REL).write_text(text, encoding="utf-8")

    def _report(self, recipient: str):
        text = (self.root / README_REL).read_text(encoding="utf-8")
        return self.module.build_report(recipient, text)

    # ------------------------------------------------------------------ 闸

    def test_最近一封已闭环则闸开(self):
        self._write_readme(
            _readme_row("采购部#16", "采购部 · 姚祖怡", "旧信", "✅ 已推送 2026-08-18")
            + _readme_row("采购部#17", "采购部 · 姚祖怡", "新信", "📥 已回件并回灌（2026-08-21）")
        )
        report = self._report("姚祖怡")
        self.assertTrue(report.gate_open)
        self.assertEqual(report.letter_number, "采购部#17")

    def test_最近一封在途则闸锁(self):
        self._write_readme(
            _readme_row("采购部#16", "采购部 · 姚祖怡", "旧信", "📥 已回件并回灌（2026-08-20）")
            + _readme_row("采购部#17", "采购部 · 姚祖怡", "新信", "✅ 已推送 2026-08-20 12:20 UTC")
        )
        report = self._report("姚祖怡")
        self.assertFalse(report.gate_open)
        self.assertEqual(report.letter_number, "采购部#17")

    def test_最近一封按表格顺序取而不是按日期(self):
        # README 串行原则段的既定口径：日期列存在补记情形，顺序才是权威。
        self._write_readme(
            _readme_row("采购部#17", "采购部 · 姚祖怡", "新信", "✅ 已推送")
            + "| 采购部#18 | 2026-07-01 | 采购部 · 姚祖怡 | 补记的旧信 | 尽快 | 📥 已回件并回灌 |\n"
        )
        self.assertEqual(self._report("姚祖怡").letter_number, "采购部#18")

    def test_闸锁不是错误退出码仍为0(self):
        self._write_readme(
            _readme_row("采购部#17", "采购部 · 姚祖怡", "新信", "✅ 已推送 2026-08-20")
        )
        with redirect_stdout(io.StringIO()):
            self.assertEqual(self.module.main(["--to", "姚祖怡"]), 0)

    def test_收信人不存在退出码2且列出已知收信人(self):
        self._write_readme(_readme_row("采购部#17", "采购部 · 姚祖怡", "x", "✅ 已推送"))
        buf = io.StringIO()
        with redirect_stdout(buf):
            self.assertEqual(self.module.main(["--to", "查无此人"]), 2)
        self.assertIn("姚祖怡", buf.getvalue())

    def test_README表损坏退出码2(self):
        (self.root / README_REL).write_text("这份文件里没有任何表格\n", encoding="utf-8")
        buf = io.StringIO()
        with redirect_stdout(buf):
            self.assertEqual(self.module.main(["--to", "姚祖怡"]), 2)
        self.assertIn("✗", buf.getvalue())

    # -------------------------------------------------------------- 编号列

    def test_编号列含待发暂不占号括注时仍取到该行并告警(self):
        """反例单测⑴（派单件 §六.3）。"""
        self._write_readme(
            _readme_row("IT部#6", "IT部 · 陈承", "旧信", "📥 已回件并回灌（2026-08-10）")
            + _readme_row("IT部#7（待发，暂不占号）", "IT部 · 陈承", "新信",
                          "📥 已回件并回灌（2026-08-12 拆件巡逻）")
        )
        report = self._report("陈承")
        self.assertEqual(report.letter_number, "IT部#7（待发，暂不占号）")
        self.assertTrue(report.gate_open)
        self.assertTrue(
            any("自称未发" in w for w in report.warnings),
            f"括注与状态矛盾时必须告警，实得：{report.warnings}",
        )
        # 下一个可用号仍按下表实际 `#N` 最大值推算，不被括注带偏。
        self.assertEqual(report.next_number, "IT部#8")

    def test_下一个可用号只看下表不读顶部自由文本(self):
        self._write_readme(
            _readme_row("采购部#16", "采购部 · 姚祖怡", "x", "📥 已回件并回灌")
            + _readme_row("采购部#17", "采购部 · 姚祖怡", "y", "📥 已回件并回灌")
        )
        self.assertEqual(self._report("姚祖怡").next_number, "采购部#18")

    def test_未知状态写法按在途保守处理且必须告警(self):
        self._write_readme(_readme_row("采购部#17", "采购部 · 姚祖怡", "x", "🤔 说不清"))
        report = self._report("姚祖怡")
        self.assertFalse(report.gate_open, "不认识的写法必须保守判为闸锁")
        self.assertTrue(any("不认识" in w for w in report.warnings))

    # ---------------------------------------------------------------- 入信

    def test_入信已到但README未转态时告警(self):
        self._write_readme(_readme_row(
            "采购部#17", "采购部 · 姚祖怡",
            "SC2 判例批改 → 目标文件：`采购部-姚祖怡-跟进-2026-08-20-SC2.md`",
            "✅ 已推送 2026-08-20 12:20 UTC",
        ))
        self._write_queue(QUEUE_HEADER + _intake_row(
            "362", "7-外部文档/采购部/采购部-YaoZuYi-回复-2026-08-21-文本反馈-abc123def456.md",
            "[S:open][D:业] 待领",
        ))
        report = self._report("姚祖怡")
        self.assertEqual([r.number for r in report.pending_intakes], ["362"])
        self.assertTrue(any("入信已到但 README 未转态" in w for w in report.warnings))

    def test_已拆件而README未转态时给出更强的那条告警(self):
        self._write_readme(_readme_row(
            "采购部#17", "采购部 · 姚祖怡",
            "SC2 判例批改 → 目标文件：`采购部-姚祖怡-跟进-2026-08-20-SC2.md`",
            "✅ 已推送 2026-08-20 12:20 UTC",
        ))
        self._write_queue(QUEUE_HEADER + _intake_row(
            "362",
            "7-外部文档/采购部/采购部-YaoZuYi-回复-2026-08-21-采购部-姚祖怡-跟进-2026-08-20-SC2-abc123def456.docx",
            "[S:done][D:业] ✅ 已拆件",
        ))
        report = self._report("姚祖怡")
        self.assertTrue(
            any("已拆件" in w and "请先转闭环态" in w for w in report.warnings),
            f"实得：{report.warnings}",
        )

    def test_IT部与归档目录名IT不一致时仍能找到入信行(self):
        # 真实差异：README 写 `IT部 · 陈承`，`department_mapping.yaml` 把陈承
        # 映射到 `IT` ⇒ 只按 README 写法找目录会恒返回零条、且不报错。
        self.assertEqual(self.module._department_dir_aliases("IT部"), ("IT部", "IT"))
        self._write_readme(_readme_row("IT部#9", "IT部 · 陈承", "x", "✅ 已推送 2026-08-18"))
        self._write_queue(QUEUE_HEADER + _intake_row(
            "330", "7-外部文档/IT/IT-2023458-回复-2026-08-12-文本反馈-8a6ed377cf9e.md",
            "[S:open][D:机] 待领",
        ))
        self.assertEqual([r.number for r in self._report("陈承").pending_intakes], ["330"])

    def test_队列文件缺失时fail_loud而不是当成没有入信(self):
        self._write_readme(_readme_row("采购部#17", "采购部 · 姚祖怡", "x", "✅ 已推送"))
        (self.root / QUEUE_BUSINESS_REL).unlink()
        rows = self.module._collect_intake_rows("采购部", None)
        self.assertTrue(any("队列文件不存在" in r.archived_path for r in rows))

    # ---------------------------------------------------------------- 渲染

    def test_人读格式与json由同一份数据渲染(self):
        self._write_readme(
            _readme_row("采购部#17", "采购部 · 姚祖怡", "x", "✅ 已推送 2026-08-20")
        )
        report = self._report("姚祖怡")
        human = self.module.render_human(report)
        self.assertIn("🔒 锁", human)
        self.assertIn(report.letter_number, human)
        buf = io.StringIO()
        with redirect_stdout(buf):
            self.module.main(["--to", "姚祖怡", "--json"])
        import json
        payload = json.loads(buf.getvalue())
        self.assertEqual(payload[0]["gate_open"], report.gate_open)
        self.assertEqual(payload[0]["letter_number"], report.letter_number)
        self.assertEqual(payload[0]["warnings"], report.warnings)

    def test_all覆盖全部收信人无遗漏无重复(self):
        self._write_readme(
            _readme_row("采购部#17", "采购部 · 姚祖怡", "x", "✅ 已推送")
            + _readme_row("质量部#8", "质量部 · 陈忱（可请朱映桦先初标）", "y", "📥 已回件并回灌")
            + _readme_row("质量部#7", "质量部 · 陈忱（可分担朱映桦）", "z", "✅ 无需回复")
        )
        names = self.module.all_recipients((self.root / README_REL).read_text(encoding="utf-8"))
        self.assertEqual(names, ["姚祖怡", "陈忱"])

    # ------------------------------------------------- 闭环形态（队列 #353）

    # 决策点 2(a) 之下，一封「起草时判定为 ✅ 无需回复」的信发出后状态格长这样。
    快照态 = (
        "✅ 无需回复 2026-08-25 07:00 UTC（企微机器人自动回填）"
        "　━━━　闭环形态（发出时快照）：`✅ 无需回复`（依据：正文写明不用回）"
        "　━━━　✅ 已推送 2026-08-25 07:00 UTC"
    )
    标注 = " → 闭环形态：`✅ 无需回复`（依据：正文写明不用回）"

    def test_起草时即有标注_发出后闸开且不需要串行豁免(self):
        """决策点 2(a) ＋ 5(c)：这一条正面回答 `质量部#7 → #8` 那次的失败。"""
        self._write_readme(
            _readme_row("质量部#7", "质量部 · 陈忱", "通报信" + self.标注, self.快照态)
        )
        report = self._report("陈忱")
        self.assertTrue(report.gate_open)
        self.assertEqual(report.closure_form_snapshot, "✅ 无需回复")
        self.assertEqual(report.closure_form_annotation, "✅ 无需回复")
        self.assertEqual(report.warnings, [])
        human = self.module.render_human(report)
        self.assertIn("闭环形态：", human)
        self.assertIn("闸采信这一份", human)

    def test_发出后补写标注_闸零效果且明确报出事后追认(self):
        self._write_readme(
            _readme_row("质量部#7", "质量部 · 陈忱", "通报信" + self.标注,
                        "✅ 已推送 2026-08-18 06:53 UTC")
        )
        report = self._report("陈忱")
        self.assertFalse(report.gate_open)                    # ← 闸仍锁
        self.assertIsNone(report.closure_form_snapshot)
        self.assertEqual(report.closure_form_annotation, "✅ 无需回复")
        self.assertTrue(any("零效果" in w for w in report.warnings))

    def test_标注与快照不一致时报出来并声明以快照为准(self):
        """🔴 决策点 5(c) 的**必配缓解**：不做这条，(c) 就是用一个静默失效
        换掉了一个静默滥用。"""
        篡改标注 = " → 闭环形态：`❌ 已作废`（依据：事后改的）"
        self._write_readme(
            _readme_row("质量部#7", "质量部 · 陈忱", "通报信" + 篡改标注, self.快照态)
        )
        report = self._report("陈忱")
        self.assertEqual(report.closure_form_snapshot, "✅ 无需回复")
        self.assertEqual(report.closure_form_annotation, "❌ 已作废")
        self.assertTrue(any("以快照为准" in w for w in report.warnings))
        self.assertTrue(report.gate_open)                     # ← 判定按快照走

    def test_越界标注被报出来且按无标注处理(self):
        self._write_readme(
            _readme_row("质量部#7", "质量部 · 陈忱",
                        "通报信 → 闭环形态：`✅ 大概不用回`（依据：x）",
                        "✅ 已推送 2026-08-18")
        )
        report = self._report("陈忱")
        self.assertIsNone(report.closure_form_annotation)
        self.assertFalse(report.gate_open)
        self.assertTrue(any("不在闭环四态枚举内" in w for w in report.warnings))

    def test_无标注的行输出与本变更前逐字相同(self):
        """54 行历史行里 53 行无标注——这条是硬要求，不是"尽量"。"""
        self._write_readme(
            _readme_row("采购部#17", "采购部 · 姚祖怡", "x", "✅ 已推送 2026-08-20")
        )
        report = self._report("姚祖怡")
        self.assertIsNone(report.closure_form_annotation)
        self.assertIsNone(report.closure_form_snapshot)
        self.assertEqual(report.warnings, [])
        self.assertNotIn("闭环形态：", self.module.render_human(report))

    def test_闭环形态两个新字段也进json(self):
        self._write_readme(
            _readme_row("质量部#7", "质量部 · 陈忱", "通报信" + self.标注, self.快照态)
        )
        buf = io.StringIO()
        with redirect_stdout(buf):
            self.module.main(["--to", "陈忱", "--json"])
        import json
        payload = json.loads(buf.getvalue())
        self.assertEqual(payload[0]["closure_form_snapshot"], "✅ 无需回复")
        self.assertEqual(payload[0]["closure_form_annotation"], "✅ 无需回复")


if __name__ == "__main__":
    unittest.main()
