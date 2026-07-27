"""xlsx_report.py 测试 —— Excel 评分表导出（陈忱灰度反馈 #116 ③）。

格式基准＝陈忱回件模板（评审汇总/评审明细/扣分明细 3 sheet），本测试锁定：
sheet 名与列头对齐模板、82 条规则全量出现在评审明细、扣分明细只含待改进/不合格、
冻结表头 + 模块筛选（auto_filter）就绪、下载文件名符合陈忱指定格式。
"""
from datetime import datetime

from qd_b_gate.evaluate import evaluate
from qd_b_gate.xlsx_report import (
    _DETAIL_COLUMNS,
    _sanitize_filename_part,
    build_workbook,
    report_filename,
)


class TestWithHuafeng:
    """真实黄金样本（华丰，技术服务类，一票否决=不合格）端到端导出验证。"""

    def _result(self, huafeng_path, tmp_path):
        return evaluate(huafeng_path, audit_path=tmp_path / "audit.jsonl", sample_id="华丰")

    def test_workbook_has_three_sheets_matching_template(self, huafeng_path, tmp_path):
        wb = build_workbook(self._result(huafeng_path, tmp_path))
        assert wb.sheetnames == ["评审汇总", "评审明细", "扣分明细"]

    def test_detail_sheet_header_matches_template_columns(self, huafeng_path, tmp_path):
        wb = build_workbook(self._result(huafeng_path, tmp_path))
        ws = wb["评审明细"]
        header = [c.value for c in ws[3]]
        assert header == _DETAIL_COLUMNS

    def test_detail_sheet_contains_all_82_rules(self, huafeng_path, tmp_path):
        wb = build_workbook(self._result(huafeng_path, tmp_path))
        ws = wb["评审明细"]
        data_rows = [row for row in ws.iter_rows(min_row=4, values_only=True)
                    if isinstance(row[0], int)]
        assert len(data_rows) == 82

    def test_detail_sheet_has_frozen_header_and_autofilter(self, huafeng_path, tmp_path):
        wb = build_workbook(self._result(huafeng_path, tmp_path))
        ws = wb["评审明细"]
        assert ws.freeze_panes == "A4"
        assert ws.auto_filter.ref is not None

    def test_deduction_sheet_only_contains_violated_statuses(self, huafeng_path, tmp_path):
        wb = build_workbook(self._result(huafeng_path, tmp_path))
        ws = wb["扣分明细"]
        statuses = {row[4] for row in ws.iter_rows(min_row=4, values_only=True) if row[4]}
        assert statuses and statuses <= {"不合格", "待改进"}

    def test_summary_sheet_shows_verdict_and_project_name(self, huafeng_path, tmp_path):
        wb = build_workbook(self._result(huafeng_path, tmp_path))
        ws = wb["评审汇总"]
        assert "不合格" in ws["A4"].value
        assert ws["B10"].value == "华丰天然气发动机EPA认证服务咨询项目"

    def test_report_filename_uses_project_name_and_date(self, huafeng_path, tmp_path):
        result = self._result(huafeng_path, tmp_path)
        name = report_filename(result, when=datetime(2026, 7, 27, 10, 0))
        assert name == "华丰天然气发动机EPA认证服务咨询项目_评审报告_20260727.xlsx"


def test_sanitize_filename_part_strips_forbidden_filesystem_chars():
    assert _sanitize_filename_part('A/B\\C:D*E?F"G<H>I|J') == "A_B_C_D_E_F_G_H_I_J"


def test_sanitize_filename_part_empty_falls_back_to_placeholder():
    assert _sanitize_filename_part("") == "未命名项目"
