"""保供看板计算服务底座（design D2/D3）——进程内重算 + 快照缓存。

把 runner（scripts/run_baoguan_dashboard.py）里的「拉三源 → build_dashboard」一段提炼为
``compute_snapshot()``，供 Flask 服务进程内直接调用（D2：不走 subprocess、不解析 markdown）。

红线：
  · real 缺端点 → fail-loud（复用 sources，绝不静默回退 mock）；
  · 快照含真实客户名 → 只持久化到 reports/（git-ignored），绝不入库；
  · 不改四色判级语义（仍调用 baoguan.build_dashboard）。
"""
from __future__ import annotations

import json
import os
import tempfile
from dataclasses import asdict, dataclass, field
from datetime import date, datetime
from pathlib import Path

from . import config
from .baoguan import RISK_GAP, RISK_GREEN, RISK_RED, RISK_YELLOW, build_dashboard, row_to_dict
# 模块级引用真实加载器：测试通过 monkeypatch 替换这三个符号（同 test_fo_health 套路）
from .sources import load_real_bom, load_real_orders, load_srm_deliveries


@dataclass
class Snapshot:
    """一次保供看板重算的结果快照（缓存 + /api/baoguan 载荷）。"""
    generated_at: str                       # 重算完成时刻（ISO，本地时间）
    today:        str                       # 重算所用业务日期
    rows:         list[dict] = field(default_factory=list)   # row_to_dict 序列化的成品行
    counts:       dict = field(default_factory=dict)         # {"red","gap","yel","grn"}
    status:       str | None = None         # FO 状态过滤口径（"2"=已审核 / None=全部）
    param_version: str = ""
    components:   int = 0                   # 直接子件总数
    srm_hit:      int = 0                   # 携客云承诺命中子件数
    ok:           bool = True               # False = 尚未刷新（空态），非错误
    note:         str = ""                  # 状态说明（空态/错误摘要，不含客户敏感数据）

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def empty(cls, *, note: str = "尚未刷新，请点击刷新或等待定时刷新") -> "Snapshot":
        """空态快照：服务刚启动、无任何缓存时返回（明确状态，非 mock、非报错）。"""
        return cls(generated_at="", today="", rows=[],
                   counts={"red": 0, "gap": 0, "yel": 0, "grn": 0},
                   ok=False, note=note)


def _now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def compute_snapshot(*, today: date | None = None, status: str | None = "2",
                     audit=None, trace=None,
                     cache_dir: str | Path | None = None,
                     srm_ttl_sec: int = 0) -> Snapshot:
    """进程内重算保供看板：FO + U9C BOM + 携客云承诺（分层）→ build_dashboard → Snapshot。

    status：FO 状态过滤（"2"=已审核，剔除草稿/关闭；None=不过滤）。
    audit / trace：平台 AuditLogger / ConnectorAudit，缺省 None（生产应注入）。
    cache_dir/srm_ttl_sec：firm 承诺交期缓存（提速立即重算）。给定时把
        cache_dir/srm_answer_cache.json + ttl 传入 load_srm_deliveries；
        缺省（None/0）= 原全量行为（测试/golden 不变）。
    real 任一源不可达 → 由 sources 层 fail-loud 抛出（本函数不吞异常，交调用方保留旧缓存）。
    """
    today = today or date.today()
    fo_base = os.environ.get("FO_API_BASE")
    ops_hook = os.environ.get("SC8_FO_OPS_WEBHOOK_URL") or os.environ.get("WECOM_WEBHOOK_URL")

    # ① 真实成品保供需求（FO 不可达 → fail-loud + 内部运维告警，不回退 mock）
    orders = load_real_orders(api_base=fo_base, audit=trace,
                              ops_webhook_url=ops_hook, status=status)
    # ② 真实 BOM（成品 → 直接子件）
    product_ids = list(dict.fromkeys(o.item_code for o in orders))
    bom = load_real_bom(product_ids, max_depth=1, audit=trace)
    components = {r.component_id for r in bom if r.level == 1}
    # ③ 真实承诺交期（分层取数：/purchase/answer 权威 > 看板辅助 > 无答复兜底）
    #    cache_dir 给定 → firm 承诺 TTL 内复用，提速立即重算（未答交仍每次重查）
    srm_cache = str(Path(cache_dir) / "srm_answer_cache.json") if cache_dir else None
    srm = load_srm_deliveries("real", materials=components, audit=trace,
                              cache_path=srm_cache, ttl_sec=srm_ttl_sec)
    # ④ 保供齐套 → 四色看板（不改判级语义）
    rows = build_dashboard(orders, bom, srm, today=today)

    counts = {
        "red": sum(1 for r in rows if r.risk == RISK_RED),
        "gap": sum(1 for r in rows if r.risk == RISK_GAP),
        "yel": sum(1 for r in rows if r.risk == RISK_YELLOW),
        "grn": sum(1 for r in rows if r.risk == RISK_GREEN),
    }
    snap = Snapshot(
        generated_at=_now_iso(), today=today.isoformat(),
        rows=[row_to_dict(r) for r in rows], counts=counts, status=status,
        param_version=config.PARAM_VERSION, components=len(components), srm_hit=len(srm),
    )
    if audit is not None:
        from zhuopin_platform.audit import AuditEvent
        audit.record(AuditEvent(
            scenario="SC8", action="baoguan_snapshot", evaluator="system",
            automation_level="L1",
            decision={"rows": len(rows), **counts, "components": len(components),
                      "srm_hit": len(srm)},
            data_sources={"fo": "real", "bom": "real", "srm_committed": "real"},
        ))
    return snap


class SnapshotStore:
    """保供快照缓存：内存 + JSON 持久化（design D3）。

    · ``get()`` 读内存最近快照（无→空态快照）；
    · ``set()`` 更新内存 + 原子写 JSON（reports/，git-ignored）；
    · 启动时从 JSON 恢复（重启不丢最近一份有效快照）。
    db_path=None → 纯内存（测试用，不落盘）。
    """

    def __init__(self, path: str | Path | None = None):
        self._path = Path(path) if path else None
        self._snap: Snapshot | None = None
        self._load()

    def _load(self) -> None:
        if not self._path or not self._path.exists():
            return
        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
            self._snap = Snapshot(**raw)
        except Exception:
            self._snap = None   # 损坏的缓存忽略，等下次刷新覆盖

    def get(self) -> Snapshot:
        return self._snap if self._snap is not None else Snapshot.empty()

    def has_data(self) -> bool:
        return self._snap is not None and self._snap.ok

    def set(self, snap: Snapshot) -> None:
        self._snap = snap
        if not self._path:
            return
        self._path.parent.mkdir(parents=True, exist_ok=True)
        # 原子写：先写临时文件再 rename，避免半截 JSON 被读到
        fd, tmp = tempfile.mkstemp(dir=str(self._path.parent), suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(snap.to_dict(), f, ensure_ascii=False)
            os.replace(tmp, self._path)
        finally:
            if os.path.exists(tmp):
                os.remove(tmp)
