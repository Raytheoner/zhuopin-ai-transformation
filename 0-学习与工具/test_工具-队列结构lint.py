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
        # 队列 #315：既有用例把 §一/§二/§三/§四 全部写在这一份文件里——
        # 白盒直接调用，故可直接 monkeypatch `QUEUE_PATHS_REL` 只含这一份，
        # 不必逐个用例改造为双文件夹具（业务场景文件相关行为另有专门用例
        # 覆盖，见 `DualFileLintTests`）。
        self.module.QUEUE_PATHS_REL = [self.module.QUEUE_REL]

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

    def test_row_truncated_before_closing_pipe_is_caught_not_silently_passed(self):
        """队列 #314①：真实历史事故复现——#313 行在 commit `298c152` 起被
        `git grep` 的正则交替符 `|` 撑破，触碰区/日期两列被整体吞掉，行不再
        以 `|` 收尾（`git show 298c152:跨桌任务队列.md` 可复现，下方首尾
        文本逐字取自该提交的真实 #313 行，中段省略）。

        修复前：`_table_data_rows` 要求行首行尾都必须是 `|`，这种行连
        `_table_data_rows` 的返回列表都进不去，`lint()` 因此报 0 violations
        （见 #314 调查记录——这正是"lint 放行"的真实机制，而非最初怀疑的
        "列数判据只查多不查少"，`column_count_ok`/`len(cells) != expected`
        本就是双向比较）。修复后：该行仍应被 `_table_data_rows` 收录、并被
        列数校验命中。"""
        real_head = (
            "🔴🔴 **`queue_table` 权威化收尾——③ 已有一处真实生产失效正在发生"
            "（P2 → 升 P1，2026-08-09 同日两次追加）**"
        )
        real_tail_no_closing_pipe = (
            "按 `CLAUDE.md` §5 机制类三条门槛：① 属纯可观测性增强、不改对外"
            "语义，大概率不触发；② 改的是模块解析路径的来源，**若使既有函数"
            "在相同输入下行为改变即命中第③条**，判不准就走"
        )
        truncated_row = (
            f"| 313 | {real_head}……（中段省略，完整正文见真实历史提交）"
            f"……{real_tail_no_closing_pipe}\n"
        )
        self.assertFalse(truncated_row.strip().endswith("|"))
        self._write(truncated_row)
        violations = self.module.lint(self.repo_root)
        self.assertTrue(
            any("列数为" in v and "313" in v for v in violations),
            f"应命中列数违规，实际：{violations}",
        )

    def test_real_production_queue_file_passes(self):
        """回归护栏：确保存量回填后的真实生产队列文件通过本 lint（队列
        #308 决策点 3 回填完成的直接验证）。队列 #315：本用例须验证真实
        的两份物理文件，先撤销 setUp 里为其它单文件用例做的 monkeypatch，
        换回模块加载时算出的真实生产路径。"""
        real_paths = [self.module.editlock.QUEUE_MECHANISM_PATH_REL,
                      self.module.editlock.QUEUE_BUSINESS_PATH_REL]
        self.module.QUEUE_PATHS_REL = real_paths
        violations = self.module.lint(self.module.REPO_ROOT)
        self.assertEqual(violations, [], f"真实生产队列文件不应有 lint 违规：{violations}")


class QueueTableImportableCheckTests(unittest.TestCase):
    """队列 #313：权威模块 zhuopin_platform.shared_tools.queue_table
    可 import 断言——兜底桩静默降级的可见化，真实场景（模块健在／
    仓库根标记缺失）均需覆盖，不能只靠人读代码确认。"""

    def setUp(self):
        self.module = _load_module()

    def test_real_repo_root_is_importable(self):
        self.assertIsNone(self.module.check_queue_table_importable(self.module.REPO_ROOT))

    def test_missing_platform_dir_is_violation(self):
        with tempfile.TemporaryDirectory() as tmp:
            fake_root = Path(tmp)
            result = self.module.check_queue_table_importable(fake_root)
            self.assertIsNotNone(result)
            self.assertIn("未找到", result)

    def test_does_not_leak_sys_path_entry_on_success(self):
        import sys

        platform_dir = str(self.module.REPO_ROOT / "5-平台底座" / "zhuopin_platform")
        was_present_before = platform_dir in sys.path
        self.module.check_queue_table_importable(self.module.REPO_ROOT)
        if not was_present_before:
            self.assertNotIn(
                platform_dir, sys.path,
                "本函数临时插入的 sys.path 条目须自行清理，不得残留影响后续 import 解析",
            )


if __name__ == "__main__":
    unittest.main()
