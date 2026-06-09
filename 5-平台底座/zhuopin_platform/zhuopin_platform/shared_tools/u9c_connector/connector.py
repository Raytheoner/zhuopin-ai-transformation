"""U9CConnector — 用友 U9C ERP 连接器骨架（收割自 supplychain src/data/u9c_connector.py）。

当前状态（待 2026-07-01 U9C MCP 接口就绪后补真实）：
  · 5 个 get_* 方法回退 CSVConnector（mock/脱敏数据），保证上层场景可运行；
  · 认证流程（RSA 登录 + Session Cookie）已设计，等 IT 确认 webapi 路径后接入；
  · 各方法 TODO 标记了真实实现位置。

切换真实 ERP：① IT 确认 webapi 路径（当前占位 /webapi/CommonEntity/Query）；
② 更新 .env 的 U9C_WEBAPI_PATH；③ 接入各方法的 HTTP 调用块。

收割改造：import 改指向平台 models/connector/csv_connector；可选注入 ConnectorAudit
（标注 CSV 回退访问痕迹）。
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import ClassVar

from ..connector import DataConnector
from ..connector_audit import ConnectorAudit
from ..csv_connector import CSVConnector
from ..models import (
    BomRow,
    InventoryRow,
    ProductionPlan,
    PurchaseOrder,
    Supplier,
)

# 默认 webapi 路径占位（IT 确认后替换 —— 7/1 MCP 接入点）
_DEFAULT_WEBAPI_PATH = "/webapi/CommonEntity/Query"


class U9CConnector(DataConnector):
    """用友 U9C ERP 数据连接器（骨架 — CSV 回退态，待 7/1 MCP）。

    认证流程（已验证可行，等待路径确认）：
      1. GET  {base_url}/mvc/Login/LoginPublicKey → RSA 公钥
      2. POST {base_url}/mvc/login/login         → 登录，获取 Session Cookie
      3. POST {base_url}/webapi/CommonEntity/Query + Cookie → 业务数据
    """

    _ENV_KEYS: ClassVar[dict[str, str]] = {
        "base_url":      "U9C_API_BASE",
        "user_code":     "U9C_USER_CODE",
        "password":      "U9C_API_PASSWORD",
        "ent_code":      "U9C_ENT_CODE",
        "org_code":      "U9C_ORG_CODE",
        "client_id":     "U9C_CLIENT_ID",
        "client_secret": "U9C_CLIENT_SECRET",
    }

    def __init__(
        self,
        base_url:      str,
        user_code:     str,
        password:      str,
        ent_code:      str,
        org_code:      str,
        client_id:     str,
        client_secret: str,
        webapi_path:   str = _DEFAULT_WEBAPI_PATH,
        fallback_dir:  Path | str | None = None,
        audit:         ConnectorAudit | None = None,
    ):
        self.base_url      = base_url.rstrip("/")
        self.user_code     = user_code
        self._password     = password          # 私有，避免打印泄漏
        self.ent_code      = ent_code
        self.org_code      = org_code
        self.client_id     = client_id
        self._client_secret = client_secret    # 私有
        self.webapi_path   = webapi_path
        self._audit = audit

        # 骨架态：回退 CSV mock，保证上层可运行
        self._fallback = CSVConnector(fallback_dir)

    @property
    def webapi_url(self) -> str:
        """完整 webapi 查询 URL（IT 确认路径后自动生效）。"""
        return self.base_url + self.webapi_path

    @classmethod
    def from_env(cls, audit: ConnectorAudit | None = None) -> "U9CConnector":
        """从环境变量读取配置（需 .env，见 .env.example）。"""
        missing = [k for k in cls._ENV_KEYS.values() if not os.environ.get(k)]
        if missing:
            raise ValueError(
                f"U9CConnector.from_env(): 以下环境变量未设置：{missing}\n"
                "请检查 .env 文件（参考 .env.example）"
            )
        return cls(
            base_url=      os.environ[cls._ENV_KEYS["base_url"]],
            user_code=     os.environ[cls._ENV_KEYS["user_code"]],
            password=      os.environ[cls._ENV_KEYS["password"]],
            ent_code=      os.environ[cls._ENV_KEYS["ent_code"]],
            org_code=      os.environ[cls._ENV_KEYS["org_code"]],
            client_id=     os.environ[cls._ENV_KEYS["client_id"]],
            client_secret= os.environ[cls._ENV_KEYS["client_secret"]],
            audit=audit,
        )

    def _trace_fallback(self, action: str) -> None:
        """标注一次 CSV 回退访问（骨架态；真实接入后改为标注真实数据源）。"""
        if self._audit is not None:
            self._audit.trace(source="U9C_CSV回退", action=action)

    # ── DataConnector 接口实现（骨架：CSV 回退）────────────────────────────

    def get_bom(self) -> list[BomRow]:
        """获取 BOM 物料清单。

        TODO 7/1 MCP：POST {webapi_url} EntityFullName=UFIDA.U9.BM.BOM.BOM
        （ReturnFields: ItemMaster.Code / BOMComponents.* / Level，Filter DocStatus=生效）
        """
        self._trace_fallback("get_bom")
        return self._fallback.get_bom()

    def get_inventory(self) -> list[InventoryRow]:
        """获取实时库存快照。

        TODO 7/1 MCP：走专用库存接口 WhQoh.IQueryBinAvailableQty（参数结构异于通用查询）。
        """
        self._trace_fallback("get_inventory")
        return self._fallback.get_inventory()

    def get_purchase_orders(self) -> list[PurchaseOrder]:
        """获取在途采购订单。

        TODO 7/1 MCP：两步查询 PurchaseOrder + Receivement（关联 DocNo 查已收量）。
        """
        self._trace_fallback("get_purchase_orders")
        return self._fallback.get_purchase_orders()

    def get_production_plan(self) -> list[ProductionPlan]:
        """获取生产工单/生产计划。

        TODO 7/1 MCP：POST {webapi_url} EntityFullName=UFIDA.U9.MO.MO.MO（Filter 下达/执行中）。
        """
        self._trace_fallback("get_production_plan")
        return self._fallback.get_production_plan()

    def get_suppliers(self) -> list[Supplier]:
        """获取供应商价格表。

        TODO 7/1 MCP：走采购价格接口 IQueryPurPriceListSRV（字段见 U9C API 字段映射表）。
        """
        self._trace_fallback("get_suppliers")
        return self._fallback.get_suppliers()

    def __repr__(self) -> str:
        return (
            f"U9CConnector(base_url={self.base_url!r}, "
            f"ent_code={self.ent_code!r}, org_code={self.org_code!r}, "
            f"status='Phase skeleton — CSV fallback active, 待 7/1 MCP')"
        )
