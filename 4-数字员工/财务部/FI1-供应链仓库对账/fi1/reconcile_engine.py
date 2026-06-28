"""对账引擎（纯算法，无副作用）—— 毛理论口径（design D2）。

理论净用量 = Σ_成品(产出 × BOM qty_per_unit)，**不含损耗**；
标准损耗基线 = Σ_成品(产出 × qty_per_unit × loss_rate[m_scrap])；
总差异 = 实际投料 − 理论净用量；差异率 = 总差异 / 理论净用量（理论为 0 → None·无基准）。

同一子件被多个成品共用时按成品累加。纯函数，便于单测与黄金回归。
"""
from __future__ import annotations

from dataclasses import dataclass

from .models import ComponentReconcile, MaterialFeed, ProductionOutput

# 浮点累加保留 6 位，消除二进制误差对"相等"判定的干扰
_ROUND = 6


@dataclass
class ReconcileComputation:
    """对账引擎产出：逐子件结果 + BOM 拉取失败的成品清单（残缺，待人工核）。"""
    components: list[ComponentReconcile]
    incomplete_products: list[str]


def compute_reconcile(
    bom_rows: list,
    outputs: list[ProductionOutput],
    feeds: list[MaterialFeed],
    *,
    bom_failed_product_ids: list[str] | tuple[str, ...] = (),
) -> ReconcileComputation:
    """计算逐子件对账（不含分类；分类见 variance_classify）。

    Args:
        bom_rows: 平台 BomRow 列表（product_id/component_id/qty_per_unit/loss_rate/...）。
        outputs:  成品产出。
        feeds:    实际投料（同子件多行自动累加）。
        bom_failed_product_ids: BOM 拉取失败的成品（其子件理论用量缺失，整料号待人工核）。
    """
    output_by_product: dict[str, float] = {}
    for o in outputs:
        output_by_product[o.product_id] = output_by_product.get(o.product_id, 0.0) + float(o.finished_qty)

    feed_qty: dict[str, float] = {}
    feed_name: dict[str, str] = {}
    feed_unit: dict[str, str] = {}
    for f in feeds:
        feed_qty[f.component_id] = feed_qty.get(f.component_id, 0.0) + float(f.actual_qty)
        feed_name.setdefault(f.component_id, f.component_name)
        feed_unit.setdefault(f.component_id, f.unit)

    theo: dict[str, float] = {}
    loss: dict[str, float] = {}
    bom_name: dict[str, str] = {}
    for row in bom_rows:
        qty = output_by_product.get(row.product_id, 0.0)
        theo[row.component_id] = theo.get(row.component_id, 0.0) + qty * float(row.qty_per_unit)
        loss[row.component_id] = loss.get(row.component_id, 0.0) + qty * float(row.qty_per_unit) * float(row.loss_rate)
        bom_name.setdefault(row.component_id, row.component_name)

    results: list[ComponentReconcile] = []
    for cid in sorted(set(theo) | set(feed_qty)):
        theoretical = round(theo.get(cid, 0.0), _ROUND)
        std_loss = round(loss.get(cid, 0.0), _ROUND)
        actual = round(feed_qty.get(cid, 0.0), _ROUND)
        if theoretical == 0 and actual == 0:
            continue  # 无活动子件，跳过
        variance = round(actual - theoretical, _ROUND)
        if theoretical > 0:
            variance_pct: float | None = round(variance / theoretical, _ROUND)
            bom_incomplete = False
        else:
            variance_pct = None          # NA·无理论基准
            bom_incomplete = True        # 有实际投料但无 BOM 理论基准
        name = bom_name.get(cid) or feed_name.get(cid) or ""
        results.append(ComponentReconcile(
            component_id=cid,
            component_name=name,
            theoretical_net=theoretical,
            standard_loss=std_loss,
            actual_feed=actual,
            total_variance=variance,
            variance_pct=variance_pct,
            bom_incomplete=bom_incomplete,
        ))

    return ReconcileComputation(
        components=results,
        incomplete_products=sorted(set(bom_failed_product_ids)),
    )
