"""`zhuopin_platform.shared_tools.followup_gate` 单测（队列 #366 / S1-S4）。

用例里的状态串**全部取自真实 README 行**（2026-08-21 实测），不是构造的
理想形态——这一族判据历次翻车都翻在真实写法的装饰上（markdown 粗体、全角
空格分段、括注），构造出来的干净样本证明不了任何事。
"""
from __future__ import annotations

import pytest

from zhuopin_platform.shared_tools import followup_gate as fg


class TestClosedStatus:
    @pytest.mark.parametrize("status", [
        "📥 已回件并回灌（2026-08-21，Cowork 环境总线 OP-0821-B 转态）",
        "✅ **无需回复**（起草时即判定：正文三要素表明写「做什么＝不用做任何事」）",
        "📨 **已确认闭环 2026-08-10**（2026-08-18 按新增闭环三态回填）",
        "**❌ 已作废 · 9 月重写**（2026-08-04，队列 #137）",
    ])
    def test_四种闭环写法全部认得(self, status):
        assert fg.is_closed_status(status)
        assert fg.classify_status(status) == "closed"

    @pytest.mark.parametrize("status", [
        "✅ 已推送 2026-08-20 12:20 UTC　🔴 **回件已到、尚不能转闭环态**",
        "✅ 已发（Paul 手动 2026-07-06，陈忱次日回）",
        "⏳ 待你审",
        "🆕 待发",
        "⏸ 暂缓",
    ])
    def test_在途写法一律不放行(self, status):
        assert not fg.is_closed_status(status)
        assert fg.classify_status(status) == "in_flight"

    def test_没见过的写法归入unknown而不是静默当成在途或闭环(self):
        # 这一类必须能被调用方看见并报出来——静默归类正是 CLAUDE.md §5
        # 「工具静默回退」那一族教训。
        assert fg.classify_status("🤔 说不清") == "unknown"
        assert not fg.is_closed_status("🤔 说不清")

    def test_第九态与已确认闭环同以邮箱emoji开头但绝不能混(self):
        arrived = f"{fg.REPLY_ARRIVED_STATUS} 2026-08-21T13:13:24Z（企微机器人自动标记）"
        assert fg.is_reply_arrived_status(arrived)
        assert not fg.is_closed_status(arrived), "第九态仍属在途，闸必须仍锁"
        assert fg.classify_status(arrived) == "reply_arrived"
        assert fg.classify_status("📨 已确认闭环 2026-08-10") == "closed"


class TestNumberColumn:
    def test_括注不妨碍取号(self):
        # 反例单测⑴（派单件 §六.3）：编号列含「（待发，暂不占号）」时仍须
        # 正确取到该行的部门与序号。
        assert fg.parse_letter_number("IT部#7（待发，暂不占号）") == ("IT部", 7)
        assert fg.parse_letter_number("采购部#17") == ("采购部", 17)

    def test_完全没有编号的行取不到号但不抛(self):
        assert fg.parse_letter_number("销售部（未发，不编号）") is None
        assert fg.parse_letter_number("采购部（未发，不编号）") is None

    def test_编号自称未发而状态表明已发出即判矛盾(self):
        # 真实两处（2026-08-21 实测）：README 顶部「下一个可用号」段与下表
        # 编号列是同一事实的两份副本，已连续失真四次。
        assert fg.number_status_mismatch(
            "采购部（未发，不编号）", "✅ 已推送 2026-08-06 01:30 UTC")
        assert fg.number_status_mismatch(
            "IT部#7（待发，暂不占号）", "📥 已回件并回灌（2026-08-12 拆件巡逻）")

    def test_已作废的信本就可以不占号不算矛盾(self):
        assert not fg.number_status_mismatch(
            "销售部（未发，不编号）", "**❌ 已作废 · 9 月重写**（2026-08-04）")

    def test_未真正发出的草稿不算矛盾(self):
        assert not fg.number_status_mismatch("质量部#8（待发，暂不占号）", "⏳ 待你审")

    def test_编号列正常时永远不判矛盾(self):
        assert not fg.number_status_mismatch("采购部#17", "✅ 已推送 2026-08-20 12:20 UTC")


class TestReplyFilenameMatching:
    # 以下文件名均取自 `7-外部文档/` 真实归档件。
    采购_真实件 = (
        "采购部-YaoZuYi-回复-2026-08-21-采购部-姚祖怡-跟进-2026-08-20-"
        "SC2采购周报口径判例批改-0d6acc8a6238e6155c6e91f874246213.docx"
    )
    财务_带回复尾缀 = (
        "财务部-tangyanping-回复-2026-08-21-财务部-唐燕萍-跟进-2026-08-18-"
        "发票段已切换请复核与FI3前置启动-回复-dfbde6f51cbad3905d76f81246916781.docx"
    )
    文本反馈件 = "采购部-YaoZuYi-回复-2026-08-19-文本反馈-19662402efb7e15f1fe4993c9ea51772.md"

    def test_原样回传的docx逐字配上(self):
        assert fg.reply_matches_letter(
            self.采购_真实件,
            "采购部-姚祖怡-跟进-2026-08-20-SC2采购周报口径判例批改.md",
        )

    def test_专员附加的回复尾缀被确定性剥掉后仍要求逐字相等(self):
        assert fg.reply_matches_letter(
            self.财务_带回复尾缀,
            "财务部-唐燕萍-跟进-2026-08-18-发票段已切换请复核与FI3前置启动.md",
        )

    def test_纯文本反馈永远配不上任何信(self):
        # 这是**设计取舍**：一条文本回件无法确定地指向哪一封信，硬配会造出
        # 比漏配更难发现的错误。派单件 §二「匹配不上时不要猜」。
        assert fg.extract_reply_source_stem(self.文本反馈件) is None
        assert not fg.reply_matches_letter(self.文本反馈件, "采购部-姚祖怡-跟进-2026-08-20-x.md")

    def test_不做包含匹配也不做最相似匹配(self):
        # 只回答「是」或「不知道」，永远不回答「大概是」。
        assert not fg.reply_matches_letter(
            self.采购_真实件, "采购部-姚祖怡-跟进-2026-08-20-SC2采购周报口径.md"
        )

    def test_不符合归档命名形态的文件名返回None而不是硬拆(self):
        assert fg.extract_reply_source_stem("随手放进来的一个文件.docx") is None


class TestFindUnsyncedLetters:
    def _intake(self, row_id, filename, dismantled):
        return fg.IntakeRecord(row_id, "q.md", filename, dismantled)

    真实入信 = (
        "财务部-tangyanping-回复-2026-08-06-财务部-唐燕萍-跟进-2026-08-05-"
        "FI2面板6项显示问题已修复请复核-回复-b01f0dd5ed0005b5ac01d9ccd9eb3006.docx"
    )
    真实目标 = "财务部-唐燕萍-跟进-2026-08-05-FI2面板6项显示问题已修复请复核.md"

    def test_已拆件而README未闭环即报(self):
        out = fg.find_unsynced_letters(
            [self._intake("291", self.真实入信, True)],
            [fg.LetterRecord("财务部#11", self.真实目标, "✅ 已推送 2026-08-06 01:30 UTC")],
        )
        assert len(out) == 1
        assert "财务部#11" in out[0].describe()
        assert "§一 #291" in out[0].describe()

    def test_未拆件的入信行不报(self):
        # 桥二治的是「拆完了忘转态」，不是「还没拆」——后者是桥一的活。
        assert fg.find_unsynced_letters(
            [self._intake("291", self.真实入信, False)],
            [fg.LetterRecord("财务部#11", self.真实目标, "✅ 已推送")],
        ) == []

    def test_README已闭环即不报(self):
        assert fg.find_unsynced_letters(
            [self._intake("291", self.真实入信, True)],
            [fg.LetterRecord("财务部#11", self.真实目标, "📥 已回件并回灌（2026-08-07）")],
        ) == []

    def test_第九态不算闭环仍会被拦(self):
        out = fg.find_unsynced_letters(
            [self._intake("291", self.真实入信, True)],
            [fg.LetterRecord("财务部#11", self.真实目标,
                             f"{fg.REPLY_ARRIVED_STATUS} 2026-08-06T01:30:00Z")],
        )
        assert len(out) == 1, "第九态是「回件到了」不是「回灌完了」，拆件后仍须转闭环"

    def test_没有目标文件标注的历史行不参与配对(self):
        # 已知边界，必须随文案说出去：零违规 ≠ 全同步。
        assert fg.find_unsynced_letters(
            [self._intake("291", self.真实入信, True)],
            [fg.LetterRecord("财务部#3", None, "✅ 已推送 2026-07-13")],
        ) == []
