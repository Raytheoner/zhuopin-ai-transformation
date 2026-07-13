## Context

> **2026-07-10 会议定稿更新**：Paul 与团队现场审 design 时，对 B2/A1/B3 三条给出了比原设计范围更大/更精确的答复，本文档已按定稿更新（见下方各 Decision 与 Open Questions 的"会议定稿"标注）。design 已无阻塞性开放问题，直接进入实现。

姚祖怡 2026-07-10 缺料批改会圈定口径（交接单 `1-转型规划/缺料保供引擎改造交接-2026-07-10.md`）覆盖两个独立引擎：

1. **`kit_engine`**（`5-平台底座/zhuopin_platform/zhuopin_platform/agents/kit_engine.py`）——O2「物料齐套预警」与 SC7「库存优化建议」共用底座。`calc_shortage(gross, inventory, purchase_orders)` 是**纯聚合函数**：`gross` 已经是跨生产计划合并后的单一毛需求字典，函数内部没有任何"需求日期"概念，`in_transit` 只按 `qty_ordered - qty_received` 累加、不看 PO 日期。**SC7 黄金基准（`auto_total=35850`/`review_total=640000`/`grand_total=675850`）是全项目锁定不变量**，任何影响 `calc_shortage` 现有调用结果的改动都不可接受。
2. **SC8 保供**（`sc8/sources.py`/`sc8/forecast.py`/`sc8/baoguan.py`）——按销售订单/预测订单逐单评估齐套，天然有"需求日"（`so.required_date`），当前用 SRM `committed_date` 做到货日估算，但 `qty_committed` 被硬编码为 0（**探测发现不是数据缺口，是没接线**：`srm_connector.py::get_delivery_orders()` 已正确从看板 `answerQty` 提取数量，SC8 自己的 `_extract_board_po_map` 只抽了日期）。

代码探测同时确认：SC7 `purchase_engine.py::calc_material_earliest_dates` 已有先例——**不改 `calc_shortage`，在调用层循环 `explode_bom(bom, [plan])` 逐计划取 `plan.planned_date` 做日期关联**。本设计延续同一模式。

U9C `BOM/Query` 原始响应实测（本 session 生产环境只读探测，15 个真实母件/1324 条子件行）确认 **BOM 主记录**层级（非子件行）带 `m_bOMVersionCode`/`m_effectiveDate`/`m_disableDate` 三字段，`ZpConnector.get_bom_for_products` 目前未提取、且现状代码对多版本返回结果无条件取第一条（见 D3 的活 bug 发现）。

PMC 月度优先级表（B4）**目前没有任何数据源/格式约定**，是真实缺口。

## Goals / Non-Goals

**Goals：**
- A1/A2：为 `kit_engine` 新增到货日过滤 + L/T 分桶两个**纯增量函数**，`calc_shortage`/`explode_bom` 签名与现有行为**零变化**；A1 的到货日字段真接 SRM 确认数据（`ZpConnector.get_purchase_orders()` 新增真实 SRM 查询，见 D1b）。
- B2：SC8 侧实现"周期累计供需匹配"算法（周期窗口+逐笔累计+跨周期结转+不满足时输出逐日可满足曲线），单一需求维度可完整实现；多需求竞争排序沿用 B4 框架桩（见 D2）。
- B3：`get_bom_for_products` 按 **BOM 主记录**的生效日期区间（`m_effectiveDate`/`m_disableDate`）过滤取现行版本，`BomRow` 结构不变；**顺带修复生产环境已发现的活 bug**（现状代码无条件取第一条 BOM 版本，27% 抽样母件因此取到过期版本，见 D3）。
- B4：搭 PMC 优先级占用的框架挂钩点，默认桩＝现状行为（不占用），不做真实抢占逻辑；该挂钩点同时服务 B2 的多需求排序需求。
- 全程 mock/脱敏测试先行，真实回归留待 LAN 环境单独验证（本次不强制在本 session 内跑通真实库）。

**Non-Goals：**
- 不改 `calc_shortage`/`explode_bom` 现有函数签名或默认输出。
- 不实现 B1（多层递归+逐层抵现货）——排期未定，另案。
- 不实现 C-1（主料/替代料合并）——已定稿走批2，另案。
- 不接入 O2/SC7 场景代码去使用新增的 A1/A2 过滤函数（本次只在底座/连接器层提供能力；O2/SC7 目前均为纯 mock，何时切真实数据是独立后续任务，不在本变更包范围）。
- 不实现 PMC 月度表的真实数据接入/格式定义（B4/B2 多需求排序均只搭框架）。
- 不实现 B2 的多需求 PMC 优先级排序（数据源不存在，沿用 B4 框架桩）。
- 不修复 B3 发现的活 bug 之外的其它潜在数据问题（只修"BOM 取错版本"这一项，不做 U9C 数据的全面审计）。

## Decisions

### D1：A1/A2 以「调用层纯函数」形式新增，不碰 `calc_shortage`
- **决策**：在 `kit_engine.py` 新增两个独立纯函数：
  - `filter_transit_by_arrival(purchase_orders, cutoff_date, *, date_field="expected_date") -> list[PurchaseOrder]`：只保留 `date_field ≤ cutoff_date` 的 PO。`cutoff_date` 由调用方传入（SC8/未来场景可传"需求日"；O2/SC7 若采用可传"今天"或计划日）。
  - `bucket_shortage_by_lead_time(shortages, demand_dates, lead_times, today) -> tuple[dict, dict]`：把 `calc_shortage` 输出的缺口按"是否临近"分成 `(urgent, observe)` 两个字典；`lead_times` 缺失的物料兜底进 `urgent`（净需求>0 即追，与交接单口径一致）。
- **为什么不改 `calc_shortage` 本身**：`calc_shortage` 现有调用方（O2 `agent.py`、SC7 `agent.py`）都是**批量单次调用**、`gross` 已丢失 per-plan 日期，若要在内部支持过滤需要破坏性签名变更（新增必填的 demand_date 参数或类似），直接威胁 SC7 锁定黄金基准。新增函数是纯增量、可选调用，零风险。
- **备选方案**：在 `calc_shortage` 加可选 kwarg（如 `cutoff_date=None`，`None`=现状行为）。**否决**：即便设默认值保证向后兼容，仍增加了核心共享函数的复杂度和被误用风险（未来某调用方忘记显式传 `None` 之外的值就可能悄悄改变生产行为），纯函数分离更清晰、职责单一。

### D1b：A1 的"到货日"字段真接 SRM 承诺数据（2026-07-10 会议定稿，方案B）
- **决策**：`ZpConnector.get_purchase_orders()` 新增真实数据链路——对已取到的 PO 清单，按 `(erpNo/po_id, supplyCode/vendor)` 配对，查询携客云 SRM 的答交确认日期（复用 `srm_connector.py::get_confirmed_dates` 或等价方法，与 SC8 `sources.py::load_srm_deliveries` 同一模式），查到就把真值写入 `PurchaseOrder.supplier_confirmed_date`（覆盖现状硬编码 `=expected_date` 的占位行为）；查不到则退回 `expected_date`。`filter_transit_by_arrival` 默认 `date_field` 改为优先用 `supplier_confirmed_date`（有值时），否则退回 `expected_date`。
- **现状确认（探测发现）**：`erp_connector/connector.py:417` 目前是 `supplier_confirmed_date=expected_date` 硬编码，**不是真实 SRM 数据**——本决策是把这行代码换成真实跨系统查询。
- **范围提醒**：本决策只改**平台连接器**（`ZpConnector`，真实可用）。O2/SC7 场景代码目前仍是纯 mock（`o2_kit_shortage`/`sc7_inventory` 都用 CSV loaders，未调用 `ZpConnector.get_purchase_orders()`），本次改造让连接器"支持真实"，但 O2/SC7 何时切换到真实数据模式是另一个独立、已有登记的后续任务，不受本次影响也不依赖本次。
- **风险**：SRM 查询失败/超时不应拖垮 PO 取数主流程——沿用 `srm_connector` 现有"失败不静默、但不阻断其他 PO"的模式（`get_confirmed_dates` 返回 `(confirmed, failed_pos)` 二元组）。

### D2：B2 重新定义为「周期累计供需匹配」算法（2026-07-10 会议定稿，取代原"加总/最新/最大"三选一框架）
- **背景**：会议澄清后，B2 不是简单的"多条记录怎么合并数量"，而是一套按周期滚动、逐笔累计的匹配算法，与 B1（多层累计，排期未定）、B4（多需求 PMC 优先级占用，无数据源）分属同一问题的不同维度——本设计只实现**不依赖 PMC 数据的部分**（单一需求自身的周期累计匹配），多需求排序部分留给 B4 框架桩。
- **决策（单一需求的周期累计匹配，可实现）**：
  1. **周期窗口**：对某次需求（某成品行的月度期望交付日 `D`），周期窗口 = `[上一次期望交付日 + 1天, D]`（例：本次期望交付 7/20 → 窗口 6/21~7/20；无"上一次"时窗口起点按业务侧另行约定，MVP 先用"D 减 1 个自然月"兜底，若与实际不符需后续调整）。
  2. **承诺取数**：窗口内该物料的 SRM 承诺记录，按 `(po/demand_id, vendor)` 配对查询当前确认状态（携客云 `/purchase/answer` 天然只返回当前最新确认值，不含历史修改版本，故"只信最新一次"由数据源本身保证，不需要额外的版本判断代码）。
  3. **累计判定**：按承诺日期升序累加数量；若窗口内累计总量 ≥ 该次需求量 → 输出"可满足"；不足 → 输出：
     - 需求日 `D` 当天累计可满足的数量（可能为 0 或部分）；
     - 从 `D` 起逐日累计（含窗口结束后继续到达的承诺），直到累计量达到需求量为止那一天——一条 `{date: 累计可满足数量}` 的逐日曲线，供保供看板显示"哪天能齐、齐多少"（呼应 C-2 部分齐套显示的展示需求，但本次不复用 C-2 代码，独立实现，避免跨批次耦合）。
  4. **跨周期结转**：当前周期计算前，先扣除"上一周期已经用于满足上一次需求的数量"，避免同一批供应量被两个周期重复计入满足判定（即维护一个"该物料已消耗至某日"的游标，逐周期推进）。
- **决策（多需求优先级，本次不实现，框架桩）**：同一物料、同一时间窗口被多个不同需求（不同 FO/SO）同时竞争时，由 **PMC 人工定的月度优先级表**决定谁先占用——这正是 B4 的范围，**本次沿用 B4 的 `priority_resolver` 挂钩点**（见下方 `stock-inventory-source`/`pmc-priority-allocation` 能力），不在 B2 里另开一套框架。`priority_resolver=None`（默认）时，多个需求各自独立跑上述周期累计匹配，不做占用扣减（即"各算各的"，与现状一致）。
- **落点**：`sc8/forecast.py` 新增周期累计匹配函数（替代/包裹 `estimate_material_arrivals` 里原本"只看日期"的判定），`sc8/baoguan.py::BaoguanRow` 需要新增字段承载"逐日可满足曲线"（或以附加结构返回，不强行塞进现有 `gap_days` 语义）。
- **向后兼容**：`qty_committed` 取不到数据（SRM 无答复）时，判定退回现状"只看日期"（不因为新算法引入而在数据缺失时产生新的误判面）。

### D3：B3 在 `get_bom_for_products` 内部按 BOM 主记录的生效日期区间过滤（2026-07-10 会议定稿，字段更正）
- **⚠️ 探测更正**：原设计误判字段位置——`m_itemVersionCode` 是**子件行自己的版本号**（与"这份 BOM 用哪个版本"无关）；真正的 BOM 版本信息在**母件级 BOM 主记录**（`_u9c_bom_post` 返回列表的每个顶层元素，而非其 `m_bOMComponents` 子件行）：`m_bOMVersionCode`（版本号，如 "A01"/"A02"）+ `m_effectiveDate`（生效日期）+ `m_disableDate`（失效日期）。
- **🔴 生产实测发现活 bug（非本次改造范围内的既有问题，需一并登记/修复）**：`get_bom_for_products` 现有代码对 `_u9c_bom_post` 返回的列表**无条件取 `[0]`**（`bom_item = bom_data[0]`），从不检查是否有多条 BOM 版本、也不判断哪条当前生效。生产环境实测（15 个真实母件）：**4 个（27%）存在多条 BOM 版本记录**（如 S02Y.0035 三版本、S04Y.0112 四版本），且这 4 个母件的**索引 `[0]` 全部是最老、已失效的版本**——即现状代码对这批母件正在使用过期作废的 BOM 去算齐套/缺料，是当前生产环境的真实数据错误，不是"口径未实现"。
- **决策**：`get_bom_for_products`（或其内部 `_u9c_bom_post` 调用点）改为：对返回列表逐条检查 `m_effectiveDate ≤ 今天 < m_disableDate`，取符合此区间的那一条作为当前生效 BOM；该条内的 `m_bOMComponents` 才走原有的 `BomRow(...)` 构造，字段结构不变。
- **风险**：若无任何一条满足区间判定（数据异常/版本空档期），过滤后拿不到 BOM。**缓解**：判定失败时回退取"失效日期最晚（`m_disableDate` 最大）的一条"作为兜底（近似"最新"），并写 audit 记录该异常，不静默返回空 BOM。
- **优先级建议**：鉴于是活跃的生产数据错误（非"口径深化"），建议本次改造里把 B3 排在实现顺序靠前（tasks.md 已按此调整），并在跨桌任务队列 #17 收工登记时单独标注这一发现供 Paul/IT 评估是否需要更紧急的独立修复。

### D4：B4 只搭框架——`stock-inventory-source` 净额快照新增可选 `priority_resolver` 挂钩
- **决策**：`baoguan_service.py`/`baoguan.py` 净额计算处新增一个**可选**参数 `priority_resolver: Callable[[str, list[str]], list[str]] | None = None`（输入物料号+竞争该物料的成品行列表，输出按 PMC 优先级排序的成品行列表）；`None`（默认）＝现状行为（各成品行独立判断现货是否≥自己毛需求，不做跨行占用扣减）。真正的 PMC 月度表解析器留空，作为**独立后续任务**（数据源到位后再实现）。
- **为什么现在就加挂钩点而不是完全不动**：交接单口径本身要求"占用扣减"是未来方向，先留好接口比事后再改判定函数签名风险更低；桩实现保证本次改造对现状**零影响**。
- **2026-07-10 会议定稿补充**：本挂钩点**同时服务 B2 的多需求排序**——B2 的周期累计匹配（D2）在"同一物料被多个需求同时竞争"时，也要靠 PMC 优先级决定谁先算、先扣谁的量，这与 B4 原本要解决的问题是同一件事，不重复建一套框架。未来实现 `priority_resolver` 时，其职责扩展为：先按 PMC 优先级给需求排序，再对每个需求依次跑 D2 的周期累计匹配、扣减已用供应量，传给下一个需求——但**这次仍只搭桩，不实现真实排序**（无 PMC 数据源）。

## Risks / Trade-offs

- **[风险] A1/A2/A1b 新函数与真实 SRM 查询不接入 O2/SC7，实际改造只对 SC8 生效** → 这是本次的既定 Non-Goal（O2/SC7 目前纯 mock，何时切真实数据是独立后续任务），已在 proposal 里写明，不算意外风险，但需要向 Paul/姚祖怡说清楚"这次改造后 O2/SC7 的缺料判定口径暂时不变"，避免预期错位。
- **[风险] B3 生效日期区间判定：若数据异常导致无任何版本满足区间** → 缓解：fail-safe 回退取 `m_disableDate` 最大的一条 + audit 留痕；生产回归时重点抽查本次发现的 4 个多版本母件（S02Y.0035/S02Y.0162/S04Y.0112/S07Y.0137），确认过滤后选中的版本与业务预期一致。
- **[风险] B2 周期窗口"无上一次期望交付日"时的兜底规则（D-1个自然月）可能与业务真实首月情形不符** → 已在 D2 里标注为 MVP 兜底，实现时若姚祖怡/PMC 对"首次"场景有更明确的口径，随时可调整，不影响其余逻辑。
- **[风险] B2 算法输出形状变化（新增逐日曲线）可能影响 `BaoguanRow`/看板前端渲染** → 缓解：以新增字段/附加结构承载，不改动现有 `gap_days`/`risk` 等既有字段语义，前端可选择性展示，不破坏现状看板。
- **[风险] B4 桩实现可能让人误以为"PMC 优先级"（含 B2 多需求排序）已经生效** → 缓解：`priority_resolver=None` 时函数/文档明确注释"框架桩，未生效"，跨桌任务队列 #17 收工登记里注明 B4/B2多需求 状态＝框架，非完整实现。

## Migration Plan

1. 先在 `kit_engine.py`/`sc8/*.py` 分别写测试（TDD），mock 数据验证 A1/A2/B2/B3/B4 桩逻辑。
2. 本地全量回归（平台+O2+SC7+SC8），确认零回归、SC7 黄金基准不漂移。
3. LAN 环境用真实数据跑一次 SC8 侧改造（B2/B3），核对 63 案例对照表里可归因误判是否清零（本次改造不在此 session 内完成，作为后续任务登记）。
4. 完成后 `openspec archive`，跨桌任务队列 #17 状态改"待验收/完成"，回填产出路径。
5. **回滚**：A1/A2/B4 均为纯新增函数/可选参数，未接入现有调用路径时对生产零影响，回滚=不调用/不传参即可，无需数据迁移。B2/B3 是行为变更（SC8 侧），回滚=还原 `sources.py`/`connector.py` 对应函数改动（git revert 级别，无持久化状态需清理）。

## Open Questions

**全部 4 项已在 2026-07-10 会议上由 Paul 定稿，design 无阻塞性开放问题：**

1. ~~B2 数量聚合口径~~ → **改为周期累计匹配算法**（不是简单加总/最新/最大三选一），见 D2。
2. ~~B3 版本号排序规则~~ → **改用 BOM 主记录的 `m_effectiveDate`/`m_disableDate` 区间判定**（比字符串排序更可靠，已用真实数据验证），见 D3；顺带发现现状代码活 bug。
3. ~~A1 的 PO 日期字段~~ → **选 `supplier_confirmed_date`，且要求接真实 SRM 数据**（方案B，非仅字段选择），见 D1b。
4. ~~A2 的 L/T 数据来源时间表~~ → **同意登记**，已加入 tasks.md（不阻塞本次交付）。
