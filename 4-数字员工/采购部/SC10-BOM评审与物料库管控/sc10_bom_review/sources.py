"""取数层 —— 现有 ERP 物料主数据可用；外部价格/参数/封装 API 未选型，整体留步。

## 为什么外部 API 只留一个 Protocol

全景规划 §2.1.2 SC10 写「接入 SRM/ERP/第三方贸易网站 API 取价格/参数/封装」，
而第三方 API **选型都还没做**（前置总表 §一 SC10 行，窗口 2027-01）。骨架期若挑一家
先接上，等于替姚祖怡把选型做了 —— 而选型结果会改字段口径、改配额、改缓存策略。

⚠️ **顺带记一处易混**：实施计划依赖表里另有一条「芯片市场价格 API」（FI10／O2 共用，
状态「待选型」），与本场景要的「第三方贸易网站 API」在服务对象与时点上都不同。
两者是否可合并采购一套，属队列 §一 `#475` 与 SC4 顺延移交单 §四 待定项 5，**本场景不代判**。
"""
from __future__ import annotations

from typing import Iterable, Protocol

from zhuopin_platform.shared_tools.models import BomRow, ProductionPlan

from . import pending
from .models import MaterialRecord


class MaterialMasterSource(Protocol):
    """公司物料主数据来源（ERP）。骨架期由 CSV/内存实现顶替，接口不变。"""

    def load_materials(self) -> Iterable[MaterialRecord]: ...


class InMemoryMasterSource:
    """mock 主数据源（红线 §7-1：先 mock 跑通再切真实库）。"""

    def __init__(self, records: Iterable[MaterialRecord]):
        self._records = list(records)

    def load_materials(self) -> list[MaterialRecord]:
        return list(self._records)


class ExternalCatalogSource(Protocol):
    """原厂/第三方贸易网站行情源（价格·参数·封装·生命周期）。"""

    def fetch(self, material_ids: Iterable[str]) -> dict[str, MaterialRecord]: ...


class UnselectedCatalogSource:
    """占位实现：调用即抛，点名卡在"选型未做"这一步。

    存在的意义是让调用链**现在就完整**：装配代码可以把它注入进去、把签名定死，
    真接入那天替换的是这一个类。
    """

    def fetch(self, material_ids: Iterable[str]) -> dict[str, MaterialRecord]:
        pending.require("external_price_api")
        raise AssertionError("unreachable")  # pragma: no cover - require() 恒抛


def load_bom_and_plans_from_platform(
    bom: list[BomRow], plans: list[ProductionPlan]
) -> tuple[list[BomRow], list[ProductionPlan]]:
    """显式声明本场景消费的是**底座模型**，不另立一套 BOM 结构。

    看起来是个没做事的函数，作用是把"BOM/生产计划一律走
    `zhuopin_platform.shared_tools.models`"这条约定钉在一个可被 import 的地方，
    而不是靠每个新文件的作者记得（同 `4-数字员工/CLAUDE.md` 第 1 步的立场）。
    """
    return bom, plans
