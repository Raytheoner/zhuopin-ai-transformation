# CLAUDE.md — SC8 客户订单交期智能承诺（场景级记忆）

> 本文件是 SC8 场景的本地记忆/进度笔记，隔离于其他场景。
> 项目级上下文见仓库根 `CLAUDE.md`；SC8 规划权威见全景规划 §2.1.3 采购部 SC8 行、
> 实施计划 §一采购表、`1-转型规划/0-全景路线图/session接力-Phase1收口.md`。
> 本场景 = CC 建造车间产物；**不改规划文档**（那是 Cowork 的活）。
>
> ⛔ **不要碰 `sc8-real-data-cutover` 变更包**（openspec/changes/sc8-real-data-cutover/）——
> 该变更包仍在进行中（等待 Paul 审核偏差数据），与本记忆文件独立。

## 1. 场景定位

- **场景**：SC8 = 采购部第 8 个数字员工，客户订单交期智能承诺（保供看板 + 对客草稿生成）。
- **全景编号**：全景规划 §2.1.3 采购部 SC8（S1 筑基期旗舰，7-8 月上线）。
- **自动化等级**：L2 — 所有对客承诺必须人工确认，fail-closed 门禁（含低置信/首次承诺/预期晚于目标日）。
- **MVP 范围**：三引擎（intake/scheduling/forecast）+ 置信度 + 启发式 + L2 门禁接线 + 保供看板 Web 服务（Flask，LAN，`0.0.0.0:8090`）+ 保供案例处置中心（SQLite 状态机）。

## 2. 关键决策记录（Paul 拍板）

| 决策 | 结论 | 依据 |
|------|------|------|
| D1：置信度模型 | **二级（高/低）** — 高=全部子件有SRM承诺；低=含无反馈或委外估算 | 简单可解释，IATF 可追溯；三级等真实数据再细化 |
| D2：启发式参数 | **集中到 config.py** — NO_FEEDBACK_LEAD_DAYS=30 / OUTSOURCE_EXTRA_DAYS=10 / LOGISTICS_DAYS=1 / DEVIATION_ALERT_DAYS=3 / PARAM_VERSION 可配 | 阈值是业务参数，集中可配+可审计"用了哪组参数" |
| D3：委外识别 | MVP 用显式维护清单（OUTSOURCE_PRODUCT_IDS）+ 料号前缀规则（OUTSOURCE_PREFIXES） | 预留 `is_outsourced()` 接口，U9C 工艺路线到位后替换 |
| D4：CRM 适配 | 轻适配器 `forecast_to_notice()` → `DelayNoticeInput`，**不收割 DelayCase 状态机** | MVP 不需跨时间案例跟踪；更正关联用 audit + so_id |
| D5：待审批队列 | `FilePendingQueue`（落 `data/pending_approvals.jsonl`，复用平台加锁 JSONL） | 轻量零外部依赖；DB/审批 UI 等规模化再升级 |
| D7：CRM 邮件 prompt | **SC8 场景层注入**，平台保留通用模板 | 对客口径应由业务（Paul）掌控，评审采纳 |
| 保供四色口径 | 🔴 真延期（有承诺仍晚>3天）/ 🟠 待催（子件未答复无确定承诺）/ 🟡 偏紧（确定1-3天）/ 🟢 按期 | Paul 2026-06-24 定，剔除无答复估算、只看确定承诺缺口 |
| L2 触发条件 | 低置信 / 首次给某客户承诺（查 audit 历史）/ 预期晚于目标日 → requires_confirmation=True | IATF L2 人工确认门禁，fail-closed（缺字段被拦） |
| VP_APPROVERS | `{"Paul"}` | B3 审批分级，VP 级审核人 |
| KEY_CUSTOMERS | `{"比亚迪", "上汽", "理想"}` | B3 重点客户/首次承诺→VP 审核（注：实际客户以工程机械/商用车为主，此清单为配置占位，生产环境按实际填） |
| 黄金基准分层口径 | /purchase/answer 按 PO 主源 + 看板辅 + 无反馈+30 兜底 | PR#13 收口，子件覆盖从 9/90 提升到 58/90 |

## 3. 复用底座资产

- **ZpConnector**（ERP BOM）：`zhuopin_platform.shared_tools.erp_connector.connector.ZpConnector.get_bom_for_products()` — A1 TLS 修复已就绪（`U9C_TLS_INSECURE` 逃生开关，real 模式硬禁）；接口返回 `(rows, failed_ids)` 二元组（B1 修复后）。
- **SRM 连接器**：`zhuopin_platform.shared_tools.srm_connector.connector.get_confirmed_dates()` — 返回 `(dict, failed_pos)` 二元组（B2 修复后，None 不计失败）。
- **Notifier**：`zhuopin_platform.shared_tools.notifiers.dispatch.Notifier`（`outbound_enabled` 参数控制，A2 修复；SC8 接 `CUSTOMER_OUTBOUND_ENABLED` 环境变量）。
- **FO 连接器**：SC8 专用 loaders.py，接 FO 正式库（GET /zp/api/ForecastOrder/Query，apiKey 走 URL query，非 OAuth2）。
- **审计**：`zhuopin_platform.audit.AuditLogger`（scenario="SC8"，全链：预测/更正/确认三链可由 so_id 串起）。
- **企微通知**：FO 健康告警 → audit + 企微采购/值班群（内部运维）；对客草稿走 Notifier 门禁。
- **答交可信度子模块**（`sc8/answer_confidence_engine.py` + `sc8/answer_confidence.py`，迁自 SC3，2026-07-06 v2.3 重排）：供应商在途订单风险评估（剩余天数 + DOS 双触发三色分级），29 tests 原样迁移；作为 SC8 交期承诺置信度未来 2→3 级化的判据来源——**当前只是代码归位，尚未接入 SC8 现有承诺/置信度主流程**（`commitment.py`/`forecast.py` 不受影响）。
- **周期累计供需匹配**（`sc8/period_match.py`，2026-07-10，`shortage-baoguan-criteria-v3`）：B2 定稿算法，纯函数 `match_period_cumulative_supply`，接 `sc8/sources.py::load_material_commitments`（真实提取逐笔 SRM 承诺数量）；已接入 `BaoguanRow.period_match`（`assess_supply_risk`/`build_dashboard` 新增可选 `material_commitments` 参数，缺省 None 时零影响）。跨周期"上一期望交付日/结转余额"持久化账本本次未做，调用方需显式传 `previous_demand_date`/`carry_in_balance`，持久化落点是独立后续任务。
- **多层 BOM 递归展开**（B1，2026-07-13/14）：`_gross_need`/`estimate_material_arrivals` 复用平台 `kit_engine.explode_bom`，无条件展开半成品至叶子件（无开关、非 opt-in）。平台底座另有 `kit_engine.explode_bom_with_netting`（逐层现货抵扣，8 tests 已过）**未接入 SC8**，留作未来若要做"半成品有货就不深挖"的可选增强。

## 4. 红线（建造时守住）

> ⚠️ **最高级别红线**：

- 🔴 **`CUSTOMER_OUTBOUND_ENABLED=False`（全程关闭）** — 对客外发闸门。此开关在 `.env`，**未经以下全部条件满足禁止设为 True**：① SRM 接通（携客云 SRM 凭据注入 + 900401 解决）；② L2 人工签字（采购经理 + VP 双签）；③ 通过《SC8 上线前置门禁》6 项检查表；④ `A2 submit_commitment` 首道入队 + `Notifier outbound_enabled` 总开关确认有效；⑤ **主要客户 SQE/采购已沟通知悉交付流程含 AI 环节**（Paul 主谈，Unknowns 登记册 U5，2026-07-05 批准新增）。
- 🔴 **`submit_commitment` 首道一律入队**（requires_confirmation=True 写死，A2 修复），无低风险旁路。
- 🔴 **`approve→send` 幂等**：同一 ID 只发一次（6.1/6.2 任务保障），禁止重复外发客户。
- **L2 门禁 fail-closed**：缺 `requires_confirmation` 字段的请求被拦，不得自动透传。
- 先 mock/脱敏跑通逻辑，再切真实库；真实库接入已在 `sc8-real-data-cutover` 变更包，不在本记忆范围。
- 所有 AI 预测写平台 `audit`（append-only，IATF 3 年留存，含 so_id 可追溯链）。
- OEM 隔离：SC8 读 SRM/ERP 供应商数据，不涉 OEM 技术数据，不强加 OEM 路由（根 CLAUDE.md §4）。
- ISO 26262：SC8 为交期承诺辅助工具，不涉功能安全评级，AI 结论为"交期建议"，对客发送必须人工确认。

## 5. 状态时间线

| 日期 | 状态 |
|------|------|
| 2026-06-10 | SC8 MVP 变更包完成（收割式 MVP）：三引擎 + L2 门禁 + 黄金基准框架 + mock 端到端，归档至 `archive/2026-06-10-sc8-delivery-date-commitment/`。 |
| 2026-06-18 | 安全修复 A/B/C 并入 master（PR#10/#11/#12）：A2 submit_commitment 首道入队 / A1 TLS 校验 / B1 BOM fail-loud / B2 SRM 区分失败/未答 / C1 偏差监控 deviation.py / C2 真实黄金回归落地（3 张真实订单全低置信🔴，确定性偏差=0，real_frozen 不入库）。 |
| 2026-06-24 | FO 正式库接通 + 保供四色口径确定 + 保供预警 Web 服务上线（Flask+waitress，8090，LAN 无鉴权，保供案例处置中心 SQLite）。未结：7.2 LAN 真实联调验收。 |
| 2026-06-18 | SC8/SC1 真实口径收口（PR#13）：分层口径（/purchase/answer 主源）子件覆盖 9/90→58/90；S02Y.0188 瓶颈子件延期+61→+184（待 PMC 核实）。 |
| 2026-07-02 | fix-a/b/c 任务核实（hygiene），全部 [x] 确认代码真实落地。 |
| 2026-07-06 | **答交可信度子模块并入**（采购域 v2.3 重排，`sc-v23-engine-migration`）：SC3 场景编号退役，其在途风险评估引擎（29 tests）原样迁入 `sc8/answer_confidence*.py`，audit `scenario` 由 "SC3" 改标 "SC8"；本次只搬代码，未接线到现有置信度流水线；全量回归 143 passed + 2 skipped，零回归。 |
| 2026-07-10 | **缺料/保供引擎口径改造**（跨桌任务队列 #17，`openspec/changes/shortage-baoguan-criteria-v3`，姚祖怡 07-10 缺料批改会圈选+现场会审 design 定稿）：新增 `sc8/period_match.py`（B2 周期累计供需匹配，会议现场重新定义——按"上次期望交付日次日→本次期望交付日"周期窗口累加 SRM 承诺，不满足时输出逐日可满足曲线，跨周期结转 carry_forward）；`sc8/sources.py` 新增 `load_material_commitments`（真实提取逐笔 SRM 承诺数量，替代原硬编码 `qty_committed=0`）；`BaoguanRow` 新增 `period_match` 字段（纯附加，`material_commitments` 缺省 None 时恒空、零漂移）；`build_dashboard` 新增 `priority_resolver` 框架桩参数（B4，PMC 优先级占用，仅接口未实现真排序）。**同批平台侧改动**（`zhuopin_platform`）：`get_purchase_orders` 新增真实 SRM 确认日期查询（A1，替换 `supplier_confirmed_date=expected_date` 占位）；`kit_engine.py` 新增 `filter_transit_by_arrival`/`bucket_shortage_by_lead_time` 纯函数（A1/A2，不改 `calc_shortage`/`explode_bom` 签名，O2/SC7 零影响）；`get_bom_for_products` **顺带修复生产活 bug**——按 BOM 主记录生效日期区间过滤当前版本，此前无条件取第一条，真实抽样 15 母件中 4 个/27%（S02Y.0035/S02Y.0162/S04Y.0112/S07Y.0137）因此取到过期 BOM 版本算齐套。全量回归：SC8 161+2skip / 平台167+1skip / SC1 53 / O2 20 / SC7 41（黄金基准 35850/640000/675850 精确不漂移），新增 39 tests 零回归。B1（多层递归）排期未定不做，C-1（主料替代料）随 openspec 批2 另案。L/T 数据源缺口登记跨桌任务队列 `#19`。真实数据 LAN 回归为独立后续任务。 |
| 2026-07-13/14 | **B1 多层 BOM 递归展开**（`openspec/changes/archive/2026-07-14-shortage-multilevel-bom-b1`）：姚祖怡批改 SC8净额开关底稿发现"半成品子件未二次分解"（S02Y.0035 瓶颈子件 R02A.0019 藏在未展开的半成品下，按期误判），Paul 现场确认"所有F开头需求的共性问题"、指示排期提前。`sc8/baoguan.py::_gross_need`/`sc8/forecast.py::estimate_material_arrivals` 改为复用 `kit_engine.explode_bom` 无条件递归展开半成品至叶子件（**方案迭代**：最初实现了"新开关`SC8_MULTILEVEL_BOM`+逐层现货抵扣"，开发中发现工作区已有预写测试规格描述更简单方案，经 Paul 确认改用无条件展开、不做净额、无新开关——`explode_bom_with_netting` 保留在平台底座作未来可选增强，本次未接入）。单层 BOM 场景结果与改造前完全一致（向后兼容）；半成品不再被误当作待答交物料查 SRM。全量回归：SC8 170+2skip / 平台175+1skip / SC1 53 / O2 20 / SC7 41（黄金基准精确不漂移），零回归。真实 LAN 环境多层取数性能/限流验证为独立后续任务。同批也排查确认第19-21行"按期误判"与本问题同根因，无需单独修复。 |
| 2026-07-14 | **B1+B3 部署到 51 服务器**：`sync-to-server.ps1` 跑完显示"服务已重启"，但实测**未真正生效**——旧进程（PID 8716，7/6 17:44 启动）仍占用 8091 端口，"重启"步骤的按端口 taskkill 未真正杀掉它（脚本自带的孤儿进程防护这次没起作用，具体时序原因未深挖，🔴 待办：`sync-to-server.ps1` 重启可靠性需要补一次修复，`schtasks /End` 后到 taskkill 扫描之间可能有时序竞争）。手动 `taskkill /F /PID 8716` + `schtasks /Run` 后确认新进程（PID 1756，CreationDate 2026-07-14 11:27）正确起来，curl 验证 HTTP 200、页面正常渲染。**结论：以后每次部署后必须验证进程 CreationDate 是否真的刷新，不能只看脚本打印"服务已重启"就当真**。 |
| **当前** | **SC8 保供看板 LAN 可用（内部）**；对客外发全程关闭；`sc8-real-data-cutover` 变更包待 Paul 审核偏差数据后继续。待办 #10：加登录/Token 鉴权再开外网（真实客户名红线）；🔴 待办：`sync-to-server.ps1` 重启可靠性修复（见上一行 2026-07-14）。 |

## 6. 关键依赖/前置（解锁条件）

- 🔴 SRM 凭据注入本仓库 `.env`（解 900401）— 真实携客云承诺取数前置，阻断 SC8 对客上线。
- 🔴 L2 双签（采购经理 + VP Paul）— 对客外发前置。
- 🔴 SC8 上线前置门禁 6 项检查表全过 — CUSTOMER_OUTBOUND_ENABLED 设 True 的前置。
- 🟡 Web 服务加 Token 鉴权（待办 #10）— 开外网前必须；LAN 内部使用暂不阻断。
- 🟡 PMC 核实 S02Y.0188 瓶颈子件延期判断（+184）— 对客沟通前置。
- 🟡 `CommonEntity/Query` 外网开放（IT）— SC8 全量 cutover（库存/PO/MO/价格）前置；LAN/VPN 过渡。
- 🟡 答交可信度接入置信度 2→3 级化 — 需显式设计"如何加权"（本次迁移不做设计决策，只做代码归位），随 SC8 深化排期，独立后续任务。
- 运行：`python scripts/run_baoguan_web.py`（保供 Web 服务，LAN，0.0.0.0:8090）；答交可信度独立跑：`python -m sc8.answer_confidence`（mock 模式）。
