"""轨 A 校准相关新行为测试（2026-07-04）。

覆盖：pptx 段落识别（点号 D1. + 无前缀标题回退）、不良分类/结案日期归一比对、
邮箱脱敏、xlsx 黄金样本加载。不依赖真实 8D 原文（gitignore/LAN）。
"""
from pathlib import Path

import pytest

from qda_prefill.calibrate import (_norm_category, clean_case_id, _compare_field,
                                    load_golden_xlsx)
from qda_prefill.doc_reader import _parse_sections, _title_section_key
from qda_prefill.scrubber import TokenState, scrub_text


# ── 段落识别（pptx 变体）──
def test_dot_separator_section_header():
    """「D1.团队成员」点号格式应识别为 D1。"""
    text = "D1.团队成员 Team member\n张三\nD2.问题描述\n漏气 NG"
    doc = _parse_sections(text, "x")
    assert "D1" in doc.sections and "D2" in doc.sections
    assert "漏气" in doc.sections["D2"]


def test_bare_title_fallback():
    """无「Dn.」前缀、只有中英文标题时，按 8D 步骤标题回退识别。"""
    text = "团队成员 Team member\n李四\n问题描述 Problem description\n短路失效\n围堵/临时措施\n隔离"
    doc = _parse_sections(text, "x")
    assert doc.sections.get("D1")
    assert "短路失效" in doc.sections.get("D2", "")
    assert doc.sections.get("D3")


def test_title_key_only_short_lines():
    assert _title_section_key("问题描述 Problem description") == "D2"
    assert _title_section_key("根本原因分析") == "D4"
    # 长正文行（>40字）不误判为标题
    assert _title_section_key("问题描述" + "补充说明历史沿革背景细节各种信息" * 4) is None


def test_section_fallback_fires_once():
    """同一 D 编号标题多次出现，只第一次作标头（防正文子标题重置段落）。"""
    text = "问题描述 Problem description\n正文A\n问题描述/ problem discripton：\n正文B"
    doc = _parse_sections(text, "x")
    assert "正文A" in doc.sections["D2"] and "正文B" in doc.sections["D2"]


# ── 比对归一 ──
def test_category_normalization():
    assert _norm_category("设计问题") == "设计"
    assert _norm_category("制程问题") == "制程"
    hit, score, _ = _compare_field("不良分类", "设计", "设计问题")
    assert hit and score == 1.0
    # 真实分歧不被归一掩盖
    hit2, _, _ = _compare_field("不良分类", "物料", "使用不当")
    assert not hit2


def test_closure_date_strips_time():
    hit, score, _ = _compare_field("结案日期", "2026-06-06", "2026-06-06 00:00:00")
    assert hit and score == 1.0


def test_clean_case_id():
    assert clean_case_id("8D-2026-06-001 连接器与电容干涉问题") == "8D-2026-06-001"
    assert clean_case_id("8D_2025_05_001") == "8D-2025-05-001"


# ── 邮箱脱敏（红线：不得漏网）──
def test_email_scrubbed():
    state = TokenState()
    res = scrub_text("联系 zhicheng.liu@equalitytec.com 确认", state)
    assert "@equalitytec.com" not in res.suggested
    assert "邮箱-" in res.suggested
    assert any(e.entity_type == "email" for e in res.entities)


def test_email_before_org_no_domain_leak():
    """邮箱先跑：ORG/OEM 不得吃掉 local-part 后残留域名。"""
    state = TokenState()
    res = scrub_text("wei.liu@cumeqelectronics.com", state)
    assert "cumeqelectronics.com" not in res.suggested


# ── 黄金样本加载 ──
def test_load_golden_xlsx():
    xlsx = Path("C:/Users/Paul Shao/OneDrive/Projects/企业AI转型/7-外部文档/质量部/"
                "产品类立项申请书及评审报告/AI质量智能建设就绪工作汇总.xlsx")
    if not xlsx.exists():
        pytest.skip("答案页 xlsx 不在预期路径")
    golden = load_golden_xlsx(xlsx)
    assert len(golden) == 7
    assert "8D-2026-06-001" in golden
    rec = golden["8D-2026-06-001"]
    assert rec["安全相关"] == "否"
    assert set(rec.keys()) >= {"案例ID", "不良分类", "安全相关", "结案日期"}
