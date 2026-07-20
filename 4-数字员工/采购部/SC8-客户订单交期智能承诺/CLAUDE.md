# CLAUDE.md — SC8 客户订单交期智能承诺（场景级记忆）

> 本文件是 SC8 场景的本地记忆/进度笔记，隔离于其他场景。
> 项目级上下文见仓库根 `CLAUDE.md`；SC8 规划权威见全景规划 §2.1.3 采购部 SC8 行、
> 实施计划 §一采购表、`1-转型规划/0-全景路线图/session接力-Phase1收口.md`。
> 本场景 = CC 建造车间产物；**不改规划文档**（那是 Cowork 的活）。
>
> ~~⛔ 不要碰 `sc8-real-data-cutover` 变更包~~ **已解除（2026-07-15）**：该变更包长期搁置未推进，
> 有效成果（FO/BOM 真实、门禁真阻塞、审计留痕）已被后续变更包承接合入 master；Paul
> 2026-07-15 拍板"已并入主线的保留、未实现且过时的关闭"，已归档
> `archive/2026-07-15-sc8-real-data-cutover/`（委外真实路线识别、Vault 凭证管理降级为独立
> backlog；SRM 真实切换未过时，接续工作见下方状态时间线）。

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
- **替代料等价合并 + 部分齐套**（C-1/C-2，2026-07-15，`sc8-baoguan-substitute-partial-kit`）：`sc8/baoguan.py::_substitute_groups`（按 `product_id`+`sequence` 分组主料/替代料，仅扫描 `so.item_code` 直属行）+ `_kittable_qty`（可齐套套数，与净额开关同一入口）。`BomRow` 新增 `sequence`/`is_substitute` 字段（平台底座，向后兼容），`get_bom_for_products` 新增提取 BOM 主件行项次/子项类型 + 读取嵌套替代料列表 `m_bOMCompSubstituteDTO4CreateSv`。`BaoguanRow` 新增 `substitute_groups`/`kittable_qty`/`kittable_bottleneck`/`kittable_shortfall` 四字段，`row_to_dict`/`_HTML_JS` 卡片渲染同步显示"可齐套 X/总需求"徽标+"含替代料 Rxx"标注。**替代料用量取值口径（2026-07-15 真实数据验证确认）**：替代料 DTO 自带的 `m_usageQty`/`m_scrap` 恒为占位值（`1.0`/`0.0`，与主件行真实用量无关），代码**恒继承主件行的 `qty_per_unit`/`loss_rate`**，不采信替代料自身字段（7 母件/20 组真实样本 100% 一致，无反例）。

## 4. 红线（建造时守住）

> ⚠️ **最高级别红线**：

- 🔴 **`CUSTOMER_OUTBOUND_ENABLED=False`（全程关闭）** — 对客外发闸门。此开关在 `.env`，**未经以下全部条件满足禁止设为 True**：① ~~SRM 接通（携客云 SRM 凭据注入 + 900401 解决）~~**已满足（2026-07-15）**——凭据已在 `.env`、900401 阻塞已解除，真实只读实测 `get_receive_board`/`get_confirmed_dates` 均可用（详见状态时间线）；② L2 人工签字（采购经理 + VP 双签）；③ 通过《SC8 上线前置门禁》6 项检查表；④ `A2 submit_commitment` 首道入队 + `Notifier outbound_enabled` 总开关确认有效；⑤ **主要客户 SQE/采购已沟通知悉交付流程含 AI 环节**（Paul 主谈，Unknowns 登记册 U5，2026-07-05 批准新增）。**②③④⑤ 仍未满足，对客外发闸门维持关闭不变**——①满足只是 SC8 内部预测可以用真实 SRM 数据，与"能否对客户外发"是两件事。
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
| 2026-07-10 | **缺料/保供引擎口径改造**（跨桌任务队列 #17，`openspec/changes/shortage-baoguan-criteria-v3`，姚祖怡 07-10 缺料批改会圈选+现场会审 design 定稿）：新增 `sc8/period_match.py`（B2 周期累计供需匹配，会议现场重新定义——按"上次期望交付日次日→本次期望交付日"周期窗口累加 SRM 承诺，不满足时输出逐日可满足曲线，跨周期结转 carry_forward）；`sc8/sources.py` 新增 `load_material_commitments`（真实提取逐笔 SRM 承诺数量，替代原硬编码 `qty_committed=0`）；`BaoguanRow` 新增 `period_match` 字段（纯附加，`material_commitments` 缺省 None 时恒空、零漂移）；`build_dashboard` 新增 `priority_resolver` 框架桩参数（B4，PMC 优先级占用，仅接口未实现真排序）。**同批平台侧改动**（`zhuopin_platform`）：`get_purchase_orders` 新增真实 SRM 确认日期查询（A1，替换 `supplier_confirmed_date=expected_date` 占位）；`kit_engine.py` 新增 `filter_transit_by_arrival`/`bucket_shortage_by_lead_time` 纯函数（A1/A2，不改 `calc_shortage`/`explode_bom` 签名，O2/SC7 零影响）；`get_bom_for_products` **顺带修复生产活 bug**——按 BOM 主记录生效日期区间过滤当前版本，此前无条件取第一条，真实抽样 15 母件中 4 个/27%（S02Y.0035/S02Y.0162/S04Y.0112/S07Y.0137）因此取到过期 BOM 版本算齐套。**历史影响已排查（2026-07-14）**：姚祖怡核实这 4 个母件在受影响窗口（2026-06-24 上线真实 BOM 数据 ~ 2026-07-10 修复）内均无生产，实际风险=0，不发正式通知给 PMC/采购；若后续发现该窗口内确有实质订单量再走正式复核（队列 §四 #14）。全量回归：SC8 161+2skip / 平台167+1skip / SC1 53 / O2 20 / SC7 41（黄金基准 35850/640000/675850 精确不漂移），新增 39 tests 零回归。B1（多层递归）排期未定不做，C-1（主料替代料）随 openspec 批2 另案。L/T 数据源缺口登记跨桌任务队列 `#19`。真实数据 LAN 回归为独立后续任务。 |
| 2026-07-13/14 | **B1 多层 BOM 递归展开**（`openspec/changes/archive/2026-07-14-shortage-multilevel-bom-b1`）：姚祖怡批改 SC8净额开关底稿发现"半成品子件未二次分解"（S02Y.0035 瓶颈子件 R02A.0019 藏在未展开的半成品下，按期误判），Paul 现场确认"所有F开头需求的共性问题"、指示排期提前。`sc8/baoguan.py::_gross_need`/`sc8/forecast.py::estimate_material_arrivals` 改为复用 `kit_engine.explode_bom` 无条件递归展开半成品至叶子件（**方案迭代**：最初实现了"新开关`SC8_MULTILEVEL_BOM`+逐层现货抵扣"，开发中发现工作区已有预写测试规格描述更简单方案，经 Paul 确认改用无条件展开、不做净额、无新开关——`explode_bom_with_netting` 保留在平台底座作未来可选增强，本次未接入）。单层 BOM 场景结果与改造前完全一致（向后兼容）；半成品不再被误当作待答交物料查 SRM。全量回归：SC8 170+2skip / 平台175+1skip / SC1 53 / O2 20 / SC7 41（黄金基准精确不漂移），零回归。真实 LAN 环境多层取数性能/限流验证为独立后续任务。同批也排查确认第19-21行"按期误判"与本问题同根因，无需单独修复。 |
| 2026-07-14 | **B1+B3 部署到 51 服务器**：`sync-to-server.ps1` 跑完显示"服务已重启"，但实测**未真正生效**——旧进程（PID 8716，7/6 17:44 启动）仍占用 8091 端口，"重启"步骤的按端口 taskkill 未真正杀掉它（脚本自带的孤儿进程防护这次没起作用，具体时序原因未深挖，🔴 待办：`sync-to-server.ps1` 重启可靠性需要补一次修复，`schtasks /End` 后到 taskkill 扫描之间可能有时序竞争）。手动 `taskkill /F /PID 8716` + `schtasks /Run` 后确认新进程（PID 1756，CreationDate 2026-07-14 11:27）正确起来，curl 验证 HTTP 200、页面正常渲染。**结论：以后每次部署后必须验证进程 CreationDate 是否真的刷新，不能只看脚本打印"服务已重启"就当真**。 |
| 2026-07-14 | **`SC8_NET_INVENTORY` 翻 ON（净额开关黄金重核签字执行）**：姚祖怡企微回传《7/17 会材》预填件净额 5 项条件全勾+签字已填（`7-外部文档/采购部/`），Paul 当日与其线下二次确认将"D段"由"7/17同场签"改为"现在算数"——CC 执行：51 服务器 `.env` 追加 `SC8_NET_INVENTORY=on` + 严格重启验证（`schtasks /End` 这次真正杀掉了旧进程、无需手动 taskkill；新 PID 4044 CreationDate 与重启时间吻合）+ `/api/refresh` 全量重算。**核验结果与姚祖怡底稿预期吻合**：🔴真延期 32→17、🟢按期 0→3（命中 S02Y.0035，与底稿"3张转🟢"一致）；R01A.0061/R01A.0012（Paul 07-13 截图指出的"有货却判短缺"案例）翻 ON 后全量 116 行中不再作为任何成品瓶颈子件出现。IATF 翻 ON 治理留痕见 `7-外部文档/采购部/采购部-SC8净额开关翻ON执行记录-2026-07-14.md`。同批 Paul 二次确认另两点：B1 排期"分批"改"全量"（与已上线实现一致，无需回退单层）；A2 采购提前期 L/T 走"IT/SRM 自动取数"路线（姚曾提议的"人工可编辑字段"未采纳），跨桌任务队列 `#19` 路线定案、`#30` 归并关闭。**未做**：完整 A1-B4+B1 系统性真实 LAN 回归报告（本次只做 #3 收口所需的定向抽验，跨桌任务队列 `#24` 仍待领）；21 张成品保供黄金基准据新判级更新登记——**07-14 当日姚祖怡已对照线上看板抽验确认结果正确，此项视为完成**（详见执行记录 §四）。 |
| 2026-07-15 | **C-1/C-2 openspec 批2起草 + sync-to-server.ps1 重启可靠性修复（代码）+ #24 等效验收销行**：① 主料/替代料等价合并判缺料（C-1）+ 部分齐套显示（C-2）按 `保供看板v2-口径定稿.md` §2 生成 openspec 提案+design+3个spec delta+tasks 四件套（`openspec/changes/sc8-baoguan-substitute-partial-kit/`，`openspec validate` 通过），design.md 留 3 处技术决策（BomRow 新字段设计/替代料合并逻辑放场景层不下沉平台/C-2 与净额开关耦合）+ 3 个 Open Question（替代料 DTO 字段结构未经真实验证，已排为 tasks.md 第一步）待 Paul 审——**按项目流程本次只做到 design，未 apply、未写业务代码**。② `sync-to-server.ps1` 重启逻辑改为远程 PowerShell 轮询确认（端口真正释放才 `/Run`，新进程真正起来才算成功），修复 2026-07-14 观察到的 taskkill 有时不生效问题；⚠️ 本次施工环境无 LAN 访问 192.168.100.51，代码已过本地语法校验，真实部署验证留待下次有 LAN 访问的 session。③ 跨桌任务队列 `#24`（完整 A1-B4+B1 系统性 LAN 回归报告）Paul 拍板不再单独出，以既有定向抽验+姚祖怡看板整体抽验作等效验收，销行。 |
| 2026-07-15 | **A2 L/T 数据源 IT 评估已回复（Paul 转达，CC 登记）**：U9C `PurProcessLT`（标准提前期）IT 明确不可用于按实际交期运算场景，不建议采用；等价字段=SRM 核价单"承诺交期"，但**现状大量空缺、无可用 API**，IT 计划 07-15 起设供应商必填，覆盖率目标 **2027-03 ≥95%**。**结论：自动取数路线方向不变但近期不可行，A2 现状兜底（净需求>0即追）需长期维持约 8 个月**，不接 `PurProcessLT` 顶替（数据不可信风险 > 显式兜底）。不阻塞现有交付；建议 2027-Q1 前后再核实覆盖率决定是否正式接入。详见 `1-转型规划/IT评估请求-SC8采购提前期LT数据源-2026-07-14.md` IT 回复段。 |
| 2026-07-15 | **C-1/C-2 apply 完成（`sc8-baoguan-substitute-partial-kit`，Paul 审 design 通过后）**：见"3. 复用底座资产"新增行。TDD 全程：`tests/test_bom_substitute_extraction.py`(7)+`tests/test_baoguan_substitute_merge.py`(8)+`tests/test_baoguan_partial_kit.py`(8)+`test_baoguan.py`新增3个，SC8 全量 188 passed+3 skip；平台193+1skip/SC1 53/SC7 41(黄金基准精确不漂移)/O2 20，零回归。**实现中顺带发现并修复一个交互 bug**：`estimate_material_arrivals`/`explode_bom` 不识别 `is_substitute`，替代料行若原样传入会被当"待答交组件"误查 SRM（幻影组件）——已在 `assess_supply_risk` 调用前过滤修复。**已知范围外风险（未处理，供后续任务参考）**：`sc8/pipeline.py`（SC8 交付承诺主流程，与 baoguan.py 保供看板是两条不同流水线）同样调用 `estimate_material_arrivals`，一旦真实 BOM 数据含替代料行会面临同样的幻影组件问题，design.md 明确本次不改 forecast.py/commitment.py，留给后续。**未做**：① tasks.md §1 真实数据字段验证（替代料 DTO 是否自带独立用量/损耗未经验证，本沙箱无 LAN 访问 U9C）；② 姚祖怡真实数据抽验（15母件/56组替代料样本+部分齐套场景）；③ `kittable_shortfall` 口径（凑够下一整套所需缺口）未经专员确认。均登记为独立后续任务，不阻塞代码合入（mock/脱敏先行，符合项目红线）。openspec 已归档 `archive/2026-07-15-sc8-baoguan-substitute-partial-kit/`。 |
| 2026-07-15 | **①真实数据字段验证已补做，发现并修正一处真实错误**（Paul 回公司确认在 LAN 后，CC 用有凭证的环境对 7 母件/20 组替代料做只读实测）：替代料 DTO 确实自带独立 `m_usageQty`，但**恒为 1.0，与主件行真实用量（1/2/3/4/9/10/16 等值）无关，是 ERP 占位值**——design.md D2 原假设"替代料自带用量则优先用自己的"被证伪；已修正 `get_bom_for_products`（`5-平台底座/zhuopin_platform/.../erp_connector/connector.py`）：替代料恒继承主件行 `qty_per_unit`/`loss_rate`，不再采信替代料自身 `m_usageQty`/`m_scrap`。修复前的实现在主件行真实用量>1 的场景会严重低估替代料应有的展开需求量，进而可能得出"现货够、判齐"的错误结论——**是一个会导致真实误判的 bug，未上线前发现修复**。同步更新 `tests/test_bom_substitute_extraction.py`（1 个测试断言方向反转）+ `openspec/specs/platform-data-connectors/spec.md`（新增 Scenario）+ 归档 design.md（补充段记录验证过程与结论）。全量回归零漂移（平台193+1skip/SC8 188+3skip/O2 20/SC7 41黄金基准精确不漂移/SC1 53）。②③ 仍需姚祖怡本人参与判断，未做——20 组真实替代料样本已可直接作她的抽验素材，登记跨桌任务队列 `#33`。 |
| 2026-07-15 | **SRM 900401 阻塞解除 + `sc8-real-data-cutover` 归档**：真实只读实测确认携客云 `get_receive_board`（488 条真实记录）+ `get_confirmed_dates`（`/purchase/answer` 权威源，真实拿到确认交期）均可用，此前长期记录的"SRM 降级 mock（900401未开通）"已过时，已清理 `config.py::srm_source_mode`/`sc8/run.py`/`tests/test_real_integration.py` 里的过时说法，新增 `test_real_srm_schema` 真实集成测试（`SC8_RUN_REAL=1` 门禁）并跑通。**Paul 07-15 当场纠正一处过度保守的判断**：`config.srm_source_mode()` 默认值最初改成"仍 mock、生产显式opt-in"，机械照搬了 `SC8_NET_INVENTORY` 的"默认关"惯例——但复查后发现这个类比不成立：① 该开关唯一消费方是 `sc8/run.py`（小样本验证 runner），其中 FO/BOM 早就无条件真实、不受任何开关控制，SRM 单独挂 mock 默认只是 900401 阻塞期打的技术补丁，不是像净额开关那样需要专员签字复核的业务口径判断；② 部署运行的保供看板服务 `baoguan_service.py::compute_snapshot` 从来没有用过这个开关——SRM 调用一直硬编码字面量 `"real"`，900401 解除只是让这个早就是"real"的调用拿到更完整数据（`/purchase/answer` 权威源从此前部分受阻退化为看板辅助日期，恢复为权威源直接可用），并非从 mock 切到 real。**已改正**：`srm_source_mode()` 默认值改为 real（仍支持显式 `SC8_SRM_SOURCE=mock` 临时脱敏），`run.py` 注释、`test_sources_and_audit.py`（`test_srm_source_mode_defaults_real` 替换原 `_defaults_mock`，新增 `test_srm_source_mode_explicit_mock_override`）同步更新，SC8 全量 189 passed+4 skip，零回归。Paul 拍板"已并入主线的功能保留、未实现且过时的关闭"——`openspec/changes/sc8-real-data-cutover/`（6月建立、长期搁置、FO/BOM真实等有效成果已被后续变更包承接合入master）已归档 `archive/2026-07-15-sc8-real-data-cutover/`，委外真实路线识别（`is_outsourced_by_routing`）与凭证 Vault 化降级为独立 backlog（未做，非阻塞，现状维护清单兜底运行良好）。全量端到端 `run_small_sample`（FO+BOM+库存+SRM 全真实）烟测因 SRM `/purchase/answer` 30s/请求限流在单张真实订单的完整 BOM 上耗时过长（>15分钟未完成，非代码 bug，是真实限流叠加），已终止——**判定不必等它跑完**：真实数据管线的正确性已由更细粒度的 `test_real_fo_orders_schema`/`test_real_bom_schema`/`test_real_srm_schema` 三个独立真实测试分别验证通过，足以确认端到端真实数据链路可用。平台/SC1/SC7/O2 零回归（本行末次全量数字以 07-15 当天最后一次 SC8 CLAUDE.md 更新为准，见"当前"行）。 |
| 2026-07-16 | **真实部署到 `.51` + 开放同事试用**：Paul 明确要求"部署所有已完成的项目到 .51 供同事试用找 bug"。SSH（`supplychain-server` 别名）确认可用（此前 ping 不通只是 ICMP 被挡，此服务器实际一直在线，"疑似关机"的判断已撤回）；跑 `sync-to-server.ps1` 真实部署，**07-15 那次重启可靠性修复首次真实验证通过**：`PORT_CLEAR` → `NEW_PID=7928 CREATED=2026-07-16 11:14:22`，全程轮询确认、未走手动介入分支。部署后 `/api/ping`+首页 200 双重确认健康，`POST /api/refresh` 触发全量重算成功（116 行：🔴15/🟠84/🟡0/🟢17），线上数据已反映今日 C-1/C2 真实替代料合并 + SRM 真实承诺交期。范围说明：本项目内只有 SC8 保供看板有 `.51` 部署管线；企微机器人服务虽也有 `sync-to-server.ps1`（目标 `C:/wecom-aibot`），但 Paul 此前已拍板该服务运行在其本机开发端监听（`ZhuopinAibotDevListener`），与 `.51` 正式部署独立，本次未动。看板地址 `http://192.168.100.51:8091/`，案例处置 `http://192.168.100.51:8091/cases`。 |
| 2026-07-20 | **`kittable_shortfall`（还差 N 件）口径改造**（跨桌任务队列 #63，源头 #33/#40 姚祖怡 07-16 企微回复）：姚祖怡确认口径＝"凑够客户下单总量（`so.qty`）还差多少"，推翻 design.md 07-15 原推荐的"凑够下一整套（`kittable_qty+1`）还差多少"（两口径数值差异大，总单量口径通常大得多）。`_kittable_qty` 瓶颈子件 shortfall 改按 `so.qty * qty_per_unit − avail`（下限 0，`best_qty`/`best_material` 判定逻辑不变）；字段注释/docstring 同步；`row_to_dict`/`_HTML_JS` tooltip 未硬编码旧口径措辞，核对后无需改动。TDD：`test_baoguan_partial_kit.py` 重写口径断言 + 新增"瓶颈子件已够撑满整单→shortfall=0"边界用例；`test_baoguan.py` 同步硬编码期望值。全量回归零漂移：SC8 190 passed+4 skip（+1）、平台 200+1skip、SC1 53、SC7 41（黄金基准精确不漂移）、O2 20。业务口径回灌 `1-转型规划/保供看板v2-口径定稿.md` §2 C-2·②+§5 裁决 5；design.md 归档件补"已实现"回填。 |
| **当前** | **SC8 保供看板已部署 `.51`、对内部同事开放试用（2026-07-16）**，`SC8_NET_INVENTORY=on`（净额现货抵扣，姚祖怡已抽验确认）+ SRM 真实数据均已生效；对客外发全程关闭；`sc8-real-data-cutover` 变更包已归档（2026-07-15）。**采购域最小端到端真实数据 MVP 现状**：FO✅真实/BOM✅真实/库存✅真实/SRM✅真实/C-1·C-2✅真实验证过（bug已修）/SMT工时仍mock（无连接器，独立缺口）/对客外发🔴仍关闭（非MVP范畴，5项前置条件仅SRM一项满足）。SC8 全量 190 passed+4 skip，平台200+1skip/SC1 53/SC7 41(黄金基准精确不漂移)/O2 20，零回归。待办 #10：加登录/Token 鉴权再开外网（真实客户名红线，`.51` 内部同事试用当前仍 LAN 无鉴权访问，尚可接受）；🟢 `sync-to-server.ps1` 重启可靠性修复已真实部署验证通过；🟢 `#24` 完整系统性 LAN 真实回归报告已按等效验收销行；🟢 姚祖怡真实数据抽验+`kittable_shortfall`口径确认均已完成（07-16 回复，跨桌任务队列 #33/#40 销行，`kittable_shortfall` 代码改造见 2026-07-20 行）；🟡 待办：A2 L/T 数据源（跨桌任务队列 #19）IT 已回复现状大量空缺、预计 2027-03 才达 95% 覆盖率，兜底口径长期维持，非阻塞；🟡 待办：同事试用期间收集的 bug/反馈需要有个收口渠道（建议随跨桌任务队列或直接问 Paul）。 |

## 6. 关键依赖/前置（解锁条件）

- ~~🔴 SRM 凭据注入本仓库 `.env`（解 900401）~~ **✅ 已解锁（2026-07-15）**— 凭据已在 `.env`（`XKY_*`），900401 阻塞已解除，真实数据可用；部署服务 `baoguan_service.py` 本就硬编码走 real（本次只是让它拿到更完整数据），`sc8/run.py` 验证 runner 的 `SC8_SRM_SOURCE` 默认值也已改 real（原计划"默认mock、生产opt-in"经 Paul 07-15 指出是机械照搬 `SC8_NET_INVENTORY` 惯例、类比不成立，已改正）。SRM 接通只是对客上线 5 项前置条件之一，其余 4 项（L2 双签/6 项门禁/首道入队确认/客户 SQE 沟通）仍未满足，对客外发仍关闭。
- 🔴 L2 双签（采购经理 + VP Paul）— 对客外发前置。
- 🔴 SC8 上线前置门禁 6 项检查表全过 — CUSTOMER_OUTBOUND_ENABLED 设 True 的前置。
- 🟡 Web 服务加 Token 鉴权（待办 #10）— 开外网前必须；LAN 内部使用暂不阻断。
- 🟡 PMC 核实 S02Y.0188 瓶颈子件延期判断（+184）— 对客沟通前置。
- 🟡 `CommonEntity/Query` 外网开放（IT）— SC8 全量 cutover（库存/PO/MO/价格）前置；LAN/VPN 过渡。
- 🟡 答交可信度接入置信度 2→3 级化 — 需显式设计"如何加权"（本次迁移不做设计决策，只做代码归位），随 SC8 深化排期，独立后续任务。
- 🟡 A2 采购提前期(L/T) SRM 承诺交期字段覆盖率 — IT 07-15 回复现状大量空缺，目标 2027-03 达 ≥95%；在此之前 A2 追料判断长期维持"净需求>0即追"兜底口径，不接 U9C `PurProcessLT`（不适用于实际交期运算）。
- 🟢 姚祖怡真实数据抽验 C-1/C-2（`sc8-baoguan-substitute-partial-kit`）— 替代料 DTO 真实字段验证已于 2026-07-15 补做完成（发现并修正一处真实 usageQty 占位值 bug），姚祖怡本人抽验（07-16 回复"判断逻辑跟预期一致"）+`kittable_shortfall`口径确认（"凑够客户下单总量还差多少"）均已完成，代码已按新口径改造（2026-07-20，跨桌任务队列 #63）。
- 运行：`python scripts/run_baoguan_web.py`（保供 Web 服务，LAN，0.0.0.0:8090）；答交可信度独立跑：`python -m sc8.answer_confidence`（mock 模式）。
