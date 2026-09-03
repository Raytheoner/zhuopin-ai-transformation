"""FI10 数据模型 —— 存货跌价测试的输入/输出契约（骨架期只定形）。

输入：
  · `InventoryAging`   库存账龄一条（料号 × 批次 × 库龄 × 成本）。
  · `InTransitPo`      在途采购一条。
  · `BomUsage`         BOM 用量（该料还会不会被用掉）。
  · `OemProjectPhase`  OEM 项目生命周期（APQP/EOP）。🔴 涉 OEM 专属数据，见下方警告。
输出：
  · `WritedownTest`    NRV vs Cost 跌价测试结果。
  · `WritedownAlert`   三类预警之一。
  · `ProvisionAdvice`  跌价准备计提建议一行。

🔴 **`OemProjectPhase` 的警告**：本类承载 **OEM 专属数据**。按根 `CLAUDE.md` §7-3，
比亚迪/上汽/理想的项目数据严格隔离、禁跨库；实现时须走
`zhuopin_platform.data_isolation_layer.OEMRouter` 按客户路由，跨库抛 `CrossOEMAccessError`。
本类的 `oem_customer` 字段**必填、无默认值**——一条不知道属于哪个客户的 OEM 项目数据，
在隔离体系里是无处安放的，让它可以留空就是给混库开了个口子。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class InventoryAging:
    """库存账龄一条。"""
    material_id: str
    material_name: str
    batch_no: str
    qty: float
    unit_cost: float
    aging_days: int
    warehouse: str = ""
    as_of_date: str = ""

    @property
    def book_cost(self) -> float:
        """账面成本 ＝ 数量 × 单位成本。纯派生量，不含判据。"""
        return self.qty * self.unit_cost


@dataclass
class InTransitPo:
    """在途采购一条（尚未到货，但已构成未来存货）。"""
    po_no: str
    material_id: str
    qty_ordered: float
    qty_received: float
    unit_price: float
    eta: str = ""

    @property
    def qty_in_transit(self) -> float:
        """在途量 ＝ 已订 − 已收。与 `kit_engine.calc_shortage` 的在途口径一致。"""
        return self.qty_ordered - self.qty_received


@dataclass
class BomUsage:
    """BOM 用量 —— 该料在在产/在手机型上还会不会被用掉。"""
    material_id: str
    product_id: str
    qty_per_unit: float
    active: bool = True


@dataclass
class OemProjectPhase:
    """OEM 项目生命周期（APQP/EOP）。🔴 见模块 docstring 的 OEM 隔离警告。"""
    project_id: str
    oem_customer: str            # 🔴 必填、无默认值：不知属谁的 OEM 数据在隔离体系里无处安放
    phase: str                   # APQP阶段 | 量产 | EOP | 终止
    material_ids: list[str] = field(default_factory=list)
    phase_date: str = ""


@dataclass
class WritedownTest:
    """NRV vs Cost 跌价测试结果。

    🔴 `needs_manual_review` 默认 `True`：本场景是 L2（AI 测算＋预警，财务/供应链经理确认）。
    """
    material_id: str
    batch_no: str
    book_cost: float
    nrv: Optional[float] = None      # 🔴 NRV 估算口径未签认时为 None，引擎须 fail-loud
    writedown_amount: Optional[float] = None
    needs_manual_review: bool = True
    basis: str = ""
    rule_version: str = ""


@dataclass
class WritedownAlert:
    """三类预警之一：库龄超期 / 芯片降价超阈值 / 项目终止未耗物料。

    🔴 `alert_type` 取 `aging` | `chip_price_drop` | `terminated_project`。
    其中 **`chip_price_drop` 在芯片价格 API 前置满足前不得产生**——见 `config
    .CHIP_PRICE_API_BLOCKED`。骨架有一条用例守住这个"不得产生"。
    """
    material_id: str
    alert_type: str
    severity: str = ""
    reason: str = ""
    rule_version: str = ""


@dataclass
class ProvisionAdvice:
    """跌价准备计提建议一行。

    🔴 `disclaimer` 无默认值：计提建议影响财务报表，任何输出都必须显式带上
    「AI 测算建议，须财务/供应链经理确认」的标注。
    """
    material_id: str
    period: str
    provision_amount: float
    disclaimer: str              # 🔴 必填，无默认值
    basis: str = ""
    rule_version: str = ""
    confirmed_by: str = ""       # 实名；空 ＝ 未确认，不得据以入账
