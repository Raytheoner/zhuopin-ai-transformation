"""FI9 数据模型 —— 研发费用归集与判定的契约（骨架期只定形）。

输入：
  · `RdProject`     研发项目主数据。
  · `CostEntry`     项目成本一条（材料/人工/制造费用），源 U9C 项目成本模块。
  · `LaborRecord`   人工工时记录。🔴 见下方警告。
输出：
  · `CapitalizationVerdict`  资本化/费用化判定。
  · `AuxLedgerRow`           研发费用辅助账一行（高新要求）。

🔴 **`LaborRecord` 的警告**：本类存在**不代表**工时系统存在。工时系统在本项目内
**无任何既有取数指针**，是否存在都未核实（见 `config.TIMESHEET_SYSTEM_UNVERIFIED`）。
本类是"若它存在、数据长这样"的契约占位，`source` 必填且骨架期只允许 `"synthetic"`。

🔴 **发票号 join 纪律**（若材料费用需与发票对碰）：本项目已实测证伪过「发票号字面 join」
一次——FI2 变更包 `fi2-tax-export-ingest`（归档 2026-08-07）原文「真实探测推翻 #249
原计划的『发票号字面 join』假设，改用后 8 位＋客户端 suffix 校验，8/8 真实样本唯一命中」。
⇒ 本场景凡涉发票号对碰须**先做一次字面一致性实测**（位数／前导零／空格／全半角／代码
前缀），**不得直接沿用 FI2 的后 8 位方案**（两套来源不同，FI2 只证明了"不能想当然"）。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class RdProject:
    """研发项目主数据。"""
    project_id: str
    project_name: str
    start_date: str
    end_date: str = ""
    status: str = ""              # 立项 | 在研 | 结项 | 终止
    is_high_tech_scope: Optional[bool] = None   # 🔴 是否纳入高新口径，须按签认政策库判定，不预设


@dataclass
class CostEntry:
    """项目成本一条（材料/人工/制造费用）。"""
    project_id: str
    entry_id: str
    cost_type: str                # 材料 | 人工 | 制造费用
    amount: float
    period: str
    account: str = ""
    invoice_no: Optional[str] = None    # 🔴 join 纪律见模块 docstring
    source_doc: str = ""


@dataclass
class LaborRecord:
    """人工工时记录。🔴 见模块 docstring 的警告——工时系统是否存在都未核实。"""
    project_id: str
    employee_id: str
    period: str
    hours: float
    source: str                   # 骨架期只允许 "synthetic"
    rate: Optional[float] = None  # 🔴 工时单价口径属判据，未签认前为 None


@dataclass
class CapitalizationVerdict:
    """资本化/费用化判定。

    🔴 `needs_manual_review` 默认 `True` 且 `is_external_ready` 恒为 `False`：
    本场景产出用于政府申报，AI 的结论永远只是建议。`is_external_ready` **没有**设为
    `True` 的合法路径——对外可用与否由人决定，不由数据结构声明。
    """
    project_id: str
    entry_id: str
    verdict: str = ""             # 资本化 | 费用化 | 待定
    basis: str = ""               # 判定所依据的准则条款/企业政策条目
    needs_manual_review: bool = True
    is_external_ready: bool = False
    rule_version: str = ""


@dataclass
class AuxLedgerRow:
    """研发费用辅助账一行（高新认定要求的格式）。

    🔴 `disclaimer` 无默认值：任何可对外提交的产物都必须**显式**带上"AI 归集建议、
    须人工审核确认"的标注。给它一个默认值就等于允许有人忘了写。
    """
    project_id: str
    period: str
    cost_type: str
    amount: float
    disclaimer: str               # 🔴 必填，无默认值
    account: str = ""
    rule_version: str = ""
    reviewed_by: str = ""         # 实名；空 ＝ 未经审核，不得对外
