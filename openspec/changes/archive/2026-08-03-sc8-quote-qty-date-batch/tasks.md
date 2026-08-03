# sc8-quote-qty-date-batch Tasks

## #211 答交数量/日期口径 v2
- [x] 真实探测 SRM 供应计划看板 `receiveType` 字段语义（R01B.0754 案例交叉验证）
- [x] `_extract_board_commitments` 新增 `receiveType==2` 筛选
- [x] `_component_supply_status` 累计目标改为 `gap_qty`
- [x] 新增/更新测试（`test_material_commitments.py`、`test_baoguan_bom_gap_eight_fields.py`）

## #212 BOM 缺口清单显示修复
- [x] 定位 `.cst-tag` white-space:nowrap 溢出根因
- [x] CSS 修复 + `CST_NOTE` 拆分 + Excel 导出补注释
- [x] 全站同类风险点排查（确认仅 `.cst-table` 一处）
- [x] 新增渲染测试

## #173 FO/PO 行级 LineStatus
- [x] 真实探测 FO `ForecastOrder/Query` 的 `LineStatus` 字段（真实单号验证 120 行核对）
- [x] `loaders.py` 新增行级过滤（`FO_LINE_STATUS_CLOSED`）
- [x] 真实探测 PO `Purchase/Query` 的 `LineStatus` 字段（确认与 `ZpViewPurOrder` 是不同端点）
- [x] `PurchaseOrder.line_no` + `_ZpPurOrderRow.erpLineNo` + `get_purchase_line_status()`
- [x] `load_purchase_orders_by_material` 按 `(po_id, line_no)` JOIN 剔除关闭行（fail-soft）
- [x] 新增测试（FO/PO 各自 loader + connector 层）
- [x] 改造前后行数对照（真实数据：FO 120→106；PO 20→19料号/38070→37353件，6料号变化）

## #213 替代料假缺口只读取证
- [x] 真实验证 F02N.0233→S02Y.0207→R01A.0707/R01A.0012 BOM 结构
- [x] 真实库存核实（R01A.0707/R01A.0012）
- [x] 根因定位（`_substitute_groups` 单层扫描限制）
- [x] 影响面估算（真实 FO 数据 F/S 前缀分布）
- [x] 与 #94 同源判定（结论：不同源，不合并）
- [x] 结论回写队列 #213/#94 行

## 收口
- [x] 全量回归零漂移（SC8/平台/SC1/SC7/O2）
- [x] openspec 归档
- [x] 场景 CLAUDE.md 更新
- [x] 部署 `.51:8091` + 冒烟（含改造前后行数对照产出，NEW_PID=8964）
- [x] 给姚祖怡起草上线跟进信（采购部#10，md+docx），Shao Peishen 已批准并发送（机器人私信+docx+采购部群webhook通报）
- [x] commit + push
- [x] 队列 #211/#212/#213/#173/#94 五行回写（协议〇.7 编辑锁）
