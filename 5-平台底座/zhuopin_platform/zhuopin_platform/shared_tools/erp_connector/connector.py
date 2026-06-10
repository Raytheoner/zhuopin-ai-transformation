"""ZpConnector — 卓品定制 REST API 连接器（收割自 supplychain src/data/zp_connector.py）。

基于公司自建 zp API（公网 https://testerp.equalitytec.com:4445/zp）。
认证：POST /U9C/webapi/OAuth2/AuthLogin → JWT token → Header: token: <jwt>
数据：POST /zp/api/ZpViewXxx/Query，响应 {"code":200,"data":[...]}
BOM：POST /U9C/webapi/BOM/Query。

收割改造：
  · import 改指向平台 models / connector / csv_connector。
  · PO 磁盘缓存改到包内 cache/ 目录（已 gitignore），可经 po_cache_file 注入（测试用 tmp）。
  · 注入 ConnectorAudit（D2 轻量痕迹，source=zp_ERP）+ 可选 DebugLog；凭据 env 注入。
"""
from __future__ import annotations

import http.client
import json
import os
import ssl
import threading
import time
import urllib.parse
import urllib.request
import urllib.error
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, field_validator, ValidationError
from typing import Optional as _Opt

from ..connector import DataConnector
from ..connector_audit import ConnectorAudit, DebugLog
from ..connector_errors import ConnectorValidationError
from ..secrets import EnvSecretsProvider, SecretsProvider
from ..models import (
    BomRow,
    InventoryRow,
    ProductionPlan,
    PurchaseOrder,
    Supplier,
)

class _ZpPurOrderRow(BaseModel):
    """zp API ZpViewPurOrder 行（Pydantic 边界校验）。"""
    erpNo:    _Opt[str] = None
    itemCode: str                 # 必填；None → 抛 ValidationError
    qty:      _Opt[float] = 0
    rcvQtyTU: _Opt[float] = 0
    makeDate: _Opt[str] = ""
    supplyCode: _Opt[str] = ""

    @field_validator("itemCode", mode="before")
    @classmethod
    def _require_item_code(cls, v):
        if v is None or str(v).strip() == "":
            raise ValueError("itemCode 不能为 None 或空")
        return str(v)

    @field_validator("qty", "rcvQtyTU", mode="before")
    @classmethod
    def _coerce_float(cls, v):
        try:
            return float(v or 0)
        except (ValueError, TypeError):
            return 0.0


# HTTPS 自签名证书忽略
_CTX = ssl.create_default_context()
_CTX.check_hostname = False
_CTX.verify_mode = ssl.CERT_NONE

# Token 有效期：接近失效前 10 分钟刷新
_TOKEN_TTL_MINUTES = 230

# PO 磁盘缓存默认路径（包内 cache/，已 gitignore）
_DEFAULT_PO_CACHE_FILE = Path(__file__).resolve().parent / "cache" / "po_cache.json"
_PO_DISK_CACHE_TTL = 4 * 3600  # 4 小时


class ZpConnector(DataConnector):
    """卓品 zp API 的 DataConnector 实现（真实 ERP：PO/物料/BOM）。

    Args:
        base_url:       完整应用根 URL，如 https://testerp.equalitytec.com:4445
        user_code:      U9C 用户名
        ent_code:       企业编码，如 "001"
        org_code:       组织编码，如 "Z"
        client_id:      API 客户端 ID
        client_secret:  API 客户端密钥
        fallback_dir:   CSV 回退目录（生产计划等暂无接口的数据）
        po_cache_file:  PO 磁盘缓存路径（默认包内 cache/po_cache.json）
        po_cache_ttl:   PO 磁盘缓存有效期（秒，默认 4 小时）
        audit:          ConnectorAudit 轻量痕迹记录器（None 则不留痕）
        debug:          DebugLog 可选 req/resp 全文（默认 None，不落盘）
    """

    def __init__(
        self,
        base_url:      str,
        user_code:     str,
        ent_code:      str,
        org_code:      str,
        client_id:     str,
        client_secret: str,
        fallback_dir:  Path | str | None = None,
        po_cache_file: Path | str | None = None,
        po_cache_ttl:  int = _PO_DISK_CACHE_TTL,
        audit:         ConnectorAudit | None = None,
        debug:         DebugLog | None = None,
    ):
        self._base = base_url.rstrip("/")
        self._user_code     = user_code
        self._ent_code      = ent_code
        self._org_code      = org_code
        self._client_id     = client_id
        self._client_secret = client_secret
        self._po_cache_file = Path(po_cache_file) if po_cache_file else _DEFAULT_PO_CACHE_FILE
        self._po_cache_ttl  = po_cache_ttl
        self._audit = audit
        self._debug = debug

        # Token 缓存（带锁，多线程安全）
        self._token: Optional[str] = None
        self._token_expires: Optional[datetime] = None
        self._token_lock = threading.Lock()

        # PO 内存缓存（同次运行内有效）
        self._pos_cache: dict[int, list] = {}
        self._pos_cache_ts: dict[int, float] = {}

        # CSV 回退（生产计划等暂无 API 的数据）
        # High5：把审计实例一并传入 fallback，保证回退路径（get_production_plan / get_bom
        # 无产品数据时）也留轻量痕迹，不脱离 IATF 留痕范围。
        from ..csv_connector import CSVConnector
        self._fallback = CSVConnector(fallback_dir, audit=audit)

    @classmethod
    def from_env(cls, audit: ConnectorAudit | None = None,
                 debug: DebugLog | None = None,
                 secrets: SecretsProvider | None = None) -> "ZpConnector":
        """从 SecretsProvider 构造（默认降级 EnvSecretsProvider，向后兼容）。"""
        sp = secrets if secrets is not None else EnvSecretsProvider()
        keys = ["U9C_API_BASE", "U9C_USER_CODE", "U9C_ENT_CODE",
                "U9C_ORG_CODE", "U9C_CLIENT_ID", "U9C_CLIENT_SECRET"]
        missing = []
        for k in keys:
            try:
                sp.get(k)
            except KeyError:
                missing.append(k)
        if missing:
            raise ValueError(f"ZpConnector.from_env(): 缺少凭证 {missing}")
        return cls(
            base_url=      sp.get("U9C_API_BASE"),
            user_code=     sp.get("U9C_USER_CODE"),
            ent_code=      sp.get("U9C_ENT_CODE"),
            org_code=      sp.get("U9C_ORG_CODE"),
            client_id=     sp.get("U9C_CLIENT_ID"),
            client_secret= sp.get("U9C_CLIENT_SECRET"),
            audit=audit, debug=debug,
        )

    # ── 认证 ─────────────────────────────────────────────────────────────

    def _get_token(self) -> str:
        """获取 JWT token，自动缓存和刷新（多线程安全）。"""
        with self._token_lock:
            now = datetime.now()
            if self._token and self._token_expires and now < self._token_expires:
                return self._token

            params = urllib.parse.urlencode({
                "userCode":     self._user_code,
                "entcode":      self._ent_code,
                "orgcode":      self._org_code,
                "clientid":     self._client_id,
                "clientsecret": self._client_secret,
                "loginDate":    f"{now.year}.{now.month}.{now.day}",
            })
            url = f"{self._base}/U9C/webapi/OAuth2/AuthLogin?{params}"
            resp = self._http_get(url)
            if not resp.get("Success"):
                raise RuntimeError(f"U9C 认证失败: {resp.get('ResMsg', resp)}")
            token = resp.get("Data") or resp.get("data")
            if not token:
                raise RuntimeError(f"认证响应中未找到 token: {resp}")
            self._token = token
            self._token_expires = now + timedelta(minutes=_TOKEN_TTL_MINUTES)
            return self._token

    # ── HTTP 工具 ─────────────────────────────────────────────────────────

    def _http_get(self, url: str) -> dict:
        req = urllib.request.Request(url, headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=15, context=_CTX) as r:
            return json.loads(r.read().decode("utf-8"))

    _MAX_RETRIES = 3   # SSL/网络抖动重试
    _RETRY_WAIT  = 1.5

    def _zp_post(self, path: str, body: dict | None = None) -> list[dict]:
        """POST 到 zp API，返回 data 列表。URLError 自动重试。

        每次调用写轻量访问痕迹（source=zp_ERP）+ 可选 req/resp 全文 debug。
        """
        last_exc: Exception | None = None
        for attempt in range(1, self._MAX_RETRIES + 1):
            token = self._get_token()
            url = f"{self._base}/zp{path}"
            data = json.dumps(body or {}, ensure_ascii=False).encode("utf-8")
            req = urllib.request.Request(url, data=data, headers={
                "Content-Type": "application/json",
                "token": token,
            }, method="POST")
            resp: dict = {}
            try:
                with urllib.request.urlopen(req, timeout=300, context=_CTX) as r:
                    resp = json.loads(r.read().decode("utf-8"))
                if resp.get("code") not in (200, None) and not resp.get("data"):
                    raise RuntimeError(f"zp API 错误: code={resp.get('code')} msg={resp.get('msg')}")
                return resp.get("data") or []
            except urllib.error.HTTPError as e:
                raise RuntimeError(f"zp API HTTP {e.code}: {path}") from e
            except (urllib.error.URLError, http.client.IncompleteRead) as exc:
                last_exc = exc
                if attempt < self._MAX_RETRIES:
                    time.sleep(self._RETRY_WAIT)
            finally:
                if self._audit is not None:
                    self._audit.trace(source="zp_ERP", action=path)
                if self._debug is not None:
                    self._debug.record(req={"path": path, "body": body}, resp=resp)
        raise last_exc

    def _u9c_bom_post(self, body: list) -> list[dict]:
        """POST 到 U9C BOM 专用端点。"""
        token = self._get_token()
        url = f"{self._base}/U9C/webapi/BOM/Query"
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers={
            "Content-Type": "application/json",
            "token": token,
        }, method="POST")
        resp: dict = {}
        try:
            with urllib.request.urlopen(req, timeout=15, context=_CTX) as r:
                resp = json.loads(r.read().decode("utf-8"))
            if not resp.get("Success"):
                raise RuntimeError(f"BOM Query 失败: {resp.get('ResMsg', '')}")
            result = resp.get("Data", [])
            return result if isinstance(result, list) else [result]
        finally:
            if self._audit is not None:
                self._audit.trace(source="zp_ERP", action="/U9C/webapi/BOM/Query")
            if self._debug is not None:
                self._debug.record(req={"path": "/U9C/webapi/BOM/Query", "body": body}, resp=resp)

    # ── DataConnector 接口实现 ────────────────────────────────────────────

    _POS_MEM_CACHE_TTL = 300  # 内存缓存 5 分钟

    def get_purchase_orders(self, days: int = 60) -> list[PurchaseOrder]:
        """从 ZpViewPurOrder 获取近期有效采购订单（两级缓存：内存 5 分钟 + 磁盘 4 小时）。

        字段映射：po_id←erpNo, material_id←itemCode, qty_ordered←qty,
        qty_received←rcvQtyTU, expected_date←deliveryDate(降级 makeDate),
        supplier_id←supplyCode, status←收/订量推断。
        """
        # 1. 内存缓存
        if (days in self._pos_cache
                and time.time() - self._pos_cache_ts.get(days, 0) < self._POS_MEM_CACHE_TTL):
            return self._pos_cache[days]

        # 2. 磁盘缓存（跨进程共享，4 小时有效）
        cache_file = self._po_cache_file
        cache_file.parent.mkdir(parents=True, exist_ok=True)
        if cache_file.exists():
            cache_age = time.time() - cache_file.stat().st_mtime
            if cache_age < self._po_cache_ttl:
                try:
                    cached = json.loads(cache_file.read_text(encoding="utf-8"))
                    if cached.get("days") == days:
                        result = [PurchaseOrder(**r) for r in cached["rows"]]
                        self._pos_cache[days] = result
                        self._pos_cache_ts[days] = time.time()
                        return result
                except Exception:
                    pass  # 缓存损坏则重新下载

        # 3. 从 API 下载
        cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
        rows = self._zp_post("/api/ZpViewPurOrder/Query")
        rows = [r for r in rows if (r.get("makeDate") or "")[:10] >= cutoff]

        result = []
        for r in rows:
            try:
                validated = _ZpPurOrderRow.model_validate(r)
            except ValidationError as e:
                first_err = e.errors()[0]
                raise ConnectorValidationError(
                    source="zp_ERP",
                    field=str(first_err.get("loc", ("itemCode",))[0]),
                    raw=r,
                ) from e
            qty_ordered  = validated.qty or 0.0
            qty_received = validated.rcvQtyTU or 0.0
            if qty_received >= qty_ordered and qty_ordered > 0:
                status = "received"
            elif qty_received > 0:
                status = "partial"
            else:
                status = "in_transit"
            make_date = (validated.makeDate or "")[:10]
            delivery_raw = (
                r.get("deliveryDate")
                or r.get("DeliveryDate")
                or r.get("expectDate")
                or r.get("planDate")
                or make_date
            )
            expected_date = (delivery_raw or make_date)[:10]
            result.append(PurchaseOrder(
                po_id=                  str(validated.erpNo or r.get("id", "")),
                material_id=            validated.itemCode,
                qty_ordered=            int(qty_ordered),
                qty_received=           int(qty_received),
                expected_date=          expected_date,
                supplier_confirmed_date=expected_date,
                supplier_id=            validated.supplyCode or "",
                status=                 status,
            ))

        # 写磁盘缓存
        try:
            cache_data = {"days": days, "timestamp": time.time(),
                          "rows": [r.__dict__ for r in result]}
            cache_file.write_text(
                json.dumps(cache_data, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception:
            pass  # 写缓存失败非致命

        self._pos_cache[days] = result
        self._pos_cache_ts[days] = time.time()
        return result

    def get_inventory(self) -> list[InventoryRow]:
        """从 ZpViewItemMaster 获取物料列表作为库存快照基础。

        注意：zp API 暂无库存余量端点，current/safety 暂为 0，待接 U9C WhQoh。
        """
        rows = self._zp_post("/api/ZpViewItemMaster/Query")
        result = []
        for r in rows:
            result.append(InventoryRow(
                material_id=   str(r.get("itemCode") or ""),
                material_name= str(r.get("itemName") or ""),
                current_stock= 0,
                safety_stock=  0,
                unit=          str(r.get("unitName") or ""),
                last_updated=  (r.get("editDate") or r.get("makeDate") or "")[:10],
            ))
        return result

    _BOM_MAX_WORKERS = 5

    def get_bom_for_products(self, product_ids: list[str], max_depth: int = 1) -> list[BomRow]:
        """从 U9C BOM/Query 并行获取指定产品的子件 BOM（默认只查直接子件）。"""
        rows: list[BomRow] = []
        rows_lock    = threading.Lock()
        queried: set[str] = set()
        queried_lock = threading.Lock()

        def _fetch(code: str, depth: int) -> None:
            with queried_lock:
                if code in queried or depth > max_depth:
                    return
                queried.add(code)
            try:
                bom_data = self._u9c_bom_post(
                    [{"Org": {"Code": self._org_code}, "ItemMaster": {"Code": code}}]
                )
            except Exception:
                return
            if not bom_data:
                return
            bom_item = bom_data[0]
            new_rows: list[BomRow] = []
            child_codes: list[str] = []
            for comp in bom_item.get("m_bOMComponents", []):
                child_master = comp.get("m_itemMaster") or {}
                child_code   = str(child_master.get("m_code") or "")
                child_name   = str(child_master.get("m_name") or "")
                issue_uom    = comp.get("m_issueUOM") or {}
                if not child_code:
                    continue
                new_rows.append(BomRow(
                    product_id=    code,
                    component_id=  child_code,
                    component_name=child_name,
                    level=         depth,
                    qty_per_unit=  float(comp.get("m_usageQty") or 0),
                    loss_rate=     float(comp.get("m_scrap") or 0),
                    unit=          str(issue_uom.get("m_code") or issue_uom.get("m_name") or ""),
                ))
                child_codes.append(child_code)
            with rows_lock:
                rows.extend(new_rows)
            if depth < max_depth:
                for child in child_codes:
                    _fetch(child, depth + 1)

        with ThreadPoolExecutor(max_workers=self._BOM_MAX_WORKERS) as executor:
            futures = [executor.submit(_fetch, pid, 1) for pid in product_ids]
            for f in as_completed(futures):
                f.result()
        return rows

    def get_bom(self) -> list[BomRow]:
        """从 U9C BOM/Query 获取 BOM；产品码不在 ERP 时回退 CSV mock。"""
        plans = self.get_production_plan()
        product_ids = list({p.product_id for p in plans})
        if product_ids:
            real_rows = self.get_bom_for_products(product_ids)
            if real_rows:
                return real_rows
        return self._fallback.get_bom()

    def get_production_plan(self) -> list[ProductionPlan]:
        """生产计划：zp API 暂无对应端点，回退 CSV mock。"""
        return self._fallback.get_production_plan()

    def get_suppliers(self) -> list[Supplier]:
        """供应商价格：从 ZpViewPurOrder 聚合（MOQ/MPQ/lead_time 暂用默认值）。"""
        rows = self._zp_post("/api/ZpViewPurOrder/Query")
        seen: dict[tuple, Supplier] = {}
        for r in rows:
            key = (str(r.get("supplyCode") or ""), str(r.get("itemCode") or ""))
            if key[0] and key[1]:
                price = float(r.get("finallyPriceTC") or 0)
                if key not in seen or price > 0:
                    seen[key] = Supplier(
                        supplier_id=   key[0],
                        material_id=   key[1],
                        unit_price=    price,
                        moq=           1,
                        mpq=           1,
                        lead_time_days=30,
                        is_approved=   True,
                    )
        return list(seen.values())

    def __repr__(self) -> str:
        return (f"ZpConnector(base={self._base!r}, "
                f"ent={self._ent_code!r}, org={self._org_code!r})")
