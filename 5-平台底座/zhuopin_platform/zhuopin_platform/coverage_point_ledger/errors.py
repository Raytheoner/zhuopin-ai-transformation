"""`coverage_point_ledger` 的异常族 —— 全部 **fail-loud**，没有一个是可吞的。

分四类，语义互不重叠：

  · `LedgerContractError`  —— 一**行**事件本身不成形（缺必填字段／日期形态不对／枚举值不存在）。
    在 `LedgerEvent` **构造期**即抛，不等到写盘。
  · `LedgerWriteRejected`  —— 行成形，但**放进这本账里**不成立（`已签认` 无 `evidence`、
    `id` 前缀与域文件不符、状态倒退却不留因、`建点` 不是第一行……）。
    ⇒ SCHEMA §三 的第 1／2／6 条全部落在这一类。
  · `LedgerReadError`      —— 读到一行不是合法 JSON，或文件里同一 `id` 的行序与状态链矛盾。
    🔴 **不跳过坏行**：跳过 ＝ 少算一个点，而少算不产生任何信号。
  · `LedgerLintError`      —— 台账**目录**布局违规（D8：出现子目录）。

🔴 四者都不提供「记个 warning 然后继续」的旁路。本台账的全部价值是
「事实一经写入即不可被静默改写」，而静默的前提就是有人吞异常。
"""
from __future__ import annotations


class LedgerError(RuntimeError):
    """本模块所有异常的基类（调用方要一把捞时用它）。"""


class LedgerContractError(LedgerError, ValueError):
    """一行事件不成形，在 `LedgerEvent` 构造期即抛。

    覆盖 SCHEMA §二 的字段契约：必填缺失、`fact_date` 既不是 `YYYY-MM-DD` 也不是
    字面量 `事实日未知`、`recorded_on` 缺时区、枚举值不在册、`carrier`／`letters`
    不是字符串数组。
    """


class LedgerWriteRejected(LedgerError):
    """行成形但写入被拒 —— SCHEMA §三 约束 1／2／6 的落点。

    🔴 这条异常**就是「`已签认` 只能由真实回件驱动」（D5）的执行面**：
    没有 `evidence` 的 `已签认` 在这里被拒，而不是被降级成 warning 后照写。
    """


class LedgerReadError(LedgerError):
    """台账文件读取失败（坏行／行序与状态链矛盾）。

    🔴 刻意不提供 `errors="ignore"` 式开关：一行读不动就是一个点算不出来，
    **必须炸在读的那一刻**，不能等到度量数字变小才被人反推出来。
    """


class LedgerLintError(LedgerError):
    """台账目录布局违规（D8：目录下出现子目录）。

    成因（审材料 §6.3 第 4 条对照组实测）：`.gitignore` 的 `!` 例外**不递归**，
    子目录里的 `.jsonl` 仍被 git 静默忽略 —— **不报错、不提示、文件就是进不了库**。
    又一个「错误不产生任何信号」，故必须由 lint 主动去找。
    """
