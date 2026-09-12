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
import json
import tempfile
import unittest
from datetime import timedelta
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
    # 取号即声明（队列 §一 `#549` ⑶）：占位台账同样钉到临时目录——否则单测会往主工作区
    # `reports/op-id-claims.jsonl` 写真占位，把当日真实取号挡掉两小时。
    M.CLAIMS_FILE = Path(_MODULE_TMP_ROOT.name) / "op-id-claims.jsonl"


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
    # 队列 §一 `#565`：subtask_lane 变体的心跳收工句要 `--batch`，从本字段现取 `B-MMDD_…`。
    line="环境总线（批 B-1231_示例批）",
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
        # 本类断言「下一个空号」，而空号推荐会避开未过期占位——用独立台账，
        # 不受同文件其它用例已写下的占位影响（顺序相关的假红）。
        self._orig_claims = M.CLAIMS_FILE
        M.CLAIMS_FILE = self.root / "op-id-claims.jsonl"

    def tearDown(self):
        M.REPO_ROOT = self._orig_repo_root
        M.CLAIMS_FILE = self._orig_claims
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
        self.assertIn(M.SUBTASK_SENTINEL_NOTE, self.out)   # 队列 §一 `#550`

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


class CoworkDontItemsTests(unittest.TestCase):
    """`--dont` 在 `--env Cowork` 下的去向（队列 §一 `#487` 子项／`OP-0906-I`，方案(甲)）。

    🔴 **修前形态**：Cowork 分支的 `body_lines` 压根不拼「不做什么」段，`--dont`
    传进来**既不出现在成品里、也不报错**——起草者以为硬约束传达到了（2026-09-06
    实撞一次，三条约束靠接力卡侥幸兜住）。判据：**一个参数被接受却不生效，
    比它被拒绝更危险。**
    """

    def test_cowork_dont_items_出现在成品里(self):
        out = M.generate_opener(**{**VALID_COWORK_KWARGS,
                                   "dont_items": ["不动销售域", "不催任何专员"]})
        self.assertIn("不做什么：", out)
        self.assertIn("- 不动销售域", out)
        self.assertIn("- 不催任何专员", out)

    def test_cowork_不做什么段排在收工段之前(self):
        out = M.generate_opener(**{**VALID_COWORK_KWARGS, "dont_items": ["不动销售域"]})
        self.assertLess(out.index("不做什么："), out.index("收工：产出登记 §二"))
        self.assertLess(out.index("做什么："), out.index("不做什么："))

    def test_cowork_未传dont时仍出段占位_不违反形态七(self):
        """未传 `--dont` ⇒ `OpenerSpec` 默认 `["…"]`，段仍在（占位），
        故形态⑦（有做什么段必须配不做什么段）恒不命中。"""
        out = M.generate_opener(**VALID_COWORK_KWARGS)
        self.assertIn("不做什么：", out)
        lint = M._load_lint_module()
        blocks = lint.iter_fenced_blocks(out)
        self.assertEqual(lint.check_block(blocks[0]), [])

    def test_cowork_带dont的成品仍过lint零违规(self):
        out = M.generate_opener(**{**VALID_COWORK_KWARGS, "dont_items": ["不动销售域"]})
        lint = M._load_lint_module()
        blocks = lint.iter_fenced_blocks(out)
        self.assertEqual(lint.check_block(blocks[0]), [])


class SilentlyDroppedBodyParamTests(unittest.TestCase):
    """`--do`／`--dont` 传给「不会拼它们」的环境×变体组合 ⇒ fail-loud 报错退出
    （队列 §一 `#487` 子项／`OP-0906-M`，**精简版(乙)**）。

    🔴 **本类只守 `--variant guardian` 一个组合**：Cowork 那个洞由方案(甲) 补段
    让 `--dont` 真的生效（见 `CoworkDontItemsTests`），**不由本守卫拦**——两者
    同落会互相打架（Shao Peishen 2026-09-06 裁 (c)：Cowork 走补段、guardian 走
    fail-loud）。guardian 的洞补段补不掉：§三bis 看护者开场词是固定形态，
    看护者的任务正本在看护件全文里。
    """

    #: guardian 变体夹具（模块级没有共享的，同 VariantGuardianTests 自建一份）。
    GUARDIAN_KWARGS = dict(
        op_id="OP-0905-VG", env="CC", variant="guardian", short_name="示例批",
        branch="master（看护者本身不建分支，不改代码）",
        worktree="☐（看护者不建，各子泳道自建）",
        workspace="无", session="新开", line="环境总线",
        input_pointer="1-转型规划/0-全景路线图/看护件-示例.md", task_class="A",
    )

    def test_guardian_传do或dont均报错(self):
        """§三bis 看护者开场词正文既不拼 do 也不拼 dont——同族静默丢弃，一并守。"""
        for key, flag in (("do_items", "--do"), ("dont_items", "--dont")):
            with self.subTest(key=key):
                with self.assertRaises(M.OpenerGenError) as cm:
                    M.generate_opener(**{**self.GUARDIAN_KWARGS, key: ["随便一条"]})
                msg = str(cm.exception)
                self.assertIn(flag, msg)
                # 只报错不给出路 ⇒ 调用方会把约束塞进另一个参数的尾巴，形态更糟。
                self.assertIn("看护件", msg)

    def test_guardian_不传两者_照常出件(self):
        """🔴 回归防线：守卫只认「显式传了内容」，`OpenerSpec` 的 `["…"]` 兜底
        不算传——否则每一次正常的看护者出件都会被自己的守卫拦死。"""
        M.generate_opener(**self.GUARDIAN_KWARGS)

    def test_guardian_传空列表不算传(self):
        M.generate_opener(**{**self.GUARDIAN_KWARGS, "dont_items": [], "do_items": []})

    def test_cowork_传dont_不再被守卫拦(self):
        """🔴 与方案(甲) 的接缝：Cowork+dont 必须**正常出件**，且约束真的进成品。
        本条钉死「不要把乙对 --env Cowork 的拦截一并落地」这个交付约束。"""
        out = M.generate_opener(**{**VALID_COWORK_KWARGS, "dont_items": ["不动销售域"]})
        self.assertIn("- 不动销售域", out)
        self.assertEqual(
            M.BODY_PARAM_SUPPORT[("Cowork", "standard")], {"do_items", "dont_items"})

    def test_cc_standard_两个都传_照常出件(self):
        out = M.generate_opener(**{**VALID_CC_KWARGS,
                                   "do_items": ["建造"], "dont_items": ["不动产线"]})
        self.assertIn("1. 建造", out)
        self.assertIn("- 不动产线", out)

    def test_cc_subtask_lane_两个都传_照常出件(self):
        out = M.generate_opener(**{**VALID_CC_KWARGS, "variant": "subtask_lane",
                                   "do_items": ["建造"], "dont_items": ["不动产线"]})
        self.assertIn("- 不动产线", out)

    def test_cli层_guardian带dont_退出码1且写stderr(self):
        """端到端：CLI 是实际被人敲的那一层，退出码与 stderr 都要对。"""
        import io as _io
        import contextlib
        argv = [
            "--op-id", "OP-1231-Z", "--env", "CC", "--variant", "guardian",
            "--short-name", "示例批",
            "--branch", "master（看护者本身不建分支，不改代码）",
            "--worktree", "☐（看护者不建，各子泳道自建）",
            "--workspace", "无", "--session", "新开", "--line", "环境总线",
            "--input-pointer", "1-转型规划/0-全景路线图/看护件-示例.md", "--task-class", "A",
            "--dont", "不动销售域",
        ]
        err = _io.StringIO()
        with contextlib.redirect_stderr(err):
            code = M.main(argv)
        self.assertEqual(code, 1)
        self.assertIn("--dont", err.getvalue())

    def test_白名单未登记的组合_fail_closed(self):
        """🔴 白名单哲学的验收：假想一个未登记的组合，守卫应**全拒**（fail-closed），
        而不是回落成「什么都放行」（fail-open ＝ 回到静默丢弃）。"""
        saved = dict(M.BODY_PARAM_SUPPORT)
        try:
            M.BODY_PARAM_SUPPORT.pop(("CC", "standard"))
            with self.assertRaises(M.OpenerGenError):
                M.generate_opener(**{**VALID_CC_KWARGS, "do_items": ["建造"]})
        finally:
            M.BODY_PARAM_SUPPORT.clear()
            M.BODY_PARAM_SUPPORT.update(saved)


class 引用版变体(unittest.TestCase):
    """队列 §一 `#489` 步骤 5（Shao Peishen 2026-09-08 答 1a）：`--variant reference`。

    立项理由＝**规则退休制**：`#284` 那条「聊天里给他的开场词一律引用版、禁手抄」
    是**人守**，2026-09-08 已计到第三犯 ⇒ 退休制要求二选一（机制化或删除）。
    本变体是「机制化」那一半——手抄四行会漏 `【设置】` 某一字段或写错标题占位符，
    拼装 ＋ `check_block` 自检不会漏。
    """

    BASE = dict(
        op_id="OP-0908-Z", env="CC", short_name="引用版试跑", branch="ref-demo",
        worktree="☑（demo-wt，新 worktree，收工自删）", workspace="无",
        session="新开", line="环境总线 OP-0907-AL", task_class="A",
        input_pointer="1-转型规划/0-全景路线图/示例派单件.md",
        variant="reference",
    )

    #: 🔴 golden 对照：逐字钉死四行形态。改动它必须是**有意改格式**，
    #: 不能是「顺手动了拼装逻辑、golden 跟着改一下让测试变绿」。
    GOLDEN_CC = (
        "```\n"
        "[OP-0908-Z]【CC】引用版试跑\n"
        "【设置】执行环境：CC ｜ 分支：master（从 master 起 `claude/op0908z-ref-demo`）"
        " ｜ worktree：☑（demo-wt，新 worktree，收工自删） ｜ 工作区：无 ｜ "
        "session：新开 ｜ 派出线：环境总线 OP-0907-AL\n"
        "开工第一件事：调 mcp__ccd_session_mgmt__set_session_title（session_id 传字面量 "
        '"self"），标题：[Win]0908Z-引用版试跑。' + M.SUBTASK_EXCEPTION + "\n"
        "读 `1-转型规划/0-全景路线图/示例派单件.md` 全文＋ `CLAUDE.md` 恢复上下文，"
        "按该件执行。本件为 A 类。\n"
        "```"
    )

    GOLDEN_COWORK = (
        "```\n"
        "[OP-0908-Y]【Cowork】引用版Cowork\n"
        "【设置】执行环境：Cowork ｜ 分支：master ｜ worktree：☐（不建，只产改 `.md`）"
        " ｜ 工作区：无 ｜ session：新开 ｜ 派出线：环境总线\n"
        "读 `1-转型规划/0-全景路线图/示例派单件.md` 全文＋ `CLAUDE.md` 恢复上下文，"
        "按该件执行。本件为 B 类。\n"
        "```"
    )

    def _gen(self, **over):
        return M.generate_opener(**{**self.BASE, **over})

    def test_golden_CC四行(self):
        self.assertEqual(self._gen(), self.GOLDEN_CC)

    def test_golden_Cowork三行_无title调用(self):
        """🔴 Cowork 侧**不放** `set_session_title`：那个工具在 Cowork 桌根本不存在
        （2026-08-27 补充一实测），放了就是教人写一个不存在的调用。"""
        out = self._gen(op_id="OP-0908-Y", env="Cowork", short_name="引用版Cowork",
                        branch="master", worktree="☐（不建，只产改 `.md`）",
                        line="环境总线", task_class="B")
        self.assertEqual(out, self.GOLDEN_COWORK)
        self.assertNotIn("set_session_title", out)

    def test_引用版自身过lint(self):
        """产出必须自己先过自己定的门——`generate_opener` 内已跑 `check_block`，
        这里再从外部独立跑一次，防止内部自检哪天被绕过。"""
        lint = M._load_lint_module()
        for out in (self._gen(),
                    self._gen(op_id="OP-0908-Y", env="Cowork", short_name="引用版Cowork",
                              branch="master", worktree="☐（不建）", line="L",
                              task_class="B")):
            block = lint.iter_fenced_blocks(out)[0]
            self.assertEqual(lint.check_block(block), [])

    def test_正文段一个都不拼(self):
        """引用版只出四行——正文在派单件里。多一段就等于把 >500 字又搬回聊天。"""
        out = self._gen()
        self.assertNotIn("做什么：", out)
        self.assertNotIn("不做什么：", out)
        self.assertEqual(len(out.strip().splitlines()), 6)   # 上下围栏 ＋ 四行

    # ── fail-loud 四条（`_resolve_input_pointer`）────────────────
    def _cli(self, argv) -> tuple[int, str]:
        import contextlib
        import io as _io
        err = _io.StringIO()
        with contextlib.redirect_stderr(err), contextlib.redirect_stdout(_io.StringIO()):
            code = M.main(argv)
        return code, err.getvalue()

    _CLI_COMMON = [
        "--env", "CC", "--short-name", "试", "--branch", "d",
        "--worktree", "☑（x）", "--workspace", "无", "--session", "新开",
        "--line", "L", "--task-class", "A",
    ]

    def test_do和dont传入即fail_loud(self):
        """🔴 正文参数在本变体下不会被拼进成品 ⇒ 必须报错，不许静默丢弃。"""
        for flag in ("--do", "--dont"):
            with self.subTest(flag=flag):
                with self.assertRaises(M.OpenerGenError):
                    self._gen(**{"do_items" if flag == "--do" else "dont_items": ["某事"]})

    def test_缺ref_file报错(self):
        code, err = self._cli(["--variant", "reference", "--op-id", "OP-0908-W"]
                              + self._CLI_COMMON)
        self.assertEqual(code, 1)
        self.assertIn("--ref-file", err)

    def test_非reference传ref_file报错(self):
        """🔴 参数被接受却不生效，比被拒绝更危险（`#487` 子项付过的学费）。"""
        code, err = self._cli(["--variant", "standard", "--op-id", "OP-0908-V",
                               "--ref-file", "a/b.md", "--do", "x", "--dont", "y"]
                              + self._CLI_COMMON)
        self.assertEqual(code, 1)
        self.assertIn("--ref-file", err)

    def test_ref_file与input_pointer冲突报错(self):
        code, err = self._cli(["--variant", "reference", "--op-id", "OP-0908-U",
                               "--ref-file", "a/b.md", "--input-pointer", "c/d.md"]
                              + self._CLI_COMMON)
        self.assertEqual(code, 1)
        self.assertIn("不得给出不同的值", err)

    def test_非reference缺input_pointer仍报错(self):
        """原 argparse `required=True` 的等价物——改成解析后校验不得把这条漏掉。"""
        code, err = self._cli(["--variant", "standard", "--op-id", "OP-0908-T",
                               "--do", "x", "--dont", "y"] + self._CLI_COMMON)
        self.assertEqual(code, 1)
        self.assertIn("--input-pointer", err)


class 子任务泳道占位段(unittest.TestCase):
    """队列 §一 `#487` 追记⑴（2026-09-09 apply）——`--variant subtask_lane` 未传
    `--do`／`--dont` 时**不得**硬塞「做什么：1. …／不做什么：- …」两段占位。

    🔴 **判据来源是骨架，不是本工具**：`opener骨架.md`【CC · 子任务泳道】节明写
    「本变体正文恒为三行，不多写一行」——做什么／不做什么／收工一律写进**队列行**。
    🔴 **与既有子项同源而镜像**：既有子项是「一个参数被接受却不生效」（`--dont` 在
    `--env Cowork` 下静默丢弃），这一处是「**一个参数没传却仍产出内容**」；根因同为
    生成器与格式正本各自演进、其间此前无机器守。
    """

    @staticmethod
    def _gen(**over):
        kw = {k: v for k, v in VALID_CC_KWARGS.items()
              if k not in ("do_items", "dont_items")}
        kw.update({"variant": "subtask_lane", "op_id": "OP-1231-A"})
        kw.update(over)
        return M.generate_opener(**kw)

    def test_未传do_dont时不出正文两段(self):
        out = self._gen()
        self.assertNotIn("做什么：", out)      # 「不做什么：」含「做什么：」，一并覆盖
        self.assertNotIn("1. …", out)
        self.assertNotIn("- …", out)

    def test_未传时正文恰为三行加四条机器口径(self):
        """三行正文 ＋ P4 两条 ＋ 心跳一条（队列 §一 `#565`，2026-09-12 有意扩入）＋
        收工哨兵一条（队列 §一 `#550`，2026-09-10 有意扩入）。"""
        body = [ln for ln in self._gen().splitlines() if not ln.startswith("```")]
        self.assertEqual(len(body), 7, f"实为 {len(body)} 行：{body}")
        self.assertEqual(body[-4:], [M.SUBTASK_PARALLEL_NOTE,
                                     M.subtask_heartbeat_note("op1231a-demo-slug", "B-1231_示例批"),
                                     M.SUBTASK_PUSH_NOTE, M.SUBTASK_SENTINEL_NOTE])

    def test_传了do_dont仍照拼_不误伤显式调用(self):
        """`BODY_PARAM_SUPPORT` 登记本组合两个都支持——调用方明确要写就不拦。"""
        out = self._gen(do_items=["建造"], dont_items=["不动产线"])
        self.assertIn("做什么：", out)
        self.assertIn("1. 建造", out)
        self.assertIn("不做什么：", out)
        self.assertIn("- 不动产线", out)

    def test_半填即fail_loud_不出半成品(self):
        """反向用例：**只传 `--do`** ⇒ `不做什么` 段会留着 `- …` 未替换。
        此时不该「照出件」——生成器自检复用 `check_block`，形态⑧ 当场把它拦下，
        调用方看到的是报错而不是一份看着正常、其实没填完的 opener。
        🔑 这条同时证明**闸真的接在生成器上**（不是只在全库扫描时才生效）。"""
        with self.assertRaises(M.OpenerGenError) as cm:
            self._gen(do_items=["建造"])
        msg = str(cm.exception)
        self.assertIn("F8", msg)
        self.assertIn("未替换的正文占位条目", msg)

    def test_标准变体不受本条影响(self):
        """收窄证明：本改动只动 subtask_lane 分支，standard 的占位段是明示设计。"""
        kw = {k: v for k, v in VALID_CC_KWARGS.items()
              if k not in ("do_items", "dont_items")}
        out = M.generate_opener(**{**kw, "op_id": "OP-1231-B"})
        self.assertIn("做什么：", out)
        self.assertIn("1. …", out)


class 分支slug前缀重复(unittest.TestCase):
    """队列 §一 `#487` 追记⑵（2026-09-09 apply）——`--branch` 传含 OP 短号的全名
    会拼出 `claude/op1231c-op0909b-docx-481`。

    🔴 **这条原本不是 bug 是用法**，但 `--help` 只写「短横线 slug」、没写「勿含 OP
    短号」，按直觉传全名必踩，且成品是一个**看起来正常的分支名、不报错**——
    与本行既有子项同族（**错得无声**）。故按 fail-loud 显式化。
    """

    @staticmethod
    def _gen(branch, op_id="OP-1231-C"):
        return M.generate_opener(**{**VALID_CC_KWARGS, "op_id": op_id, "branch": branch})

    def test_含op短号的slug被拒(self):
        with self.assertRaises(M.OpenerGenError) as cm:
            self._gen("op0909b-docx-481")
        msg = str(cm.exception)
        self.assertIn("--branch", msg)
        self.assertIn("op0909b-docx-481", msg)
        self.assertIn("docx-481", msg)          # 报错须给出「应传什么」

    def test_报错信息给出拼坏后的分支名(self):
        with self.assertRaises(M.OpenerGenError) as cm:
            self._gen("op0909b-docx-481")
        self.assertIn("claude/op1231c-op0909b-docx-481", str(cm.exception))

    def test_无字母后缀的短号同样被拒(self):
        with self.assertRaises(M.OpenerGenError):
            self._gen("op0909-docx", op_id="OP-1231-D")

    def test_正常slug不误伤(self):
        """`\\d{4}` 要四个真数字 ⇒ 这些真实 slug 一个都不该被拦。"""
        for slug in ("opener-gen", "ops-fix", "op-0909-x", "dont-guard-487",
                     "openspec-apply"):
            with self.subTest(slug=slug):
                self._gen(slug, op_id="OP-1231-E")   # 不抛即通过

    def test_guardian变体不受约束(self):
        """guardian 的分支字段是骨架 §三bis 固定字面量，不是 slug。"""
        M.generate_opener(**{
            **VALID_CC_KWARGS, "op_id": "OP-1231-F", "variant": "guardian",
            "short_name": "示例批", "branch": "master（看护者本身不建分支，不改代码）",
            "worktree": "☐（看护者不建，各子泳道自建）",
            "do_items": None, "dont_items": None,
        })

    def test_help文本写明勿含op短号(self):
        help_text = M._build_arg_parser().format_help()
        self.assertIn("勿再含", help_text)
        self.assertIn("opNNNN", help_text)


class 骨架与生成器契约(unittest.TestCase):
    """🔑 **本类就是队列 §一 `#487` 判据里那道闸**：此前**格式正本与生成器之间没有
    机器守**，全靠人每次肉眼比对——两处口径各自演进，2026-09-06（`--dont` 静默丢弃）
    与 2026-09-09（子任务泳道硬塞占位）已各出一例，不建闸必有第三例。

    🔴 **闸的做法是「从正本现读，不在测试里抄第二份」**：本类的期望值全部现读
    `opener骨架.md`【CC · 子任务泳道】那一节；正本改了而生成器没跟（或反过来），
    本类当场红。测试里若把骨架内容硬抄一遍，就又造出了第三份会漂的判据。
    """

    SECTION_HEADING = "## 【CC · 子任务泳道】骨架"

    @classmethod
    def setUpClass(cls):
        text = M.SKELETON_FILE.read_text(encoding="utf-8")
        start = text.index(cls.SECTION_HEADING)
        nxt = text.index("\n## ", start + 1)
        cls.section = text[start:nxt]
        lint = M._load_lint_module()
        blocks = lint.iter_fenced_blocks(cls.section)
        assert len(blocks) == 1, f"该节应恰有 1 个围栏块，实为 {len(blocks)}"
        cls.canon_lines = [ln for ln in blocks[0].lines if ln.strip()]
        kw = {k: v for k, v in VALID_CC_KWARGS.items()
              if k not in ("do_items", "dont_items")}
        kw.update({"variant": "subtask_lane", "op_id": "OP-1231-G"})
        out = M.generate_opener(**kw)
        cls.gen_lines = [ln for ln in out.splitlines()
                         if ln.strip() and not ln.startswith("```")]

    def test_正本仍写着恒为三行那条硬规则(self):
        """规则本身被删/改写 ⇒ 本用例红，逼人看一眼，而不是让闸静默失效。"""
        self.assertIn("正文恒为三行，不多写一行", self.section)
        self.assertIn("做什么／不做什么／收工", self.section)

    def test_行数与正本一致(self):
        self.assertEqual(len(self.gen_lines), len(self.canon_lines),
                         f"正本 {len(self.canon_lines)} 行 ／ 生成器 "
                         f"{len(self.gen_lines)} 行：\n正本={self.canon_lines}\n"
                         f"生成器={self.gen_lines}")

    def test_正本与生成器都不含做什么段(self):
        for label, lines in (("正本", self.canon_lines), ("生成器", self.gen_lines)):
            with self.subTest(来源=label):
                self.assertFalse([ln for ln in lines if "做什么：" in ln],
                                 f"{label} 出现了「做什么／不做什么」段")

    def test_四条机器口径逐字取自正本(self):
        """正本尾四行（P4 两条 ＋ 心跳一条 ＋ 收工哨兵，队列 §一 `#550`／`#565`）
        必须与生成器常量**逐字**相同——改一处不改另一处即红。心跳行比的是占位符版
        （正本教形态、生成器填真值，`OP-0912-F`）。"""
        self.assertEqual(self.canon_lines[-4], M.SUBTASK_PARALLEL_NOTE)
        self.assertEqual(self.canon_lines[-3], M.subtask_heartbeat_note(
            M.SUBTASK_HEARTBEAT_LANE_PLACEHOLDER, M.SUBTASK_HEARTBEAT_BATCH_PLACEHOLDER))
        self.assertEqual(self.canon_lines[-2], M.SUBTASK_PUSH_NOTE)
        self.assertEqual(self.canon_lines[-1], M.SUBTASK_SENTINEL_NOTE)

    def test_正本写明哨兵行是有意扩入(self):
        """骨架该节此前纪律是「P4 两条」——本次扩为三条，正本必须写明理由与 `#550`，
        否则下一个人会按旧纪律把它删掉（派单件 §二 第 1 步的明文要求）。"""
        self.assertIn("#550", self.section)
        self.assertIn("有意扩入", self.section)

    def test_正本写明心跳行是有意扩入(self):
        """同上，心跳约定行是 2026-09-12 `#565` 扩入的，正本必须写明理由，
        否则下一个人会按「P4 两条＋收工哨兵」的旧纪律把它删掉。"""
        self.assertIn("#565", self.section)
        self.assertIn("有意扩入", self.section)

    def test_前三行形状与正本对齐(self):
        """占位符不同、结构必须同：首行编号形态、`【设置】` 六字段、`读 ①` 起手。"""
        canon_head, gen_head = self.canon_lines[:3], self.gen_lines[:3]
        self.assertTrue(canon_head[0].startswith("[OP-MMDD-X]【CC】"))
        self.assertTrue(gen_head[0].startswith("[OP-1231-G]【CC】"))
        for label, line in (("正本", canon_head[2]), ("生成器", gen_head[2])):
            with self.subTest(来源=label):
                self.assertTrue(line.startswith("读 ① "), line[:20])
                self.assertIn("恢复上下文", line)
        lint = M._load_lint_module()
        for label, line in (("正本", canon_head[1]), ("生成器", gen_head[1])):
            with self.subTest(来源=label):
                self.assertEqual(
                    [f for f in lint.SETTINGS_FIELD_ORDER if f in line],
                    list(lint.SETTINGS_FIELD_ORDER), f"{label} 的六字段不全或错序")

    def test_生成器产物过lint零违规(self):
        lint = M._load_lint_module()
        fenced = "\n".join(["```"] + self.gen_lines + ["```"])
        blocks = lint.iter_fenced_blocks(fenced)
        self.assertEqual(lint.check_block(blocks[0], is_subtask_lane=True), [])


class 收工哨兵强制注入(unittest.TestCase):
    """队列 §一 `#550`（2026-09-10）——`--variant subtask_lane` 拼装时**自动带上**收工哨兵行，
    不依赖起草人记得写。

    🔑 **成因**：`工具-opener批处理执行v2.ps1` 判成败靠 `claude` 退出码 ＋ 顶格哨兵两个指标；
    2026-09-10 四条泳道活全做了、无一 `OPENER_DONE`——因为子任务泳道 opener 此前一个字
    没提哨兵。**修法必须落在生成器注入**（`#487` 已证明「正文里写一句」拦不住，本次更前
    一步：压根没生成）。`工具-opener块lint.py` 形态⑨是它的机器守。
    """

    @staticmethod
    def _gen(**over):
        kw = {k: v for k, v in VALID_CC_KWARGS.items() if k not in ("do_items", "dont_items")}
        kw.update({"variant": "subtask_lane", "op_id": "OP-1230-S"})
        kw.update(over)
        return M.generate_opener(**kw)

    def test_子任务泳道成品含哨兵行且在末行(self):
        body = [ln for ln in self._gen().splitlines() if not ln.startswith("```")]
        self.assertEqual(body[-1], M.SUBTASK_SENTINEL_NOTE)
        self.assertIn("OPENER_DONE", body[-1])
        self.assertIn("OPENER_PARTIAL", body[-1])

    def test_传了do_dont仍在最末(self):
        body = [ln for ln in self._gen(do_items=["建造"], dont_items=["不动产线"]).splitlines()
                if not ln.startswith("```")]
        self.assertEqual(body[-4:], [M.SUBTASK_PARALLEL_NOTE,
                                     M.subtask_heartbeat_note("op1230s-demo-slug", "B-1231_示例批"),
                                     M.SUBTASK_PUSH_NOTE, M.SUBTASK_SENTINEL_NOTE])

    def test_其它变体不注入(self):
        """收窄：标准／guardian／reference 都是人粘贴进交互会话的，不经批处理器，不加。"""
        std = M.generate_opener(**{**VALID_CC_KWARGS, "op_id": "OP-1230-T"})
        self.assertNotIn("OPENER_DONE", std)
        kw = {k: v for k, v in VALID_CC_KWARGS.items() if k not in ("do_items", "dont_items")}
        kw.update(op_id="OP-1230-U", variant="guardian", short_name="示例批",
                  branch="master（看护者本身不建分支，不改代码）")
        guardian = M.generate_opener(**kw)
        self.assertNotIn("OPENER_DONE", guardian)

    def test_变异检验_去掉哨兵行lint即转红(self):
        """🔴 队列 `#550` ⑷ 的变异检验以单测形式钉死：把注入逻辑注释掉（等价于从成品
        里删掉那一行），`check_block(is_subtask_lane=True)` 必须报 F9——证明生成器
        自检那道闸对本项**不是恒真**。"""
        lint = M._load_lint_module()
        out = self._gen()
        mutated = "\n".join(ln for ln in out.splitlines() if ln != M.SUBTASK_SENTINEL_NOTE)
        self.assertNotEqual(mutated, out)
        block = lint.iter_fenced_blocks(mutated)[0]
        codes = {c for c, _ in lint.check_block(block, is_subtask_lane=True)}
        self.assertIn("F9", codes)


class 心跳尾句强制注入(unittest.TestCase):
    """队列 §一 `#565`（2026-09-12）——`--variant subtask_lane` 拼装时**自动带上**心跳尾句，
    泳道标识与批次由生成器从 spec 推导（真值，`OP-0912-F`），不靠起草人记得写。

    🔑 **成因**：看护批 `B-0911_机制收口` 五条泳道全做完、`summary` 报「终态泳道 0 条」、
    `reports/lane-heartbeat/` 零文件——心跳命令此前只在 SKILL.md 与看护件 §一（看护者读的
    那段）里，子任务拿到的 prompt ＝ opener 正文原样，一个字没提。且 SKILL.md 缩略形收工句
    漏了 `--batch`，照做也进不了任何一批的账（`#536`）。
    🔴 位置沿对照棒（`6733cb4`）：排在并行上限之后、push 规则之前（成品第二条机器口径）。
    """

    @staticmethod
    def _gen(**over):
        kw = {k: v for k, v in VALID_CC_KWARGS.items() if k not in ("do_items", "dont_items")}
        kw.update({"variant": "subtask_lane", "op_id": "OP-1230-H"})
        kw.update(over)
        return M.generate_opener(**kw)

    @staticmethod
    def _body(text: str) -> list[str]:
        return [ln for ln in text.splitlines() if not ln.startswith("```")]

    @staticmethod
    def _heartbeat_line(body: list[str]) -> str:
        hits = [ln for ln in body if "工具-泳道看护状态机.py heartbeat" in ln]
        assert len(hits) == 1, hits
        return hits[0]

    def test_心跳行在并行上限之后push规则之前_哨兵仍在末行(self):
        body = self._body(self._gen())
        idx_parallel = body.index(M.SUBTASK_PARALLEL_NOTE)
        idx_heartbeat = body.index(self._heartbeat_line(body))
        idx_push = body.index(M.SUBTASK_PUSH_NOTE)
        self.assertEqual(idx_heartbeat, idx_parallel + 1)
        self.assertEqual(idx_push, idx_heartbeat + 1)
        self.assertEqual(body[-1], M.SUBTASK_SENTINEL_NOTE)

    def test_泳道标识等于worktree名与分支名同源(self):
        """`--lane` 值 ＝ `op{mmdd}{x}-{slug}` ＝ 【设置】行分支名去掉 `claude/`——看护者只看
        【设置】行就能推出 `check-heartbeat --heartbeat-file` 该填什么。"""
        body = self._body(self._gen(branch="demo-slug"))
        self.assertIn("--lane op1230h-demo-slug ", self._heartbeat_line(body))
        self.assertIn("`claude/op1230h-demo-slug`", body[1])

    def test_不留占位符(self):
        """🔴 真值填充的反面：成品里不得残留骨架占位符（`OP-0912-F` 派单件 §一 3⑴）。"""
        line = self._heartbeat_line(self._body(self._gen()))
        self.assertNotIn(M.SUBTASK_HEARTBEAT_LANE_PLACEHOLDER, line)
        self.assertNotIn(M.SUBTASK_HEARTBEAT_BATCH_PLACEHOLDER, line)
        self.assertNotIn("<泳道标识", line)

    def test_批次从派出线现取(self):
        body = self._body(self._gen(line="Cowork 环境总线 OP-1230-Z（批 B-1230_夜批）"))
        self.assertIn("--done --batch B-1230_夜批 ", self._heartbeat_line(body))

    def test_批次直写在派出线不带括号也能取(self):
        """看护件既有写法之二：「业务总线 B-0905_B」。"""
        body = self._body(self._gen(line="Cowork 业务总线 B-1230_B"))
        self.assertIn("--done --batch B-1230_B ", self._heartbeat_line(body))

    def test_显式batch优先于派出线(self):
        body = self._body(self._gen(line="环境总线（批 B-1230_甲）", batch="B-1230_乙"))
        line = self._heartbeat_line(body)
        self.assertIn("--batch B-1230_乙 ", line)
        self.assertNotIn("B-1230_甲 ", line)

    def test_无批次即拒绝出件(self):
        """不带 `--batch` 的 `heartbeat --done` 让泳道归属未知、`summary --batch` 报 0——
        正是 `#565` 的现象本身，生成器不替下游留这个洞。"""
        with self.assertRaises(M.OpenerGenError) as ctx:
            self._gen(line="环境总线 OP-1230-Z")
        self.assertIn("--batch", str(ctx.exception))
        self.assertIn("#565", str(ctx.exception))

    def test_收工句带batch_开工句不带done(self):
        line = self._heartbeat_line(self._body(self._gen()))
        start = line.index("--text \"已开工\"")
        self.assertNotIn("--done", line[:start])
        self.assertIn("--done --batch B-1231_示例批 --text \"产出落点：<落点>\"", line)

    def test_不教人给不存在的参数(self):
        """SKILL.md 步骤 4 明写：工具没有 `--repo-root`／`--heartbeat-file`，尾句必须把这条带上，
        否则子任务按旧散文自己拼路径又会写回各自 worktree。"""
        line = self._heartbeat_line(self._body(self._gen()))
        self.assertIn("--repo-root", line)
        self.assertIn("--heartbeat-file", line)

    def test_batch传给非子任务变体即拒绝(self):
        """参数被接受却不生效比被拒更危险（`#487` 子项同判据）。"""
        kw = dict(VALID_CC_KWARGS)
        kw.update({"op_id": "OP-1230-I", "batch": "B-1230_X"})
        with self.assertRaises(M.OpenerGenError):
            M.generate_opener(**kw)

    def test_其它变体不注入(self):
        """收窄：标准／guardian／reference 都是人粘贴进交互会话的，不经批处理器，不加。"""
        std = M.generate_opener(**{**VALID_CC_KWARGS, "op_id": "OP-1229-T"})
        self.assertNotIn("工具-泳道看护状态机.py heartbeat", std)
        kw = {k: v for k, v in VALID_CC_KWARGS.items() if k not in ("do_items", "dont_items")}
        kw.update(op_id="OP-1229-U", variant="guardian", short_name="示例批",
                  branch="master（看护者本身不建分支，不改代码）")
        guardian = M.generate_opener(**kw)
        self.assertNotIn("工具-泳道看护状态机.py heartbeat", guardian)

    def test_CLI_batch旗标可用(self):
        import io as _io
        import contextlib
        out, err = _io.StringIO(), _io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            rc = M.main([
                "--op-id", "OP-1230-J", "--env", "CC", "--short-name", "心跳示例",
                "--branch", "hb-demo", "--worktree", "☑（hb，新 worktree，收工自删）",
                "--workspace", "无", "--session", "新开", "--line", "环境总线 OP-1230-Z",
                "--input-pointer", "1-转型规划/0-全景路线图/示例派单件.md", "--task-class", "A",
                "--variant", "subtask_lane", "--batch", "B-1230_单棒",
            ])
        self.assertEqual(rc, 0, err.getvalue())
        self.assertIn("--done --batch B-1230_单棒 ", out.getvalue())

    def test_产物过lint零违规(self):
        lint = M._load_lint_module()
        blocks = lint.iter_fenced_blocks(self._gen())
        self.assertEqual(lint.check_block(blocks[0], is_subtask_lane=True), [])

    def test_变异检验_去掉心跳行lint即转红(self):
        """🔴 队列 `#565` 的变异检验以单测形式钉死：把注入逻辑注释掉（等价于从成品里
        删掉那一行），`check_block(is_subtask_lane=True)` 必须报 F10——证明生成器
        自检那道闸对本项**不是恒真**。"""
        lint = M._load_lint_module()
        out = self._gen()
        hb = self._heartbeat_line(self._body(out))
        mutated = "\n".join(ln for ln in out.splitlines() if ln != hb)
        self.assertNotEqual(mutated, out)
        block = lint.iter_fenced_blocks(mutated)[0]
        codes = {c for c, _ in lint.check_block(block, is_subtask_lane=True)}
        self.assertIn("F10", codes)
        # 反向：原样成品零违规。
        self.assertEqual(lint.check_block(lint.iter_fenced_blocks(out)[0], is_subtask_lane=True), [])


class 取号即声明(unittest.TestCase):
    """队列 §一 `#549` ⑶／`#531` 子项（2026-09-10）——取号时写一条轻量占位到
    `reports/op-id-claims.jsonl`，查重同时扫「已落档文件」与「已取未落档的占位」。

    🔑 **成因**：2026-09-10 `OP-0910-I`／`OP-0910-J` 两次撞号**未被拦**——两边都在起草期、
    都没落档，`_scan_used_suffixes` 只看得见已落档的号；同日 `OP-0910-H` 被拦，差别只在
    对方已落档。两次对比正好界定了旧查重的边界，占位就是补这一段真空。
    """

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self._old_root, self._old_claims = M.REPO_ROOT, M.CLAIMS_FILE
        M.REPO_ROOT = self.root
        M.CLAIMS_FILE = self.root / "reports" / "op-id-claims.jsonl"

    def tearDown(self):
        M.REPO_ROOT, M.CLAIMS_FILE = self._old_root, self._old_claims
        self._tmp.cleanup()

    @staticmethod
    def _kw(**over):
        kw = dict(VALID_CC_KWARGS)
        kw.update({"op_id": "OP-1229-A"})
        kw.update(over)
        return kw

    def _claims(self) -> list[dict]:
        return M._load_claims(M.CLAIMS_FILE)

    def test_出件即写占位(self):
        M.generate_opener(**self._kw())
        recs = self._claims()
        self.assertEqual(len(recs), 1)
        self.assertEqual(recs[0]["op_id"], "OP-1229-A")
        self.assertEqual(recs[0]["short_name"], VALID_CC_KWARGS["short_name"])
        self.assertIn("claimed_at", recs[0])

    def test_并发取同号_第二份起草件撞红(self):
        """🔴 变异检验的靶子（队列 `#549` ⑷）：把 `_claim_op_id` 的调用注释掉，本用例必红——
        两份件都没落档、`_scan_used_suffixes` 两边都看不见，只有占位能拦。"""
        M.generate_opener(**self._kw(short_name="甲线派单", line="业务总线"))
        with self.assertRaises(M.OpenerGenError) as cm:
            M.generate_opener(**self._kw(short_name="乙线派单", line="环境总线"))
        msg = str(cm.exception)
        self.assertIn("起草中", msg)
        self.assertIn("甲线派单", msg)
        self.assertIn("OP-1229-B", msg)   # 下一个空号避开已声明的 A

    def test_同一草稿重生成不自撞(self):
        """短名相同＝同一份草稿改参数再跑一次，刷新占位而不是拦自己。"""
        M.generate_opener(**self._kw(short_name="同一份件"))
        M.generate_opener(**self._kw(short_name="同一份件", branch="another-slug"))
        recs = self._claims()
        self.assertEqual(len(recs), 1)

    def test_同线不同件同号仍撞(self):
        """🔴 刻意不看 `line`：同一条线在同一时段起两份不同的件却传同一个号，正是要拦的。"""
        M.generate_opener(**self._kw(short_name="件一", line="业务总线"))
        with self.assertRaises(M.OpenerGenError):
            M.generate_opener(**self._kw(short_name="件二", line="业务总线"))

    def test_过期占位不挡号且被清理(self):
        old = M._fmt_utc(M._utc_now() - timedelta(minutes=M.CLAIM_TTL_MINUTES + 1))
        M.CLAIMS_FILE.parent.mkdir(parents=True)
        M.CLAIMS_FILE.write_text(json.dumps({
            "op_id": "OP-1229-A", "mmdd": "1229", "suffix": "A", "short_name": "陈旧件",
            "line": "X", "claimed_at": old}) + "\n", encoding="utf-8")
        M.generate_opener(**self._kw(short_name="新件"))
        recs = self._claims()
        self.assertEqual([r["short_name"] for r in recs], ["新件"])

    def test_未过期占位_隔线仍挡(self):
        """反向配对：同样的记录只是没过期 ⇒ 必须拦，证明上一条的放行来自时效而非记录被忽略。"""
        fresh = M._fmt_utc(M._utc_now() - timedelta(minutes=1))
        M.CLAIMS_FILE.parent.mkdir(parents=True)
        M.CLAIMS_FILE.write_text(json.dumps({
            "op_id": "OP-1229-A", "mmdd": "1229", "suffix": "A", "short_name": "在跑件",
            "line": "X", "claimed_at": fresh}) + "\n", encoding="utf-8")
        with self.assertRaises(M.OpenerGenError):
            M.generate_opener(**self._kw(short_name="新件"))

    def test_已落档的号_占位自动清理(self):
        """落了档就由 `_scan_used_suffixes` 接管；占位只覆盖取号→落档的真空。"""
        M.generate_opener(**self._kw(short_name="要落档的件"))
        (self.root / "1-转型规划").mkdir()
        (self.root / "1-转型规划" / "派单件.md").write_text("[OP-1229-A]【CC】要落档的件", encoding="utf-8")
        # 任意一次当日取号都会顺手清理：取 B。
        M.generate_opener(**self._kw(op_id="OP-1229-B", short_name="另一件"))
        recs = self._claims()
        self.assertEqual([r["op_id"] for r in recs], ["OP-1229-B"])
        # 已落档的 A 仍被拦（由落档扫描拦，不是由占位拦）。
        with self.assertRaises(M.OpenerGenError) as cm:
            M.generate_opener(**self._kw(short_name="第三件"))
        self.assertIn("已被使用", str(cm.exception))

    def test_落档撞号时下一空号也避开占位(self):
        M.generate_opener(**self._kw(op_id="OP-1229-B", short_name="占了B"))
        (self.root / "1-转型规划").mkdir()
        (self.root / "1-转型规划" / "x.md").write_text("OP-1229-A 已落档", encoding="utf-8")
        with self.assertRaises(M.OpenerGenError) as cm:
            M.generate_opener(**self._kw(short_name="再取A"))
        self.assertIn("OP-1229-C", str(cm.exception))

    def test_台账写不了即不出件(self):
        """fail-closed：不能证明占到号就不算取到号（同「缺字段直接报错退出、不出半成品」）。"""
        blocker = self.root / "reports"
        blocker.write_text("我是文件不是目录", encoding="utf-8")   # 使 reports/ 无法成为目录
        with self.assertRaises(M.OpenerGenError) as cm:
            M.generate_opener(**self._kw())
        self.assertIn("fail-closed", str(cm.exception))

    def test_不同日期同后缀互不干扰(self):
        M.generate_opener(**self._kw(op_id="OP-1228-A", short_name="昨天的A"))
        M.generate_opener(**self._kw(op_id="OP-1229-A", short_name="今天的A"))
        self.assertEqual(len(self._claims()), 2)

    def test_坏行不崩(self):
        M.CLAIMS_FILE.parent.mkdir(parents=True)
        M.CLAIMS_FILE.write_text("{not json\n\n", encoding="utf-8")
        M.generate_opener(**self._kw())
        self.assertEqual(len(self._claims()), 1)

    def test_台账落主工作区_跨worktree共享(self):
        """`CLAIMS_FILE` 未覆盖时按 `git rev-parse --git-common-dir` 解析到主工作区——
        Cowork 在主 checkout、CC 泳道在各自 worktree，各算各的就会写出 N 份互相看不见的台账。"""
        M.CLAIMS_FILE = None
        M.REPO_ROOT = SCRIPT.parents[1]   # 真实仓库位置（setUpModule 已把它钉到空临时目录）
        try:
            shared = M._shared_repo_root()
            self.assertTrue((shared / ".git").exists(), shared)
            self.assertEqual(M._claims_file(), shared / M.CLAIMS_FILE_REL)
        finally:
            M.CLAIMS_FILE = self.root / "reports" / "op-id-claims.jsonl"
            M.REPO_ROOT = self.root


if __name__ == "__main__":
    unittest.main()
