# sc8-baoguan-v2-batch1 Design

## Context

保供看板（`sc8/baoguan.py` assess_supply_risk）现为**单层、日期驱动**：`estimate_material_arrivals(成品, BOM直接子件, SRM承诺)` → 齐料日 = max(直接子件到货日)。`load_real_bom(max_depth=1)` 只取直接子件。现货净额（`stock-api-inventory-source`）已加、但只净**直接子件**、不净半成品自身、不下钻。专员反馈暴露三处结构缺陷（五递归 / 二.4半成品净额 / 二.2多行）+ 两处看板增强（一.1窗口 / 一.2未答复全展开）。

## Goals / Non-Goals

**Goals**：F 成品 → S 半成品递归展开到叶；逐层半成品自库存净额；看板窗口过滤 + 未答复全展开；PO 多行答交核实。全回归不漂移（现黄金 flag OFF）。
**Non-Goals**：委外厂排产/半成品加工周期（点六，Phase2）——本包半成品若需自制，其"可得日"暂按其子件最晚到货（不加工时），加工排产 backlog 留六。主料/替代料评估（一.3）+ 部分齐套显示（四）= 批2 专线口径，不在本包。不翻 `SC8_NET_INVENTORY`（交付即用需专员黄金重核）。

## Decisions

- **D1 递归 BOM（五）**：`load_real_bom` 支持 `max_depth>1` 递归展开（`get_bom_for_products` 已支持深度参数）；保供拿到多层 BOM 后，齐料评估**自顶向下**：成品直接子件里，叶料 = 采购到货判定（现逻辑），半成品 = 递归其子件的齐料日 rollup。备选（局部展开）否：单一 BOM 源、复用连接器递归。
- **D2 逐层半成品净额（二.4）**：自顶向下算每料**净需求** = 毛需求 − 该料白名单仓可用现货（复用 `get_inventory`）。半成品 S：net(S) ≤ 0 → 视为现货齐备、不下钻、其"可得日"=now；net(S) > 0 → 只对**净需求部分**下钻展开 S 的子件（子件毛需求按 net(S) 计），S 可得日 = max(其净需求子件到货日)。即"1264−264=1000 才下钻"。
- **D3 齐料日多层滚动**：成品齐料日 = max(直接子件可得日)，其中半成品可得日按 D2 递归得出（叶到货 → 半成品 rollup → 成品）。瓶颈子件 = 关键路径最晚那个**叶级**料（专员要的是可采购/可催的真瓶颈，不是半成品本身）。
- **D4 窗口过滤（一.1）**：`build_dashboard`/`compute_snapshot` 增 `ship_before`（默认 `2026-10-31`，可配 `SC8_BAOGUAN_SHIP_BEFORE`）；出货日 > 窗口的成品行不进看板。滚动口径（是否每月自动滚 3 月）待专员确认，先用固定日 + 可配。
- **D5 未答复全展开（一.2）**：`BaoguanRow` 已含 `no_feedback_materials` 全量；`render_*`/`row_to_dict` 补充展示全部未答复子件（现只突出瓶颈 1 个），前端行详情列出清单。
- **D6 PO 多行核实（二.2）**：核 `sources.load_srm_deliveries` 的 `/purchase/answer` 是否对同料多 PO 行只取首行；漏则改为遍历全部 PO 行、取最早有效答交（committed_date），与引擎 `srm_index` 取最早一致。先用 R01F.0005（PO ZPCG20260509006 行40/50）真实数据核。

## Risks / Trade-offs

- [递归 BOM 深度/环路] → `get_bom_for_products` 已有 visited 防环（kit_engine 同款）；深度上限设合理值（如 5），超深告警。
- [半成品无加工工时 → 齐料日偏乐观] → 明示点六（排产）为 Phase2；本包半成品可得日=子件最晚到货，文档标注"未含加工周期"，专员知悉。
- [多层+净额显著改四色/瓶颈] → 与 stock-api 同批经专员黄金重核签字；本包默认行为受 `SC8_NET_INVENTORY` 门控，OFF 时退化到现单层逻辑、零漂移。
- [性能：递归 BOM + 每料 get_inventory N 次] → 复用并发；BOM 一次多层拉取；inventory 批量。

## Migration Plan

1. `load_real_bom` 递归（max_depth 可配）+ 单测。
2. 保供多层齐料 + 逐层净额引擎（D2/D3），挂 `SC8_NET_INVENTORY` 门；OFF 退化现逻辑（零漂移回归）。
3. 窗口过滤（D4）+ 未答复全展开（D5）。
4. PO 多行核实（D6）：真实数据核 R01F.0005，漏则修 + 回归。
5. 全回归；正式库真实抽验专员案例（S02Y.0035/0120/0166、F02N.0226）；出净额/多层前后对比给专员黄金重核。
- **回滚**：`SC8_NET_INVENTORY=off` 退回现单层无净额逻辑。

## Open Questions

- 窗口滚动口径（固定 2026-10-31 vs 每月滚 3 月）——待专员/Paul 定（先固定+可配）。
- 半成品加工周期（点六）——Phase2；本包不含。
- 批2（一.3 主料替代料去重、四 部分齐套 1000/8139 显示）——姚祖怡专线口径先行。
