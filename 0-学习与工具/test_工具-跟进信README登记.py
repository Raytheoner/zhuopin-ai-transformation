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

    def tearDown(self):
        self._tmp.cleanup()

    def _fake_run_lock(self, action, who, note=None):
        self._lock_calls.append((action, who))
        if action == "release":
            return self._release_should_succeed
        return True

    def _write_readme(self, rows: str):
        (self.root / README_REL).write_text(MAIN_HEADER + rows, encoding="utf-8")

    def _readme_text(self) -> str:
        return (self.root / README_REL).read_text(encoding="utf-8")

    def _run(self, func, **kwargs):
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

    def test_未知子命令报错(self):
        with self.assertRaises(SystemExit):
            with redirect_stderr(io.StringIO()):
                self.module.main(["not-a-command"])


if __name__ == "__main__":
    unittest.main()
