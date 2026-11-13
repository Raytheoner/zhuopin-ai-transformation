"""补件入口合同：临时 README，绝不登记/批准/发送真实信件。"""
import importlib.util
import sys
from pathlib import Path
from unittest.mock import patch
import unittest

BASE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("supplement_registry_helpers", BASE / "test_工具-跟进信README登记.py")
helpers = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = helpers
spec.loader.exec_module(helpers)

SUPPLEMENT_HEADER = (
    "\n## 补件登记（不占编号、不占串行闸）\n\n"
    "| 承接编号 | 日期 | 收信人 | 主要事项 | 需回复 | 发送状态 |\n"
    "|---|---|---|---|---|---|\n"
)

class SupplementRegistryTests(helpers.RegistryCliTestBase):
    def prepare(self, number="采购部#27", recipient="采购部 · 姚祖怡", reply="是", status="📨 回件已到，待拆件"):
        self._write_readme(helpers._row(number, recipient, "原信事项", "原交期", status))
        path = self.root / helpers.README_REL
        path.write_text(path.read_text(encoding="utf8") + SUPPLEMENT_HEADER, encoding="utf8")
        letter = self._write_letter(name="补件.md", extra_fields=f"承接编号: {number}\n收信人: {recipient}")
        return dict(who="supplement-test", number=number, date="2026-11-12", topic="唯一补件事项", letter_path=letter, reply_required=reply)

    def call(self, **args):
        return self._run(self.module.cmd_append_supplement, **args)

    def test_two_existing_inflight_numbers_keep_parent_gate_and_number(self):
        for number, recipient in (("采购部#27", "采购部 · 姚祖怡"), ("质量部#18", "质量部 · 陈忱")):
            with self.subTest(number=number):
                args = self.prepare(number, recipient)
                original = self.module.iter_rows(self._readme_text())[0].cells.copy()
                with patch.object(self.module.gate_query, "_next_available_number", side_effect=AssertionError("补件不应取号")):
                    code, out, err = self.call(**args)
                self.assertEqual(code, 0, err)
                self.assertEqual(self.module.iter_rows(self._readme_text())[0].cells, original)
                rows = self.module.iter_rows(self._readme_text(), self.module.SUPPLEMENT_TABLE_SECTION)
                self.assertEqual(len(rows), 1)
                self.assertEqual(rows[0].cells, [number, "2026-11-12", recipient, args["topic"], "是", self.module.DRAFT_STATUS])
                self.assertIn("[READBACK]", out)
                self.assertIn("--table 补件", out)
                self.assertEqual(self._lock_calls[-2:], [("acquire", args["who"]), ("release", args["who"])])

    def test_no_reply_stays_draft_until_existing_approval_sender(self):
        args = self.prepare(reply="否")
        code, _, err = self.call(**args)
        self.assertEqual(code, 0, err)
        row = self.module.iter_rows(self._readme_text(), self.module.SUPPLEMENT_TABLE_SECTION)[0]
        self.assertEqual(row.cells[4:], ["否", "⏳ 待你审"])

    def test_repeat_registration_refused_without_new_number_or_write(self):
        args = self.prepare()
        self.assertEqual(self.call(**args)[0], 0)
        before = self._readme_text()
        self.assertEqual(self.call(**args)[0], 1)
        self.assertEqual(self._readme_text(), before)

    def test_other_supplement_rows_and_other_sections_preserved(self):
        args = self.prepare()
        path = self.root / helpers.README_REL
        existing = "| 财务部#15 | 2026-08-25 | 财务部 · 唐燕萍 | 历史补件 | 否 | ✅ 无需回复 |\n"
        path.write_text(self._readme_text() + existing + "\n## 后续章节\n\n他人记录。\n", encoding="utf8")
        self.assertEqual(self.call(**args)[0], 0)
        self.assertIn(existing, self._readme_text())
        self.assertTrue(self._readme_text().endswith("## 后续章节\n\n他人记录。\n"))

    def test_fresh_read_after_lock_preserves_author_update(self):
        args = self.prepare()
        old_lock = self.module._run_lock
        def concurrent(action, who, note=None):
            result = old_lock(action, who, note)
            if action == "acquire":
                (self.root / helpers.README_REL).write_text(self._readme_text().replace("原信事项", "他人刚更新的原信事项"), encoding="utf8")
            return result
        self.module._run_lock = concurrent
        self.assertEqual(self.call(**args)[0], 0)
        self.assertIn("他人刚更新的原信事项", self._readme_text())

    def test_duplicate_added_during_lock_is_not_overwritten(self):
        args = self.prepare()
        old_lock = self.module._run_lock
        def concurrent(action, who, note=None):
            result = old_lock(action, who, note)
            if action == "acquire":
                text = self._readme_text() + f"| 采购部#27 | 2026-11-12 | 采购部 · 姚祖怡 | {args['topic']} | 是 | ⏳ 待你审 |\n"
                (self.root / helpers.README_REL).write_text(text, encoding="utf8")
            return result
        self.module._run_lock = concurrent
        self.assertEqual(self.call(**args)[0], 1)
        self.assertEqual(len(self.module.iter_rows(self._readme_text(), self.module.SUPPLEMENT_TABLE_SECTION)), 1)
        self.assertEqual(self._lock_calls[-1][0], "release")

    def test_missing_native_parent_never_allocates_new_number(self):
        args = self.prepare()
        args["number"] = "采购部#999"
        before = self._readme_text()
        self.assertEqual(self.call(**args)[0], 1)
        self.assertEqual(self._readme_text(), before)
        self.assertEqual(self._lock_calls, [])

    def test_parent_draft_refused(self):
        args = self.prepare(status="⏳ 待你审")
        self.assertEqual(self.call(**args)[0], 1)
        self.assertEqual(self._lock_calls, [])

    def test_letter_number_or_recipient_mismatch_refused(self):
        for binding in ("承接编号: 采购部#28\n收信人: 采购部 · 姚祖怡", "承接编号: 采购部#27\n收信人: 质量部 · 陈忱"):
            with self.subTest(binding=binding):
                args = self.prepare()
                args["letter_path"] = self._write_letter(name="错绑.md", extra_fields=binding)
                before = self._readme_text()
                self.assertEqual(self.call(**args)[0], 1)
                self.assertEqual(self._readme_text(), before)

    def test_existing_letter_frontmatter_does_not_require_new_business_fields(self):
        args = self.prepare()
        args["letter_path"] = self.default_letter
        self.assertEqual(self.call(**args)[0], 0)

    def test_missing_decision_points_refused(self):
        args = self.prepare()
        args["letter_path"] = self._write_letter(decision=None)
        self.assertEqual(self.call(**args)[0], 1)
        self.assertEqual(self._lock_calls, [])

    def test_invalid_reply_field_and_injected_topic_refused(self):
        for overrides in ({"reply_required": ""}, {"reply_required": "待定"}, {"topic": "事项|越列"}, {"topic": "事项\n换行"}):
            with self.subTest(overrides=overrides):
                args = self.prepare()
                args.update(overrides)
                before = self._readme_text()
                self.assertEqual(self.call(**args)[0], 1)
                self.assertEqual(self._readme_text(), before)

    def test_missing_supplement_section_never_falls_back_to_main(self):
        args = self.prepare()
        before = self._readme_text().split("\n## 补件登记")[0]
        (self.root / helpers.README_REL).write_text(before, encoding="utf8")
        self.assertEqual(self.call(**args)[0], 1)
        self.assertEqual(self._readme_text(), before)

    def test_empty_supplement_and_reordered_columns(self):
        args = self.prepare()
        text = self._readme_text().replace("| 承接编号 | 日期 | 收信人 | 主要事项 | 需回复 | 发送状态 |", "| 发送状态 | 需回复 | 主要事项 | 收信人 | 日期 | 承接编号 |")
        (self.root / helpers.README_REL).write_text(text, encoding="utf8")
        code, out, err = self.call(**args)
        self.assertEqual(code, 0, err)
        self.assertIn('[READBACK]', out)
        row = self.module.iter_rows(self._readme_text(), self.module.SUPPLEMENT_TABLE_SECTION)[0]
        self.assertEqual(row.cells[0], "⏳ 待你审")
        self.assertEqual(row.cells[-1], "采购部#27")

    def test_dry_run_does_not_acquire_lock_or_write(self):
        args = self.prepare()
        before = self._readme_text()
        self.assertEqual(self.call(**args, dry_run=True)[0], 0)
        self.assertEqual(self._readme_text(), before)
        self.assertEqual(self._lock_calls, [])

    def test_lock_failure_does_not_write(self):
        args = self.prepare()
        before = self._readme_text()
        self.module._run_lock = lambda *a, **kw: False
        self.assertEqual(self.call(**args)[0], 1)
        self.assertEqual(self._readme_text(), before)

    def test_readback_failure_retains_lock_and_reports_failure(self):
        args = self.prepare()
        def failed(*a):
            raise self.module.ReadbackMismatchError("模拟回读不一致")
        self.module._write_readback = failed
        code, out, err = self.call(**args)
        self.assertEqual(code, 1)
        self.assertNotIn("[OK]", out)
        self.assertIn("READBACK-FAILED", err)
        self.assertEqual(self._lock_calls, [("acquire", args["who"])])

    def test_release_rejection_never_reports_success(self):
        args = self.prepare()
        self._release_should_succeed = False
        code, out, err = self.call(**args)
        self.assertEqual(code, 1)
        self.assertNotIn("[OK]", out)
        self.assertIn("WRITTEN-LOCK-HELD", err)

    def test_cli_requires_reply_choice_and_has_no_send_or_new_number_switch(self):
        args = ["append-supplement", "--who", "t", "--number", "采购部#27", "--date", "2026-11-12", "--topic", "补件", "--letter-path", self.default_letter]
        with self.assertRaises(SystemExit) as exc:
            self.module.main(args)
        self.assertEqual(exc.exception.code, 2)

if __name__ == "__main__":
    unittest.main()
