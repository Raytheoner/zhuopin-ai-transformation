"""工具-队列查询.py 单测（队列 #268）。

黑盒方式：每个用例起子进程调用脚本，`--file` 指向本用例专属的临时文件，
不触碰真实的跨桌任务队列.md，用例之间互不干扰。
"""
from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().with_name("工具-队列查询.py")

FIXTURE = """## 一、任务看板

| # | 任务 | 领取方 | 输入（指针） | 期望产出 | 状态 | 触碰区 | 登记 |
|---|------|--------|-------------|----------|------|--------|------|
| 100 | 示例任务A | CC | 无 | 无 | ✅ 已完成（简单场景） | 无 | 2026-08-01 |
| 101 | 示例任务B（头尾冲突场景，模拟 #268 真实事故） | CC | 无 | 无 | ✅ 已完成初判——但深入核实后发现前提有误，实际仍待领，需重新处理。 | 无 | 2026-08-01 |
| 102 | 示例任务C（反方向：开头待领，结尾已拍板） | CC | 无 | 无 | 待领——补充说明：Shao Peishen 已拍板选项 (a)，只是尚未回填措辞。 | 无 | 2026-08-01 |
| 103 | 列偏移场景 | CC | 无 | 无 | 状态含裸竖线|导致列数偏移 | 无 | 2026-08-01 |
| 104 | 机器字段场景（队列 #308） | CC | 无 | 无 | [S:open][D:机] 待领（P1） | 无 | 2026-08-01 |
| 105 | 机器字段+正文头尾冲突场景 | CC | 无 | 无 | [S:done][D:机] ✅ 已完成初判——但深入核实后发现前提有误，实际仍待领。 | 无 | 2026-08-01 |

## 二、待 commit 批次（CC 取活销行）

| 批次 | 文件清单 | 说明 | 状态 |
|------|---------|------|------|
| B-0801_示例批次 | `示例文件.md` | 示例说明 | ✅ 已完成 |

## 三、口径冻结标（重梳期防在途建造撞车）

（暂无）

## 四、需 Shao Peishen 的动作（例外与拍板）

| # | 事项 | 等谁 | 截止 |
|---|------|------|------|
| 100 | §四示例事项，无独立状态列，混合叙述 | Shao Peishen | 不急 |
"""


def run(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        capture_output=True, text=True, encoding="utf-8",
    )


class QueueQueryTests(unittest.TestCase):
    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.target = Path(self._tmpdir.name) / "假想队列.md"
        self.target.write_text(FIXTURE, encoding="utf-8")

    def tearDown(self):
        self._tmpdir.cleanup()

    def test_finds_row_in_section_one_full_status_no_truncation(self):
        result = run("--row", "100", "--section", "一", "--file", str(self.target))
        self.assertEqual(result.returncode, 0)
        self.assertIn("✅ 已完成（简单场景）", result.stdout)

    def test_leading_done_trailing_pending_triggers_conflict_warning(self):
        result = run("--row", "101", "--section", "一", "--file", str(self.target))
        self.assertEqual(result.returncode, 0)
        self.assertIn("冲突警告", result.stdout)
        self.assertIn("待领", result.stdout)

    def test_leading_pending_trailing_done_triggers_conflict_warning_reverse(self):
        result = run("--row", "102", "--section", "一", "--file", str(self.target))
        self.assertEqual(result.returncode, 0)
        self.assertIn("冲突警告", result.stdout)

    def test_clean_row_no_conflict_warning(self):
        result = run("--row", "100", "--section", "一", "--file", str(self.target))
        self.assertNotIn("冲突警告", result.stdout)

    def test_row_without_machine_field_shows_degradation_notice(self):
        result = run("--row", "100", "--section", "一", "--file", str(self.target))
        self.assertIn("未识别到 [S:...] 机器字段", result.stdout)

    def test_row_with_machine_field_shows_parsed_values(self):
        result = run("--row", "104", "--section", "一", "--file", str(self.target))
        self.assertEqual(result.returncode, 0)
        self.assertIn("机器字段解析", result.stdout)
        self.assertIn("状态＝open", result.stdout)
        self.assertIn("域 机", result.stdout)
        self.assertNotIn("冲突警告", result.stdout)

    def test_machine_field_row_conflict_check_applies_to_natural_text_only(self):
        """字段本身（[S:done][D:机]）不参与头尾冲突扫描，只扫字段之后的
        自然语言正文——本例正文本身仍有真实头尾冲突（✅已完成…实际仍待
        领），应仍被检出。"""
        result = run("--row", "105", "--section", "一", "--file", str(self.target))
        self.assertEqual(result.returncode, 0)
        self.assertIn("机器字段解析", result.stdout)
        self.assertIn("状态＝done", result.stdout)
        self.assertIn("冲突警告", result.stdout)

    def test_section_two_lookup_by_batch_id(self):
        result = run("--row", "B-0801_示例批次", "--section", "二", "--file", str(self.target))
        self.assertEqual(result.returncode, 0)
        self.assertIn("✅ 已完成", result.stdout)

    def test_section_four_has_no_dedicated_status_column_falls_back_to_topic(self):
        result = run("--row", "100", "--section", "四", "--file", str(self.target))
        self.assertEqual(result.returncode, 0)
        self.assertIn("事项", result.stdout)
        self.assertIn("无独立状态列", result.stdout)
        self.assertIn("§四示例事项", result.stdout)

    def test_not_found_returns_nonzero(self):
        result = run("--row", "99999", "--file", str(self.target))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("未找到", result.stdout)

    def test_ambiguous_number_across_sections_requires_disambiguation(self):
        # §一 与 §四 都存在编号 100，不指定 --section 时应拒绝猜测。
        result = run("--row", "100", "--file", str(self.target))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("--section", result.stdout)

    def test_field_all_prints_every_column_labeled(self):
        result = run("--row", "100", "--section", "一", "--field", "all", "--file", str(self.target))
        self.assertEqual(result.returncode, 0)
        for label in ("【#】", "【任务】", "【领取方】", "【状态】", "【触碰区】", "【登记】"):
            self.assertIn(label, result.stdout)

    def test_column_offset_row_warns_about_mismatch(self):
        result = run("--row", "103", "--section", "一", "--file", str(self.target))
        self.assertIn("列偏移", result.stdout)

    def test_missing_file_reports_error(self):
        result = run("--row", "1", "--file", str(Path(self._tmpdir.name) / "不存在.md"))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("读取目标文件失败", result.stdout)


if __name__ == "__main__":
    unittest.main()
