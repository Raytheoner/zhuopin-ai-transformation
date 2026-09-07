"""`工具-跟进信往返度量.py` 单测（队列 §一 `#447` ⑵ 度量侧）。

白盒方式：按文件路径 importlib 加载被测脚本（本目录既定手法）。`build_report`
接收表格文本、不读文件，故绝大多数用例**不触碰真实 README**、也不需要临时夹具。

🔴 本文件的核心断言只有一条：**`事实日未知` 与「无标注」各自单列、都不混入中
位数，且两者不许合并。** 其余用例都是围着这一条的边界。
"""
from __future__ import annotations

import importlib.util
import io
import sys
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

SCRIPT = Path(__file__).resolve().with_name("工具-跟进信往返度量.py")

MAIN_HEADER = (
    "## 现有跟进信清单\n\n"
    "| 编号 | 日期 | 收信人 | 主要事项 | 交期要点 | 发送状态（2026-07-06） |\n"
    "|--------|------|--------|---------|---------|---------|\n"
)


def _load():
    spec = importlib.util.spec_from_file_location("_roundtrip_metric_under_test", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _row(number, sent_date, status):
    return f"| {number} | {sent_date} | 采购部 · 姚祖怡 | 事项 | 无 | {status} |\n"


def _mark(fact, recorded):
    return f"〔事实日 {fact} ／ 补记日 {recorded}〕"


class RoundtripMetricTests(unittest.TestCase):
    def setUp(self):
        self.module = _load()

    def _report(self, rows):
        return self.module.build_report(MAIN_HEADER + rows, "夹具")

    # ---- 分桶 ----------------------------------------------------------

    def test_有具体事实日的行进可算桶并算出往返天数(self):
        rows = _row("采购部#1", "2026-08-01", "📥 已回件并回灌 " + _mark("2026-08-04", "2026-08-05"))
        report = self._report(rows)
        self.assertEqual(report["counts"][self.module.BUCKET_COMPUTABLE], 1)
        self.assertEqual(report["items"][0]["roundtrip_days"], 3)
        self.assertEqual(report["items"][0]["backfill_lag_days"], 1)

    def test_事实日未知单列且不进可算桶(self):
        rows = _row("采购部#1", "2026-08-01", "📥 已回件并回灌 " + _mark("事实日未知", "2026-08-23"))
        report = self._report(rows)
        self.assertEqual(report["counts"][self.module.BUCKET_UNKNOWN], 1)
        self.assertEqual(report["counts"][self.module.BUCKET_COMPUTABLE], 0)
        self.assertEqual(report["buckets"][self.module.BUCKET_UNKNOWN], ["采购部#1"])

    def test_无尾标的历史行归无标注桶而不是事实日未知桶(self):
        """🔴 「没记」不许被洗成「记了不知道」——这两个桶合并即是本行要根治的
        那类信息销毁的温和版本。"""
        rows = _row("采购部#1", "2026-08-01", "📥 已回件并回灌（2026-08-23，拆件巡逻）")
        report = self._report(rows)
        self.assertEqual(report["counts"][self.module.BUCKET_UNMARKED], 1)
        self.assertEqual(report["counts"][self.module.BUCKET_UNKNOWN], 0)

    def test_不承载事实日的状态归不适用桶(self):
        rows = (
            _row("采购部#1", "2026-08-01", "⏳ 待你审")
            + _row("采购部#2", "2026-08-01", "🆕 待发")
            + _row("采购部#3", "2026-08-01", "⏸ 暂缓")
            + _row("采购部#4", "2026-08-01", "✅ 无需回复（发出即闭环）")
            + _row("采购部#5", "2026-08-01", "❌ 已作废")
        )
        report = self._report(rows)
        self.assertEqual(report["counts"][self.module.BUCKET_NA], 5)
        self.assertEqual(report["counts"][self.module.BUCKET_COMPUTABLE], 0)

    def test_四个桶之和等于主表行数(self):
        rows = (
            _row("采购部#1", "2026-08-01", "📥 已回件并回灌 " + _mark("2026-08-04", "2026-08-05"))
            + _row("采购部#2", "2026-08-01", "📥 已回件并回灌 " + _mark("事实日未知", "2026-08-23"))
            + _row("采购部#3", "2026-08-01", "📥 已回件并回灌（无尾标）")
            + _row("采购部#4", "2026-08-01", "⏳ 待你审")
        )
        report = self._report(rows)
        self.assertEqual(sum(report["counts"].values()), report["total_rows"])
        self.assertEqual(report["total_rows"], 4)

    # ---- 中位数 --------------------------------------------------------

    def test_可算样本不足时拒报中位数而不是报0(self):
        """一个「没有样本也照样给数」的度量脚本，就是 §4.5 那两个中位数的
        制造方式。"""
        rows = _row("采购部#1", "2026-08-01", "📥 已回件并回灌 " + _mark("2026-08-04", "2026-08-05"))
        report = self._report(rows)
        self.assertIsNone(report["median_days"])
        self.assertIn("拒绝报中位数", report["median_reason"])

    def test_样本够时报中位数且两个单列桶不参与计算(self):
        rows = "".join(
            _row(f"采购部#{i}", "2026-08-01", "📥 已回件并回灌 " + _mark(f"2026-08-0{i+1}", "2026-08-10"))
            for i in range(1, 6)
        )
        # 再塞 20 个「无标注」与「事实日未知」——若被混进去，中位数必然被拽走。
        rows += "".join(
            _row(f"质量部#{i}", "2026-08-01", "📥 已回件并回灌（无尾标）") for i in range(1, 11)
        )
        rows += "".join(
            _row(f"IT部#{i}", "2026-08-01", "📥 已回件并回灌 " + _mark("事实日未知", "2026-08-23"))
            for i in range(1, 11)
        )
        report = self._report(rows)
        self.assertEqual(report["samples"], [1, 2, 3, 4, 5])
        self.assertEqual(report["median_days"], 3)
        self.assertEqual(report["counts"][self.module.BUCKET_UNMARKED], 10)
        self.assertEqual(report["counts"][self.module.BUCKET_UNKNOWN], 10)

    def test_补记滞后一并报出(self):
        """补记滞后正是 2026-08-23 那次批量补转态当时看不见的那个量。"""
        rows = "".join(
            _row(f"采购部#{i}", "2026-08-01", "📥 已回件并回灌 " + _mark("2026-08-03", "2026-08-23"))
            for i in range(1, 6)
        )
        report = self._report(rows)
        self.assertEqual(report["backfill_lag_median"], 20)
        self.assertEqual(report["backfill_lag_max"], 20)

    # ---- 判据同源 ------------------------------------------------------

    def test_尾标判据与写侧同一份(self):
        """写侧与读侧各写一份正则的后果是写进去的标读不出来，而且不报错。"""
        registry_spec = importlib.util.spec_from_file_location(
            "_roundtrip_registry_probe",
            SCRIPT.with_name("工具-跟进信README登记.py"),
        )
        registry = importlib.util.module_from_spec(registry_spec)
        sys.modules[registry_spec.name] = registry
        registry_spec.loader.exec_module(registry)
        self.assertIs(self.module.FACT_DATE_UNKNOWN, registry.FACT_DATE_UNKNOWN)
        self.assertEqual(
            self.module.registry.FACT_MARK_RE.pattern, registry.FACT_MARK_RE.pattern
        )
        self.assertEqual(
            self.module.registry.FACT_DATE_REQUIRED_PREFIXES,
            registry.FACT_DATE_REQUIRED_PREFIXES,
        )
        # 端到端：写侧渲染出来的尾标，读侧必须原样认得。
        rendered = registry._render_fact_mark("2026-08-10", "2026-08-23")
        self.assertEqual(
            self.module.registry._parse_fact_mark(f"📥 已回件并回灌 {rendered}"),
            ("2026-08-10", "2026-08-23"),
        )

    # ---- 坏输入 --------------------------------------------------------

    def test_日期形态坏掉时退回单列而不是按0计(self):
        rows = _row("采购部#1", "不是日期", "📥 已回件并回灌 " + _mark("2026-08-04", "2026-08-05"))
        report = self._report(rows)
        self.assertEqual(report["counts"][self.module.BUCKET_COMPUTABLE], 0)
        self.assertEqual(report["counts"][self.module.BUCKET_UNMARKED], 1)
        self.assertIn("日期解析失败", report["items"][0]["reason"])

    def test_主表无数据行即报错而不是给一份空报告(self):
        """🔑「只读结果太干净先怀疑没读到对象」。"""
        with self.assertRaises(self.module.MetricError) as ctx:
            self.module.build_report(MAIN_HEADER, "夹具")
        self.assertIn("没读到目标文件", str(ctx.exception))

    # ---- 渲染与 CLI ----------------------------------------------------

    def test_渲染文本点名两个桶不许合并(self):
        rows = _row("采购部#1", "2026-08-01", "📥 已回件并回灌 " + _mark("事实日未知", "2026-08-23"))
        text = self.module.render(self._report(rows))
        self.assertIn("各自单列", text)
        self.assertIn("不许合并", text)
        self.assertIn("事实日未知", text)
        self.assertIn("无标注", text)

    def test_读不到文件时退出码1(self):
        err = io.StringIO()
        with redirect_stderr(err), redirect_stdout(io.StringIO()):
            code = self.module.main(["--file", "不存在的文件.md"])
        self.assertEqual(code, 1)
        self.assertIn("读不到", err.getvalue())

    def test_真实README可跑通且json可解析(self):
        """对生产 README 实跑一次——只读，不写。"""
        import json
        out = io.StringIO()
        with redirect_stdout(out):
            code = self.module.main(["--json"])
        self.assertEqual(code, 0)
        report = json.loads(out.getvalue())
        self.assertEqual(sum(report["counts"].values()), report["total_rows"])
        self.assertGreater(report["total_rows"], 0)


if __name__ == "__main__":
    unittest.main()
