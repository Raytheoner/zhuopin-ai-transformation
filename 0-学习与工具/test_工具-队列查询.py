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


if __name__ == "__main__":
    unittest.main()
