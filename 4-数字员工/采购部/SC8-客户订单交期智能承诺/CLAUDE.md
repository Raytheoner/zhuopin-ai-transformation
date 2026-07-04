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

## 4. 红线（建造时守住）

> ⚠️ **最高级别红线**：

- 🔴 **`CUSTOMER_OUTBOUND_ENABLED=False`（全程关闭）** — 对客外发闸门。此开关在 `.env`，**未经以下全部条件满足禁止设为 True**：① SRM 接通（携客云 SRM 凭据注入 + 900401 解决）；② L2 人工签字（采购经理 + VP 双签）；③ 通过《SC8 上线前置门禁》6 项检查表；④ `A2 submit_commitment` 首道入队 + `Notifier outbound_enabled` 总开关确认有效。
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
| **当前** | **SC8 保供看板 LAN 可用（内部）**；对客外发全程关闭；`sc8-real-data-cutover` 变更包待 Paul 审核偏差数据后继续。待办 #10：加登录/Token 鉴权再开外网（真实客户名红线）。 |

## 6. 关键依赖/前置（解锁条件）

- 🔴 SRM 凭据注入本仓库 `.env`（解 900401）— 真实携客云承诺取数前置，阻断 SC8 对客上线。
- 🔴 L2 双签（采购经理 + VP Paul）— 对客外发前置。
- 🔴 SC8 上线前置门禁 6 项检查表全过 — CUSTOMER_OUTBOUND_ENABLED 设 True 的前置。
- 🟡 Web 服务加 Token 鉴权（待办 #10）— 开外网前必须；LAN 内部使用暂不阻断。
- 🟡 PMC 核实 S02Y.0188 瓶颈子件延期判断（+184）— 对客沟通前置。
- 🟡 `CommonEntity/Query` 外网开放（IT）— SC8 全量 cutover（库存/PO/MO/价格）前置；LAN/VPN 过渡。
- 运行：`python scripts/run_baoguan_web.py`（保供 Web 服务，LAN，0.0.0.0:8090）。
