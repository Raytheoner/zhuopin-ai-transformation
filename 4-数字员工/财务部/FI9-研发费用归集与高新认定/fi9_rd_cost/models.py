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

🔴 **`RdProject.oem_customer` 的三态**（`EE-3`，Shao Peishen 2026-09-03 裁 design.md
§定夺项 ①③④，`openspec/changes/fi9-rd-cost-mvp/design.md` E2.1）：
  · `None`（**默认**）—— 未判，还没人认定这个项目属谁；允许归集明细，**禁止进任何
    汇总与对外产物**（③=(b)），并须出现在「因归属未判被排除的项目」清单的显要位置。
  · `REGISTERED_OEMS`（`zhuopin_platform.data_isolation_layer`）内的注册名，如
    `"比亚迪"` —— 归属须**随研发侧项目主数据来，财务侧只读不判**（④=(a)），🔴
    **绝不得从 `project_id`/`project_name` 的命名规则推导**（推错不报错，一错就是
    把 A 客户的费用记到 B 客户名下）。
  · `NON_OEM_PROJECT`（本模块显式哨兵常量）—— 明确非 OEM（平台预研/内部工装/通用
    技术储备）。🔴 **不许写成 `None`**：那会与「未判」共用同一表示，让「这个项目
    不涉客户数据」和「压根没人看过这个项目」变成同一件事。
  实现见 `fi9_rd_cost/oem_isolation.py`；该形态**不是判据**（数据字段的形状，非须
  签认的口径），故不进 `config.CRITERIA` 注册表。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

#: `RdProject.oem_customer` 的显式哨兵——「明确非 OEM」，与「未判」（`None`）严格区分。
#: 取值本身不必是自然语言（不对外展示），但须与任何真实 OEM 注册名（见
#: `zhuopin_platform.data_isolation_layer.REGISTERED_OEMS`）不冲突。
NON_OEM_PROJECT = "__NON_OEM_PROJECT__"


@dataclass
class RdProject:
    """研发项目主数据。"""
    project_id: str
    project_name: str
    start_date: str
    end_date: str = ""
    status: str = ""              # 立项 | 在研 | 结项 | 终止
    is_high_tech_scope: Optional[bool] = None   # 🔴 是否纳入高新口径，须按签认政策库判定，不预设
    oem_customer: Optional[str] = None
    # 🔴 OEM 归属，三态见模块 docstring：None=未判(默认) | 注册 OEM 名 | NON_OEM_PROJECT。
    # 只读字段——本类与本模块均不提供任何从 project_id/project_name 推导它的函数。


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
