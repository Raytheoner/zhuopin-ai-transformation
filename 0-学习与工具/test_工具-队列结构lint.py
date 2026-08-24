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


SECTION_TWO_HEADER = (
    "\n## 二、待 commit 批次（CC 取活销行）\n\n"
    "| 批次 | 文件清单 | 建议 message | 状态 |\n"
    "|------|---------|--------------|------|\n"
)
SECTION_THREE_HEADER = "\n## 三、口径冻结标（重梳期防在途建造撞车）\n\n"
SECTION_FOUR_HEADER = (
    "\n## 四、需 Shao Peishen 的动作（例外与拍板）\n\n"
    "| # | 事项 | 等谁 | 截止 |\n"
    "|---|------|------|------|\n"
)


class FollowupRestateWarnTests(unittest.TestCase):
    """队列 #366 / S2 一期：队列禁止复述信状态（只 warn、不进 `lint()`）。

    S1（Shao Peishen 2026-08-21 答 §四 #85 选 (b)）确立：一封信的状态唯一
    权威源是跟进信 README 的「发送状态」列，队列只允许写指针。

    判据窗口（前后各 ≤8 字）是**实测标定**的，不是拍的——用例同时锁住
    「该命中的」与「不该命中的」两侧，任何一侧漂了都会红。
    """

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.repo_root = Path(self._tmpdir.name)
        self.module = _load_module()
        self.target_path = self.repo_root / self.module.QUEUE_REL
        self.target_path.parent.mkdir(parents=True, exist_ok=True)
        self.module.QUEUE_PATHS_REL = [self.module.QUEUE_REL]

    def tearDown(self):
        self._tmpdir.cleanup()

    def _write(self, section_one_rows="", section_two_rows="", section_four_rows=""):
        self.target_path.write_text(
            HEADER + section_one_rows
            + SECTION_TWO_HEADER + section_two_rows
            + SECTION_THREE_HEADER
            + SECTION_FOUR_HEADER + section_four_rows,
            encoding="utf-8",
        )

    def _warn(self):
        return self.module.followup_restate_warnings(self.repo_root)

    def test_四区活行复述被告警(self):
        self._write(section_four_rows=(
            "| 65 | 三条规则走哪条确认路径（等采购部#15 闭环） | Shao Peishen | 无 |\n"
        ))
        warnings, historical = self._warn()
        self.assertEqual(len(warnings), 1, warnings)
        self.assertIn("等采购部#15 闭环", warnings[0])
        self.assertIn("工具-跟进闸查询.py", warnings[0],
                      "提示必须给出替代指针，不能只说「别写」")
        self.assertEqual(historical, 0)

    def test_一区未完成行复述被告警(self):
        self._write(section_one_rows=(
            "| 361 | SC2 收口承接行 | 采购专线 | `x.md` | 产出 | "
            "[S:open][D:业] 等姚祖怡采购部#16 闭环 | 队列 | 2026-08-21 |\n"
        ))
        warnings, _ = self._warn()
        self.assertEqual(len(warnings), 1, warnings)
        self.assertIn("#361", warnings[0])

    def test_一区已完成行按历史记录不追改豁免但必须计数(self):
        self._write(section_one_rows=(
            "| 150 | 判例包待发 | 采购专线 | `x.md` | 产出 | "
            "[S:done][D:业] ✅ 已完成，当时待采购部#10 回件闭环 | 队列 | 2026-08-03 |\n"
        ))
        warnings, historical = self._warn()
        self.assertEqual(warnings, [], "已完成的历史行不得报违规")
        self.assertEqual(historical, 1, "但必须计数并打印——静默豁免正是本判据要治的毛病")

    def test_二区历史批次行不被误报(self):
        """反例单测⑵（派单件 §六.3）。"""
        self._write(section_two_rows=(
            "| B-0805_01 | `跨桌任务队列.md` | docs: 登记等采购部#10 回件闭环一事 | ✅ 已提交 |\n"
        ))
        warnings, historical = self._warn()
        self.assertEqual(warnings, [], "§二 批次行天然是历史记录，不在扫描范围")
        self.assertEqual(historical, 0, "§二 也不计入历史计数——它压根不扫")

    def test_事后陈述式引用不被误报(self):
        # 窗口收窄的正当性由这一条锁住：「已作为 采购部#16 发出、现等回件」
        # 是**事后陈述**而非判据快照；放宽到 40 字窗口会把它一并卷进来
        # （2026-08-21 实测：18 处命中里绝大多数是这一类）。
        self._write(section_one_rows=(
            "| 344 | 判例包 | 采购专线 | `x.md` | 产出 | "
            "[S:open][D:业] 其判例包已作为 采购部#16 发出、现等回件，留在 open 会冒充可开工 "
            "| 队列 | 2026-08-19 |\n"
        ))
        self.assertEqual(self._warn()[0], [])

    def test_写成指针的合规形态不被告警(self):
        self._write(section_one_rows=(
            "| 361 | SC2 收口承接行 | 采购专线 | `x.md` | 产出 | "
            "[S:open][D:业] 串行闸状态跑 工具-跟进闸查询.py --to 姚祖怡 "
            "| 队列 | 2026-08-21 |\n"
        ))
        self.assertEqual(self._warn()[0], [])

    def test_告警不影响lint退出码(self):
        self._write(section_four_rows="| 65 | 等采购部#15 闭环 | Shao Peishen | 无 |\n")
        self.assertEqual(
            self.module.lint(self.repo_root), [],
            "S2 一期只 warn——不得进 `lint()` 的违规列表，否则等于直接硬拦",
        )


class FollowupGateImportableCheckTests(unittest.TestCase):
    """队列 #366 / S4：`followup_gate` 可 import 断言（#313 范式的扩用）。

    编辑锁对该模块有兜底（import 不到即跳过 S4 桥二校验，只打一行 ⚠）——
    **那条降级路径本身是静默的**，本断言存在的唯一目的就是让它在 CI 里红。
    """

    def setUp(self):
        self.module = _load_module()

    def test_real_repo_root_has_followup_gate(self):
        self.assertIsNone(self.module.check_queue_table_importable(self.module.REPO_ROOT))

    def test_editlock_uses_the_authoritative_module_not_its_stub(self):
        self.assertIsNotNone(
            self.module.editlock.followup_gate,
            "真实仓库里编辑锁必须拿到权威模块本体；拿到 None 说明它正在走隔离"
            "兜底路径，S4 桥二校验会整条静默跳过",
        )
        self.assertEqual(
            self.module.editlock.FOLLOWUP_SERIAL_CLOSED_PREFIXES,
            self.module.editlock.followup_gate.CLOSED_STATUS_PREFIXES,
            "闭环四态判据必须只有一份，编辑锁不得自持一套字面量",
        )


class AppellationBaselineTests(unittest.TestCase):
    """队列 #352：称呼判据 + baseline（`Paul` → `Shao Peishen`）。

    两向都必须锁住，缺任一向这道门禁都是假的：
      · baseline 内的存量命中**不报**（否则 CI 长期红 ⇒ 门禁自废）；
      · baseline 外的新增命中**即报**（否则它只是个装饰）。
    另加三类豁免与「baseline 读不到必须 fail-loud」。
    """

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.repo_root = Path(self._tmpdir.name)
        self.module = _load_module()
        self.target_path = self.repo_root / self.module.QUEUE_REL
        self.target_path.parent.mkdir(parents=True, exist_ok=True)
        self.module.QUEUE_PATHS_REL = [self.module.QUEUE_REL]
        self.baseline_path = self.repo_root / "baseline.json"

    def tearDown(self):
        self._tmpdir.cleanup()

    def _write_baseline(self, hits: dict) -> None:
        self.baseline_path.write_text(
            __import__("json").dumps({"命中": hits}, ensure_ascii=False),
            encoding="utf-8",
        )

    def _write(self, section_one_rows="", section_two_rows="", section_four_rows=""):
        self.target_path.write_text(
            HEADER + section_one_rows
            + SECTION_TWO_HEADER + section_two_rows
            + SECTION_THREE_HEADER
            + SECTION_FOUR_HEADER + section_four_rows,
            encoding="utf-8",
        )

    def _check(self):
        return self.module.appellation_check(self.repo_root, self.baseline_path)

    # ---- 两向：baseline 内不报 / baseline 外即报 ----------------------------

    def test_baseline内命中不报(self):
        self._write(section_one_rows=(
            "| 150 | 历史任务 | CC | 指针 | 产出 | "
            "[S:open][D:机] Paul 2026-07-24 拍板，Paul 另定一条 | 触碰区 | 2026-08-09 |\n"
        ))
        self._write_baseline({"一#150": 2})
        violations, _ = self._check()
        self.assertEqual(violations, [], "存量已冻结，不得报违规——否则 CI 长期红")

    def test_baseline外新增行即报(self):
        self._write(section_one_rows=(
            "| 151 | 新任务 | CC | 指针 | 产出 | "
            "[S:open][D:机] Paul 2026-08-24 拍板 | 触碰区 | 2026-08-24 |\n"
        ))
        self._write_baseline({"一#150": 2})
        violations, _ = self._check()
        self.assertEqual(len(violations), 1, violations)
        self.assertIn("#151", violations[0])
        self.assertIn("Shao Peishen", violations[0], "提示必须给出正确写法，不能只说「别写」")
        self.assertIn(self.module.APPELLATION_EXEMPT_MARK, violations[0],
                      "提示必须给出逃生阀，否则唯一出路是重刷 baseline")

    def test_baseline内行再加一处即报(self):
        """棘轮：已 baseline 的行也不能继续往里加——否则历史行会变成藏新
        违规的安全屋。"""
        self._write(section_one_rows=(
            "| 150 | 历史任务 | CC | 指针 | 产出 | "
            "[S:open][D:机] Paul 拍板，Paul 补充，Paul 又补一句 | 触碰区 | 2026-08-24 |\n"
        ))
        self._write_baseline({"一#150": 2})
        violations, _ = self._check()
        self.assertEqual(len(violations), 1, violations)
        self.assertIn("新增 1 处", violations[0])

    def test_行内命中变少只算漂移不算违规(self):
        self._write(section_one_rows=(
            "| 150 | 历史任务 | CC | 指针 | 产出 | "
            "[S:open][D:机] Paul 拍板 | 触碰区 | 2026-08-24 |\n"
        ))
        self._write_baseline({"一#150": 5})
        violations, stats = self._check()
        self.assertEqual(violations, [])
        self.assertEqual(len(stats["drift"]), 1, stats)

    def test_行从一份队列挪到另一份不产生假违规(self):
        """行键刻意不含文件名（`_appellation_row_key` docstring）：#315 式
        拆分把行从机制环境挪到业务场景时，一个字都没改却报违规是不可接受
        的——那种噪音的最省事修法就是重刷 baseline。"""
        other = self.repo_root / "另一份队列.md"
        other.write_text(
            HEADER + "| 150 | 历史任务 | CC | 指针 | 产出 | "
            "[S:open][D:机] Paul 拍板，Paul 另定 | 触碰区 | 2026-08-09 |\n"
            + SECTION_TWO_HEADER + SECTION_THREE_HEADER + SECTION_FOUR_HEADER,
            encoding="utf-8",
        )
        self._write()  # 原文件里这一行已被挪走
        self.module.QUEUE_PATHS_REL = [self.module.QUEUE_REL, "另一份队列.md"]
        self._write_baseline({"一#150": 2})
        violations, _ = self._check()
        self.assertEqual(violations, [], "纯搬家不得报违规")

    # ---- 三类豁免 ---------------------------------------------------------

    def test_路径与账户名里的PaulShao不报(self):
        """根 CLAUDE.md §1：🔴 绝不替换路径里的 `Paul Shao`（改了路径即失效）。
        本机用户目录与计划任务运行身份字面量都长这样。"""
        self._write(section_one_rows=(
            "| 151 | 取证 | CC | 指针 | 产出 | "
            "[S:open][D:机] 真身 `C:\\Users\\Paul Shao\\Claude\\Sc`；"
            "`ZhuopinCommitSweep` 实为 `Paul Shao / S4U`；"
            "bash 在 `Paul Shao` 的空格处截断 | 触碰区 | 2026-08-24 |\n"
        ))
        self._write_baseline({})
        violations, _ = self._check()
        self.assertEqual(violations, [], f"路径形态不得被判违规：{violations}")

    def test_一区已完成行按历史记录不追改豁免但必须计数(self):
        self._write(section_one_rows=(
            "| 152 | 老任务 | CC | 指针 | 产出 | "
            "[S:done][D:机] ✅ 已完成，Paul 2026-07-01 拍板 | 触碰区 | 2026-07-01 |\n"
        ))
        self._write_baseline({})
        violations, stats = self._check()
        self.assertEqual(violations, [], "已完成的历史行不得报违规")
        self.assertEqual(
            [(k, r) for k, r, _ in stats["exempt_rows"]], [("一#152", "[S:done] 历史行")],
            "但必须计数——静默豁免正是本判据这一族毛病本身",
        )

    def test_行内称呼豁免标记生效且必须可计数(self):
        """逃生阀，范式沿用 §四 #58 已验证过的 `WIP豁免：`：理由的唯一真源
        是行内标记，不是命令行开关。真实用例＝队列 #352 行自己（定义判据的
        行必须引用它要拦的字面量）。"""
        self._write(section_one_rows=(
            "| 352 | 称呼判据 | CC | 指针 | 产出 | "
            "[S:open][D:机] 称呼豁免：本行是判据定义行，须引用 `Paul` 字面量 "
            "| 触碰区 | 2026-08-24 |\n"
        ))
        self._write_baseline({})
        violations, stats = self._check()
        self.assertEqual(violations, [])
        self.assertEqual([(k, r) for k, r, _ in stats["exempt_rows"]],
                         [("一#352", "行内标记")])

    def test_代码标识符不被误伤(self):
        """大小写敏感是判据的一部分：`PAUL_USERID` 是企微 userid 常量、
        `cc_to_paul` 是函数参数名，两者都不是称呼。"""
        self._write(section_one_rows=(
            "| 153 | 机器人 | CC | 指针 | 产出 | "
            "[S:open][D:机] `PAUL_USERID` 与 `cc_to_paul=False`，另有 `paulista` "
            "| 触碰区 | 2026-08-24 |\n"
        ))
        self._write_baseline({})
        self.assertEqual(self._check()[0], [])

    # ---- 扫描面与 fail-loud ------------------------------------------------

    def test_二区与四区同在扫描面内(self):
        self._write(
            section_two_rows="| B-0824_01 | `x.md` | docs: Paul 拍板 | ⏳ 待提交 |\n",
            section_four_rows="| 99 | 某事项 | Paul | 无 |\n",
        )
        self._write_baseline({})
        violations, _ = self._check()
        self.assertEqual(len(violations), 2, violations)
        self.assertTrue(any("二 #B-0824_01" in v for v in violations), violations)
        self.assertTrue(any("四 #99" in v for v in violations), violations)

    def test_baseline文件缺失必须fail_loud而不是当成空(self):
        """空字典也会红，但红的原因会被读成「队列里突然多了几十处称呼违规」，
        而真相是「baseline 没找着」——同 CLAUDE.md §5「工具静默回退」。"""
        self._write()
        violations, _ = self._check()
        self.assertEqual(len(violations), 1, violations)
        self.assertIn("baseline 文件不存在", violations[0])

    def test_baseline文件损坏必须fail_loud(self):
        self.baseline_path.write_text("{不是 JSON", encoding="utf-8")
        self._write()
        violations, _ = self._check()
        self.assertEqual(len(violations), 1, violations)
        self.assertIn("无法解析", violations[0])

    def test_违规计入lint退出码(self):
        """与 #366/S2 那条只 warn 的判据的分野：本判据有 baseline，存量已
        冻结、当天即绿，硬拦不会拦住任何既有内容。"""
        self._write(section_four_rows="| 99 | 某事项 | Paul | 无 |\n")
        self.module.APPELLATION_BASELINE_PATH = self.baseline_path
        self._write_baseline({})
        self.assertTrue(
            any("称呼违规" in v for v in self.module.lint(self.repo_root)),
            "称呼违规必须进 `lint()` 的违规列表，否则退出码永远是 0",
        )


class AppellationEmitBaselineTests(unittest.TestCase):
    """`--emit-baseline`：只产 JSON 文本，不写盘；豁免行不入 baseline。"""

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.repo_root = Path(self._tmpdir.name)
        self.module = _load_module()
        self.target_path = self.repo_root / self.module.QUEUE_REL
        self.target_path.parent.mkdir(parents=True, exist_ok=True)
        self.module.QUEUE_PATHS_REL = [self.module.QUEUE_REL]

    def tearDown(self):
        self._tmpdir.cleanup()

    def _emit(self, section_one_rows):
        self.target_path.write_text(
            HEADER + section_one_rows + SECTION_TWO_HEADER
            + SECTION_THREE_HEADER + SECTION_FOUR_HEADER,
            encoding="utf-8",
        )
        import json

        return json.loads(self.module.emit_appellation_baseline(self.repo_root))

    def test_只产文本不写盘(self):
        real_baseline = self.module.APPELLATION_BASELINE_PATH
        before = real_baseline.read_bytes() if real_baseline.exists() else None
        self._emit("| 150 | 任务 | CC | 指针 | 产出 | [S:open][D:机] Paul 拍板 | 触碰区 | 2026-08-24 |\n")
        after = real_baseline.read_bytes() if real_baseline.exists() else None
        self.assertEqual(before, after, "`--emit-baseline` 不得改写 baseline 文件本身")

    def test_豁免行不入baseline(self):
        """写进去只会让读 baseline 的人误以为那些行是被 baseline 放行的。"""
        data = self._emit(
            "| 150 | 活行 | CC | 指针 | 产出 | [S:open][D:机] Paul 拍板 | 触碰区 | 2026-08-24 |\n"
            "| 151 | 历史行 | CC | 指针 | 产出 | [S:done][D:机] ✅ Paul 拍板 | 触碰区 | 2026-07-01 |\n"
            "| 152 | 判据定义行 | CC | 指针 | 产出 | "
            "[S:open][D:机] 称呼豁免：须引用 `Paul` 字面量 | 触碰区 | 2026-08-24 |\n"
        )
        self.assertEqual(data["命中"], {"一#150": 1}, data["命中"])


class AppellationRealQueueTests(unittest.TestCase):
    """回归护栏：真实生产队列 + 入库的 baseline 必须零违规。

    这一条是「无 baseline 不得合入」这句要求的机器表达——baseline 若没随
    代码一起入库、或与队列现状对不上，本用例立刻红。
    """

    def setUp(self):
        self.module = _load_module()

    def test_real_queue_with_committed_baseline_is_clean(self):
        self.module.QUEUE_PATHS_REL = [self.module.editlock.QUEUE_MECHANISM_PATH_REL,
                                       self.module.editlock.QUEUE_BUSINESS_PATH_REL]
        violations, stats = self.module.appellation_check(self.module.REPO_ROOT)
        self.assertEqual(violations, [], f"真实队列不应有称呼违规：{violations}")
        self.assertGreater(
            stats["live_rows"], 0,
            "受管活行为 0 说明扫描面塌了（如队列路径解错）——那时「零违规」是假的",
        )

    def test_committed_baseline_file_exists_and_parses(self):
        hits, error = self.module.load_appellation_baseline()
        self.assertIsNone(error, error)
        self.assertGreater(len(hits), 0, "baseline 必须随代码入库，否则门禁开局即红")


if __name__ == "__main__":
    unittest.main()
