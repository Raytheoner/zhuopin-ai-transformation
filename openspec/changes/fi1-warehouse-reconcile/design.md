## Context

FI1 供应链自动仓库对账是财务旗舰（全景 §FI1），Paul 第一管辖域（供应链）与财务的交叉场景。**SMT 非精准发料**模式下，线体实际投料与 BOM 理论用量持续偏差，加之委外加工商库存需人工盘点，财务+供应链每月多人天逐笔核对、逐笔翻查定位差异。本设计把人工对账转译为数字人**自动差异分析 + 分类 + 出报告**，L2 决策权（异常结案）保留在财务+供应链经理。

**当前状态/约束**：
- 落位 `4-数字员工/财务部/FI1-供应链仓库对账/`，`pip install -e` 平台底座（已 scaffold + imports 全绿）。
- **MVP 仅内部对账**（SMT 投料 vs BOM 理论）；委外库存对账卡 8/15 商务条款 → 二期留接口位；损耗基线趋势模型 → 二期。
- **数据闸现状（2026-06-28 实测）**：BOM 理论用量这条路真通——SC8 已在 LAN 真实跑通 `ZpConnector.get_bom_for_products`（U9C `BOM/Query`，OAuth2），返回 `BomRow` 带 `qty_per_unit`（`m_usageQty`）+ `loss_rate`（`m_scrap`，工艺标准损耗率）。但**投料/出入库/完工(MO) 这条路 webapi 当前取不到**：`get_inventory()` 真实返回 `current_stock=0`，`UFIDA.U9.MO.MO.MO`、`WhQoh.IQueryBinAvailableQty` 走 `CommonEntity/Query`，**外网 404**（仅 `OAuth2/AuthLogin` + `BOM/Query` + `FO/Query` 开放，见 `5-平台底座/连接器收敛设计…md` §外网现状 + 附录 A）。
- **Paul 拍板**：① 损耗口径 = **毛理论 + 差异显性拆分**（用 `m_scrap` 拆标准损耗 vs 超损）；② 黄金基准 = **暂用合成样本**，8/15 真实替换；③ 投料/产出 **最终目标 = U9C 直读（webapi）**，但 **2026-06-29 细化：过渡期保留 CSV 应急桥接**（ERP 定期导出 → 平台加载，已授权，见 S1 复盘 2026-06-25）——避免 9 月试点真实数据完全押在 IT 端点开放上、无兜底；端点一开切 U9C 直读不改对账逻辑。
- 红线（CLAUDE.md §7）：先 mock/脱敏再切真实；所有判定写 audit；L2 超阈值不自动结案；财务红色金额脱敏/仅聚合；AI 结论=对账建议非终局；OEM 隔离不适用财务。

**stakeholders**：Paul（VP，拍板）、财务 AI 对接人（2026-06-29 到位，定差异分类规则/L2 阈值/历史样本验收）、生产/IT（投料/MO entity 与端点开放）、财务+供应链经理（L2 复核结案）、AIOps（建造）。

## Goals / Non-Goals

**Goals:**
- 给定产出数量 + BOM（含 `m_scrap`）+ 实际投料，纯函数算出逐料号理论净用量/标准损耗基线/总差异/差异率，零语义歧义、可解释、可回归。
- 差异自动分类（损耗溢短/来料短缺/管理差异）走数据驱动规则注册表，临时口径占位，对接人定稿即替换、不改引擎。
- 出逐料号库存对账差异报告 + L2 超阈值标"需人工确认"门禁 + 全链审计，对齐 IATF 可追溯。
- BOM 真实读复用 SC8 已验证路径；投料/产出 **最终对接 U9C 直读架构**，**过渡期走 CSV 应急桥接取真实数据**、开发期 mock 夹具，三源（mock/csv/u9c）统一接口、切源零改对账逻辑；U9C 端点未开放时 real-u9c 路径 fail-loud。
- 黄金基准回归（仿 SC8/QD-B）：确定性引擎零偏差为通过标准。

**Non-Goals:**
- 委外加工商库存对账（二期，卡 8/15 商务条款，本期仅留接口位）。
- 损耗基线趋势模型 / 持续监控趋势变化（二期；MVP 先把单期差异算准）。
- MO/领料 CommonEntity 读提升进平台 ZpConnector（端点开放后另起变更；本期场景本地）。
- 财务月结/三单匹配（那是 FI2）；金额台账、跌价测试等其他财务场景。
- 自动结案/对外放行——AI 不做终局决策。

## Decisions

### D1：四能力分层（接入 / 对账引擎 / 差异分类 / 聚合门禁）
- 选 `fi1-feed-source` + `fi1-reconcile-engine` + `fi1-variance-classify` + `fi1-recon-report` 四层，沿用 SC5/QD-B"解析-接入/纯算法引擎/规则注册表/聚合门禁"分层纪律。
- 理由：数据接入（含真实连接器+网络失败模式）、确定性数值计算（可纯单测）、可演进的分类规则（业务口径未定）、L2 聚合与审计，四者失败模式与可测性完全不同，分层使引擎可纯单测、分类规则可独立替换、接入可独立 mock/real 切换，互不污染。
- 备选：单体脚本一把梭——否决，真实连接器与纯计算混在一起无法单测、无法黄金回归。

### D2：毛理论口径 + 损耗显性拆分（Paul 选）
- 理论**净**用量 = Σ_product(产出 qty × BOM `qty_per_unit`)，**不含损耗**；标准损耗基线 = 理论净用量 × `m_scrap`（工艺 BOM 损耗率，作参考基线）；总差异 = 实际投料 − 理论净用量；差异率 = 总差异 / 理论净用量。差异再拆三段：`标准损耗内`（0 < 差异 ≤ 标准损耗基线）/ `超损`（差异 > 标准损耗基线，正向超用）/ `短缺或溢料`（差异 < 0，实际少于理论净用量，疑来料短缺/盘点错）。
- 理由：损耗显性、对账最透明——财务能看到"标准该损耗多少、实际超损多少"，而非把损耗藏进理论用量。`m_scrap` 已在 `BomRow.loss_rate` 现成可用，零额外取数。
- 备选：净理论（理论 = 用量 ×(1+`m_scrap`)，差异只反映超标部分）——否决（Paul 选），损耗不显性、看板信息量低。

### D3：数据接入——BOM 真实复用 ZpConnector；投料/产出 三源统一接口（mock / CSV 应急桥接 / U9C 直读目标）
- BOM：`fi1-feed-source` 直接调平台 `ZpConnector.get_bom_for_products(product_ids, max_depth)`（已验证），消费 `(rows, failed_ids)` 二元组——`failed_ids` 非空则该料号 BOM 残缺、对账标"待人工核"不静默通过（沿用 SC8 B1 纪律）。
- 投料/产出：feed-source 对"产出数量 / 实际投料数量"做统一记录抽象 + 依赖注入，背后三个 loader 由 `data_source` 切换，**切源不改对账引擎/门禁逻辑**：
  - `mock`（默认，开发期）：读贴 U9C 实体 schema 的 mock 夹具，供单测/黄金回归。
  - `csv`（**过渡期真实数据路径**，Paul 2026-06-29 定保留）：ERP 定期导出投料/产出 CSV → 平台加载（已授权，S1 复盘 2026-06-25）；Pydantic 边界校验，字段贴 U9C `MO.FinishedQty`/`MOPickList` 语义，端点开放后弃用不改引擎。
  - `u9c`（**最终目标架构**）：U9C MO 实体 `UFIDA.U9.MO.MO.MO`.`FinishedQty` + 领料 `MOPickList`，经 `CommonEntity/Query`。**外网当前 404** → 端点不可达时 **fail-loud** 抛 `RealEndpointNotReadyError`（复用平台异常），**绝不静默回退 mock/csv**。
- 理由：U9C 直读是最终目标，但端点开放是 IT 侧前置、9 月试点不能完全押在它上面；CSV 应急桥接（已授权）给试点真实数据兜底，三源同一接口、切换零改对账逻辑（同 SC8 sources 依赖注入纪律）。CSV 字段贴 U9C 语义，不引入第二套口径。
- 备选：只做 U9C 直读无兜底——否决（端点 404，9 月试点恐无真实数据）；继续用 `get_inventory()` 的 0 库存——否决，无法对账。

### D4：MO/领料 CommonEntity 读 MVP 暂留 FI1 场景本地，端点开放后提升进 ZpConnector
- 收敛设计已预定"CommonEntity 类实体方法（库存/PO+Receivement/MO/价格表）→ IT 外网开放后**新增到 ZpConnector 内**（加 `_u9c_entity_query` helper），不另起类"。但当前外网 404 + FI1 是这些读的**首消费方**，MVP 先在 `fi1-feed-source` 内实现 MO/领料读（保持与 ZpConnector 一致的 OAuth2/token 复用接口形状），**不动平台 spec**；端点开放且确认真复用时，提升进 ZpConnector 并另起变更修订 `platform-data-connectors`。
- 理由：rule-of-three + 不为 404 端点过早改底座契约；同时保留收敛设计预定的归属方向。**收口-5 交 Paul 确认提升时机。**
- 备选：现在就改 ZpConnector 加 MO 方法——否决，端点 404 无法验证、过早改底座。

### D5：差异分类 = 数据驱动规则注册表，临时口径，对接人 7/31 替换
- 分类规则（损耗溢短/来料短缺/管理差异）做成规则注册表（仿 QD-B rule registry）：每条 `{规则ID, 条件(差异方向/是否在标准损耗内/阈值), 分类档, 严重度, 是否触发 L2}`，元数据以表为单一可信源、版本登记。MVP 用 Paul 临时口径占位，财务对接人 7/31 定稿后替换表、不改分类引擎代码。
- 理由：IATF 单一可信源；业务口径会演进，数据驱动比硬编码易审计易回归。**收口-1 交对接人。**
- 备选：分类标准写死代码——否决，表一改代码即漂移。

### D6：L2 门禁——超阈值标"需人工确认"不自动结案，阈值 configurable，AI 非终局
- 对账结果逐料号过 L2 门禁：差异金额或差异比例超阈值（configurable，对接人定稿）→ 标 `需人工确认`、**不自动结案**；阈值内 → 标 `AI 建议通过` 但仍待经理复核。报告/审计标注"AI 对账建议，结案在财务+供应链经理"。
- 理由：CLAUDE.md §7 红线 L2；财务红色数据决策必须可归责到人。**阈值待收口-1。**

### D7：审计复用底座 AuditLogger，数量为主、金额脱敏
- 每笔对账判定 + 分类写 `zhuopin_platform.audit.AuditLogger`（`AuditEvent(scenario="FI1", action="warehouse_reconcile"/"variance_classify", automation_level="L2", evaluator=<经理>, decision={料号,理论净用量,标准损耗,实际投料,总差异,差异率,分类,是否需人工}, data_sources={bom,mo,feed})`）。decision **以数量/差异率为主**；金额若折算只存**聚合**或脱敏值，**原始单价不落 AI 侧**（红线）。
- 理由：CLAUDE.md §4 单一可信源审计载体（hash-chain，IATF 3 年），勿重建；§7 财务红色数据脱敏。

### D8：OEM 隔离不适用，不接 data_isolation_layer
- FI1 读供应商/ERP 内部数据（BOM/投料/产出），按 CLAUDE.md §4 边界不强加 OEM 路由、不接 `data_isolation_layer`。
- 理由：OEM 隔离只针对研发/含 OEM 信息的质量数据，财务 ERP 内部数据明确不在内。

### D9：黄金基准仿 SC8/QD-B，暂用合成样本，确定性引擎零偏差
- 取合成对账样本（已知差异定位结论的小样本）存 `data/golden/`（合成、可入库；真实件不入库，`.gitignore` 已挡 `real_*`），AI 重跑 vs 预期逐项对比。通过标准：对账引擎（D2 计算）**零偏差**；分类档与预期一致。8/15 历史人工对账到位后替换为真实 golden（收口待对接人）。
- 理由：先用合成 golden 锁住引擎确定性行为不阻塞 8 月开发（Paul 选），真实样本到位再升级可信度。

### D10：损耗基线趋势模型 = 二期 Non-Goal
- 全景 yaml 的"建立损耗基线模型，持续监控趋势变化"明确**二期**；MVP 先把单期差异算准、分类对、报告出、审计全。
- 理由：趋势模型需多期真实数据积累，MVP 无真实数据无从建模；先证伪单期对账正确性。

## Risks / Trade-offs

- **[U9C MO/领料 webapi 外网 404，真实投料/产出取不到]** → **CSV 应急桥接兜底**（D3 `csv` loader，已授权）给 9 月试点真实数据，不押在 IT 端点上；U9C 直读为最终目标，端点开放后切 `u9c` 零改逻辑。「IT 开放 MO/领料/出入库 webapi 端点（或 LAN/VPN）」仍登记为最终直读前置，但不再是试点的阻断项。
- **[差异分类规则/L2 阈值未定，真实结案验收卡住]** → D5/D6 临时口径占位先跑 mock；收口-1 交对接人 7/31，未定前只跑 mock 不上真实结案（就绪清单一.3/一.4）。
- **[产出/完工口径不清——MO.FinishedQty 跨期/在制/批次归属]** → 收口-3 交对接人+生产；MVP 假设"对账期内完工数量"，口径确认前报告标"产出口径待确认"。
- **[实际投料权威源不确定——线体投料 vs 工单领料]** → 收口-4 交 IT/生产确认 entity；feed-source 接口对"实际投料数量"抽象，源切换不改引擎。
- **[BOM 残缺/部分拉取失败致理论用量虚低]** → 复用 ZpConnector `(rows, failed_ids)`，`failed_ids` 料号对账标"待人工核"不静默通过（SC8 B1 纪律）。
- **[财务红色金额泄漏]** → D7 审计数量为主、金额脱敏/仅聚合、原始单价不落 AI 侧；报告默认数量口径，金额折算可选且脱敏。
- **[AI 越权自动结案]** → D6 L2 门禁，超阈值不自动结案，AI 永远"对账建议"，经理复核结案；规则调整走黄金回归。

## Migration Plan

1. **feed-source（mock 先行）**：定义 BOM/投料/产出统一加载接口 + `data_source` 三源开关 + Pydantic 边界校验 + U9C MO 实体 mock 夹具（贴 schema）；BOM 接 ZpConnector。`csv` loader（应急桥接）与 `u9c` loader（fail-loud 占位）同接口实现。
2. **reconcile-engine（先测后实现）**：毛理论/标准损耗/总差异/差异率纯函数，mock 夹具单测，合成 golden 逐项比对。
3. **variance-classify**：规则注册表 + 临时口径分类，每档夹具单测；规则版本登记。
4. **recon-report**：逐料号报告契约 + L2 超阈值门禁 + 写平台 audit + "非终局"标注。
5. **黄金基准回归**：合成 golden 全绿（引擎零偏差）；接口冒烟（real fail-loud 行为验证）。
6. **真实数据验证（过渡期 = CSV 应急桥接）**：ERP 导出投料/产出 CSV → feed-source `csv` 切真实 + BOM 已真实 → 小样本对账，对接人核对账规则、给历史 golden。**最终切换**：IT 开放 MO/领料端点后切 `u9c` 直读，零改对账逻辑。
7. `/opsx:archive` → git push。
- **回滚**：场景独立工程，不动底座 spec、不动其他场景；mock 阶段无真实库副作用；无对外/对客外发面，回滚=停用场景入口。

## Open Questions（🔴 apply 前必须收口，交 Paul + 财务 AI 对接人）

- **收口-1 差异分类规则 + L2 阈值**：分类档判定边界（损耗溢短/来料短缺/管理差异）+ 差异金额/比例人工确认阈值，财务对接人 7/31 主笔。MVP 临时口径占位，真实结案验收待定稿。→ 待对接人。
- **收口-2 标准损耗基准归属**：用工艺 BOM `m_scrap`（Paul 选）还是财务另立标准损耗表？若另立需对接人提供基准表。→ 待对接人确认。
- **收口-3 产出/完工数量口径**：`MO.FinishedQty` 是否=对账期产出？批次/在制/跨期归属如何处理。→ 待对接人 + 生产。
- **收口-4 实际投料权威源 entity**：SMT 线体投料过账 vs 工单领料 `MOPickList`，哪个作"实际投料"权威源 + 字段。→ 待 IT/生产。
- **收口-5 MO/领料 CommonEntity 读提升进 ZpConnector 时机**：端点开放后提升、另起变更修订 `platform-data-connectors`。→ 待 Paul 定时机。
