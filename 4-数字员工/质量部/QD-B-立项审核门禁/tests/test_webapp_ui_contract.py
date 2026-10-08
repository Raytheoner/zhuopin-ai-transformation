"""只消费合成展示对象；不调用上传、解析、evaluate 或 audit writer。"""
import html
import re
from html.parser import HTMLParser

import pytest

from zhuopin_platform.audit import AuditEvent
from qd_b_gate.evaluate import EvaluationResult
from qd_b_gate.models import ExtractStatus, FieldValue, ProposalDocument, RuleResult, Verdict
from qd_b_gate.report import DISCLAIMER, GateReport
from qd_b_gate.report_items import build_module_rates, build_scored_items
from qd_b_gate.rules.registry import load_registry
from qd_b_gate.scoring import ModuleScore, ScoreResult
from qd_b_gate.webapp import _INDEX_BODY, _PAGE_HEAD, _report_page


class TableReader(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tables = {}
        self.active = None
        self.rows = []
        self.cells = []
        self.cell_text = None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "table":
            self.active = attrs.get("id", "anonymous")
            self.rows = []
        elif tag == "tr" and self.active:
            self.cells = []
        elif tag == "td" and self.active:
            self.cell_text = ""

    def handle_data(self, text):
        if self.cell_text is not None:
            self.cell_text += text

    def handle_endtag(self, tag):
        if tag == "td" and self.cell_text is not None:
            self.cells.append(self.cell_text)
            self.cell_text = None
        elif tag == "tr" and self.active and self.cells:
            self.rows.append(self.cells)
        elif tag == "table" and self.active:
            self.tables[self.active] = self.rows
            self.active = None


def make_display_result(*, tier="有条件合格", timestamp="2026-10-08T01:30:00+00:00"):
    """字段与结果直接构造，评分数字也是展示输入，没有执行业务运算。"""
    reg = load_registry()
    verdicts = list(Verdict)
    results = [RuleResult(
        rule_id=rule.rule_id, check_item=rule.check_item,
        verdict=verdicts[i % len(verdicts)], evidence=f"合成依据{i} <script> & \"长中文\"" + "资料核对" * 12,
        suggestion=f"合成建议{i} <补充资料>",
    ) for i, rule in enumerate(reg.rules)]
    modules = {mk: ModuleScore(mk, float(base), float(base) * .25, float(base) * .75)
               for mk, base in reg.scoring["module_base_scores"].items()}
    sr = ScoreResult(False, [], 75.0, tier, modules, True, 55, 2)
    doc = ProposalDocument(template_version="A2.1", project_type="产品类")
    key = "一、项目信息/项目名称"
    doc.fields[key] = FieldValue(key, "合成项目 <img src=x onerror=alert(1)> &长中文" * 3, ExtractStatus.EXTRACTED)
    cross = [RuleResult(f"C{i:02}", f"合成跨模块{i}", verdicts[(i - 1) % len(verdicts)],
                        evidence=f"跨模块依据{i} <只读>", suggestion=f"跨模块建议{i}")
             for i in range(1, 11)]
    rep = GateReport(tier, sr,
                     [r for r in results if r.verdict == Verdict.FAIL],
                     [r for r in results if r.verdict == Verdict.WARN],
                     [r for r in results if r.verdict == Verdict.MANUAL],
                     results, "A2.1", "合成规则版本 <2026>", "产品类", "合成样本 <只读>", cross)
    event = AuditEvent("QD-B", "synthetic-display", "contract-test", "L2",
                       content_hash="1234567890abcdef" * 4, timestamp=timestamp)
    # AuditEvent 空值构造时会自动补当前时间；模拟历史缺值须明确赋空。
    event.timestamp = timestamp
    return EvaluationResult(doc, results, sr, rep, event)


def test_upload_preserves_contract_and_supports_mobile():
    page = _PAGE_HEAD + _INDEX_BODY
    assert 'name="viewport"' in page
    assert 'action="/evaluate" method="post" enctype="multipart/form-data"' in page
    assert 'name="proposal"' in page and 'accept=".xlsx"' in page and "required" in page
    assert "EQQR8082 A2.1" in page and "20 MB" in page
    assert '<label for="proposal"' in page


def test_report_exposes_navigation_and_distinguishes_time_sources():
    result = make_display_result()
    page = _report_page(result, "/download/synthetic.xlsx")
    assert 'href="#report-summary"' in page and 'href="#rule-evidence"' in page
    assert re.search(r'id="rule-evidence">\s*<h3>⑥', page)
    assert re.search(r'id="manual-todo">\s*<h3>⑦', page)
    assert "本次评估时间" in page and result.audit_event.timestamp in page
    assert "原始资料更新时间" in page and "未提供" in page
    assert html.escape(result.report.sample_id) in page
    assert html.escape(result.report.rule_version) in page
    assert "1234567890abcdef…" in page and html.escape(DISCLAIMER) in page
    assert 'href="/download/synthetic.xlsx"' in page and 'href="/"' in page


def test_missing_evaluation_time_is_not_replaced_by_current_time():
    page = _report_page(make_display_result(timestamp=""), "")
    assert "本次评估时间</b>：未提供" in page
    assert "原始资料更新时间</b>：未提供" in page
    assert "Excel 导出暂不可用" in page


def test_all_detail_rows_keep_status_numbers_evidence_and_suggestions():
    result = make_display_result()
    parser = TableReader()
    parser.feed(_report_page(result, ""))
    rows = parser.tables["detail-table"]
    items = build_scored_items(result.report)
    assert len(rows) == len(items) == 82
    for row, item in zip(rows, items):
        assert row == [str(item.idx), item.section, item.check_item, item.pass_condition,
                       item.status_label, f"{item.std_score:.2f}", f"{item.actual_score:.2f}",
                       f"-{item.deduction:.2f}" if item.deduction else "0.00", item.detail_text]
    assert len(build_module_rates(result.report)) == 13
    assert len(parser.tables["module-rates"]) == 13
    assert len(parser.tables["cross-results"]) == 10


@pytest.mark.parametrize("verdict", list(Verdict))
def test_cross_module_states_are_text_and_keep_evidence(verdict):
    result = make_display_result()
    result.report.cross_module_items = [RuleResult("C01", "合成检查", verdict,
                                                 evidence="依据 <html>", suggestion="建议 & 核对")]
    parser = TableReader()
    parser.feed(_report_page(result, ""))
    row = parser.tables["cross-results"][0]
    assert row[2] == ("待人工核" if verdict == Verdict.PENDING else verdict.value)
    assert "依据 <html>" in row[3] and "建议 & 核对" in row[3]


@pytest.mark.parametrize("tier", ["合格", "有条件合格", "不合格"])
def test_summary_keeps_input_tier_and_human_authority(tier):
    page = _report_page(make_display_result(tier=tier), "")
    assert tier in page and "75.0" in page
    expected_class = {"合格": "v-pass", "有条件合格": "v-warn", "不合格": "v-fail"}[tier]
    assert f'class="verdict {expected_class}"' in page
    assert html.escape(DISCLAIMER) in page
    assert "暂定" in page and "2 条 A 类规则未实现" in page


def test_long_text_is_escaped_and_all_sections_remain():
    result = make_display_result()
    page = _report_page(result, "")
    assert "<img src=x" not in page and "<script> &" not in page
    assert html.escape(result.document.get("一、项目信息/项目名称").value) in page
    for title in ["① 总判定", "② 各模块得分率", "③ 扣分明细", "④ 全量评审明细",
                  "⑤ 改进建议", "⑥ 跨模块", "⑦ 转人工", "⑧ 审计"]:
        assert title in page
    assert 'id="flt-module"' in page and 'id="flt-status"' in page and 'id="flt-problem"' in page
    assert 'data-label="详情"' in page


def test_veto_remains_a_veto_without_numeric_release_action():
    result = make_display_result(tier="不合格")
    result.score_result.veto = True
    page = _report_page(result, "")
    assert "❌ 一票否决" in page and '75.0<span' not in page
    assert html.escape(DISCLAIMER) in page


def test_empty_sections_and_unavailable_export_remain_explicit():
    result = make_display_result()
    result.report.all_results = []
    result.report.blocking_items = []
    result.report.warning_items = []
    result.report.manual_todo_items = []
    result.report.cross_module_items = []
    page = _report_page(result, "")
    assert "无待改进/不合格项" in page and "无跨模块校验结果" in page
    assert "转人工待办项（0 条）" in page and "Excel 导出暂不可用" in page
    assert "全量评审明细表（82 项）" in page  # 缺评估结果沿用未实现行，不丢注册表明细


def test_time_and_hash_metadata_are_escaped():
    result = make_display_result(timestamp='<time>&"')
    result.audit_event.content_hash = '<hash>&"'
    page = _report_page(result, "")
    assert html.escape(result.audit_event.timestamp) in page
    assert html.escape(result.audit_event.content_hash) in page
    assert '<time>' not in page and '<hash>' not in page


def test_desktop_score_cells_keep_complete_decimal_values():
    # 1440px 实际页图发现标准分等被长依据挤成两行；数字应完整可读。
    for label in ["序号", "标准分", "实得", "扣分"]:
        assert f'td[data-label="{label}"]' in _PAGE_HEAD
    assert 'white-space:nowrap' in _PAGE_HEAD.split('table.grid td[data-label="序号"]', 1)[1].split('}', 1)[0]
