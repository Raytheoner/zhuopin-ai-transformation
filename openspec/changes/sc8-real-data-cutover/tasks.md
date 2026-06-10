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
- [ ] 5.2 **〔待 Paul〕** 核对预测交付日 vs 实际承诺/到货：S02Y.0162 → 2026-08-05（延 36 天），F02N.0184 → 2026-07-21（延 36 天），均低置信（SRM 缺席，符合预期）。确定性日期加减经手工复核一致；待 Paul 在 PR 审核中确认偏差可接受。
- [x] 5.3 抽查全链 audit：`data_sources={fo:real,bom:real,srm_committed:mock}`、`confidence=低`、`param_version=sc8-params-v0`、hash-chain `prev_hash` 在位，可追溯。

## 6. 收尾
- [x] 6.1 全部测试绿：41 passed + 2 real-integration passed，mock 黄金回归无退化。
- [ ] 6.2 archive 变更 + 开 PR（一并 add `1-转型规划/SC8真实库切换就绪检查清单.md`、`0-学习与工具/携客云SRM-OpenAPI核实与申请要点.md`），停下等 Paul 审，**先不合 master**。

---
**完成定义（本期）**：FO+BOM 真实源接通、门禁真阻塞、内部小样本验证确定性零偏差、mock 黄金回归无退化、全链审计可追溯。**对真实客户外发开关保持关闭**，待 SRM 联调通过 + 真实黄金对账后另议。
