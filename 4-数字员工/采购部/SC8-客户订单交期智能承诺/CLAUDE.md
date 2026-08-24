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
| D2：启发式参数 | **集中到 config.py** — NO_FEEDBACK_LEAD_DAYS=**90**（v0=30，2026-07-23 姚祖怡业务口径校准+Paul 同日拍板改 90，PARAM_VERSION 同步 v0→v1）/ OUTSOURCE_EXTRA_DAYS=10 / LOGISTICS_DAYS=1 / DEVIATION_ALERT_DAYS=3 / PARAM_VERSION 可配 | 阈值是业务参数，集中可配+可审计"用了哪组参数" |
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

> 🔴 **本节已按场景级判据 J5 二次瘦身（2026-08-22，OP-0822-D）**：本次再迁出 5 行（`2026-06-10`／`2026-07-02`／`2026-07-16`／`2026-08-18`／`2026-08-20`）入同目录 `CHANGELOG.md`，本节由 11 行减为 6 行。**首批 24 行已于 2026-08-21 迁出**，同一份 `CHANGELOG.md`。
>
> ⚠️ **剩下的 5 个日期行不得随后顺手迁走**——它们**全部**因 J1 判为「无承接载体且含未闭合措辞」而刻意留下：`2026-06-24`（「未结：7.2 LAN 真实联调验收」）／`2026-07-06`（「未接线到现有置信度流水线」）／`2026-07-14`（B1+B3 部署，挂着待办）／`2026-07-15 A2 L/T`（长期跟踪项，2027-03 才到期）／`2026-07-15 C-1/C-2`。**五者确有未闭合事项且没有任何队列行承接，迁走即丢。要迁请先为它们立队列行。**
>
> 📌 **2026-08-21 那份注解已作废**：它写的是「8 行不得迁走」，而本次实测其中 `2026-06-10`／`2026-07-02`／`2026-07-16` 三行正文零未闭合措辞、按 J1 第 ⑵ 档可迁，已迁出。**旧注解把「没点名队列号」与「有未闭合事项」混为一谈了**——它自己那句「其余 5 行只是没点名队列号」其实已经指出了这个区别，只是当时的判据还接不住。
>
> ⚠️ **`**当前**` 行因超 J3 长度上限（1,200 字符）已压缩**，只留现状结论与在办指针；**压缩前原文全文见同目录 `CHANGELOG.md` §「长文存档」**。

| 日期 | 状态 |
|------|------|
| 2026-06-24 | FO 正式库接通 + 保供四色口径确定 + 保供预警 Web 服务上线（Flask+waitress，8090，LAN 无鉴权，保供案例处置中心 SQLite）。未结：7.2 LAN 真实联调验收。 |
| 2026-07-06 | **答交可信度子模块并入**（采购域 v2.3 重排，`sc-v23-engine-migration`）：SC3 场景编号退役，其在途风险评估引擎（29 tests）原样迁入 `sc8/answer_confidence*.py`，audit `scenario` 由 "SC3" 改标 "SC8"；本次只搬代码，未接线到现有置信度流水线；全量回归 143 passed + 2 skipped，零回归。 |
| 2026-07-14 | **B1+B3 部署到 51 服务器**：`sync-to-server.ps1` 跑完显示"服务已重启"，但实测**未真正生效**——旧进程（PID 8716，7/6 17:44 启动）仍占用 8091 端口，"重启"步骤的按端口 taskkill 未真正杀掉它（脚本自带的孤儿进程防护这次没起作用，具体时序原因未深挖，🔴 待办：`sync-to-server.ps1` 重启可靠性需要补一次修复，`schtasks /End` 后到 taskkill 扫描之间可能有时序竞争）。手动 `taskkill /F /PID 8716` + `schtasks /Run` 后确认新进程（PID 1756，CreationDate 2026-07-14 11:27）正确起来，curl 验证 HTTP 200、页面正常渲染。**结论：以后每次部署后必须验证进程 CreationDate 是否真的刷新，不能只看脚本打印"服务已重启"就当真**。 |
| 2026-07-15 | **A2 L/T 数据源 IT 评估已回复（Paul 转达，CC 登记）**：U9C `PurProcessLT`（标准提前期）IT 明确不可用于按实际交期运算场景，不建议采用；等价字段=SRM 核价单"承诺交期"，但**现状大量空缺、无可用 API**，IT 计划 07-15 起设供应商必填，覆盖率目标 **2027-03 ≥95%**。**结论：自动取数路线方向不变但近期不可行，A2 现状兜底（净需求>0即追）需长期维持约 8 个月**，不接 `PurProcessLT` 顶替（数据不可信风险 > 显式兜底）。不阻塞现有交付；建议 2027-Q1 前后再核实覆盖率决定是否正式接入。详见 `1-转型规划/IT评估请求-SC8采购提前期LT数据源-2026-07-14.md` IT 回复段。 |
| 2026-07-15 | **C-1/C-2 apply 完成（`sc8-baoguan-substitute-partial-kit`，Paul 审 design 通过后）**：见"3. 复用底座资产"新增行。TDD 全程：`tests/test_bom_substitute_extraction.py`(7)+`tests/test_baoguan_substitute_merge.py`(8)+`tests/test_baoguan_partial_kit.py`(8)+`test_baoguan.py`新增3个，SC8 全量 188 passed+3 skip；平台193+1skip/SC1 53/SC7 41(黄金基准精确不漂移)/O2 20，零回归。**实现中顺带发现并修复一个交互 bug**：`estimate_material_arrivals`/`explode_bom` 不识别 `is_substitute`，替代料行若原样传入会被当"待答交组件"误查 SRM（幻影组件）——已在 `assess_supply_risk` 调用前过滤修复。**已知范围外风险（未处理，供后续任务参考）**：`sc8/pipeline.py`（SC8 交付承诺主流程，与 baoguan.py 保供看板是两条不同流水线）同样调用 `estimate_material_arrivals`，一旦真实 BOM 数据含替代料行会面临同样的幻影组件问题，design.md 明确本次不改 forecast.py/commitment.py，留给后续。**未做**：① tasks.md §1 真实数据字段验证（替代料 DTO 是否自带独立用量/损耗未经验证，本沙箱无 LAN 访问 U9C）；② 姚祖怡真实数据抽验（15母件/56组替代料样本+部分齐套场景）；③ `kittable_shortfall` 口径（凑够下一整套所需缺口）未经专员确认。均登记为独立后续任务，不阻塞代码合入（mock/脱敏先行，符合项目红线）。openspec 已归档 `archive/2026-07-15-sc8-baoguan-substitute-partial-kit/`。 |
| **当前** | **✅ SC8 保供看板 ＋ 物料看板均已部署 `.51`、对内部同事开放试用**（成品看板 2026-07-16 起；`/materials` 物料看板 2026-08-20 起，队列 #334，两者共用同一份快照、不触发独立取数、不参与任何判定）。**开关与数据源**：`SC8_NET_INVENTORY=on`（净额现货抵扣，姚祖怡已抽验确认）＋ `SC8_PO_TRANSIT=on`（回溯窗口 365 天）；FO／BOM／库存／SRM／PO 在途**均已切真实**，SMT 工时仍 mock（无连接器，独立缺口）；🔴 **对客外发全程关闭**（非 MVP 范畴，5 项前置仅 SRM 一项满足）。 ━━━ 🔴 **在办与阻塞（均有承接行，勿在此复述细节）**：`#10` 加登录/Token 鉴权再开外网（真实客户名红线；`.51` 当前仍 LAN 无鉴权）；`#19`＋`#18-c` 根治部分**阻塞在 IT 接口缺口**（FO 行级状态字段 ／ PO 行级关闭状态字段），建议与 #80 的 `POChange/Query` 缺口合并一次性向 IT 提；`#118` 批2 ATP 引擎（优先级占用扣减／多月逐期齐套）；A2 L/T 数据源 IT 已回复预计 2027-03 才达 95% 覆盖，兜底口径长期维持、非阻塞；物料看板品牌／责任人两列全库无取数源，解锁条件＝IT 核实携客云 OpenAPI 是否提供「请购需求池-采购订单协同」端点。**试用期反馈目前没有固定收口渠道**，暂随队列走。 ━━━ 🔴 **通知姚祖怡试用物料看板的跟进信尚未发出、也尚未起草**——其串行闸锁着（采购部#16 未闭环），本信排在 SC2 判例包之后，最早 采购部#18。 ━━━ 历史与本行改写前的原文全文见同目录 `CHANGELOG.md`。 |


## 6. 关键依赖/前置（解锁条件）

- ~~🔴 SRM 凭据注入本仓库 `.env`（解 900401）~~ **✅ 已解锁（2026-07-15）**— 凭据已在 `.env`（`XKY_*`），900401 阻塞已解除，真实数据可用；部署服务 `baoguan_service.py` 本就硬编码走 real（本次只是让它拿到更完整数据），`sc8/run.py` 验证 runner 的 `SC8_SRM_SOURCE` 默认值也已改 real（原计划"默认mock、生产opt-in"经 Paul 07-15 指出是机械照搬 `SC8_NET_INVENTORY` 惯例、类比不成立，已改正）。SRM 接通只是对客上线 5 项前置条件之一，其余 4 项（L2 双签/6 项门禁/首道入队确认/客户 SQE 沟通）仍未满足，对客外发仍关闭。
- 🔴 L2 双签（采购经理 + VP Paul）— 对客外发前置。
- 🔴 SC8 上线前置门禁 6 项检查表全过 — CUSTOMER_OUTBOUND_ENABLED 设 True 的前置。
- ✅ Web 服务加 Token 鉴权（待办 #10）已止血（2026-07-30，队列 #160）— 共享口令+Cookie 门禁上线，详见下方状态时间线；仍非正式身份鉴权，企微 OAuth SSO 待另出架构决策件。
- 🟡 PMC 核实 S02Y.0188 瓶颈子件延期判断（+184）— 对客沟通前置。
- 🟡 `CommonEntity/Query` 外网开放（IT）— SC8 全量 cutover（库存/PO/MO/价格）前置；LAN/VPN 过渡。
- ✅ **齐料日期/瓶颈物料只按最早答交日期取值、不看答交数量 —— 已修复（2026-08-24，队列 #344，`sc8-kit-date-qty-cumulative`）**。原缺陷（2026-08-18 实测定性，姚祖怡 `F02N.0224` 举证）：`sources.load_srm_deliveries` 合并时取 `min(auth_dates)` 且 `qty_committed` 恒写 0，`forecast.estimate_material_arrivals` 的 `srm_index` 同样只留最早日期 ⇒ 答交数量为 0 的记录也会被当成到货日（真实取数 `R01I.0622`：2026-08-20 答交数量 0 被引擎采用／2027-05-20 的 10000 才是唯一有量的一笔）。**现改为按已签认的四条口径取值**（判例批改 3 条 ✅ 全签认 ＋ 口径 ⑷ 文本回件）：按答交数量累计到覆盖需求为止的那一笔的日期；一笔即够不再往后累；不够继续累计到够；答交数量为 0 等同无答交。🔑 **结构性收益比修好这一处更值得记**：`_cumulative_confirmed_batches` 已由 `baoguan.py` **下沉到 `forecast.py`**，齐料日／BOM 缺口清单／物料看板三处**共用同一个函数对象**——「下面清单对、上面汇总数不对」这一族在齐料日这个落点上从此不可能复发，而不是靠「记得同步改三处」。**与 #266 分属两层**（那条是 BOM 展开深度，这条是答交数量匹配）。
  🔴 **两处未闭合，都已登记、都无默认**：⑴ **「答了但累计仍不够」**（如需求 15000 只答了 8000）签认口径未覆盖，现按保守外推处理（判无答交 ＋ 取 `max(启发式估算日, 最晚正数答交日)`），**待姚祖怡以判例确认**；⑵ **规则 1 实测未覆盖**（无答交估算的起算点应为「出货日前推 3 个月的 20 日」，现行仍是出货日 +90，比他的规则更晚、偏保守），**本变更包只测不改**，是否另立变更包须 Shao Peishen 定。两项详见 `docs/queue_344_kit_date修复前后对照-2026-08-24.md`。
- 🟡 答交可信度接入置信度 2→3 级化 — 需显式设计"如何加权"（本次迁移不做设计决策，只做代码归位），随 SC8 深化排期，独立后续任务。
- 🟡 A2 采购提前期(L/T) SRM 承诺交期字段覆盖率 — IT 07-15 回复现状大量空缺，目标 2027-03 达 ≥95%；在此之前 A2 追料判断长期维持"净需求>0即追"兜底口径，不接 U9C `PurProcessLT`（不适用于实际交期运算）。
- 🟢 姚祖怡真实数据抽验 C-1/C-2（`sc8-baoguan-substitute-partial-kit`）— 替代料 DTO 真实字段验证已于 2026-07-15 补做完成（发现并修正一处真实 usageQty 占位值 bug），姚祖怡本人抽验（07-16 回复"判断逻辑跟预期一致"）+`kittable_shortfall`口径确认（"凑够客户下单总量还差多少"）均已完成，代码已按新口径改造（2026-07-20，跨桌任务队列 #63）。
- 运行：`python scripts/run_baoguan_web.py`（保供 Web 服务，LAN，0.0.0.0:8090）；答交可信度独立跑：`python -m sc8.answer_confidence`（mock 模式）。

## 路径引导（队列 #345，2026-08-18）—— 扁平部署布局下不再硬失败

- **改了什么**：本组件下列入口顶部的 #300 worktree 隔离引导，**找不到 `5-平台底座/zhuopin_platform` 标记时不再无条件 `raise`**：`sc8/answer_confidence.py`（Web 入口 `scripts/run_baoguan_web.py` 已于 `a858769` 修过）
- **为什么**：`.51` 的部署布局是扁平的 `C:/<svc>/app` ＋ `C:/<svc>/zhuopin_platform`（后者已由 deploy 脚本 `pip install -e` 进该服务 venv，全机唯一一份），**本就没有 `5-平台底座/` 这层目录**。原实现在此直接 raise，等于把入口在生产布局上钉死。2026-08-18 SC8（8091）与 QD-B（8093）当天各自被它打挂过一次。
- **改法**（同 QD-B `dcc4162` / SC8 `a858769` 已验证范式）：找到标记 → 按 #300 原样前插（开发机 N 个平等 worktree 需确定性）；找不到 → 只插自身包路径、平台底座交环境解析（生产机唯一一份、无歧义）；**只有当环境里也没有 `zhuopin_platform` 时才 raise** —— 不引入静默失败。
- 🔑 **为什么这类雷本地测不出来**：**本地永远能找到仓库根标记**，全量测试全绿与它毫无关系。凡"引导/路径解析"类改动，**本地绿 ≠ 生产可启动**。
- ⚠️ **`tests/conftest.py` 刻意不改**：在 monorepo 内 fail-loud 是**有价值的**——测试就该跑在仓库里，找不到标记说明环境真错了，此时静默回退才是隐患。
- **收拢为平台底座共享函数** 见 `openspec/changes/platform-bootstrap-ensure-paths/`（已 propose，待 Shao Peishen 审 design，本次未 apply）。
