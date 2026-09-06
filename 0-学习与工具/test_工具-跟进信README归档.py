"""`工具-跟进信README归档.py` 单测（`followup-readme-phase2` D2，队列 §一 `#490`）。

白盒方式：按文件路径 importlib 加载被测脚本（本目录既定手法），把 `REPO_ROOT`
指向临时夹具目录——**不触碰真实 README**。`_run_lock` 统一 monkeypatch 为
受控桩，理由同 `test_工具-跟进信README登记.py`。
"""
from __future__ import annotations

import datetime
import importlib.util
import io
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

SCRIPT = Path(__file__).resolve().with_name("工具-跟进信README归档.py")
README_REL = "6-人才与组织/部门AI专员跟进/README-跟进机制与命名约定.md"

MAIN_HEADER = (
    "## 现有跟进信清单\n\n"
    "| 编号 | 日期 | 收信人 | 主要事项 | 交期要点 | 发送状态（2026-07-06） |\n"
    "|--------|------|--------|---------|---------|---------|\n"
)

TODAY = datetime.date(2026, 9, 6)


def _load():
    spec = importlib.util.spec_from_file_location("_followup_archive_under_test", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _row(number, date, recipient, topic, note, status):
    return f"| {number} | {date} | {recipient} | {topic} | {note} | {status} |\n"


class PlanMigrationTests(unittest.TestCase):
    def setUp(self):
        self.module = _load()

    def _plan(self, rows_text: str):
        return self.module.plan_migration(MAIN_HEADER + rows_text, TODAY)

    def test_终态超过30天的行入选(self):
        candidates = self._plan(
            _row("采购部#1", "2026-07-01", "采购部 · 姚祖怡", "事项", "无",
                 "📥 已回件并回灌（2026-07-10）")
        )
        self.assertEqual([c.cells[0] for c in candidates], ["采购部#1"])

    def test_已作废也算终态(self):
        candidates = self._plan(
            _row("采购部#1", "2026-07-01", "采购部 · 姚祖怡", "事项", "无", "❌ 已作废")
        )
        self.assertEqual(len(candidates), 1)

    def test_未满30天不入选(self):
        candidates = self._plan(
            _row("采购部#1", "2026-08-20", "采购部 · 姚祖怡", "事项", "无",
                 "📥 已回件并回灌（2026-08-20）")
        )
        self.assertEqual(candidates, [])

    def test_非终态不入选(self):
        candidates = self._plan(
            _row("采购部#1", "2026-07-01", "采购部 · 姚祖怡", "事项", "无",
                 "✅ 已推送 2026-07-01 08:00 UTC")
        )
        self.assertEqual(candidates, [])

    def test_无需回复与已确认闭环不在归档范围内(self):
        """派单件只点名 📥 已回件并回灌／❌ 已作废 两个前缀，
        不是全部四个闭环态——这里锁死范围不被悄悄扩大。"""
        candidates = self._plan(
            _row("质量部#1", "2026-07-01", "质量部 · 陈忱", "事项", "无", "✅ 无需回复")
            + _row("质量部#2", "2026-07-01", "质量部 · 陈忱", "事项", "无", "📨 已确认闭环 2026-07-02")
        )
        self.assertEqual(candidates, [])

    def test_日期列非法值跳过不迁(self):
        candidates = self._plan(
            _row("采购部#1", "不是日期", "采购部 · 姚祖怡", "事项", "无", "❌ 已作废")
        )
        self.assertEqual(candidates, [])

    def test_历史列数异常行不参与判定不报错(self):
        # 模拟 2026-09-06 实测的「采购部#14」形态：状态列混入未转义竖线，
        # 朴素分列多出一列——列数校验应静默跳过，不崩溃、不误判。
        broken = "| 采购部#14 | 2026-07-01 | 采购部 · 姚祖怡 | 事项 | 无 | 段一 | 段二 |\n"
        candidates = self._plan(broken)
        self.assertEqual(candidates, [])

    def test_未编号但已作废的行照样入选(self):
        candidates = self._plan(
            _row("销售部（未发，不编号）", "2026-07-01", "销售部 · 泓钦", "事项", "无", "❌ 已作废")
        )
        self.assertEqual(len(candidates), 1)


class BuildNewTextsTests(unittest.TestCase):
    def setUp(self):
        self.module = _load()

    def _rows(self, text: str):
        full = MAIN_HEADER + text
        return self.module.iter_rows(full), full

    def test_迁移行从主表移除并原文原样追加进归档(self):
        keep = _row("采购部#2", "2026-08-30", "采购部 · 姚祖怡", "在途", "无", "⏳ 待你审")
        move = _row("采购部#1", "2026-07-01", "采购部 · 姚祖怡", "旧事项", "无",
                    "📥 已回件并回灌（2026-07-10）")
        rows, full_text = self._rows(move + keep)
        candidates = [r for r in rows if r.cells[0] == "采购部#1"]
        new_readme, new_archive, moved = self.module.build_new_texts(
            full_text, None, candidates, 0
        )
        self.assertEqual([m.cells[0] for m in moved], ["采购部#1"])
        self.assertNotIn("采购部#1", new_readme)
        self.assertIn("采购部#2", new_readme, "未迁移的行必须原样保留")
        self.assertIn("采购部#1", new_archive)
        self.assertTrue(new_archive.startswith(MAIN_HEADER), "归档件表头须与主表一致")

    def test_重复运行时已在归档件里的编号不重复追加(self):
        move = _row("采购部#1", "2026-07-01", "采购部 · 姚祖怡", "旧事项", "无", "❌ 已作废")
        rows, full_text = self._rows(move)
        candidates = list(rows)
        existing_archive = MAIN_HEADER + move  # 该行已在归档件中（模拟重复运行）
        new_readme, new_archive, moved = self.module.build_new_texts(
            full_text, existing_archive, candidates, 0
        )
        self.assertEqual(moved, [], "已存在于归档件的编号不得重复迁移")
        self.assertEqual(new_archive.count("采购部#1"), 1)


class _FakeArgs:
    def __init__(self, **kwargs):
        self.dry_run = False
        for k, v in kwargs.items():
            setattr(self, k, v)


class RunIntegrationTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.module = _load()
        self.module.REPO_ROOT = self.root
        (self.root / README_REL).parent.mkdir(parents=True, exist_ok=True)
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

    def _run(self, **kwargs):
        args = _FakeArgs(**kwargs)
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = self.module.run(args, today=TODAY)
        return code, out.getvalue(), err.getvalue()

    def test_dry_run不取锁不写入(self):
        self._write_readme(
            _row("采购部#1", "2026-07-01", "采购部 · 姚祖怡", "事项", "无", "❌ 已作废")
        )
        before = self._readme_text()
        code, out, _err = self._run(dry_run=True)
        self.assertEqual(code, 0)
        self.assertIn("PLAN", out)
        self.assertEqual(self._readme_text(), before)
        self.assertEqual(self._lock_calls, [])

    def test_真实执行迁移一行并释放锁(self):
        self._write_readme(
            _row("采购部#2", "2026-08-30", "采购部 · 姚祖怡", "在途", "无", "⏳ 待你审")
            + _row("采购部#1", "2026-07-01", "采购部 · 姚祖怡", "旧事项", "无",
                   "📥 已回件并回灌（2026-07-10）")
        )
        code, out, _err = self._run(who="t")
        self.assertEqual(code, 0)
        self.assertIn("[OK]", out)
        self.assertNotIn("采购部#1", self._readme_text())
        self.assertIn("采购部#2", self._readme_text())
        archive_path = self.root / "6-人才与组织/部门AI专员跟进/README-归档-202609.md"
        self.assertTrue(archive_path.exists())
        self.assertIn("采购部#1", archive_path.read_text(encoding="utf-8"))
        self.assertEqual(self._lock_calls, [("acquire", "t"), ("release", "t")])

    def test_没有候选行时不取锁(self):
        self._write_readme(
            _row("采购部#1", "2026-08-30", "采购部 · 姚祖怡", "事项", "无", "⏳ 待你审")
        )
        code, out, _err = self._run(who="t")
        self.assertEqual(code, 0)
        self.assertIn("PLAN", out)
        self.assertEqual(self._lock_calls, [])

    def test_release被拒绝时报告写入但锁仍占用(self):
        self._write_readme(
            _row("采购部#1", "2026-07-01", "采购部 · 姚祖怡", "旧事项", "无", "❌ 已作废")
        )
        self._release_should_succeed = False
        code, out, err = self._run(who="t")
        self.assertEqual(code, 1)
        self.assertNotIn("[OK]", out)
        self.assertIn("LOCK-HELD", err)
        # 文件确已写入（release 拒绝不等于撤销写入）。
        self.assertNotIn("采购部#1", self._readme_text())

    def test_重复运行幂等不产生重复归档行(self):
        self._write_readme(
            _row("采购部#1", "2026-07-01", "采购部 · 姚祖怡", "旧事项", "无", "❌ 已作废")
        )
        code1, _out1, _err1 = self._run(who="t")
        self.assertEqual(code1, 0)
        # 模拟人为把行手动放回主表（正常不会发生，只为验证 dedup 生效）。
        self._write_readme(
            _row("采购部#1", "2026-07-01", "采购部 · 姚祖怡", "旧事项", "无", "❌ 已作废")
        )
        code2, out2, _err2 = self._run(who="t")
        self.assertEqual(code2, 0)
        archive_path = self.root / "6-人才与组织/部门AI专员跟进/README-归档-202609.md"
        self.assertEqual(archive_path.read_text(encoding="utf-8").count("采购部#1"), 1)


if __name__ == "__main__":
    unittest.main()
