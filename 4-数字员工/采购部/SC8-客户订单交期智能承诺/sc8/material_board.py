"""物料看板聚合引擎（capability: baoguan-material-board，队列 #334）。

姚祖怡 2026-08-12 采购部#13 回件新问题 5（原话用的是「我要求」）：现有保供看板只能
「按逐个项目」看缺料，而采购员日常补料是**按单个物料**下单的——同一个 `R01B.0105`
分散在十几张成品卡片里，要人工把各卡片里的缺口数量抄下来再相加，才知道这个料到底
还缺多少。本模块把**同一份保供快照**按物料维度重新切一次。

🔴 **纯派生、零取数、零判定**：输入就是 `build_dashboard` 已经算好的 `BaoguanRow`
列表，本模块不拉任何数据源、不改四色/齐料日/可齐套/BOM 缺口清单任何既有判定。
快照重算一次约 15 分钟（携客云 SRM 1 req/30s 限流），物料看板**绝不能**触发独立取数。

设计决策见 `openspec/changes/sc8-material-board-view/design.md`：
  · D2  三个月窗口＝以快照业务日期所在月为首的连续 N 个自然月，列标题显示真实月份；
  · D3  答交明细取**物料级**承诺全量、按物料三月合计缺口累计（不复用行级 `cst[].cb`）；
  · D5/D6（Shao Peishen 2026-08-19 拍板按推荐 (a)）品牌／责任人无任何可用取数源 →
        保留该列、每行显式标注取数缺口，**不留空、不以近似字段顶替**；
  · D10 状态列取既有四态，同一物料在各成品行下不一致时如实标示分歧、不静默取其一；
  · D11 `role == "substitute"` 的替代料展示行不单独成行（它沿用主料需求量，聚合会
        把同一份缺口重复计一次），只在主料行上标「含替代料」。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from .baoguan import _cumulative_confirmed_batches

# 取数缺口标记（D5/D6）：品牌／责任人两列当前**全库无源**，2026-08-19 已用生产凭据
# 逐端点探测坐实（8 个 SRM 候选路径全部 404、ERP 三个端点逐字段查无品牌、ERP 制单人
# 被他自己的样例证伪）。这两列每一行都填这个标记——**留空会被读成「这个料没有品牌／
# 没有责任人」，那是假信息；填一个近似字段会被读成「负责人就是这个人」，那是错信息**。
# 页面顶部另有一段说明写清原因与下一步，见 webapp._materials_page。
FIELD_GAP = "—（取数缺口）"

# 状态分歧标记（D10）：同一物料的状态派生自物料级的未交 PO 与物料级答交记录，与成品
# 无关，理论上应在各成品行间一致——但那是推断，不是验证。真出现不一致时如实标示，
# 并把该现象单独登记为待查行，不顺手改既有判定。
STATUS_DIVERGENT = "divergent"

# 四态中文标签（物料看板页面与 Excel 导出共用）。
# ⚠️ 成品看板的前端 JS 里另有一份同名同值的 `CST_LABEL`（`baoguan._HTML_JS`）——那是
# 内嵌在静态看板 JS 里的常量，物料看板页不加载那段 JS，无法直接复用。**两份必须逐字
# 相同**（同一个状态在两个页面上显示成两种说法，会被读成两回事），已由
# `test_material_board.py::test_status_labels_match_dashboard_js` 守护：改一处而没改
# 另一处即测试失败。`divergent` 是物料看板独有的（成品行粒度不存在分歧），不在那份里。
STATUS_LABELS = {
    "no_transit":          "无未交订单无答交",
    "transit_unconfirmed": "有未交订单无答交",
    "transit_confirmed":   "有未交订单已答交",
    "confirmed_no_transit": "无未交订单有答交",
    STATUS_DIVERGENT:      "各项目下状态不一致",
}


@dataclass(frozen=True)
class MonthBucket:
    """一个月度缺口列。`ym` 供归集与排序，`label` 供页面/导出显示真实月份。"""
    ym:    str    # "2026-08"
    label: str    # "8月"；跨年时为 "2027年1月"（否则「1月」在 12/1/2 三列里指代不清）

    def to_dict(self) -> dict:
        return {"ym": self.ym, "label": self.label}


@dataclass
class MaterialBoard:
    """物料看板一次聚合的完整结果：行 + 使这些行可被正确解读所必需的元信息。

    刻意不是一个裸的 list——月份列标题与窗口范围是**读懂那几个数字的前提**（D7：
    可算但有前提，就把前提写在脸上）；「窗口外被排除了多少」同理，藏起来就成了
    静默截断（No silent caps）。
    """
    months: list[MonthBucket] = field(default_factory=list)
    rows:   list[dict] = field(default_factory=list)
    # 窗口外缺口：**不计入任何月度列与合计列**（spec 明确要求），但必须可见。
    # 「全部缺口都落在窗口外」的物料不出现在行里（一行全 0 会被读成「没有缺口」），
    # 改为在这里计数，由页面写明「另有 N 个物料的缺口全部落在窗口之外，未列出」。
    out_of_window_materials: int = 0
    out_of_window_qty:       float = 0.0

    def meta(self) -> dict:
        """随 `Snapshot.materials_meta` 落盘的元信息（纯标量/字符串，可 JSON 序列化）。"""
        return {
            "months": [m.to_dict() for m in self.months],
            "window": (f"{self.months[0].ym} ~ {self.months[-1].ym}" if self.months else ""),
            "out_of_window_materials": self.out_of_window_materials,
            "out_of_window_qty": self.out_of_window_qty,
        }


def month_span(today: date, months: int) -> list[MonthBucket]:
    """以 `today` 所在月为首的连续 `months` 个自然月（D2：随快照滚动，不写死月份）。"""
    out: list[MonthBucket] = []
    for i in range(max(1, months)):
        idx = today.month - 1 + i
        yy = today.year + idx // 12
        mm = idx % 12 + 1
        label = f"{mm}月" if yy == today.year else f"{yy}年{mm}月"
        out.append(MonthBucket(ym=f"{yy:04d}-{mm:02d}", label=label))
    return out


def _gap_of(comp) -> float | None:
    """一条 BOM 缺口物料记录的缺口数量。

    `gap_qty` 仅在净额开关开启且传入 inventory 时非 None（`_component_supply_status`
    的既有约定：不以 0 冒充）。关闭时退回本项目毛需求 `qty_needed`——那是该场景下
    「还缺多少」唯一可得的量，不是近似顶替另一个语义的字段。生产环境
    `SC8_NET_INVENTORY=on` 恒开，回退路径只在测试/降级时走到。
    """
    if comp.gap_qty is not None:
        return float(comp.gap_qty)
    if comp.qty_needed is None:
        return None
    return float(comp.qty_needed)


def build_material_board(
    rows: list, *, today: date,
    commitments: dict[str, list[tuple[date, float]]] | None = None,
    supply_by_material: dict[str, dict[str, list[str]]] | None = None,
    months: int | None = None,
) -> MaterialBoard:
    """把成品维度的 `BaoguanRow` 列表按物料重新聚合成物料看板行。

    rows：`build_dashboard` 的输出（成品行）。只读，不修改。
    today：快照业务日期，决定三个月窗口的起点（D2）。
    commitments：`sources.load_material_commitments` 的输出 `{料号: [(日期,数量),...]}`
        **全量**——D3 刻意不复用行级 `cst[].cb`：那是按单张成品行的缺口累计截断出来的，
        多行取并集会既重复又缺漏。这里按物料的三月合计缺口重新跑一次同一个既有函数
        `_cumulative_confirmed_batches`（同一口径、同一实现，不是第二份判据）。
        ⚠️ 由此物料看板与成品卡片在同一物料上**可能显示不同的批次条数**——这是正确的
        （累计目标不同：一个是这张单要的量，一个是三个月要的总量），页面须写明。
    supply_by_material：`sources.load_purchase_supply_by_material` 的输出；None → 供应商
        列为空列表（页面显示取数缺口态），**不报错**（纯展示派生列 fail-soft）。
    months：月度列跨度；None → `config.material_board_month_span()`（默认 3）。
    """
    if months is None:
        from . import config
        months = config.material_board_month_span()
    buckets = month_span(today, months)
    bucket_index = {b.ym: i for i, b in enumerate(buckets)}
    commitments = commitments or {}
    supply_by_material = supply_by_material or {}

    acc: dict[str, dict] = {}
    for r in rows:
        ship = getattr(r, "ship_date", None)
        ym = f"{ship.year:04d}-{ship.month:02d}" if ship else ""
        for comp in getattr(r, "component_status", None) or []:
            if comp.role == "substitute":
                continue          # D11：替代料展示行沿用主料需求量，聚合会重复计一次
            gap = _gap_of(comp)
            if gap is None or gap <= 0:
                continue          # spec：只纳入存在真实缺口（缺口数量大于 0）的物料
            slot = acc.get(comp.component_id)
            if slot is None:
                slot = acc[comp.component_id] = {
                    "name": "", "statuses": set(), "tq": 0.0,
                    "m": [0.0] * len(buckets), "out": 0.0, "sub": False, "nrow": 0,
                }
            if not slot["name"]:
                slot["name"] = (comp.component_name
                                or (getattr(r, "component_names", None) or {}).get(
                                    comp.component_id, ""))
            slot["statuses"].add(comp.status)
            # 未交订单数量是**物料级**取值（`purchase_orders[料号]`，与成品无关），
            # 同一物料在各成品行下由构造即相同；取 max 只是防御，不是在做选择。
            slot["tq"] = max(slot["tq"], float(comp.transit_qty or 0.0))
            slot["sub"] = slot["sub"] or comp.role == "primary"
            slot["nrow"] += 1
            idx = bucket_index.get(ym)
            if idx is None:
                slot["out"] += gap    # 窗口外：不计入任何月度列与合计列，但要可见
            else:
                slot["m"][idx] += gap

    out_rows: list[dict] = []
    out_of_window_materials = 0
    out_of_window_qty = 0.0
    for mid, slot in acc.items():
        total = sum(slot["m"])
        if total <= 0:
            # 该物料的缺口全部落在三个月窗口之外。列一行全 0 会被读成「这个料不缺」，
            # 比不列更误导；故不列，但在 meta 里计数，由页面写明有多少被排除。
            if slot["out"] > 0:
                out_of_window_materials += 1
                out_of_window_qty += slot["out"]
            continue
        out_of_window_qty += slot["out"]
        statuses = sorted(slot["statuses"])
        supply = supply_by_material.get(mid) or {}
        out_rows.append({
            "id": mid,
            "name": slot["name"],
            # 品牌（D6-a）：全库无源，逐行显式标注取数缺口。
            "brand": FIELD_GAP,
            "st": statuses[0] if len(statuses) == 1 else STATUS_DIVERGENT,
            "sts": statuses,                       # 分歧时供页面/导出列出全部实际状态
            "tq": slot["tq"],
            "m": slot["m"],                        # 与 meta.months 逐位对应
            "total": total,
            "out": slot["out"],                    # 该物料落在窗口外的缺口（不计入 total）
            # 答交数量/日期（D3）：物料级承诺全量，按三月合计缺口累计截断。
            "cb": [{"d": d.isoformat(), "q": q}
                   for d, q in _cumulative_confirmed_batches(
                       commitments.get(mid, []), total)],
            "sup": list(supply.get("suppliers") or []),
            # 责任人（D5-a）：SRM「请购需求池-采购订单协同」无 OpenAPI 端点，ERP 制单人
            # 已被真实数据证伪 ⇒ 逐行显式标注取数缺口，**不得**用下面的 buyers 顶替。
            "owner": FIELD_GAP,
            # 制单人：只随载荷保留供内部排障与判例包取证（同 `row_to_dict` 的 `cd` 约定），
            # 页面「责任人」列与 Excel 导出均不使用它。
            "buyers": list(supply.get("buyers") or []),
            "hasSub": slot["sub"],
            "nrow": slot["nrow"],                  # 该物料出现在几张成品卡片里（供下钻核对）
        })
    out_rows.sort(key=lambda x: (-x["total"], x["id"]))
    return MaterialBoard(months=buckets, rows=out_rows,
                         out_of_window_materials=out_of_window_materials,
                         out_of_window_qty=out_of_window_qty)
