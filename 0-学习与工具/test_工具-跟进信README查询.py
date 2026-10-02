"""`工具-跟进信README查询.py` 单测（队列 §一 #382⑵）。

白盒方式：按文件路径 importlib 加载被测脚本（同 `test_工具-跟进闸查询.py`
既定手法），把 `REPO_ROOT` 指向临时夹具目录——不触碰真实 README。
"""
from __future__ import annotations

import hashlib
import importlib.util
import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

SCRIPT = Path(__file__).resolve().with_name("工具-跟进信README查询.py")

README_REL = "6-人才与组织/部门AI专员跟进/README-跟进机制与命名约定.md"

README_HEADER = (
    "## 现有跟进信清单\n\n"
    "| 编号 | 日期 | 收信人 | 主要事项 | 交期要点 | 发送状态（2026-07-06） |\n"
    "|--------|------|--------|---------|---------|---------|\n"
)


def _load():
    spec = importlib.util.spec_from_file_location("_followup_readme_digest_under_test", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _row(number, recipient, delivery, status, date="2026-08-20", topic="事项"):
    return f"| {number} | {date} | {recipient} | {topic} | {delivery} | {status} |\n"


class FollowupReadmeDigestTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.module = _load()
        self.module.REPO_ROOT = self.root
        (self.root / README_REL).parent.mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        self._tmp.cleanup()

    def _write_readme(self, rows: str):
        (self.root / README_REL).write_text(README_HEADER + rows, encoding="utf-8")

    def _rows(self, width=None):
        text = (self.root / README_REL).read_text(encoding="utf-8")
        kwargs = {} if width is None else {"width": width}
        return self.module.build_digest_rows(text, **kwargs)

    # ------------------------------------------------------------ 三态识别

    def test_三个待发态各自被正确识别(self):
        self._write_readme(
            _row("采购部#1", "采购部 · 姚祖怡", "尽快", "⏳ 待你审")
            + _row("采购部#2", "采购部 · 姚祖怡", "尽快", "🆕 待发")
            + _row("采购部#3", "采购部 · 姚祖怡", "尽快", "⏸ 暂缓")
        )
        rows = self._rows()
        got = {r["number"]: r["not_yet_sent_prefix"] for r in rows}
        self.assertEqual(got, {
            "采购部#1": "⏳ 待你审",
            "采购部#2": "🆕 待发",
            "采购部#3": "⏸ 暂缓",
        })

    def test_已闭环与已推送均不计入待发三态(self):
        self._write_readme(
            _row("采购部#1", "采购部 · 姚祖怡", "尽快", "📥 已回件并回灌（2026-08-23）")
            + _row("采购部#2", "采购部 · 姚祖怡", "尽快", "✅ 已推送 2026-08-20 12:20 UTC")
            + _row("采购部#3", "采购部 · 姚祖怡", "尽快", "📨 回件已到，待拆件 2026-09-02T00:00:00Z")
        )
        rows = self._rows()
        self.assertTrue(all(r["not_yet_sent_prefix"] is None for r in rows))
        kinds = {r["number"]: r["status_kind"] for r in rows}
        self.assertEqual(kinds, {
            "采购部#1": "closed",
            "采购部#2": "in_flight",
            "采购部#3": "reply_arrived",
        })

    # ------------------------------------------------------------ 截断安全

    def test_状态前缀在任意窄宽度下均不被截断(self):
        """回归 #439 那类"关键判断信息被截断算法误伤"缺陷：即便
        --digest-width 小到 1，`not_yet_sent_prefix` 仍必须正确识别——
        判定读的是原始状态列，不是被截断过的展示字符串。"""
        long_tail = "，" + "补充说明" * 50  # 制造一个远超任何合理宽度的尾巴
        self._write_readme(_row("采购部#1", "采购部 · 姚祖怡", "尽快", "🆕 待发" + long_tail))
        for width in (1, 5, 40):
            rows = self._rows(width=width)
            self.assertEqual(rows[0]["not_yet_sent_prefix"], "🆕 待发",
                              f"width={width} 时前缀判定不应受影响")
            self.assertTrue(rows[0]["status_digest"].startswith("🆕 待发"),
                             f"width={width} 时展示文本必须仍以完整前缀开头，实得：{rows[0]['status_digest']}")

    def test_未识别前缀落入非静默降级兜底(self):
        self._write_readme(_row("采购部#1", "采购部 · 姚祖怡", "尽快", "🔄 已并入合并件，本件不发"))
        rows = self._rows()
        self.assertTrue(rows[0]["status_malformed"])
        self.assertEqual(rows[0]["status_kind"], "unknown")
        self.assertNotEqual(rows[0]["status_digest"], "")

    def test_交期要点超宽度按分隔符或宽度截断并补省略号(self):
        self._write_readme(_row("采购部#1", "采购部 · 姚祖怡",
                                 "① 这是第一项相当长的交期说明；② 第二项", "🆕 待发"))
        rows = self._rows(width=12)
        self.assertTrue(rows[0]["delivery_digest"].endswith("…") or "；" not in rows[0]["delivery_digest"][12:])

    # ------------------------------------------------------------ 收信人/部门

    def test_收信人正常解析出部门与姓名(self):
        self._write_readme(_row("质量部#9", "质量部 · 陈忱（可分担朱映桦）", "尽快", "🆕 待发"))
        rows = self._rows()
        self.assertEqual(rows[0]["department"], "质量部")
        # `name`（裸姓名，不含括注/部门前缀）——sweep 侧交叉红标要用它去
        # 匹配队列行里惯用的裸姓名写法（如"姚祖怡那封信先暂缓"），不能只
        # 靠完整 `recipient` 字段（"质量部 · 陈忱（可分担朱映桦）"）。
        self.assertEqual(rows[0]["name"], "陈忱")

    def test_收信人无法解析部门时不崩溃(self):
        self._write_readme(_row("销售部（未发，不编号）", "销售部", "尽快", "🆕 待发"))
        rows = self._rows()
        self.assertIsNone(rows[0]["department"])

    # ------------------------------------------------------------ CLI

    def test_digest文本模式与json模式行数一致(self):
        self._write_readme(
            _row("采购部#1", "采购部 · 姚祖怡", "尽快", "🆕 待发")
            + _row("采购部#2", "采购部 · 姚祖怡", "尽快", "📥 已回件并回灌（2026-08-23）")
        )
        text_buf = io.StringIO()
        with redirect_stdout(text_buf):
            code = self.module.main(["--digest"])
        self.assertEqual(code, 0)
        self.assertIn("合计 2 行", text_buf.getvalue())
        self.assertIn("🆕 待发×1", text_buf.getvalue())

        json_buf = io.StringIO()
        with redirect_stdout(json_buf):
            code = self.module.main(["--digest", "--json"])
        self.assertEqual(code, 0)
        data = json.loads(json_buf.getvalue())
        self.assertEqual(data["total_rows"], 2)
        self.assertEqual(len(data["rows"]), 2)

    def test_file参数指向归档件时读取归档件而非主表(self):
        """`followup-readme-phase2` D2 任务 2.5：归档件章节标题/表头与主表
        一致，同一套解析逻辑读取，供人工核对历史用。"""
        self._write_readme(_row("采购部#22", "采购部 · 姚祖怡", "尽快", "🆕 待发"))
        archive_rel = "6-人才与组织/部门AI专员跟进/README-归档-202609.md"
        (self.root / archive_rel).write_text(
            README_HEADER + _row("采购部#1", "采购部 · 姚祖怡", "尽快", "❌ 已作废"),
            encoding="utf-8",
        )
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = self.module.main(["--digest", "--file", archive_rel])
        self.assertEqual(code, 0)
        self.assertIn("采购部#1", buf.getvalue())
        self.assertNotIn("采购部#22", buf.getvalue())

    def test_file参数省略时默认读主表行为不变(self):
        self._write_readme(_row("采购部#22", "采购部 · 姚祖怡", "尽快", "🆕 待发"))
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = self.module.main(["--digest"])
        self.assertEqual(code, 0)
        self.assertIn("采购部#22", buf.getvalue())

    def test_README表损坏退出码1(self):
        (self.root / README_REL).write_text("这份文件里没有任何跟进信表格\n", encoding="utf-8")
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = self.module.main(["--digest"])
        self.assertEqual(code, 1)
        self.assertIn("✗", buf.getvalue())

    def test_digest宽度非正数报错(self):
        self._write_readme(_row("采购部#1", "采购部 · 姚祖怡", "尽快", "🆕 待发"))
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = self.module.main(["--digest", "--digest-width", "0"])
        self.assertEqual(code, 1)

    def test_空表输出零行不崩溃(self):
        self._write_readme("")
        rows = self._rows()
        self.assertEqual(rows, [])


class FollowupReadmeRawRowTests(unittest.TestCase):
    """`--row` 整格原文只读模式（队列 §一 #501⑴）。

    本类的核心是一对**正反用例**：同一个超长状态格，`--row` 必须逐字还原
    （正），`--digest` 即便把 `--digest-width` 开到 3000 也仍然截断（反）。
    反用例不是"演示 digest 不好用"——它是 `#501` 立行的那条成因本身
    （`--digest-width` 对状态列无效，实测传 3000 无变化），把它钉成回归，
    以后谁想"放宽宽度就够了"会当场看到这条测试。
    """

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.module = _load()
        self.module.REPO_ROOT = self.root
        (self.root / README_REL).parent.mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        self._tmp.cleanup()

    def _write_readme(self, rows: str):
        (self.root / README_REL).write_text(README_HEADER + rows, encoding="utf-8")

    def _text(self):
        return (self.root / README_REL).read_text(encoding="utf-8")

    @staticmethod
    def _long_status():
        """一格远超任何 digest 宽度的真实形态状态：闭环前缀 ＋ 长叙述，且
        叙述里嵌着一句被**引用**的 `串行豁免：` 口令——`质量部#7` 的形态。"""
        return (
            "✅ **无需回复**（起草时即判定，发出即闭环、不占串行闸）"
            + "　补充说明" * 300
            + "　须走 `串行豁免：前信为无需回复形态` 逃生阀。"
        )

    # ------------------------------------------------- 正：整格原文零截断

    def test_row模式逐字还原长状态格(self):
        status = self._long_status()
        self._write_readme(_row("质量部#7", "质量部 · 陈忱", "尽快", status))
        raw = self.module.build_raw_row(self._text(), "质量部#7")
        cell = next(c for c in raw["cells"] if c["is_status_column"])
        self.assertEqual(cell["value"], status)
        self.assertNotIn("…", cell["value"])
        self.assertEqual(cell["chars"], len(status))
        self.assertEqual(cell["bytes"], len(status.encode("utf-8")))
        self.assertEqual(cell["sha256"], hashlib.sha256(status.encode("utf-8")).hexdigest())

    def test_row模式CLI人读输出含状态格全文(self):
        status = self._long_status()
        self._write_readme(_row("质量部#7", "质量部 · 陈忱", "尽快", status))
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = self.module.main(["--row", "质量部#7", "--field", "发送状态"])
        self.assertEqual(code, 0)
        out = buf.getvalue()
        self.assertIn(status, out)
        # 只出这一列——其它列的内容不得随之泄进上下文（一次只出一行一列，
        # 正是"不开通读后门"这条约束的可测形态）。
        self.assertNotIn("质量部 · 陈忱", out.split("──── [")[-1])

    # ------------------------------------------------- 反：digest 仍然截断

    def test_digest对同一长状态格仍截断且digest_width无效(self):
        status = self._long_status()
        self._write_readme(_row("质量部#7", "质量部 · 陈忱", "尽快", status))
        text = self._text()
        default_digest = self.module.build_digest_rows(text)[0]["status_digest"]
        wide_digest = self.module.build_digest_rows(text, width=3000)[0]["status_digest"]
        # ⑴ 截断确实发生（远短于原文）；⑵ 把宽度开到 3000 一个字都没多——
        # 状态列延续文本走的是 STATUS_CONTINUATION_WIDTH 这个独立常量。
        self.assertLess(len(default_digest), len(status))
        self.assertEqual(default_digest, wide_digest)
        self.assertNotIn("串行豁免", default_digest)

    # ------------------------------------------------- 匹配判据

    def test_字面相等优先于编号解析值相等(self):
        self._write_readme(
            _row("质量部#7（待你审，暂不占号）", "质量部 · 陈忱", "尽快", "⏳ 待你审")
            + _row("质量部#7", "质量部 · 陈忱", "尽快", "✅ 无需回复")
        )
        raw = self.module.build_raw_row(self._text(), "质量部#7")
        self.assertEqual(raw["matched_by"], "字面相等")
        self.assertEqual(raw["number_cell_literal"], "质量部#7")
        status = next(c for c in raw["cells"] if c["is_status_column"])
        self.assertEqual(status["value"], "✅ 无需回复")

    def test_无字面命中时回落解析值相等(self):
        self._write_readme(_row("质量部#7（待你审，暂不占号）", "质量部 · 陈忱", "尽快", "⏳ 待你审"))
        raw = self.module.build_raw_row(self._text(), "质量部#7")
        self.assertEqual(raw["matched_by"], "编号解析值相等")
        self.assertEqual(raw["number_cell_literal"], "质量部#7（待你审，暂不占号）")

    def test_解析值命中多行时报歧义不静默取第一行(self):
        """`set-status` 在同样的输入下会静默取第一行；本模式据以取证，取错行
        的代价是把改写落到别人那行上，故收窄为报错。"""
        self._write_readme(
            _row("质量部#7（待你审，暂不占号）", "质量部 · 陈忱", "尽快", "⏳ 待你审")
            + _row("质量部#7（未发）", "质量部 · 陈忱", "尽快", "🆕 待发")
        )
        with self.assertRaises(self.module.RawRowNotFound) as ctx:
            self.module.build_raw_row(self._text(), "质量部#7")
        msg = str(ctx.exception)
        self.assertIn("歧义", msg)
        self.assertIn("质量部#7（未发）", msg)

    def test_编号不存在退出码1(self):
        self._write_readme(_row("质量部#7", "质量部 · 陈忱", "尽快", "✅ 无需回复"))
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = self.module.main(["--row", "质量部#99"])
        self.assertEqual(code, 1)
        self.assertIn("✗", buf.getvalue())

    # ------------------------------------------------- 选列

    def test_field按列名子串匹配表头括注(self):
        self._write_readme(_row("质量部#7", "质量部 · 陈忱", "尽快", "✅ 无需回复"))
        raw = self.module.build_raw_row(self._text(), "质量部#7")
        cells = self.module._select_raw_cells(raw, "发送状态")
        self.assertEqual(len(cells), 1)
        self.assertTrue(cells[0]["column"].startswith("发送状态"))

    def test_field选不中即报错不静默返回空(self):
        self._write_readme(_row("质量部#7", "质量部 · 陈忱", "尽快", "✅ 无需回复"))
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = self.module.main(["--row", "质量部#7", "--field", "并不存在的列"])
        self.assertEqual(code, 1)
        self.assertIn("✗", buf.getvalue())

    def test_field默认all出全部列(self):
        self._write_readme(_row("质量部#7", "质量部 · 陈忱", "尽快", "✅ 无需回复"))
        raw = self.module.build_raw_row(self._text(), "质量部#7")
        self.assertEqual(len(self.module._select_raw_cells(raw, self.module.RAW_FIELD_ALL)), 6)

    # ------------------------------------------------- JSON / CLI 形态

    def test_json模式给全长sha256与行号(self):
        status = self._long_status()
        self._write_readme(_row("质量部#7", "质量部 · 陈忱", "尽快", status))
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = self.module.main(["--row", "质量部#7", "--json"])
        self.assertEqual(code, 0)
        data = json.loads(buf.getvalue())
        self.assertEqual(data["number_cell_literal"], "质量部#7")
        self.assertEqual(data["readme"], README_REL)
        cell = next(c for c in data["cells"] if c["is_status_column"])
        self.assertEqual(cell["value"], status)
        self.assertEqual(len(cell["sha256"]), 64)
        # markdown 行号：表头 2 行 + 章节标题 2 行 ⇒ 第一条数据行 line_index=4
        self.assertEqual(data["line_index"], 4)

    def test_row与digest互斥且必传其一(self):
        self._write_readme(_row("质量部#7", "质量部 · 陈忱", "尽快", "✅ 无需回复"))
        for argv in (["--row", "质量部#7", "--digest"], []):
            buf = io.StringIO()
            with redirect_stdout(buf):
                code = self.module.main(argv)
            self.assertEqual(code, 1, f"argv={argv}")
            self.assertIn("✗", buf.getvalue())

    def test_row模式支持file指向归档件(self):
        self._write_readme(_row("质量部#9", "质量部 · 陈忱", "尽快", "🆕 待发"))
        archive_rel = "6-人才与组织/部门AI专员跟进/README-归档-202609.md"
        (self.root / archive_rel).write_text(
            README_HEADER + _row("质量部#7", "质量部 · 陈忱", "尽快", "❌ 已作废（归档件里的那一行）"),
            encoding="utf-8",
        )
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = self.module.main(["--row", "质量部#7", "--file", archive_rel])
        self.assertEqual(code, 0)
        self.assertIn("归档件里的那一行", buf.getvalue())

    def test_表结构坏了退出码1(self):
        (self.root / README_REL).write_text("这份文件里没有任何跟进信表格\n", encoding="utf-8")
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = self.module.main(["--row", "质量部#7"])
        self.assertEqual(code, 1)


if __name__ == "__main__":
    unittest.main()


import subprocess

class ExplicitFixtureRootTests(unittest.TestCase):
    def _case(self):
        import os, runpy
        from unittest import mock
        with mock.patch.dict(os.environ):
            os.environ.pop('ZHUOPIN_CODEX_FIXTURE_ROOT', None)
            namespace = runpy.run_path(str(SCRIPT), run_name='fixture_root_tests')['_resolve_repo_root'].__globals__
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name) / 'linked fixture 中文'
        tools = root / '0-学习与工具'; tools.mkdir(parents=True)
        (root / '.git').write_text('gitdir: synthetic-test-admin', encoding='utf8')
        namespace['__file__'] = str(tools / SCRIPT.name)
        namespace['_TOOLS_DIR'] = tools
        namespace['_REPO_GUESS'] = root
        config = root / '.codex/runtime.local.json'; config.parent.mkdir()
        state = root / 'reports/state'
        import json
        config.write_text(json.dumps({'state_root':str(state)}), encoding='utf8')
        env = {'ZHUOPIN_CODEX_FIXTURE_ROOT':str(root), 'ZHUOPIN_CODEX_RUNTIME':str(config), 'ZHUOPIN_CODEX_STATE':str(state)}
        def git_result(argv, **kwargs):
            if 'list' in argv:
                out = 'worktree ' + str(root) + '\0HEAD ' + 'a'*40 + '\0detached\0\0'
            elif '--show-toplevel' in argv:
                out = str(root)
            else:
                out = str(root.parent / 'canonical/.git')
            return subprocess.CompletedProcess(argv, 0, out, '')
        return namespace, root, config, state, env, git_result

    def test_explicit_fixture_root_is_used(self):
        import os
        from unittest import mock
        ns, root, config, state, env, git_result = self._case()
        with mock.patch.dict(os.environ, env), mock.patch.object(subprocess, 'run', side_effect=git_result):
            self.assertEqual(ns['_resolve_repo_root'](), root.resolve())

    def test_fixture_git_checks_use_command_scoped_safe_directory(self):
        import os
        from unittest import mock
        ns, root, config, state, env, git_result = self._case()
        calls = []
        def recording_git(argv, **kwargs):
            calls.append(argv)
            return git_result(argv, **kwargs)
        with mock.patch.dict(os.environ, env), mock.patch.object(subprocess, 'run', side_effect=recording_git):
            self.assertEqual(ns['_resolve_repo_root'](), root.resolve())
        self.assertEqual(len(calls), 2)
        expected = f'safe.directory={root.resolve().as_posix()}'
        self.assertTrue(all(argv[0:3] == ['git', '-c', expected] for argv in calls))

    def test_invalid_override_does_not_fall_back_to_main(self):
        import os
        from unittest import mock
        for value in ('relative-root', '', 'different'):
            with self.subTest(value=value):
                ns, root, config, state, env, git_result = self._case()
                env['ZHUOPIN_CODEX_FIXTURE_ROOT'] = str(root.parent / value) if value=='different' else value
                with mock.patch.dict(os.environ, env), mock.patch.object(subprocess, 'run', side_effect=git_result):
                    with self.assertRaises(ValueError): ns['_resolve_repo_root']()

    def test_runtime_and_state_must_stay_inside_fixture(self):
        import os, json
        from unittest import mock
        for kind in ('runtime-outside', 'state-outside', 'runtime-state-outside', 'state-mismatch'):
            with self.subTest(kind=kind):
                ns, root, config, state, env, git_result = self._case()
                if kind=='runtime-outside': env['ZHUOPIN_CODEX_RUNTIME']=str(root.parent/'runtime.json')
                if kind=='state-outside': env['ZHUOPIN_CODEX_STATE']=str(root.parent/'state')
                if kind=='runtime-state-outside': config.write_text(json.dumps({'state_root':str(root.parent/'state')}))
                if kind=='state-mismatch': env['ZHUOPIN_CODEX_STATE']=str(root/'different-state')
                with mock.patch.dict(os.environ, env), mock.patch.object(subprocess, 'run', side_effect=git_result):
                    with self.assertRaises(ValueError): ns['_resolve_repo_root']()

    def test_unregistered_or_primary_checkout_is_rejected(self):
        import os
        from unittest import mock
        for kind in ('unregistered', 'primary'):
            ns, root, config, state, env, git_result = self._case()
            if kind=='primary': (root/'.git').unlink(); (root/'.git').mkdir()
            def result(argv, **kwargs):
                if kind=='unregistered' and 'list' in argv: return subprocess.CompletedProcess(argv,0,'worktree '+str(root.parent/'other')+'\0','')
                return git_result(argv,**kwargs)
            with self.subTest(kind=kind), mock.patch.dict(os.environ,env), mock.patch.object(subprocess,'run',side_effect=result):
                with self.assertRaises(ValueError): ns['_resolve_repo_root']()

    def test_unset_override_preserves_canonical_root(self):
        import os
        from pathlib import Path
        from unittest import mock
        ns, root, config, state, env, git_result = self._case()
        calls = []
        def recording_git(argv, **kwargs):
            calls.append(argv)
            return git_result(argv, **kwargs)
        with mock.patch.dict(os.environ, env), mock.patch.object(subprocess,'run',side_effect=recording_git):
            os.environ.pop('ZHUOPIN_CODEX_FIXTURE_ROOT',None)
            self.assertEqual(ns['_resolve_repo_root'](), root.parent/'canonical')
        self.assertEqual(len(calls), 1)
        checkout = Path(ns['__file__']).resolve().parents[1]
        self.assertEqual(calls[0][0:3], ['git', '-c', f'safe.directory={checkout.as_posix()}'])
