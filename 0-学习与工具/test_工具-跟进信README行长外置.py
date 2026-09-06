"""`工具-跟进信README行长外置.py` 单测（`followup-readme-phase2` D3，队列 §一 `#490`）。

白盒方式：按文件路径 importlib 加载被测脚本（本目录既定手法），把 `REPO_ROOT`
指向临时夹具目录——**不触碰真实 README**。`_run_lock` 统一 monkeypatch 为
受控桩，理由同 `test_工具-跟进信README归档.py`。
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

SCRIPT = Path(__file__).resolve().with_name("工具-跟进信README行长外置.py")
README_REL = "6-人才与组织/部门AI专员跟进/README-跟进机制与命名约定.md"
LOG_DIR_REL = "6-人才与组织/部门AI专员跟进/跟进信行日志"

MAIN_HEADER = (
    "## 现有跟进信清单\n\n"
    "| 编号 | 日期 | 收信人 | 主要事项 | 交期要点 | 发送状态（2026-07-06） |\n"
    "|--------|------|--------|---------|---------|---------|\n"
)
# `_validate_followup_readme_release`（队列 #399 决策点 3(b)）要求两张表的
# 章节标题必须同时在位——`RunIntegrationTests` 会真的跑到 release（含本包
# 新增的串行闸冲突消解），故其夹具须带上补件表章节，纯函数测试
# （`PlanExternalizationTests` 等只调 `plan_externalization`，不经过
# release 校验）不受影响、无需改动。
SUPPLEMENT_HEADER = (
    "\n## 补件登记（不占编号、不占串行闸）\n\n"
    "| 承接编号 | 日期 | 收信人 | 主要事项 | 需回复 | 发送状态 |\n"
    "|---------|------|--------|---------|--------|---------|\n"
)

TODAY = datetime.date(2026, 9, 6)


def _load():
    spec = importlib.util.spec_from_file_location("_followup_rowlength_under_test", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _row(number, date, recipient, topic, note, status):
    return f"| {number} | {date} | {recipient} | {topic} | {note} | {status} |\n"


class BuildTopicSummaryTests(unittest.TestCase):
    def setUp(self):
        self.module = _load()

    def test_取首句加指针(self):
        text = "第一句话。第二句话第二句话第二句话。"
        summary = self.module.build_topic_summary(text, "采购部#1")
        self.assertTrue(summary.startswith("第一句话。"))
        self.assertIn("详见", summary)
        self.assertIn("跟进信行日志/采购部#1.md", summary)

    def test_首句过长时取前200字(self):
        text = ("填" * 300) + "。"  # 单句 300 字，超过 200 字上限
        summary = self.module.build_topic_summary(text, "采购部#1")
        # 摘要的正文部分（去掉指针）不应超过 200 个原始字符。
        pointer = self.module._pointer_note("采购部#1")
        body = summary[: -len(pointer)] if summary.endswith(pointer) else summary
        self.assertLessEqual(len(body), self.module.SUMMARY_FIRST_SENTENCE_CHAR_CAP)

    def test_摘要本身不超过阈值(self):
        text = ("填" * 300) + "。"
        summary = self.module.build_topic_summary(text, "财务部#16")
        self.assertLessEqual(len(summary.encode("utf-8")), self.module.TOPIC_CAP_BYTES)

    def test_无句末标点时整体当首句处理(self):
        text = "没有句末标点的一整段文字"
        summary = self.module.build_topic_summary(text, "采购部#1")
        self.assertIn("没有句末标点的一整段文字", summary)


class BuildStatusCompactTests(unittest.TestCase):
    def setUp(self):
        self.module = _load()

    def test_按分隔符取首段与末段(self):
        sep = self.module.SEGMENT_SEP
        text = f"首段内容{sep}中段一{sep}中段二{sep}末段内容"
        compact = self.module.build_status_compact(text, "财务部#16")
        self.assertIn("首段内容", compact)
        self.assertIn("末段内容", compact)
        self.assertNotIn("中段一", compact)
        self.assertIn("详见", compact)

    def test_压缩结果不超过上限(self):
        sep = self.module.SEGMENT_SEP
        text = ("首段" + "填" * 2000) + sep + ("末段" + "填" * 2000)
        compact = self.module.build_status_compact(text, "财务部#16")
        self.assertLessEqual(len(compact.encode("utf-8")), self.module.ROW_LENGTH_CAP_BYTES)

    def test_无分隔符时退化为截断加指针(self):
        text = "填" * 2000  # 无 ━━━，连续文本
        compact = self.module.build_status_compact(text, "财务部#16")
        self.assertIn("详见", compact)
        self.assertLessEqual(len(compact.encode("utf-8")), self.module.ROW_LENGTH_CAP_BYTES)


class PlanExternalizationTests(unittest.TestCase):
    def setUp(self):
        self.module = _load()

    def _plan(self, rows_text: str):
        return self.module.plan_externalization(MAIN_HEADER + rows_text)

    def test_主要事项超阈值入选(self):
        long_topic = "事项：" + ("填" * 250)  # ≈750 B > 600 B
        actions = self._plan(
            _row("采购部#1", "2026-08-01", "采购部 · 姚祖怡", long_topic, "无", "⏳ 待你审")
        )
        self.assertEqual(len(actions), 1)
        self.assertEqual(actions[0].column, "主要事项")

    def test_发送状态超阈值入选(self):
        long_status = "⏳ 待你审｜" + ("填" * 1500)  # ≈4500+ B > 4096 B
        actions = self._plan(
            _row("采购部#1", "2026-08-01", "采购部 · 姚祖怡", "短事项", "无", long_status)
        )
        self.assertEqual(len(actions), 1)
        self.assertEqual(actions[0].column, "发送状态")

    def test_同一行两列均超阈值时各成一项(self):
        long_topic = "事项：" + ("填" * 250)
        long_status = "⏳ 待你审｜" + ("填" * 1500)
        actions = self._plan(
            _row("财务部#16", "2026-08-01", "财务部 · 唐燕萍", long_topic, "无", long_status)
        )
        self.assertEqual({a.column for a in actions}, {"主要事项", "发送状态"})

    def test_均在阈值内不入选(self):
        actions = self._plan(
            _row("采购部#1", "2026-08-01", "采购部 · 姚祖怡", "短事项", "无", "⏳ 待你审")
        )
        self.assertEqual(actions, [])

    def test_带真实豁免标记的行跳过外置(self):
        long_topic = ("行长豁免：本行暂留，K2 同族豁免｜事项：") + ("填" * 250)
        actions = self._plan(
            _row("采购部#1", "2026-08-01", "采购部 · 姚祖怡", long_topic, "无", "⏳ 待你审")
        )
        self.assertEqual(actions, [], "真实逃生阀标记应使本工具跳过该列，不越权外置")

    def test_仅提及占位符不构成豁免仍入选(self):
        long_topic = ("逃生阀写法说明：行长豁免：<理由>｜事项：") + ("填" * 250)
        actions = self._plan(
            _row("采购部#1", "2026-08-01", "采购部 · 姚祖怡", long_topic, "无", "⏳ 待你审")
        )
        self.assertEqual(len(actions), 1)

    def test_历史列数异常行不参与判定不报错(self):
        broken = "| 采购部#14 | 2026-07-01 | 采购部 · 姚祖怡 | 事项 | 无 | 段一 | 段二 |\n"
        actions = self._plan(broken)
        self.assertEqual(actions, [])


class _FakeArgs:
    def __init__(self, **kwargs):
        self.dry_run = False
        self.file = README_REL
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

    def _fake_run_lock(self, target_file, action, who, note=None):
        self._lock_calls.append((action, who))
        if action == "release":
            return self._release_should_succeed
        return True

    def _write_readme(self, rows: str):
        (self.root / README_REL).write_text(
            MAIN_HEADER + rows + SUPPLEMENT_HEADER, encoding="utf-8"
        )

    def _readme_text(self) -> str:
        return (self.root / README_REL).read_text(encoding="utf-8")

    def _run(self, **kwargs):
        args = _FakeArgs(**kwargs)
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = self.module.run(args, today=TODAY)
        return code, out.getvalue(), err.getvalue()

    def test_dry_run不取锁不写入(self):
        long_topic = "事项：" + ("填" * 250)
        self._write_readme(
            _row("采购部#1", "2026-08-01", "采购部 · 姚祖怡", long_topic, "无", "⏳ 待你审")
        )
        before = self._readme_text()
        code, out, _err = self._run(dry_run=True)
        self.assertEqual(code, 0)
        self.assertIn("PLAN", out)
        self.assertEqual(self._readme_text(), before)
        self.assertEqual(self._lock_calls, [])

    def test_真实执行外置主要事项并写日志文件(self):
        long_topic = "第一句话。" + ("填" * 250)
        self._write_readme(
            _row("采购部#1", "2026-08-01", "采购部 · 姚祖怡", long_topic, "无", "⏳ 待你审")
        )
        code, out, _err = self._run(who="t")
        self.assertEqual(code, 0)
        self.assertIn("[OK]", out)
        new_text = self._readme_text()
        self.assertNotIn(long_topic, new_text)
        self.assertIn("第一句话。", new_text)
        log_path = self.root / LOG_DIR_REL / "采购部#1.md"
        self.assertTrue(log_path.exists())
        log_text = log_path.read_text(encoding="utf-8")
        self.assertIn(long_topic, log_text)
        self.assertIn("title:", log_text)
        self.assertEqual(self._lock_calls, [("acquire", "t"), ("release", "t")])

    def test_同一行两列都外置写入同一日志文件两个小节(self):
        long_topic = "事项：" + ("填" * 250)
        long_status = "⏳ 待你审｜" + ("填" * 1500)
        self._write_readme(
            _row("财务部#16", "2026-08-01", "财务部 · 唐燕萍", long_topic, "无", long_status)
        )
        code, out, _err = self._run(who="t")
        self.assertEqual(code, 0)
        log_path = self.root / LOG_DIR_REL / "财务部#16.md"
        log_text = log_path.read_text(encoding="utf-8")
        self.assertIn("发送状态列外置前原文", log_text)
        self.assertIn("主要事项列外置前原文", log_text)
        self.assertIn(long_topic, log_text)
        self.assertIn(long_status, log_text)

    def test_没有候选行时不取锁(self):
        self._write_readme(
            _row("采购部#1", "2026-08-01", "采购部 · 姚祖怡", "短事项", "无", "⏳ 待你审")
        )
        code, out, _err = self._run(who="t")
        self.assertEqual(code, 0)
        self.assertIn("PLAN", out)
        self.assertEqual(self._lock_calls, [])

    def test_release被拒绝时报告写入但锁仍占用(self):
        long_topic = "事项：" + ("填" * 250)
        self._write_readme(
            _row("采购部#1", "2026-08-01", "采购部 · 姚祖怡", long_topic, "无", "⏳ 待你审")
        )
        self._release_should_succeed = False
        code, out, err = self._run(who="t")
        self.assertEqual(code, 1)
        self.assertNotIn("[OK]", out)
        self.assertIn("LOCK-HELD", err)
        self.assertNotIn(long_topic, self._readme_text())

    def test_重复运行幂等不重复外置(self):
        long_topic = "事项：" + ("填" * 250)
        self._write_readme(
            _row("采购部#1", "2026-08-01", "采购部 · 姚祖怡", long_topic, "无", "⏳ 待你审")
        )
        code1, _out1, _err1 = self._run(who="t")
        self.assertEqual(code1, 0)
        code2, out2, _err2 = self._run(who="t")
        self.assertEqual(code2, 0)
        self.assertIn("没有满足", out2)
        log_path = self.root / LOG_DIR_REL / "采购部#1.md"
        # 第二次运行未产生新的候选，不应再追加一次同款小节。
        self.assertEqual(log_path.read_text(encoding="utf-8").count("主要事项列外置前原文"), 1)


class SerialGateConflictResolutionTests(RunIntegrationTests):
    """2026-09-06 对生产 README 真实执行时撞见的真实缺口：压缩「主要事项」
    列改变了 `_followup_row_identity`，若该行不是其收信人当前最新一封、
    且真正最新一封仍未闭环，跟进信串行原则闸会把这次**纯历史内容压缩**
    误判成"新起草的跟进信"而拒绝 release。复用 `RunIntegrationTests` 的
    全部 fixture（同一个类体系，只加这一组场景）。
    """

    def test_压缩历史行触发串行闸误判时自动追加豁免并成功release(self):
        long_topic = "事项：" + ("填" * 250)
        # 采购部 · 姚祖怡：#1 是较早一封（未闭环）、#2 是真正最新一封
        # （同样未闭环）——压缩 #1 的主要事项会让 #1"看起来像新增行"，
        # 串行闸据此回查"前一封"（#2？不，闸按表格顺序找排在它之前的
        # 那一封，此处 #1 本身就是首封，故不会误报——需要构造"中间行"
        # 场景：#1（首封，闭环）→ #2（中间，待压缩，未闭环）→ #3（最新，
        # 未闭环）；压缩 #2 后串行闸误判"#2 是新增行"，回查其前一封 #1
        # 已闭环 ⇒ 不误报；**真正会误报的是** #1（未闭环）→ #2（待压缩，
        # 未闭环）→ #3（未闭环，最新）：压缩 #2 令其"看似新增"，前一封 #1
        # 未闭环 ⇒ 触发。
        self._write_readme(
            _row("采购部#1", "2026-07-01", "采购部 · 姚祖怡", "首封事项", "不急",
                 "✅ 已推送 2026-07-01 08:00 UTC")
            + _row("采购部#2", "2026-07-15", "采购部 · 姚祖怡", long_topic, "不急",
                   "⏳ 待你审")
            + _row("采购部#3", "2026-08-01", "采购部 · 姚祖怡", "最新事项", "不急",
                   "⏳ 待你审")
        )
        code, out, _err = self._run(who="t")
        self.assertEqual(code, 0, out)
        self.assertIn("[OK]", out)
        self.assertIn("串行", out)

        new_text = self._readme_text()
        self.assertIn(
            f"{self.module.editlock.FOLLOWUP_SERIAL_WAIVER_MARKER}"
            f"{self.module.SERIAL_WAIVER_REASON}",
            new_text,
        )
        self.assertIn("首封事项", new_text, "未涉及的行不应被本机制动到")
        self.assertIn("最新事项", new_text, "未涉及的行不应被本机制动到")

    def test_豁免只写在交期要点列不污染主要事项摘要本身(self):
        long_topic = "第一句摘要。" + ("填" * 250)
        self._write_readme(
            _row("采购部#1", "2026-07-01", "采购部 · 姚祖怡", "首封事项", "不急",
                 "✅ 已推送 2026-07-01 08:00 UTC")
            + _row("采购部#2", "2026-07-15", "采购部 · 姚祖怡", long_topic, "不急",
                   "⏳ 待你审")
            + _row("采购部#3", "2026-08-01", "采购部 · 姚祖怡", "最新事项", "不急",
                   "⏳ 待你审")
        )
        code, _out, _err = self._run(who="t")
        self.assertEqual(code, 0)
        new_text = self._readme_text()
        summary_line = next(l for l in new_text.splitlines() if l.startswith("| 采购部#2 |"))
        self.assertTrue(summary_line.startswith("| 采购部#2 | 2026-07-15 | 采购部 · 姚祖怡 | 第一句摘要。"))
        self.assertNotIn(
            self.module.editlock.FOLLOWUP_SERIAL_WAIVER_MARKER,
            summary_line.split("|")[4],  # 主要事项列本身
        )


if __name__ == "__main__":
    unittest.main()
