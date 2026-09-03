"""场景判据注册表 —— 一个场景把它全部待签认判据登记在一处。

🔴 **本模块刻意没有的东西**（每一条都是被主动否掉的，不是忘了写）：
  · ``value_of(key, default=...)``  —— 有 default 就等于有旁路，本模块的全部保护一行绕过；
  · ``get_or_none(key)``            —— 同上，换了个名字而已；
  · ``__getattr__`` / ``__getitem__`` 上的容错回退 —— 拼错 key 必须炸，不许静默返回空；
  · 任何 ``warnings.warn`` 后继续执行的路径 —— warning 不是信号，是噪音里的一行。

要「先问问签没签」，用 `is_signed()` / `unsigned_keys()`：它们返回布尔与 key 列表，
**永远不返回判据的值**，所以不能被当成旁路使用。
"""
from __future__ import annotations

from collections.abc import Iterable, Iterator
from typing import Any

from .errors import CriterionContractError, UnknownCriterionError
from .models import Criterion

# 规则版本号在「尚有判据未签认」时必须自陈的标记。
# 来源：FI5/FI6/FI8/FI9/FI10 五份场景各写了一遍 `assert "unsigned" in config.RULE_VERSION`
# （5 > 3，rule-of-three 触发），此处收拢为一处。
UNSIGNED_VERSION_TAG = "unsigned"


class CriteriaRegistry:
    """某个场景的全部待签认判据。

    用法（场景 ``config.py`` 里声明一次，全场景共用）::

        CRITERIA = CriteriaRegistry("FI5", [
            Criterion("L2_BUDGET_BLOCK_PCT",
                      question="占用预算余额超过百分之几即拦截并通知上级",
                      owner="财务侧"),
        ])
        RULE_VERSION = "fi5-skeleton-unsigned-2026-09-03"
        CRITERIA.assert_rule_version(RULE_VERSION)   # 版本号与签认状态对不上即抛

    引擎侧::

        pct = CRITERIA.value_of("L2_BUDGET_BLOCK_PCT")   # 未签认 ⇒ 抛，不返回 None
    """

    def __init__(self, scenario: str, criteria: Iterable[Criterion]) -> None:
        if not isinstance(scenario, str) or not scenario.strip():
            raise CriterionContractError("注册表：scenario（场景编号）不得为空")
        self._scenario = scenario.strip()
        self._criteria: dict[str, Criterion] = {}
        for c in criteria:
            if not isinstance(c, Criterion):
                raise CriterionContractError(
                    f"注册表 {self._scenario}：只接受 Criterion 实例，得到 {type(c).__name__}"
                )
            if c.key in self._criteria:
                raise CriterionContractError(
                    f"注册表 {self._scenario}：判据 key {c.key!r} 重复声明。"
                    f"重复 key 会让后一条静默盖掉前一条——两条判据里必有一条从此无人守。"
                )
            self._criteria[c.key] = c

    # ── 基本容器语义（只暴露 key 与判据对象，不直接吐值）────────────────────
    @property
    def scenario(self) -> str:
        return self._scenario

    def __len__(self) -> int:
        return len(self._criteria)

    def __iter__(self) -> Iterator[Criterion]:
        return iter(self._criteria.values())

    def __contains__(self, key: object) -> bool:
        return key in self._criteria

    def keys(self) -> tuple[str, ...]:
        """全部已声明的判据 key（声明顺序）。"""
        return tuple(self._criteria)

    def criterion(self, key: str) -> Criterion:
        """取判据对象本身（用于检视 question / owner / is_signed）。

        ⚠️ 它返回的是判据**对象**，不是判据的值——读值仍须走 ``.value``，那条路照样会抛。
        """
        try:
            return self._criteria[key]
        except KeyError:
            raise UnknownCriterionError(
                f"注册表 {self._scenario} 没有声明判据 {key!r}。"
                f"已声明的是：{'、'.join(self._criteria) or '（空）'}"
            ) from None

    # ── 读值（唯一路径，无 default 参数）────────────────────────────────────
    def value_of(self, key: str) -> Any:
        """读一条判据的值。**未签认即抛 `CriterionNotSignedOffError`。**

        🔴 本方法的签名**只有 ``key`` 一个参数，永远不会加 ``default``**。
        单测 `test_no_default_bypass_in_public_api` 盯着这个签名；谁加了 default 参数，CI 立刻红。
        """
        return self.criterion(key).value

    # ── 状态查询（返回布尔与 key，从不返回值）────────────────────────────────
    def is_signed(self, key: str) -> bool:
        """这条判据签认了没有。"""
        return self.criterion(key).is_signed

    def unsigned_keys(self) -> tuple[str, ...]:
        """尚未签认的判据 key（声明顺序）。"""
        return tuple(k for k, c in self._criteria.items() if not c.is_signed)

    def signed_keys(self) -> tuple[str, ...]:
        """已签认的判据 key（声明顺序）。"""
        return tuple(k for k, c in self._criteria.items() if c.is_signed)

    @property
    def fully_signed(self) -> bool:
        """全部判据都签认了才为真；**空注册表返回 False**。

        空表返回 False 是刻意的：一个还没声明任何判据的场景，说它「判据全签完了」
        是最坏的一种假绿灯——它会让下游的 `require_all_signed()` 直接放行。
        """
        return bool(self._criteria) and not self.unsigned_keys()

    def require_all_signed(self) -> None:
        """全部签认才放行，否则一次性列出所有缺口后抛。

        给「引擎整体启动前」用；单条判据的保护由 ``value_of`` 承担，两者不互相替代
        ——只做整体校验会漏掉运行期才走到的分支，只做单条校验则要跑到那一行才发现。
        """
        if not self._criteria:
            raise CriterionContractError(
                f"注册表 {self._scenario} 未声明任何判据——"
                f"「没有判据」和「判据都签完了」不是一回事，此处不放行。"
            )
        missing = self.unsigned_keys()
        if missing:
            lines = [f"场景 {self._scenario} 尚有 {len(missing)} 条判据未签认，不得运行："]
            for k in missing:
                c = self._criteria[k]
                lines.append(f"  · {k}（应由 {c.owner} 签）：{c.question}")
            raise CriterionContractError("\n".join(lines))

    # ── 规则版本一致性 ──────────────────────────────────────────────────────
    def assert_rule_version(self, rule_version: str) -> None:
        """规则版本号必须与签认状态一致，对不上即抛。

        两个方向都查（只查一半等于没查）：
          · 尚有未签认判据，版本号却不含 ``unsigned`` ⇒ 骨架会被下游误当已定稿引用；
          · 判据全签认了，版本号却仍含 ``unsigned`` ⇒ 版本号在撒谎，下游据此判断即误判。
        """
        if not isinstance(rule_version, str) or not rule_version.strip():
            raise CriterionContractError(f"注册表 {self._scenario}：rule_version 不得为空")
        has_tag = UNSIGNED_VERSION_TAG in rule_version.lower()
        missing = self.unsigned_keys()
        if missing and not has_tag:
            raise CriterionContractError(
                f"场景 {self._scenario} 的 RULE_VERSION={rule_version!r} 未自陈 "
                f"{UNSIGNED_VERSION_TAG!r}，但仍有 {len(missing)} 条判据未签认："
                f"{'、'.join(missing)}。版本号不自陈，骨架就会被下游误当已定稿引用。"
            )
        if not missing and has_tag:
            raise CriterionContractError(
                f"场景 {self._scenario} 的判据已全部签认，RULE_VERSION={rule_version!r} "
                f"却仍带 {UNSIGNED_VERSION_TAG!r} 标记——版本号与实际状态不符，请升版。"
            )

    def __repr__(self) -> str:  # pragma: no cover - 诊断用
        return (
            f"<CriteriaRegistry {self._scenario}: "
            f"{len(self.signed_keys())} 已签 / {len(self._criteria)} 共>"
        )
