# Tasks — SC8 真实切换（sc8-real-data-cutover）

> 6/11 提前开工。承接 SC8 MVP（已归档 2026-06-10）。**真实客户外发的最终闸。**
> design.md 已 Paul 审过（D1–D6 全通过，Open Questions 已拍板）。
> 工作流：先写测试再实现；切真实前过黄金基准；全程不跳门禁。
> **本期 = 部分切换（D1）**：FO+BOM 真实、SRM 降级 mock、内部验证不外发。
> **对真实客户外发开关全程关闭**，直到 SRM 联调通过 + 真实黄金基准零偏差 + 门禁 6 项全勾。

## 1. 底座加固（依赖，不在本变更重做）
- [x] 1.1 确认 `platform-hardening-p2`（Pydantic 边界校验 / SRM 限流退避 / SecretsProvider / audit hash-chain）已完成（4 节任务全 `[x]`）；本变更**依赖**之，§1 原 4 项不重做。〔注：platform-hardening-p2 仍在 active，需另行归档〕

## 2. 真实连接器接入（D2 / D3）
- [x] 2.1 收割 FO 连接器进 SC8 `loaders.load_forecast_orders_from_api`（命中 ZpViewSO），`parse_forecast_order_rows` 做 **Pydantic 边界校验**（缺 DocNo/ItemCode/ShipPlanDate → 显式报错挡脏数据），保留 `MVP_ITEM_PREFIXES`（F/S/Y/X）过滤。测试 `test_fo_loader.py`。
- [x] 2.2 数据源开关 `config.data_source_mode`（`SC8_DATA_SOURCE=mock|real`）+ `config.srm_source_mode`（`SC8_SRM_SOURCE`，本期固定 mock）；`sources.py` 真实拉取（FO + `ZpConnector.get_bom_for_products` + `XkySrmConnector` 降级）。测试 `test_sources_and_audit.py`。
- [x] 2.3 `pipeline.compute_forecasts(data_sources=...)` → `_record_forecast` 按源如实标记（`fo=real, bom=real, srm_committed=mock`）；不传则默认全 mock（向后兼容）。测试已验证审计留痕。
- [x] 2.4 委外维护清单可经 `SC8_OUTSOURCE_IDS` env 注入（`config.outsource_ids_from_env`，与常量取并集）；**不臆造料号**，真实料号待 PMC 确认 / U9C 工艺路线 `IsSubContract`（接口缝 `is_outsourced_by_routing` 已留）。

## 3. 客户隔离 + 门禁真阻塞（D4 / D5）
- [x] 3.1 客户隔离键 `config.customer_isolation_key`（`ISOLATION_KEY_FIELD="customer_name"`，可一处切 customer_id，空值回退客户名）；审计冗余记录 `customer_name`/`customer_key`。测试 A/B 客户不串。
- [x] 3.2 L2 真阻塞：平台 `Notifier.send` fail-closed（已有）+ `dispatch.route_forecast` **一律入待审批队列、绝不自动外发**；`FilePendingQueue.approve` 无 `confirmed_by` 拒放行。测试 `test_dispatch_block.py`。
- [x] 3.3 `dispatch.route_forecast` real 模式**强制关闭对客外发**（无视调用方误传）+ 总开关 `CUSTOMER_OUTBOUND_ENABLED=False` 全程关。测试覆盖。
- [x] 3.4 CRM 结构性核验：测试断言 `crm_notifier.draft` 无任何「发客户」函数（仅草稿）；审计记录**置信度分类（高/低）** + `requires_confirmation` + `sent=False`。
- [x] 3.5 回退/更正：低置信/数据异常一律转人工不外发（gate 低置信→requires_confirmation；连接器 `ConnectorValidationError` 异常即 raise，不入队不外发）；`build_correction_draft` 走同一门禁关联 so_id；授权人 = VP 或指定供应链计划负责人（design D6 引用 Cowork 侧 `3-治理与合规/` 回滚 SOP）。

## 4. 真实集成测试 + mock 黄金回归（先写测试后实现）
- [x] 4.1 真实集成测试 `test_real_integration.py`（FO+BOM 真实、SRM mock）：默认跳过，`SC8_RUN_REAL=1` + 凭据下运行，本次实跑 **2 passed**（schema/前缀/BomRow 校验通过）。
- [x] 4.2 mock 黄金回归 `test_golden.py` 仍全绿（确定性零偏差），真实化**无退化**。
- [x] 4.3 启发式 v0 初值维持（无反馈 +30 / 委外 +10 / 物流 +1 / 偏差 3 天），SRM 通后真实对账再校准。

## 5. 小样本真实验证（放量前必做，不外发）
- [x] 5.1 `sc8/run.py` 跑 2 张真实订单（FO2026050001：S02Y.0162 / F02N.0184），FO+BOM 真实、SRM mock，结果**全部入待审批队列、未外发**（pending=2，outcome=queued）。
- [x] 5.2 **超越（2026-07-15）**：本条原等 Paul 在 PR 审核中核对偏差——PR 从未开（见 6.2），本条实际未走到审核环节。**Paul 2026-07-15 直接拍板**"能用真实数据尽量早切换真实，如有问题累计给姚祖怡排查"，等同以更宽松的口径整体批准继续推进真实切换，本条不再单独要求 PR 审核这一具体动作；SRM 真实数据的对齐核验改走新流程（见 `4-数字员工/采购部/SC8-客户订单交期智能承诺/CLAUDE.md` 2026-07-15 起的状态记录）。
- [x] 5.3 抽查全链 audit：`data_sources={fo:real,bom:real,srm_committed:mock}`、`confidence=低`、`param_version=sc8-params-v0`、hash-chain `prev_hash` 在位，可追溯。

## 6. 收尾
- [x] 6.1 全部测试绿：41 passed + 2 real-integration passed，mock 黄金回归无退化。
- [x] 6.2 **改为直接归档，不开 PR**（2026-07-15）：本条原计划"开 PR 停下等 Paul 审、先不合 master"，但本变更包自 6 月建立后长期未推进（FO/BOM 真实等有效成果已被 2026-07 起的多个后续变更包——`stock-api-inventory-source`/`shortage-baoguan-criteria-v3`/`sc8-baoguan-substitute-partial-kit` 等——各自独立提议、审核、合入 master，事实上已承接并超越本变更包大部分范围）。Paul 2026-07-15 拍板"已并入主线的功能保留、未实现且已过时的功能关闭"，判定：① BOM 真实/客户隔离/L2 门禁真阻塞/审计留痕——已并入主线（见上方各任务标注的落点，代码活跃在用）；② 委外识别 U9C 工艺路线真实化（`is_outsourced_by_routing`，任务 2.4）——未实现，接口缝已留但一直用维护清单兜底运行良好，判定过时降级为独立 backlog（不在本变更包续做）；③ 凭证 Vault/K8s Secrets 动态注入（`SecretsProvider` 协议已就绪，真实 Vault 后端未接）——未实现，同样判定为独立 backlog；④ SRM 真实切换——**未实现但不过时**，2026-07-15 已验证 900401 阻塞解除、技术上可行，接续工作转到新的真实数据推进（不复用本变更包，见 SC8 CLAUDE.md）。综上：直接归档本变更包，不单独开 PR。

---
**完成定义（本期，原定义，供历史参照）**：FO+BOM 真实源接通、门禁真阻塞、内部小样本验证确定性零偏差、mock 黄金回归无退化、全链审计可追溯。**对真实客户外发开关保持关闭**，待 SRM 联调通过 + 真实黄金对账后另议。**实际结果（2026-07-15 归档时）**：FO+BOM 真实接通与门禁/审计部分已通过后续变更包合入 master 生效；对客外发开关仍按设计保持关闭；SRM 真实切换未在本变更包完成，接续工作见 SC8 CLAUDE.md。
