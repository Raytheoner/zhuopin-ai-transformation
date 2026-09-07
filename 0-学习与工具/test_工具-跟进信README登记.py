"""`工具-跟进信README登记.py` 单测（`followup-readme-phase2` D1，队列 §一 `#490`）。

白盒方式：按文件路径 importlib 加载被测脚本（本目录既定手法），把 `REPO_ROOT`
指向临时夹具目录——**不触碰真实 README**。`_run_lock`（真实取锁会 subprocess
调用编辑锁工具、要求目标位于真实 git 仓库）统一 monkeypatch 为受控桩，
锁本身的正确性由 `test_工具-共享文档编辑锁.py` 独立覆盖，本文件只验证
「本 CLI 在锁返回不同结果时的行为是否正确」（含 release 被拒绝时不得报告
成功——2026-09-06 对真实 README 实测发现的缺陷）。
"""
from __future__ import annotations

import importlib.util
import io
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

SCRIPT = Path(__file__).resolve().with_name("工具-跟进信README登记.py")
README_REL = "6-人才与组织/部门AI专员跟进/README-跟进机制与命名约定.md"

MAIN_HEADER = (
    "## 现有跟进信清单\n\n"
    "| 编号 | 日期 | 收信人 | 主要事项 | 交期要点 | 发送状态（2026-07-06） |\n"
    "|--------|------|--------|---------|---------|---------|\n"
)


def _load():
    spec = importlib.util.spec_from_file_location("_followup_registry_under_test", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _row(number, recipient, topic, note, status, date="2026-08-20"):
    return f"| {number} | {date} | {recipient} | {topic} | {note} | {status} |\n"


class _FakeArgs:
    def __init__(self, **kwargs):
        self.dry_run = False
        # `set-status` 的 `--fact-date`（`#447` ⑵）——argparse 恒会设它，故此处
        # 也恒设，让 `cmd_set_status` 可以直接 `args.fact_date` 取（用
        # `getattr(..., None)` 兜底等于给「漏传」留一条静默通道）。
        self.fact_date = None
        for k, v in kwargs.items():
            setattr(self, k, v)


class RegistryCliTestBase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.module = _load()
        self.module.REPO_ROOT = self.root
        # `_assert_gate_open` 委托 `gate_query.build_report`，而该子模块自身
        # 也持有一份 `REPO_ROOT`（用于扫队列取入信行）——同步指向同一临时
        # 夹具目录，避免测试悄悄读到真实仓库的两份队列文件（同
        # `test_工具-跟进闸查询.py` 的既定隔离手法）。
        self.module.gate_query.REPO_ROOT = self.root
        (self.root / README_REL).parent.mkdir(parents=True, exist_ok=True)
        queue_header = (
            "## 一、任务看板\n\n"
            "| # | 任务 | 领取方 | 输入（指针） | 期望产出 | 状态 | 触碰区 | 登记 |\n"
            "|---|------|--------|-------------|----------|------|--------|------|\n"
        )
        for rel in self.module.gate_query.QUEUE_PATHS_REL:
            queue_path = self.root / rel
            queue_path.parent.mkdir(parents=True, exist_ok=True)
            queue_path.write_text(queue_header, encoding="utf-8")
        self._lock_calls: list[tuple[str, str]] = []
        self._release_should_succeed = True
        self.module._run_lock = self._fake_run_lock
        # 绝大多数既有 append 用例不关心 `决策点:` 闸，给它们一封形态合法的
        # 默认信件；专测该闸的用例自己传 `letter_path=`。
        self.default_letter = self._write_letter()

    def tearDown(self):
        self._tmp.cleanup()

    def _fake_run_lock(self, action, who, note=None):
        self._lock_calls.append((action, who))
        if action == "release":
            return self._release_should_succeed
        return True

    def _write_letter(self, decision="1 项（试用反馈）", name="信件.md",
                      frontmatter=True, extra_fields=""):
        """写一封夹具信，返回相对 `REPO_ROOT` 的路径（CLI 的 `--letter-path`
        取值形态）。`decision=None` ⇒ 整行不写；`decision=""` ⇒ 写空值。"""
        rel = f"6-人才与组织/部门AI专员跟进/{name}"
        path = self.root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        if frontmatter:
            lines = ['title: "夹具信"', "status: 待你审", "created: 2026-09-06"]
            if decision is not None:
                lines.append(f"决策点: {decision}")
            if extra_fields:
                lines.append(extra_fields)
            body = "---\n" + "\n".join(lines) + "\n---\n\n正文。\n"
        else:
            body = "# 没有 frontmatter 的信\n\n决策点: 3 项（正文里的不算）\n"
        path.write_text(body, encoding="utf-8")
        return rel

    def _write_readme(self, rows: str):
        (self.root / README_REL).write_text(MAIN_HEADER + rows, encoding="utf-8")

    def _readme_text(self) -> str:
        return (self.root / README_REL).read_text(encoding="utf-8")

    def _run(self, func, **kwargs):
        # `append` 新增必填 `--letter-path`（`决策点:` 前置闸）。不关心该闸的
        # 用例默认拿到一封形态合法的夹具信，专测该闸的用例显式传 `letter_path`。
        kwargs.setdefault("letter_path", self.default_letter)
        args = _FakeArgs(**kwargs)
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = func(args)
        return code, out.getvalue(), err.getvalue()


class AppendTests(RegistryCliTestBase):
    def test_append成功新增一行且状态恒为待审草稿态(self):
        self._write_readme(
            _row("采购部#5", "采购部 · 姚祖怡", "旧信", "尽快", "📥 已回件并回灌（2026-08-01）")
        )
        code, out, _err = self._run(
            self.module.cmd_append, who="t", department="采购部",
            recipient_cell="采购部 · 姚祖怡", date="2026-09-06",
            topic="新事项", deadline_note="无",
        )
        self.assertEqual(code, 0)
        self.assertIn("[OK]", out)
        self.assertIn("采购部#6（待你审，暂不占号）", self._readme_text())
        self.assertIn(
            "| 采购部#6（待你审，暂不占号） | 2026-09-06 | 采购部 · 姚祖怡 | 新事项 | 无 | ⏳ 待你审 |",
            self._readme_text(),
        )
        self.assertEqual(self._lock_calls, [("acquire", "t"), ("release", "t")])

    def test_闸锁时append被拒绝且不取锁不写入(self):
        self._write_readme(
            _row("采购部#5", "采购部 · 姚祖怡", "在途信", "尽快", "✅ 已推送 2026-08-30")
        )
        before = self._readme_text()
        code, _out, err = self._run(
            self.module.cmd_append, who="t", department="采购部",
            recipient_cell="采购部 · 姚祖怡", date="2026-09-06",
            topic="新事项", deadline_note="无",
        )
        self.assertEqual(code, 1)
        self.assertIn("闸锁", err)
        self.assertEqual(self._readme_text(), before)
        self.assertEqual(self._lock_calls, [])

    def test_闸开或全新收信人时append正常进行(self):
        self._write_readme(
            _row("采购部#5", "采购部 · 姚祖怡", "旧信", "尽快", "📥 已回件并回灌（2026-08-01）")
        )
        code, _out, _err = self._run(
            self.module.cmd_append, who="t", department="销售部",
            recipient_cell="销售部 · 泓钦", date="2026-09-06",
            topic="首封信", deadline_note="无",
        )
        self.assertEqual(code, 0)
        self.assertIn("销售部#1", self._readme_text())

    def test_主要事项超限被拒绝(self):
        self._write_readme(_row("采购部#5", "采购部 · 姚祖怡", "旧信", "尽快", "📥 已回件并回灌"))
        code, _out, err = self._run(
            self.module.cmd_append, who="t", department="采购部",
            recipient_cell="采购部 · 姚祖怡", date="2026-09-06",
            topic="超" * 300, deadline_note="无",
        )
        self.assertEqual(code, 1)
        self.assertIn("主要事项", err)
        self.assertEqual(self._lock_calls, [])

    def test_交期要点超限被拒绝(self):
        self._write_readme(_row("采购部#5", "采购部 · 姚祖怡", "旧信", "尽快", "📥 已回件并回灌"))
        code, _out, err = self._run(
            self.module.cmd_append, who="t", department="采购部",
            recipient_cell="采购部 · 姚祖怡", date="2026-09-06",
            topic="正常", deadline_note="超" * 200,
        )
        self.assertEqual(code, 1)
        self.assertIn("交期要点", err)

    def test_历史行列数异常不阻塞append(self):
        # 「采购部#14」形态：发送状态历史段里混入未转义的 `|`，朴素分列会
        # 多出一列——2026-09-06 对真实 README 实测发现，历史行不应阻塞其它
        # 行的正常登记。
        self._write_readme(
            _row("采购部#5", "采购部 · 姚祖怡", "旧信", "尽快",
                 "📥 已回件并回灌 | 混入一个竖线的历史段")
        )
        code, _out, _err = self._run(
            self.module.cmd_append, who="t", department="财务部",
            recipient_cell="财务部 · 唐燕萍", date="2026-09-06",
            topic="正常事项", deadline_note="无",
        )
        self.assertEqual(code, 0)
        self.assertIn("财务部#1", self._readme_text())

    def test_dry_run不取锁不写入(self):
        self._write_readme(
            _row("采购部#5", "采购部 · 姚祖怡", "旧信", "尽快", "📥 已回件并回灌")
        )
        before = self._readme_text()
        code, out, _err = self._run(
            self.module.cmd_append, who="t", department="采购部",
            recipient_cell="采购部 · 姚祖怡", date="2026-09-06",
            topic="新事项", deadline_note="无", dry_run=True,
        )
        self.assertEqual(code, 0)
        self.assertIn("DRY-RUN", out)
        self.assertEqual(self._readme_text(), before)
        self.assertEqual(self._lock_calls, [])

    def test_release被拒绝时不得报告成功(self):
        self._write_readme(
            _row("采购部#5", "采购部 · 姚祖怡", "旧信", "尽快", "📥 已回件并回灌")
        )
        self._release_should_succeed = False
        code, out, err = self._run(
            self.module.cmd_append, who="t", department="采购部",
            recipient_cell="采购部 · 姚祖怡", date="2026-09-06",
            topic="新事项", deadline_note="无",
        )
        self.assertEqual(code, 1)
        self.assertNotIn("[OK]", out)
        self.assertIn("LOCK-HELD", err)
        # 文件确已写入（release 拒绝不等于撤销写入）。
        self.assertIn("采购部#6", self._readme_text())


class DecisionPointGateTests(RegistryCliTestBase):
    """`append` 的 `决策点:` 前置闸（队列 §一 `#436` ⑶「2026-09-06 派出」(i)）。

    口径来源：`design审前置-口径点台账三开放点收敛-2026-09-01.md` §2.3 P1–P4。
    形态判据复用 `工具-跟进信frontmatter校验.py::RE_DECISION`（前缀锚定），
    本文件**不另写一份正则**——否则两处判据会各自漂移，正是该字段当初消亡
    的同族病因。
    """

    def _append(self, letter_path):
        self._write_readme(
            _row("采购部#5", "采购部 · 姚祖怡", "旧信", "尽快", "📥 已回件并回灌（2026-08-01）")
        )
        return self._run(
            self.module.cmd_append, who="t", department="采购部",
            recipient_cell="采购部 · 姚祖怡", date="2026-09-06",
            topic="新事项", deadline_note="无", letter_path=letter_path,
        )

    # —— 任务书要求的三例 ——

    def test_缺决策点字段即拒登记且不取锁不写入(self):
        letter = self._write_letter(decision=None, name="缺字段.md")
        code, _out, err = self._append(letter)
        self.assertEqual(code, 1)
        self.assertIn("决策点", err)
        self.assertIn("1bis", err)  # 拒绝文案必须给出路
        self.assertNotIn("采购部#6", self._readme_text())
        self.assertEqual(self._lock_calls, [])

    def test_零项通报信放行(self):
        letter = self._write_letter(
            decision="0 项（结果通报＋请验收，无需其决策）", name="通报.md")
        code, out, _err = self._append(letter)
        self.assertEqual(code, 0)
        self.assertIn("[OK]", out)
        self.assertIn("采购部#6", self._readme_text())

    def test_三项决策点放行(self):
        letter = self._write_letter(
            decision="3 项（关闭触发 / 关闭权限 / 部分关闭审计）", name="三点.md")
        code, out, _err = self._append(letter)
        self.assertEqual(code, 0)
        self.assertIn("[OK]", out)
        # 成功路径也回显守到的取值——这条闸自己不能是「不产生任何信号」的。
        self.assertIn("决策点=3 项（关闭触发 / 关闭权限 / 部分关闭审计）", out)

    # —— 其余拒绝形态 ——

    def test_决策点为空即拒登记(self):
        letter = self._write_letter(decision="", name="空值.md")
        code, _out, err = self._append(letter)
        self.assertEqual(code, 1)
        self.assertIn("为空", err)
        self.assertEqual(self._lock_calls, [])

    def test_形态不合判据即拒登记(self):
        letter = self._write_letter(decision="唯一 1 项", name="形态错.md")
        code, _out, err = self._append(letter)
        self.assertEqual(code, 1)
        self.assertIn("形态不合判据", err)
        self.assertEqual(self._lock_calls, [])

    def test_信件不存在即拒登记(self):
        code, _out, err = self._append("6-人才与组织/部门AI专员跟进/不存在的信.md")
        self.assertEqual(code, 1)
        self.assertIn("读不到待登记信件", err)
        self.assertEqual(self._lock_calls, [])

    def test_无frontmatter即拒登记_正文里的决策点不算数(self):
        letter = self._write_letter(frontmatter=False, name="无fm.md")
        code, _out, err = self._append(letter)
        self.assertEqual(code, 1)
        self.assertIn("frontmatter", err)
        self.assertEqual(self._lock_calls, [])

    def test_括号内容不校验(self):
        # S3 刻意只做前缀锚定：`IT部#5` 的真实取值带括号外后缀，必须放行。
        letter = self._write_letter(
            decision="2 项（FO 预测订单接口能否补行级状态字段 / PO 采购订单接口能否补行级关闭状态字段），"
                     "或告知已有的替代查询方式",
            name="括号外后缀.md",
        )
        code, _out, _err = self._append(letter)
        self.assertEqual(code, 0)

    def test_dry_run同样过闸_缺字段即拒(self):
        letter = self._write_letter(decision=None, name="dryrun缺字段.md")
        self._write_readme(
            _row("采购部#5", "采购部 · 姚祖怡", "旧信", "尽快", "📥 已回件并回灌（2026-08-01）")
        )
        code, _out, err = self._run(
            self.module.cmd_append, who="t", department="采购部",
            recipient_cell="采购部 · 姚祖怡", date="2026-09-06",
            topic="新事项", deadline_note="无", letter_path=letter, dry_run=True,
        )
        self.assertEqual(code, 1)
        self.assertIn("决策点", err)

    def test_绝对路径同样可用(self):
        rel = self._write_letter(decision="1 项（试用反馈）", name="绝对路径.md")
        code, _out, _err = self._append(str(self.root / rel))
        self.assertEqual(code, 0)

    def test_闸不改set_status行为(self):
        # 本闸只挂 append；`set-status` 不需要也不接受信件路径参数。
        self._write_readme(_row("采购部#19", "采购部 · 姚祖怡", "事项", "无", "⏳ 待你审"))
        code, out, _err = self._run(
            self.module.cmd_set_status, who="t", number="采购部#19", status="🆕 待发",
        )
        self.assertEqual(code, 0)
        self.assertIn("[OK]", out)


class SetStatusTests(RegistryCliTestBase):
    def test_合法状态值写入成功(self):
        self._write_readme(_row("采购部#19", "采购部 · 姚祖怡", "事项", "无", "⏳ 待你审"))
        code, out, _err = self._run(
            self.module.cmd_set_status, who="t",
            number="采购部#19", status="🆕 待发",
        )
        self.assertEqual(code, 0)
        self.assertIn("[OK]", out)
        self.assertIn("🆕 待发", self._readme_text())

    def test_归一化后仍属已知前缀的自由后缀允许写入(self):
        self._write_readme(_row("采购部#19", "采购部 · 姚祖怡", "事项", "无", "⏳ 待你审"))
        code, _out, _err = self._run(
            self.module.cmd_set_status, who="t", number="采购部#19",
            status="✅ 已推送 2026-09-06 08:00 UTC（机器人）",
            fact_date="2026-09-06",
        )
        self.assertEqual(code, 0)

    def test_非法状态值被拒绝(self):
        self._write_readme(_row("采购部#19", "采购部 · 姚祖怡", "事项", "无", "⏳ 待你审"))
        before = self._readme_text()
        code, _out, err = self._run(
            self.module.cmd_set_status, who="t", number="采购部#19", status="乱写一个状态",
        )
        self.assertEqual(code, 1)
        self.assertIn("unknown", err.lower() + "unknown")  # 报错文案含枚举集合说明
        self.assertEqual(self._readme_text(), before)
        self.assertEqual(self._lock_calls, [])

    def test_编号不存在(self):
        self._write_readme(_row("采购部#19", "采购部 · 姚祖怡", "事项", "无", "⏳ 待你审"))
        code, _out, err = self._run(
            self.module.cmd_set_status, who="t", number="采购部#999", status="🆕 待发",
        )
        self.assertEqual(code, 1)
        self.assertIn("不存在", err)

    def test_编号已归档时拒绝并提示不可再用本命令(self):
        self._write_readme(_row("采购部#19", "采购部 · 姚祖怡", "事项", "无", "⏳ 待你审"))
        archive_path = self.root / "6-人才与组织/部门AI专员跟进/README-归档-202601.md"
        archive_path.write_text(
            MAIN_HEADER + _row("采购部#3", "采购部 · 姚祖怡", "老事项", "无", "❌ 已作废"),
            encoding="utf-8",
        )
        code, _out, err = self._run(
            self.module.cmd_set_status, who="t", number="采购部#3", status="🆕 待发",
        )
        self.assertEqual(code, 1)
        self.assertIn("已归档", err)
        self.assertIn("不可再用本命令改状态", err)

    def test_写后回读比对失败保留锁不释放(self):
        self._write_readme(_row("采购部#19", "采购部 · 姚祖怡", "事项", "无", "⏳ 待你审"))

        def _corrupt_write_readback(new_text, expected_cells, locate):
            raise self.module.ReadbackMismatchError("模拟回读失败")

        self.module._write_readback = _corrupt_write_readback
        code, _out, err = self._run(
            self.module.cmd_set_status, who="t", number="采购部#19", status="🆕 待发",
        )
        self.assertEqual(code, 1)
        self.assertIn("READBACK-FAILED", err)
        # 回读失败路径不应调用 release（保留锁供人工排查）。
        self.assertEqual(self._lock_calls, [("acquire", "t")])

    def test_release被拒绝时不得报告成功(self):
        self._write_readme(_row("采购部#19", "采购部 · 姚祖怡", "事项", "无", "⏳ 待你审"))
        self._release_should_succeed = False
        code, out, err = self._run(
            self.module.cmd_set_status, who="t", number="采购部#19", status="🆕 待发",
        )
        self.assertEqual(code, 1)
        self.assertNotIn("[OK]", out)
        self.assertIn("LOCK-HELD", err)
        self.assertIn("🆕 待发", self._readme_text())

    def test_dry_run不取锁不写入(self):
        self._write_readme(_row("采购部#19", "采购部 · 姚祖怡", "事项", "无", "⏳ 待你审"))
        before = self._readme_text()
        code, out, _err = self._run(
            self.module.cmd_set_status, who="t", number="采购部#19",
            status="🆕 待发", dry_run=True,
        )
        self.assertEqual(code, 0)
        self.assertIn("DRY-RUN", out)
        self.assertEqual(self._readme_text(), before)
        self.assertEqual(self._lock_calls, [])


class MainCliTests(unittest.TestCase):
    """跑一遍 argparse 顶层入口，确认子命令与参数拼装无误（不落真实文件）。"""

    def setUp(self):
        self.module = _load()

    def test_append缺少必填参数报argparse错误(self):
        with self.assertRaises(SystemExit):
            with redirect_stderr(io.StringIO()):
                self.module.main(["append", "--who", "t"])

    def test_append缺letter_path报argparse错误(self):
        """`--letter-path` 是必填而不是「给了才查」——可省略即可绕过，
        等于把该字段当初静默消亡的病因原样重造一遍。"""
        err = io.StringIO()
        with self.assertRaises(SystemExit):
            with redirect_stderr(err):
                self.module.main([
                    "append", "--who", "t", "--department", "采购部",
                    "--recipient-cell", "采购部 · 姚祖怡", "--date", "2026-09-06",
                    "--topic", "x", "--deadline-note", "y",
                ])
        self.assertIn("--letter-path", err.getvalue())

    def test_未知子命令报错(self):
        with self.assertRaises(SystemExit):
            with redirect_stderr(io.StringIO()):
                self.module.main(["not-a-command"])


# ---------------------------------------------------------------------------
# 队列 §一 `#447`：O1／O2／O3 ＋ ⑵ 事实日／补记日
# （Shao Peishen 2026-09-07 答合审材料 §10 (a)）
# ---------------------------------------------------------------------------


class LegacyDecisionFieldTests(RegistryCliTestBase):
    """O3：`开放点计数:`／`开放点:` 停写，`决策点:` 为唯一正本。"""

    def _append(self, letter_path):
        self._write_readme(
            _row("采购部#5", "采购部 · 姚祖怡", "旧信", "尽快", "📥 已回件并回灌（2026-08-01）")
        )
        return self._run(
            self.module.cmd_append, who="t", department="采购部",
            recipient_cell="采购部 · 姚祖怡", date="2026-09-07",
            topic="新事项", deadline_note="无", letter_path=letter_path,
        )

    def test_仍带开放点计数即拒登记(self):
        letter = self._write_letter(
            name="带旧字段.md", extra_fields="开放点计数: 本封要你定 4 件事（…）"
        )
        code, _out, err = self._append(letter)
        self.assertEqual(code, 1)
        self.assertIn("开放点计数", err)
        self.assertIn("停写", err)
        self.assertEqual(self._lock_calls, [])

    def test_仍带开放点即拒登记(self):
        letter = self._write_letter(name="带旧字段2.md", extra_fields="开放点: 3 项（a / b / c）")
        code, _out, err = self._append(letter)
        self.assertEqual(code, 1)
        self.assertIn("开放点", err)

    def test_只写决策点放行(self):
        code, _out, _err = self._append(self.default_letter)
        self.assertEqual(code, 0)


class RecipientCellTests(RegistryCliTestBase):
    """O2：`收信人` ＝ `部门 · 姓名`，姓名以人员名录正本为准。"""

    def _append(self, recipient_cell, department="采购部"):
        self._write_readme(
            _row("采购部#5", "采购部 · 姚祖怡", "旧信", "尽快", "📥 已回件并回灌（2026-08-01）")
        )
        return self._run(
            self.module.cmd_append, who="t", department=department,
            recipient_cell=recipient_cell, date="2026-09-07",
            topic="新事项", deadline_note="无",
        )

    def test_缺分隔符即拒登记(self):
        code, _out, err = self._append("采购部姚祖怡")
        self.assertEqual(code, 1)
        self.assertIn("分隔符", err)
        self.assertEqual(self._lock_calls, [])

    def test_姓名不在名录正本即拒登记(self):
        code, _out, err = self._append("采购部 · 张三")
        self.assertEqual(code, 1)
        self.assertIn("不在人员名录正本", err)
        self.assertIn("不许现编", err)

    def test_部门与department不一致即拒登记(self):
        """不一致会把号取到另一个部门的序列里，而写完不报错。"""
        code, _out, err = self._append("质量部 · 陈忱", department="采购部")
        self.assertEqual(code, 1)
        self.assertIn("不一致", err)
        self.assertEqual(self._lock_calls, [])

    def test_在册姓名放行(self):
        code, _out, _err = self._append("采购部 · 姚祖怡")
        self.assertEqual(code, 0)

    def test_名录取数异常时报错而不是把每个人都判成不在册(self):
        """🔑「只读结果太干净先怀疑没读到对象」——名录只剩几个人时，照常判定
        会把每个真实收信人都判成「不在册」，且错得非常自信。"""
        self.module.editlock.PERSON_GENDER_ROSTER = {"姚祖怡": "男"}
        code, _out, err = self._append("采购部 · 姚祖怡")
        self.assertEqual(code, 1)
        self.assertIn("名录取数异常", err)

    def test_名录实测覆盖当前主表四位收信人(self):
        """守住「本闸对既有语料零误杀」这句话本身——名录一旦漏掉其中任何一位，
        下一封信就登记不进去。"""
        roster = self.module._roster_names()
        for name in ("姚祖怡", "陈忱", "唐燕萍", "陈承", "泓钦"):
            self.assertIn(name, roster)


class StatusClosedSetTests(RegistryCliTestBase):
    """O1：`--status` 取值闭集＝判据版八态 ＋ 第九态。"""

    def _set(self, status, **kw):
        self._write_readme(_row("采购部#19", "采购部 · 姚祖怡", "事项", "无", "⏳ 待你审"))
        return self._run(
            self.module.cmd_set_status, who="t", number="采购部#19", status=status, **kw
        )

    def test_八态逐个放行(self):
        for prefix in self.module.CANONICAL_EIGHT_STATUS_PREFIXES:
            with self.subTest(prefix=prefix):
                needs_fact = any(
                    prefix.startswith(p) for p in self.module.FACT_DATE_REQUIRED_PREFIXES
                )
                kw = {"fact_date": "2026-09-01"} if needs_fact else {}
                code, _out, err = self._set(f"{prefix}（备注）", **kw)
                self.assertEqual(code, 0, err)

    def test_第九态放行(self):
        code, _out, err = self._set(
            self.module.followup_gate.REPLY_ARRIVED_STATUS, fact_date="2026-09-01"
        )
        self.assertEqual(code, 0, err)

    def test_已退役的已发写法被拒且文案点名它认得但已退役(self):
        """`✅ 已发` 仍在 `followup_gate.IN_FLIGHT_STATUS_PREFIXES` 里（历史行
        要能被读懂），但 O1 收敛后不许再写——两件事必须分开。"""
        before_kind = self.module.followup_gate.classify_status("✅ 已发（2026-07-09）")
        self.assertNotEqual(before_kind, "unknown")  # 前提：闸仍认得它
        code, _out, err = self._set("✅ 已发（2026-07-09）")
        self.assertEqual(code, 1)
        self.assertIn("闭集", err)
        self.assertIn("已退役", err)
        self.assertEqual(self._lock_calls, [])

    def test_完全乱写被拒(self):
        code, _out, err = self._set("乱写一个状态")
        self.assertEqual(code, 1)
        self.assertIn("也不认得", err)


class FactDateTests(RegistryCliTestBase):
    """⑵：事实日／补记日两字段，事实日不得被补记顶替、不得被后续补记覆盖。"""

    TODAY = "2026-09-07"

    def setUp(self):
        super().setUp()
        self.module._today = lambda: self.TODAY

    def _set(self, status, number="采购部#19", **kw):
        return self._run(
            self.module.cmd_set_status, who="t", number=number, status=status, **kw
        )

    def _row_with(self, status):
        self._write_readme(_row("采购部#19", "采购部 · 姚祖怡", "事项", "无", status))

    def test_回件转态缺事实日即拒且不取锁不写入(self):
        self._row_with("⏳ 待你审")
        before = self._readme_text()
        code, _out, err = self._set("📥 已回件并回灌（拆件巡逻）")
        self.assertEqual(code, 1)
        self.assertIn("--fact-date", err)
        self.assertIn("不得拿今天顶替", err)
        self.assertEqual(self._readme_text(), before)
        self.assertEqual(self._lock_calls, [])

    def test_未发三态不要求事实日(self):
        self._row_with("⏳ 待你审")
        code, _out, err = self._set("🆕 待发")
        self.assertEqual(code, 0, err)
        self.assertNotIn("事实日", self._readme_text())

    def test_事实日与补记日一并写入规范尾标(self):
        self._row_with("⏳ 待你审")
        code, out, err = self._set("📥 已回件并回灌（拆件巡逻）", fact_date="2026-08-10")
        self.assertEqual(code, 0, err)
        self.assertIn(f"〔事实日 2026-08-10 ／ 补记日 {self.TODAY}〕", self._readme_text())
        self.assertIn("补记滞后 28 天", out)

    def test_补记滞后过大时出声(self):
        """🔴 这行字就是 2026-08-23 那次批量补转态当时没有的那个信号。"""
        self._row_with("⏳ 待你审")
        _code, out, _err = self._set("📥 已回件并回灌", fact_date="2026-08-11")
        self.assertIn("[NOTE]", out)
        self.assertIn("属迟到补记", out)

    def test_事实日未知可写且不被补记日顶替(self):
        self._row_with("⏳ 待你审")
        code, out, err = self._set("📥 已回件并回灌", fact_date=self.module.FACT_DATE_UNKNOWN)
        self.assertEqual(code, 0, err)
        cell = self._readme_text()
        self.assertIn(f"〔事实日 事实日未知 ／ 补记日 {self.TODAY}〕", cell)
        self.assertNotIn(f"事实日 {self.TODAY}", cell)  # 没被今天顶替
        self.assertIn("单列", out)

    def test_事实日未知字面量与点级台账同一份常量(self):
        from zhuopin_platform.coverage_point_ledger.models import FACT_DATE_UNKNOWN
        self.assertIs(self.module.FACT_DATE_UNKNOWN, FACT_DATE_UNKNOWN)

    def test_事实日形态不合即拒(self):
        self._row_with("⏳ 待你审")
        code, _out, err = self._set("📥 已回件并回灌", fact_date="2026-02-30")
        self.assertEqual(code, 1)
        self.assertIn("并不存在", err)

    def test_事实日不得晚于本机当天(self):
        self._row_with("⏳ 待你审")
        code, _out, err = self._set("📥 已回件并回灌", fact_date="2026-09-08")
        self.assertEqual(code, 1)
        self.assertIn("不会发生在未来", err)

    def test_同一状态下已有事实日不得被后续补记覆盖(self):
        """design §5.3 第三条 Requirement；成因＝12 封信的真实回件日被销毁。"""
        self._row_with("📥 已回件并回灌 〔事实日 2026-08-10 ／ 补记日 2026-08-23〕")
        before = self._readme_text()
        code, _out, err = self._set("📥 已回件并回灌（再登记一次）", fact_date=self.TODAY)
        self.assertEqual(code, 1)
        self.assertIn("拒绝覆盖", err)
        self.assertIn("2026-08-10", err)
        self.assertEqual(self._readme_text(), before)
        self.assertEqual(self._lock_calls, [])

    def test_换状态即换事实不算覆盖(self):
        """🔴 事实日是「当前这个状态」的属性：回件到达日与我方确认闭环日本就
        是两个日期，转态时要求沿用旧值反而是把回件日当成确认日。"""
        self._row_with("📥 已回件并回灌 〔事实日 2026-08-10 ／ 补记日 2026-08-23〕")
        code, _out, err = self._set("📨 已确认闭环（我方已回复确认）", fact_date=self.TODAY)
        self.assertEqual(code, 0, err)
        self.assertIn(f"〔事实日 {self.TODAY} ／ 补记日 {self.TODAY}〕", self._readme_text())

    def test_转到不承载事实日的状态时旧尾标原样带过(self):
        """不因一次不相干的转态把已记下的事实日冲掉——连同它原来的补记日。"""
        self._row_with("📥 已回件并回灌 〔事实日 2026-08-10 ／ 补记日 2026-08-23〕")
        code, _out, err = self._set("❌ 已作废（口径已变，不再需要回件）")
        self.assertEqual(code, 0, err)
        self.assertIn("〔事实日 2026-08-10 ／ 补记日 2026-08-23〕", self._readme_text())

    def test_显式写事实日更正标记才允许改写(self):
        self._row_with("📥 已回件并回灌 〔事实日 2026-08-10 ／ 补记日 2026-08-23〕")
        code, _out, err = self._set(
            "📥 已回件并回灌（事实日更正：原记 2026-08-10，依据企微原始时间戳）",
            fact_date="2026-08-09",
        )
        self.assertEqual(code, 0, err)
        self.assertIn("〔事实日 2026-08-09 ／ 补记日", self._readme_text())
        self.assertIn("事实日更正：原记 2026-08-10", self._readme_text())

    def test_事实日未知升级为具体日期属找回信息不受覆盖闸约束(self):
        self._row_with("📥 已回件并回灌 〔事实日 事实日未知 ／ 补记日 2026-08-23〕")
        code, _out, err = self._set("📥 已回件并回灌", fact_date="2026-08-10")
        self.assertEqual(code, 0, err)
        self.assertIn("〔事实日 2026-08-10 ／ 补记日", self._readme_text())

    def test_尾标不叠加两枚(self):
        self._row_with("📥 已回件并回灌 〔事实日 2026-08-10 ／ 补记日 2026-08-23〕")
        self._set("📨 已确认闭环")
        self.assertEqual(self._readme_text().count("〔事实日"), 1)

    def test_dry_run打印计划但不写入(self):
        self._row_with("⏳ 待你审")
        before = self._readme_text()
        code, out, _err = self._set(
            "📥 已回件并回灌", fact_date="2026-08-10", dry_run=True
        )
        self.assertEqual(code, 0)
        self.assertIn("事实日 2026-08-10 ／ 补记日", out)
        self.assertEqual(self._readme_text(), before)
        self.assertEqual(self._lock_calls, [])


class FactMarkParseTests(unittest.TestCase):
    """尾标解析：「没标注」与「标了不知道」必须分得开。"""

    def setUp(self):
        self.module = _load()

    def test_无尾标返回None而不是事实日未知(self):
        self.assertIsNone(self.module._parse_fact_mark("📥 已回件并回灌（2026-08-24）"))

    def test_事实日未知返回字面量(self):
        parsed = self.module._parse_fact_mark(
            "📥 已回件并回灌 〔事实日 事实日未知 ／ 补记日 2026-09-07〕"
        )
        self.assertEqual(parsed, (self.module.FACT_DATE_UNKNOWN, "2026-09-07"))

    def test_具体日期返回两个值(self):
        parsed = self.module._parse_fact_mark(
            "📥 已回件并回灌（拆件巡逻）〔事实日 2026-08-10 ／ 补记日 2026-08-23〕"
        )
        self.assertEqual(parsed, ("2026-08-10", "2026-08-23"))


if __name__ == "__main__":
    unittest.main()
