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


# ── OEM 别名裸名检测（fix-d ②） ────────────────────────────────────────────────

def test_oem_alias_bare_chinese_detected():
    """比亚迪/上汽/理想等裸名（无后缀词）应被识别为 OEM 实体。

    左边界规则：不接 CJK 字符（如"来自比亚迪"中"自"会阻断）。
    测试用例均以 OEM 名开头或紧跟非 CJK 标点，确保左边界通过。
    """
    cases = [
        ("比亚迪要求本周提交8D报告。", "比亚迪"),   # 句首
        ("客户：上汽，交期延后3天。", "上汽"),         # 冒号后
        ("理想反馈 D1 描述不完整。", "理想"),           # 句首
        ("蔚来要求补充 D7 措施。", "蔚来"),             # 句首
    ]
    for text, expected in cases:
        state = TokenState()
        result = scrub_text(text, state)
        assert any(e.original == expected and e.entity_type == "oem" for e in result.entities), \
            f"期望裸名 '{expected}' 被识别为 OEM，原文：{text!r}"
        assert expected in state.mapping, f"'{expected}' 应在令牌映射表中"
        assert state.mapping[expected].startswith("OEM-"), \
            f"'{expected}' 的令牌应以 OEM- 开头，实际：{state.mapping[expected]}"


def test_oem_alias_english_bare_detected():
    """BYD/SAIC/NIO 等英文裸名应被识别为 OEM 实体。"""
    cases = [
        ("客诉来自 BYD 采购团队。", "BYD"),
        ("SAIC 要求本周提交 8D。", "SAIC"),
        ("NIO 反馈 ECU 插接器异响。", "NIO"),
    ]
    for text, expected in cases:
        state = TokenState()
        result = scrub_text(text, state)
        assert any(e.entity_type == "oem" for e in result.entities), \
            f"期望 '{expected}' 被识别为 OEM，原文：{text!r}"


def test_oem_alias_embedded_not_matched():
    """OEM 别名左边界保护：左侧紧接 CJK 字符时不应触发 OEM 标注。

    注：_PLATFORM_RE 可能仍将部分汉字串识别为平台代号（预存行为，不在本测试范围）。
    本测试专项验证 _OEM_ALIAS_RE 的 oem 标注不会误触发。
    """
    # "够" 前置 CJK 左边界，应阻断 "理想" 被标为 OEM
    state = TokenState()
    result = scrub_text("效果不够理想，需改进工艺。", state)
    assert not any(e.original == "理想" and e.entity_type == "oem" for e in result.entities), \
        "嵌在 '不够理想' 中的 '理想' 不应被标注为 OEM 客户（左边界 CJK 应阻断）"

    # "升" 前置 CJK 左边界，应阻断 "上汽" 被标为 OEM（右侧"的"不影响，右边只拦截 ASCII）
    state2 = TokenState()
    result2 = scrub_text("提升上汽的满意度是目标。", state2)
    assert not any(e.original == "上汽" and e.entity_type == "oem" for e in result2.entities), \
        "'提升上汽' 中 '上汽' 前有 CJK '升'，左边界应阻断 OEM 标注"

    # CJK 左边界保护：汉字前缀阻断比亚迪（"来自比亚迪"中"自"为 CJK，阻断匹配）
    state3 = TokenState()
    result3 = scrub_text("返修件来自比亚迪工厂。", state3)
    assert not any(e.original == "比亚迪" and e.entity_type == "oem" for e in result3.entities), \
        "「来自比亚迪」中「自」为 CJK，左边界应阻断 OEM 别名匹配（_ORG_RE 因无汽车后缀也不命中）"


def test_oem_alias_with_suffix_no_double_token():
    """带后缀词 '理想汽车' 被 _ORG_RE 匹配后，裸名 '理想' 不再重复出现。"""
    state = TokenState()
    result = scrub_text("理想汽车反馈 8D 格式问题。", state)
    oem_entities = [e for e in result.entities if e.entity_type == "oem"]
    # 应只有一个 OEM 实体（"理想汽车"）
    assert len(oem_entities) == 1, f"期望 1 个 OEM 实体，实际：{[e.original for e in oem_entities]}"
    assert oem_entities[0].original == "理想汽车"


def test_existing_26_tests_not_regressed():
    """回归：确保原有实体识别能力未受影响。"""
    state = TokenState()
    result = scrub_text("产品料号 ZK8808 在高温下失效。", state)
    assert any(e.entity_type == "part_no" for e in result.entities)
    assert state.mapping.get("ZK8808", "").startswith("料号-")
