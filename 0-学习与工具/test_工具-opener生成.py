"""`工具-opener生成.py` 单测（队列 §一 `#461`，OP-0904-M）。

白盒方式：直接调 `generate_opener` / `OpenerGenError`，不跑子进程、不碰真实仓库文件。

三条反例 ＋ 一条正例，覆盖任务原文列出的验收点：
- 反例①：缺任一必填字段 ⇒ 报错退出、不出件。
- 反例②：`worktree` 写成裸名字（非 ☑／☐ 勾选符号开头）⇒ 报错。
- 反例③：`开工第一件事` 那一行被换成伪代码（非真实工具名 ＋ `"self"` 字面量）⇒ 报错——
  本工具不单独实现一套"像不像伪代码"的判据，而是复用
  `工具-opener块lint.py::check_block` 做拼装结果自检，伪代码天然不含
  `set_session_title` 字面子串，自检的形态①判据即会拦下（不写第二份判据）。
- 正例：按一组完整参数生成 CC 侧 opener，逐字比对 `opener骨架.md`
  （2026-09-04 生效版，唯一可照抄物——`专线opener模板库.md` §〇.00 现仅存指针，
  本文件顶部注释已记录这处时效落差）的骨架结构：六字段顺序、
  `session：新开` 字面出现、`set_session_title` 整行含子任务例外句。
"""
from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().with_name("工具-opener生成.py")


def _load_module():
    spec = importlib.util.spec_from_file_location("_opener_gen_under_test", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


M = _load_module()

#: P7① 撞号查重（`_check_op_id_not_reused`）扫的是 `M.REPO_ROOT / 1-转型规划`。
#: 除 `UsedSuffixDedupTests` 外，本文件其余用例的关注点与撞号无关，不该受真实
#: 仓库当日已出现过哪些编号影响（那会让测试结果随仓库内容漂移）——`setUpModule`
#: 把 `M.REPO_ROOT` 钉死到一个空临时目录，等价于"当日零已用编号"。
_MODULE_TMP_ROOT: tempfile.TemporaryDirectory | None = None


def setUpModule():
    global _MODULE_TMP_ROOT
    _MODULE_TMP_ROOT = tempfile.TemporaryDirectory()
    M.REPO_ROOT = Path(_MODULE_TMP_ROOT.name)


def tearDownModule():
    if _MODULE_TMP_ROOT is not None:
        _MODULE_TMP_ROOT.cleanup()

#: 一组完整合法的 CC 侧参数——各条反例均从这份基线上单独破坏一个字段。
VALID_CC_KWARGS = dict(
    op_id="OP-0905-A",
    env="CC",
    short_name="示例任务",
    branch="demo-slug",
    worktree="☑（demo-wt，新 worktree，收工自删）",
    workspace="无（纯库内，不触碰 `.51`）",
    session="新开",
    line="环境总线",
    input_pointer="1-转型规划/0-全景路线图/示例派单件.md",
    task_class="A",
    do_items=["第一步", "第二步"],
    dont_items=["不做的事"],
)

VALID_COWORK_KWARGS = dict(
    op_id="OP-0905-B",
    env="Cowork",
    short_name="示例二",
    branch="master",
    worktree="☐（不建，只产改 `.md`）",
    workspace="无",
    session="新开",
    line="环境总线",
    input_pointer="1-转型规划/0-全景路线图/示例派单件2.md",
    task_class="B",
)


class MissingFieldTests(unittest.TestCase):
    """反例① —— 十项必填字段任一缺失即报错退出、不出件。"""

    def test_missing_each_required_field_raises(self):
        for field in M.REQUIRED_FIELDS:
            with self.subTest(field=field):
                kwargs = dict(VALID_CC_KWARGS)
                del kwargs[field]
                with self.assertRaises(M.OpenerGenError):
                    M.generate_opener(**kwargs)

    def test_blank_field_treated_as_missing(self):
        """空字符串／纯空白同样判缺失（`_require_all_fields` 用 `.strip()` 判空）。"""
        kwargs = dict(VALID_CC_KWARGS)
        kwargs["line"] = "   "
        with self.assertRaises(M.OpenerGenError):
            M.generate_opener(**kwargs)

    def test_valid_kwargs_do_not_raise(self):
        """基线本身必须是干净的合法输入——否则上面两条反例测的不是"缺字段"这一件事。"""
        M.generate_opener(**VALID_CC_KWARGS)
        M.generate_opener(**VALID_COWORK_KWARGS)


class WorktreeCheckboxTests(unittest.TestCase):
    """反例② —— worktree 写成裸名字（非 ☑／☐ 勾选符号开头）必须报错。"""

    def test_bare_worktree_name_raises(self):
        kwargs = dict(VALID_CC_KWARGS)
        kwargs["worktree"] = "demo-wt"  # 裸名字，没有勾选符号
        with self.assertRaises(M.OpenerGenError) as ctx:
            M.generate_opener(**kwargs)
        self.assertIn("勾选符号", str(ctx.exception))

    def test_checkbox_prefixed_worktree_passes(self):
        kwargs = dict(VALID_CC_KWARGS)
        kwargs["worktree"] = "☑（另一个-wt，新 worktree，收工自删）"
        M.generate_opener(**kwargs)  # 不应抛错


class TitleCallPseudocodeTests(unittest.TestCase):
    """反例③ —— `set_session_title` 写成伪代码（非真实工具名＋`"self"` 字面量）必须报错。"""

    def test_pseudocode_title_call_raises(self):
        kwargs = dict(VALID_CC_KWARGS)
        kwargs["title_call_override"] = "开工第一件事：调用改名工具，把标题设为示例任务。"
        with self.assertRaises(M.OpenerGenError) as ctx:
            M.generate_opener(**kwargs)
        # 断言拦下的正是复用的 check_block 形态①（不是本模块另起的第二套判据）
        self.assertIn("check_block", str(ctx.exception))
        self.assertIn("set_session_title", str(ctx.exception))

    def test_title_call_missing_subtask_exception_raises(self):
        """伪代码之外的另一种破坏：有真实工具名但删掉了子任务例外句 —— 同样该被拦（形态②）。"""
        kwargs = dict(VALID_CC_KWARGS)
        kwargs["title_call_override"] = (
            '开工第一件事：调 mcp__ccd_session_mgmt__set_session_title'
            '（session_id 传字面量 "self"），标题：[Win]0905A-示例任务。'
        )
        with self.assertRaises(M.OpenerGenError) as ctx:
            M.generate_opener(**kwargs)
        self.assertIn("check_block", str(ctx.exception))

    def test_real_tool_call_with_exception_passes(self):
        kwargs = dict(VALID_CC_KWARGS)
        kwargs["title_call_override"] = M._title_call_line(
            kwargs["op_id"], kwargs["short_name"])
        M.generate_opener(**kwargs)  # 不应抛错


class PositiveGenerationTests(unittest.TestCase):
    """正例 —— 完整参数生成 CC opener，逐字比对 `opener骨架.md` 骨架结构。"""

    def setUp(self):
        self.out = M.generate_opener(**VALID_CC_KWARGS)

    def test_wrapped_in_fence(self):
        self.assertTrue(self.out.startswith("```\n"))
        self.assertTrue(self.out.endswith("\n```"))

    def test_first_line_matches_title_convention(self):
        first_line = self.out.splitlines()[1]  # 0 号行是围栏 ```
        self.assertEqual(first_line, "[OP-0905-A]【CC】示例任务")

    def test_six_fields_present_in_order(self):
        """六字段顺序固定：执行环境｜分支｜worktree｜工作区｜session｜派出线（骨架硬规则）。"""
        settings_line = [ln for ln in self.out.splitlines() if ln.startswith("【设置】")][0]
        order = ("执行环境", "分支", "worktree", "工作区", "session", "派出线")
        positions = [settings_line.find(field) for field in order]
        self.assertTrue(all(p != -1 for p in positions), f"六字段有缺失：{settings_line}")
        self.assertEqual(positions, sorted(positions), f"六字段顺序颠倒：{settings_line}")

    def test_session_literal_xinkai_appears(self):
        self.assertIn("session：新开", self.out)

    def test_title_call_line_has_real_tool_and_self_literal(self):
        self.assertIn(
            'mcp__ccd_session_mgmt__set_session_title（session_id 传字面量 "self"）', self.out)

    def test_title_call_line_has_subtask_exception_clause(self):
        self.assertIn("子任务", self.out)
        self.assertIn("例外", self.out)
        self.assertIn(M.SUBTASK_EXCEPTION, self.out)

    def test_output_passes_lint_check_block_with_zero_problems(self):
        """产出本身必须让 `工具-opener块lint.py::check_block` 判零违规——同一份判据两处都用。"""
        lint = M._load_lint_module()
        blocks = lint.iter_fenced_blocks(self.out)
        self.assertEqual(len(blocks), 1)
        self.assertEqual(lint.check_block(blocks[0]), [])

    def test_cowork_output_also_passes_lint(self):
        out = M.generate_opener(**VALID_COWORK_KWARGS)
        lint = M._load_lint_module()
        blocks = lint.iter_fenced_blocks(out)
        self.assertEqual(lint.check_block(blocks[0]), [])
        self.assertIn("session：新开", out)
        self.assertIn("收工：产出登记 §二 待 commit 批次", out)


class ValidationEdgeCaseTests(unittest.TestCase):
    """骨架硬规则的其余边界——短名长度、编号格式、session 字面值、Cowork 分支固定。"""

    def test_short_name_over_12_chars_raises(self):
        kwargs = dict(VALID_CC_KWARGS)
        kwargs["short_name"] = "一二三四五六七八九十一二三"  # 13 字
        with self.assertRaises(M.OpenerGenError):
            M.generate_opener(**kwargs)

    def test_malformed_op_id_raises(self):
        kwargs = dict(VALID_CC_KWARGS)
        kwargs["op_id"] = "OP-905-A"  # 月日缺一位
        with self.assertRaises(M.OpenerGenError):
            M.generate_opener(**kwargs)

    def test_session_value_other_than_xinkai_raises(self):
        kwargs = dict(VALID_CC_KWARGS)
        kwargs["session"] = "沿用当前"
        with self.assertRaises(M.OpenerGenError):
            M.generate_opener(**kwargs)

    def test_cowork_branch_must_be_master(self):
        kwargs = dict(VALID_COWORK_KWARGS)
        kwargs["branch"] = "some-slug"
        with self.assertRaises(M.OpenerGenError):
            M.generate_opener(**kwargs)

    def test_windows_absolute_path_input_pointer_raises(self):
        kwargs = dict(VALID_CC_KWARGS)
        kwargs["input_pointer"] = r"C:\Dev\zhuopin-ai\1-转型规划\0-全景路线图\示例派单件.md"
        with self.assertRaises(M.OpenerGenError):
            M.generate_opener(**kwargs)


class UsedSuffixDedupTests(unittest.TestCase):
    """P7①（构建环境瘦身第三轮方案 P7；队列 §一 `#487`）—— 当日撞号即拒，
    报下一个空号；三条覆盖计划原文明写的验收点：撞号拒／空号放行／短形
    `MMDDX` 也算已用。"""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        (self.root / "1-转型规划" / "0-全景路线图").mkdir(parents=True)
        self._orig_repo_root = M.REPO_ROOT
        M.REPO_ROOT = self.root

    def tearDown(self):
        M.REPO_ROOT = self._orig_repo_root
        self._tmp.cleanup()

    def _write(self, name: str, content: str) -> None:
        (self.root / "1-转型规划" / "0-全景路线图" / name).write_text(content, encoding="utf-8")

    def test_full_form_collision_rejected_with_next_free_suffix(self):
        self._write("看护件.md", "已用编号 OP-0905-A 出现在正文里。")
        kwargs = dict(VALID_CC_KWARGS)
        kwargs["op_id"] = "OP-0905-A"
        with self.assertRaises(M.OpenerGenError) as ctx:
            M.generate_opener(**kwargs)
        self.assertIn("撞号", str(ctx.exception))
        self.assertIn("OP-0905-B", str(ctx.exception))  # A 已用，下一个空号是 B

    def test_unused_op_id_passes(self):
        self._write("看护件.md", "已用编号 OP-0905-A 出现在正文里。")
        kwargs = dict(VALID_CC_KWARGS)
        kwargs["op_id"] = "OP-0905-Z"  # Z 全天未用
        M.generate_opener(**kwargs)  # 不应抛错

    def test_short_form_session_title_also_counts_as_used(self):
        # 短形只认 `[Win]MMDDX-` 锚点（骨架「短形只用于 session 名」），全文没有
        # 任何 `OP-0905-C` 全称，仅有一行短形 session 标题——同样必须命中撞号。
        self._write("看护件.md", "标题：[Win]0905C-看护批次。正文其余无编号字样。")
        kwargs = dict(VALID_CC_KWARGS)
        kwargs["op_id"] = "OP-0905-C"
        with self.assertRaises(M.OpenerGenError) as ctx:
            M.generate_opener(**kwargs)
        self.assertIn("撞号", str(ctx.exception))

    def test_bare_digits_without_win_anchor_do_not_count_as_short_form(self):
        # 骨架明写「短形 MMDDX 只用于 session 名」——裸数字巧合（无 `[Win]` 锚点）
        # 不该被误判为已用，否则正文任何提到日期的地方都会造成假撞号。
        self._write("看护件.md", "0905D 只是正文里的一个巧合数字串，不是 session 标题。")
        kwargs = dict(VALID_CC_KWARGS)
        kwargs["op_id"] = "OP-0905-D"
        M.generate_opener(**kwargs)  # 不应抛错

    def test_different_date_same_suffix_does_not_collide(self):
        self._write("看护件.md", "OP-0904-A 是昨天的编号。")
        kwargs = dict(VALID_CC_KWARGS)
        kwargs["op_id"] = "OP-0905-A"  # 今天的 A，昨天的 A 不冲突
        M.generate_opener(**kwargs)  # 不应抛错

    def test_next_free_suffix_skips_multiple_used_letters(self):
        used = {"A", "B", "C"}
        self.assertEqual(M._next_free_suffix(used), "D")


class VariantSubtaskLaneTests(unittest.TestCase):
    """P4（同方案 P4）—— `variant="subtask_lane"` 不放 set_session_title 行，
    且无条件追加并行上限/错峰、push 不 ff 两条默认口径。"""

    def setUp(self):
        kwargs = dict(VALID_CC_KWARGS)
        kwargs["variant"] = "subtask_lane"
        kwargs["op_id"] = "OP-0905-VS"  # 骨架首行/标题正则只认字母后缀，不能用 V1
        self.out = M.generate_opener(**kwargs)

    def test_no_session_title_line(self):
        self.assertNotIn("set_session_title", self.out)

    def test_default_parallel_and_push_notes_present(self):
        self.assertIn(M.SUBTASK_PARALLEL_NOTE, self.out)
        self.assertIn(M.SUBTASK_PUSH_NOTE, self.out)

    def test_passes_lint_as_subtask_lane_form6_not_triggered(self):
        lint = M._load_lint_module()
        blocks = lint.iter_fenced_blocks(self.out)
        self.assertEqual(len(blocks), 1)
        problems = lint.check_block(blocks[0], is_subtask_lane=True)
        self.assertEqual(problems, [])

    def test_would_fail_form1_if_lint_run_without_subtask_flag(self):
        # 反向用例：证明"不报 F1"确实来自 `is_subtask_lane=True`，不是巧合。
        lint = M._load_lint_module()
        blocks = lint.iter_fenced_blocks(self.out)
        problems = lint.check_block(blocks[0], is_subtask_lane=False)
        codes = [p[0] for p in problems]
        self.assertIn("F1", codes)

    def test_cowork_env_rejects_subtask_lane_variant(self):
        kwargs = dict(VALID_COWORK_KWARGS)
        kwargs["variant"] = "subtask_lane"
        with self.assertRaises(M.OpenerGenError):
            M.generate_opener(**kwargs)


class VariantGuardianTests(unittest.TestCase):
    """P4 —— `variant="guardian"`（§三bis 看护者开场词）含 set_session_title，
    首行为「看护<短名>」，同样追加 P4 默认口径（讲给看护者听）。"""

    def setUp(self):
        self.kwargs = dict(
            op_id="OP-0905-VG", env="CC", variant="guardian", short_name="示例批",
            branch="master（看护者本身不建分支，不改代码）",
            worktree="☐（看护者不建，各子泳道自建）",
            workspace="无", session="新开", line="环境总线",
            input_pointer="1-转型规划/0-全景路线图/看护件-示例.md", task_class="A",
        )
        self.out = M.generate_opener(**self.kwargs)

    def test_first_line_is_guardian_label(self):
        first_line = self.out.splitlines()[1]
        self.assertEqual(first_line, "[OP-0905-VG]【CC】看护示例批")

    def test_has_session_title_with_guardian_label(self):
        self.assertIn("set_session_title", self.out)
        self.assertIn("[Win]0905VG-看护示例批", self.out)

    def test_default_note_present(self):
        self.assertIn(M.GUARDIAN_PARALLEL_NOTE, self.out)

    def test_passes_lint_check_block(self):
        lint = M._load_lint_module()
        blocks = lint.iter_fenced_blocks(self.out)
        self.assertEqual(lint.check_block(blocks[0]), [])

    def test_short_name_plus_guardian_prefix_over_12_chars_raises(self):
        kwargs = dict(self.kwargs)
        kwargs["short_name"] = "一二三四五六七八九十一"  # 11 字 + "看护" 2 字 = 13
        with self.assertRaises(M.OpenerGenError):
            M.generate_opener(**kwargs)

    def test_guardian_branch_not_forced_into_slug_template(self):
        # 分支字段须原样透传（固定字面量），不会被套上标准变体的
        # "从 master 起 claude/opMMDDx-<slug>" 拼装模板。
        self.assertIn("master（看护者本身不建分支，不改代码）", self.out)
        self.assertNotIn("从 master 起 `claude/", self.out)


if __name__ == "__main__":
    unittest.main()
