"""携客云 SRM Connector（只读，收割自 supplychain src/data/xky_srm_connector.py）。

职责：从携客云 OpenAPI 读取供应商承诺交期（vExpectedDate）与供应计划看板。
**只读**——不对 SRM 执行任何写操作。

请求结构（2026-05-19 确认）：POST /purchase/answer.json
  commonParam{appKey, ownerCompanyCode, operateCompanyCode, timestamp(毫秒,不签名),
  timestamps(秒,参与签名), sign} + body{erpCode, ...}
签名：对 appKey/ownerCompanyCode/operateCompanyCode/timestamps 按 key 字典序，values 冒号拼接
+ :appSecret，MD5 小写。

审计（D2 收割改造）：
  · 剥离原 SQLite 自审计（srm_audit.db）。
  · 每次 _post 写**轻量访问痕迹**（ConnectorAudit：source=SRM/动作/PO号/时间），
    与场景层合规 AuditEvent 物理分离；合规决策由场景层负责。
  · req/resp 全文仅在显式开启的 DebugLog 中落盘（默认关、*.debug.log、已 gitignore）。
"""
from __future__ import annotations

import datetime
import hashlib
import json
import os
import time
import urllib.request
import urllib.error
from pathlib import Path

from pydantic import BaseModel, field_validator, ValidationError
from typing import Optional as _Opt

from ..models import SrmDemandOrder, SrmDeliveryOrder
from ..connector_audit import ConnectorAudit, DebugLog
from ..connector_errors import ConnectorValidationError
from ..secrets import EnvSecretsProvider, SecretsProvider


class _SrmAnswerLine(BaseModel):
    """SRM 承诺交期接口 lineList 行（Pydantic 边界校验）。"""
    vExpectedDate: _Opt[int] = None   # 时间戳（秒或毫秒），None 表示无交期

    @field_validator("vExpectedDate", mode="before")
    @classmethod
    def _coerce_timestamp(cls, v):
        if v is None:
            return None
        try:
            return int(v)
        except (ValueError, TypeError):
            raise ValueError(f"vExpectedDate 不是有效时间戳: {v!r}")


import threading as _threading


class _TokenBucket:
    """进程级令牌桶（线程安全，1 token/rate_interval 秒）。

    consume() 若无令牌则阻塞等待至下一令牌可用。
    """

    def __init__(self, rate: float, capacity: float = 1.0) -> None:
        """
        Args:
            rate:     每秒补充令牌数（如 1/30 表示 30 秒一个令牌）
            capacity: 桶容量（最大令牌数）
        """
        self._rate = rate
        self._capacity = capacity
        self._tokens = capacity
        self._last_refill = time.monotonic()
        self._lock = _threading.Lock()

    def consume(self, tokens: float = 1.0) -> None:
        """消耗令牌；不足时阻塞等待。"""
        while True:
            with self._lock:
                now = time.monotonic()
                elapsed = now - self._last_refill
                self._tokens = min(self._capacity,
                                   self._tokens + elapsed * self._rate)
                self._last_refill = now
                if self._tokens >= tokens:
                    self._tokens -= tokens
                    return
                wait = (tokens - self._tokens) / self._rate
            time.sleep(wait)


# 携客云时间戳以 CST(UTC+8) 解析
_CST = datetime.timezone(datetime.timedelta(hours=8))

# 看板文件缓存目录（gitignore 的 cache/ 下）
_CACHE_DIR = Path(__file__).resolve().parent / "cache"


def _ts_to_date(ts) -> str:
    """携客云时间戳（秒或毫秒）转 YYYY-MM-DD 字符串，以 CST(+8) 解析。"""
    ts_int = int(ts)
    if ts_int > 10**10:  # 毫秒级
        ts_int //= 1000
    return datetime.datetime.fromtimestamp(ts_int, tz=_CST).date().isoformat()


class XkySrmConnector:
    """携客云 SRM 只读数据工具。提供承诺交期查询与供应计划看板解析。"""

    # 进程级令牌桶（D3）：key=endpoint path，所有实例共享，尊重携客云 30s 限制
    _buckets: dict[str, _TokenBucket] = {}
    _buckets_lock = _threading.Lock()

    # 900301 退避参数
    _RATE_LIMIT_CODE = "900301"
    _BACKOFF_BASE    = 30    # 秒，指数退避 base
    _BACKOFF_RETRIES = 3

    def _get_bucket(self, path: str) -> _TokenBucket:
        """取（或惰性创建）path 对应的令牌桶。"""
        with XkySrmConnector._buckets_lock:
            if path not in XkySrmConnector._buckets:
                XkySrmConnector._buckets[path] = _TokenBucket(rate=1/30, capacity=1)
            return XkySrmConnector._buckets[path]

    def __init__(
        self,
        api_base: str = "",
        app_key: str = "",
        app_secret: str = "",
        owner_company_code: str = "",
        erp_code: str = "",
        audit: ConnectorAudit | None = None,
        debug: DebugLog | None = None,
    ):
        self.api_base           = api_base or os.environ.get("XKY_API_BASE", "https://openapi.xiekeyun.com")
        self.app_key            = app_key or os.environ.get("XKY_APP_KEY", "")
        self.app_secret         = app_secret or os.environ.get("XKY_APP_SECRET", "")
        self.owner_company_code = owner_company_code or os.environ.get("XKY_OWNER_COMPANY_CODE", "")
        self.erp_code           = erp_code or os.environ.get("XKY_ERP_CODE", "")

        # D2/D5：审计依赖注入。audit=None → 不留痕（测试/离线）；debug=None → 无全文日志。
        self._audit = audit
        self._debug = debug

    @classmethod
    def from_env(cls, audit: ConnectorAudit | None = None,
                 debug: DebugLog | None = None,
                 secrets: SecretsProvider | None = None) -> "XkySrmConnector":
        """从 SecretsProvider 构造（默认降级 EnvSecretsProvider，向后兼容）。

        必需凭证：XKY_APP_KEY / XKY_APP_SECRET / XKY_OWNER_COMPANY_CODE / XKY_ERP_CODE
        """
        if audit is None:
            import warnings
            warnings.warn(
                "XkySrmConnector.from_env() 未注入 audit：生产环境连接器访问将不留痕"
                "（IATF 可追溯红线，应注入 ConnectorAudit）",
                UserWarning, stacklevel=2,
            )
        sp = secrets if secrets is not None else EnvSecretsProvider()
        required = ["XKY_APP_KEY", "XKY_APP_SECRET", "XKY_OWNER_COMPANY_CODE", "XKY_ERP_CODE"]
        missing = []
        for k in required:
            try:
                sp.get(k)
            except KeyError:
                missing.append(k)
        if missing:
            raise ValueError(f"XkySrmConnector.from_env(): 缺少凭证 {missing}")
        return cls(
            app_key=sp.get("XKY_APP_KEY"),
            app_secret=sp.get("XKY_APP_SECRET"),
            owner_company_code=sp.get("XKY_OWNER_COMPANY_CODE"),
            erp_code=sp.get("XKY_ERP_CODE"),
            audit=audit,
            debug=debug,
        )

    # ── 签名与请求 ──────────────────────────────────────────────────────

    _SIGN_FIELDS = {"appKey", "ownerCompanyCode", "operateCompanyCode", "timestamps"}

    def _sign(self, common_params: dict) -> str:
        """对 4 个 commonParam 字段按 key 字典序签名，MD5 小写。"""
        fields = {k: v for k, v in common_params.items() if k in self._SIGN_FIELDS}
        sorted_vals = [str(fields[k]) for k in sorted(fields.keys())]
        sign_str = ":".join(sorted_vals) + ":" + self.app_secret
        return hashlib.md5(sign_str.encode("utf-8")).hexdigest()

    _MAX_RETRIES = 3    # SSL/网络抖动重试次数
    _RETRY_WAIT  = 1.5  # 每次重试前等待秒数

    def _post(self, path: str, body_params: dict) -> dict:
        """发 POST（commonParam + body 嵌套结构），超时 15 秒，SSL 错误自动重试。

        P2 加固：
          - 发请求前消耗进程级令牌桶（1 req/30s per endpoint），尊重携客云限流。
          - 收到 900301 限流错误码时指数退避重试（base 30s，最多 3 次），
            耗尽后抛 RateLimitError。
        """
        from ..connector_errors import RateLimitError

        # 令牌桶限速（D3）：进程级，每 endpoint 共享
        self._get_bucket(path).consume()

        t = time.time()
        common = {
            "appKey":             self.app_key,
            "ownerCompanyCode":   self.owner_company_code,
            "operateCompanyCode": self.owner_company_code,
            "timestamp":          str(int(t * 1000)),
            "timestamps":         str(int(t)),
        }
        common["sign"] = self._sign(common)

        payload = {
            "commonParam": common,
            "body": {"erpCode": self.erp_code, **body_params},
        }
        url = self.api_base.rstrip("/") + path
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        target = str(body_params.get("poErpNo", ""))

        last_exc: Exception | None = None
        for attempt in range(1, self._BACKOFF_RETRIES + 1):
            req = urllib.request.Request(
                url, data=data,
                headers={"Content-Type": "application/json"}, method="POST",
            )
            resp: dict = {}
            error_code = "?"
            try:
                with urllib.request.urlopen(req, timeout=15) as r:
                    resp = json.loads(r.read().decode("utf-8"))
                error_code = str(resp.get("errorCode", resp.get("code", "0")))

                if error_code == self._RATE_LIMIT_CODE:
                    # 900301：指数退避
                    if attempt < self._BACKOFF_RETRIES:
                        wait = self._BACKOFF_BASE * (2 ** (attempt - 1))
                        time.sleep(wait)
                        continue
                    else:
                        raise RateLimitError(source="SRM", attempts=self._BACKOFF_RETRIES)

                return resp

            except urllib.error.URLError as exc:
                last_exc = exc
                error_code = f"SSL_RETRY_{attempt}"
                if attempt < self._MAX_RETRIES:
                    time.sleep(self._RETRY_WAIT)
            finally:
                if self._audit is not None:
                    self._audit.trace(source="SRM", action=path, target=target)
                if self._debug is not None:
                    self._debug.record(req=payload, resp=resp, error=error_code)

        raise last_exc

    # ── 业务方法（只读）──────────────────────────────────────────────────

    def get_confirmed_date(self, po_erp_no: str, inner_vendor_code: str) -> str | None:
        """查询单张采购单的供应商承诺交期。无答交记录返回 None。"""
        resp = self._post("/purchase/answer.json", {
            "poErpNo":         po_erp_no,
            "innerVendorCode": inner_vendor_code,
        })
        raw_code = resp.get("errorCode", resp.get("code"))
        error_code = str(raw_code) if raw_code is not None else "0"
        if error_code in ("0", "200", "None"):
            pass
        elif error_code == "300115":   # 该 PO 在 SRM 无答交记录
            return None
        else:
            raise RuntimeError(
                f"携客云 SRM 返回错误 {error_code}: {resp.get('errorMsg', resp.get('msg', ''))}"
            )

        data = resp.get("data") or {}
        for raw_line in data.get("lineList") or []:
            try:
                line = _SrmAnswerLine.model_validate(raw_line)
            except ValidationError as e:
                first_err = e.errors()[0]
                raise ConnectorValidationError(
                    source="SRM",
                    field=str(first_err.get("loc", ("vExpectedDate",))[0]),
                    raw=raw_line,
                ) from e
            if line.vExpectedDate:
                return _ts_to_date(line.vExpectedDate)
        return None

    def get_confirmed_dates(
        self, po_vendor_pairs: list[tuple[str, str]]
    ) -> tuple[dict[str, str], list[str]]:
        """批量查询承诺交期。区分"查询失败"与"供应商未答交"（B2 / 审计报告 §2.4 P1）。

        Returns:
            (confirmed, failed_pos)
            confirmed:   {po → 承诺交期}（仅含有交期者）
            failed_pos:  查询**异常**的 PO 清单（与"未答交"区分——后者 get_confirmed_date
                         返回 None，是正常业务态，既不在 confirmed 也不在 failed）。
        单 PO 异常不影响其他，但**不再静默吞**：计入 failed_pos + audit error 留痕，
        使在途三色清单不把查询失败误当无延期。
        """
        result: dict[str, str] = {}
        failed_pos: list[str] = []
        for po_erp_no, inner_vendor_code in po_vendor_pairs:
            try:
                date_str = self.get_confirmed_date(po_erp_no, inner_vendor_code)
                if date_str:
                    result[po_erp_no] = date_str
            except Exception:
                failed_pos.append(po_erp_no)
                if self._audit is not None:
                    self._audit.trace(source="SRM", action="confirmed_date_query_failed",
                                      target=po_erp_no)
        return result, failed_pos

    # ── SRM 供应计划看板 ─────────────────────────────────────────────────

    @staticmethod
    def _parse_board_date(val) -> str:
        if val is None:
            return ""
        s = str(val)
        if s.isdigit():
            return _ts_to_date(int(s))
        return s[:10]

    def get_receive_board(self, start_date: str | None = None,
                          end_date: str | None = None) -> list[dict]:
        """查询供应计划看板（receiveBoard/queryList.json），返回原始 dataList。

        内置 90 秒文件缓存（跨子进程复用）；pytest 运行时禁用文件缓存避免污染。
        SRM 限制：同账号 30 秒内不重复、查询范围 ≤ 60 天。
        """
        today = datetime.date.today()
        start = start_date or today.isoformat()
        end   = end_date   or (today + datetime.timedelta(days=60)).isoformat()

        # P2：查询跨度超过 60 天时提前校验，不发必定失败的请求
        try:
            _start_d = datetime.date.fromisoformat(start[:10])
            _end_d   = datetime.date.fromisoformat(end[:10])
            if (_end_d - _start_d).days > 60:
                raise ValueError(
                    f"SRM 查询跨度超过 60 天限制：{start} → {end}"
                    f"（跨度 {(_end_d - _start_d).days} 天）"
                )
        except (ValueError, TypeError) as e:
            if "60" in str(e):
                raise
            pass  # 日期格式错误留给下游报

        cache_file = _CACHE_DIR / "srm_board_cache.json"
        cache_ttl  = 90
        use_file_cache = not os.environ.get("PYTEST_CURRENT_TEST")
        cache_key = (start, end)

        # 1. 内存缓存
        if hasattr(self, "_board_cache"):
            cached_t, cached_key, cached_data = self._board_cache
            if cached_key == cache_key and (time.time() - cached_t) < cache_ttl:
                return cached_data

        # 2. 文件缓存（pytest 时跳过）
        try:
            if use_file_cache and cache_file.exists():
                fc = json.loads(cache_file.read_text(encoding="utf-8"))
                if fc.get("key") == list(cache_key) and (time.time() - fc["ts"]) < cache_ttl:
                    result = fc["data"]
                    self._board_cache = (fc["ts"], cache_key, result)
                    return result
        except Exception:
            pass

        resp = self._post("/receiveBoard/queryList.json", {
            "startDate": start, "endDate": end, "cancelFlag": 0,
        })
        raw_code = resp.get("errorCode", resp.get("code"))
        error_code = str(raw_code) if raw_code is not None else "0"
        if error_code not in ("0", "200", "None"):
            if str(error_code) == "900301":   # 限流，尝试返回过期文件缓存
                try:
                    if use_file_cache and cache_file.exists():
                        fc = json.loads(cache_file.read_text(encoding="utf-8"))
                        if fc.get("key") == list(cache_key):
                            return fc["data"]
                except Exception:
                    pass
                raise RuntimeError("SRM 接口限流（900301），请等待 30 秒后重试")
            raise RuntimeError(f"携客云 SRM 看板查询失败 {error_code}: {resp.get('errorMsg', '')}")

        data = resp.get("data") or {}
        result = (
            resp.get("dataList")
            or (data.get("dataList") if isinstance(data, dict) else data)
            or []
        )
        self._board_cache = (time.time(), cache_key, result)

        try:
            if use_file_cache:
                cache_file.parent.mkdir(parents=True, exist_ok=True)
                cache_file.write_text(
                    json.dumps({"key": list(cache_key), "ts": time.time(), "data": result},
                               ensure_ascii=False),
                    encoding="utf-8",
                )
        except Exception:
            pass

        return result

    def get_demand_orders(self, start_date: str | None = None,
                          end_date: str | None = None) -> list[SrmDemandOrder]:
        """从供应计划看板读取物料需求单（每个 item → 一条 SrmDemandOrder）。"""
        result = []
        for record in self.get_receive_board(start_date, end_date):
            product_code  = str(record.get("productCode") or "")
            material_name = str(
                record.get("productName")
                or record.get("prodFeature")
                or record.get("productFeature")
                or product_code
            )
            for item in (record.get("itemList") or []):
                plan_qty    = int(item.get("planQty")       or 0)
                answer_qty  = int(item.get("answerQty")     or 0)
                deliver_qty = int(item.get("deliveriedQty") or 0)
                board_date  = self._parse_board_date(item.get("boardDate"))
                demand_id   = str(item.get("scheduleBatch") or "") or f"{product_code}_{board_date}"

                po_no = ""
                for po in (item.get("poLineList") or []):
                    # 看板真实字段是 poErpNo（2026-06-18 实测；历史误用 pdrNo→customer_order 恒空，
                    # 待办 #8）。兼容保留 pdrNo 兜底，优先 poErpNo。
                    po_no = str(po.get("poErpNo") or po.get("pdrNo") or "")
                    if po_no:
                        break

                if deliver_qty >= plan_qty > 0:
                    status = "delivered"
                elif answer_qty > 0:
                    status = "ordered"
                else:
                    status = "pending"

                result.append(SrmDemandOrder(
                    demand_id=      demand_id,
                    material_id=    product_code,
                    material_name=  material_name,
                    qty_required=   plan_qty,
                    customer_order= po_no,
                    product_id=     "",
                    required_date=  board_date,
                    status=         status,
                ))
        return result

    def get_delivery_orders(self, start_date: str | None = None,
                            end_date: str | None = None) -> list[SrmDeliveryOrder]:
        """从供应计划看板读取供应商承诺交付记录（仅 answerQty > 0）。"""
        result = []
        for record in self.get_receive_board(start_date, end_date):
            product_code = str(record.get("productCode")     or "")
            vendor_code  = str(record.get("innerVendorCode") or "")
            for item in (record.get("itemList") or []):
                answer_qty = int(item.get("answerQty") or 0)
                if answer_qty <= 0:
                    continue
                deliver_qty = int(item.get("deliveriedQty") or 0)
                board_date  = self._parse_board_date(item.get("boardDate"))
                demand_id   = str(item.get("scheduleBatch") or "") or f"{product_code}_{board_date}"
                status = "delivered" if deliver_qty >= answer_qty else "confirmed"

                result.append(SrmDeliveryOrder(
                    delivery_id=    f"DEL-{demand_id}",
                    demand_id=      demand_id,
                    supplier_id=    vendor_code,
                    material_id=    product_code,
                    qty_committed=  answer_qty,
                    committed_date= board_date,
                    status=         status,
                ))
        return result

    def get_pending_demands(self) -> list[SrmDemandOrder]:
        """读取尚无供应商回复的需求单（status=pending）。"""
        return [d for d in self.get_demand_orders() if d.status == "pending"]

    def get_customer_order_mapping(self) -> dict[str, str]:
        """返回 {需求单号 → 客户订单号} 映射。"""
        return {d.demand_id: d.customer_order for d in self.get_demand_orders()}
