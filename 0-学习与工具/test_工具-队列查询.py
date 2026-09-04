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
| 106 | 行尾被截断场景（模拟队列 #313 真实事故，触碰区/日期两列被外部工具吞掉） | CC | 无 | 无 | 状态列写到一半就断了，没有收尾

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

    def test_row_not_ending_in_pipe_is_still_found(self):
        """队列 #314①：`_table_data_rows` 此前要求行首行尾都必须是 `|`，
        导致行尾被外部工具吞掉的行（真实事故见队列 #313——`git show
        298c152` 可复现）连"未找到"都不会真的报"结构损坏"，只会静默报
        "未找到"，看起来像编号写错而非文件本身坏了。放宽为只要求行首后，
        该行仍应被找到（同时被判定为列数偏移，两件事互不矛盾）。"""
        result = run("--row", "106", "--section", "一", "--file", str(self.target))
        self.assertEqual(result.returncode, 0)
        self.assertIn("列偏移", result.stdout)
        self.assertIn("状态列写到一半就断了", result.stdout)

    def test_missing_file_reports_error(self):
        result = run("--row", "1", "--file", str(Path(self._tmpdir.name) / "不存在.md"))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("读取目标文件失败", result.stdout)


# ══════════════════════════════════════════════════════════════════════════
# 队列 #441：--digest 单文件模式（黑盒，--file 指向本用例专属临时文件）
# ══════════════════════════════════════════════════════════════════════════

DIGEST_FIXTURE = """## §一 任务看板 · 归档式标题（无顿号，模拟 #442 归档件标题写法）

| # | 任务 | 领取方 | 输入（指针） | 期望产出 | 状态 | 触碰区 | 登记 |
|---|------|--------|-------------|----------|------|--------|------|
| 500 | 这是一段刻意写得比默认宽度四十字更长的任务标题，用来验证截断与省略号是否正确附加在尾部 | CC | 无 | 无 | [S:open][D:机] 待领（P1） | 无 | 2026-08-01 |
| 501 | 短标题 | CC | 无 | 无 | [S:done][D:业] ✅ 已完成 | 无 | 2026-08-01 |
| 502 | 状态列没有机器字段的历史行 | CC | 无 | 无 | 待领，08-09 之前的老行没有 [S:...] 前缀 | 无 | 2026-07-01 |

## 四、需 Shao Peishen 的动作（例外与拍板）

| # | 事项 | 等谁 | 截止 |
|---|------|------|------|
| 500 | §四 也有编号 500，不得被 §一 digest 误收 | Shao Peishen | 不急 |
"""


class DigestModeTests(unittest.TestCase):
    """队列 #441：--digest 单文件模式黑盒用例。"""

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.target = Path(self._tmpdir.name) / "假想队列.md"
        self.target.write_text(DIGEST_FIXTURE, encoding="utf-8")

    def tearDown(self):
        self._tmpdir.cleanup()

    def test_digest_finds_rows_under_non_standard_heading(self):
        """核心架构验证（队列 #442 起因）：本夹具标题故意不写成 `## 一、`
        （改用归档件常见的 `## §一 ... ·` 无顿号写法），结构性扫描应仍能
        找到 §一 数据行——若退化为按 `## 一、` 标题切分，会像归档件
        `跨桌任务队列-归档-202608.md` 那样静默得到零行（实测：该归档件
        对 `^## ([一二三四])、` 正则只命中两处 `## 二、`，`## 一、` 零命中）。"""
        result = run("--digest", "--file", str(self.target))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("500｜", result.stdout)
        self.assertIn("501｜", result.stdout)
        self.assertIn("502｜", result.stdout)

    def test_digest_excludes_section_four_row_with_same_number(self):
        """§四 同样有编号 500，§一 digest 不得把它当成 §一 的第 500 行
        混进来——结构性扫描按列数（8 vs 4）天然分开，不需要额外过滤。"""
        result = run("--digest", "--file", str(self.target))
        self.assertEqual(result.returncode, 0)
        self.assertNotIn("不得被 §一 digest 误收", result.stdout)

    def test_digest_line_format_uses_fullwidth_separator(self):
        result = run("--digest", "--file", str(self.target))
        self.assertIn("501｜[S:done][D:业]｜短标题", result.stdout)

    def test_digest_truncates_long_task_with_ellipsis_at_default_width(self):
        result = run("--digest", "--file", str(self.target))
        self.assertEqual(result.returncode, 0)
        self.assertIn("…", result.stdout)
        self.assertNotIn("是否正确附加在尾部", result.stdout)

    def test_digest_short_task_has_no_trailing_ellipsis(self):
        result = run("--digest", "--file", str(self.target))
        lines = [l for l in result.stdout.splitlines() if l.startswith("501｜")]
        self.assertEqual(len(lines), 1)
        self.assertFalse(lines[0].endswith("…"))

    def test_digest_width_flag_changes_truncation_point(self):
        result = run("--digest", "--digest-width", "2", "--file", str(self.target))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("501｜[S:done][D:业]｜短标…", result.stdout)

    def test_digest_width_must_be_positive(self):
        result = run("--digest", "--digest-width", "0", "--file", str(self.target))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("正整数", result.stdout)

    def test_digest_missing_machine_field_shown_as_placeholder_not_silent(self):
        """#502 状态列没有 [S:...] 前缀（模拟 #308 落地前的老行，归档件里
        大量存在）——须显式标 [S:?]，不得留空/跳过/伪造一个状态（同 #308
        「非静默降级」既有原则）。"""
        result = run("--digest", "--file", str(self.target))
        self.assertEqual(result.returncode, 0)
        self.assertIn("502｜[S:?]｜", result.stdout)
        self.assertIn("1 行状态列未识别到", result.stdout)

    def test_digest_rejects_section_four(self):
        result = run("--digest", "--section", "四", "--file", str(self.target))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("仅支持 §一", result.stdout)

    def test_digest_and_row_are_mutually_exclusive(self):
        result = run("--row", "500", "--digest", "--file", str(self.target))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("not allowed", result.stderr)

    def test_neither_row_nor_digest_is_an_error(self):
        result = run("--file", str(self.target))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("required", result.stderr)

    def test_digest_header_reports_source_file_and_row_count(self):
        result = run("--digest", "--file", str(self.target))
        self.assertEqual(result.returncode, 0)
        self.assertIn("合计 3 行", result.stdout)
        self.assertIn(str(self.target), result.stdout)

    def test_concatenating_before_parsing_would_lose_seam_rows(self):
        """反例锁定（队列 #441 实现红线：绝不拼接文本再解析一次）：本用例
        直接构造"两份文件被拼接成一份"的场景——文件 A 末行若没有尾随换行
        （工具生成的文件常见此形态），紧跟文件 B 首行会合并成一条物理行，
        列数从 8 撞成 17，结构性过滤器按预期把它当噪声整行丢弃，两行
        （#800/#801）双双消失，且不报错（正是"静默"两字的体现）。真正
        实现绝不会撞上这个缝——它逐份读取解析后合并，见
        DigestDualFileTests.test_dual_file_digest_survives_the_seam_that_
        concatenation_would_corrupt 用相同两行内容证明这一点。"""
        no_trailing_newline_part = (
            "## §一 任务看板 · A\n\n"
            "| # | 任务 | 领取方 | 输入（指针） | 期望产出 | 状态 | 触碰区 | 登记 |\n"
            "|---|------|--------|-------------|----------|------|--------|------|\n"
            "| 800 | 文件A末行 | CC | 无 | 无 | [S:done][D:机] 已完成 | 无 | 2026-08-01 |"
        )
        next_part_starting_with_pipe = (
            "| 801 | 文件B首行 | CC | 无 | 无 | [S:open][D:机] 待领 | 无 | 2026-08-01 |\n"
        )
        concatenated = no_trailing_newline_part + next_part_starting_with_pipe
        target = Path(self._tmpdir.name) / "拼接撞缝.md"
        target.write_text(concatenated, encoding="utf-8")

        result = run("--digest", "--file", str(target))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertNotIn("800｜", result.stdout)
        self.assertNotIn("801｜", result.stdout)
        self.assertIn("合计 0 行", result.stdout)


# ══════════════════════════════════════════════════════════════════════════
# 队列 §一 #381⑸ⓗ1：--grep 单文件模式（黑盒，--file 指向本用例专属临时文件）
# ══════════════════════════════════════════════════════════════════════════

GREP_FIXTURE = """## 一、任务看板

| # | 任务 | 领取方 | 输入（指针） | 期望产出 | 状态 | 触碰区 | 登记 |
|---|------|--------|-------------|----------|------|--------|------|
| 600 | 任务列直接含编辑锁三个字 | CC | 无 | 无 | [S:open][D:机] 待领 | 无 | 2026-09-01 |
| 601 | 任务列不含关键词 | CC | 无 | 无 | [S:open][D:机] 待领 | `工具-共享文档编辑锁.py` | 2026-09-01 |
| 602 | 两列都不含关键词 | CC | 无 | 无 | [S:open][D:机] 待领 | 无关触碰区 | 2026-09-01 |
| 603 | 任务列含大小写混排OP-0904编号 | CC | 无 | 无 | [S:open][D:机] 待领 | 无 | 2026-09-01 |

## 四、需 Shao Peishen 的动作（例外与拍板）

| # | 事项 | 等谁 | 截止 |
|---|------|------|------|
| 600 | §四也含编辑锁字样，不应混入 §一 digest --grep 结果 | Shao Peishen | 不急 |
"""


class GrepModeTests(unittest.TestCase):
    """队列 §一 #381⑸ⓗ1：`--digest --grep` 单文件模式黑盒用例。"""

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.target = Path(self._tmpdir.name) / "假想队列.md"
        self.target.write_text(GREP_FIXTURE, encoding="utf-8")

    def tearDown(self):
        self._tmpdir.cleanup()

    def test_grep_matches_task_column(self):
        result = run("--digest", "--grep", "编辑锁", "--file", str(self.target))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("600｜", result.stdout)

    def test_grep_matches_touch_zone_column_with_annotation(self):
        """#601 关键词只落在触碰区列——摘要行须附「命中触碰区」提示，
        否则读者对着截断后的任务列摘要找不到命中理由。"""
        result = run("--digest", "--grep", "编辑锁", "--file", str(self.target))
        self.assertEqual(result.returncode, 0)
        line601 = next(l for l in result.stdout.splitlines() if l.startswith("601｜"))
        self.assertIn("命中触碰区", line601)
        self.assertIn("工具-共享文档编辑锁.py", line601)

    def test_grep_task_column_hit_has_no_touch_zone_annotation(self):
        """#600 关键词已在任务列摘要里可见——不应附加多余的触碰区提示。"""
        result = run("--digest", "--grep", "编辑锁", "--file", str(self.target))
        line600 = next(l for l in result.stdout.splitlines() if l.startswith("600｜"))
        self.assertNotIn("命中触碰区", line600)

    def test_grep_excludes_rows_matching_neither_column(self):
        result = run("--digest", "--grep", "编辑锁", "--file", str(self.target))
        self.assertEqual(result.returncode, 0)
        self.assertNotIn("602｜", result.stdout)

    def test_grep_is_case_insensitive(self):
        """本项目关键词常混排中英文/编号（如 `OP-0904`），大小写不一致是
        常见笔误而非有意区分——见模块 docstring ⓗ1 段。"""
        result = run("--digest", "--grep", "op-0904", "--file", str(self.target))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("603｜", result.stdout)

    def test_grep_excludes_section_four_row_with_same_number(self):
        """§四 #600 事项列同样含「编辑锁」——digest 本身即锁定只扫 §一
        （既有边界），--grep 不应绕开这个边界误收 §四 行。"""
        result = run("--digest", "--grep", "编辑锁", "--file", str(self.target))
        self.assertEqual(result.returncode, 0)
        self.assertNotIn("不应混入", result.stdout)

    def test_grep_zero_hits_reports_zero_of_total_not_error(self):
        result = run("--digest", "--grep", "这个关键词绝对不会命中任何一行XYZ",
                      "--file", str(self.target))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("命中 0／4 行", result.stdout)

    def test_grep_header_reports_keyword_and_hit_over_total_count(self):
        result = run("--digest", "--grep", "编辑锁", "--file", str(self.target))
        self.assertIn("关键词「编辑锁」命中 2／4 行", result.stdout)

    def test_grep_without_digest_is_rejected_not_silently_ignored(self):
        """`--grep` 是「在 --digest 摘要基础上过滤」，不是独立模式——配合
        `--row` 传入时必须报错，不能悄悄忽略掉这个参数。"""
        result = run("--row", "600", "--grep", "编辑锁", "--file", str(self.target))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("--digest", result.stdout)

    def test_grep_rejects_blank_keyword(self):
        """空白关键词会让 `needle in cell` 恒真、命中全部行——等于没过滤，
        必须拒绝而非静默当成「不过滤」处理（同 #268「工具静默回退」既有
        戒律）。"""
        result = run("--digest", "--grep", "   ", "--file", str(self.target))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("不得为空白", result.stdout)


MECH_FIXTURE = """## 一、任务看板

| # | 任务 | 领取方 | 输入（指针） | 期望产出 | 状态 | 触碰区 | 登记 |
|---|------|--------|-------------|----------|------|--------|------|
| 200 | 机制文件里的行 | CC | 无 | 无 | [S:open][D:机] 待领 | 无 | 2026-08-11 |

## 二、待 commit 批次（CC 取活销行）

| 批次 | 文件清单 | 说明 | 状态 |
|------|---------|------|------|
"""

BIZ_FIXTURE = """## 一、任务看板

| # | 任务 | 领取方 | 输入（指针） | 期望产出 | 状态 | 触碰区 | 登记 |
|---|------|--------|-------------|----------|------|--------|------|
| 201 | 业务文件里的行 | CC | 无 | 无 | [S:open][D:业] 待领 | 无 | 2026-08-11 |

## 二、待 commit 批次（CC 取活销行）

| 批次 | 文件清单 | 说明 | 状态 |
|------|---------|------|------|
"""


class DualFileQueryTests(unittest.TestCase):
    """队列 #315：不显式传 `--file` 时的双文件联合查询——黑盒真实 git 仓库
    方式（`REPO_ROOT` 按 `--git-common-dir` 解析），同 `EditLockCrossWorktree
    Tests` 惯例，验证子进程实际读取生产相对路径而非依赖进程内 monkeypatch。
    """

    MECH_REL = Path("1-转型规划") / "0-全景路线图" / "跨桌任务队列-机制环境.md"
    BIZ_REL = Path("1-转型规划") / "0-全景路线图" / "跨桌任务队列-业务场景.md"

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.repo_root = Path(self._tmpdir.name)
        subprocess.run(["git", "init", "-q"], cwd=self.repo_root, check=True)
        subprocess.run(["git", "config", "user.email", "test@example.com"],
                        cwd=self.repo_root, check=True)
        subprocess.run(["git", "config", "user.name", "Test"],
                        cwd=self.repo_root, check=True)
        script_dir = self.repo_root / "0-学习与工具"
        script_dir.mkdir()
        (script_dir / "工具-队列查询.py").write_text(
            SCRIPT.read_text(encoding="utf-8"), encoding="utf-8",
        )
        (self.repo_root / self.MECH_REL).parent.mkdir(parents=True)
        (self.repo_root / self.MECH_REL).write_text(MECH_FIXTURE, encoding="utf-8")
        (self.repo_root / self.BIZ_REL).write_text(BIZ_FIXTURE, encoding="utf-8")
        subprocess.run(["git", "add", "-A"], cwd=self.repo_root, check=True)
        subprocess.run(["git", "commit", "-q", "-m", "init"], cwd=self.repo_root, check=True)

    def tearDown(self):
        self._tmpdir.cleanup()

    def _run_in_repo(self, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, str(self.repo_root / "0-学习与工具" / "工具-队列查询.py"), *args],
            cwd=self.repo_root, capture_output=True, text=True, encoding="utf-8",
        )

    def test_finds_row_in_mechanism_file_without_explicit_file_arg(self):
        result = self._run_in_repo("--row", "200", "--section", "一")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("状态＝open", result.stdout)
        self.assertIn(str(self.MECH_REL.name), result.stdout)

    def test_finds_row_in_business_file_without_explicit_file_arg(self):
        result = self._run_in_repo("--row", "201", "--section", "一")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("域 业", result.stdout)
        self.assertIn(str(self.BIZ_REL.name), result.stdout)

    def test_not_found_message_lists_both_files_searched(self):
        result = self._run_in_repo("--row", "99999")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn(str(self.MECH_REL.name), result.stdout)
        self.assertIn(str(self.BIZ_REL.name), result.stdout)


# ══════════════════════════════════════════════════════════════════════════
# 队列 #441：--digest 默认（不传 --file）双文件合并——真实 git 仓库黑盒
# ══════════════════════════════════════════════════════════════════════════

DIGEST_MECH_FIXTURE = """## §一 任务看板 · 机制环境（归档式标题）

| # | 任务 | 领取方 | 输入（指针） | 期望产出 | 状态 | 触碰区 | 登记 |
|---|------|--------|-------------|----------|------|--------|------|
| 700 | 机制文件的行 | CC | 无 | 无 | [S:open][D:机] 待领 | 无 | 2026-08-11 |
| 800 | 文件A末行 | CC | 无 | 无 | [S:done][D:机] 已完成 | 无 | 2026-08-01 |

## 二、待 commit 批次（CC 取活销行）

| 批次 | 文件清单 | 说明 | 状态 |
|------|---------|------|------|
"""

DIGEST_BIZ_FIXTURE = """## §一 任务看板 · 业务场景（归档式标题）

| # | 任务 | 领取方 | 输入（指针） | 期望产出 | 状态 | 触碰区 | 登记 |
|---|------|--------|-------------|----------|------|--------|------|
| 701 | 业务文件的行 | CC | 无 | 无 | [S:open][D:业] 待领 | 无 | 2026-08-11 |
| 801 | 文件B首行 | CC | 无 | 无 | [S:open][D:业] 待领 | 无 | 2026-08-01 |

## 二、待 commit 批次（CC 取活销行）

| 批次 | 文件清单 | 说明 | 状态 |
|------|---------|------|------|
"""


class DigestDualFileTests(unittest.TestCase):
    """队列 #441：--digest 默认（不传 --file）双文件合并——同
    DualFileQueryTests 的真实 git 仓库黑盒方式（子进程实际读取生产相对
    路径，不依赖进程内 monkeypatch）。两份夹具刻意都用归档式标题
    （`## §一 ... ·`，无顿号），一并验证结构性扫描对队列真身与归档件
    一视同仁（队列 #442）。"""

    MECH_REL = Path("1-转型规划") / "0-全景路线图" / "跨桌任务队列-机制环境.md"
    BIZ_REL = Path("1-转型规划") / "0-全景路线图" / "跨桌任务队列-业务场景.md"

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.repo_root = Path(self._tmpdir.name)
        subprocess.run(["git", "init", "-q"], cwd=self.repo_root, check=True)
        subprocess.run(["git", "config", "user.email", "test@example.com"],
                        cwd=self.repo_root, check=True)
        subprocess.run(["git", "config", "user.name", "Test"],
                        cwd=self.repo_root, check=True)
        script_dir = self.repo_root / "0-学习与工具"
        script_dir.mkdir()
        (script_dir / "工具-队列查询.py").write_text(
            SCRIPT.read_text(encoding="utf-8"), encoding="utf-8",
        )
        (self.repo_root / self.MECH_REL).parent.mkdir(parents=True)
        (self.repo_root / self.MECH_REL).write_text(DIGEST_MECH_FIXTURE, encoding="utf-8")
        (self.repo_root / self.BIZ_REL).write_text(DIGEST_BIZ_FIXTURE, encoding="utf-8")
        subprocess.run(["git", "add", "-A"], cwd=self.repo_root, check=True)
        subprocess.run(["git", "commit", "-q", "-m", "init"], cwd=self.repo_root, check=True)

    def tearDown(self):
        self._tmpdir.cleanup()

    def _run_in_repo(self, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, str(self.repo_root / "0-学习与工具" / "工具-队列查询.py"), *args],
            cwd=self.repo_root, capture_output=True, text=True, encoding="utf-8",
        )

    def test_digest_merges_rows_from_both_files_sorted_by_number(self):
        result = self._run_in_repo("--digest")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        lines = [l for l in result.stdout.splitlines() if "｜" in l and not l.startswith("【")]
        ids = [l.split("｜")[0] for l in lines]
        self.assertEqual(ids, ["700", "701", "800", "801"])

    def test_digest_header_reports_per_file_counts(self):
        result = self._run_in_repo("--digest")
        self.assertEqual(result.returncode, 0)
        self.assertIn("合计 4 行", result.stdout)
        self.assertIn(str(self.MECH_REL.name), result.stdout)
        self.assertIn(str(self.BIZ_REL.name), result.stdout)

    def test_dual_file_digest_survives_the_seam_that_concatenation_would_corrupt(self):
        """反例的另一半（配 DigestModeTests.test_concatenating_before_
        parsing_would_lose_seam_rows）：#800（机制文件行）与 #801（业务
        文件行）分别落在两份真实物理文件——真正实现走
        queue_table.iter_queue_paths() 逐份读取解析后合并，两行都应完整
        出现，不因"文件边界"互相影响；对照组已证明若拼接文本再解析，这
        两行会一起消失。"""
        result = self._run_in_repo("--digest")
        self.assertEqual(result.returncode, 0)
        self.assertIn("800｜[S:done][D:机]｜文件A末行", result.stdout)
        self.assertIn("801｜[S:open][D:业]｜文件B首行", result.stdout)

    def test_digest_with_explicit_file_only_queries_that_one_file(self):
        result = self._run_in_repo("--digest", "--file", str(self.MECH_REL))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("合计 2 行", result.stdout)
        self.assertNotIn("701｜", result.stdout)
        self.assertNotIn("801｜", result.stdout)

    def test_grep_merges_hits_from_both_files(self):
        """队列 §一 #381⑸ⓗ1：`--grep` 须「联合两份真身」——不显式传
        `--file` 时，过滤发生在两份文件逐份解析合并之后的 `all_rows` 上，
        四行（分别落在机制/业务两份物理文件）都含「文件」二字，应全部
        命中。"""
        result = self._run_in_repo("--digest", "--grep", "文件")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        for row_id in ("700", "701", "800", "801"):
            self.assertIn(f"{row_id}｜", result.stdout)
        self.assertIn("命中 4／4 行", result.stdout)


if __name__ == "__main__":
    unittest.main()
