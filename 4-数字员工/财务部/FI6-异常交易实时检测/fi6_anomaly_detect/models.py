"""FI6 数据模型 —— 交易流水与异常判定的契约（骨架期只定形）。

输入：
  · `Transaction`      应付/应收交易流水一笔。
  · `PartyProfile`     往来单位（供应商/客户）主数据，关联方识别的输入之一。
  · `HistoryBaseline`  某单位/科目的历史模式基线快照。
输出：
  · `AnomalyFinding`   逐笔异常判定（命中模式／风险等级／是否推送／理由）。
  · `CaseRecord`       可疑交易案例库条目（人工确认后的判例，供持续学习）。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Transaction:
    """应付/应收交易流水一笔。

    🔴 `direction` 只取 `AP`（应付）/`AR`（应收）。**付款环节**的重复/超额/账户风险
    属 `FI3` 范围，不在本场景内（#471 范围边界）。
    """
    txn_id: str
    direction: str                 # AP | AR
    party_id: str                  # 往来单位编码
    account: str                   # 科目
    amount: float
    txn_date: str
    period: str = ""
    source_doc: str = ""           # 来源单据号


@dataclass
class PartyProfile:
    """往来单位主数据（关联方识别的输入之一）。

    🔴 本类**刻意不含任何"是否关联方"的布尔字段**——关联口径尚未定义（`config
    .RELATED_PARTY_CRITERIA` 为 `None`）。留一个 `is_related` 字段会诱使实现方
    先填上再说，那就是判据被默默造出来的方式。
    """
    party_id: str
    party_name: str
    party_type: str = ""           # 供应商 | 客户
    unified_social_code: str = ""  # 统一社会信用代码
    registered_address: str = ""


@dataclass
class HistoryBaseline:
    """某（单位 × 科目 × 方向）的历史模式基线快照。

    字段刻意留成描述性统计量，**不含任何判定阈值**——阈值属判据、在 `config` 里且未签认。
    """
    party_id: str
    account: str
    direction: str
    sample_months: int
    mean_amount: float
    median_amount: float
    stddev_amount: float
    mean_monthly_count: float


@dataclass
class AnomalyFinding:
    """逐笔异常判定结论。

    🔴 `escalated` 默认 `False` 但 `needs_manual_review` 默认 `True`：本场景是 L2
    （AI 标记并推送，财务主管确认处理），AI 不自行处置；"是否升级推送"由签认门限决定，
    未签认前引擎须 fail-loud、而不是默认推或默认不推。
    """
    txn_id: str
    patterns: list[str] = field(default_factory=list)   # amount_surge | frequency | related_party
    risk_grade: str = ""
    needs_manual_review: bool = True
    escalated: bool = False
    reason: str = ""
    rule_version: str = ""


@dataclass
class CaseRecord:
    """可疑交易案例库条目 —— 人工确认后的判例，供持续学习。

    🔴 该库当前**无既有载体**（本泳道 2026-09-03 实测），本类是它的第一个契约定义。
    `confirmed_by` 必填实名：判例的价值全在"谁认的"，匿名判例不可用于回归。
    """
    case_id: str
    txn_id: str
    verdict: str                   # 确属异常 | 误报 | 待定
    confirmed_by: str              # 🔴 实名，不得留空
    confirmed_at: str
    patterns: list[str] = field(default_factory=list)
    note: str = ""
    rule_version: str = ""
