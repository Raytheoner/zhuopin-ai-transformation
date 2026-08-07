# sc8-baoguan-answer-tristate-substitute-display Proposal

## Why

姚祖怡 2026-08-06 第四次举证（队列 #296／#297，前三轮见 #211/#212/#213/#173 →
#262/#263）：`S02Y.0035` 的缺口物料 `R01D.0015`／`R02A.0019`，答交数量/日期仍显示
「无」，且 `R02A.0019` 的"状态"列显示"有未交订单已答交"是错的（SRM 侧该单据实际
是"待答交"）。**本次她首次书面给出完整的 SRM 单据状态三态判据**（此前从未定义
过，我方一直在猜）：SRM 供应计划看板单据状态共"差异已确认"／"无差异"／"待答交"
三种；"待答交"的单据答交数量/日期应显示"无"，"差异已确认"/"无差异"的单据答交
数量应为数字型（含 0）。核心缺陷一句话：**「无」（查无答交）与 `0`（已答交但答 0）
此前被混为一谈**；另一处错误是"已答交/未答交"状态判定挂错了源。

同时她提出一项新展示需求（#297，不在 #263 范围内）：BOM 缺口物料清单里的替代料应
**并列展示**在主料下方一行（8 字段与主料取值规则一致），而不是只隐式合并进齐套
判定看不见。

## What Changes

### #296 · 答交口径 v4 + 三态判据落地

- `sc8/sources.py::_extract_board_commitments`：**根因已用真实凭据实测坐实**——
  供应计划看板 `itemList` 条目只有 `answerQty`/`planQty` 两个数字字段，**没有**
  独立的"单据状态"字符串字段（763 条真实 record／1302 条 item 全字段枚举确认）。
  她描述的三态由 `answerQty` 是否为 `None` 与是否等于 `planQty` 派生：
  `answerQty is None` → 待答交；`answerQty is not None`（含 `0`）→ 已答交
  （差异已确认/无差异，两者对本次展示逻辑等价，均需显示实际数字）。当前实现
  `int(item.get("answerQty") or 0); if answer_qty <= 0: continue` 把 `None` 和
  `0` 一并跳过是本次核心 bug 根因（真实数据：223 个 item 的 `answerQty is None`，
  669 个 item 的 `answerQty == 0`——后者此前被误当"无记录"丢弃）。
- `sc8/baoguan.py::_component_supply_status`：**状态列判定改挂 SRM 单据状态**
  ——当前"已答交/未答交"（`confirmed` 标志）来自 `mat.no_feedback_materials`
  （旧 `/purchase/answer`+看板最早日期 60 天窗口口径），与驱动⑦⑧答交数量/日期
  的 `material_commitments`（`receiveType==2` 口径）是两条不同管线，产生
  `R02A.0019` 这类"答交数量/日期显示无、但状态却显示已答交"的自相矛盾。改为
  `confirmed` 直接由 `material_commitments.get(m)`（同一管线，同一份数据）是否
  存在有效记录派生，与⑦⑧同源。
- `sc8/config.py`：`material_commitment_lookahead_days()` 默认值 180→365 天
  （姚祖怡明确要求）。**真实成本已测**：`_chunk_date_windows` 从 3 段增至 6 段
  （非"约7段"，实测 6 段），`/receiveBoard/queryList.json` 进程级令牌桶
  1 req/30s 与 `load_srm_deliveries` 共享，多出 3 次顺序调用最坏情形增加约 90
  秒等待——与既有 180 天口径"约 60 秒排队、与 BOM 多层递归同数量级可接受"的
  先例同量级，判定可接受、不升级 §四（详见 design.md D3）。
- **范围仅限本函数/本状态派生链**，不影响 `_extract_board_po_map`/
  `load_srm_deliveries` 驱动的既有 kit_date/gap_days/四色风险判定口径（红线不动，
  同 #211 v2、#262 先例）。
- 全量口径复核对照表（她第三次重申的"整体复核一遍"）随 apply 阶段真实数据产出，
  落 `docs/queue_296_tristate_audit.md`（不落 `reports/`，见队列 #267 教训）。

### #297 · BOM 缺口物料清单替代料并列展示

- `sc8/baoguan.py::_component_supply_status`：对已在缺口清单中的每条主料行，若
  `_substitute_groups()` 命中其替代料，紧随其后追加一行"替代料展示行"——复用
  同一份 8 字段计算逻辑（状态/可用现货/答交数量/答交日期均取替代料自身在
  `inventory`/`purchase_orders`/`material_commitments` 中的数据），**本项目需求
  数量沿用主料行的需求量**（与她给的模板逐字段吻合：主料/替代料两行 qty 相同、
  avail/status/gap 各自独立），**不参与既有 `_covered_by_stock`/`_kittable_qty`
  聚合计算、不改变主料行是否出现在清单中的既有过滤口径**（红线：#263 已完成的
  跨层级替代料齐套判定不受影响，本次纯展示层追加）。
- `ComponentSupplyStatus` 新增 `role`（`""`=主料/无替代关系、`"primary"`=有替代
  料的主料、`"substitute"`=替代料展示行）；前端 `componentStatusHtml` 按
  `role` 追加「（主料）」「（替代料）」文案。
- **BREAKING**：无。`ComponentSupplyStatus` 新字段有默认值，向后兼容；JSON
  序列化新增键，前端未知键静默忽略；单层 BOM/无替代料场景零漂移。

## Capabilities

### Modified Capabilities

延续本场景近期批次一贯做法（#262/#263/#211-#213 均未见对应
`openspec/specs/sc8-baoguan-*` 单独 spec 文件，判定与决策留痕在 proposal+design+
CLAUDE.md 场景记忆），本次仍 `skip_specs: true`。

## 知识资产三问（强制，全景规划 §1.4 第 2 条）

1. **本流程哪些判断是人脑默会经验？** 三处：① SRM 单据"待答交/差异已确认/无差异"
   三态与 API 字段（`answerQty`/`planQty`）的映射关系——纯业务口径，只有姚祖怡
   （采购专员）看得到 SRM 系统界面本身的状态标签，代码只能反推派生；② 365 天前瞻
   窗口是否够用、限流代价是否可接受——业务判断（她要多远的前瞻期）与工程判断
   （限流成本）的交叉点；③ 替代料并列展示的字段取值规则（"与主料一致"）——她的
   业务口径，非工程可自行推断。
2. **由谁显性化？** 持有人＝姚祖怡（采购部 AI 专员，08-06 回件首次书面给出完整
   三态判据）；backup／仲裁＝Shao Peishen（OPVP）；登记进
   `6-人才与组织/部门AI专员跟进/` 跟进信台账（含 §四#55 悬空签字并入下一封信）。
3. **用什么方法提取？** 判例批改法（她举证 `R01D.0015`/`R02A.0019`/`F02N.0242`/
   `R01A.1459` 四个真实案例，原话给出正确判据与展示模板）+ 真实数据取证反推
   （本次对 SRM `get_receive_board` 做只读实测，穷举全字段确认三态无独立字段、
   由 answerQty/planQty 组合派生，而非凭假设编码）。

## 验收与晋档条件（强制，四档口径）

- **本变更包交付后场景所处档位**：档3 内部服务不变（`.51:8091` 已在生产运行供
  内部试用，本次为缺陷修正+展示增强批次，非首次上线）。
- **晋下一档的条件**：不适用（对客交付/档4 前置条件——L2 双签/6 项门禁/客户 SQE
  沟通——均未满足，本批不改变 `CUSTOMER_OUTBOUND_ENABLED` 关闭状态）。
- **价值指标**（质量型）：BOM 缺口物料清单答交数量/日期与 SRM 真实值一致率
  （基线：她本次举证的 2 个已知错误案例 `R01D.0015`/`R02A.0019`，目标：修复后
  两案例归零 + 全量料号口径复核对照表零新增偏差）；替代料信息可见度（基线：0，
  目标：BOM 缺口清单每条有替代关系的主料行均可见替代料并列数据）。
- **LLM 判据黄金集**：不适用（本变更不含 LLM 运行时判断）。

## Impact

- 受影响代码：`4-数字员工/采购部/SC8-客户订单交期智能承诺/sc8/{sources.py,baoguan.py,config.py}`。
- 红线核对：mock 先行——不适用（复用既有 SRM 连接器，无新数据源）；audit 留痕——
  沿用既有 `ConnectorAudit`；OEM 隔离——不适用（供应商/采购数据）；L2 人工确认
  门禁——不适用；ISO 26262——不适用。
- **本批不改变四色风险判定/净额/缺口聚合计算结果**——#296 只改答交展示与状态列
  取数源（均为展示派生字段），#297 只做展示层追加，均不触碰 `_covered_by_stock`/
  `_kittable_qty`/`gap_days`/`_classify` 等判定核心；交付须含黄金基准重跑
  counts 不变的显式证明。
