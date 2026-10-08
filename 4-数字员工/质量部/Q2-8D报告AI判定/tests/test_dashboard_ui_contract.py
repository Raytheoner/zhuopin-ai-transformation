from copy import deepcopy
from dataclasses import replace
from html import escape
from html.parser import HTMLParser
from pathlib import Path
import builtins
import socket
import pytest
from q2_8d_verdict import config, dashboard, webapp
from q2_8d_verdict.models import (
    Disposition, RedlineFinding, RedlineStatus, RuleFinding, RuleStatus, Verdict,
)


def _case(**changes):
    rules = tuple(RuleFinding(
        f"rule-{i}", step, f"维度-{i}", "词面核对", 3.0,
        0.0 if step == "D6" else 1.0,
        RuleStatus.PENDING if step == "D6" else RuleStatus.PARTIAL, f"依据-{step}",
    ) for i, step in enumerate(dashboard.STEPS, 1))
    verdict = Verdict(
        report_id="合成检查-1", scene="制造", scene_flags=("场景待核",),
        structural_return=False, structural_empty_sections=(),
        redlines=tuple(RedlineFinding(i, "D6", f"描述-{i}", status, f"红线依据-{i}")
                       for i, status in enumerate(RedlineStatus, 1)),
        rules=rules, score_auto=6.0, score_pending_max=3.0, score_max=21.0,
        grade=None, grade_range=("D", "C"), disposition=Disposition.MANUAL,
        needs_manual_review=True, automation_level="L2", notes=("人工核实措施",),
    )
    return replace(verdict, **changes)


def _locked(monkeypatch, verdicts):
    before = deepcopy(verdicts)
    def forbidden(*args, **kwargs):
        raise AssertionError("渲染调用了禁止的业务/文件/网络接口")
    with monkeypatch.context() as patch:
        patch.setattr(webapp, "create_app", forbidden)
        patch.setattr(webapp.VerdictEngine, "__init__", forbidden)
        patch.setattr(webapp.VerdictEngine, "evaluate", forbidden)
        patch.setattr(webapp.feed_source, "load_mock", forbidden)
        patch.setattr(webapp.AuditLogger, "jsonl", forbidden)
        patch.setattr(builtins, "open", forbidden)
        for method in ("open", "read_text", "read_bytes", "write_text", "write_bytes"):
            patch.setattr(Path, method, forbidden)
        patch.setattr(socket.socket, "connect", forbidden)
        patch.setattr(socket, "create_connection", forbidden)
        page = webapp._render_page(verdicts)
    assert verdicts == before
    return page


class _TableParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.tables, self.caption, self.rows = {}, "", []
        self.row, self.cell, self.in_caption = [], None, False
    def handle_starttag(self, tag, attrs):
        if tag == "table":
            self.caption, self.rows = "", []
        elif tag == "caption":
            self.in_caption = True
        elif tag == "tr":
            self.row = []
        elif tag in ("th", "td"):
            self.cell = ""
    def handle_data(self, data):
        if self.in_caption:
            self.caption += data
        if self.cell is not None:
            self.cell += data
    def handle_endtag(self, tag):
        if tag == "caption":
            self.in_caption = False
        elif tag in ("th", "td"):
            self.row.append(self.cell)
            self.cell = None
        elif tag == "tr":
            self.rows.append(self.row)
        elif tag == "table":
            self.tables[self.caption] = self.rows


def _tables(page):
    parser = _TableParser()
    parser.feed(page)
    return parser.tables


def test_aggregate_original_values(monkeypatch):
    verdicts = [_case(), _case(report_id="第二份", grade="A",
                              disposition=Disposition.ARCHIVE)]
    tables = _tables(_locked(monkeypatch, verdicts))
    summary = dashboard.summarize(verdicts)
    assert tables["七维得分（已自动判定部分）"][1:] == [
        [step, str(v["auto"]), str(v["max"]), ""]
        for step, v in summary["by_step"].items()
    ]
    assert tables["分级分布"][1:] == [[g, str(n)] for g, n in summary["by_grade"].items()]
    assert tables["处置建议分布"][1:] == [
        [d, str(n)] for d, n in summary["by_disposition"].items()
    ]


@pytest.mark.parametrize("status", list(RedlineStatus))
def test_redline_fields_and_original_status(monkeypatch, status):
    finding = RedlineFinding(8, "D6", "原描述", status, "原依据")
    tables = _tables(_locked(monkeypatch, [_case(redlines=(finding,))]))
    assert tables["逐红线依据"][1:] == [["8", "D6", "原描述", status.value, "原依据"]]
    hits = tables["需关注的红线记录"][1:]
    assert hits == ([["本批无此类记录"]] if status == RedlineStatus.CLEAR
                    else [["合成检查-1", "8", status.value]])


@pytest.mark.parametrize("status", list(RuleStatus))
def test_rule_fields_and_original_status(monkeypatch, status):
    finding = RuleFinding("原规则", "D6", "措施验证", "原方法", 4.0, 0.0, status, "原依据")
    tables = _tables(_locked(monkeypatch, [_case(rules=(finding,))]))
    assert tables["逐规则依据"][1:] == [[
        "原规则", "D6", "措施验证", "原方法", status.value, "0.0", "4.0", "原依据"
    ]]


@pytest.mark.parametrize("grade,expected", [(None, "D → C（待人工）"), ("B", "B")])
def test_grade_and_score_bounds(monkeypatch, grade, expected):
    page = _locked(monkeypatch, [_case(grade=grade)])
    assert f"<dd>{expected}</dd>" in page
    for label, value in (("已自动判定得分", "6.0"), ("可能得分上界", "9.0"),
                         ("待人工部分满分", "3.0"), ("适用满分", "21.0")):
        assert f"<dt>{label}</dt><dd>{value}</dd>" in page
    assert "上界不是最终评分" in page


@pytest.mark.parametrize("flag", [True, False])
def test_manual_flag_and_human_responsibility(monkeypatch, flag):
    page = _locked(monkeypatch, [_case(needs_manual_review=flag, grade="A",
                                     disposition=Disposition.ARCHIVE)])
    assert f"<dt>需要人工复核</dt><dd>{'是' if flag else '否'}</dd>" in page
    assert "质量工程师" in page and "此页不提交退回/签发" in page
    assert "建议归档" in page and "L2" in page


def test_structural_return_without_findings(monkeypatch):
    page = _locked(monkeypatch, [_case(
        structural_return=True, structural_empty_sections=("D3", "D6"),
        rules=(), redlines=(), score_auto=0.0, score_pending_max=0.0,
        disposition=Disposition.STRUCTURAL_RETURN, notes=("原结构备注",),
    )])
    assert "D3" in page and "D6" in page and "原结构备注" in page
    assert "原结果：结构性退回" in page and "建议结构性退回" in page
    assert "全部合格" not in page and "全部通过" not in page


def test_empty_batch_zero_dimensions_and_empty_lists(monkeypatch):
    empty = _locked(monkeypatch, [])
    assert "暂无报告结果" in empty and "报告数：0" in empty
    assert "mock合成数据" in empty and "质量工程师" in empty
    tables = _tables(_locked(monkeypatch, [_case(rules=(), redlines=())]))
    assert tables["七维得分（已自动判定部分）"][1:] == [
        [s, "0.0", "0.0", "本批无可计分项"] for s in dashboard.STEPS
    ]
    assert tables["分级分布"][1:] == [
        ["A", "0"], ["B", "0"], ["C", "0"], ["D", "0"], [dashboard.PENDING_BUCKET, "1"]
    ]
    assert tables["需关注的红线记录"][1:] == [["本批无此类记录"]]


def test_missing_evidence_version_and_grade_range(monkeypatch):
    monkeypatch.setattr(config, "RULE_VERSION", "")
    rule = RuleFinding("缺依据", "D6", "维度", "方法", 3.0, 0.0, RuleStatus.PENDING, "")
    redline = RedlineFinding(1, "D6", "描述", RedlineStatus.SUSPECTED, "")
    page = _locked(monkeypatch, [_case(rules=(rule,), redlines=(redline,),
                                     grade_range=("", ""))])
    assert "规则版本：未提供" in page and "等级范围未提供（待人工）" in page
    assert page.count("依据未提供") >= 2


def test_html_long_text_scene_notes_and_unique_anchors(monkeypatch):
    hostile = '<script>alert("x")</script>&' + "长中文" * 100
    page = _locked(monkeypatch, [_case(report_id=hostile, scene=hostile,
                                       scene_flags=(hostile,), notes=(hostile,)),
                                _case(report_id=hostile)])
    assert "<script>" not in page and escape(hostile, quote=True) in page
    assert page.count('id="q2-report-1"') == 1
    assert page.count('id="q2-report-2"') == 1
    assert 'id="' + hostile not in page
    assert "场景标记" in page and "原备注" in page


def test_source_and_capability_gaps(monkeypatch):
    monkeypatch.setattr(config, "DATA_SOURCE_DEFAULT", "real")
    page = _locked(monkeypatch, [_case()])
    for text in ("档1 · mock合成数据", "非真实8D评审结论", "AI建议",
                 "源数据更新时间未提供", "单份审计标识未接入",
                 "原报告入口未接入", "复核人及签认时间未提供"):
        assert text in page
    for tag in ("<form", "<button", "<input", "<script"):
        assert tag not in page
    assert 'href="http://192.168.100.51:8092/"' in page


def test_original_markdown_and_no_external_calls(monkeypatch):
    verdicts = [_case(report_id="<原Markdown>&"), _case(report_id="第二份")]
    md = dashboard.render_markdown(verdicts, rule_version=config.RULE_VERSION,
                                   automation_level=config.AUTOMATION_LEVEL)
    assert f"<pre>{escape(md, quote=True)}</pre>" in _locked(monkeypatch, verdicts)

def test_layout_css_and_semantic_scroll_regions(monkeypatch):
    page = _locked(monkeypatch, [_case()])
    for token in ("grid-template-columns: repeat(2, minmax(0, 1fr))",
                  "@media (max-width: 700px)", "grid-template-columns: 1fr",
                  "overflow-x: auto", "overflow-wrap: anywhere",
                  "prefers-reduced-motion", "min-height: 44px", ":focus-visible"):
        assert token in page
    assert 'role="region" tabindex="0" aria-label="逐规则依据"' in page
    assert '<th scope="col">' in page and '<details class="report-detail"' in page
    assert 'role="dialog"' not in page and '<script' not in page


def test_long_rule_and_version_are_escaped(monkeypatch):
    long_text = '<img src=x onerror="alert(1)">&' + "长依据" * 200
    monkeypatch.setattr(config, "RULE_VERSION", long_text)
    rule = RuleFinding(long_text, "D6", long_text, long_text, 3.0, 0.0,
                       RuleStatus.PENDING, long_text)
    page = _locked(monkeypatch, [_case(rules=(rule,), scene_flags=(long_text,))])
    assert "<img" not in page and escape(long_text, quote=True) in page
