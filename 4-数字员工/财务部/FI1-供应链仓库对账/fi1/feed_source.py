"""数据接入层（design D3）—— 三源统一接口：mock / csv 应急桥接 / u9c 直读。

投料/产出由 `data_source` 切 loader，**切源不改对账引擎/门禁逻辑**：
  · mock：贴 U9C 实体 schema 的夹具（单测/回归）。
  · csv ：ERP 定期导出投料/产出 CSV（过渡期真实路径，已授权）；Pydantic 边界校验。
  · u9c ：U9C MO(FinishedQty)/领料(MOPickList) via CommonEntity/Query；端点 404 → fail-loud。
BOM 始终复用平台 ZpConnector（已验证），消费 (rows, failed_ids)，残缺不静默通过。
"""
from __future__ import annotations

import csv
from pathlib import Path
from typing import Optional as _Opt

from pydantic import BaseModel, field_validator

from zhuopin_platform.shared_tools.connector_errors import RealEndpointNotReadyError

from . import config as _config
from .models import MaterialFeed, ProductionOutput


# ── Pydantic 边界校验（脏数据挡在接入层）─────────────────────────────────────

class _OutputRow(BaseModel):
    product_id: str
    product_name: _Opt[str] = ""
    finished_qty: float
    period: _Opt[str] = ""

    @field_validator("product_id", mode="before")
    @classmethod
    def _require_pid(cls, v):
        if v is None or str(v).strip() == "":
            raise ValueError("product_id 不能为空")
        return str(v).strip()

    @field_validator("finished_qty", mode="before")
    @classmethod
    def _coerce_qty(cls, v):
        if v is None or str(v).strip() == "":
            raise ValueError("finished_qty 不能为空")
        return float(v)


class _FeedRow(BaseModel):
    component_id: str
    component_name: _Opt[str] = ""
    actual_qty: float
    unit: _Opt[str] = ""
    period: _Opt[str] = ""

    @field_validator("component_id", mode="before")
    @classmethod
    def _require_cid(cls, v):
        if v is None or str(v).strip() == "":
            raise ValueError("component_id 不能为空")
        return str(v).strip()

    @field_validator("actual_qty", mode="before")
    @classmethod
    def _coerce_qty(cls, v):
        if v is None or str(v).strip() == "":
            raise ValueError("actual_qty 不能为空")
        return float(v)


def _read_csv(path: Path | str) -> list[dict]:
    with open(path, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def parse_outputs(rows: list[dict]) -> list[ProductionOutput]:
    """原始行 → ProductionOutput（Pydantic 边界校验，脏数据显式报错）。"""
    out: list[ProductionOutput] = []
    for raw in rows:
        try:
            r = _OutputRow.model_validate(raw)
        except Exception as e:
            raise ValueError(f"FI1 产出行校验失败: {e}") from None
        out.append(ProductionOutput(r.product_id, r.product_name or "", r.finished_qty, r.period or ""))
    return out


def parse_feeds(rows: list[dict]) -> list[MaterialFeed]:
    """原始行 → MaterialFeed（Pydantic 边界校验，脏数据显式报错）。"""
    out: list[MaterialFeed] = []
    for raw in rows:
        try:
            r = _FeedRow.model_validate(raw)
        except Exception as e:
            raise ValueError(f"FI1 投料行校验失败: {e}") from None
        out.append(MaterialFeed(r.component_id, r.component_name or "", r.actual_qty, r.unit or "", r.period or ""))
    return out


class FeedSource:
    """投料/产出/BOM 统一加载器。

    Args:
        data_source: "mock" | "csv" | "u9c"（None → config.DATA_SOURCE_DEFAULT）。
        mock_dir:    mock 夹具目录（含 outputs.csv/feeds.csv/bom.csv）。
        csv_dir:     ERP 导出 CSV 目录（应急桥接，含 outputs.csv/feeds.csv）。
        bom_connector: 注入 ZpConnector（测试用 fake）；None 时 csv/u9c 走 from_env，mock 读夹具。
        audit:       ConnectorAudit（连接器访问留痕）。
    """

    def __init__(self, data_source: str | None = None, *, mock_dir: Path | str | None = None,
                 csv_dir: Path | str | None = None, bom_connector=None, audit=None, cfg=_config):
        self.data_source = (data_source or cfg.DATA_SOURCE_DEFAULT).strip().lower()
        self.mock_dir = Path(mock_dir) if mock_dir else None
        self.csv_dir = Path(csv_dir) if csv_dir else None
        self.bom_connector = bom_connector
        self.audit = audit
        self.cfg = cfg

    # ── 产出 / 投料 ──────────────────────────────────────────────────────
    def load_outputs(self) -> list[ProductionOutput]:
        if self.data_source == "mock":
            return parse_outputs(_read_csv(self.mock_dir / "outputs.csv"))
        if self.data_source == "csv":
            return parse_outputs(_read_csv(self.csv_dir / "outputs.csv"))
        if self.data_source == "u9c":
            raise RealEndpointNotReadyError("load_outputs", self.cfg.U9C_MO_NOT_READY)
        raise ValueError(f"未知 data_source: {self.data_source}")

    def load_feeds(self) -> list[MaterialFeed]:
        if self.data_source == "mock":
            return parse_feeds(_read_csv(self.mock_dir / "feeds.csv"))
        if self.data_source == "csv":
            return parse_feeds(_read_csv(self.csv_dir / "feeds.csv"))
        if self.data_source == "u9c":
            raise RealEndpointNotReadyError("load_feeds", self.cfg.U9C_MO_NOT_READY)
        raise ValueError(f"未知 data_source: {self.data_source}")

    # ── BOM（始终复用 ZpConnector；mock 读夹具）─────────────────────────────
    def load_bom(self, product_ids: list[str], *, max_depth: int = 1) -> tuple[list, list[str]]:
        """返回 (bom_rows, failed_product_ids)。残缺由调用方据 failed 列表标待人工核。"""
        if self.bom_connector is not None:
            return self.bom_connector.get_bom_for_products(list(dict.fromkeys(product_ids)), max_depth=max_depth)
        if self.data_source == "mock":
            return self._load_bom_mock(product_ids), []
        # csv / u9c：BOM 是已开放的真实端点，走平台 ZpConnector
        from zhuopin_platform.shared_tools.erp_connector.connector import ZpConnector
        zp = ZpConnector.from_env(audit=self.audit)
        return zp.get_bom_for_products(list(dict.fromkeys(product_ids)), max_depth=max_depth)

    def _load_bom_mock(self, product_ids: list[str]) -> list:
        from zhuopin_platform.shared_tools.models import BomRow
        wanted = set(product_ids)
        rows: list = []
        for raw in _read_csv(self.mock_dir / "bom.csv"):
            if raw["product_id"].strip() not in wanted:
                continue
            rows.append(BomRow(
                product_id=raw["product_id"].strip(),
                component_id=raw["component_id"].strip(),
                component_name=raw.get("component_name", "").strip(),
                level=int(raw.get("level", 1) or 1),
                qty_per_unit=float(raw["qty_per_unit"]),
                loss_rate=float(raw.get("loss_rate", 0) or 0),
                unit=raw.get("unit", "").strip(),
            ))
        return rows
