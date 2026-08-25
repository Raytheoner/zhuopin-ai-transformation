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


class TestDispatchedVsNotYetSent:
    """`OP-0823-D`：「在途」一直混着两件事——已发出等回，与还没发出。"""

    @pytest.mark.parametrize("status", ["⏳ 待你审", "🆕 待发", "⏸ 暂缓"])
    def test_三种未发出态都不算已发出(self, status):
        assert fg.is_not_yet_sent(status)
        assert not fg.is_dispatched(status)

    @pytest.mark.parametrize("status", [
        "✅ 已推送 2026-08-18 07:23 UTC",
        "✅ 已发（Paul 手动 2026-07-06，陈忱次日回）",
        "📥 已回件并回灌（2026-08-21）",
        "❌ 已作废 · 9 月重写",
        f"{fg.REPLY_ARRIVED_STATUS} 2026-08-21T13:15:30Z",
    ])
    def test_其余一律算已发出(self, status):
        assert fg.is_dispatched(status)

    def test_没见过的写法算已发出而不是没发出(self):
        """两个方向的代价不对称：误判成「没发出」会让它在排序里被跳过，
        回件被配到更早的另一封信上，**错得悄无声息**。"""
        assert fg.is_dispatched("🤔 说不清")


class TestDepartmentNormalisation:
    @pytest.mark.parametrize("raw,expected", [
        ("采购部", "采购"), ("IT部", "IT"), ("IT", "IT"), ("财务部", "财务"),
        ("", ""), (None, ""),
    ])
    def test_剥掉尾字部(self, raw, expected):
        assert fg.normalize_department(raw) == expected

    @pytest.mark.parametrize("cell,expected", [
        ("采购部 · 姚祖怡", "采购"),
        ("采购部 · 姚祖怡（+团队）", "采购"),
        ("质量部 · 陈忱（可分担朱映桦）", "质量"),
        ("采购部 · 姚祖怡（转汤易水第④项）", "采购"),
        ("IT部 · 陈承（抄唐燕萍）", "IT"),
    ])
    def test_收信人列的四种真实括注形态都取得出部门(self, cell, expected):
        assert fg.recipient_department(cell) == expected

    def test_没有分隔符时取不出而不是瞎猜(self):
        assert fg.recipient_department("姚祖怡") is None


def _row(number, date, status, order, recipient="采购部 · 姚祖怡", target=None):
    return fg.LetterRow(number=number, date=date, recipient=recipient,
                        target_filename=target, status=status, order=order)


class TestLatestDispatched:
    def test_按日期取最新而不是按表内行序(self):
        """实测：`采购部#4`（07-21）在真身 README 里排在 `#17`（08-20）之后。"""
        rows = [
            _row("采购部#17", "2026-08-20", "✅ 已推送", 0),
            _row("采购部#4", "2026-07-21", "✅ 已推送", 1),
        ]
        assert fg.latest_dispatched_letter(rows, "采购部").number == "采购部#17"

    def test_同日多封按编号决胜(self):
        rows = [
            _row("采购部#15", "2026-08-18", "✅ 已推送", 0),
            _row("采购部#16", "2026-08-18", "✅ 已推送", 1),
        ]
        assert fg.latest_dispatched_letter(rows, "采购部").number == "采购部#16"

    def test_跳过尚未发出的信(self):
        rows = [
            _row("采购部#17", "2026-08-20", "✅ 已推送", 0),
            _row("采购部#18", "2026-08-22", "⏳ 待你审", 1),
        ]
        assert fg.latest_dispatched_letter(rows, "采购部").number == "采购部#17"

    def test_部门不匹配的行不参与(self):
        rows = [_row("财务部#1", "2026-08-20", "✅ 已推送", 0,
                     recipient="财务部 · 唐燕萍")]
        assert fg.latest_dispatched_letter(rows, "采购部") is None

    def test_部门取不到时返回None不瞎配(self):
        rows = [_row("采购部#17", "2026-08-20", "✅ 已推送", 0)]
        assert fg.latest_dispatched_letter(rows, None) is None


class TestPairReplyToLetter:
    真实入信 = (
        "采购部-YaoZuYi-回复-2026-08-21-采购部-姚祖怡-跟进-2026-08-20-"
        "SC2采购周报口径判例批改-0d6acc8a6238e6155c6e91f874246213.docx"
    )
    真实目标 = "采购部-姚祖怡-跟进-2026-08-20-SC2采购周报口径判例批改.md"
    文本反馈件 = "采购部-YaoZuYi-回复-2026-08-19-文本反馈-19662402efb7e15f1fe4993c9ea51772.md"

    def test_stem优先于最新一封(self):
        rows = [
            _row("采购部#17", "2026-08-20", "✅ 已推送", 0, target=self.真实目标),
            _row("采购部#18", "2026-08-22", "✅ 已推送", 1),
        ]
        out = fg.pair_reply_to_letter(
            archive_filename=self.真实入信, department="采购部", rows=rows)
        assert out.matched and out.channel == fg.PAIR_CHANNEL_STEM
        assert out.letter.number == "采购部#17"

    def test_纯文字回件走后备通道(self):
        rows = [
            _row("采购部#16", "2026-08-18", "✅ 已推送", 0),
            _row("采购部#17", "2026-08-20", "✅ 已推送", 1),
        ]
        out = fg.pair_reply_to_letter(
            archive_filename=self.文本反馈件, department="采购部", rows=rows)
        assert out.matched and out.channel == fg.PAIR_CHANNEL_LATEST
        assert out.letter.number == "采购部#17"

    def test_最新一封已闭环即未命中且属预期内常态(self):
        rows = [_row("采购部#17", "2026-08-20", "📥 已回件并回灌（2026-08-21）", 0)]
        out = fg.pair_reply_to_letter(
            archive_filename=self.文本反馈件, department="采购部", rows=rows)
        assert not out.matched, "带着 letter 不等于命中——这一格曾把补充说明当成真配对"
        assert out.channel == fg.PAIR_MISS_LATEST_CLOSED
        assert out.is_expected_quiet, "闭环后的补充说明是常态，不得升级为告警"
        assert out.letter.number == "采购部#17", "虽未命中，也要说得出是哪封已闭环"

    def test_一封已发出的信都没有则fail_loud(self):
        rows = [_row("采购部#18", "2026-08-22", "⏳ 待你审", 0)]
        out = fg.pair_reply_to_letter(
            archive_filename=self.文本反馈件, department="采购部", rows=rows)
        assert not out.matched and out.channel == fg.PAIR_MISS_NO_DISPATCHED
        assert not out.is_expected_quiet

    def test_部门取不到则不猜(self):
        rows = [_row("采购部#17", "2026-08-20", "✅ 已推送", 0)]
        out = fg.pair_reply_to_letter(
            archive_filename=self.文本反馈件, department=None, rows=rows)
        assert not out.matched and out.channel == fg.PAIR_MISS_NO_DEPARTMENT

    def test_历史未闭环堆积不阻塞配对(self):
        """🔴 反例锁死已被推翻的方案 B（唯一在途）：生产数据上四位收信人各有
        7／6／4／4 封已发出未闭环的历史信，按「恰好一封」实现会一次都不命中。"""
        rows = [_row(f"采购部#{n}", f"2026-07-{10 + n:02d}", "✅ 已推送", n)
                for n in range(1, 8)]
        rows.append(_row("采购部#17", "2026-08-20", "✅ 已推送", 99))
        out = fg.pair_reply_to_letter(
            archive_filename=self.文本反馈件, department="采购部", rows=rows)
        assert out.matched and out.letter.number == "采购部#17"


class TestUnclosedHealthCheck:
    def test_只报数且不含尚未发出的信(self):
        rows = [
            _row("采购部#1", "2026-07-11", "✅ 已推送", 0),
            _row("采购部#2", "2026-07-12", "✅ 已发", 1),
            _row("采购部#3", "2026-07-13", "📥 已回件并回灌", 2),
            _row("采购部#4", "2026-08-22", "⏳ 待你审", 3),
            _row("财务部#1", "2026-07-11", "✅ 已推送", 4, recipient="财务部 · 唐燕萍"),
        ]
        out = fg.unclosed_dispatched_by_department(rows)
        assert [r.number for r in out["采购"]] == ["采购部#1", "采购部#2"]
        assert [r.number for r in out["财务"]] == ["财务部#1"]


class TestReplyArrivedBacklink:
    归档件 = "财务部-tangyanping-回复-2026-08-10-文本反馈-7340bdb8.md"

    def test_第九态且溯源逐字对上才认(self):
        status = f"{fg.REPLY_ARRIVED_STATUS} 2026-08-10T02:00:00Z（入信归档 `{self.归档件}`）"
        assert fg.reply_arrived_cites(status, self.归档件)

    def test_溯源是另一份则不认(self):
        status = f"{fg.REPLY_ARRIVED_STATUS} 2026-08-10T02:00:00Z（入信归档 `别的.docx`）"
        assert not fg.reply_arrived_cites(status, self.归档件)

    def test_不是第九态就不认(self):
        assert not fg.reply_arrived_cites(f"✅ 已推送（{self.归档件}）", self.归档件)

    def test_桥二靠回指把纯文字回件纳入覆盖面(self):
        status = f"{fg.REPLY_ARRIVED_STATUS} 2026-08-10T02:00:00Z（入信归档 `{self.归档件}`）"
        out = fg.find_unsynced_letters(
            [fg.IntakeRecord("323", "q.md", self.归档件, True)],
            [fg.LetterRecord("财务部#11", None, status)],
        )
        assert len(out) == 1
        assert out[0].channel == fg.PAIR_CHANNEL_REPLY_ARRIVED


# ---------------------------------------------------------------------------
# 闭环形态标注（队列 #353；openspec `followup-closure-form-survives-backfill`）
# ---------------------------------------------------------------------------

# 逐字取自 README `质量部#7` 那一行「主要事项」列里起草人真写下的那句散文
# 所表达的判定——本包做的正是把它归一化到机器认得的形态上。
真实依据 = "正文三要素表明写「做什么＝不用做任何事」「什么时候交＝不用回」"
合法标注 = f"… → 闭环形态：`✅ 无需回复`（依据：{真实依据}）"


class TestParseClosureForm:
    def test_合法标注解析出取值与依据(self):
        parsed = fg.parse_closure_form(合法标注)
        assert parsed.is_annotated
        assert parsed.form.form == "✅ 无需回复"
        assert parsed.form.basis == 真实依据
        assert parsed.violation is None

    def test_取值越界则报出来且按无标注处理(self):
        parsed = fg.parse_closure_form("→ 闭环形态：`✅ 大概不用回`（依据：随便写的）")
        assert not parsed.is_annotated          # ← 闸仍锁，保守方向
        assert parsed.violation is not None
        assert "不在闭环四态枚举内" in parsed.violation

    def test_缺依据段则报出来且按无标注处理(self):
        parsed = fg.parse_closure_form("→ 闭环形态：`✅ 无需回复`")
        assert not parsed.is_annotated
        assert "依据" in parsed.violation

    def test_依据为空串同样报出来(self):
        parsed = fg.parse_closure_form("→ 闭环形态：`✅ 无需回复`（依据：　）")
        assert not parsed.is_annotated
        assert "为空" in parsed.violation

    def test_只有字样没有形态也报出来不静默(self):
        # 「有人在这一格里提了闭环形态，但没按格式写」——这是要被看见的形态，
        # 不是「什么都没发生」。
        parsed = fg.parse_closure_form("这封信的闭环形态另行判断")
        assert not parsed.is_annotated
        assert parsed.violation is not None

    def test_无标注既不报违规也不算标注(self):
        parsed = fg.parse_closure_form("**C01–C10 已落地** → 目标文件：`x.md`")
        assert not parsed.is_annotated
        assert parsed.violation is None

    @pytest.mark.parametrize("form", list(fg.CLOSED_STATUS_PREFIXES))
    def test_枚举四态全部认得而不是退化成布尔(self, form):
        # 🔴 实测语料里只有 `✅ 无需回复` 真被用过，枚举**刻意**仍写成四态：
        # 写成布尔就等于在消费者侧悄悄复制了第二份口径（design 决策点 4(a)）。
        parsed = fg.parse_closure_form(f"→ 闭环形态：`{form}`（依据：x）")
        assert parsed.form.form == form

    def test_粗体装饰不影响取值(self):
        # 同 `normalize_status` 那一族教训：真实 README 写法带 markdown 强调。
        parsed = fg.parse_closure_form("→ 闭环形态：`**✅ 无需回复**`（依据：x）")
        assert parsed.form.form == "✅ 无需回复"

    def test_同一个解析器也读得懂状态格里的快照(self):
        # 标注与快照共用同一套语法，故只有一份解析实现——两份迟早只认得一份。
        snapshot = (
            f"✅ 无需回复 2026-08-25 07:00 UTC{fg.PRESERVED_SEGMENT_SEPARATOR}"
            f"{fg.CLOSURE_FORM_SNAPSHOT_LABEL}：`✅ 无需回复`（依据：{真实依据}）"
        )
        parsed = fg.parse_closure_form(snapshot)
        assert parsed.form.form == "✅ 无需回复"
        assert parsed.form.basis == 真实依据


class TestClosureFormRegressionGuard:
    """🔴 兼容性护栏：**无标注的行行为与本变更前逐字相同**（spec 的 MUST）。

    54 行历史行里 53 行无标注，这条不是"尽量"。
    """

    @pytest.mark.parametrize("status", [
        "🆕 待发",
        "⏳ 待你审",
        "⏸ 暂缓",
        "✅ 已推送 2026-08-18 06:53 UTC",
        "📥 已回件并回灌（2026-08-21）",
        "📨 回件已到，待拆件 2026-08-21T13:13:24Z",
    ])
    def test_未标注状态的分类判定一个字都没变(self, status):
        assert fg.parse_closure_form(status).form is None
        assert fg.parse_closure_form(status).violation is None
        # 下面四条是本变更**没有**碰过的既有判据，此处只是把它们钉住。
        assert fg.classify_status(status) in ("closed", "reply_arrived", "in_flight", "unknown")
        assert fg.is_closed_status(status) == any(
            fg.normalize_status(status).startswith(p) for p in fg.CLOSED_STATUS_PREFIXES
        )
