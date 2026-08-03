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
import warnings
import urllib.parse
import urllib.request
import urllib.error
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, field_validator, ValidationError
from typing import Optional as _Opt

from ..connector import DataConnector
from ..connector_audit import ConnectorAudit, DebugLog
from ..connector_errors import (
    ConnectorValidationError,
    InsecureTLSError,
    RealEndpointNotReadyError,
)
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
    erpLineNo: _Opt[int] = None   # 行号，供跨端点 JOIN Purchase/Query 的 DocLineNo（队列 #173）
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


# TLS（A1 / 审计报告 §2.4 P0）：默认开启证书+主机名校验（与 srm_connector 一致）。
# 逃生开关 U9C_TLS_INSECURE=1 仅在 mock/LAN 应急时关闭校验（warn + audit 留痕）；
# real（对客权威）模式禁用逃生开关，强制证书校验。可选 U9C_TLS_CAFILE 做证书 pin。
def _build_ssl_context(data_source: str, audit: "ConnectorAudit | None") -> ssl.SSLContext:
    ctx = ssl.create_default_context()
    cafile = os.environ.get("U9C_TLS_CAFILE", "").strip()
    if cafile:
        ctx.load_verify_locations(cafile)   # 证书 pin（可选，IT 提供受信证书后启用）
    insecure = os.environ.get("U9C_TLS_INSECURE", "").strip().lower() in ("1", "true", "yes")
    if insecure:
        if data_source == "real":
            raise InsecureTLSError()         # 对客权威路径绝不允许裸信道
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        warnings.warn(
            "U9C_TLS_INSECURE=1：TLS 证书校验已关闭（仅限 mock/LAN 应急），生产/对客禁用",
            UserWarning, stacklevel=2,
        )
        if audit is not None:
            audit.trace(source="TLS_INSECURE", action="ssl_context_insecure")
    return ctx


# Token 有效期：接近失效前 10 分钟刷新
_TOKEN_TTL_MINUTES = 230

# PO 磁盘缓存默认路径（包内 cache/，已 gitignore）
_DEFAULT_PO_CACHE_FILE = Path(__file__).resolve().parent / "cache" / "po_cache.json"
_PO_DISK_CACHE_TTL = 4 * 3600  # 4 小时

# 齐套"可用现货"只计入这 6 个仓（Paul 2026-07-05 定，见 7-外部文档/U9C库存取数-侦察结果与推荐-2026-07-05.md）：
#   WW01 委外仓 / ZP01 物料仓 / ZP21 半成品库 / ZP22 委外半成品库 / ZP02 成品库 / ZP23 委外成品库。
# 其余仓（不良品仓、委外线边仓等）一律排除，不计入可投产现货。
ALLOWED_STOCK_WAREHOUSES = ("WW01", "ZP01", "ZP21", "ZP22", "ZP02", "ZP23")


class _StockRow(BaseModel):
    """`/zp/api/Stock/Query` 返回行（StockRowDTO）边界校验。"""
    ItemCode:     str
    ItemName:     _Opt[str] = ""
    WhName:       _Opt[str] = ""
    SupplierName: _Opt[str] = ""
    ProjectCode:  _Opt[str] = ""
    StoreQty:     _Opt[float] = 0    # 现存量
    AvailQty:     _Opt[float] = 0    # 可用量（ERP 服务端已净预留）

    @field_validator("ItemCode", mode="before")
    @classmethod
    def _require_item_code(cls, v):
        if v is None or str(v).strip() == "":
            raise ValueError("ItemCode 不能为空")
        return str(v)

    @field_validator("StoreQty", "AvailQty", mode="before")
    @classmethod
    def _coerce_qty(cls, v):
        try:
            return float(v or 0)
        except (ValueError, TypeError):
            return 0.0


class ZpConnector(DataConnector):
    """U9C / ERP **唯一规范连接器**（u9c-connector-convergence）。

    一套 ERP（U9C）的两个 API 面，本类统一前置：
      · U9C 标准 webapi `/U9C/webapi/*`：OAuth2 鉴权（`AuthLogin`→JWT→header `token`）、
        BOM（`/U9C/webapi/BOM/Query`，审计来源 `U9C_webapi`）。
      · 卓品自建 REST `/zp/api/ZpViewXxx/Query`：PO/物料/供应商（审计来源 `zp_ERP`）。
    （已退役重复的 `U9CConnector` 骨架；BOM 单一来源 = `get_bom_for_products`。）

    **base 约定（关键）**：`base_url` 为 **host-only**（如 `https://erp.equalitytec.com:4443`），
    本类内部自拼 `/U9C` 与 `/zp`。带 `/U9C` 后缀会变 `/U9C/U9C/...` 而 404。鉴权 = OAuth2
    (client_id/secret)，**不需要 admin 密码**。

    **数据源开关（U9C_DATA_SOURCE，design D2 / Q3）**：
      · `mock`（默认）：无真实端点的方法（生产计划）走 CSV 回退、审计 `CSV`。
      · `real`：无真实端点的方法 **fail-loud**（抛 `RealEndpointNotReadyError`，绝不静默回退 mock）；
        仅当显式 `allow_mock_fallback` 才回退 CSV，且审计标 `CSV_mock`、结果非权威、禁入对客/L2。

    Args:
        base_url:       host-only 应用根 URL（不含 /U9C），如 https://erp.equalitytec.com:4443
        user_code/ent_code/org_code/client_id/client_secret: OAuth2 凭据（只从 .env/SecretsProvider 注入）
        fallback_dir:   CSV 回退目录（mock 模式 / 无真实端点的数据）
        po_cache_file:  PO 磁盘缓存路径（默认包内 cache/po_cache.json）
        po_cache_ttl:   PO 磁盘缓存有效期（秒，默认 4 小时）
        audit:          ConnectorAudit 轻量痕迹记录器（None 则不留痕）
        debug:          DebugLog 可选 req/resp 全文（默认 None，不落盘）
        data_source:    "mock" | "real"（None → 读 env U9C_DATA_SOURCE，默认 mock）
        allow_mock_fallback: real 模式下显式 opt-in 回退（None → 读 env U9C_ALLOW_MOCK_FALLBACK）
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
        data_source:   str | None = None,
        allow_mock_fallback: bool | None = None,
        srm_connector: object | None = None,
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
        # A1 扩展（shortage-baoguan-criteria-v3）：可选注入 SRM 连接器（如 XkySrmConnector），
        # 用于 get_purchase_orders 按 PO+供应商查真实答交确认日期。None（默认）＝现状行为
        # 不变（supplier_confirmed_date 仍等于 expected_date 占位），零风险。
        self._srm_connector = srm_connector

        # D2 数据源开关（默认 mock，保留现有 CSV 回退行为；real 触发 fail-loud）
        ds = data_source if data_source is not None else os.environ.get("U9C_DATA_SOURCE", "mock")
        self._data_source = ds.strip().lower()
        if allow_mock_fallback is None:
            allow_mock_fallback = os.environ.get("U9C_ALLOW_MOCK_FALLBACK", "").strip().lower() in ("1", "true", "yes")
        self._allow_mock_fallback = bool(allow_mock_fallback)

        # TLS context（A1）：按 data_source + env 计算，默认安全；real 模式禁逃生开关
        self._ctx = _build_ssl_context(self._data_source, audit)

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
        if audit is None:
            warnings.warn(
                "ZpConnector.from_env() 未注入 audit：生产环境连接器访问将不留痕"
                "（IATF 可追溯红线，应注入 ConnectorAudit）",
                UserWarning, stacklevel=2,
            )
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
        with urllib.request.urlopen(req, timeout=15, context=self._ctx) as r:
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
                with urllib.request.urlopen(req, timeout=300, context=self._ctx) as r:
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
            with urllib.request.urlopen(req, timeout=15, context=self._ctx) as r:
                resp = json.loads(r.read().decode("utf-8"))
            if not resp.get("Success"):
                raise RuntimeError(f"BOM Query 失败: {resp.get('ResMsg', '')}")
            result = resp.get("Data", [])
            return result if isinstance(result, list) else [result]
        finally:
            # Q1：BOM 走 U9C 标准 webapi → 审计来源标 U9C_webapi（区别于 zp 视图 zp_ERP）
            if self._audit is not None:
                self._audit.trace(source="U9C_webapi", action="/U9C/webapi/BOM/Query")
            if self._debug is not None:
                self._debug.record(req={"path": "/U9C/webapi/BOM/Query", "body": body}, resp=resp)

    # ── DataConnector 接口实现 ────────────────────────────────────────────

    _POS_MEM_CACHE_TTL = 300  # 内存缓存 5 分钟

    def _overlay_srm_confirmed_dates(self, orders: list[PurchaseOrder]) -> None:
        """按 (po_id, supplier_id) 查真实 SRM 确认日期，覆盖 `supplier_confirmed_date`
        占位值（A1 扩展，shortage-baoguan-criteria-v3，2026-07-10 会议定稿方案B）。

        未注入 `srm_connector`（默认）→ 不做任何事，行为与现状完全一致。
        查询异常/查不到某 PO → 该 PO 保留 `expected_date` 占位，不阻断其它 PO。
        原地修改 `orders` 里各 `PurchaseOrder.supplier_confirmed_date`。
        """
        if self._srm_connector is None or not orders:
            return
        pairs = [(po.po_id, po.supplier_id) for po in orders if po.po_id and po.supplier_id]
        if not pairs:
            return
        try:
            confirmed, _failed = self._srm_connector.get_confirmed_dates(pairs)
        except Exception:
            if self._audit is not None:
                self._audit.trace(source="SRM", action="po_confirmed_date_query_failed")
            return
        for po in orders:
            if po.po_id in confirmed:
                po.supplier_confirmed_date = confirmed[po.po_id]

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
                line_no=                str(validated.erpLineNo) if validated.erpLineNo is not None else "",
            ))

        self._overlay_srm_confirmed_dates(result)

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

    _STOCK_MAX_WORKERS = 8

    def get_inventory(self, material_ids: list[str] | None = None) -> list[InventoryRow]:
        """库存快照。

        · `material_ids` 给定（缺料/齐套用）：经卓品自建 `GET /zp/api/Stock/Query` 取**真实现货**，
          只计白名单仓 `ALLOWED_STOCK_WAREHOUSES`，逐料号并发查询 + 按 ItemCode 精确匹配 + 跨仓聚合。
          `current_stock` = Σ AvailQty(白名单仓可用量，ERP 已净预留)，`safety_stock=0`。
          real 模式缺 STOCK 配置/端点不可用 → fail-loud（不静默回退、不以 0 冒充）。
        · `material_ids=None`（旧接口 / SC3 等）：返回 ZpViewItemMaster 物料清单（**不含真实现货**，
          current/safety=0）。缺料/齐套请传 material_ids 走 Stock API。

        base/apiKey 从 env 注入（`STOCK_API_BASE` / `STOCK_API_KEY`），apiKey 脱敏不入日志/审计。
        """
        if material_ids is None:
            rows = self._zp_post("/api/ZpViewItemMaster/Query")
            return [InventoryRow(
                material_id=   str(r.get("itemCode") or ""),
                material_name= str(r.get("itemName") or ""),
                current_stock= 0, safety_stock= 0,
                unit=          str(r.get("unitName") or ""),
                last_updated=  (r.get("editDate") or r.get("makeDate") or "")[:10],
            ) for r in rows]

        base = os.environ.get("STOCK_API_BASE", "").rstrip("/")
        key  = os.environ.get("STOCK_API_KEY", "")
        if not base or not key:
            if self._data_source == "real":
                raise RealEndpointNotReadyError(
                    "Stock API 未配置（STOCK_API_BASE/STOCK_API_KEY）；real 模式不回退 mock、不以 0 冒充现货"
                )
            return self._fallback.get_inventory()   # mock：CSV 夹具回退

        wh = ",".join(ALLOWED_STOCK_WAREHOUSES)
        today = datetime.now().strftime("%Y-%m-%d")

        def _one(code: str) -> Optional[InventoryRow]:
            rows = self._stock_query(base, key, code, wh)
            exact = [r for r in rows if r.ItemCode == code]   # itemCode 模糊 → 剔他料
            if not exact:
                return None
            avail = sum(r.AvailQty for r in exact)            # 跨白名单仓聚合可用量
            return InventoryRow(
                material_id=code, material_name=exact[0].ItemName or "",
                current_stock=int(round(avail)), safety_stock=0,
                unit="", last_updated=today,
            )

        result: list[InventoryRow] = []
        seen = list(dict.fromkeys(m for m in material_ids if m))   # 去重保序
        with ThreadPoolExecutor(max_workers=self._STOCK_MAX_WORKERS) as ex:
            for fut in as_completed({ex.submit(_one, c) for c in seen}):
                row = fut.result()
                if row is not None:
                    result.append(row)
        if self._audit is not None:                            # 每次取数一条轻量痕迹（不含 apiKey）
            self._audit.trace(source="Stock", action=f"Stock/Query x{len(seen)}")
        return result

    def _stock_query(self, base: str, key: str, item_code: str,
                     wh_codes: str, limit: int = 1000) -> list["_StockRow"]:
        """单料号库存查询；apiKey 走 URL query，报错用不含 apiKey 的 safe_url。"""
        qs = urllib.parse.urlencode(
            {"apiKey": key, "itemCode": item_code, "whCode": wh_codes, "limit": limit})
        url = f"{base}/zp/api/Stock/Query?{qs}"
        safe = f"{base}/zp/api/Stock/Query?itemCode={item_code}"   # 脱敏（无 apiKey），仅报错用
        try:
            req = urllib.request.Request(url, headers={"Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=30, context=self._ctx) as r:
                body = json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            raise RuntimeError(f"Stock API HTTP {e.code}: {safe}") from None
        except (urllib.error.URLError, http.client.IncompleteRead) as e:
            raise RuntimeError(f"Stock API 不可达: {safe}") from None
        if not body.get("Success"):
            raise RuntimeError(f"Stock API 错误: {safe} :: {body.get('ResMsg')}")
        out: list[_StockRow] = []
        for d in (body.get("Data") or {}).get("Rows") or []:
            try:
                out.append(_StockRow(**d))
            except ValidationError:
                continue   # 坏行（缺 ItemCode 等）跳过，不污染聚合
        return out

    # ── 财务三单查询（design D15，队列 #60，FI2/FI3 共用）───────────────────
    # 与 Stock/Query 同一物理服务器、同一凭据（Paul 2026-07-20 确认，复用
    # STOCK_API_BASE/STOCK_API_KEY，不新开环境变量）。

    def _fi_credentials(self) -> tuple[str, str]:
        base = os.environ.get("STOCK_API_BASE", "").rstrip("/")
        key = os.environ.get("STOCK_API_KEY", "")
        if not base or not key:
            raise RealEndpointNotReadyError(
                "财务三单查询 API 未配置（STOCK_API_BASE/STOCK_API_KEY，与库存/预测订单同一凭据）"
            )
        return base, key

    def _fi_request(self, path: str, params: dict) -> dict:
        """单次财务 GET 请求，返回完整响应体（`Success`/`Data.Total`/`Data.Rows`）。
        `params` 不得含 `apiKey`（本方法统一注入），报错信息按 `params` 原样脱敏
        （即不含 apiKey，其余参数如 docNo/supplierCode 非敏感可直接展示）。
        """
        base, key = self._fi_credentials()
        qs = urllib.parse.urlencode({"apiKey": key, **params})
        url = f"{base}{path}?{qs}"
        safe = f"{base}{path}?{urllib.parse.urlencode(params)}"   # 脱敏（无 apiKey），仅报错用
        try:
            req = urllib.request.Request(url, headers={"Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=30, context=self._ctx) as r:
                body = json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            raise RuntimeError(f"财务查询 API HTTP {e.code}: {safe}") from None
        except (urllib.error.URLError, http.client.IncompleteRead) as e:
            raise RuntimeError(f"财务查询 API 不可达: {safe}") from None
        if not body.get("Success"):
            raise RuntimeError(f"财务查询 API 错误: {safe} :: {body.get('ResMsg')}")
        if self._audit is not None:
            self._audit.trace(source="zp_FI", action=f"{path}?{urllib.parse.urlencode(params)}")
        return body

    def _fi_query(self, path: str, doc_no: str) -> list[dict]:
        """财务只读查询公共实现（Purchase/GR/AP Query 共用，信封同 Stock/Query）——`docNo` 单查。"""
        body = self._fi_request(path, {"docNo": doc_no})
        return (body.get("Data") or {}).get("Rows") or []

    _FI_PAGE_SIZE = 200

    def _fi_query_paginated(self, path: str, filters: dict) -> list[dict]:
        """按 `filters`（如 `supplierCode`）分页拉取全部匹配行（design D16，队列 #61
        追加）。`AP/Query` 的 `supplierCode`/`itemCode`/`invoiceNo` 过滤参数此前有
        服务器端 SQL bug（列名映射错误，2026-07-20 发现并跟催 IT，见
        `6-人才与组织/部门AI专员跟进/IT部-陈承-跟进-2026-07-20-*.md`），
        **2026-07-21 复验已由 IT 修复**（队列 #61），本方法据此打开批量取数路径。
        """
        all_rows: list[dict] = []
        page = 1
        while True:
            body = self._fi_request(path, {**filters, "page": page, "pageSize": self._FI_PAGE_SIZE})
            data = body.get("Data") or {}
            rows = data.get("Rows") or []
            all_rows.extend(rows)
            total = data.get("Total", len(all_rows))
            if not rows or len(all_rows) >= total:
                break
            page += 1
        return all_rows

    def get_purchase_lines(self, doc_no: str) -> list[dict]:
        """采购订单明细行（真实源，design D15）——GET `/zp/api/Purchase/Query`。"""
        return self._fi_query("/zp/api/Purchase/Query", doc_no)

    def get_purchase_line_status(self, item_codes: list[str]) -> dict[tuple[str, str], int]:
        """按料号批量查询采购订单行级关闭状态（队列 #173，#139④ 根治，2026-08-03）。

        `ZpViewPurOrder/Query`（`get_purchase_orders` 用的端点）不带行级状态字段
        （2026-08-03 真实探测确认，27,641 行 0 命中 `LineStatus`）；行级状态实际
        暴露在 `Purchase/Query`（与 `get_purchase_lines` 同一端点，IT 2026-07-30
        已补齐 `LineStatus` 字段，取自 `PM_POLine.Status`：0=开立/1=审核中/
        2=已审核未交清/3=自然关闭/4=短缺关闭/5=超额关闭）。复用该端点已支持的
        `itemCode` 批量过滤路径（与 `AP/Query` 的 supplierCode/itemCode 分页取数
        同源，design D16/队列 #61）——按料号逐个查询（服务端每次只接受一个
        itemCode 过滤值，不支持"多料号一次查全部"），返回
        `{(DocNo, str(DocLineNo)): LineStatus}`，供 `sc8.sources.load_purchase_orders_by_material`
        按 `(po_id, line_no)` 与 `ZpViewPurOrder` 数据 JOIN，剔除已关闭行——不受其
        数量口径（`qty_ordered` vs `qty_received`）误判"仍在途"影响（真实案例：
        短缺关闭/超额关闭的行 `qty_received` 常年小于/大于 `qty_ordered`，纯数量
        启发式会一直误判为"partial"/"in_transit"）。

        real fail-loud：任一料号查询异常原样上抛，与 `get_purchase_orders` 同一
        约定，由调用方（`load_purchase_orders_by_material`）决定是否降级。
        """
        out: dict[tuple[str, str], int] = {}
        for code in item_codes:
            rows = self._fi_query_paginated("/zp/api/Purchase/Query", {"itemCode": code})
            for r in rows:
                doc_no = str(r.get("DocNo") or "")
                line_no = str(r.get("DocLineNo") or "")
                status = r.get("LineStatus")
                if doc_no and line_no and status is not None:
                    out[(doc_no, line_no)] = int(status)
        return out

    def get_gr_lines(self, doc_no: str) -> list[dict]:
        """收货单明细行（真实源，design D15）——GET `/zp/api/GR/Query`。"""
        return self._fi_query("/zp/api/GR/Query", doc_no)

    def get_ap_lines(self, doc_no: str) -> list[dict]:
        """应付单明细行（真实源，design D15）——GET `/zp/api/AP/Query`，`docNo` 单查。"""
        return self._fi_query("/zp/api/AP/Query", doc_no)

    def get_ap_lines_by_supplier(
        self,
        supplier_code: str,
        *,
        date_from: str | None = None,
        date_to: str | None = None,
        min_balance: float | None = None,
    ) -> list[dict]:
        """应付单明细行·按供应商批量取数（design D16，队列 #61 追加）——GET
        `/zp/api/AP/Query` 的 `supplierCode` 过滤 + 自动分页，取代"手工给 AP 单号
        清单"的 MVP 限制（该限制源于 D15-a① 记录的服务器端 bug，2026-07-21 已修复）。

        design D17（队列 #70 追加，2026-07-22）：可选窄化条件——`date_from`/
        `date_to`（按立账日期 `AccrueDate` 过滤，服务器端实测确认字段）+
        `min_balance`（按余额下限过滤）。均不传时行为与 D16 原实现完全一致；
        `supplier_code` 仍是必填主键，不做成可选（供应商无关的整期批量取数
        属另一使用场景，本次未实现，见 CLAUDE.md/tasks.md 登记）。
        """
        filters: dict = {"supplierCode": supplier_code}
        if date_from is not None:
            filters["dateFrom"] = date_from
        if date_to is not None:
            filters["dateTo"] = date_to
        if min_balance is not None:
            filters["minBalance"] = min_balance
        return self._fi_query_paginated("/zp/api/AP/Query", filters)

    # ── 附件（发票扫描件，design D18，队列 #78，2026-07-23 首碰真实探测已确认）──
    # 与 Purchase/GR/AP/Stock 不同：List 的信封是 {Data:[...]}（数组，无 Rows 包裹），
    # Download 直接返回原始文件二进制（非 JSON）。均不能复用 _fi_query/_fi_request
    # 的 JSON-Rows 假设，单独实现；凭据仍复用 _fi_credentials（同一 STOCK_API_BASE/KEY）。

    def list_attachments(self, doc_no: str, doc_type: str) -> list[dict]:
        """单据附件列表——GET `/zp/api/Attachment/List`，返回 `Data` 数组原样
        （`[{"ID":..., "Title":"<文件名>", "Size":"<如 63KB>"}, ...]`）。真实探测
        （2026-07-23，8 个真实 AP 单）均恰好 1 个附件，本方法不做消歧义假设，
        原样返回全部条目由调用方决定取哪个。
        """
        body = self._fi_request("/zp/api/Attachment/List", {"docNo": doc_no, "docType": doc_type})
        data = body.get("Data")
        return data if isinstance(data, list) else []

    def download_attachment(self, doc_no: str, doc_type: str) -> bytes:
        """下载单据附件原始二进制——GET `/zp/api/Attachment/Download`。响应非 JSON
        （真实探测确认为 `Content-Type: application/pdf` 的原始文件流），不经
        `_fi_request` 的 JSON 解析路径，单独实现请求 + 错误处理（HTTPError 脱敏同
        `_fi_request`）。单据含多附件时，服务器返回其中一个（真实探测 8 单均恰好
        1 附件，未出现需要按 `ID` 精确指定的场景，见 design D18 Non-Goals）。
        """
        base, key = self._fi_credentials()
        params = {"docNo": doc_no, "docType": doc_type}
        qs = urllib.parse.urlencode({"apiKey": key, **params})
        url = f"{base}/zp/api/Attachment/Download?{qs}"
        safe = f"{base}/zp/api/Attachment/Download?{urllib.parse.urlencode(params)}"
        try:
            req = urllib.request.Request(url, headers={"Accept": "*/*"})
            with urllib.request.urlopen(req, timeout=30, context=self._ctx) as r:
                content = r.read()
        except urllib.error.HTTPError as e:
            raise RuntimeError(f"附件下载 API HTTP {e.code}: {safe}") from None
        except (urllib.error.URLError, http.client.IncompleteRead) as e:
            raise RuntimeError(f"附件下载 API 不可达: {safe}") from None
        if not content:
            raise RuntimeError(f"附件下载 API 返回空内容: {safe}")
        if self._audit is not None:
            self._audit.trace(source="zp_FI", action=f"Attachment/Download?{urllib.parse.urlencode(params)}")
        return content

    _BOM_MAX_WORKERS = 5

    @staticmethod
    def _select_current_bom_version(bom_records: list[dict], today: date) -> dict:
        """从同一母件的多条 BOM 主记录中选出当前生效版本（B3，shortage-baoguan-criteria-v3）。

        版本区间判定：`m_effectiveDate ≤ today < m_disableDate`。区间理论上互不重叠，
        命中第一条即可。全部不满足（数据异常/版本空档期）→ fail-safe 回退取
        `m_disableDate` 最大的一条（近似"最新"），不静默返回空。

        修复现状 bug：原逻辑无条件取 `bom_records[0]`——生产环境实测确认部分母件
        （多版本）的索引 0 恰是已失效的旧版本，会用过期 BOM 算齐套/缺料。
        """
        def _d(v: str | None, fallback: str) -> date:
            return date.fromisoformat((v or fallback)[:10])

        for rec in bom_records:
            if _d(rec.get("m_effectiveDate"), "0001-01-01") <= today < _d(rec.get("m_disableDate"), "9999-12-31"):
                return rec
        return max(bom_records, key=lambda r: _d(r.get("m_disableDate"), "0001-01-01"))

    def get_bom_for_products(
        self, product_ids: list[str], max_depth: int = 1, *, today: date | None = None
    ) -> tuple[list[BomRow], list[str]]:
        """从 U9C BOM/Query 并行获取指定产品的子件 BOM（默认只查直接子件）。

        B1（审计报告 §2.4 P1）：单品查询失败**不再静默吞**——收集失败料号清单。
        B3（shortage-baoguan-criteria-v3）：同一母件返回多条 BOM 版本时，按生效日期
        区间选取当前生效版本，不再无条件取第一条；`today` 供测试注入，缺省=今天。
        Returns:
            (rows, failed_ids)
            部分失败 → 返回已得 rows + failed_ids，并写 bom_partial_failure 审计痕迹；
            **全失败**（有失败且无任何 rows）→ 抛 RuntimeError（带失败明细），
            绝不返回残缺/空 BOM 当成功（否则下游齐套虚低、漏报缺料、威胁对客承诺）。
        """
        today = today or date.today()
        rows: list[BomRow] = []
        rows_lock    = threading.Lock()
        queried: set[str] = set()
        queried_lock = threading.Lock()
        failed: list[str] = []
        failed_lock  = threading.Lock()

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
                with failed_lock:
                    failed.append(code)   # 不静默吞：记入失败清单
                return
            if not bom_data:
                return
            if len(bom_data) == 1:
                bom_item = bom_data[0]
            else:
                bom_item = self._select_current_bom_version(bom_data, today)
                if not any(
                    date.fromisoformat((r.get("m_effectiveDate") or "0001-01-01")[:10]) <= today
                    < date.fromisoformat((r.get("m_disableDate") or "9999-12-31")[:10])
                    for r in bom_data
                ) and self._audit is not None:
                    self._audit.trace(source="U9C_webapi", action="bom_version_fallback", target=code)

            # 响应自证码校验（队列 #66，姚祖怡 07-21 真实试用报"瓶颈子件张冠李戴"/"ERP无此料号"）：
            # BOM/Query 响应体母件行自带 m_itemMaster.m_code，此前从不核对它与本次请求的 code
            # 是否一致——服务端若在任意时点返回错母件数据（并发响应错位/缓存串号等未知成因），
            # 我方会静默信任并挂错子件到错成品上。有值且不符 → 视为该料号拉取失败，绝不静默采用；
            # 响应缺该字段（未知边缘情况）→ 无法校验，维持现状放行，不误伤正常数据。
            returned_code = str((bom_item.get("m_itemMaster") or {}).get("m_code") or "")
            if returned_code and returned_code != code:
                with failed_lock:
                    failed.append(code)
                if self._audit is not None:
                    self._audit.trace(source="U9C_webapi", action="bom_product_code_mismatch",
                                      target=f"{code}!={returned_code}")
                return

            new_rows: list[BomRow] = []
            child_codes: list[str] = []
            for comp in bom_item.get("m_bOMComponents", []):
                child_master = comp.get("m_itemMaster") or {}
                child_code   = str(child_master.get("m_code") or "")
                child_name   = str(child_master.get("m_name") or "")
                issue_uom    = comp.get("m_issueUOM") or {}
                if not child_code:
                    continue
                sequence     = str(comp.get("m_sequence") or "")
                qty_per_unit = float(comp.get("m_usageQty") or 0)
                loss_rate    = float(comp.get("m_scrap") or 0)
                unit         = str(issue_uom.get("m_code") or issue_uom.get("m_name") or "")
                new_rows.append(BomRow(
                    product_id=    code,
                    component_id=  child_code,
                    component_name=child_name,
                    level=         depth,
                    qty_per_unit=  qty_per_unit,
                    loss_rate=     loss_rate,
                    unit=          unit,
                    sequence=      sequence,
                    is_substitute= False,
                ))
                child_codes.append(child_code)
                # C-1（sc8-baoguan-substitute-partial-kit）：替代料嵌套在主件行自己的
                # m_bOMCompSubstituteDTO4CreateSv 子列表里，与主件行共享同一项次（sequence）。
                # 真实数据验证（2026-07-15，生产 BOM/Query 只读实测，7 母件/20 组替代料，
                # 100% 一致）：替代料 DTO 自带 m_usageQty，但恒为 1.0，与主件行真实用量
                # （样本中出现 1/2/3/4/9/10/16 等值）无关——是 ERP 侧的占位值，不是真实替代
                # 用量语义。因此**恒继承主件行的 qty_per_unit/loss_rate，忽略替代料自身
                # m_usageQty/m_scrap**（不采用"有则优先用自己的"）。替代料不参与递归展开
                # （不加入 child_codes）。
                for sub in comp.get("m_bOMCompSubstituteDTO4CreateSv") or []:
                    sub_master = sub.get("m_itemMaster") or {}
                    sub_code   = str(sub_master.get("m_code") or "")
                    if not sub_code:
                        continue
                    new_rows.append(BomRow(
                        product_id=    code,
                        component_id=  sub_code,
                        component_name=str(sub_master.get("m_name") or ""),
                        level=         depth,
                        qty_per_unit=  qty_per_unit,
                        loss_rate=     loss_rate,
                        unit=          unit,
                        sequence=      sequence,
                        is_substitute= True,
                    ))
            with rows_lock:
                rows.extend(new_rows)
            if depth < max_depth:
                for child in child_codes:
                    _fetch(child, depth + 1)

        with ThreadPoolExecutor(max_workers=self._BOM_MAX_WORKERS) as executor:
            futures = [executor.submit(_fetch, pid, 1) for pid in product_ids]
            for f in as_completed(futures):
                f.result()

        if failed:
            if not rows:
                # 全失败：无任何可用 BOM → fail-loud，绝不返回空当成功
                raise RuntimeError(
                    f"BOM 拉取全部失败（{len(failed)} 项）：{failed}"
                )
            # 部分失败：返回已得 + 失败清单，并留痕（下游据失败清单决定是否阻断）
            if self._audit is not None:
                self._audit.trace(source="U9C_webapi", action="bom_partial_failure",
                                  target=",".join(failed))
        return rows, failed

    def get_bom(self) -> list[BomRow]:
        """从 U9C BOM/Query 获取 BOM；真实 BOM 为空时走 fail-loud 闸门（B1）。

        消除原"真实空 → 直接 CSV 回退、审计错标 CSV"旁路：经 `_fallback_or_failloud`，
        real 未 opt-in → fail-loud；opt-in → CSV_mock + warn（非权威、禁入对客/L2）。
        """
        plans = self.get_production_plan()
        product_ids = list({p.product_id for p in plans})
        if product_ids:
            real_rows, _failed = self.get_bom_for_products(product_ids)
            if real_rows:
                return real_rows
        return self._fallback_or_failloud(
            "get_bom", self._fallback.get_bom,
            reason="真实 BOM 为空（产品码不在 U9C 或全部无子件），待核对料号/接通 U9C",
        )

    def _fallback_or_failloud(self, name: str, csv_fn, *, reason: str = ""):
        """无真实端点的方法统一走此闸（design D2 / Q3）。

        · real 模式 + 未 opt-in → fail-loud（抛 RealEndpointNotReadyError，绝不静默回退 mock）。
        · real 模式 + 显式 opt-in → CSV 但审计标 `CSV_mock` + UserWarning（非权威、禁入对客/L2）。
        · mock 模式 → CSV 回退（CSVConnector 自带 source=CSV 痕迹，不重复 trace）。
        """
        if self._data_source == "real" and not self._allow_mock_fallback:
            raise RealEndpointNotReadyError(name, reason)
        if self._data_source == "real":
            if self._audit is not None:
                self._audit.trace(source="CSV_mock", action=name)
            warnings.warn(
                f"{name}: U9C_DATA_SOURCE=real 显式回退 mock（非权威），禁止用于对客/L2 决策",
                UserWarning, stacklevel=3,
            )
        return csv_fn()

    def get_production_plan(self) -> list[ProductionPlan]:
        """生产计划：zp 无对应端点。mock→CSV 回退；real→fail-loud（除非显式 opt-in）。

        TODO（解锁）：U9C MO 实体 `UFIDA.U9.MO.MO.MO`（CommonEntity/Query；外网 404，
        待 IT 外网开放或 LAN/VPN；字段见 `5-平台底座/连接器收敛设计…md` 附录 A）。
        """
        return self._fallback_or_failloud(
            "get_production_plan", self._fallback.get_production_plan,
            reason="zp 无生产计划端点，待 U9C MO（UFIDA.U9.MO.MO.MO）CommonEntity 外网开放或 LAN/VPN",
        )

    def get_suppliers(self) -> list[Supplier]:
        """供应商价格：从 ZpViewPurOrder 聚合（MOQ/MPQ/lead_time 暂用默认值）。

        TODO（解锁）：U9C 专用服务 `UFIDA.U9.ISV.PM.IQueryPurPriceListSRV`（取真实 MOQ/MPQ/
        LeadTime/IsApproved；外网 404，待 IT 外网开放或 LAN/VPN；字段见连接器收敛设计 md 附录 A）。
        在途采购订单的权威口径同理走 `UFIDA.U9.PM.PO.PurchaseOrder` + `Receivement`（见附录 A）。
        """
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
