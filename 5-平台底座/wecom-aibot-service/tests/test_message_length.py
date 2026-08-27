"""长度守卫与超限降级（队列 #416，`OP-0828-B`）。

本文件钉的是**判据本身**；「三条通道发同一份、失败必须是干净的」那几条钉在
`test_delivery_length_guard.py`。
"""
from __future__ import annotations

import pytest

from aibot_service.message_length import (
    CC_PREFIX,
    DEFAULT_MARKDOWN_MAX_BYTES,
    ENV_MARKDOWN_MAX_BYTES,
    OversizedMessageError,
    build_summary,
    extract_outline,
    markdown_max_bytes,
    measure,
    outbound_variants,
    plan_body,
)

_FILLER = "正文若干，这里刻意写长一点，好让整封信超过测试里设的上限。" * 8

LETTER = f"""\
# 采购部#9 · 三条口径请你回

祖怡，先说最要紧的一句。

## 一、判例表 A

{_FILLER}

## 二、责任人列请你改选

{_FILLER}

## 三、四件知会，不用回

{_FILLER}
"""


def test_measure_counts_utf8_bytes_not_characters():
    """按字节不按字符——中文一字 3 字节，两者差 3 倍，混了就等于没守卫。"""
    assert measure("中文") == 6
    assert len("中文") == 2


def test_default_threshold_is_the_measured_boundary_not_a_guess():
    """🔴 阈值 ＝ 20,480 B，**实测钉死的边界**，不是估值也不是凑的整数。

    2026-08-28 二分实测（靶子全是 ShaoPeiShen 本人）：**20,480 B 发得出、
    20,481 B 发不出**，服务端错误帧原文 `exceed max length 20480`。
    判定用 `<=`，与服务端「> 20480 即拒」对齐。

    ⚠️ 改这个数之前请重跑一次二分实测——**它现在是一个测量结果，不是一个
    可以按感觉调的旋钮**。
    """
    assert DEFAULT_MARKDOWN_MAX_BYTES == 20480
    # 两条历史样本仍必须落在正确的一侧（回归保护）：
    assert 13254 <= DEFAULT_MARKDOWN_MAX_BYTES, "质量部#8 那种信不该被降级"
    assert DEFAULT_MARKDOWN_MAX_BYTES < 24597, "采购部#19 那封必须被拦下"


def test_boundary_is_counted_in_bytes_not_characters():
    """按字节不按字符——由实测数据本身证死。

    20,481 B 那条只有 **6,851 个字符**：若限额是「20,480 个字符」，它离限还差
    三分之二、不可能被拒；它恰好在第 20,481 个**字节**上被拒。本用例把这个
    区分钉在判据上——`measure()` 一旦改成数字符，下面两条立刻翻。
    """
    at_limit = "啊" * (DEFAULT_MARKDOWN_MAX_BYTES // 3)      # 6,826 字符 / 20,478 B
    assert measure(at_limit) <= DEFAULT_MARKDOWN_MAX_BYTES
    assert len(at_limit) < DEFAULT_MARKDOWN_MAX_BYTES // 2   # 字符数远小于字节上限
    plan = plan_body(at_limit + "啊", cc_channels=[], attachment_names=["a.docx"])
    assert plan.degraded is True, "多出的那个汉字使字节数越界，必须降级"


def test_env_override_and_illegal_value_falls_back(monkeypatch):
    monkeypatch.setenv(ENV_MARKDOWN_MAX_BYTES, "2048")
    assert markdown_max_bytes() == 2048
    monkeypatch.setenv(ENV_MARKDOWN_MAX_BYTES, "不是数字")
    assert markdown_max_bytes() == DEFAULT_MARKDOWN_MAX_BYTES
    monkeypatch.setenv(ENV_MARKDOWN_MAX_BYTES, "-1")
    assert markdown_max_bytes() == DEFAULT_MARKDOWN_MAX_BYTES
    monkeypatch.delenv(ENV_MARKDOWN_MAX_BYTES)
    assert markdown_max_bytes() == DEFAULT_MARKDOWN_MAX_BYTES


def test_extract_outline_takes_h1_and_all_level_two_headings():
    h1, sections = extract_outline(LETTER)
    assert h1 == "采购部#9 · 三条口径请你回"
    assert sections == ["一、判例表 A", "二、责任人列请你改选", "三、四件知会，不用回"]


def test_extract_outline_ignores_headings_inside_code_fences():
    """围栏里的 `## xxx` 是正文内容，不是小节标题——漏判会把 opener 模板
    之类的代码块整段当成目录列出去。"""
    text = "# 标题\n\n```\n## 这不是小节\n```\n\n## 这才是小节\n"
    h1, sections = extract_outline(text)
    assert h1 == "标题"
    assert sections == ["这才是小节"]


def test_extract_outline_falls_back_to_level_three_then_first_line():
    _, sections = extract_outline("# T\n\n### 甲\n\n### 乙\n")
    assert sections == ["甲", "乙"]
    h1, sections = extract_outline("没有任何标题的一封短信。\n再一行。\n")
    assert h1 == "没有任何标题的一封短信。"
    assert sections == []


def test_within_limit_sends_原文_unchanged():
    plan = plan_body(LETTER, cc_channels=["抄送ShaoPeiShen"],
                     attachment_names=["letter.docx"], limit=100_000)
    assert plan.degraded is False
    assert plan.body == LETTER
    assert plan.body_bytes == measure(LETTER)


def test_over_limit_degrades_and_says_so_in_the_body():
    """降级正文**必须显式告知内容不全在此**——这一条比降级本身更要紧。"""
    plan = plan_body(LETTER, cc_channels=[], attachment_names=["letter.docx"],
                     limit=800)
    assert plan.degraded is True
    assert "只是提要，不是完整正文" in plan.body
    assert "以附件为准" in plan.body
    assert "letter.docx" in plan.body
    assert plan.original_bytes == measure(LETTER)
    assert plan.body_bytes < plan.original_bytes


def test_degraded_summary_lists_every_section_title():
    """全列出来、一条不漏——正文里没有任何机器可读标记能区分「要他办的」
    与「只是知会」，靠中文措辞挑就是 #308 那一族。"""
    plan = plan_body(LETTER, cc_channels=[], attachment_names=["letter.docx"],
                     limit=800)
    for title in ["一、判例表 A", "二、责任人列请你改选", "三、四件知会，不用回"]:
        assert title in plan.body
    assert plan.omitted_sections == 0


def test_guard_counts_the_cc_prefixed_string_not_the_original():
    """🔴 本文件最要紧的一条：一封正文**刚好在限内**、加 `【抄送】` 前缀后
    超限的信，必须照样降级。

    只按原文算 ⇒ 私信成功、抄送两条静默失败 ⇒ 外观是「发出去了」而群里
    什么都没有（同族＝#270 fail-closed 静默跳过）。**只验私信侧会漏掉的
    正是这一种。**
    """
    # 正文要够长，才使降级后的提要仍在限内（提要骨架约 490 B）。
    body = "# T\n\n" + "啊" * 400          # 6 + 1200 = 1206 B
    limit = measure(body)                   # 正文恰好等于上限

    # 不抄送 ⇒ 不该降级
    solo = plan_body(body, cc_channels=[], attachment_names=["a.docx"], limit=limit)
    assert solo.degraded is False

    # 一旦抄送，实际外发串是 `【抄送】`＋正文，比上限长 ⇒ 必须降级
    with_cc = plan_body(body, cc_channels=["群抄送"], attachment_names=["a.docx"],
                        limit=limit)
    assert with_cc.degraded is True
    assert all(v.size <= limit for v in with_cc.variants)


def test_outbound_variants_cover_every_channel_actually_used():
    variants = outbound_variants("正文", cc_channels=["抄送ShaoPeiShen", "群抄送"])
    assert [v.channel for v in variants] == ["私信", "抄送ShaoPeiShen", "群抄送"]
    assert variants[0].size == measure("正文")
    assert variants[1].size == measure(CC_PREFIX + "正文")
    assert variants[2].size == variants[1].size


def test_over_limit_without_attachment_refuses_instead_of_dropping_content():
    """🔴 降级的前提是「完整内容在附件里」。没有附件时降级＝静默丢内容，
    宁可干净失败。"""
    with pytest.raises(OversizedMessageError) as exc:
        plan_body(LETTER, cc_channels=[], attachment_names=[], limit=800)
    assert "无附件" in str(exc.value)


def test_summary_trims_sections_loudly_never_silently():
    """提要本身仍超限时逐条砍小节，并**明写砍了几条**——绝不静默截断。"""
    many = "# 标题\n\n" + "\n\n".join(f"## 第 {i} 节标题写得比较长一些" for i in range(40))
    plan = plan_body(many, cc_channels=[], attachment_names=["a.docx"], limit=600)
    assert plan.degraded is True
    assert plan.omitted_sections > 0
    assert f"另有 **{plan.omitted_sections}** 个小节未在此列出" in plan.body
    assert all(v.size <= 600 for v in plan.variants)


def test_even_skeleton_over_limit_raises_rather_than_truncating():
    with pytest.raises(OversizedMessageError) as exc:
        plan_body(LETTER, cc_channels=[], attachment_names=["a.docx"], limit=50)
    assert "仍超过单条消息上限" in str(exc.value)


def test_build_summary_without_sections_says_so():
    summary, omitted = build_summary(
        "没有小节的一封短信。", attachment_names=["a.docx"],
        original_bytes=999, limit=100,
    )
    assert omitted == 0
    assert "正文未分小节" in summary


def test_audit_fields_expose_the_numbers_for_later_review():
    plan = plan_body(LETTER, cc_channels=["群抄送"], attachment_names=["a.docx"],
                     limit=800)
    fields = plan.audit_fields()["length_guard"]
    assert fields["degraded"] is True
    assert fields["limit_bytes"] == 800
    assert fields["original_bytes"] == measure(LETTER)
    assert set(fields["channels"]) == {"私信", "群抄送"}
