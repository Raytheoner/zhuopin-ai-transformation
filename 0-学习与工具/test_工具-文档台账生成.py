"""工具-文档台账生成.py 单测。

一、队列 §一 行列数自检（队列 #164，2026-07-30 状态页取数时实测发现六行裸竖线
    致列数偏离标准 8 列）——`check_queue_row_column_counts` 是纯函数，直接喂合成
    队列文本即可，不依赖真实项目文件。
二、构建/缓存产物排除（队列 #98 并入项，2026-08-17）——夹具造一个真实的
    `.pytest_cache/README.md`，跑完整 `main()` 断言它既不出现在台账正文里、
    也不计入份数与"待补状态头"计数。
"""
from __future__ import annotations

import importlib.util
import tempfile
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


class BuildArtifactExclusionTests(unittest.TestCase):
    """队列 #98 并入项回归：构建/缓存产物不得进台账、不得计入份数。

    成因（实测，非假想）：同一 commit 下主工作区跑出 338 份 md／20 份待补状态头，
    某 worktree 内跑出 335／17，差的 3 份全是 `.pytest_cache/README.md`。
    ⇒ 份数随「这个 checkout 最近有没有跑过 pytest」漂移，
    「份数变了 ⇒ 有人动过文档」这个判断因此变成假信号。
    """

    def test_is_build_artifact_matches_directory_segments(self):
        cases = {
            "0-学习与工具/.pytest_cache/README.md": True,
            "0-学习与工具/__pycache__/x.md": True,
            "1-转型规划/a/.mypy_cache/b/c.md": True,  # 深层嵌套同样命中
            "5-平台底座/zhuopin_platform.egg-info/PKG.md": True,  # 后缀型
            "0-学习与工具/正常文档.md": False,
            "1-转型规划/0-全景路线图/README.md": False,  # 与产物同名但不在产物目录下
        }
        for rel, expected in cases.items():
            with self.subTest(rel=rel):
                self.assertEqual(ledger.is_build_artifact(Path(rel)), expected)

    def test_last_segment_is_not_judged_as_directory(self):
        """只判目录段——一个恰好叫 `__pycache__.md` 的文档不该被误伤。"""
        self.assertFalse(ledger.is_build_artifact(Path("0-学习与工具/__pycache__.md")))

    def _run_main_in(self, root: Path) -> str:
        """在临时根上跑完整 main()，返回生成的台账正文。"""
        out = root / "台账.md"
        originals = (ledger.REPO_ROOT, ledger.OUTPUT_PATH, ledger.SCAN_DIRS, ledger.QUEUE_PATHS)
        ledger.REPO_ROOT, ledger.OUTPUT_PATH = root, out
        ledger.SCAN_DIRS, ledger.QUEUE_PATHS = ["docs"], []
        try:
            ledger.main()
            return out.read_text(encoding="utf-8")
        finally:
            (ledger.REPO_ROOT, ledger.OUTPUT_PATH,
             ledger.SCAN_DIRS, ledger.QUEUE_PATHS) = originals

    def test_pytest_cache_readme_absent_from_ledger_and_counts(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            docs = root / "docs"
            docs.mkdir()
            (docs / "真文档.md").write_text(
                "---\nstatus: 生效\ntitle: 真文档\n---\n\n# 真文档\n", encoding="utf-8"
            )
            cache = docs / ".pytest_cache"
            cache.mkdir()
            # pytest 真实生成的那份 README（无 frontmatter ⇒ 修复前必落"待补状态头"）
            (cache / "README.md").write_text(
                "# pytest cache directory #\n\nThis directory contains data...\n",
                encoding="utf-8",
            )

            text = self._run_main_in(root)

            # 注：不能直接断言 `"pytest_cache" not in text`——台账头部那句排除口径
            # 说明本身就含这个词；要断言的是它没有作为**条目**被收录。
            self.assertNotIn("docs/.pytest_cache/README.md", text)
            self.assertNotIn("待补状态头清单", text)
            self.assertIn("真文档", text)
            self.assertIn("共 1 份 md，0 份待补状态头", text)

    def test_fixture_would_be_collected_without_the_blacklist(self):
        """反向用例：证明上一条不是恒真——把黑名单清空，同一夹具立刻被收录
        并落入"待补状态头"，即修复前的真实症状。"""
        original = ledger.EXCLUDED_DIR_NAMES
        ledger.EXCLUDED_DIR_NAMES = frozenset()
        try:
            with tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                docs = root / "docs"
                (docs / ".pytest_cache").mkdir(parents=True)
                (docs / ".pytest_cache" / "README.md").write_text(
                    "# pytest cache directory #\n", encoding="utf-8"
                )
                text = self._run_main_in(root)
            self.assertIn("docs/.pytest_cache/README.md", text)
            self.assertIn("共 1 份 md，1 份待补状态头", text)
        finally:
            ledger.EXCLUDED_DIR_NAMES = original

    def test_count_is_stable_whether_or_not_cache_exists(self):
        """同一份文档集，有无 pytest 缓存都必须跑出同一个份数——本行是本次修的
        那个"信号可信度"本身，比上一条更贴近立行理由。"""
        counts = []
        for with_cache in (False, True):
            with tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                docs = root / "docs"
                docs.mkdir()
                (docs / "甲.md").write_text("---\nstatus: 生效\n---\n", encoding="utf-8")
                (docs / "乙.md").write_text("---\nstatus: 在办\n---\n", encoding="utf-8")
                if with_cache:
                    for sub in (".pytest_cache", "__pycache__"):
                        d = docs / sub
                        d.mkdir()
                        (d / "README.md").write_text("# cache\n", encoding="utf-8")
                text = self._run_main_in(root)
                counts.append(
                    [ln for ln in text.splitlines() if "份 md" in ln][0]
                )
        self.assertEqual(counts[0], counts[1])


if __name__ == "__main__":
    unittest.main()
