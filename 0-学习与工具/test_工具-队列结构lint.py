"""工具-队列结构lint.py 单测（队列 #306，队列 #308 决策点 1 新增机器字段
硬门禁）。

白盒方式：直接调用 `lint(repo_root)`（该函数本就接收 repo_root 参数，
按其内部 `QUEUE_REL` 常量拼出目标文件相对路径），指向临时夹具目录（不
触碰真实生产队列文件）。
"""
from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().with_name("工具-队列结构lint.py")


def _load_module():
    spec = importlib.util.spec_from_file_location("_queue_lint_under_test", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


HEADER = (
    "> **编号高水位线：§一 #200 ｜ §四 #40**（说明文字）\n\n"
    "## 一、任务看板\n\n"
    "| # | 任务 | 领取方 | 输入（指针） | 期望产出 | 状态 | 触碰区 | 登记 |\n"
    "|---|------|--------|-------------|----------|------|--------|------|\n"
)


class QueueLintTests(unittest.TestCase):
    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.repo_root = Path(self._tmpdir.name)
        self.module = _load_module()
        self.target_path = self.repo_root / self.module.QUEUE_REL
        self.target_path.parent.mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        self._tmpdir.cleanup()

    def _write(self, section_one_row: str) -> None:
        text = (
            HEADER + section_one_row +
            "\n## 二、待 commit 批次（CC 取活销行）\n\n"
            "| 批次 | 文件清单 | 建议 message | 状态 |\n"
            "|------|---------|--------------|------|\n"
            "\n## 三、口径冻结标（重梳期防在途建造撞车）\n\n"
            "\n## 四、需 Shao Peishen 的动作（例外与拍板）\n\n"
            "| # | 事项 | 等谁 | 截止 |\n"
            "|---|------|------|------|\n"
        )
        self.target_path.write_text(text, encoding="utf-8")

    def test_row_with_valid_field_passes(self):
        self._write("| 150 | 任务 | CC | 指针 | 产出 | [S:open][D:机] 待领 | 触碰区 | 2026-08-09 |\n")
        self.assertEqual(self.module.lint(self.repo_root), [])

    def test_row_missing_field_is_violation(self):
        self._write("| 150 | 任务 | CC | 指针 | 产出 | 待领（未回填） | 触碰区 | 2026-08-09 |\n")
        violations = self.module.lint(self.repo_root)
        self.assertEqual(len(violations), 1)
        self.assertIn("缺少机器可读字段", violations[0])

    def test_row_with_malformed_field_is_violation(self):
        self._write("| 150 | 任务 | CC | 指针 | 产出 | [S:已完成] 正文 | 触碰区 | 2026-08-09 |\n")
        violations = self.module.lint(self.repo_root)
        self.assertEqual(len(violations), 1)

    def test_column_mismatch_still_detected(self):
        self._write("| 150 | 任务 | CC | 指针 | 产出 | [S:open] 待领 | 触碰区 |\n")  # 7 列，少登记
        violations = self.module.lint(self.repo_root)
        self.assertTrue(any("列数为 7" in v for v in violations))

    def test_all_six_status_values_pass(self):
        for value in ("done", "open", "partial", "hold", "blocked", "timed=2026-09-01"):
            with self.subTest(value=value):
                self._write(f"| 150 | 任务 | CC | 指针 | 产出 | [S:{value}][D:机] 正文 | 触碰区 | 2026-08-09 |\n")
                self.assertEqual(self.module.lint(self.repo_root), [])

    def test_section_two_ambiguous_status_still_detected(self):
        text = (
            HEADER +
            "| 150 | 任务 | CC | 指针 | 产出 | [S:open][D:机] 待领 | 触碰区 | 2026-08-09 |\n"
            "\n## 二、待 commit 批次（CC 取活销行）\n\n"
            "| 批次 | 文件清单 | 建议 message | 状态 |\n"
            "|------|---------|--------------|------|\n"
            "| B-TEST | `x.md` | `msg` | 本session直接commit |\n"
            "\n## 三、口径冻结标（重梳期防在途建造撞车）\n\n"
            "\n## 四、需 Shao Peishen 的动作（例外与拍板）\n\n"
            "| # | 事项 | 等谁 | 截止 |\n"
            "|---|------|------|------|\n"
        )
        self.target_path.write_text(text, encoding="utf-8")
        violations = self.module.lint(self.repo_root)
        self.assertTrue(any("状态列模糊" in v for v in violations))

    def test_real_production_queue_file_passes(self):
        """回归护栏：确保 106 行存量回填后的真实生产队列文件通过本 lint
        （队列 #308 决策点 3 回填完成的直接验证）。"""
        violations = self.module.lint(self.module.REPO_ROOT)
        self.assertEqual(violations, [], f"真实生产队列文件不应有 lint 违规：{violations}")


if __name__ == "__main__":
    unittest.main()
