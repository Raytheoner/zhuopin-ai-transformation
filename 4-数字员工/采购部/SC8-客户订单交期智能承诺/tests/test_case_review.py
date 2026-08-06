"""判例包网页表单化测试（队列 #110 Feature B）：加载/列举 + 07-28 硬设计约束的渲染验证。"""
from __future__ import annotations

import json

import pytest

from sc8 import case_review


def _write_package(d, package_id="pkg-1", cases=None):
    cases = cases if cases is not None else [
        {"case_no": 1, "scenario": "真实场景A", "current_verdict": "现状A", "proposed_verdict": "拟改A"},
        {"case_no": 2, "scenario": "真实场景B", "current_verdict": "现状B", "proposed_verdict": "拟改B"},
    ]
    data = {"package_id": package_id, "title": "批X · 议题", "recipient": "姚祖怡", "cases": cases}
    (d / f"{package_id}.json").write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return data


def test_load_package_roundtrip(tmp_path):
    _write_package(tmp_path)
    pkg = case_review.load_package(tmp_path, "pkg-1")
    assert pkg.package_id == "pkg-1"
    assert pkg.title == "批X · 议题"
    assert pkg.recipient == "姚祖怡"
    assert len(pkg.cases) == 2
    assert pkg.cases[0].scenario == "真实场景A"


def test_load_package_missing_raises_file_not_found(tmp_path):
    with pytest.raises(FileNotFoundError):
        case_review.load_package(tmp_path, "nope")


def test_list_packages_empty_dir_returns_empty(tmp_path):
    assert case_review.list_packages(tmp_path) == []


def test_list_packages_missing_dir_returns_empty(tmp_path):
    assert case_review.list_packages(tmp_path / "does-not-exist") == []


def test_list_packages_skips_corrupt_json(tmp_path):
    _write_package(tmp_path, package_id="good")
    (tmp_path / "bad.json").write_text("not json", encoding="utf-8")
    (tmp_path / "missing-field.json").write_text('{"package_id":"x"}', encoding="utf-8")
    pkgs = case_review.list_packages(tmp_path)
    assert [p.package_id for p in pkgs] == ["good"]


def test_render_review_page_shows_all_case_fields(tmp_path):
    _write_package(tmp_path)
    pkg = case_review.load_package(tmp_path, "pkg-1")
    html = case_review.render_review_page(pkg)
    assert "真实场景A" in html and "现状A" in html and "拟改A" in html
    assert "真实场景B" in html


def test_render_review_page_verdict_and_note_are_independent_fields():
    """硬约束①：✅/❌（verdict_N）与 ✏️ 自由文本（note_N）必须是各自独立的表单字段，
    不是同一个 select/三选一控件——即"✏️非空 ≠ 改判"，两者互不覆盖。"""
    pkg = case_review.CaseReviewPackage(
        package_id="p", title="t", recipient="r",
        cases=[case_review.CaseItem(case_no=1, scenario="s", current_verdict="c", proposed_verdict="p")],
    )
    html = case_review.render_review_page(pkg)
    assert 'name="verdict_1"' in html
    assert 'name="note_1"' in html
    # 两个字段名不同、互相独立（不是同一个 name，不会互相覆盖提交值）
    assert 'name="verdict_1"' != 'name="note_1"'


def test_render_review_page_has_unconstrained_supplement_section():
    """硬约束②：表单末尾必须有不受约束的自由补充区。"""
    pkg = case_review.CaseReviewPackage(package_id="p", title="t", recipient="r", cases=[])
    html = case_review.render_review_page(pkg)
    assert 'name="supplement"' in html


def test_render_review_page_supports_appending_new_issues():
    """硬约束③：支持一次提交内追加"新增问题"条目（前端可重复添加 name="new_issue" 字段）。"""
    pkg = case_review.CaseReviewPackage(package_id="p", title="t", recipient="r", cases=[])
    html = case_review.render_review_page(pkg)
    assert "new_issue" in html
    assert "rv-add-issue" in html  # 前端追加按钮存在


def test_render_review_page_escapes_html_in_scenario():
    pkg = case_review.CaseReviewPackage(
        package_id="p", title="t", recipient="r",
        cases=[case_review.CaseItem(case_no=1, scenario="<script>alert(1)</script>",
                                    current_verdict="c", proposed_verdict="p")],
    )
    html = case_review.render_review_page(pkg)
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;" in html
