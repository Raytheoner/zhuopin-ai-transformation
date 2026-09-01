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
# 模块级引用真实加载器：测试通过 monkeypatch 替换这几个符号（同 test_fo_health 套路）
from .material_board import build_material_board
from .sources import (_fetch_line_status, load_material_commitments,
                      load_purchase_orders_by_material, load_purchase_supply_by_material,
                      load_real_bom, load_real_orders, load_srm_deliveries)


@dataclass
class Snapshot:
    """一次保供看板重算的结果快照（缓存 + /api/baoguan 载荷）。"""
    generated_at: str                       # 重算完成时刻（ISO，本地时间）
    today:        str                       # 重算所用业务日期
    rows:         list[dict] = field(default_factory=list)   # row_to_dict 序列化的成品行
    counts:       dict = field(default_factory=dict)         # {"red","gap","yel","grn"}
    status:       str | None = None         # FO 状态过滤口径（"2"=已审核 / None=全部；
                                            # 该字段是单据头状态，不反映行级"关闭"——
                                            # 行级关闭另由 loaders.parse_forecast_order_rows
                                            # 按 LineStatus 过滤，见队列 #173）
    param_version: str = ""
    components:   int = 0                   # 直接子件总数
    srm_hit:      int = 0                   # 携客云承诺命中子件数
    ok:           bool = True               # False = 尚未刷新（空态），非错误
    note:         str = ""                  # 状态说明（空态/错误摘要，不含客户敏感数据）
    # ── 物料看板（队列 #334，2026-08-20）：同一份快照的第二种切法 ─────────────
    # 纯派生自上面的 rows（见 material_board.build_material_board），一次计算两处消费，
    # 不新拉任何数据源、不改任何既有判定。两个字段**都带缺省值**——旧格式缓存
    # （无这两个键）经 `Snapshot(**raw)` 反序列化时取缺省，页面显示空态而非报错，
    # 下一次重算即填满（design D1 向后兼容条款，有回归测试守护）。
    materials:      list[dict] = field(default_factory=list)   # 物料行
    materials_meta: dict = field(default_factory=dict)         # 月份列/窗口/窗口外计数

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


def _prefetch_line_status(components: set[str], *, audit=None) -> dict[tuple[str, str], int]:
    """为 ⑥⑧ 预取一次采购订单行级关闭状态；任何失败都降级为 `{}`，绝不阻断重算。

    单独抽成模块级函数（而非内联进 `compute_snapshot`）是为了让测试能像其它加载器一样
    对它 monkeypatch —— 否则每个 `compute_snapshot` 测试都会真的去 `ZpConnector.from_env()`。
    """
    if not components:
        return {}
    try:
        from zhuopin_platform.shared_tools.erp_connector.connector import ZpConnector
        conn = ZpConnector.from_env(audit=audit)
        return _fetch_line_status(conn, components)
    except Exception:
        return {}


def compute_snapshot(*, today: date | None = None, status: str | None = "2",
                     audit=None, trace=None,
                     cache_dir: str | Path | None = None,
                     srm_ttl_sec: int = 0) -> Snapshot:
    """进程内重算保供看板：FO + U9C BOM + 携客云承诺（分层）→ build_dashboard → Snapshot。

    status：FO 状态过滤（"2"=已审核；None=不过滤），单据头口径。行级"关闭"由
    `load_real_orders`→`load_forecast_orders_from_api` 内部按 LineStatus 过滤，
    本参数与之独立、无需调用方额外处理（队列 #173，#19 根治）。
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
    # ② 真实 BOM（成品 → 全部叶子件，多层递归——姚祖怡 07-26 V6 #9 根因修复：
    #    max_depth 此前恒为 1，半成品自身子件从未拉取，见 config.bom_max_depth 注释）
    product_ids = list(dict.fromkeys(o.item_code for o in orders))
    bom = load_real_bom(product_ids, max_depth=config.bom_max_depth(), audit=trace)
    # 叶子件 = 不作为任何行 product_id 出现的 component_id（与 kit_engine.explode_bom
    # 判定"是否继续展开"用的 sub_assemblies 同一口径）——半成品/中间节点自身不应计入
    # SRM 答交查询/库存核对范围（半成品是自制件，从无供应商承诺，也不应占位现货核对）。
    # max_depth=1（旧行为）时天然只有一层，本口径与旧版 `r.level == 1` 结果一致，向后兼容。
    sub_assembly_ids = {r.product_id for r in bom}
    components = {r.component_id for r in bom if r.component_id not in sub_assembly_ids}
    # ③ 真实承诺交期（分层取数：/purchase/answer 权威 > 看板辅助 > 无答复兜底）
    #    cache_dir 给定 → firm 承诺 TTL 内复用，提速立即重算（未答交仍每次重查）
    srm_cache = str(Path(cache_dir) / "srm_answer_cache.json") if cache_dir else None
    srm = load_srm_deliveries("real", materials=components, audit=trace,
                              cache_path=srm_cache, ttl_sec=srm_ttl_sec)
    # ⑤ 现货净额（开关默认关；开时经 Stock API 取白名单仓可用量，消除"有货却被追料"误判 P0）
    inventory = None
    if config.net_inventory_enabled():
        from zhuopin_platform.shared_tools.erp_connector import ZpConnector
        conn = ZpConnector.from_env(audit=trace)
        inventory = {r.material_id: r.current_stock
                     for r in conn.get_inventory(sorted(components))}
    # ⑥ PO 在途数据（功能批1，姚祖怡 07-23，#12/#14 共享基础）：纯展示派生列，失败不阻断
    #    整体重算——与 FO/BOM/SRM 等核心数据源的强 fail-loud 语义有意区分（见 sources.py
    #    load_purchase_orders_by_material docstring）；异常时降级为 None，#12/#14 相关
    #    字段随之退化为空/None，其余核心看板（四色/kit_date/净额）不受影响。
    purchase_orders = None
    line_status: dict[tuple[str, str], int] = {}   # ⑥⑧ 共用；显式初始化，不依赖分支求值顺序
    if config.po_transit_enabled():
        # 行级关闭状态预取一次，⑥⑧ 共用（`sources._fetch_line_status` docstring 说明为何：
        # 该查询按料号逐个打 ERP、无缓存，约 1600 次 HTTP／约 2 分钟；物料看板若让它再跑
        # 一遍，等于把每小时重算的这笔开销翻倍）。预取本身 fail-soft 返回 `{}`，两个 loader
        # 拿到 `{}` 即跳过关闭行剔除，与改造前的降级行为完全一致。
        line_status = _prefetch_line_status(components, audit=trace)
        try:
            purchase_orders = load_purchase_orders_by_material(
                components, audit=trace, line_status=line_status)
        except Exception as e:
            purchase_orders = None
            if audit is not None:
                from zhuopin_platform.audit import AuditEvent
                audit.record(AuditEvent(
                    scenario="SC8", action="po_transit_load_failed", evaluator="system",
                    automation_level="L1", decision={"error": f"{type(e).__name__}: {e}"[:200]},
                ))
    # ⑦ 物料逐笔承诺明细（#18-a/b，姚祖怡 07-28 判例回件，队列 #139）：驱动 BOM 缺口
    #    物料清单里的"答交数量"累计展示，同 ⑥ 一样是纯展示派生列，失败不阻断整体重算。
    material_commitments = None
    try:
        material_commitments = load_material_commitments("real", materials=components)
    except Exception as e:
        material_commitments = None
        if audit is not None:
            from zhuopin_platform.audit import AuditEvent
            audit.record(AuditEvent(
                scenario="SC8", action="material_commitments_load_failed", evaluator="system",
                automation_level="L1", decision={"error": f"{type(e).__name__}: {e}"[:200]},
            ))
    # ④ 保供齐套 → 四色看板（判级语义不变；inventory/purchase_orders/material_commitments
    #    =None（默认）时零漂移）
    rows = build_dashboard(orders, bom, srm, today=today, inventory=inventory,
                           purchase_orders=purchase_orders,
                           material_commitments=material_commitments)

    # ⑧ 未交 PO 的供应商/制单人（物料看板，队列 #334，design D4-a）：与 ⑥ 同一批 PO
    #    行、同一份在途口径，只是汇总维度不同（⑥ 汇总数量、本步汇总名称）。ERP 连接器
    #    自带 4 小时磁盘缓存，不增加真实请求量；同 ⑥⑦ 一样是纯展示派生列，fail-soft。
    supply_by_material = None
    if config.po_transit_enabled():
        try:
            supply_by_material = load_purchase_supply_by_material(
                components, audit=trace, line_status=line_status)
        except Exception as e:
            supply_by_material = None
            if audit is not None:
                from zhuopin_platform.audit import AuditEvent
                audit.record(AuditEvent(
                    scenario="SC8", action="purchase_supply_load_failed", evaluator="system",
                    automation_level="L1", decision={"error": f"{type(e).__name__}: {e}"[:200]},
                ))
    # ⑨ 物料看板派生（队列 #334）：纯派生自上面已算好的 rows，零取数、零判定改动。
    #    本步异常同样不得阻断整体重算——物料看板是新增视图，它算不出来不应该让既有
    #    四色看板一起打不开（与 ⑥⑦⑧ 同一 fail-soft 约定）。
    board = None
    try:
        board = build_material_board(rows, today=today,
                                     commitments=material_commitments,
                                     supply_by_material=supply_by_material)
    except Exception as e:
        board = None
        if audit is not None:
            from zhuopin_platform.audit import AuditEvent
            audit.record(AuditEvent(
                scenario="SC8", action="material_board_build_failed", evaluator="system",
                automation_level="L1", decision={"error": f"{type(e).__name__}: {e}"[:200]},
            ))

    counts = {
        "red": sum(1 for r in rows if r.risk == RISK_RED),
        "gap": sum(1 for r in rows if r.risk == RISK_GAP),
        "yel": sum(1 for r in rows if r.risk == RISK_YELLOW),
        "grn": sum(1 for r in rows if r.risk == RISK_GREEN),
    }
    snap = Snapshot(
        generated_at=_now_iso(), today=today.isoformat(),
        rows=[row_to_dict(r) for r in rows], counts=counts, status=status,
        param_version=config.active_param_version(), components=len(components), srm_hit=len(srm),
        materials=board.rows if board is not None else [],
        materials_meta=board.meta() if board is not None else {},
    )
    if audit is not None:
        from zhuopin_platform.audit import AuditEvent
        audit.record(AuditEvent(
            scenario="SC8", action="baoguan_snapshot", evaluator="system",
            automation_level="L1",
            decision={"rows": len(rows), **counts, "components": len(components),
                      "srm_hit": len(srm), "materials": len(snap.materials)},
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
