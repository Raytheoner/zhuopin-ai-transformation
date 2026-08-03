# sc8-quote-qty-date-batch Design

## D1：#211 交货方式字段（receiveType）语义确认

真实探测 `XkySrmConnector.get_receive_board()`（2026-08-03，生产凭据）确认供应计划看板每条
`record` 自带 `receiveType` 字段（1 或 2），此前代码从未读取。用 R01B.0754 真实案例交叉验证：

- 姚祖怡举证的错误值（答交 500、日期 2026-08-07）命中 `receiveType=1` 的记录（该记录
  `poLineList` 挂 `poErpNo`，无 `scheduleBatch`）。
- 同料号同时存在 `receiveType=2` 的记录（`scheduleBatch`/`scheduleCreateName`/
  `schedulePublishName` 均有值，`poLineList` 恒空）。
- 时间戳换算 `boardDate=1786032000000` → `2026-08-07`（CST），与姚祖怡截图逐字吻合。

**结论**：`receiveType=1`=按订单交货（挂 PO，非姚祖怡要求的口径）；`receiveType=2`=按排程
交货（有排程计划编号，姚祖怡指定的唯一权威来源）。修复范围**仅限** `_extract_board_commitments`
（驱动 ⑦⑧ 答交数量/日期展示与 B2 周期匹配），**不改** `_extract_board_po_map`/
`load_srm_deliveries`（驱动 kit_date/gap_days/四色风险判定的既有口径）——展示层取数源头
修正，不触碰红线保护的判定逻辑。

## D2：#211 累计目标改为 gap_qty

`_cumulative_confirmed_batches` 此前以 `gross.get(m, 0.0)`（本项目需求数量）为累计目标；
姚祖怡原话"直至累计答交数量满足**缺口数量**为止"——目标应为 `gap_qty`（需求−现货净额）。
`_component_supply_status` 内调整代码顺序，先算 `available_qty`/`gap_qty`（若净额开关开启），
再把 `gap_qty if not None else need`（净额开关关闭时无 gap_qty 概念，退回 need，零漂移）
作为累计目标传入。

## D3：#212 cst-tag 溢出根因与修法

`.cst-tag{white-space:nowrap}` 在 `table-layout:fixed` 的窄列（状态列约占表宽 1/8）里，
`confirmed_no_transit` 状态文案（含内嵌"（异常，如实展示）"注释，16 字符）远长于其余三态
（8 字符），被迫单行不换行，溢出到相邻"可用现货数量"列，造成姚祖怡红圈标出的"看不清楚"。
修法：① 移除 `.cst-tag` 的 `white-space:nowrap`（继承父级 `.cst-table td` 既有的
`white-space:normal;word-break:break-word`，允许换行）；② 把注释文字从 `CST_LABEL` 拆到
独立的 `CST_NOTE` 常量 + `.cst-tag-note` 元素，四态徽标本身长度统一，不再依赖不换行来保持
"看起来完整"。全站扫描确认 `.cst-table` 是唯一采用 `table-layout:fixed` + 内嵌状态徽标的
组合，无同类风险点需要一并处理。

## D4：#173 FO 行级状态

IT 陈承 2026-07-30 回件：`ForecastOrder/Query` 已补 `LineStatus`（`SM_ForecastOrderLine.Status`，
2=核准/3=关闭）。2026-08-03 真实探测：120 条当前 FO 行中 106 条 LineStatus=2、14 条=3；
真实单号 `FO2026070001` 行60(`S02Y.0120`)/行230(`S02Y.0166`) 均为 3，与 ERP 界面"关闭"
一致——与 IT 回件验证结论吻合。`_FoApiRow` 新增 `LineStatus: _Opt[int]=None`（缺省核准，
向后兼容），`parse_forecast_order_rows` 在 `validate=True/False` 两条路径均剔除
`LineStatus==3` 行。

## D5：#173 PO 行级状态——跨端点 JOIN

真实探测确认 `ZpViewPurOrder/Query`（`get_purchase_orders` 现用端点）**不带**行级状态字段
（27,641 行 0 命中 `LineStatus`）；行级状态实际暴露在 `Purchase/Query`（与 `get_purchase_lines`
同端点，`get_ap_lines_by_supplier` 已示范的 `itemCode` 批量过滤路径可复用）。两端点字段
交叉验证：`ZpViewPurOrder` 的 `erpLineNo` 与 `Purchase/Query` 的 `DocLineNo` 对同一
`(erpNo/DocNo)` 一一对应（真实单号 `ZPCG20210915006` 核对一致）。

设计：`PurchaseOrder` 新增 `line_no` 字段（默认空串，向后兼容）；`get_purchase_orders`
从 `_ZpPurOrderRow.erpLineNo`（新增可选字段）回填；新增 `ZpConnector.get_purchase_line_status
(item_codes)`（按料号逐个查 `Purchase/Query`，聚合 `{(DocNo,DocLineNo): LineStatus}`，
real fail-loud，与 `get_purchase_orders` 同一约定）。`load_purchase_orders_by_material`
按 `(po_id, line_no)` JOIN 后剔除 `LineStatus∈{3,4,5}`（自然/短缺/超额关闭）的行，
**不受其数量口径**（`qty_received` 常年追不上/超过 `qty_ordered`）误判影响。

**365 天回溯窗口未退役**：它是数量数据（`qty_ordered`/`qty_received`）取数范围本身的
折衷（#139④ 已有的已知局限）；行级关闭过滤是叠加其上的正确性修正，两者互补非互斥——
即便未来某天窗口扩大/取消，关闭行过滤依然需要（真实关闭的行不该被算进在途，与回溯窗口
大小无关）。line_status 查询失败**单独 fail-soft**（本函数其余部分仍是既有的 real
fail-loud 约定）：它是在既有能力之上的附加修正，其失败不应连累"仅按数量口径"这条独立、
改造前就可用的能力整体降级。

## D6：#213 只读取证结论（不改判定，详情见 CLAUDE.md 场景记忆与队列 #213 行）

真实验证 F02N.0233→S02Y.0207→R01A.0707/R01A.0012 的替代料关系确实存在（`get_bom_for_products`
深度 2 拉取核实，与 ERP 截图逐字段一致），根因是 `_substitute_groups(bom, so.item_code)`
只扫描 `row.product_id==so.item_code` 的**直接**行，F02N.0233 自己的直接子件（14 行，均为
包材/结构件）没有替代料，替代料关系实际嵌在其半成品子件 S02Y.0207 自己的 BOM 里——
`_substitute_groups` 永远看不到这一层。该函数自身 2026-07-15 落地时的 docstring 已注明
"未见真实需求前是独立后续任务"，本次姚祖怡举证的真实案例即是该"真实需求"。

与 #94（`pipeline.py::compute_forecasts` 幻影组件风险）判定**不同源**：#94 是"替代料行
未过滤、被误当独立组件查 SRM"（发生在 `sc8/pipeline.py`，SC8 交付承诺主流程），#213 是
"替代料分组提取只扫顶层、漏掉嵌套层级"（发生在 `sc8/baoguan.py`，保供看板 BOM 缺口清单）
——文件不同、机制不同、触发路径不同，**不合并处置**，#94 维持独立 P2。

修复本身（让 `_substitute_groups` 递归穿透多层 BOM）会改变缺口/齐套计算的实际输出，
触碰红线，需按 SC8 既有惯例由采购专员重核黄金基准并签字——本轮范围外，留待下轮独立
立项（含 17 个 F 前缀成品的精确影响面核实）。
