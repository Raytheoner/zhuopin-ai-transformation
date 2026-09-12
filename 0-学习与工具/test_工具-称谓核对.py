"""`工具-称谓核对.py` 与编辑锁 release 挂载点的单测（队列 §一 `#566` ⑤）。

🔴 **7 个易错名做成用例、写反即红**——正本 §二「`祖怡`／`燕萍`／`映桦`／`植雅`／
`易水`／`姣龙`／`国庆`」。用例**不硬编码性别**：应写哪个代词由
`editlock.PERSON_GENDER_ROSTER` 现算（名录改了用例跟着改，不会两处漂移）；
「写反」＝把名录给的那个字换成另一个。
"""
from __future__ import annotations

import contextlib
import importlib.util
import io
import os
import subprocess
import sys
import tempfile
import unittest
import unittest.mock
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
TOOL = HERE / "工具-称谓核对.py"
EDITLOCK = HERE / "工具-共享文档编辑锁.py"
ROSTER_MD = HERE.parent / "6-人才与组织" / "人员名录-称谓与性别-正本.md"

# 正本 §二 的 7 个易错名（短名形态）——测试夹具，不是第二份名录：性别一律现查常量。
TRICKY_SHORT_NAMES = ("祖怡", "燕萍", "映桦", "植雅", "易水", "姣龙", "国庆")


def _load_tool():
    spec = importlib.util.spec_from_file_location("_gender_lint_under_test", TOOL)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _load_editlock():
    spec = importlib.util.spec_from_file_location("_gender_lint_editlock_under_test", EDITLOCK)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _flip(pronoun: str) -> str:
    return "她" if pronoun == "他" else "他"


def _docx_bytes(paragraphs: list[list[str]], table_cell: list[str] | None = None) -> bytes:
    """最小 docx：每段由若干 `<w:t>` run 拼成（真实 docx 常把一句话拆成多个 run）；
    可选一个表格单元格——`#566` 明写「docx 走全文，不只解析表头」。"""
    body = ""
    for runs in paragraphs:
        body += "<w:p>" + "".join(f"<w:r><w:t xml:space=\"preserve\">{r}</w:t></w:r>" for r in runs) + "</w:p>"
    if table_cell is not None:
        body += ("<w:tbl><w:tr><w:tc><w:p>"
                 + "".join(f"<w:r><w:t>{r}</w:t></w:r>" for r in table_cell)
                 + "</w:p></w:tc></w:tr></w:tbl>")
    xml = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
           '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
           f"<w:body>{body}</w:body></w:document>")
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("[Content_Types].xml", "<Types/>")
        z.writestr("word/document.xml", xml)
    return buf.getvalue()


class TrickyNamesTests(unittest.TestCase):
    """⑤ 7 个易错名：短名与全名两种形态，写反即红、写对即绿。"""

    @classmethod
    def setUpClass(cls):
        cls.t = _load_tool()
        cls.roster = cls.t.editlock.PERSON_GENDER_ROSTER
        cls.aliases = cls.t.editlock.gender_roster_aliases(cls.roster, include_short_names=True)

    def _expected(self, alias: str) -> str:
        name = self.aliases[alias]
        return self.t.editlock._expected_pronoun_for(self.roster[name])

    def test_all_seven_short_names_derive_from_roster(self):
        """短名必须能从名录派生出来——派生规则坏了，下面的用例会退化成恒真。"""
        for short in TRICKY_SHORT_NAMES:
            self.assertIn(short, self.aliases, f"短名「{short}」没从名录派生出来")

    def test_wrong_pronoun_after_short_name_is_red(self):
        for short in TRICKY_SHORT_NAMES:
            wrong = _flip(self._expected(short))
            hits = self.t.scan_units([(1, f"{short}回件了，{wrong}说口径要改。")])
            self.assertEqual(len(hits), 1, f"「{short}…{wrong}」应命中")
            self.assertEqual(hits[0]["written"], wrong)
            self.assertEqual(hits[0]["expected"], self._expected(short))
            self.assertEqual(hits[0]["line"], 1)

    def test_wrong_pronoun_after_full_name_is_red(self):
        for short in TRICKY_SHORT_NAMES:
            full = self.aliases[short]
            wrong = _flip(self._expected(short))
            hits = self.t.scan_units([(3, f"请{full}先做初标，你只裁{wrong}拿不准的那几条。")])
            self.assertEqual(len(hits), 1, f"「{full}…{wrong}」应命中")
            self.assertEqual(hits[0]["alias"], full)
            self.assertEqual(hits[0]["line"], 3)

    def test_correct_pronoun_is_green(self):
        for short in TRICKY_SHORT_NAMES:
            right = self._expected(short)
            self.assertEqual(
                self.t.scan_units([(1, f"{short}回件了，{right}说口径要改。")]), [],
                f"「{short}…{right}」写对了不该命中",
            )

    def test_incident_sentence_reproduces(self):
        """`财务部#14` 事故原句形态（CHANGELOG 附录 F）：名字 ＋「的企微账号」。"""
        full = self.aliases["姣龙"]
        wrong = _flip(self._expected("姣龙"))
        hits = self.t.scan_units([(71, f"麻烦告诉我们{full}在这套流程里具体负责哪一段、以及{wrong}的企微账号")])
        self.assertEqual([h["line"] for h in hits], [71])


class JudgementEdgeTests(unittest.TestCase):
    """判据边界：未确认／别名／遮蔽／豁免／围栏。"""

    @classmethod
    def setUpClass(cls):
        cls.t = _load_tool()
        cls.el = cls.t.editlock

    def test_unconfirmed_flags_both_pronouns_and_asks_neutral(self):
        roster = dict(self.el.PERSON_GENDER_ROSTER)
        roster["某新人"] = self.el.GENDER_UNCONFIRMED
        for pronoun in ("他", "她"):
            hits = self.t.scan_units([(1, f"某新人已到岗，{pronoun}负责制单。")], roster=roster,
                                     aliases=self.el.gender_roster_aliases(roster, include_short_names=True))
            self.assertEqual(len(hits), 1, f"未确认者写「{pronoun}」应命中")
            self.assertEqual(hits[0]["expected"], self.el.GENDER_NEUTRAL_HINT)

    def test_decision_maker_english_alias_is_not_misattributed(self):
        """「唐燕萍与 Shao Peishen 讨论后，他决定…」——「他」指他本人，不是给唐燕萍写错。"""
        roster = self.el.PERSON_GENDER_ROSTER
        aliases = self.el.gender_roster_aliases(roster, include_short_names=True)
        self.assertIn("Shao Peishen", aliases)
        his = self.el._expected_pronoun_for(roster[aliases["Shao Peishen"]])
        female = next(n for n, g in roster.items() if g != roster[aliases["Shao Peishen"]])
        self.assertEqual(self.t.scan_units([(1, f"{female}与 Shao Peishen 讨论后，{his}决定按 (a) 走。")]), [])

    def test_holiday_compound_is_not_a_person(self):
        """「国庆假期后他…」——`国庆` 在这里是节日，不是孙国庆。"""
        self.assertEqual(self.t.scan_units([(1, "国庆假期后他会把样本给到。国庆节前她已交。")]), [])

    def test_qita_and_tamen_are_masked(self):
        name = next(n for n, g in self.el.PERSON_GENDER_ROSTER.items() if g == "女")
        self.assertEqual(self.t.scan_units([(1, f"{name}圈定了口径，其他几项待定，他们下周碰。")]), [])

    def test_waiver_with_reason_passes_both_markers(self):
        name = next(n for n, g in self.el.PERSON_GENDER_ROSTER.items() if g == "女")
        for marker in ("性别豁免：", "代词豁免："):
            line = f"{name}那封旧信原文写「他」（{marker}原样引用历史信件，不追改）"
            self.assertEqual(self.t.scan_units([(1, line)]), [], marker)

    def test_waiver_without_reason_is_its_own_hit(self):
        name = next(n for n, g in self.el.PERSON_GENDER_ROSTER.items() if g == "女")
        hits = self.t.scan_units([(9, f"{name}说他会来（性别豁免：）")])
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0]["kind"], "waiver-without-reason")
        self.assertEqual(hits[0]["line"], 9)

    def test_md_code_fence_skipped_but_blockquote_judged(self):
        name = next(n for n, g in self.el.PERSON_GENDER_ROSTER.items() if g == "男")
        text = "\n".join([
            "# 标题", "", "```", f"{name}她 —— 围栏里的原样引用", "```", "",
            f"> {name}回了，她补了一条。",
        ])
        units = self.t.md_units(text)
        self.assertEqual([no for no, _ in units], [1, 7])
        hits = self.t.scan_units(units)
        self.assertEqual([h["line"] for h in hits], [7])


class DocxTests(unittest.TestCase):
    """docx：`word/document.xml` 全文、跨 run 拼接、表格单元格也扫、段序号可定位。"""

    @classmethod
    def setUpClass(cls):
        cls.t = _load_tool()
        cls.el = cls.t.editlock

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_split_runs_and_table_cell_are_scanned(self):
        name = next(n for n, g in self.el.PERSON_GENDER_ROSTER.items() if g == "男")
        path = self.root / "x.docx"
        path.write_bytes(_docx_bytes(
            [["卓品智能"], [name, "回了件，", "她", "补了一条"], ["无关段落"]],
            table_cell=["做什么：请", name, "先初标，你只裁她拿不准的"],
        ))
        hits = self.t.scan_files([path], repo_root=self.root)
        self.assertEqual([h["line"] for h in hits], [2, 4])
        self.assertTrue(all(h["path"] == "x.docx" for h in hits))

    def test_bad_docx_is_unexecutable_not_clean(self):
        path = self.root / "bad.docx"
        path.write_bytes(b"not a zip")
        with self.assertRaises(self.t.GenderLintError):
            self.t.scan_files([path], repo_root=self.root)
        rc = self.t.run([str(path)], repo_root=self.root)
        self.assertEqual(rc, 2)


class TargetSetTests(unittest.TestCase):
    """目标集合：信件判别、白名单跳过历史件、--dirty 取材。"""

    @classmethod
    def setUpClass(cls):
        cls.t = _load_tool()
        cls.el = cls.t.editlock

    def test_is_letter_path(self):
        d = self.t.LETTER_DIR_REL
        self.assertTrue(self.t.is_letter_path(f"{d}/财务部-某人-跟进-2026-09-12-x.md"))
        self.assertTrue(self.t.is_letter_path(f"{d}/财务部-某人-跟进-2026-09-12-x.docx"))
        self.assertFalse(self.t.is_letter_path(f"{d}/README-跟进机制与命名约定.md"))
        self.assertFalse(self.t.is_letter_path(f"{d}/README-归档-202609.md"))
        self.assertFalse(self.t.is_letter_path(f"{d}/跟进信行日志/财务部#14.md"))
        self.assertFalse(self.t.is_letter_path(f"{d}/口径点台账/x.md"))
        self.assertFalse(self.t.is_letter_path("1-转型规划/x.md"))
        self.assertFalse(self.t.is_letter_path(f"{d}/x.txt"))

    def test_all_skips_whitelisted_and_reports_count(self):
        name = next(n for n, g in self.el.PERSON_GENDER_ROSTER.items() if g == "女")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            letters = root / self.t.LETTER_DIR_REL
            letters.mkdir(parents=True)
            (letters / "旧信.md").write_text(f"{name}说他会来。", encoding="utf-8")
            (letters / "新信.md").write_text(f"{name}说他会来。", encoding="utf-8")
            (letters / "README-x.md").write_text(f"{name}说他会来。", encoding="utf-8")
            wl = root / self.t.WHITELIST_REL
            wl.parent.mkdir(parents=True)
            wl.write_text(f"# 注释\n{self.t.LETTER_DIR_REL}/旧信.md\t已发出\n", encoding="utf-8")
            paths, skipped = self.t.all_letter_paths(root)
            self.assertEqual(skipped, [f"{self.t.LETTER_DIR_REL}/旧信.md"])
            self.assertEqual(paths, [f"{self.t.LETTER_DIR_REL}/新信.md"])
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                rc = self.t.run(paths, repo_root=root, skipped=skipped)
            self.assertEqual(rc, 1)
            self.assertIn("白名单跳过历史件 1 个", out.getvalue())
            self.assertIn("新信.md:1", out.getvalue())

    def test_repo_whitelist_lists_only_existing_files(self):
        """白名单里的路径必须真实存在——文件改名后白名单静默失效、历史件又会被报。"""
        wl = self.t.load_whitelist(HERE.parent)
        self.assertGreater(len(wl), 0)
        for rel in wl:
            self.assertTrue((HERE.parent / rel).is_file(), f"白名单路径不存在：{rel}")
            self.assertTrue(self.t.is_letter_path(rel), rel)

    def test_tool_source_has_no_hardcoded_person(self):
        """同 `test_hooks-哨兵.py::test_H4_脚本内零硬编码人名与性别`：写出人名即第二份名录。"""
        src = TOOL.read_text(encoding="utf-8")
        for name in self.el.PERSON_GENDER_ROSTER:
            self.assertFalse(name in src, f"工具源码里出现了具体人名：{name}")
        for short in TRICKY_SHORT_NAMES:
            self.assertFalse(short in src, f"工具源码里出现了短名：{short}")


class RosterSyncTests(unittest.TestCase):
    """`#566` ①：常量正本仍是名录文件——本工具不解析正本；此处再核一次正本 §一 ⊆ 常量，
    与编辑锁那条同步用例互为备份（那条若被删，这条还在）。"""

    def test_roster_file_names_all_in_constant(self):
        import re
        el = _load_editlock()
        text = ROSTER_MD.read_text(encoding="utf-8")
        start, end = text.index("## 一、"), text.index("## 二、")
        declared = {m.group(1): m.group(2)
                    for m in re.finditer(r"([一-龥]{2,4})（(男|女)[^）]*）", text[start:end])}
        self.assertGreaterEqual(len(declared), 15)
        for name, gender in declared.items():
            self.assertEqual(el.PERSON_GENDER_ROSTER.get(name), gender, name)

    def test_tricky_names_in_roster_file_section_two(self):
        text = ROSTER_MD.read_text(encoding="utf-8")
        for short in TRICKY_SHORT_NAMES:
            self.assertIn(f"`{short}`", text, f"正本 §二 易错名清单缺「{short}」——夹具与正本漂移")


class ReleaseHookTests(unittest.TestCase):
    """③ 编辑锁 release 挂载点：用真实 git 仓库跑，本项价值就在「机器亲眼看到
    工作区里刚写出来、还没 commit 的信」。"""

    @classmethod
    def setUpClass(cls):
        cls.el = _load_editlock()
        cls.male = next(n for n, g in cls.el.PERSON_GENDER_ROSTER.items() if g == "男")
        cls.female = next(n for n, g in cls.el.PERSON_GENDER_ROSTER.items() if g == "女")

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        for args in (["init", "-q"], ["config", "user.email", "t@example.com"],
                     ["config", "user.name", "t"]):
            subprocess.run(["git", *args], cwd=self.root, check=True, capture_output=True, text=True)
        (self.root / "seed.txt").write_text("seed", encoding="utf-8")
        subprocess.run(["git", "add", "-A"], cwd=self.root, check=True, capture_output=True)
        subprocess.run(["git", "commit", "-qm", "seed"], cwd=self.root, check=True, capture_output=True)
        self.letters = self.root / "6-人才与组织" / "部门AI专员跟进"
        self.letters.mkdir(parents=True)

    def tearDown(self):
        self._tmp.cleanup()

    def _letter(self, name: str, text: str) -> str:
        (self.letters / name).write_text(text, encoding="utf-8")
        return f"6-人才与组织/部门AI专员跟进/{name}"

    def _lock(self, *snapshot: str) -> dict:
        return {"who": "某会话", "dirty_at_acquire": list(snapshot)}

    def _run(self, waivers=None, lock=None, queue_texts=None):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            v = self.el._gender_sendside_guard_violations(self.root, waivers or [], lock, queue_texts)
        return v, out.getvalue()

    def test_no_letters_touched_prints_and_passes(self):
        (self.root / "别的.md").write_text(f"{self.male}她", encoding="utf-8")
        v, out = self._run()
        self.assertEqual(v, [])
        self.assertIn("本次未触碰跟进信件", out)

    def test_own_new_letter_with_wrong_pronoun_blocks(self):
        rel = self._letter("财务部-x-跟进-2026-09-12-y.md", f"{self.female}说他会来。")
        v, out = self._run(lock=self._lock("别的文件.md"))
        self.assertEqual(len(v), 1)
        self.assertIn(rel, v[0])
        self.assertIn("寄出去撤不回", v[0])
        self.assertIn("命中 1 处", out)

    def test_docx_also_blocks(self):
        """md 改好、docx 没重出 ⇒ 照样翻车，docx 必须在扫。"""
        (self.letters / "财务部-x-跟进-2026-09-12-y.docx").write_bytes(
            _docx_bytes([[self.female, "说", "他", "会来。"]]))
        v, _ = self._run(lock=self._lock())
        self.assertEqual(len(v), 1)
        self.assertIn(".docx:1", v[0])

    def test_correct_letter_passes(self):
        self._letter("财务部-x-跟进-2026-09-12-y.md", f"{self.female}说她会来。")
        v, out = self._run(lock=self._lock())
        self.assertEqual(v, [])
        self.assertIn("命中 0 处", out)

    def test_others_letter_degrades_to_warning(self):
        rel = self._letter("财务部-他线在办.md", f"{self.female}说他会来。")
        v, out = self._run(lock=self._lock(rel))
        self.assertEqual(v, [])
        self.assertIn("不落在本次持锁者触碰过的信件里", out)
        self.assertIn(rel, out)

    def test_registered_in_own_batch_reattributes(self):
        rel = self._letter("财务部-先写后锁.md", f"{self.female}说他会来。")
        queue_texts = {"q.md": "\n".join([
            "## 二、待 commit 批次", "",
            "| 批次 | 文件清单 | 建议 message | 状态 |", "|------|---------|--------------|------|",
            f"| B-0912_称谓 | `{rel}` | docs(x) | 待处理 |", "",
        ])}
        v, _ = self._run(lock=self._lock(rel), queue_texts=queue_texts)
        self.assertEqual(len(v), 1)

    def test_note_waiver_passes_with_trace(self):
        self._letter("财务部-x.md", f"{self.female}说他会来。")
        v, out = self._run(waivers=[f"{self.el.GENDER_PRONOUN_WAIVER_MARKER}原样引用旧信"], lock=self._lock())
        self.assertEqual(v, [])
        self.assertIn("检测到性别豁免声明", out)

    def test_inline_waiver_in_letter_passes(self):
        self._letter("财务部-x.md", f"{self.female}说他会来（性别豁免：引用对方原话）。")
        v, _ = self._run(lock=self._lock())
        self.assertEqual(v, [])

    def test_git_status_failure_is_fail_closed(self):
        self._letter("财务部-x.md", f"{self.female}说她会来。")
        with unittest.mock.patch.object(self.el, "_local_git_status_paths", return_value=None):
            v, _ = self._run()
        self.assertEqual(len(v), 1)
        self.assertIn("fail-closed", v[0])

    def test_readme_and_row_logs_are_not_letters(self):
        self._letter("README-跟进机制与命名约定.md", f"{self.female}说他会来。")
        (self.letters / "跟进信行日志").mkdir()
        (self.letters / "跟进信行日志" / "财务部#14.md").write_text(f"{self.female}说他会来。", encoding="utf-8")
        v, out = self._run(lock=self._lock())
        self.assertEqual(v, [])
        self.assertIn("本次未触碰跟进信件", out)


class CliTests(unittest.TestCase):
    """黑盒：退出码三态与回显必有的那一行。"""

    def _cli(self, *args: str) -> tuple[int, str]:
        proc = subprocess.run([sys.executable, str(TOOL), *args], capture_output=True,
                              text=True, encoding="utf-8", cwd=HERE.parent)
        return proc.returncode, proc.stdout + proc.stderr

    def test_missing_mode_errors(self):
        rc, out = self._cli()
        self.assertEqual(rc, 2)

    def test_explicit_file_paths(self):
        el = _load_editlock()
        female = next(n for n, g in el.PERSON_GENDER_ROSTER.items() if g == "女")
        with tempfile.TemporaryDirectory() as tmp:
            bad = Path(tmp) / "a.md"
            bad.write_text(f"{female}说他会来。", encoding="utf-8")
            good = Path(tmp) / "b.md"
            good.write_text(f"{female}说她会来。", encoding="utf-8")
            rc, out = self._cli(str(bad))
            self.assertEqual(rc, 1)
            self.assertIn("命中 1 处", out)
            rc, out = self._cli(str(good))
            self.assertEqual(rc, 0)
            self.assertIn("命中 0 处", out)
            rc, out = self._cli(str(Path(tmp) / "不存在.md"))
            self.assertEqual(rc, 2)

    def test_all_on_repo_is_green_with_whitelist(self):
        """建档日实扫：白名单之外零命中——这条红了说明有新信写错，或有人往白名单外的
        历史件动了手。"""
        rc, out = self._cli("--all")
        self.assertEqual(rc, 0, out)
        self.assertIn("白名单跳过历史件", out)


if __name__ == "__main__":
    unittest.main()
