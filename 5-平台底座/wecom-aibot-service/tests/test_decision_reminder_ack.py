"""决策提醒的指纹确认（`OP-0828-B`，判据关不掉的修法）。

🔴 **本文件的验收判据是不对称的**：
- 「关得掉」只要一条用例；
- 「**真没闭环的仍必须命中**」要好几条 —— **只验前者会造出一个「什么都不报」
  的假绿，比现在更糟**。
"""
from __future__ import annotations

from datetime import date

import pytest

from aibot_service.decision_reminder import (
    ACK_COMMAND_HINT,
    ackable_state,
    default_state,
    evaluate,
    format_digest_message,
    item_fingerprint,
    record_ack,
)

TODAY = date(2026, 8, 28)

# 三行照真实队列的形状造：
# #47  —— 已收口，只是截止列没写 ✅（真实误报形态一）
# #124 —— 截止列里那个日期是「登记日期」、本行明写「不卡时间」（真实误报形态二）
# #103 —— 开头就是 ✅、写着「本项到此闭环」，但同一格里还挂着一个三选一
#          （真实的 TRUE positive，🔴 长得最像误报的那一条）
QUEUE = """\
## 四、需 Shao Peishen 的动作（例外与拍板）

| # | 事项 | 等谁 | 截止 |
|---|------|------|------|
| 47 | IT部#6 抄送处理方式……**✅ 已拍板并执行**……本行处置完毕 | Shao Peishen | **已收口 2026-08-03** |
| 103 | ✅ **已拍板并执行：续用、回退闸已摘**……**本项到此闭环**……🔴 **未闭合：转态动作本身尚未执行**……须 Shao Peishen 定转态形态（三选一） | Shao Peishen | 2026-08-24 |
| 124 | 同一条串行原则的两个实现口径不一致 | Shao Peishen | 🔴 **不设默认生效**（判据类）。**不卡时间** ━━━ 登记：2026-08-26 |

## 五、别的
"""


def _eval(queue=QUEUE, acks=None, state=None):
    return evaluate(queue, TODAY, state if state is not None else default_state(), acks=acks)


def test_baseline_all_three_rows_fire_before_any_ack():
    """基线：改动前后判定形态不变——无确认文件时，三条照旧全部命中。"""
    result = _eval()
    assert {i.key for i in result.items} == {"§四#47", "§四#103", "§四#124"}
    assert result.suppressed == []


def test_ack_silences_the_two_real_false_positives():
    """⑴ 关得掉 —— `#47`（已收口、只差个 ✅）与 `#124`（那个日期是登记日期）。"""
    acks = {}
    first = _eval()
    for key in ("§四#47", "§四#124"):
        hit = next(i for i in first.items if i.key == key)
        acks = record_ack(acks, key, fingerprint=hit.fingerprint, note="逐字读过原文，确已闭环")

    result = _eval(acks=acks)
    assert {i.key for i in result.items} == {"§四#103"}
    assert {s.key for s in result.suppressed} == {"§四#47", "§四#124"}


def test_the_row_that_looks_most_like_a_false_positive_still_fires():
    """⑵ 🔴 真没闭环的仍命中 —— `#103`。

    它开头就是 `✅`、还写着「本项到此闭环」，**任何靠读事项列中文措辞去
    自动关闭的修法，第一个误杀的就是它**；而它挂着一个没人答的三选一。
    这条用例是这套修法「没有走上那条路」的证明。
    """
    acks = {}
    first = _eval()
    for key in ("§四#47", "§四#124"):
        hit = next(i for i in first.items if i.key == key)
        acks = record_ack(acks, key, fingerprint=hit.fingerprint, note="核过")
    result = _eval(acks=acks)
    assert "§四#103" in {i.key for i in result.items}


def test_ack_is_not_a_permanent_whitelist_fingerprint_change_reopens_it():
    """⑶ 判据格一被改写，确认自动失效 —— 它不是白名单。"""
    hit = next(i for i in _eval().items if i.key == "§四#47")
    acks = record_ack({}, "§四#47", fingerprint=hit.fingerprint, note="核过")
    assert "§四#47" not in {i.key for i in _eval(acks=acks).items}

    # 有人给这一行补了一个新的截止日期 ⇒ 指纹变 ⇒ 必须重新报出来
    changed = QUEUE.replace("**已收口 2026-08-03**", "2026-08-05 前再答一次")
    assert "§四#47" in {i.key for i in _eval(queue=changed, acks=acks).items}


def test_stale_ack_is_reported_not_silently_kept():
    """确认对不上任何现存行时要出声——它核的是一个已经不存在的东西。"""
    acks = record_ack({}, "§四#999", fingerprint="deadbeefdeadbeef", note="核过一个不存在的行")
    result = _eval(acks=acks)
    assert result.stale_acks == ["§四#999"]


def test_unrelated_appends_to_the_narrative_cell_do_not_reopen_an_ack():
    """指纹只盖判据格：事项列被追加一段无关的话，不该把已核实的重新捅红。

    🔴 队列行一天被追加三五段是常态；盖整行等于把本次要治的病换个方向再犯
    一遍。
    """
    hit = next(i for i in _eval().items if i.key == "§四#47")
    acks = record_ack({}, "§四#47", fingerprint=hit.fingerprint, note="核过")
    appended = QUEUE.replace("本行处置完毕", "本行处置完毕 ━━━ 📎 又追记了一段跟处置无关的话")
    assert "§四#47" not in {i.key for i in _eval(queue=appended, acks=acks).items}


def test_ack_expiry_alerts_immediately_not_on_the_1_3_7_cadence():
    """指纹失效后立即报一次，不接着上一轮的升级节奏慢慢来（fail-loud 方向）。"""
    first = _eval()
    hit = next(i for i in first.items if i.key == "§四#47")
    acks = record_ack({}, "§四#47", fingerprint=hit.fingerprint, note="核过")
    # 被 ack 的项不进 escalation，计数就此清零
    result = _eval(acks=acks, state=first.state)
    assert "§四#47" not in result.state["escalation"]
    # 指纹失效当轮即命中
    changed = QUEUE.replace("**已收口 2026-08-03**", "2026-08-05 前再答一次")
    again = evaluate(changed, TODAY, result.state, acks=acks)
    assert "§四#47" in {i.key for i in again.items}


def test_ackable_state_excludes_rows_that_are_not_yet_nagging():
    """🔴 只有「此刻真的在烦人的」才允许被 ack —— 否则就造出了永久白名单。

    一个截止日还在**未来**的行若能被 ack，等它到期时截止列一个字没改 ⇒ 指纹
    不变 ⇒ **它永远不会响**。`--ack-item` 因此用 `ackable_state()` 评估，而不是
    空状态。
    """
    queue = QUEUE.replace("| Shao Peishen | 2026-08-24 |", "| Shao Peishen | 2026-12-31 |")
    ackable = evaluate(queue, TODAY, ackable_state(queue, TODAY))
    keys = {i.key for i in ackable.items}
    assert "§四#103" not in keys, "截止日还在未来的行不得进入可 ack 清单"
    assert {"§四#47", "§四#124"} <= keys, "已过截止的行必须仍可被 ack"

    # 对照：空状态下它会因为「新增」混进来 —— 那正是不能用空状态的原因
    assert "§四#103" in {i.key for i in evaluate(queue, TODAY, default_state()).items}


def test_empty_note_is_rejected():
    """空确认等于没确认，还会伪装成已核。"""
    with pytest.raises(ValueError):
        record_ack({}, "§四#47", fingerprint="abc", note="   ")


def test_fingerprint_is_stable_and_content_addressed():
    assert item_fingerprint("同样的一格") == item_fingerprint("同样的一格")
    assert item_fingerprint("A") != item_fingerprint("B")


def test_digest_echoes_suppressed_count_and_the_command_to_close_one():
    """🔴 抑制清单必须回显，且关掉它的命令每轮原样打出来。

    一个只会变长、从不回显的抑制清单，正是这套告警最该防的「看起来干净」。
    """
    first = _eval()
    hit = next(i for i in first.items if i.key == "§四#47")
    acks = record_ack({}, "§四#47", fingerprint=hit.fingerprint, note="核过")
    result = _eval(acks=acks)
    message = format_digest_message(result.items, result.suppressed, result.stale_acks)
    assert "另有 1 项已确认闭环、本轮静默" in message
    assert ACK_COMMAND_HINT in message


def test_digest_without_suppression_is_unchanged_in_shape():
    """无抑制时不多一句废话——回显只在有东西可回显时出现。"""
    message = format_digest_message(_eval().items)
    assert "已确认闭环" not in message
    assert ACK_COMMAND_HINT in message  # 操作说明仍在，那是常设的
