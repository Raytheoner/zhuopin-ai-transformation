"""信 ↔ 点 的连接面 —— **只读**（tasks §2bis 的 2b.2／2b.3 共用这一份判据）。

## 为什么单独一个文件

回件侧（拆件 skill §三 4bis）与发送侧（`delivery.push_followup` 发出成功后）问的
是**同一个问题**：「`部门#N` 这封信投影了台账里哪几个点？」两侧若各写一份查法，
就又是「两份副本互相印证着一起错」（tasks 6.3 风险型指标那条，基线 6 次）。
⇒ 判据只此一份，两侧都 import 它。

## 判据

一个点被某封信投影 ⟺ **该点事件链里出现过同一个 `部门#N`**（`Point.letters`）。

🔴 **比对前两侧都归一化**，不做字面量比较：台账里的实际写法带过起草期括注
（真身实例：`"财务部#17（待你审，暂不占号）"`，`OP-0907-L` 2026-09-07 写入），
而回件侧拿到的是干净的 `财务部#17`。字面量比较会把这一对判成「不是同一封信」
—— 且判错之后的外观是「这封信不投影任何点」，与真的不投影**一模一样**，
不产生任何信号。归一化用 `followup_gate.parse_letter_number`（全项目唯一一份
「信编号长什么样」的实现），本文件不另写正则。

## 🔴 认不出 ≠ 没投影

`points_for_letter` 对**认不出的编号**抛错、不返回空元组。两者的业务含义完全
相反：

  · 空元组 ＝ 「这封信确实不投影任何点」⇒ 回件侧报固定一句、零回写（正常形态，
    `采购部#21` 即此形态）。
  · 认不出 ＝ 「传进来的东西根本不是信编号」⇒ 这是调用方的 bug。

若把认不出也返回空元组，一个传错参数的回件侧会**安静地报出「非台账投影」**，
而真正该回写的点一个都没动 —— 正是本包在治的那类「错误不产生信号」。
"""
from __future__ import annotations

from pathlib import Path

from zhuopin_platform.shared_tools.followup_gate import parse_letter_number

from .aggregate import Point, Snapshot, aggregate
from .errors import LedgerContractError
from .store import LedgerStore

#: 回件侧「本信不投影任何点」时报告里的固定一句（tasks 2b.2）。
#: 🔴 固定串放这里而不是写在 SKILL.md 里，是为了让 2b.4 的负样本断言有个**可比对的常量**
#: ——报告措辞若两处各写一份，改了一处不会有任何东西报错。
NON_PROJECTION_REPORT_LINE = "本信非台账投影，零回写"


def normalize_letter_ref(text: str) -> str | None:
    """把任意写法的信引用归一到 `部门#N`；认不出返回 ``None``。

    容忍括注与前后缀 —— 判据只认 `<部门>#<数字>` 这个片段本身（同
    `followup_gate.parse_letter_number`）::

        normalize_letter_ref("财务部#17（待你审，暂不占号）")  -> "财务部#17"
        normalize_letter_ref("财务部#17")                      -> "财务部#17"
        normalize_letter_ref("销售部（未发，不编号）")           -> None
    """
    if not isinstance(text, str):
        return None
    parsed = parse_letter_number(text)
    if parsed is None:
        return None
    dept, number = parsed
    return f"{dept}#{number}"


def require_letter_ref(text: str) -> str:
    """归一化，认不出即抛 —— 见模块文档《认不出 ≠ 没投影》。"""
    ref = normalize_letter_ref(text)
    if ref is None:
        raise LedgerContractError(
            f"{text!r} 不是一个信编号（形如 `财务部#17`）。"
            f"🔴 这与「这封信不投影任何点」是两件事：后者返回空、报固定一句，"
            f"前者是调用方传错了东西，必须报错——两者外观相同而含义相反。"
        )
    return ref


def points_for_letter(
    source: LedgerStore | Snapshot | Path | str, letter: str
) -> tuple[Point, ...]:
    """`letter` 这封信投影出去的全部点，按 `id` 排序（稳定输出，便于比对与报告）。

    :param source: `LedgerStore`／已聚合的 `Snapshot`／台账目录路径。
    :param letter: 信编号，任意写法（带括注亦可）；认不出即抛 `LedgerContractError`。
    :returns: 匹配到的点；**空元组 ＝ 这封信不投影任何点**（正常形态）。

    🔴 本函数**不写任何文件**：它走的是 `aggregate()`（D3 只读），没有落盘路径。
    """
    ref = require_letter_ref(letter)
    snapshot = source if isinstance(source, Snapshot) else aggregate(source)
    hits = [
        point
        for point in snapshot.points.values()
        if any(normalize_letter_ref(one) == ref for one in point.letters)
    ]
    return tuple(sorted(hits, key=lambda p: p.id))
