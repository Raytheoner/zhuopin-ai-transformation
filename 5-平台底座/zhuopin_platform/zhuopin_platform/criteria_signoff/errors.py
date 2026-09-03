"""`criteria_signoff` 的异常族 —— 全部是 **fail-loud** 用的，没有一个是可吞的。

分三类，语义互不重叠：
  · `CriterionNotSignedOffError` —— **读**了一条尚未签认的判据。本模块的核心语义就是它。
  · `CriterionContractError`     —— **声明/签认**时违反了不变式（如填了数却没签认人）。
  · `UnknownCriterionError`      —— 读了一个本场景根本没声明过的 key（拼错名字）。

🔴 三者都不提供「返回默认值」的旁路。若你正在找一个 `get(key, default=...)`，
本模块**刻意没有**——理由见 `registry.py` 首部与 `openspec/changes/criteria-signoff-platform/design.md` D2。
"""
from __future__ import annotations


class CriteriaSignoffError(RuntimeError):
    """本模块所有异常的基类（调用方要一把捞时用它）。"""


class CriterionNotSignedOffError(CriteriaSignoffError):
    """读取了一条未签认的判据。

    🔴 这条异常**就是本模块存在的理由**。未签认判据的值恒为 ``None``，而 ``None``
    一旦被当成正常返回值流进下游，就会静默变成「没有阈值 ＝ 不拦截」「没有标准 ＝ 都合规」
    ——不报错、不产生任何信号、却已经替业务侧做了判断。故读取路径一律抛，
    不返回 ``None``、不回退默认、不记 warning 后继续。
    """


class CriterionContractError(CriteriaSignoffError, ValueError):
    """判据声明或签认违反不变式，在**构造期**即抛（不等到读取）。

    覆盖四种写法，它们都是「把未签认伪装成已签认」的不同外衣：
      ⑴ 填了值但没有签认记录（`raw_value is not None and signoff is None`）；
      ⑵ 有签认记录但值是 ``None``（空签——签了个寂寞，且会与「未签认」撞语义）；
      ⑶ 签认记录字段留空或填占位词（`签认人=""` / `"TBD"` / `"待定"`）；
      ⑷ 同一注册表里 key 重复（后者会静默盖掉前者）。
    """


class UnknownCriterionError(CriteriaSignoffError):
    """读取了本场景未声明的判据 key。

    刻意**不**继承 ``KeyError``：``dict`` 语义里 KeyError 常被 ``.get()`` 顺手吞掉，
    而本模块要的正是「吞不掉」。
    """
