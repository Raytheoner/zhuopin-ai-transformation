"""超期扫描 —— **只生成催办草稿，绝不改状态**（D5，断言测试 ＝ tasks §1.5）。

## 一句话语义

超期的唯一后果是**多出一份催办草稿**；点的状态**保持 `在途`**，
`已签认` 只能由**真实回件**驱动（IATF 显式签认红线：判据／口径／阈值类永不默认生效）。

## 本文件的存在本身就是断言的一部分

D5 说的是「**不存在**任何超期自动签认路径」。一条「不存在」很难直接证明 ——
所以本包把「超期之后会发生什么」收敛到这一个文件里：

  · 它 `import` 了 `Status`，但**从不构造** `Status.SIGNED` 的事件；
  · 它**不 import `LedgerStore`**，因而在语法层面就够不着写入口；
  · 它返回的 `OverdueDraft` 是一份**草稿**，`status` 字段恒为超期时的原状态。

tasks §1.5 的三条断言分别打这三面：行为面（扫完状态不变、台账不长行）、
入口面（全包只有 `LedgerStore._append_line` 一处写内容）、构造面
（`已签认` 缺 `evidence` 连对象都造不出来）。

## `default_after_h` 为什么在这里不生效

`试用反馈`／`材料索取` 可标 `default_after_h`（P4），但**「默认生效」发生在业务侧
（如：没人反对就按拟改判定执行），不等于台账可以自己写一行 `已签认`**。
本模块只把「已过默认时限」标在草稿上供调用方判断，`推进状态的动作永远由人或回件触发`。
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from .aggregate import Point, Snapshot
from .models import PointType, Status

# 会进超期扫描的状态：只有还在等回件的点才谈得上超期。
# 🔴 `已签认` 及其后的状态**不在**这里 —— 它们已经有回件了，不需要催，
# 更不能被这个函数碰。
SCANNABLE_STATUSES = frozenset({Status.ASKING, Status.IN_FLIGHT})


@dataclass(frozen=True)
class OverdueDraft:
    """一份催办草稿 —— **草稿，不是动作**。

    🔴 `status` 字段记的是扫描时该点的**原状态**，本类没有、也不会有
    「把它改成 `已签认`」的方法。要推进状态，只能有人拿着真实回件去 `LedgerStore.append`。
    """

    point_id: str
    scene: str | None
    proposer: str | None
    status: Status
    type: PointType | None
    due: str
    days_overdue: int
    letters: tuple[str, ...]
    #: `判据类` 恒为 ``False``（永不默认生效）；其余类型在过了 `default_after_h`
    #: 后为 ``True``，含义仅是「业务侧可以按默认走了」，**不代表台账已签认**。
    default_window_elapsed: bool = False

    @property
    def hint(self) -> str:
        """给催办信起草用的一句话（不含任何状态推进的暗示）。"""
        who = self.proposer or "提出人未记"
        return (
            f"口径点 {self.point_id}（{self.scene or '场景未记'}／{who}）"
            f"到期日 {self.due} 已超 {self.days_overdue} 天，仍为 `{self.status.value}`。"
            f"请催办回件；🔴 无回件不得推进状态。"
        )


def _parse_date(text: str) -> date | None:
    try:
        return date.fromisoformat(text)
    except (ValueError, TypeError):
        return None


def scan_overdue(snapshot: Snapshot, *, today: date) -> tuple[OverdueDraft, ...]:
    """扫出所有已过 `due` 且仍在等回件的点，返回催办草稿。

    🔴 **本函数不接收 `LedgerStore`、不写台账、不返回任何可用于写入的事件对象。**
    它的返回值全部是 `OverdueDraft`，而 `LedgerStore.append` 只接受 `LedgerEvent`
    —— 两个类型之间**没有转换函数**，这条「超期 → 签认」的路在类型层面就不通。

    :param snapshot: `aggregate()` 的结果（内存对象）。
    :param today: 判超期用的今天。🔴 **必须显式传**，不默认 `date.today()`
        —— 一个读隐式当前时间的函数，测试里永远只能测到「今天」这一种情况。
    """
    drafts: list[OverdueDraft] = []
    for point in snapshot.points.values():
        draft = _draft_for(point, today=today)
        if draft is not None:
            drafts.append(draft)
    return tuple(sorted(drafts, key=lambda d: (-d.days_overdue, d.point_id)))


def _draft_for(point: Point, *, today: date) -> OverdueDraft | None:
    if point.status not in SCANNABLE_STATUSES:
        return None
    if point.due is None:
        return None
    due = _parse_date(point.due)
    if due is None or due >= today:
        return None

    point_type = point.created.type
    default_after_h = point.created.default_after_h
    elapsed = False
    if point_type is not None and point_type.may_default and default_after_h is not None:
        # `判据类` 走不到这里（`may_default` 为 False）——那是 IATF 红线，
        # 不是一个可以配出来的开关。
        elapsed = (today - due).days * 24 >= default_after_h

    return OverdueDraft(
        point_id=point.id,
        scene=point.scene,
        proposer=point.proposer,
        status=point.status,
        type=point_type,
        due=point.due,
        days_overdue=(today - due).days,
        letters=point.letters,
        default_window_elapsed=elapsed,
    )
