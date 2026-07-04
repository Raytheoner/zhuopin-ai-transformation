"""scrubber 单测 — 实体识别与令牌建议。"""
from qda_prefill.scrubber import TokenState, build_token_table, scrub_text


def test_part_no_detected_and_tokenized():
    state = TokenState()
    result = scrub_text("产品料号 ZK8808 在高温下失效。", state)
    # ZK8808 应被识别为料号（大写字母开头+数字）
    assert any(e.entity_type == "part_no" for e in result.entities)
    assert "ZK8808" in state.mapping
    assert state.mapping["ZK8808"].startswith("料号-")


def test_same_entity_gets_same_token():
    state = TokenState()
    scrub_text("供应商 某电子有限公司 批货延迟。", state)
    scrub_text("某电子有限公司 已回复。", state)
    # 同一名称只分配一个令牌
    tokens = [v for k, v in state.mapping.items() if "电子" in k]
    assert len(tokens) == 1


def test_token_table_markdown():
    state = TokenState()
    scrub_text("ZK-ECU-088 在高温失效，由供应商-A提供。", state)
    table = build_token_table(state)
    assert "| 原始内容 | 建议令牌 |" in table


def test_empty_text_returns_empty_entities():
    state = TokenState()
    result = scrub_text("", state)
    assert result.entities == []
    assert result.suggested == ""


def test_oem_level_b_default():
    state = TokenState()
    state.assign("某工程机械集团", "oem")
    mapping = state.mapping
    assert list(mapping.values())[0].startswith("OEM-B-")


def test_oem_level_a_when_configured():
    state = TokenState(oem_level="A")
    state.assign("某战略客户集团", "oem")
    assert list(state.mapping.values())[0].startswith("OEM-A-")
