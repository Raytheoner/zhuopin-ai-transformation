"""工具-文档台账生成.py 单测。

聚焦新增的队列 §一 行列数自检（队列 #164，2026-07-30 状态页取数时实测发现
六行裸竖线致列数偏离标准 8 列）——`check_queue_row_column_counts` 是纯函数，
直接喂合成队列文本即可，不依赖真实项目文件。
"""
from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().with_name("工具-文档台账生成.py")

_spec = importlib.util.spec_from_file_location("doc_ledger", SCRIPT)
ledger = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ledger)

QUEUE_HEADER = (
    "---\ntitle: 测试队列\n---\n\n# 测试队列\n\n"
    "## 一、任务看板\n\n"
    "| # | 任务 | 领取方 | 输入（指针） | 期望产出 | 状态 | 触碰区 | 登记 |\n"
    "|---|------|--------|-------------|----------|------|--------|------|\n"
    "{rows}"
    "\n## 二、待 commit 批次\n\n（无）\n"
)


class CheckQueueRowColumnCountsTests(unittest.TestCase):
    def test_standard_eight_column_row_is_clean(self):
        text = QUEUE_HEADER.format(
            rows="| 1 | 任务描述 | CC | 输入 | 产出 | 待领 | 触碰区 | 07-30 |\n"
        )
        self.assertEqual(ledger.check_queue_row_column_counts(text), [])

    def test_bare_pipe_in_prose_inflates_column_count(self):
        # 正文里一个裸竖线把本应是一列的内容切成两列——列数变 9（模拟真实
        # 故障：期望产出内部含一个裸竖线，此处只关心列数，不关心语义错位）。
        malformed_row = (
            "| 2 | 任务描述 | CC | 输入 | 期望产出前段 | 期望产出后段 "
            "| 状态 | 触碰区 | 08-01 |\n"
        )
        text = QUEUE_HEADER.format(rows=malformed_row)
        anomalies = ledger.check_queue_row_column_counts(text)
        self.assertEqual(anomalies, [("2", 9)])

    def test_two_bare_pipes_inflate_to_ten_columns(self):
        row = (
            "| 3 | 任务 A段 | 任务 B段 | 任务 C段 | 领取方 | 输入 | 产出 "
            "| 状态 | 触碰区 | 08-01 |\n"
        )
        text = QUEUE_HEADER.format(rows=row)
        anomalies = ledger.check_queue_row_column_counts(text)
        self.assertEqual(anomalies, [("3", 10)])

    def test_multiple_rows_only_reports_anomalous_ones(self):
        rows = (
            "| 1 | 正常行 | CC | 输入 | 产出 | 待领 | 触碰区 | 07-30 |\n"
            "| 2 | 坏行 A段 | 坏行 B段 | CC | 输入 | 产出 | 待领 | 触碰区 | 07-30 |\n"
            "| 3 | 又一个正常行 | CC | 输入 | 产出 | 待领 | 触碰区 | 07-30 |\n"
        )
        text = QUEUE_HEADER.format(rows=rows)
        anomalies = ledger.check_queue_row_column_counts(text)
        self.assertEqual(anomalies, [("2", 9)])

    def test_header_and_separator_rows_are_skipped(self):
        # 表头 "# | 任务 | ..." 与分隔行 "---|---|..." 不应被当成数据行误报。
        text = QUEUE_HEADER.format(rows="")
        self.assertEqual(ledger.check_queue_row_column_counts(text), [])

    def test_missing_section_returns_empty(self):
        self.assertEqual(ledger.check_queue_row_column_counts("# 空文档\n"), [])

    def test_six_row_regression_fixture_all_clean(self):
        """回归夹具：模拟队列 #164 实际修复的六行结构（长正文 + 全角／替代裸竖线），
        确认修复后的写法不再触发自检。"""
        rows = (
            "| 111 | 长任务描述，结尾带全角替代符／已完成（口径）／填数待各专线 "
            "| Cowork | 输入 | 产出 | 状态 | 触碰区 | 07-25 |\n"
            "| 125 | 含转义后的命令片段`Get-CimInstance Win32_Process ／ Where-Object` "
            "| CC | 输入 | 产出 | 状态 | 触碰区 | 07-27 |\n"
        )
        text = QUEUE_HEADER.format(rows=rows)
        self.assertEqual(ledger.check_queue_row_column_counts(text), [])

    def test_backtick_wrapped_bare_pipe_is_not_miscounted(self):
        """队列 #313/#314 回归：反引号包裹的代码示例内出现裸竖线（如
        `git grep` 正则交替符）此前会被本函数自行实现的朴素 `split("|")`
        误判为额外列分隔符、产生假阳性（#313 行实测命中，11 列 vs 应有
        8 列）。委托 `queue_table.parse_section_rows`（反引号感知，#314）
        后不应再误报。"""
        row = (
            '| 4 | 任务描述含代码示例 `git grep -E "a|b"` 结尾 '
            "| CC | 输入 | 产出 | 待领 | 触碰区 | 08-09 |\n"
        )
        text = QUEUE_HEADER.format(rows=row)
        self.assertEqual(ledger.check_queue_row_column_counts(text), [])


if __name__ == "__main__":
    unittest.main()
