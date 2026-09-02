#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""按料号统计采购提前期中位数（队列 §一 #403 子项 ⑵ / §四 #125 拍板 D-2(b)）。

口径（🔴 先读这段，数字的意义全在这里）
────────────────────────────────────────────────────────────────────
本脚本算的是「**供应商实际交付周期**」＝ 采购订单行的**单据日期**（`Purchase/Query.
BusinessDate`）到该行**首次实际入库日**（`GR/Query.BusinessDate`）的自然日天数。

⚠️ **它不等于 ERP 里的「采购提前期」（`PurProcessLT`）**，也不等于教科书意义上的
「采购提前期」：
  · 它**含**供应商响应波动、排产、运输、我方收货过账的全部延迟；
  · 它**不含**我方内部的请购→下单审批段（那段在 PO 制单之前，本数据看不到）；
  · 它是**已发生的历史事实**，不是承诺值。
陈承已两次（2026-07-15、2026-08-24）答复 ERP `PurProcessLT` 字段不准确、不要取，
我方接受并另寻来源——本脚本即那个来源。

🔴 **本脚本只回答「这个数是多少、怎么算的」，不替换任何生产参数。**
`connector.py:1133` 的 `lead_time_days=30` 硬编码**由本脚本原样保留、不动**；
替换它属于改口径（🟡 档），须先经 Shao Peishen 拍板。

数据卫生（每一条都会在输出的漏斗表里给出被剔除的行数，不静默丢弃）
────────────────────────────────────────────────────────────────────
H1  GR 行 `SrcDocNo` 为空 ⇒ 剔除（无采购单来源，接不上制单日）
H2a GR 行 `RcvQtyTU` < 0 ⇒ 剔除（退货/红字冲销）
H2b GR 行 `RcvQtyTU` = 0 ⇒ 剔除（零入库，无实物到货）
H3  PO 行 `ConfirmQty` <= 0 ⇒ 剔除（红字/作废采购行）
    🔴 **实测 H2a 与 H3 均匹配 0 行**——这两个端点里不出现负数量/红字行。故
    「退货已剔除」只能说成「**红字行未在数据中出现**」，且两端点均无单据类型字段
    可识别独立退货单 ⇒ 若退货走独立单据类型，本统计看不到也剔不掉。详见报告 §四。
H4  一单多次分批入库 ⇒ **只取首次到货**（同一 PO 行按 `BusinessDate` 取最小值）。
    口径选择理由：SC7 的 `calc_order_date` 问的是「最迟什么时候下单，货能开始到」，
    对应的是**首批到货**；取末次会把分批交付的尾巴算成提前期，系统性偏长。
    ⇒ 用 `--arrival last` 可切到末次口径做敏感性对照。
H5  提前期为负 ⇒ 剔除（入库日早于制单日，数据错误，另行计数报出）
H6  样本量 < `--min-samples`（默认 5）的料号 ⇒ **不出中位数**，标「样本不足」

🔴 JOIN 字面一致性先验（`verify_join` 阶段，失败即 fail-loud 中止）
────────────────────────────────────────────────────────────────────
财务域已有先例教训：join 字段字面不一致会**静默落空且不报错**——两边都跑成功、
结果是空的或只剩零头，而报表看上去完全正常。故本脚本在聚合前强制做一次
命中率体检：`GR.(SrcDocNo, SrcDocLineNo)` → `Purchase.(DocNo, DocLineNo)`，
命中率低于 `_MIN_JOIN_HIT_RATE` 即中止并打印两侧单号形状分布，**不出数**。

用法
────────────────────────────────────────────────────────────────────
    python leadtime_median.py                  # 默认：近 24 个月，min-samples=5
    python leadtime_median.py --months 0       # 全历史
    python leadtime_median.py --arrival last   # 末次到货口径（敏感性对照）
    python leadtime_median.py --refresh        # 忽略磁盘缓存，重新拉取
    python leadtime_median.py --out ../reports/leadtime.md

只读：全程仅 GET `Purchase/Query` 与 `GR/Query`，不写任何 ERP 数据。
"""
from __future__ import annotations

import argparse
import json
import os
import re
import ssl
import statistics
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path

# ── 端点常量（与 `zhuopin_platform.shared_tools.erp_connector.connector` 同源）──
_PURCHASE_PATH = "/zp/api/Purchase/Query"
_GR_PATH = "/zp/api/GR/Query"

#: 服务端分页硬顶——实测传 1000 仍只返回 500（两个端点一致）。
_PAGE_SIZE = 500

#: 传输层瞬时失败重试次数。该端点会随机在 TLS 握手/读取中途断连
#: （`SSL: UNEXPECTED_EOF_WHILE_READING`），重打一次即恢复 ⇒ 瞬时故障。
#: 整表拉取要打约 114 次请求，单次 5% 失败率下不重试几乎必然被打穿。
_TRANSPORT_RETRIES = 6
_RETRY_BACKOFF_SEC = 0.5

#: 整表缓存有效期（秒）。整表拉取较重（约 5.6 万行），与 SC2 的收货缓存同为 4 小时。
_CACHE_TTL = 4 * 3600

#: JOIN 命中率下限。低于此值判为「join 字面不一致导致静默落空」，fail-loud 中止。
#: 取 0.30 而非更高：GR 表里本就有约 16% 的行 `SrcDocNo` 为空（非采购来源的入库），
#: 以及 `PO*`/`SF*` 等其它单据类型前缀，正常命中率不会接近 1。
_MIN_JOIN_HIT_RATE = 0.30

#: 中位数所需最小样本量。取 5 的理由：n<5 时四分位数 P25/P75 退化（几乎由单个
#: 观测决定），中位数本身也易被一次异常交付整体拉偏；n>=5 时中位数至少需要
#: 3 个观测同向移动才会改变，对个别异常单具备抗性。
_DEFAULT_MIN_SAMPLES = 5


# ══════════════════════════════════════════════════════════════════
# 取数层
# ══════════════════════════════════════════════════════════════════

def _load_env() -> dict[str, str]:
    """读仓库根 `.env`（不覆盖已存在的进程环境变量）。"""
    env: dict[str, str] = {}
    here = Path(__file__).resolve()
    for parent in here.parents:
        f = parent / ".env"
        if f.exists():
            text = f.read_text(encoding="utf-8")
            for m in re.finditer(r"^([A-Z0-9_]+)\s*=\s*(.*)$", text, re.M):
                env[m.group(1)] = m.group(2).strip()
            break
    for k in ("STOCK_API_BASE", "STOCK_API_KEY"):
        if os.environ.get(k):
            env[k] = os.environ[k]
    return env


class ErpReader:
    """`Purchase/Query` / `GR/Query` 只读整表拉取器（带磁盘缓存）。"""

    def __init__(self, env: dict[str, str], cache_dir: Path, refresh: bool = False):
        base = (env.get("STOCK_API_BASE") or "").rstrip("/")
        key = env.get("STOCK_API_KEY") or ""
        if not base or not key:
            raise SystemExit(
                "❌ 未配置 STOCK_API_BASE / STOCK_API_KEY —— 财务三单查询与库存查询同一凭据，"
                "请检查仓库根 `.env`。")
        self._base, self._key = base, key
        self._cache_dir = cache_dir
        self._refresh = refresh
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        self._ctx = ssl.create_default_context()
        self._ctx.check_hostname = False
        self._ctx.verify_mode = ssl.CERT_NONE

    def _request(self, path: str, params: dict) -> dict:
        qs = urllib.parse.urlencode({"apiKey": self._key, **params})
        url = f"{self._base}{path}?{qs}"
        safe = f"{self._base}{path}?{urllib.parse.urlencode(params)}"   # 脱敏，仅报错用
        for attempt in range(1, _TRANSPORT_RETRIES + 1):
            try:
                req = urllib.request.Request(url, headers={"Accept": "application/json"})
                with urllib.request.urlopen(req, timeout=60, context=self._ctx) as r:
                    body = json.loads(r.read().decode("utf-8"))
                break
            except urllib.error.HTTPError as e:
                raise SystemExit(f"❌ ERP 查询 HTTP {e.code}: {safe}") from None
            except Exception:
                if attempt >= _TRANSPORT_RETRIES:
                    # 🔴 重试用尽即原样失败：不返回空集、不返回部分数据。
                    # 部分数据会让中位数看上去正常而实际建立在半张表上。
                    raise SystemExit(
                        f"❌ ERP 查询不可达（已重试 {attempt} 次）: {safe}") from None
                time.sleep(_RETRY_BACKOFF_SEC * attempt)
        if not body.get("Success"):
            raise SystemExit(f"❌ ERP 查询业务错误: {safe} :: {body.get('ResMsg')}")
        return body

    def fetch_all(self, path: str, label: str) -> list[dict]:
        """整表分页拉取。

        🔴 **必须整表取回、在客户端过滤**：该端点的服务端过滤不可信——2026-08-18 SC2
        实测 `startDate`/`endDate`/`businessDate`/`beginDate` 以及一个**故意拼错的
        参数名**，五者返回的 `Total` 全部等于无过滤基线，即「静默返回全表」。
        """
        cache_file = self._cache_dir / f"{label}_all.json"
        if not self._refresh and cache_file.exists() \
                and time.time() - cache_file.stat().st_mtime < _CACHE_TTL:
            try:
                rows = json.loads(cache_file.read_text(encoding="utf-8"))
                print(f"  · {label}: {len(rows):,} 行（磁盘缓存）")
                return rows
            except Exception:
                pass    # 缓存损坏则重新下载

        all_rows: list[dict] = []
        page = 1
        total = None
        while True:
            body = self._request(path, {"page": page, "pageSize": _PAGE_SIZE})
            data = body.get("Data") or {}
            rows = data.get("Rows") or []
            all_rows.extend(rows)
            total = data.get("Total", len(all_rows))
            print(f"\r  · {label}: {len(all_rows):,}/{total:,} 行", end="", flush=True)
            if not rows or len(all_rows) >= total:
                break
            page += 1
        print()
        if total is not None and len(all_rows) < total:
            raise SystemExit(
                f"❌ {label} 拉取不完整：取到 {len(all_rows)} 行，服务端声称 {total} 行")
        try:
            cache_file.write_text(json.dumps(all_rows, ensure_ascii=False), encoding="utf-8")
        except Exception:
            pass    # 写缓存失败非致命
        return all_rows


# ══════════════════════════════════════════════════════════════════
# 规整与 JOIN
# ══════════════════════════════════════════════════════════════════

def _norm_doc(v) -> str:
    """单号规整：去空白。**刻意不做大小写折叠、不去前后缀**——
    真实数据里 `ZPCG20220628001W` 的 `W` 是有意义的后缀，折叠会把两张不同的单合并。"""
    return str(v or "").strip()


def _norm_line(v) -> str:
    """行号规整：数值型统一成十进制整数字符串，避免 `10` / `10.0` / `'10'` 三态不相等。"""
    s = str(v if v is not None else "").strip()
    if not s:
        return ""
    try:
        return str(int(float(s)))
    except (TypeError, ValueError):
        return s


def _parse_date(v) -> date | None:
    s = str(v or "")[:10]
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except ValueError:
        return None


def _shape(doc_no: str) -> str:
    """单号形状指纹（数字折成 `#`），用于 join 体检时肉眼比对两侧字面。"""
    return re.sub(r"\d", "#", doc_no) or "<空>"


def verify_join(po_rows: list[dict], gr_rows: list[dict]) -> dict:
    """🔴 JOIN 字面一致性先验体检——命中率过低即 fail-loud 中止，不出数。

    成因：财务域先例——join 字段字面不一致时两边都跑成功、结果静默落空，
    而下游报表看上去完全正常。故此处宁可中止，也不出一个「看着对」的中位数。
    """
    po_keys = {(_norm_doc(r.get("DocNo")), _norm_line(r.get("DocLineNo"))) for r in po_rows}
    linked = [r for r in gr_rows if _norm_doc(r.get("SrcDocNo"))]
    hit = sum(1 for r in linked
              if (_norm_doc(r.get("SrcDocNo")), _norm_line(r.get("SrcDocLineNo"))) in po_keys)
    rate = hit / len(linked) if linked else 0.0

    print(f"\n【JOIN 体检】GR 有来源单号的行 {len(linked):,} 条，"
          f"命中 Purchase 行 {hit:,} 条 ⇒ 命中率 {rate:.1%}")
    if rate < _MIN_JOIN_HIT_RATE:
        print("\n❌ JOIN 命中率低于下限 "
              f"{_MIN_JOIN_HIT_RATE:.0%}，判为字面不一致导致静默落空，**中止出数**。")
        print("\n  Purchase.DocNo 形状 TOP10：")
        for s, c in Counter(_shape(_norm_doc(r.get("DocNo"))) for r in po_rows).most_common(10):
            print(f"    {s:<24} x{c:,}")
        print("\n  GR.SrcDocNo 形状 TOP10：")
        for s, c in Counter(_shape(_norm_doc(r.get("SrcDocNo"))) for r in gr_rows).most_common(10):
            print(f"    {s:<24} x{c:,}")
        raise SystemExit(1)

    # 命中率达标也要把「谁没命中」报出来——沉默的缺口同样会歪结论。
    miss_shapes = Counter(_shape(_norm_doc(r.get("SrcDocNo"))) for r in linked
                          if (_norm_doc(r.get("SrcDocNo")),
                              _norm_line(r.get("SrcDocLineNo"))) not in po_keys)
    return {"linked": len(linked), "hit": hit, "rate": rate,
            "miss_shapes": miss_shapes.most_common(10)}


# ══════════════════════════════════════════════════════════════════
# 统计
# ══════════════════════════════════════════════════════════════════

def compute(po_rows: list[dict], gr_rows: list[dict], *,
            months: int, arrival: str, min_samples: int) -> dict:
    """返回 {funnel, per_material, join_info, window}。"""
    funnel: dict[str, int] = {}

    # ── PO 侧：建 (DocNo, DocLineNo) → {制单日, 料号, 供应商} 索引 ────────
    funnel["PO 行 · 原始"] = len(po_rows)
    po_idx: dict[tuple[str, str], dict] = {}
    po_drop_qty = po_drop_date = 0
    for r in po_rows:
        qty = r.get("ConfirmQty")
        if qty is None or float(qty) <= 0:          # H3 红字/作废采购行
            po_drop_qty += 1
            continue
        d = _parse_date(r.get("BusinessDate"))
        if d is None:
            po_drop_date += 1
            continue
        key = (_norm_doc(r.get("DocNo")), _norm_line(r.get("DocLineNo")))
        if not key[0] or not key[1]:
            continue
        # 同键重复行取最早制单日（真实数据里同一 DocNo/DocLineNo 会重复出现）
        prev = po_idx.get(key)
        if prev is None or d < prev["order_date"]:
            po_idx[key] = {"order_date": d,
                           "item_code": _norm_doc(r.get("ItemCode")),
                           "item_name": str(r.get("ItemName") or ""),
                           "supplier": str(r.get("SupplierName") or "")}
    funnel["PO 行 · H3 剔除 ConfirmQty<=0（红字/作废）"] = po_drop_qty
    funnel["PO 行 · 剔除无效制单日"] = po_drop_date
    funnel["PO 行 · 去重后可用采购行"] = len(po_idx)

    # ── GR 侧：逐行过滤 ─────────────────────────────────────────────
    funnel["GR 行 · 原始"] = len(gr_rows)
    gr_drop_nosrc = gr_drop_neg = gr_drop_zero = gr_drop_date = gr_drop_nojoin = 0
    # (DocNo, LineNo) → 该 PO 行的全部有效入库日
    arrivals: dict[tuple[str, str], list[date]] = defaultdict(list)
    for r in gr_rows:
        src = _norm_doc(r.get("SrcDocNo"))
        if not src:                                  # H1 无采购单来源
            gr_drop_nosrc += 1
            continue
        qty = r.get("RcvQtyTU")
        if qty is None or float(qty) < 0:            # H2a 退货/红字冲销
            gr_drop_neg += 1
            continue
        if float(qty) == 0:                          # H2b 零入库（无实物到货）
            gr_drop_zero += 1
            continue
        d = _parse_date(r.get("BusinessDate"))
        if d is None:
            gr_drop_date += 1
            continue
        key = (src, _norm_line(r.get("SrcDocLineNo")))
        if key not in po_idx:                        # 接不上采购行
            gr_drop_nojoin += 1
            continue
        arrivals[key].append(d)
    funnel["GR 行 · H1 剔除无来源单号"] = gr_drop_nosrc
    # 🔴 H2a 与 H2b 分开计数是刻意的：合成一个 `<=0` 会让「退货已剔除」看上去成立，
    # 而实测 H2a 恒为 0 —— 这两个端点里根本不出现负数量行（详见报告「口径边界」节）。
    funnel["GR 行 · H2a 剔除 RcvQtyTU<0（退货/红字冲销）"] = gr_drop_neg
    funnel["GR 行 · H2b 剔除 RcvQtyTU=0（零入库，无实物到货）"] = gr_drop_zero
    funnel["GR 行 · 剔除无效入库日"] = gr_drop_date
    funnel["GR 行 · 剔除接不上采购行"] = gr_drop_nojoin
    funnel["GR 行 · 有效入库行"] = sum(len(v) for v in arrivals.values())

    # ── H4 一单多次分批入库 → 取首次（或末次）───────────────────────
    pick = min if arrival == "first" else max
    multi = sum(1 for v in arrivals.values() if len(v) > 1)
    funnel[f"采购行 · 收到货的行（H4 按「{'首次' if arrival == 'first' else '末次'}到货」取 1 次）"] \
        = len(arrivals)
    funnel["采购行 · 其中分多次入库的行"] = multi

    # ── 提前期计算 ──────────────────────────────────────────────────
    cutoff = None
    if months > 0:
        cutoff = date.today() - timedelta(days=int(months * 30.44))
    neg = 0
    out_of_window = 0
    per_material: dict[str, dict] = defaultdict(
        lambda: {"days": [], "item_name": "", "suppliers": set()})
    for key, dates in arrivals.items():
        po = po_idx[key]
        recv = pick(dates)
        days = (recv - po["order_date"]).days
        if days < 0:                                 # H5 入库早于制单，数据错误
            neg += 1
            continue
        # 窗口按**制单日**归属：问的是「那段时间下的单，交付要多久」
        if cutoff and po["order_date"] < cutoff:
            out_of_window += 1
            continue
        m = per_material[po["item_code"]]
        m["days"].append(days)
        m["item_name"] = m["item_name"] or po["item_name"]
        if po["supplier"]:
            m["suppliers"].add(po["supplier"])
    funnel["采购行 · H5 剔除提前期为负（入库早于制单）"] = neg
    if cutoff:
        funnel[f"采购行 · 剔除窗口外（制单日 < {cutoff}）"] = out_of_window
    funnel["采购行 · 进入统计"] = sum(len(m["days"]) for m in per_material.values())

    # ── 按料号聚合 ──────────────────────────────────────────────────
    results = []
    for code, m in per_material.items():
        ds = sorted(m["days"])
        n = len(ds)
        row = {"item_code": code, "item_name": m["item_name"], "n": n,
               "suppliers": len(m["suppliers"]),
               "enough": n >= min_samples}
        if row["enough"]:
            row["median"] = statistics.median(ds)
            # 用「最近秩」分位数：样本量小时不做插值，避免造出数据里没有的天数
            row["p25"] = ds[max(0, int(round(0.25 * (n - 1))))]
            row["p75"] = ds[max(0, int(round(0.75 * (n - 1))))]
            row["min"], row["max"] = ds[0], ds[-1]
        results.append(row)
    results.sort(key=lambda r: (-r["n"], r["item_code"]))

    return {"funnel": funnel, "results": results,
            "window": {"months": months, "cutoff": str(cutoff) if cutoff else "全历史"},
            "arrival": arrival, "min_samples": min_samples}


# ══════════════════════════════════════════════════════════════════
# 报告
# ══════════════════════════════════════════════════════════════════

def render(res: dict, join_info: dict, generated: str) -> str:
    enough = [r for r in res["results"] if r["enough"]]
    short = [r for r in res["results"] if not r["enough"]]
    meds = sorted(r["median"] for r in enough)

    L = []
    A = L.append
    A(f"# 采购提前期中位数统计（按料号）")
    A("")
    A(f"> 生成时间：{generated}（本地 / UTC+8）　·　队列 §一 #403 子项 ⑵ ／ §四 #125 拍板 D-2(b)")
    A(f"> 数据源：U9C `Purchase/Query` ＋ `GR/Query`（**只读查询**，未写任何 ERP 数据）")
    A("")
    A("## 一、这个数是什么（口径）")
    A("")
    A("**提前期 ＝ 采购订单行的单据日期（制单日）→ 该行首次实际入库日，自然日天数。**")
    A("")
    A("🔴 **它不是 ERP 的 `PurProcessLT`，也不是教科书口径的「采购提前期」**：")
    A("")
    A("- **含**：供应商响应波动、排产、运输、我方收货过账延迟；")
    A("- **不含**：我方内部请购 → 下单审批段（发生在 PO 制单之前，本数据看不到）；")
    A("- **是**已发生的历史事实，**不是**供应商承诺值。")
    A("")
    A("陈承已两次（2026-07-15、2026-08-24）答复 ERP `PurProcessLT` 不准确、不要取，"
      "我方接受并另寻来源 —— 本统计即那个来源。")
    A("")
    w = res["window"]
    A(f"- **统计窗口**：{'近 ' + str(w['months']) + ' 个月' if w['months'] else '全历史'}"
      f"（按**制单日**归属，起点 {w['cutoff']}）")
    A(f"- **分批到货口径**：{'首次到货' if res['arrival'] == 'first' else '末次到货'}"
      f"（同一采购行多次入库时只取一次）")
    A(f"- **样本量门槛**：n ≥ {res['min_samples']} 才出中位数，不足者标「样本不足」")
    A("")
    A("## 二、结论")
    A("")
    A(f"- 出数料号：**{len(enough):,}** 个（样本量达标）")
    A(f"- 样本不足料号：**{len(short):,}** 个（已标注，不出中位数）")
    if meds:
        A(f"- 这些料号的**中位数本身**的分布：最小 {meds[0]} 天 ／ "
          f"P25 {meds[max(0, int(round(0.25 * (len(meds) - 1))))]} 天 ／ "
          f"**中位 {statistics.median(meds):.0f} 天** ／ "
          f"P75 {meds[max(0, int(round(0.75 * (len(meds) - 1))))]} 天 ／ "
          f"最大 {meds[-1]} 天")
        lo = sum(1 for m in meds if m <= 15)
        hi = sum(1 for m in meds if m > 45)
        A("")
        A(f"🔑 **对写死的 30 天意味着什么**：{lo:,} 个料号（{lo / len(meds):.0%}）中位数 ≤ 15 天，"
          f"{hi:,} 个料号（{hi / len(meds):.0%}）中位数 > 45 天。"
          f"**一律按 30 天，对前者过度提前、对后者严重滞后**——而「最迟下单日」"
          f"（`SC7-库存优化建议/sc7_inventory/purchase_engine.py::calc_order_date`）"
          f"正是采购同事拿来排优先级的那一列。")
    A("")
    if res.get("compare"):
        A("### 口径敏感性（同一份数据，换口径重算）")
        A("")
        A("| 口径 | 出数料号 | 样本不足 | 料号中位数的**中位** | 最小 | 最大 |")
        A("|---|---:|---:|---:|---:|---:|")
        for c in res["compare"]:
            mark = " ←本报告" if c["primary"] else ""
            A(f"| {c['label']}{mark} | {c['n_enough']:,} | {c['n_short']:,} | "
              f"**{c['median_of_medians']:.0f} 天** | {c['lo']} | {c['hi']} |")
        A("")
        A("🔑 **这张表本身就是一个结论**：「提前期中位数是多少」**没有唯一答案**，"
          "20～36 天的差别全部来自口径选择（首次 vs 末次到货、近 24 个月 vs 全历史），"
          "而不是来自数据质量。**因此下游若要用这个数，必须连口径一起用，不能只搬数字。**")
        A("")
    A("🔴 **本报告只交「这个数是多少、怎么算的」，未替换任何生产参数。**")
    A("`5-平台底座/.../erp_connector/connector.py:1133` 的 `lead_time_days=30` "
      "**原样保留、未动**——替换属改口径（🟡 档），须先经 Shao Peishen 拍板。")
    A("")
    A("## 三、数据卫生漏斗（每一步剔除多少行，均不静默丢弃）")
    A("")
    A("| 步骤 | 行数 |")
    A("|---|---:|")
    for k, v in res["funnel"].items():
        A(f"| {k} | {v:,} |")
    A("")
    A("### JOIN 字面一致性体检")
    A("")
    A(f"`GR.(SrcDocNo, SrcDocLineNo)` → `Purchase.(DocNo, DocLineNo)`，"
      f"命中 **{join_info['hit']:,} / {join_info['linked']:,} ＝ {join_info['rate']:.1%}**"
      f"（下限 {_MIN_JOIN_HIT_RATE:.0%}，低于即中止出数）。")
    A("")
    A("⚠️ **为什么专门做这一步**：财务域先例——join 字段字面不一致时两边都跑成功、"
      "结果静默落空，而下游报表看上去完全正常。实测两侧单号确有多种字面形状"
      "（`ZPCG*` 为主，另有 `PO*`／`DLJS*`／`SF*`／纯数字等），**未命中的形状分布**：")
    A("")
    if join_info["miss_shapes"]:
        A("| GR.SrcDocNo 形状 | 未命中行数 |")
        A("|---|---:|")
        for s, c in join_info["miss_shapes"]:
            A(f"| `{s}` | {c:,} |")
    else:
        A("（无未命中）")
    A("")
    A("## 四、🔴 口径边界与已知未覆盖（读数前必看）")
    A("")
    neg_n = res["funnel"].get("GR 行 · H2a 剔除 RcvQtyTU<0（退货/红字冲销）", 0)
    h3_n = res["funnel"].get("PO 行 · H3 剔除 ConfirmQty<=0（红字/作废）", 0)
    A("**1. 「已剔除退货/红字单」这句话，只能说一半——实测这两个端点里根本不出现红字行。**")
    A("")
    A(f"- `GR/Query` 全表 {res['funnel']['GR 行 · 原始']:,} 行中，"
      f"`RcvQtyTU` **< 0 的行数 ＝ {neg_n}**（实测最小值为 0，无负数）；")
    A(f"- `Purchase/Query` 全表 {res['funnel']['PO 行 · 原始']:,} 行中，"
      f"`ConfirmQty` **≤ 0 的行数 ＝ {h3_n}**（实测最小值 0.5，无 None、无负数）。")
    A("")
    A("⇒ **H2a 与 H3 两道过滤器都在位、但都匹配到 0 行**。因此正确的表述是"
      "「**红字/退货行未在数据中出现**」，**不是**「已把退货剔干净了」。")
    A("")
    A("⚠️ **这构成一个真实的口径缺口**：这两个端点的字段里**没有单据类型/状态字段**"
      "可用来识别退货单（GR 行只有 `RcvDocNo`／`SrcDocNo`／`ItemCode`／`RcvQtyTU`／"
      "`BusinessDate`／`SupplierName`／`FinalPriceTC` 等）。若公司的退货走**独立的退货单据"
      "类型**而不是负数量冲销，则那些退货**根本不在本次拉取的两张表里**，"
      "本统计既看不到、也无从剔除。**这一点无法从我方现有端点自证，需要 IT 或采购确认。**")
    A("")
    A("**2. 分批到货只取首次，是一个选择、不是唯一正确答案。**")
    A(f"本次 {res['funnel'].get('采购行 · 其中分多次入库的行', 0):,} 个采购行分多次入库"
      f"（占收到货行的 "
      f"{res['funnel'].get('采购行 · 其中分多次入库的行', 0) / max(1, res['funnel'].get('采购行 · 收到货的行（H4 按「首次到货」取 1 次）', res['funnel'].get('采购行 · 收到货的行（H4 按「末次到货」取 1 次）', 1))):.1%}）。"
      "取首次 ＝ 「货开始到」，取末次 ＝ 「这一行交齐」，两者对分批交付的料号差别很大。"
      "用 `--arrival last` 可跑末次口径做敏感性对照。")
    A("")
    A("**3. 窗口按制单日归属，且近期下单、尚未到货的行不在样本内。**")
    A("一张 3 个月前下的、至今未到货的长周期料 PO，**不会**进入统计（它还没有入库日）。"
      "⇒ **对长周期料，本统计存在系统性低估**（幸存者偏差：只有已到货的才被看见）。"
      "料号越长周期、窗口越短，这个偏差越大。")
    A("")
    A("**4. 这是「料号 × 全部供应商」的合并中位数。**")
    A("同一料号若有多家供应商（明细表末列给出供应商家数），交付周期可能差异很大，"
      "合并中位数会把它们抹平。若要按供应商分档，需另跑一版。")
    A("")
    A("## 五、按料号明细（样本量达标）")
    A("")
    A("| 料号 | 品名 | 样本量 n | **中位数（天）** | P25 | P75 | 最小 | 最大 | 供应商数 |")
    A("|---|---|---:|---:|---:|---:|---:|---:|---:|")
    for r in enough:
        A(f"| `{r['item_code']}` | {r['item_name'][:28]} | {r['n']} | "
          f"**{r['median']:.0f}** | {r['p25']} | {r['p75']} | {r['min']} | {r['max']} | "
          f"{r['suppliers']} |")
    A("")
    A(f"## 六、样本不足料号（n < {res['min_samples']}，不出中位数）")
    A("")
    A(f"共 **{len(short):,}** 个。**刻意不出中位数**：n<5 时 P25/P75 退化（几乎由单个观测决定），"
      "中位数本身也易被一次异常交付整体拉偏。")
    A("")
    A("<details><summary>展开清单</summary>")
    A("")
    A("| 料号 | 品名 | 样本量 n |")
    A("|---|---|---:|")
    for r in short:
        A(f"| `{r['item_code']}` | {r['item_name'][:28]} | {r['n']} |")
    A("")
    A("</details>")
    A("")
    return "\n".join(L)


def main() -> int:
    ap = argparse.ArgumentParser(description="按料号统计采购提前期中位数（只读）")
    ap.add_argument("--months", type=int, default=24,
                    help="统计窗口月数，按制单日归属；0 ＝ 全历史（默认 24）")
    ap.add_argument("--arrival", choices=("first", "last"), default="first",
                    help="一单多次分批入库时取哪一次（默认 first ＝ 首次到货）")
    ap.add_argument("--min-samples", type=int, default=_DEFAULT_MIN_SAMPLES,
                    help=f"出中位数所需最小样本量（默认 {_DEFAULT_MIN_SAMPLES}）")
    ap.add_argument("--refresh", action="store_true", help="忽略磁盘缓存，重新拉取整表")
    ap.add_argument("--out", type=Path, default=None, help="报告输出路径（.md）")
    ap.add_argument("--json-out", type=Path, default=None, help="附带输出机读 JSON")
    args = ap.parse_args()

    generated = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cache_dir = Path(__file__).resolve().parent.parent / "reports" / "_leadtime_cache"

    print("【取数】U9C 只读整表拉取（服务端过滤不可信，一律客户端过滤）")
    reader = ErpReader(_load_env(), cache_dir, refresh=args.refresh)
    po_rows = reader.fetch_all(_PURCHASE_PATH, "Purchase")
    gr_rows = reader.fetch_all(_GR_PATH, "GR")

    join_info = verify_join(po_rows, gr_rows)

    res = compute(po_rows, gr_rows, months=args.months,
                  arrival=args.arrival, min_samples=args.min_samples)

    # 口径敏感性对照：同一份已在内存的数据，换口径重算（不额外打端点）。
    # 🔴 之所以固定跑这三档：本项唯一的产出是「一个数」，而这个数对口径高度敏感——
    # 只给一个数而不给它的口径带宽，读者会把它当成客观事实搬走。
    res["compare"] = []
    for label, months, arrival in (
            ("首次到货 · 近 24 个月", 24, "first"),
            ("末次到货 · 近 24 个月", 24, "last"),
            ("首次到货 · 全历史", 0, "first")):
        r = res if (months == args.months and arrival == args.arrival) else \
            compute(po_rows, gr_rows, months=months, arrival=arrival,
                    min_samples=args.min_samples)
        en = [x for x in r["results"] if x["enough"]]
        if not en:
            continue
        ms = sorted(x["median"] for x in en)
        res["compare"].append({
            "label": label, "primary": r is res,
            "n_enough": len(en), "n_short": len(r["results"]) - len(en),
            "median_of_medians": statistics.median(ms), "lo": ms[0], "hi": ms[-1]})

    print("\n【漏斗】")
    for k, v in res["funnel"].items():
        print(f"  {k:<52} {v:>8,}")

    enough = [r for r in res["results"] if r["enough"]]
    print(f"\n【结论】出数料号 {len(enough):,} 个，"
          f"样本不足 {len(res['results']) - len(enough):,} 个")
    if enough:
        meds = sorted(r["median"] for r in enough)
        print(f"  料号中位数的中位数 ＝ {statistics.median(meds):.0f} 天"
              f"（min {meds[0]} / max {meds[-1]}）")

    report = render(res, join_info, generated)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(report, encoding="utf-8")
        print(f"\n✅ 报告已写入 {args.out}")
    else:
        print("\n" + report)

    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        payload = {"generated": generated, "join": {k: v for k, v in join_info.items()
                                                    if k != "miss_shapes"},
                   "funnel": res["funnel"], "window": res["window"],
                   "arrival": res["arrival"], "min_samples": res["min_samples"],
                   "results": [{k: v for k, v in r.items()} for r in res["results"]]}
        args.json_out.write_text(json.dumps(payload, ensure_ascii=False, indent=2),
                                 encoding="utf-8")
        print(f"✅ 机读 JSON 已写入 {args.json_out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
