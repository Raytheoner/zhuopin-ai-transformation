"""料品编码归一化预处理单测（design D14，spec: fi2-match-engine 附属）。"""
from __future__ import annotations

from fi2.item_normalize import normalize_item_code


def test_normalize_strips_whitespace():
    assert normalize_item_code("A 001") == normalize_item_code("A001")


def test_normalize_fullwidth_to_halfwidth():
    assert normalize_item_code("Ａ００１") == normalize_item_code("A001")


def test_normalize_bracket_variants_equivalent():
    assert normalize_item_code("A(001)") == normalize_item_code("A（001）")


def test_normalize_separator_dash_slash_equivalent():
    assert normalize_item_code("A-001") == normalize_item_code("A/001")


def test_normalize_case_insensitive():
    assert normalize_item_code("a001") == normalize_item_code("A001")


def test_normalize_empty_and_none_safe():
    assert normalize_item_code("") == ""
    assert normalize_item_code(None) == ""


def test_normalize_distinct_codes_stay_distinct():
    assert normalize_item_code("A001") != normalize_item_code("A002")
