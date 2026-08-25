"""工具-CI覆盖率护栏.py 单测（队列 #398⑶ 新增）。

本护栏此前无单测。#398⑶ 给它加的能力是「跌破时把是哪些用例、为什么跳
一并摊开」，其价值全在于**能把两种形态区分开**，故用例按这两种形态写：

- 合理增长：每条 skip 都带显式理由（真实样本 gitignore／`*_RUN_REAL=1` 闸）
- 🔴 静默失效（反例）：skip 无理由 —— 必须在清单里显形为「(无理由)」，
  不能因为"数字对得上"就混过去

以及聚合与三条下界判定本身的基本正确性。
"""
from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().with_name("工具-CI覆盖率护栏.py")

_spec = importlib.util.spec_from_file_location("ci_coverage_guardrail", SCRIPT)
guardrail = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(guardrail)


def _write_leg(base: Path, leg: str, cases: list[tuple[str, str | None]]) -> None:
    """造一条矩阵腿的 JUnit XML。cases 中 skip_message 为 None 表示该用例通过。"""
    leg_dir = base / leg
    leg_dir.mkdir(parents=True, exist_ok=True)
    skipped = sum(1 for _, msg in cases if msg is not None)
    body = []
    for name, msg in cases:
        if msg is None:
            body.append(f'<testcase classname="tests.test_x" name="{name}"/>')
        elif msg == "":
            # 无 message 属性——真正的"静默跳过"形态
            body.append(
                f'<testcase classname="tests.test_x" name="{name}"><skipped/></testcase>'
            )
        else:
            body.append(
                f'<testcase classname="tests.test_x" name="{name}">'
                f'<skipped message="{msg}"/></testcase>'
            )
    xml = (
        f'<testsuite tests="{len(cases)}" skipped="{skipped}" failures="0" errors="0">'
        + "".join(body)
        + "</testsuite>"
    )
    (leg_dir / "pytest-result.xml").write_text(xml, encoding="utf-8")


class AggregateTests(unittest.TestCase):
    def test_counts_across_legs(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            _write_leg(base, "leg-0", [("a", None), ("b", "环境闸")])
            _write_leg(base, "leg-1", [("c", None), ("d", None)])
            stats = guardrail.aggregate(base)
            self.assertEqual(stats["project_count"], 2)
            self.assertEqual(stats["tests"], 4)
            self.assertEqual(stats["skipped"], 1)
            self.assertEqual(stats["passed"], 3)


class SkipReasonBreakdownTests(unittest.TestCase):
    def test_explicit_reasons_are_grouped_and_counted(self):
        """合理增长形态：同理由合并计数，按腿排序。"""
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            _write_leg(base, "leg-qdb", [
                ("t1", "华丰黄金样本不存在（本地脱敏样本，不入库）"),
                ("t2", "华丰黄金样本不存在（本地脱敏样本，不入库）"),
                ("t3", "真实集成测试：置 SC8_RUN_REAL=1 才运行"),
                ("t4", None),
            ])
            per_leg = guardrail.collect_skip_reasons(base)
            self.assertEqual(
                per_leg["leg-qdb"],
                {
                    "华丰黄金样本不存在（本地脱敏样本，不入库）": 2,
                    "真实集成测试：置 SC8_RUN_REAL=1 才运行": 1,
                },
            )
            lines = "\n".join(guardrail.format_skip_breakdown(per_leg))
            self.assertIn("leg-qdb：跳过 3 条", lines)
            self.assertIn("2 × 华丰黄金样本不存在", lines)

    def test_skip_without_reason_shows_as_unexplained(self):
        """🔴 反例：无理由的 skip 正是"测试悄悄不跑了"的形态，必须显形。"""
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            _write_leg(base, "leg-x", [("t1", ""), ("t2", "")])
            per_leg = guardrail.collect_skip_reasons(base)
            self.assertEqual(per_leg["leg-x"], {"(无理由)": 2})
            lines = "\n".join(guardrail.format_skip_breakdown(per_leg))
            self.assertIn("2 × (无理由)", lines)

    def test_legs_ordered_by_skip_count_desc(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            _write_leg(base, "leg-small", [("t1", "理由A")])
            _write_leg(base, "leg-big", [("t1", "理由B"), ("t2", "理由B"), ("t3", "理由B")])
            lines = guardrail.format_skip_breakdown(guardrail.collect_skip_reasons(base))
            self.assertIn("leg-big", lines[0])

    def test_leg_without_skips_is_omitted(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            _write_leg(base, "leg-clean", [("t1", None), ("t2", None)])
            self.assertEqual(guardrail.format_skip_breakdown(guardrail.collect_skip_reasons(base)), [])

    def test_long_reason_is_truncated(self):
        """路径尾巴不带增量信息，且会把清单撑爆——截断到 100 字符。"""
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            _write_leg(base, "leg-long", [("t1", "理由" + "路" * 300)])
            per_leg = guardrail.collect_skip_reasons(base)
            self.assertEqual(len(next(iter(per_leg["leg-long"]))), 100)


class BaselineConstantsTests(unittest.TestCase):
    """基线是口径，改动须走队列 §四 拍板——本用例把当前值钉住，
    任何人改了这三个数，测试立刻红，逼出一次显式说明。"""

    def test_baselines_are_the_2026_08_08_values(self):
        self.assertEqual(guardrail.BASELINE_PASSED_MIN, 1698)
        self.assertEqual(guardrail.BASELINE_SKIPPED_MAX, 46)
        self.assertEqual(guardrail.BASELINE_PROJECT_COUNT_MIN, 13)


if __name__ == "__main__":
    unittest.main()
