"""`followup_gate` §八 闭环形态标注判据单测（变更包
`followup-closure-form-survives-backfill`，tasks 2.3／5.2／5.3 判据侧）。

四类（合法／越界／缺依据／无标注）＋ 快照读回 ＋ 决策点 5(c) 必配缓解
（「标注 ≠ 快照 ⇒ 报『以快照为准』」）。护栏②的反例（越界 ⇒ 仍写
`✅ 已推送`、闸仍锁）在这里只证到「按无标注处理」；回填落字那一半在
`wecom-aibot-service/tests/test_closure_form_backfill.py`。
"""
from __future__ import annotations

import pytest

from zhuopin_platform.shared_tools import followup_gate as fg

合法标注 = "主题一句 → 闭环形态：`✅ 无需回复`（依据：三要素明写不用回）"


class TestParseClosureForm:
    def test_合法标注被识别(self):
        form = fg.parse_closure_form(合法标注)
        assert form is not None and form.is_valid
        assert form.value == "✅ 无需回复"
        assert form.basis == "三要素明写不用回"
        assert form.problem is None

    def test_无标注返回None_与今天逐字同行为(self):
        assert fg.parse_closure_form("普通主题 → 目标文件：`x.md`") is None
        assert fg.parse_closure_form("") is None

    def test_越界取值报出来且按无标注处理(self):
        """护栏②／决策点 4(a)：不在闭环四态枚举内 ⇒ fail-loud，`value=None`。"""
        form = fg.parse_closure_form("主题 → 闭环形态：`✅ 大概不用回`（依据：随便）")
        assert form is not None
        assert not form.is_valid
        assert form.value is None
        assert "不在闭环四态枚举内" in form.problem
        assert "闸仍锁" in form.problem

    def test_缺依据同样报出来(self):
        form = fg.parse_closure_form("主题 → 闭环形态：`✅ 无需回复`")
        assert form is not None and not form.is_valid
        assert form.value is None
        assert "缺依据" in form.problem

    def test_依据括号为空也算缺依据(self):
        form = fg.parse_closure_form("主题 → 闭环形态：`✅ 无需回复`（依据：）")
        assert form is not None and not form.is_valid

    @pytest.mark.parametrize("value", fg.CLOSED_STATUS_PREFIXES)
    def test_四态枚举逐一合法_不退化为布尔(self, value):
        form = fg.parse_closure_form(f"主题 → 闭环形态：`{value}`（依据：x）")
        assert form is not None and form.is_valid and form.value == value

    def test_取值比对是整串相等_不是前缀(self):
        """`✅ 无需回复了` 不是枚举值——机器要读的位置不做模糊识别。"""
        form = fg.parse_closure_form("主题 → 闭环形态：`✅ 无需回复了`（依据：x）")
        assert form is not None and not form.is_valid

    def test_取值容忍markdown粗体装饰(self):
        form = fg.parse_closure_form("主题 → 闭环形态：`✅ **无需回复**`（依据：x）")
        assert form is not None and form.is_valid and form.value == "✅ 无需回复"

    def test_历史散文形态同样命中(self):
        """`质量部#7` 行日志里的原句形态（引导词后带散文再接反引号）——
        与 `#241` 的 `目标文件` 正则同一条兼容策略。"""
        prose = "🔑 **闭环形态＝起草时即判定为 `✅ 无需回复`**（依据：正文三要素表明写不用回）"
        form = fg.parse_closure_form(prose)
        assert form is not None and form.is_valid and form.value == "✅ 无需回复"


class TestSnapshot:
    def test_快照段能拼能读回(self):
        form = fg.parse_closure_form(合法标注)
        seg = fg.build_closure_snapshot_segment(form)
        assert seg.startswith(fg.CLOSURE_SNAPSHOT_LABEL)
        status = f"✅ 无需回复 2026-09-12 08:00 UTC{fg.STATUS_SEGMENT_SEPARATOR}{seg}{fg.STATUS_SEGMENT_SEPARATOR}✅ 已推送 2026-09-12 08:00 UTC"
        assert fg.extract_closure_snapshot(status) == "✅ 无需回复"

    def test_违规标注不得快照(self):
        form = fg.parse_closure_form("主题 → 闭环形态：`✅ 大概不用回`（依据：x）")
        with pytest.raises(ValueError):
            fg.build_closure_snapshot_segment(form)

    def test_无快照段返回None(self):
        assert fg.extract_closure_snapshot("✅ 已推送 2026-09-12 08:00 UTC") is None
        # 状态格里只是**提到**闭环形态四个字（`质量部#7` 旧格的散文）不算快照
        assert fg.extract_closure_snapshot(
            "✅ 无需回复（起草时即判定……）｜ 闭环形态判定会被覆盖") is None

    def test_快照穿越第九态仍可读(self):
        """tasks 4.4：桥一把整个原状态原样接在后面，快照一路活到第九态。"""
        form = fg.parse_closure_form(合法标注)
        seg = fg.build_closure_snapshot_segment(form)
        backfilled = f"✅ 已推送 T{fg.STATUS_SEGMENT_SEPARATOR}{seg}"
        ninth = f"{fg.REPLY_ARRIVED_STATUS} 2026-09-12T08:00:00Z（…）　━━━　原状态 ━━━　{backfilled}"
        assert fg.is_reply_arrived_status(ninth)
        assert fg.extract_closure_snapshot(ninth) == "✅ 无需回复"


class TestMismatchWarning:
    """决策点 5(c) 必配缓解：三种不一致形态都要出声、都声明「以快照为准」。"""

    快照态 = ("✅ 无需回复 T　━━━　闭环形态（发出时快照） ━━━　✅ 无需回复（依据：三要素明写不用回）"
             "　━━━　✅ 已推送 T")

    def test_一致时不报(self):
        assert fg.closure_form_mismatch_warning(合法标注, self.快照态) is None

    def test_两侧皆无不报(self):
        assert fg.closure_form_mismatch_warning("主题", "✅ 已推送 T") is None

    def test_标注在发出后被改成别的取值_报以快照为准(self):
        topic = "主题 → 闭环形态：`❌ 已作废`（依据：改口）"
        msg = fg.closure_form_mismatch_warning(topic, self.快照态)
        assert msg is not None and "以快照为准" in msg
        assert "❌ 已作废" in msg and "✅ 无需回复" in msg

    def test_标注被删而快照仍在_报以快照为准(self):
        msg = fg.closure_form_mismatch_warning("主题（标注被删了）", self.快照态)
        assert msg is not None and "以快照为准" in msg

    def test_发出后才补写标注_无快照_报事后追认对闸零效果(self):
        """tasks 5.3 前半：发出后补写 ⇒ 闸零效果，且必须被点破。"""
        msg = fg.closure_form_mismatch_warning(合法标注, "✅ 已推送 2026-08-18 06:53 UTC")
        assert msg is not None
        assert "事后追认" in msg and "以快照为准" in msg and "零效果" in msg

    def test_未发出的行有标注无快照_不报(self):
        """草稿／待发／暂缓阶段标注还没到快照那一步，报它只会制造噪音。"""
        for status in ("⏳ 待你审", "🆕 待发", "⏸ 暂缓（依据：等一下）"):
            assert fg.closure_form_mismatch_warning(合法标注, status) is None

    def test_越界标注无快照且已发出_也出声(self):
        topic = "主题 → 闭环形态：`✅ 大概不用回`（依据：x）"
        msg = fg.closure_form_mismatch_warning(topic, "✅ 已推送 T")
        assert msg is not None and "以快照为准" in msg
