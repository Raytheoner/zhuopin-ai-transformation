# sc8-quote-qty-date-batch Proposal

## Why

姚祖怡 07-31 验收 BOM 缺口物料清单时提出三个新问题，加上队列 #173（前置 IT 缺口已解除的 #19/#139④ 根治），本批合并交付（四件均触碰保供看板 `sc8/` 同一批文件，同一 session 处理避免分批交付）：

- **#211**：答交数量/日期看板显示与 SRM 真实值不一致（S04Y.0112/R01B.0754：看板 500/2026-08-07，实际 14000/2026-12-25）——07-29 那轮（#152）只处理了"查不到即显示无"，未处理"交货方式"筛选，且累计目标用错了字段。
- **#212**：BOM 缺口物料清单 confirmed_no_transit 状态徽标文案过长，在窄列里视觉溢出、盖住相邻列，姚祖怡"看不清楚"。
- **#213**：BOM 缺口物料清单未考虑 ERP 替代料关系，产生假缺口（F02N.0233/R01A.0707，其替代料 R01A.0012 现货充足却未被计入）——本轮范围仅只读取证，不改判定。
- **#173**：#19（FO 只取核准状态）与 #139④（PO 行级关闭）此前因接口无行级字段无法实现，IT 2026-07-30 已补齐 `LineStatus` 字段，现可根治。

## What Changes

- `sc8/sources.py::_extract_board_commitments`：新增 `receiveType==2`（按排程交货）筛选，剔除 `receiveType==1`（按订单交货）记录——2026-08-03 真实探测确认字段语义与姚祖怡举证案例完全吻合。
- `sc8/baoguan.py::_component_supply_status`：答交数量/日期累计目标从"本项目需求数量"改为"缺口数量"（姚祖怡权威判定原文）。
- `sc8/baoguan.py`：`.cst-tag` 移除强制 `white-space:nowrap`，`confirmed_no_transit` 的解释性注释拆到独立 `.cst-tag-note` 元素，不再挤进同一个不可换行徽标。
- `sc8/loaders.py::parse_forecast_order_rows`：新增按行级 `LineStatus==3`（关闭）剔除 FO 需求行。
- `zhuopin_platform` ERP 连接器：`PurchaseOrder` 新增 `line_no` 字段；新增 `ZpConnector.get_purchase_line_status()`（按料号批量查 `Purchase/Query` 的行级 `LineStatus`）；`sc8/sources.py::load_purchase_orders_by_material` 按 `(po_id, line_no)` JOIN 剔除已关闭行（3/4/5），fail-soft（查询失败不连累既有数量口径）。
- `#213` 只产出只读取证结论（回写队列行），不改任何判定/计算代码。
- **BREAKING**：无。均为在既有函数内新增过滤/修正逻辑，输出结构（字段/JSON schema）不变，净额开关默认行为不变。

## Capabilities

### Modified Capabilities

（本批四项均是对既有 SC8 保供看板展示层与取数层的修正，`openspec/specs/` 下未见对应 sc8-baoguan 系capability spec 文件——延续本场景近期批次一贯做法，`skip_specs: true`，判定与决策留痕在本 proposal + design + CLAUDE.md 场景记忆。）

## 知识资产三问（强制，全景规划 §1.4 第 2 条）

1. **本流程哪些判断是人脑默会经验？** 三处：① SRM "按排程交货 vs 按订单交货"该取哪个——纯业务口径，只有姚祖怡（采购专员）知道正确答案，代码无法自行推断；② 答交数量累计目标该是"需求"还是"缺口"——同样是业务口径判断，姚祖怡原话逐字澄清；③ #213 替代料是否该纳入齐套判定、纳入后对四色风险的影响——涉及缺口计算口径变更，超出本次授权范围，需专员重核黄金基准（同 `SC8_NET_INVENTORY` 翻 ON 先例）。
2. **由谁显性化？** 持有人＝姚祖怡（采购部 AI 专员，07-31 回件逐条给出权威判定）；backup／仲裁＝Shao Peishen（OPVP，08-03 拍板 §四#42 选 (b) 确定本轮范围）；登记进 `6-人才与组织/部门AI专员跟进/` 跟进信台账。
3. **用什么方法提取？** 判例批改法（姚祖怡 07-31 回件逐条对照真实案例给出"现状判定 vs 正确判定"）+ 真实数据取证反推（本次对 SRM/ERP 连接器做只读实测，确认 `receiveType`/`LineStatus` 字段语义，而非凭假设编码）。

## 验收与晋档条件（强制，四档口径）

- **本变更包交付后场景所处档位**：档3 内部服务不变（SC8 保供看板已在 `.51:8091` 生产运行供内部试用，本次是缺陷修正批次，非首次上线）。
- **晋下一档的条件**：不适用（对客交付/档4 前置条件——L2 双签、6 项门禁检查表、客户 SQE 沟通——均未满足，本批不改变对客外发闸门状态，`CUSTOMER_OUTBOUND_ENABLED` 维持关闭）。
- **价值指标**（质量型）：BOM 缺口物料清单答交数量/日期与 SRM 供应计划看板真实值一致率（基线：07-31 举证的 1 个已知错误案例，目标：#211 修复后同类案例归零）；FO/PO 在途误判率（#173 修复前后行数对照，交付时给出具体数字）。
- **LLM 判据黄金集**：不适用（本变更不含 LLM 运行时判断）。

## Impact

- 受影响代码：`4-数字员工/采购部/SC8-客户订单交期智能承诺/sc8/{sources.py,baoguan.py,loaders.py,baoguan_service.py}`、`scripts/run_baoguan_dashboard.py`；`5-平台底座/zhuopin_platform/zhuopin_platform/shared_tools/models.py`、`.../erp_connector/connector.py`。
- 红线核对：mock 先行——不适用（无新数据源接入，复用既有 SRM/ERP 连接器新增字段）；audit 留痕——沿用既有 `ConnectorAudit`/`AuditLogger`，新增连接器方法（`get_purchase_line_status`）复用 `_fi_request` 既有审计路径；OEM 隔离——不适用（供应商/采购数据，非 OEM 技术数据）；L2 人工确认门禁——不适用（本批不涉及对客承诺自动发送）；ISO 26262——不适用。
- **#213 明确不改判定逻辑**——四色风险/齐套/缺口计算口径本批不变，红线不动。
