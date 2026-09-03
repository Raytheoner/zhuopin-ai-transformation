"""判据与签认记录的数据结构。

两个类，一句话分工：
  · `Signoff`   —— 「**谁**、在**什么时候**、凭**哪份落档**、把规则升到**哪一版**」。
  · `Criterion` —— 一条待签认判据本身；未签认时值恒为 ``None``，读取即抛。

🔴 **`None` 在本模块里只有一个含义：未签认。** 若某条判据的签认结论恰好是「不设阈值」，
必须签成一个**显式值**（``False`` / ``{}`` / 自定义哨兵对象），**不得签成 ``None``**
——否则「业务上定了不设限」和「压根没人定」这两件完全不同的事会共用同一个表示，
本模块的全部保护随之失效。该约束由 `Criterion.__post_init__` 的不变式 ⑵ 强制。
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any

from .errors import CriterionContractError, CriterionNotSignedOffError

# 占位词黑名单：这些不是签认，是「签认」两个字的 cosplay。
# 收在这里而不是散在各场景，是因为空签的形态跨场景完全一致（design D3 定夺项 ①）。
_PLACEHOLDER_TOKENS = frozenset(
    {"tbd", "todo", "n/a", "na", "none", "null", "-", "?", "待定", "待确认", "待补", "未定", "无"}
)


def _require_text(field_name: str, value: Any, *, context: str) -> str:
    """字段必须是非空、非占位词的字符串，否则构造期即抛。"""
    if not isinstance(value, str):
        raise CriterionContractError(f"{context}：{field_name} 必须是字符串，得到 {type(value).__name__}")
    text = value.strip()
    if not text:
        raise CriterionContractError(f"{context}：{field_name} 不得为空")
    if text.lower() in _PLACEHOLDER_TOKENS:
        raise CriterionContractError(
            f"{context}：{field_name}={value!r} 是占位词，不算签认。"
            f"签认要的是实名与真凭据——填不出来就说明这条判据还没签认，让它留在未签认状态即可。"
        )
    return text


@dataclass(frozen=True)
class Signoff:
    """一次判据签认的落档记录。四个字段**全部必填、无默认值**。

    「无默认值」是刻意的：给任何一个字段配默认，就等于允许有人漏填它还能构造成功
    ——与 FI6 `CaseRecord.confirmed_by`、FI9 `AuxLedgerRow.disclaimer` 同一条纪律。

    :param signed_by:    签认人**实名**（真人姓名，不是「财务部」这类部门名——IATF 要可归责到人）
    :param signed_on:    签认日期（``YYYY-MM-DD``）
    :param evidence:     落档凭据（文件路径 / 文号 / 会议纪要编号，须可被第三方翻出来核对）
    :param rule_version: 本次签认后生效的规则版本号
    """

    signed_by: str
    signed_on: str
    evidence: str
    rule_version: str

    def __post_init__(self) -> None:
        ctx = "签认记录"
        for name in ("signed_by", "signed_on", "evidence", "rule_version"):
            _require_text(name, getattr(self, name), context=ctx)


@dataclass(frozen=True)
class Criterion:
    """一条判据。未签认时 ``raw_value is None``，且读 ``.value`` 必抛。

    :param key:       判据标识（在其注册表内唯一）
    :param question:  这条判据到底要人定什么，一句话说清（写给三个月后的承接方看）
    :param owner:     应由谁签认（角色/部门，如「财务侧」「CFO 办公室」）
    :param note:      可选补充说明（为什么还签不下来、卡在哪）
    :param signoff:   签认记录；``None`` ＝ 未签认
    :param raw_value: **未经保护的原值**，仅供检视/测试断言。业务代码请一律走 ``.value``。

    不变式（构造期强制，见 `errors.CriterionContractError`）：
      ⑴ ``raw_value`` 非空 ⇒ ``signoff`` 必须在（不许「填了数没人签」）；
      ⑵ ``signoff`` 在 ⇒ ``raw_value`` 不得为 ``None``（不许空签，且见模块首部对 ``None`` 的说明）。

    ⚠️ ``raw_value`` 这个名字是刻意起丑的：它读起来就像「你正在绕过保护」，
    因为你确实是。若只是想知道签没签，用 ``is_signed``，别去看 ``raw_value``。
    """

    key: str
    question: str
    owner: str
    note: str = ""
    signoff: Signoff | None = None
    raw_value: Any = None

    def __post_init__(self) -> None:
        ctx = f"判据 {self.key!r}" if isinstance(self.key, str) and self.key.strip() else "判据"
        _require_text("key", self.key, context="判据声明")
        _require_text("question", self.question, context=ctx)
        _require_text("owner", self.owner, context=ctx)
        if self.note is not None and not isinstance(self.note, str):
            raise CriterionContractError(f"{ctx}：note 必须是字符串")

        if self.raw_value is not None and self.signoff is None:
            raise CriterionContractError(
                f"{ctx} 已被填值 {self.raw_value!r}，却没有签认记录。"
                f"填数是替 {self.owner} 做判断——要么补上 Signoff（实名＋日期＋落档凭据），"
                f"要么把值撤回 None。"
            )
        if self.signoff is not None and self.raw_value is None:
            raise CriterionContractError(
                f"{ctx} 有签认记录（{self.signoff.signed_by}）却没有值。"
                f"若签认结论就是「不设阈值」，请签成显式值（False / {{}} / 哨兵对象），"
                f"不得签成 None —— None 在本模块里唯一含义是「未签认」。"
            )

    # ── 读取路径 ───────────────────────────────────────────────────────────
    @property
    def is_signed(self) -> bool:
        """签认了没有。**这是唯一允许的「先问问」方式**，且它不返回值、只返回布尔。"""
        return self.signoff is not None

    @property
    def value(self) -> Any:
        """判据的值。**未签认时抛 `CriterionNotSignedOffError`，永不返回 ``None``。**

        🔴 本属性没有、也不会有 ``default`` 参数——属性天生就传不了参，
        这是刻意选属性而非 ``get_value(default=...)`` 方法的原因之一。
        """
        if self.signoff is None:
            raise CriterionNotSignedOffError(
                f"判据 {self.key!r} 尚未签认，不得读取。\n"
                f"  它要定的是：{self.question}\n"
                f"  应由谁签：{self.owner}\n"
                + (f"  备注：{self.note}\n" if self.note else "")
                + f"  正确做法：等 {self.owner} 签认落档后 → `criterion.signed(值, Signoff(...))` → 升 RULE_VERSION → 同步改守卫用例。\n"
                f"  🔴 不要在这里 try/except 兜个默认值：那正是本异常要拦的事。"
            )
        return self.raw_value

    # ── 签认（不可变：返回新对象，不就地改）────────────────────────────────
    def signed(self, value: Any, signoff: Signoff) -> "Criterion":
        """返回一条**新的**已签认判据。原对象不变（frozen）。

        刻意不做成 ``criterion.value = x`` 的 setter：判据从未签认变成已签认是一次
        **有据可查的状态跃迁**，不是给字段赋个值；不可变 ＋ 显式重建让「谁在哪一行签的」
        永远留在代码里，而不是被某个运行期赋值悄悄改掉。
        """
        if not isinstance(signoff, Signoff):
            raise CriterionContractError(
                f"判据 {self.key!r}：signed() 的第二个参数必须是 Signoff 实例，"
                f"得到 {type(signoff).__name__}"
            )
        return replace(self, raw_value=value, signoff=signoff)
