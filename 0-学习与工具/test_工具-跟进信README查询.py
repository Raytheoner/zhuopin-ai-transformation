"""`工具-跟进信README查询.py` 单测（队列 §一 #382⑵）。

白盒方式：按文件路径 importlib 加载被测脚本（同 `test_工具-跟进闸查询.py`
既定手法），把 `REPO_ROOT` 指向临时夹具目录——不触碰真实 README。
"""
from __future__ import annotations

import importlib.util
import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

SCRIPT = Path(__file__).resolve().with_name("工具-跟进信README查询.py")

README_REL = "6-人才与组织/部门AI专员跟进/README-跟进机制与命名约定.md"

README_HEADER = (
    "## 现有跟进信清单\n\n"
    "| 编号 | 日期 | 收信人 | 主要事项 | 交期要点 | 发送状态（2026-07-06） |\n"
    "|--------|------|--------|---------|---------|---------|\n"
)


def _load():
    spec = importlib.util.spec_from_file_location("_followup_readme_digest_under_test", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _row(number, recipient, delivery, status, date="2026-08-20", topic="事项"):
    return f"| {number} | {date} | {recipient} | {topic} | {delivery} | {status} |\n"


class FollowupReadmeDigestTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.module = _load()
        self.module.REPO_ROOT = self.root
        (self.root / README_REL).parent.mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        self._tmp.cleanup()

    def _write_readme(self, rows: str):
        (self.root / README_REL).write_text(README_HEADER + rows, encoding="utf-8")

    def _rows(self, width=None):
        text = (self.root / README_REL).read_text(encoding="utf-8")
        kwargs = {} if width is None else {"width": width}
        return self.module.build_digest_rows(text, **kwargs)

    # ------------------------------------------------------------ 三态识别

    def test_三个待发态各自被正确识别(self):
        self._write_readme(
            _row("采购部#1", "采购部 · 姚祖怡", "尽快", "⏳ 待你审")
            + _row("采购部#2", "采购部 · 姚祖怡", "尽快", "🆕 待发")
            + _row("采购部#3", "采购部 · 姚祖怡", "尽快", "⏸ 暂缓")
        )
        rows = self._rows()
        got = {r["number"]: r["not_yet_sent_prefix"] for r in rows}
        self.assertEqual(got, {
            "采购部#1": "⏳ 待你审",
            "采购部#2": "🆕 待发",
            "采购部#3": "⏸ 暂缓",
        })

    def test_已闭环与已推送均不计入待发三态(self):
        self._write_readme(
            _row("采购部#1", "采购部 · 姚祖怡", "尽快", "📥 已回件并回灌（2026-08-23）")
            + _row("采购部#2", "采购部 · 姚祖怡", "尽快", "✅ 已推送 2026-08-20 12:20 UTC")
            + _row("采购部#3", "采购部 · 姚祖怡", "尽快", "📨 回件已到，待拆件 2026-09-02T00:00:00Z")
        )
        rows = self._rows()
        self.assertTrue(all(r["not_yet_sent_prefix"] is None for r in rows))
        kinds = {r["number"]: r["status_kind"] for r in rows}
        self.assertEqual(kinds, {
            "采购部#1": "closed",
            "采购部#2": "in_flight",
            "采购部#3": "reply_arrived",
        })

    # ------------------------------------------------------------ 截断安全

    def test_状态前缀在任意窄宽度下均不被截断(self):
        """回归 #439 那类"关键判断信息被截断算法误伤"缺陷：即便
        --digest-width 小到 1，`not_yet_sent_prefix` 仍必须正确识别——
        判定读的是原始状态列，不是被截断过的展示字符串。"""
        long_tail = "，" + "补充说明" * 50  # 制造一个远超任何合理宽度的尾巴
        self._write_readme(_row("采购部#1", "采购部 · 姚祖怡", "尽快", "🆕 待发" + long_tail))
        for width in (1, 5, 40):
            rows = self._rows(width=width)
            self.assertEqual(rows[0]["not_yet_sent_prefix"], "🆕 待发",
                              f"width={width} 时前缀判定不应受影响")
            self.assertTrue(rows[0]["status_digest"].startswith("🆕 待发"),
                             f"width={width} 时展示文本必须仍以完整前缀开头，实得：{rows[0]['status_digest']}")

    def test_未识别前缀落入非静默降级兜底(self):
        self._write_readme(_row("采购部#1", "采购部 · 姚祖怡", "尽快", "🔄 已并入合并件，本件不发"))
        rows = self._rows()
        self.assertTrue(rows[0]["status_malformed"])
        self.assertEqual(rows[0]["status_kind"], "unknown")
        self.assertNotEqual(rows[0]["status_digest"], "")

    def test_交期要点超宽度按分隔符或宽度截断并补省略号(self):
        self._write_readme(_row("采购部#1", "采购部 · 姚祖怡",
                                 "① 这是第一项相当长的交期说明；② 第二项", "🆕 待发"))
        rows = self._rows(width=12)
        self.assertTrue(rows[0]["delivery_digest"].endswith("…") or "；" not in rows[0]["delivery_digest"][12:])

    # ------------------------------------------------------------ 收信人/部门

    def test_收信人正常解析出部门与姓名(self):
        self._write_readme(_row("质量部#9", "质量部 · 陈忱（可分担朱映桦）", "尽快", "🆕 待发"))
        rows = self._rows()
        self.assertEqual(rows[0]["department"], "质量部")
        # `name`（裸姓名，不含括注/部门前缀）——sweep 侧交叉红标要用它去
        # 匹配队列行里惯用的裸姓名写法（如"姚祖怡那封信先暂缓"），不能只
        # 靠完整 `recipient` 字段（"质量部 · 陈忱（可分担朱映桦）"）。
        self.assertEqual(rows[0]["name"], "陈忱")

    def test_收信人无法解析部门时不崩溃(self):
        self._write_readme(_row("销售部（未发，不编号）", "销售部", "尽快", "🆕 待发"))
        rows = self._rows()
        self.assertIsNone(rows[0]["department"])

    # ------------------------------------------------------------ CLI

    def test_digest文本模式与json模式行数一致(self):
        self._write_readme(
            _row("采购部#1", "采购部 · 姚祖怡", "尽快", "🆕 待发")
            + _row("采购部#2", "采购部 · 姚祖怡", "尽快", "📥 已回件并回灌（2026-08-23）")
        )
        text_buf = io.StringIO()
        with redirect_stdout(text_buf):
            code = self.module.main(["--digest"])
        self.assertEqual(code, 0)
        self.assertIn("合计 2 行", text_buf.getvalue())
        self.assertIn("🆕 待发×1", text_buf.getvalue())

        json_buf = io.StringIO()
        with redirect_stdout(json_buf):
            code = self.module.main(["--digest", "--json"])
        self.assertEqual(code, 0)
        data = json.loads(json_buf.getvalue())
        self.assertEqual(data["total_rows"], 2)
        self.assertEqual(len(data["rows"]), 2)

    def test_README表损坏退出码1(self):
        (self.root / README_REL).write_text("这份文件里没有任何跟进信表格\n", encoding="utf-8")
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = self.module.main(["--digest"])
        self.assertEqual(code, 1)
        self.assertIn("✗", buf.getvalue())

    def test_digest宽度非正数报错(self):
        self._write_readme(_row("采购部#1", "采购部 · 姚祖怡", "尽快", "🆕 待发"))
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = self.module.main(["--digest", "--digest-width", "0"])
        self.assertEqual(code, 1)

    def test_空表输出零行不崩溃(self):
        self._write_readme("")
        rows = self._rows()
        self.assertEqual(rows, [])


if __name__ == "__main__":
    unittest.main()
