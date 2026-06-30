"""SRM /purchase/answer 承诺交期缓存（design D-incremental，2026-06-30）。

目的：让「⟳ 立即重算」提速。瓶颈是 load_srm_deliveries 对每一对
(采购单 poErpNo, 供应商 vendor) 逐个调 /purchase/answer 查权威承诺交期——
几百对就是几百次串行 HTTP（携客云还限流）。

观察：已答交的 firm 承诺交期很少变；会变的是【尚未答交】的子件（供应商正在答交）。
做法：
  · firm 命中（拿到承诺日）→ 写缓存，TTL 内复用，**跳过** /purchase/answer 调用；
  · 未答交（无承诺日）→ **不缓存**，每次重算都重新查（这正是会变的部分）；
  · 新增 / 过期 / 曾无答复 → 重新查。

正确性：firm 日期最多滞后 TTL（默认 6h，可经 SC8_SRM_ANSWER_TTL_MIN 调）；
未答交始终最新。缓存落 reports/（gitignored）；只含 PO 号+承诺日，无客户名。

本模块**无平台依赖**（纯标准库），便于单元测试。
"""
from __future__ import annotations

import json
import time
from pathlib import Path


def _load(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}   # 无缓存 / 损坏 → 当作空，下次重新填充


def _save(path: Path, cache: dict) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")
        tmp.replace(path)   # 原子替换，避免半截 JSON 被读到
    except Exception:
        pass    # 写缓存失败不影响主流程（下次全量重查即可）


def fetch_confirmed_cached(
    connector,
    pairs: list[tuple[str, str]],
    *,
    cache_path: str | Path,
    ttl_sec: int,
    now: float | None = None,
) -> tuple[dict[str, str], dict]:
    """对 (poErpNo, vendor) 对取权威承诺交期，firm 结果 TTL 内复用。

    Args:
        connector:  XkySrmConnector（需有 get_confirmed_dates(pairs)->(dict, failed)）。
        pairs:      [(poErpNo, vendor), ...] 待查对（来自看板的 BOM 子件 PO）。
        cache_path: 缓存 JSON 路径（reports/srm_answer_cache.json）。
        ttl_sec:    firm 承诺缓存有效期（秒）；<=0 关闭复用（等同不缓存）。
        now:        当前时间戳（测试可注入）。

    Returns:
        (confirmed, stats)
          confirmed: {poErpNo: 承诺日 YYYY-MM-DD}  —— 与 connector.get_confirmed_dates 的字典口径一致
          stats:     {"total","reused","queried"}  —— 供日志/审计，便于观测提速效果
    """
    now = time.time() if now is None else now
    path = Path(cache_path)
    cache = _load(path)

    confirmed: dict[str, str] = {}
    to_fetch: list[tuple[str, str]] = []
    for po, vendor in pairs:
        key = f"{po}|{vendor}"
        ent = cache.get(key)
        if (ttl_sec > 0 and ent and ent.get("date")
                and (now - ent.get("fetched_at", 0)) < ttl_sec):
            confirmed[po] = ent["date"]          # firm 且新鲜 → 复用，跳过 API
        else:
            to_fetch.append((po, vendor))        # 新 / 过期 / 曾无答复 → 重新查

    if to_fetch:
        fresh, _failed = connector.get_confirmed_dates(to_fetch)
        for po, vendor in to_fetch:
            key = f"{po}|{vendor}"
            d = fresh.get(po)
            if d:
                confirmed[po] = d
                cache[key] = {"date": d, "fetched_at": now}   # firm → 缓存
            else:
                cache.pop(key, None)   # 未答交 → 不缓存（下次仍重查这部分）
        _save(path, cache)

    return confirmed, {"total": len(pairs), "reused": len(pairs) - len(to_fetch),
                       "queried": len(to_fetch)}
