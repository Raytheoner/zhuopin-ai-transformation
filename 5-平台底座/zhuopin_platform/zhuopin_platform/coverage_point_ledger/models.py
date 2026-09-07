"""口径点台账的数据结构 —— 一行 JSONL ＝ 一个 `LedgerEvent`。

正本 ＝ `6-人才与组织/部门AI专员跟进/口径点台账/SCHEMA.md`（§一 文件表、§二 字段表、§三 六条约束）。
本文件是那份 schema 的可执行形态；**两处冲突以 SCHEMA.md 为准并当场改齐本文件**。

四个枚举 ＋ 一个冻结 dataclass：

  · `Domain`      —— 五个域，各自的文件名与 `id` 前缀（D2：**前缀隐含域，不设 `域` 字段**）。
  · `Event`       —— `建点`／`转态`／`补记`／`作废`。
  · `Status`      —— `待问`→`在途`→`已签认`→`已回灌`→`已落码` 单向；`已作废` 另计。
  · `PointType`   —— `判据类`／`试用反馈`／`材料索取`（P4）。
  · `LedgerEvent` —— 一行事件；**冻结**，构造期校验字段契约，之后不可改。

🔴 **为什么 `LedgerEvent` 必须 frozen**：本台账要防的那件事（2026-08-23 的 12 封信被批量
「补转态」，真实回件日在补记那一刻被**覆盖式销毁、不可复原**）在代码里的形态就是
「某处拿到一个已有事件对象，改掉它的 `fact_date` 再写回去」。frozen 让这个动作在
**赋值那一行**就抛 `FrozenInstanceError`，而不是等到度量中位数从 2 天变成 7 天才被发现。

---

## ✅ `carrier` 口径已定死（Shao Peishen 2026-09-06 经 `OP-0906-X` 拍板 (a)）

**结论：`carrier` ≥1 仅对 `建点` 行生效；`转态` 行可空，两类行都不在写入期强制。**
SCHEMA §二 字段表已同步改齐（`≥1（**仅建点行**）`），本模块实现无需改动。

原不一致（`OP-0906-Z` 登记）：字段表原写「≥1（建点**或转态**行）」，而同节最小示例的
第 2、3 行（两条 `转态`）都没有 `carrier`，两者不可能同时成立。按下述两条理由裁向「不强制」：

  ⑴ **强制会消灭它自己要保护的指标** —— tasks 6.3 的质量型价值指标就是
     「承接载体缺失」数量（首次全量扫描定基线、目标归零）。写入期强制 ≥1 之后，
     这个数**结构性恒为 0**，基线与「归零」都失去意义。
  ⑵ **强制会逼出假数据** —— tasks §2 回溯拆点要如实录入历史点，其中相当一部分
     本来就没有承接载体（这正是立项要解决的问题）。若不填就写不进去，
     现场唯一的出路是**编一个载体**，而编出来的载体不产生任何信号。

⇒ 载体缺失走**度量**（`Snapshot.missing_carrier`），不走写入拒绝。
🔑 本条已闭合，**不再进两包合审**；合审剩余项只有 SCHEMA §四「`id` 与 `criteria_signoff` 同名」那条。
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import date
from enum import Enum
from typing import Any

from .errors import LedgerContractError

# `fact_date` 不可考时的唯一合法字面量（SCHEMA §二）。
# 🔴 它**不是**「没填」的同义词：度量脚本要把这一类单列、不混入中位数，
# 故必须显式写出来，不得用空串、`null` 或补记日顶替。
FACT_DATE_UNKNOWN = "事实日未知"

_ISO_DATE_RE = re.compile(r"\d{4}-\d{2}-\d{2}")
# `recorded_on` ＝ 本机 `Get-Date` 带 `+08:00`（SCHEMA §二）。秒可省、偏移不可省
# ——没有偏移的时间戳在「UTC 还是本地」上永远说不清，而它正是用来算补记滞后的那一半。
_RECORDED_ON_RE = re.compile(
    r"\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}(:\d{2}(\.\d+)?)?([+-]\d{2}:\d{2}|Z)"
)


class Domain(Enum):
    """五个域 —— 平铺于 `6-人才与组织/部门AI专员跟进/口径点台账/`（D2 ＋ D8）。

    🔑 **`id_prefixes` 按最长前缀匹配，不按声明顺序**：`SC8-…` 同时命中 `SC`（采购）
    与 `S`（销售），`QD-B-…` 同时命中 `QD-`（质量）与 `Q`（质量）。若按顺序匹配，
    「哪个域先声明」就会变成一条**看不见的判据**，且改动声明顺序不报错。
    """

    PROCUREMENT = ("采购", "采购域.jsonl", ("SC",))
    FINANCE = ("财务", "财务域.jsonl", ("FI",))
    QUALITY = ("质量", "质量域.jsonl", ("QD-", "Q"))
    SALES = ("销售", "销售域.jsonl", ("S",))
    IT = ("IT", "IT域.jsonl", ("D-IT", "IT"))

    def __init__(self, label: str, filename: str, id_prefixes: tuple[str, ...]) -> None:
        self.label = label
        self.filename = filename
        self.id_prefixes = id_prefixes

    @classmethod
    def for_id(cls, point_id: str) -> "Domain":
        """由 `id` 前缀定域；命中多个时**最长者胜**，一个都不命中即抛。"""
        best: tuple[int, "Domain"] | None = None
        for domain in cls:
            for prefix in domain.id_prefixes:
                if point_id.startswith(prefix) and (best is None or len(prefix) > best[0]):
                    best = (len(prefix), domain)
        if best is None:
            raise LedgerContractError(
                f"id={point_id!r} 的前缀不属于任何域。"
                f"合法前缀：{sorted(p for d in cls for p in d.id_prefixes)}。"
                f"🔴 前缀隐含域（D2），改前缀就是改域——不要为了让它通过而新造前缀，"
                f"先回 SCHEMA.md §一 确认这个点该进哪本账。"
            )
        return best[1]

    @classmethod
    def for_filename(cls, filename: str) -> "Domain":
        for domain in cls:
            if domain.filename == filename:
                return domain
        raise LedgerContractError(
            f"{filename!r} 不是台账域文件。合法文件：{[d.filename for d in cls]}"
        )


class Event(Enum):
    """事件类型（SCHEMA §二 `event`）。

    🔴 `补记` ＝ 迟到登记，**只能加行、不得改前行**——本模块根本不提供改前行的入口，
    这条不是靠自觉遵守，是靠没有那个函数。
    """

    CREATE = "建点"
    TRANSITION = "转态"
    BACKFILL = "补记"
    VOID = "作废"


class Status(Enum):
    """状态（SCHEMA §二 `status`）。

    `待问`→`在途`→`已签认`→`已回灌`→`已落码` 单向推进；`已作废` 不在这条链上。
    倒退**不禁止**（现实里确有推翻重来），但**必须带 `note` 留因**（SCHEMA §三.1）。
    """

    ASKING = "待问"
    IN_FLIGHT = "在途"
    SIGNED = "已签认"
    FED_BACK = "已回灌"
    LANDED = "已落码"
    VOIDED = "已作废"

    @property
    def rank(self) -> int:
        """链上序号；`已作废` 不在链上，返回 ``-1``。"""
        return _STATUS_RANK.get(self, -1)


_STATUS_RANK: dict[Status, int] = {
    Status.ASKING: 0,
    Status.IN_FLIGHT: 1,
    Status.SIGNED: 2,
    Status.FED_BACK: 3,
    Status.LANDED: 4,
}

# 🔴 必须带 `evidence` 的状态（SCHEMA §二 `evidence` 行 ＋ §三.2 ＋ D5）。
# `已签认` 在这个集合里，就是 D5「只能由真实回件驱动」在数据层的全部实现——
# 没有落档回件路径就构造不出这一行，构造不出就没有任何代码路径能把点推到 `已签认`。
EVIDENCE_REQUIRED_STATUSES = frozenset({Status.SIGNED, Status.FED_BACK})


class PointType(Enum):
    """口径点类型（P4 分流，SCHEMA §二 `type`）。

    🔴 `判据类` **永不默认生效**（IATF 显式签认红线）——`default_after_h` 只对
    `试用反馈`／`材料索取` 合法，见 `LedgerEvent` 不变式 ⑹。
    """

    CRITERION = "判据类"
    TRIAL_FEEDBACK = "试用反馈"
    MATERIAL_REQUEST = "材料索取"

    @property
    def may_default(self) -> bool:
        return self is not PointType.CRITERION


def _require_text(field_name: str, value: Any, *, context: str) -> str:
    if not isinstance(value, str):
        raise LedgerContractError(
            f"{context}：{field_name} 必须是字符串，得到 {type(value).__name__}"
        )
    text = value.strip()
    if not text:
        raise LedgerContractError(f"{context}：{field_name} 不得为空")
    return text


def _require_str_list(field_name: str, value: Any, *, context: str) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str) or not isinstance(value, (list, tuple)):
        raise LedgerContractError(
            f"{context}：{field_name} 必须是字符串数组，得到 {type(value).__name__}"
            f"（单个字符串也不行——写成 [\"…\"]，否则遍历它会逐字符跑）"
        )
    out = []
    for i, item in enumerate(value):
        out.append(_require_text(f"{field_name}[{i}]", item, context=context))
    return tuple(out)


def _require_fact_date(value: Any, *, context: str) -> str:
    """`fact_date` ＝ 严格 `YYYY-MM-DD` 且真实存在的一天，或字面量 `事实日未知`。"""
    text = _require_text("fact_date", value, context=context)
    if text == FACT_DATE_UNKNOWN:
        return text
    if not _ISO_DATE_RE.fullmatch(text):
        raise LedgerContractError(
            f"{context}：fact_date={value!r} 不是 YYYY-MM-DD 形态。"
            f"事实日不可考时写字面量 {FACT_DATE_UNKNOWN!r}，"
            f"🔴 **不得用补记日顶替**（SCHEMA §二；成因见 tasks 3.3 的 12 封信实证）。"
        )
    try:
        date.fromisoformat(text)
    except ValueError as exc:
        raise LedgerContractError(
            f"{context}：fact_date={value!r} 形态对但这一天并不存在（{exc}）"
        ) from exc
    return text


def _require_optional_date(field_name: str, value: Any, *, context: str) -> str | None:
    if value is None:
        return None
    text = _require_text(field_name, value, context=context)
    if not _ISO_DATE_RE.fullmatch(text):
        raise LedgerContractError(f"{context}：{field_name}={value!r} 不是 YYYY-MM-DD 形态")
    try:
        date.fromisoformat(text)
    except ValueError as exc:
        raise LedgerContractError(
            f"{context}：{field_name}={value!r} 形态对但这一天并不存在（{exc}）"
        ) from exc
    return text


def _require_recorded_on(value: Any, *, context: str) -> str:
    text = _require_text("recorded_on", value, context=context)
    if not _RECORDED_ON_RE.fullmatch(text):
        raise LedgerContractError(
            f"{context}：recorded_on={value!r} 必须是带时区偏移的时间戳"
            f"（如 2026-09-06T21:30:00+08:00）。"
            f"🔴 没有偏移的时间戳说不清是 UTC 还是本地，而它正是算「补记滞后」的那一半。"
        )
    return text


def _as_enum(enum_cls: type[Enum], field_name: str, value: Any, *, context: str) -> Any:
    if isinstance(value, enum_cls):
        return value
    text = _require_text(field_name, value, context=context)
    for member in enum_cls:
        if member.value == text:
            return member
    raise LedgerContractError(
        f"{context}：{field_name}={value!r} 不在册。合法值：{[m.value for m in enum_cls]}"
    )


@dataclass(frozen=True)
class LedgerEvent:
    """台账里的一行 —— **一次事件**，不是一个点的当前态。

    同一 `id` 的多行按文件顺序 ＝ 时间顺序，**最后一行**是当前态（SCHEMA §一 引言）。
    历史行永不改写：本类 frozen，且 `LedgerStore` 只提供 append、没有 update／delete。
    """

    id: str
    event: Event
    status: Status
    fact_date: str
    recorded_on: str
    by: str
    # —— 以下为 `建点` 行必填、其余行可空 ——
    type: PointType | None = None
    scene: str | None = None
    proposer: str | None = None
    case_text: str | None = None
    proposed_ruling: str | None = None
    # —— 以下全行可空 ——
    carrier: tuple[str, ...] = ()
    letters: tuple[str, ...] = ()
    due: str | None = None
    evidence: str | None = None
    note: str | None = None
    default_after_h: int | None = None

    # 未在 SCHEMA §二 字段表里的键，原样保留、不丢弃（向前兼容）。
    # 🔴 **保留而不是静默丢弃**：丢弃一个未知键 ＝ 悄悄改写了别人写下的事实。
    extra: dict[str, Any] = field(default_factory=dict, compare=False)

    def __post_init__(self) -> None:
        ctx = f"台账行 id={self.id!r} event={getattr(self.event, 'value', self.event)!r}"

        object.__setattr__(self, "id", _require_text("id", self.id, context=ctx))
        object.__setattr__(self, "event", _as_enum(Event, "event", self.event, context=ctx))
        object.__setattr__(self, "status", _as_enum(Status, "status", self.status, context=ctx))
        object.__setattr__(self, "fact_date", _require_fact_date(self.fact_date, context=ctx))
        object.__setattr__(self, "recorded_on", _require_recorded_on(self.recorded_on, context=ctx))
        object.__setattr__(self, "by", _require_text("by", self.by, context=ctx))
        object.__setattr__(self, "carrier", _require_str_list("carrier", self.carrier, context=ctx))
        object.__setattr__(self, "letters", _require_str_list("letters", self.letters, context=ctx))
        object.__setattr__(self, "due", _require_optional_date("due", self.due, context=ctx))

        for name in ("scene", "proposer", "case_text", "proposed_ruling", "evidence", "note"):
            value = getattr(self, name)
            if value is not None:
                object.__setattr__(self, name, _require_text(name, value, context=ctx))

        if self.type is not None:
            object.__setattr__(self, "type", _as_enum(PointType, "type", self.type, context=ctx))

        # 不变式 ⑴：`建点` 行五个字段必填（SCHEMA §二「✅（建点行）」那一列）。
        if self.event is Event.CREATE:
            missing = [
                n
                for n in ("type", "scene", "proposer", "case_text", "proposed_ruling")
                if getattr(self, n) is None
            ]
            if missing:
                raise LedgerContractError(
                    f"{ctx}：`建点` 行缺必填字段 {missing}。"
                    f"🔑 建点行是这个点唯一一次记录「它是什么」的机会——"
                    f"后续 `转态` 行不重复这些字段，此处缺了就永远缺了。"
                )
            # 不变式 ⑵：`id` 必须以 `<scene>-` 开头（SCHEMA §二 `id` 两形态皆如此）。
            if not self.id.startswith(f"{self.scene}-"):
                raise LedgerContractError(
                    f"{ctx}：id={self.id!r} 与 scene={self.scene!r} 不一致，"
                    f"id 须形如 `<场景码>-…`"
                )
            # ⚠️ `carrier` **刻意不在此处强制 ≥1** —— 见本文件首部《`carrier` 口径已定死》。
            # 一句话：强制 ≥1 会让 tasks 6.3 的质量型指标「承接载体缺失数量」
            # 结构性恒为 0（指标被自己的校验消灭），且 tasks §2 回溯拆点里那些
            # 本来就没有载体的历史点将**无法如实入库**，只能被迫编一个载体。
            # ⇒ 载体缺失走**度量**（`Snapshot.missing_carrier`），不走写入拒绝。

        # 不变式 ⑷：`作废` 事件与 `已作废` 状态互为充要（避免两个字段各说各话）。
        if (self.event is Event.VOID) != (self.status is Status.VOIDED):
            raise LedgerContractError(
                f"{ctx}：event=`作废` 与 status=`已作废` 必须同时出现或同时不出现，"
                f"当前 event={self.event.value}／status={self.status.value}"
            )

        # 不变式 ⑸：`已签认`／`已回灌` 行必须带 `evidence`（SCHEMA §三.2，D5）。
        # 🔴 这一条放在**构造期**而不是写入期，是刻意的：连一个「没有回件的已签认」
        # 对象都造不出来，就没有任何代码路径能把它传给写入口去碰运气。
        if self.status in EVIDENCE_REQUIRED_STATUSES and not self.evidence:
            raise LedgerContractError(
                f"{ctx}：status={self.status.value} 的行必须带 evidence（落档回件路径）。"
                f"🔴 D5：`已签认` 只能由**真实回件**驱动，不存在任何超期自动签认路径。"
                f"没有回件就让它留在 `在途`——超期只生成催办草稿，不改状态。"
            )

        # 不变式 ⑹：`判据类` 永不默认生效（IATF 显式签认红线，P4）。
        if self.default_after_h is not None:
            if not isinstance(self.default_after_h, int) or isinstance(self.default_after_h, bool):
                raise LedgerContractError(f"{ctx}：default_after_h 必须是整数小时")
            if self.default_after_h <= 0:
                raise LedgerContractError(f"{ctx}：default_after_h 必须为正")
            if self.type is PointType.CRITERION:
                raise LedgerContractError(
                    f"{ctx}：`判据类` 不得带 default_after_h。"
                    f"🔴 判定规则／口径／阈值类**永不默认生效**（IATF 显式签认红线，P4）；"
                    f"可标默认的只有 `试用反馈`／`材料索取`。"
                )

    # ---------------------------------------------------------------- 序列化

    def to_dict(self) -> dict[str, Any]:
        """按 SCHEMA §二 的字段顺序输出；`None`／空数组不写键（保持行短、可读）。"""
        out: dict[str, Any] = {
            "id": self.id,
            "event": self.event.value,
            "status": self.status.value,
        }
        if self.type is not None:
            out["type"] = self.type.value
        for name in ("scene", "proposer"):
            if getattr(self, name) is not None:
                out[name] = getattr(self, name)
        out["fact_date"] = self.fact_date
        out["recorded_on"] = self.recorded_on
        out["by"] = self.by
        for name in ("case_text", "proposed_ruling"):
            if getattr(self, name) is not None:
                out[name] = getattr(self, name)
        if self.carrier:
            out["carrier"] = list(self.carrier)
        if self.letters:
            out["letters"] = list(self.letters)
        if self.due is not None:
            out["due"] = self.due
        if self.evidence is not None:
            out["evidence"] = self.evidence
        if self.note is not None:
            out["note"] = self.note
        if self.default_after_h is not None:
            out["default_after_h"] = self.default_after_h
        out.update(self.extra)
        return out

    def to_json_line(self) -> str:
        """一行 JSON，UTF-8、不转义中文、不含换行（换行由写入口补）。"""
        return json.dumps(self.to_dict(), ensure_ascii=False, separators=(",", ":"))

    _KNOWN_KEYS = frozenset(
        {
            "id", "event", "status", "type", "scene", "proposer", "fact_date",
            "recorded_on", "by", "case_text", "proposed_ruling", "carrier",
            "letters", "due", "evidence", "note", "default_after_h",
        }
    )

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "LedgerEvent":
        if not isinstance(raw, dict):
            raise LedgerContractError(f"台账行必须是 JSON 对象，得到 {type(raw).__name__}")
        missing = [k for k in ("id", "event", "status", "fact_date", "recorded_on", "by")
                   if k not in raw]
        if missing:
            raise LedgerContractError(f"台账行缺必填键 {missing}：{raw!r}")
        return cls(
            id=raw["id"],
            event=raw["event"],
            status=raw["status"],
            fact_date=raw["fact_date"],
            recorded_on=raw["recorded_on"],
            by=raw["by"],
            type=raw.get("type"),
            scene=raw.get("scene"),
            proposer=raw.get("proposer"),
            case_text=raw.get("case_text"),
            proposed_ruling=raw.get("proposed_ruling"),
            carrier=tuple(raw.get("carrier") or ()),
            letters=tuple(raw.get("letters") or ()),
            due=raw.get("due"),
            evidence=raw.get("evidence"),
            note=raw.get("note"),
            default_after_h=raw.get("default_after_h"),
            extra={k: v for k, v in raw.items() if k not in cls._KNOWN_KEYS},
        )

    @classmethod
    def from_json_line(cls, line: str) -> "LedgerEvent":
        return cls.from_dict(json.loads(line))

    @property
    def domain(self) -> Domain:
        """该行所属的域（由 `id` 前缀推出，D2）。"""
        return Domain.for_id(self.id)
