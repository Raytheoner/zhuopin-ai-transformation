> **⚠️ v3 口径修正（2026-07-09，见文末"v3 口径修正补充决策"）**：核对对象改 **AP 单 vs INV**（PO 降级为价格前置参照）、匹配粒度改**按料品汇总归集**（非逐 PO 行）、四维改「料品+数量+未税金额+税额」、新增 **AP-PO 单价强制比对**（R7）。下文 Context/Goals/D1-D9 为 v1 原意（架构性决策 D1/D6/D7/D8/D9 仍生效），与 v3 冲突处**以文末补充决策 D10-D13 为准**。

## Context

FI2 三单匹配自动对账是财务域 2026 年唯一按期落地场景（FI1 因需求变更暂缓封存，见根 `CLAUDE.md` 2026-07-06 记录），2026-09 启动。财务人员目前逐笔核对**发票↔入库单(GRN)↔付款凭证(Payment)**，沿 PO 行核对数量/单价/金额/税额是否一致，效率低且**"总额对、明细行错位"**这类隐蔽差异极易漏检——一旦漏检，按行核算的产品成本会失真而不自知，是财务反复强调的最高风险点。

**当前状态/约束**：
- 落位 `4-数字员工/财务部/FI2-三单匹配自动对账/`（包名 `fi2`），已 scaffold + `pip install -e` 平台底座 + 本包，import 验证通过。
- U9C 财务接口 / SRM 发票 / OCR 均需 9 月才通（7/15 双反馈门待核）。MVP **mock 先行、不等数据闸**——打法照 FI1（`fi1-temp` 模式）：临时口径起 propose，接口通后只切数据源、不改引擎。
- 口径底稿已由 Cowork 财务专线出好：《FI2 三单匹配口径-mock 备料》（匹配键/容差/状态机/9 类根因/mock 表结构）+《FI4 三单匹配-就绪清单与 MVP 细化》（就绪清单 + 五分类判定边界，编号 FI4 即 FI2 内容，同一份口径）。两份高度重合，本设计以后者的"MVP 口径底稿"五分类表为准（更细化），前者的 4 张 mock 表结构与 9 类根因档作为 intake/分类扩展参考。
- 自动化等级 **L3**（建议/预警，人工确认，不自动过账）；L4（自动过账/拦截）待查准/查全率达标后另行晋级，不在本次范围。
- 红线（根 `CLAUDE.md` §7 + 财务场景惯例）：先 mock/脱敏跑通逻辑再切真实库；每笔判定写 `audit`；L3 不自动过账；财务红色金额脱敏/仅聚合，原始单价不落 AI 侧；OEM 隔离不适用（财务/ERP 内部数据）。

**stakeholders**：Paul（VP，本 design 拍板人）、唐燕萍（财务 AI 专员，R1-R6 规则口径主笔，约 2026-08 底交付）、IT/SRM（U9C 财务端点 + 发票源 + OCR 选型）、财务对账人员（L3 复核结案）。

## Goals / Non-Goals

**Goals:**
- 给定 PO 明细行 + GRN + Invoice + Payment 四表，纯函数沿 `(po_no, line_no)` 串联三单、沿 `inv_no` 串联 Invoice↔Payment，逐行做物料编码/数量/金额/税额四维比对，输出确定性、可解释、可回归的匹配结果。
- 结果分五类（🟢完全匹配/🟡金额微差/🔴明细错位/🔴数量金额不符/🔴无 GR 支撑），**"明细错位"检出是核心价值点**，必须有显式算法定义、不能遗漏。
- 容差/分类边界/根因归类全部数据驱动（config + 规则注册表），临时口径先占位，唐燕萍规则定稿后只换配置层、不改引擎。
- 数据接入三源统一接口（`mock`/`csv`/`u9c`，仿 FI1 `feed_source.py`），`u9c` 源当前 fail-loud，接口就绪后切源零改引擎。
- 每笔匹配判定/分类写平台 `audit`（`scenario="FI2"`），金额脱敏——审计与报告只记差异比例/分类结果，不落原始发票单价/含税金额明细。
- L3 人工改判 CLI（仿 FI1 `confirm.py`），`--reason` 必填、幂等、写审计，AI 结论恒为"建议"、结案在财务人员。

**Non-Goals:**
- FI2-3 税率专项 / FI2-4 查重 / FI2-5 容差专项收口 / FI2-6 退单 / FI2-7 考核 / FI2-8 学习——二期叠加，本次不做。
- FI3 付款校验——独立场景，依赖本场景结果但不在本次范围。
- OCR 发票解析——本 MVP 用 mock 结构化发票数据占位，OCR 选型/接入是数据闸事项，不在本次实现范围。
- L4 自动过账/拦截——MVP 只到 L3 建议，不实现自动执行路径。
- 物料编码映射表构建——MVP 假设 mock 数据已用统一编码；真实场景的供应商编码↔我方编码映射表是数据闸依赖项（FI4 就绪清单 #4），不在本次实现。

## Decisions

### D1：五层架构（接入 / 数据模型 / 匹配引擎 / 结果分类 / 聚合报告+L3门禁+审计）
- `fi2/feed_source.py`（四表接入，三源）+ `fi2/models.py`（POLine/GRNLine/InvoiceLine/PaymentRecord/MatchResult）+ `fi2/match_engine.py`（纯函数四维比对）+ `fi2/result_classify.py`（五类判定规则注册表）+ `fi2/recon_report.py`（聚合报告 + L3 门禁 + 写 audit）+ `fi2/confirm.py`（L3 人工改判 CLI）。
- 理由：比照 FI1 D1 的四层分层纪律（接入/引擎/分类/聚合门禁），FI2 因四表接入 + 四维比对逻辑更复杂，把"匹配引擎"（纯计算）与"结果分类"（可演进规则）拆开，理由同 FI1——失败模式与可测性不同，分层使引擎可纯单测、分类规则可独立替换（唐燕萍定稿后只换 `result_classify` 规则表）、接入可独立 mock/real 切换。
- 备选：单体脚本一把梭——否决，理由同 FI1（真实连接器/纯计算/可演进规则混一起无法单测、无法黄金回归）。

### D2（🔴待 Paul 拍板 ①）：临时容差口径用 mock 备料稿 strawman 默认
- 落 `config.py`：数量容差 `±2%` 或 `±N 个`（分批尾差，两者取宽松者）；金额容差 `±0.5 元/行`（尾差）；税率必须一致（不一致直接归入"数量金额不符"或专设税率差异类，本期先并入"数量金额不符"，FI2-3 税率专项二期细化）；时间窗暂不做门禁（仅记录，不阻断匹配，跨期识别留 FI2-8 二期）。
- **推荐**：采纳 strawman 默认先起 mock，唐燕萍 R1-R6 定稿（约 8 月底）后**只替换 `config.py` 常量与规则表条目，不改 `match_engine.py`/`result_classify.py` 逻辑**。
- 备选：等唐燕萍定稿再起——否决（会压缩 9 月建造窗口，且 FI1 已验证"临时口径先起、事后换配置层"打法零引擎返工）。

### D3（🔴待 Paul 拍板 ②）：五类判定边界 + 判定优先级，"明细错位"算法定义
- 判定边界照抄 FI4 细化稿：🟢完全匹配（物料/数量/金额/税额四维全在容差内）/ 🟡金额微差（仅金额差 ≤ 尾差容差）/ 🔴明细错位（见下）/ 🔴数量金额不符（超容差）/ 🔴无 GR 支撑（发票无对应入库）。
- **判定优先级**（同一 PO 行只落一类，按序判定，命中即停）：① 无 GR 支撑（缺入库单，无法比对，最先排除）→ ② 明细错位（跨行总额校验，见下）→ ③ 数量/金额/税额任一维度超容差 → ④ 仅金额差在尾差容差内 → ⑤ 全维度在容差内 = 完全匹配。
- **"明细错位"算法定义**（核心价值点，必须显式）：同一 `po_no` 下所有行，若逐行比对时**至少两行**同时超出数量或金额容差、且这些行的**方向相反**（一行多、一行少），同时**该 PO 号下发票总额 vs GRN 应付总额在 PO 级容差内一致**——判定为"明细错位"（数据被错放到别的行但总数对上了），对该 PO 号下所有超容差行整体标红、不逐行拆散成"数量金额不符"。若只有单行超容差、无法在同 PO 下找到方向相反的配对行，则判"数量/金额不符"而非"明细错位"（避免把普通超容差误判为错位、制造假阳性）。
- 理由：五分类边界是 FI4 细化稿现成结论（对接人已给出 strawman），照抄降低本次决策面；判定优先级与"明细错位"算法是细化稿未展开的实现细节，本设计补齐、避免留白导致 tasks 阶段各自猜测。
- 备选：明细错位只要金额对、任意行超容差就判——否决，会把"真实数量差异+巧合总额相近"误判为错位（假阳性拦截率过高，人工排查成本反而上升）。

### D4（🔴待 Paul 拍板 ③）：L3 建议路由——仅四类非完全匹配强制转人工，完全匹配类进"L3建议通过"待抽查队列
- 🟡金额微差 / 🔴明细错位 / 🔴数量金额不符 / 🔴无 GR 支撑，四类**强制标 `needs_review`**、进人工待确认队列，逐笔走 `confirm.py` 改判留痕。🟢完全匹配类标 `l3_suggested_pass`（AI 建议通过），进报告但**不强制逐笔人工点击**，财务人员可批量抽查；不自动过账（L4 才有自动过账，MVP 未实现）。
- **推荐理由**：若五类结果全部强制逐笔人工确认，L3 阶段就与"AI 建议"定位脱节、效率提升为零（等同人工全量核对，AI 只是换了个展示界面）；只对高风险四类强制人工，符合"AI 建议、人工确认异常"的 L3→L4 分期设计初衷，也是统计查准/查全率、决定何时晋级 L4 的数据基础（完全匹配类的抽查结果可反过来验证 AI 判定准确率）。
- 备选：全部强制人工——否决，效率收益为零；全部自动通过不留痕——否决，违反 L3 门禁红线。**此项直接影响价值指标（工时型）能否兑现，请 Paul 明确拍板。**

### D5（🔴待 Paul 拍板 ④）：mock 四表结构照抄口径备稿
- `po_lines`(po_no, line_no, supplier, item_code, qty, unit_price, tax_rate, amount, po_date) / `grn`(grn_no, po_no, line_no, item_code, recv_qty, recv_date) / `invoice`(inv_no, po_no, line_no, item_code, inv_qty, inv_unit_price, inv_amount, tax_rate, inv_date) / `payment`(pay_no, inv_no, pay_amount, pay_date)。四表齐备后可脱离真实接口独立跑通全部五类分支回归。
- mock 数据需埋 9 类根因样本（口径备稿 §四）中至少覆盖本 MVP 五分类判定用到的场景：F1 有货无票、F2 有票无货（无 GR 支撑）、F4 价格差异、F5 数量差异（含"明细错位"的跨行配对场景）、F6 重复入账（同 PO 行多张发票，需在 intake 层做完整性校验时识别），每类 1-2 条作回归。F3(未付款)/F7(税率)/F8(跨期)/F9(汇率) 本 MVP 记录但不作专项判定分支（并入现有五类或仅记录不拦截）。
- 理由：口径备稿字段已对齐 U9C 语义命名习惯，接口开放后 loader 换真实源、字段映射在接入层做，不改 `models.py`/`match_engine.py`。
- 备选：自行设计字段——否决，重复造轮子且可能与后续 U9C 真实字段映射脱节。

### D6：数据接入三源统一接口（mock / csv / u9c），仿 FI1 `feed_source.py`
- `FeedSource(data_source="mock"|"csv"|"u9c")`，四表 `load_po_lines/load_grn/load_invoice/load_payment`，`mock` 读夹具 CSV，`csv` 读 ERP/SRM 导出（未来应急桥接，本次先占位不接真实路径），`u9c` 抛 `RealEndpointNotReadyError`（复用平台 `shared_tools.connector_errors`）。Pydantic 边界校验挡脏数据（贴 FI1 `_OutputRow`/`_FeedRow` 校验器范式）。
- 理由：切源不改匹配引擎/分类逻辑，FI1 已验证此模式零引擎返工地完成 mock→csv 过渡。
- 备选：直接接 U9C 无兜底——否决，9 月接口不一定齐全，会阻断本场景建造。

### D7：审计复用底座 AuditLogger，金额脱敏——只记差异比例/分类结果，原始金额不落盘
- 每行匹配判定写 `AuditEvent(scenario="FI2", action="line_match", automation_level="L3", decision={po_no, line_no, item_code, 分类结果, 差异维度, 差异比例(非绝对金额)}, data_sources={po,grn,invoice,payment})`。**审计与报告不落原始发票单价/含税金额绝对值**——匹配运算过程中金额参与内存计算，但写盘（audit/report）只保留差异比例（如 `"amount_diff_pct": 0.3`）与分类结果；人工需要查看原始单据金额时回原系统查（PO/发票号已留痕，可追溯定位）。
- 理由：财务红色数据红线（金额脱敏/仅聚合，原始单价不落 AI 侧）与匹配核心需要金额比对看似冲突，此决策把"运算需要金额"和"落盘脱敏"分开处理——运算在内存/单次调用内完成，不持久化明细金额，只持久化判定结果与差异比例，满足红线又不牺牲匹配准确性。
- 备选：审计里存完整金额明细——否决，违反财务红色数据红线；完全不记录金额相关信息——否决，无法支撑金额微差/数量金额不符类的差异比例可解释性。

### D8：OEM 隔离不适用，不接 `data_isolation_layer`
- FI2 处理 PO/GRN/Invoice/Payment，均为供应商/ERP 内部数据，按根 `CLAUDE.md` §4 边界不强加 OEM 路由。

### D9：黄金基准仿 FI1/SC5，合成样本 + 确定性零偏差
- `data/golden/` 存合成四表样本（覆盖 D5 提及的 9 类根因子集 + D3 的明细错位配对场景），通过标准：`match_engine` 逐行判定结果与 `result_classify` 五分类结果对预期**零偏差**。真实小样本待 9 月接口/OCR 就绪后另行提交变更包补真实 golden（晋档 2）。

## Risks / Trade-offs

- **[明细错位算法假阳性/假阴性]** → D3 限定"至少两行超容差 + 方向相反 + PO 级总额容差内一致"才判错位，单行超容差不算错位；tasks 阶段需专门构造"真实独立超容差、非错位"的反例回归，防止误判扩大化。
- **[临时容差口径与唐燕萍定稿差距较大]** → 全部落 `config.py` + 规则注册表，定稿后仅替换配置/表条目，`match_engine.py`/`result_classify.py` 判定顺序结构不改；但若定稿改变五分类边界结构本身（如新增第六类），需回头修 design/specs 再 apply（比照 FI1 CLAUDE.md 的"若涉及范围/口径结构变化需重新 propose"纪律）。
- **[mock 四表字段与真实 U9C/SRM 字段差距]** → 三源统一接口，字段映射收敛在 `feed_source.py` 接入层，`u9c`/`csv` loader 就绪后独立改，不碰 `match_engine`/`result_classify`。
- **[金额脱敏与匹配准确性的张力]** → D7 拆分运算与落盘：内存参与比对用完整金额，落盘只留差异比例，兼顾红线与可解释性；若后续审计需要更强可追溯性（如金额区间而非精确比例），需 Paul 与合规再议。
- **[L3 完全匹配类"建议通过不强制人工"可能被误读为已过账]** → 报告/CLI 输出必须显式标注"AI 建议通过，未过账，L4 开放前一律不自动执行"，UI/报告文案红线核对。
- **[AI 越权自动执行]** → MVP 无 L4 路径，代码层面不存在"自动过账"入口，杜绝越权可能性（Non-Goal 已排除）。

## Migration Plan

1. **feed_source（mock 先行）**：四表统一加载接口 + `data_source` 三源开关 + Pydantic 边界校验 + mock 四表 CSV 夹具（贴口径备稿字段+D5 根因样本）。
2. **models.py**：POLine/GRNLine/InvoiceLine/PaymentRecord/MatchResult 数据类，比照 FI1 `models.py` 范式。
3. **match_engine（先测后实现）**：四维比对纯函数（沿 PO 行 + inv_no 串联），先写单测覆盖五类判定路径 + 明细错位配对算法 + 反例（真实独立超容差不误判），再实现。
4. **result_classify**：五类判定规则注册表（config 驱动容差 + 判定优先级），临时口径落表，版本登记。
5. **recon_report + L3 门禁 + audit 接线**：聚合报告契约（`needs_review` vs `l3_suggested_pass`）+ 每行判定写 `audit`（金额脱敏落盘）+ "AI 建议非终局"标注。
6. **confirm.py（L3 改判 CLI）**：`--reason` 必填、幂等、写 `l3_override` 审计事件，比照 FI1 `confirm.py`。
7. **黄金基准回归**：合成 golden 全绿（含明细错位场景 + 反例）；`u9c` 源 fail-loud 冒烟测试。
8. `/opsx:archive` 前提：Paul 审 design 通过 + mock MVP 全绿；真实数据验证（晋档 2）待 9 月数据闸另行提交变更包，不阻塞本次 mock MVP 先行 commit。
- **回滚**：场景独立工程，不动底座 spec、不动 FI1/其他场景；mock 阶段无真实库副作用；无对客/对外发面；回滚=停用场景入口。

## Open Questions（🔴 apply 前必须收口，交 Paul）

- **收口-D2/D3/D4/D5（本 design 已列 4 项待拍板决策，见上）**：Paul 审后若有改动，回填本文件对应 Decision 再 apply。
- **收口-后续 唐燕萍 R1-R6 规则草案**：约 2026-08 底交付，届时替换 `config.py` 临时口径，不改引擎（D2/D3 已预留此路径）。
- **收口-后续 物料编码映射表来源**：真实场景供应商编码↔我方编码映射表待对接人+采购确认（FI4 就绪清单 #4），MVP mock 阶段假设编码已统一，不阻塞本次。
- **收口-后续 OCR 选型 + U9C 财务接口开放时点**：7/15 双反馈门待核，晋档 2（真实数据跑通）的硬前提，不阻塞本次 mock MVP。

---

## v3 口径修正补充决策（2026-07-09，唐燕萍团队应付会计实操细化 + Paul 三裁决，见《财务域场景v3-局部定稿》§1 修正1-7）

> 触发：唐燕萍团队回传《核实对照表》——应付会计实操细化揭示 MVP 阶段"沿 PO 行逐行四维匹配"的核对对象/匹配键/匹配逻辑与实际业务流程不符（实际配票流程核对对象是 AP 单 vs INV，且供应商发票无我方物料编码、明细存在多对多）。Paul 全盘采纳口径修正。以下决策在原 D1-D9 基础上补充，**D1（五层架构）/D6（三源接入）/D7（金额脱敏）/D8（OEM 隔离不适用）/D9（黄金基准打法）四条架构性决策不变**，D2-D5 的"临时口径先起、事后只换配置层"打法沿用，仅比对对象/算法细节随本节调整。

### D10：匹配对象与数据流调整——AP 单 vs INV，PO 降级为价格前置参照
- 实际配票流程：采购在 SRM 收 INV → U9C 应付模块选 GR 配票 → 生成 AP 前缀应付单 → 应付会计核对 **AP 单 vs INV**。原设计"逐 PO 行比对 GRN vs Invoice"不成立——GRN 已被"配票"动作吸收进 AP，AP 才是应付会计实际核对、且最终触发付款的对象。
- **数据流调整**：`POLine`/`GRNLine` 保留加载（`feed_source` 仍读三张表 PO/GR/AP，GR 用于未来 FI2-1 完整性校验/R6 孤儿单据检测，本次 v3 切片暂不接入匹配数学，避免超出本次任务范围造功能）；新增 `APLine`（配票生成，天然带我方料品编码，是发票的比对锚点）；`InvoiceLine` 改为直接挂载 `ap_no`（U9C 应付单附件语义，见 D-发票源）。
- **PO 的新角色**：从"逐行匹配主体"降级为"AP 单价的前置参照"——只用于 D12 的 AP-PO 单价强制比对，不参与 D11 的料品汇总归集比对。
- 理由：贴合应付会计真实核对动作，且改动集中在数据对象与聚合维度，判定优先级/分层架构（D1/D3 结构）原样保留，符合"临时口径可换、算法骨架不轻易动"的一贯打法——本次是骨架内的对象替换，不是架构重来。

### D11：匹配粒度改为料品级汇总归集，四维改「料品+数量+未税金额+税额」
- **匹配标识改料品**：供应商 INV 无我方物料编码，以"规格型号/项目名称"经《料品↔INV规格型号/项目名称映射表》解出料品编码；MVP mock 层比照原 Non-Goal（物料编码映射表构建不在本次实现）延伸——mock InvoiceLine 直接以 `item_code` 落地（相当于假设映射已解出，代 OCR+映射的产出），真实映射表构建仍是晋档 2 前置。
- **聚合算法**：`build_item_matches(ap_lines, invoice_rows)` 按 `(ap_no, item_code)` 双向聚合——AP 侧多行求和（qty/untaxed_amount/tax_amount），INV 侧多行求和（同）——一次聚合天然吸收 AP↔INV 的多对一/一对多/多对多，不需要额外分支逻辑。**迭代方向定为 AP 驱动**（遍历 AP 聚合键，查 INV 聚合是否存在）——因为 AP 是"即将触发付款"的一方，是需要被验证是否有凭证支撑的对象，此方向与原 D3"以发票(付款请求方)为迭代驱动、核验 GRN(事实方)是否支撑"的精神完全对应（只是新架构下"付款请求方"从 Invoice 换成 AP，"事实/凭证方"从 GRN 换成 Invoice 本身）。
- **四维改为「料品+数量+未税金额+税额」**：原"物料编码匹配"维度因料品即聚合键而隐式满足（不再需要单独判断）；原"税率一致性"布尔维度改为"税额"数值容差维度（`TAX_AMOUNT_TOLERANCE`，尾差同 `AMOUNT_TAIL_TOLERANCE` 量级占位 0.5 元），因为按料品汇总后比较税率是否相等已无意义（汇总后应比较税额绝对值）；原"金额"维度改为"未税金额"（贴合 INV 实际字段，含税金额=未税金额+税额分开建模，见 D-字段）。
- **判定优先级结构不变**（命中即停）：① 无发票支撑（原"无GR支撑"改名，语义对应：AP 料品行存在但该 `ap_no` 下找不到对应料品的 INV 支撑）→ ② 明细错位（跨料品总额校验，见 D-明细错位）→ ③ 数量/未税金额/税额任一维度超容差 → ④ 仅未税金额差在尾差容差内 → ⑤ 全维度在容差内=完全匹配。`assign_category` 函数结构与 v1（D3）逐行对应，仅将"item_code_match/tax_rate_match 布尔维度"换成"tax_ok 容差维度"，"amount_diff(含税)"换成"untaxed_amount_diff(未税)"——不改判定顺序、不改函数骨架。
- **"明细错位"跨料品配对算法**：同一 `ap_no` 下，若存在 ≥2 个料品的未税金额差异同时超尾差容差、方向相反（一多一少），且该 `ap_no` 下所有料品未税金额差异总和在 `AP_LEVEL_AMOUNT_TOLERANCE`（原 `PO_LEVEL_AMOUNT_TOLERANCE` 改名，同量级 0.5 元，语义从"PO 号总额容差"改"AP 单总额容差"）内一致——判"明细错位"。单料品超容差无配对、或同向配对，均不得误判（两条反例回归照搬 D3 精神，改用料品级夹具重构）。
- **数据字段（v3 修正4）**：`InvoiceLine` 字段改为 `inv_no/ap_no/item_code/unit/unit_price/inv_qty/untaxed_amount/tax_rate/tax_amount/inv_date`（贴 INV 实际票面字段：项目名称→item_code(经映射)/单位/单价/金额(即未税金额)/税率/税额/发票号/开票日期）。

### D12：新增 AP-PO 单价强制比对（独立模块，堵配票改金额控制漏洞，R7 容差占位）
- ERP 配票环节允许手动改 AP 金额、无 PO 强制校验——存在"AP/INV 单价与 PO 单价不一致仍过流程"的风险（尤其虚报/多算的方向，比"总额对但明细错位"更直接损害现金）。新增独立函数 `price_check.check_ap_po_price(ap_lines, po_lines, cfg)`：每条 AP 行的 `unit_price` 相对其 `(po_no, line_no)` 对应 PO 行 `unit_price` 的偏离比例，超 `cfg.AP_PO_PRICE_TOLERANCE_PCT` → `exceeds_tolerance=True`。
- **与五类判定的合并规则**：价格超差是独立于料品汇总五类判定的"第六项校验"——即便某料品的五类判定结果是"完全匹配"，只要其任一 AP 行价格超差，报告聚合层（`recon_report`）仍 MUST 将该料品状态强制改写为 `needs_review`（不因四维吻合而被完全匹配的"建议通过不强制人工"路径放过）。
- **R7 容差占位**：唐燕萍尚未定稿具体量级（授权她定，留汇率波动豁口），本次 CC 拟定 **占位 ±3%**（`config.AP_PO_PRICE_TOLERANCE_PCT = 0.03`，人民币兑主要外币短期波动的常见量级），落 `config.py`，唐燕萍定稿后只换该常量，不改 `price_check.py` 函数结构。真实外币折算（按付款日汇率折算后再比对）留 `fx_rate` 参数位，MVP mock 假设同币种、暂不实现折算步骤。
- **金额脱敏**：`PriceCheckResult` 落盘/报告只留 `price_diff_pct`，不落 AP/PO 原始单价绝对值（D7 红线延伸）。
- 理由：这是本次 v3 修正里**唯一新增的检测维度**（而非既有维度改名/换算法），独立成模块便于唐燕萍定稿 R7 时单独替换、不牵动料品汇总匹配引擎；也便于未来汇率折算逻辑只改这一个文件。

### D13：黄金测试用例来源——CC 按 v3 定稿文档自拟 strawman，唐燕萍后续批改
- 本次 v3 引擎调整无法等应付会计逐一提供真实场景数据（会阻塞本次建造窗口），采用与 D2/D5 一致的"AI 起草·专家批改"打法：CC 依据《财务域场景v3-局部定稿》§1 修正1-7 + 《FI4 就绪清单》v3 banner/R1-R7 strawman 自拟黄金测试用例（覆盖五类判定 + 明细错位正反例 + 价格超差/未超差 + 多对一/一对多/多对多聚合 + 孤立发票），提交 Paul 拍板本 design 后先行 apply；唐燕萍 R1-R7 规则草案（约 2026-08 底）交付后，回归比对 strawman 用例是否需要调整，不影响本次先行 commit。
- 备选：暂缓引擎调整、等应付会计提供真实用例——否决（会话已明确"真实数据接入等 7/10+ 端点实通 + 唐燕萍 R1-R7 定稿，本次只做 mock 层调整"，用例来源不应反向阻塞 mock 层先行）。

### Non-Goals 追加（v3，不改变原 Non-Goals 范围，仅重申/收紧）
- FI2-6（退单）初期缩范围进一步明确：本次 v3 调整**不新增任何退单相关代码**（原 MVP 本就未实现退单模块），退单仅"拦截+通知"停留在文字口径层面，退单闭环统计留待后置——与原 design Non-Goals 一致，无新增实现负担。
- 料品↔INV规格型号/项目名称映射表构建（OCR 输出解析真实规格型号→料品编码）不在本次实现范围，mock 层假设映射已解出（同原 Non-Goals"物料编码映射表构建"条延伸）。

### Risks / Trade-offs 追加（v3）
- **[迭代方向选择的假设风险]** → D11 选择"AP 驱动迭代、以 INV 为凭证方"，若唐燕萍批改后认为应双向都检测（AP 无 INV 支撑 + INV 无 AP 支撑都要各自标红），需回头加一条"孤立发票有 ap_no 但料品在该 AP 下找不到"的反向检测分支——本次先做单向（AP 驱动），双向扩展是可加而非需重构的增量。
- **[R7 占位值与真实汇率波动的偏差]** → ±3% 为 CC 估算的常见量级，非唐燕萍拍板；晋档 2 前必须替换，MVP 阶段不作为真实拦截依据。**已于 D14 替换为真值 ±2%**。
- **[黄金用例非专家批改的假阳性/假阴性风险]** → D13 已限定用例来源为 strawman，本 design 的 Migration Plan 步骤 7（黄金基准回归）产出后需在 tasks.md 新增"唐燕萍批改黄金用例"收口项，避免误当作已定稿口径。**D14 已按真值回归更新 golden 预期，但 strawman 用例本身仍待批改**。

---

## D14：R1/R5/R7 定稿真值落地 + R5 门禁新增 + 料品编码归一化（2026-07-10，队列 #14/#16）

> 触发：唐燕萍团队两份圈改回件（`FI2-三单匹配-就绪清单与MVP细化-回复.docx`）+ Paul 三拍板（R5 门禁分母/阈值、R7 汇率两方案、料品映射开放点），产出《FI2-FI3-规则定稿-交CC-2026-07-10.md》（队列 #14）。较原计划（约 2026-08 底）提前 7 周交付。CC 分支 `feat/fi2-v3-recon-engine` 承接落地（队列 #16）。**判定不触发重组**（无编号/排期/场景变动）。

### D14-a：R1 真值——数量精确匹配 + 未税金额比例备用 + 税额随税率动态换算
- **数量容差**：合计 ±0（精确匹配），取消 CC 占位的 ±2%/±5 个豁口。`config.QTY_TOLERANCE_PCT`/`QTY_TOLERANCE_ABS` 默认改 0，`match_engine._qty_in_tolerance` 函数结构不变（配置归零后天然只放行 diff=0）。
- **未税金额容差**：绝对值 ±0.5 元/料品不变，新增"比例口径备用：未税 ≤0.5%"（`config.UNTAXED_AMOUNT_TOLERANCE_PCT=0.005`），两者取宽松者——`match_engine._amount_in_tolerance` 新函数，仿 `_qty_in_tolerance` 的 OR 模式。
- **税额容差**：R1 原文"税额随税率"——不是独立固定值，而是按该料品 AP 侧有效税率动态换算：`tax_tolerance = AMOUNT_TAIL_TOLERANCE × ap_tax_rate`（`ap_tax_rate = ap_tax合计/ap_untaxed合计`，AP 未税金额合计为 0 时记 0）。`ItemMatch` 新增 `ap_tax_rate` 字段（`build_item_matches` 填），废弃独立的 `TAX_AMOUNT_TOLERANCE` 常量。
- 理由：三条真值均只改容差判定的输入来源（配置值/换算公式），未改变 `assign_category` 的判定优先级结构，符合"唐燕萍定稿后只换配置层"的既定打法。

### D14-b：R5 门禁新增——整单差异总额分级 L2/L3（原设计完全没有此概念）
- **背景**：R5 是 v1/v3 设计均未涉及的**全新规则**——原 D4 只有"四类非完全匹配强制 needs_review / 完全匹配标建议通过"的二元路由，唐燕萍团队新增"整单差异总额"维度的三级路由：差异总额 ≤¥1（或 ≤0.5%，两者取宽松者，比例线复用 R1 备用线）→ **L2 AP 自行消化**（不转人工）；超线 → L3 人工。
- **范围：仅对"金额微差"分类生效（Paul 2026-07-16 拍板：不扩大到"明细错位"，本条为最终口径）**。理由：
  1. "金额微差"由构造保证是纯"未税金额尾差"问题（`assign_category` 判定路径要求 `qty_ok` 且 `tax_ok` 均通过才会走到未税金额分支）——门禁"差异总额"语义上就是指这类纯尾差累计，而非数量/税额/结构性问题。
  2. 若门禁面向"数量金额不符"生效，会产生假阴性：某料品因**税额**大幅偏差（如税率错录）被判"数量金额不符"，但其**未税金额**恰好持平（diff=0）——若门禁只看未税金额总差，会误判该 AP 整单"差异总额≈0"从而错误降级为 L2，掩盖真实的税额错误（已在 golden 样本 AP-6000 场景验证到此陷阱）。
  3. 若门禁面向"明细错位"生效，该类按定义（D11）本身要求 AP 级总额差异已在 `AP_LEVEL_AMOUNT_TOLERANCE`（0.5 元）内，几乎必然满足 R5 的 ¥1 门禁线，会导致"明细错位"永远自动降级 L2——但明细错位是**结构性问题**（料品间错位，涉及不同料品/成本归属，即便净额抵消也需人工核实是否记错了具体是哪个料品/项目），不应仅因总额小而免检。**Paul 已确认维持这一收紧解读，明细错位不纳入 R5 门禁范围**，代码无需改动。
- **实现**：`recon_report._l2_gated_ap_docs`——按 `ap_no` 聚合"金额微差"料品的未税金额差异总额，分母 `_po_untaxed_by_ap` 取该 `ap_no` 下 AP 明细行关联的 `(po_no, line_no)` 精确匹配对应 PO 行未税金额（`qty×unit_price`）求和（"整单（PO 行）合计未税金额"，用 PO 侧独立基线而非 AP/INV 自身总额，避免分母被同一份差异污染）。降级后状态字段新增 `l2_self_resolved`（原只有 `needs_review`/`l3_suggested_pass` 二态），报告 `summary` 新增 `l2_self_resolved` 计数。
- **优先级**：价格超差（R7/`price_check`）> R5 门禁 > 原始五类判定路由——即便"金额微差"整单差异在门禁线内，若该料品同时价格超差，仍 MUST 强制转人工（与 D12 一致的"价格校验独立于五类判定"精神）。
- **向后兼容**：`build_report` 新增 `ap_lines`/`po_lines` 两个可选关键字参数，缺省（`None`）时门禁计算跳过（返回空集合），所有"金额微差"维持原 needs_review 行为——不强制所有调用方立即改造。`run.py` 已接入传参。

### D14-c：料品编码归一化预处理（新增 `item_normalize.py`）
- 唐燕萍团队实操描述：AP/INV 侧同一料品的编码常见差异模式=字符空格、全角/半角、括号类符号、"-"与"/"记法不一致，均为表层书写差异。新增 `normalize_item_code`（NFKC 全角转半角 + 分隔符等价类映射 + 去空格/括号 + 大写化），仅用于 `match_engine.build_item_matches` 的聚合 key 比对，不改写原始存储字段（报告/审计仍展示 AP 侧原始 item_code）。
- **明确不做**：模糊匹配 + 置信度分档 + 人工确认队列 + 自学习精确对照表（唐燕萍团队回件里"料品映射"段的完整机制）——这是依赖真实《料品↔INV规格型号/项目名称映射表》的长线能力，留待 U9C/OCR 真实数据接入阶段另行设计，本次只覆盖"归一化预处理"这一个子项（唐燕萍团队原话"应覆盖大头"）。

### D14-d：R7 真值——人民币 ±2% 落地；外币过渡规则与方案一升级位均未实现
- 人民币供应商统一 ±2%（方案二），替换 CC 占位 ±3%，`price_check.py` 函数结构不变。
- **外币供应商过渡规则未实现**："外币供应商（三家，供应商清单向唐燕萍团队取）容差内连续 2 次同向偏移 → 推人工抽查"——供应商清单尚未提供（`config.FOREIGN_CURRENCY_SUPPLIERS` 暂空），且该规则本身需要**跨运行历史状态**（"连续 2 次"要求比对历史批次结果，而本 MVP 每次 `run()` 均为无状态单次计算）——两个前置条件均未就绪，本次不实现，列入 future-work（见 tasks.md）。清单/状态机制到位前，外币供应商行按人民币同一 ±2% 处理，不触发增量抽查。
- **方案一升级位未实现**：原始外币单价 + 下单日汇率字段，IT 评估中，按唐燕萍团队要求"写入 future-work，勿实现"，本次未触碰 `price_check.py`/`models.APLine`/`models.POLine` 字段结构。

### Open Questions 追加（D14，🔴 待唐燕萍团队/Paul 批改，不阻塞本次 mock 先行落地）
- ~~**R5 门禁范围是否应扩大到"明细错位"**~~ → **✅ Paul 已拍板（2026-07-16）：不扩大**，R5 门禁维持仅对"金额微差"生效，D14-b 收紧解读即为最终口径，代码无需改动。
- **R5 分母的"整单"颗粒度**：本次按 `ap_no` 关联的 `(po_no, line_no)` 精确匹配求和（而非整张 PO 单不论是否被本次引用的行都计入）；若唐燕萍团队原意是"整张 PO 单"而非"该 AP 引用到的 PO 行集合"，需回头调整 `_po_untaxed_by_ap`。
- ~~**外币供应商清单 + 跨运行历史状态设计**~~ → **✅ Paul 已拍板（2026-07-16）：明确推迟**——先以当前最小 MVP（外币供应商行按人民币同一 ±2% 处理，不触发增量抽查）为准；待 IT/唐燕萍团队提供外币供应商清单后再评估是否要实现"容差内连续 2 次同向偏移推人工抽查"的跨运行历史状态机制，非本次范围、不阻塞交付，见 D14-d + tasks.md 10.12。

---

## D15：真实 U9C 财务接口接入（feed_source 真实源）+ R7 外币供应商真值 + 三实测点结论（2026-07-19/20，队列 #60，🔴 待 Paul 审）

> 触发：财务数据闸已实质解除（队列 #6/#47，唐燕萍团队 07-17 交付《U9C 自定义 API 接口文档》），队列 #60 要求把 `feed_source.py` 的 `u9c` 源从"全量 fail-loud 占位"推进到真实可用，并落 R7 外币供应商清单真值 + 回写 3 个实测结论。**本节仅为 propose→design 阶段产出，代码未动，等 Paul 审后再 `/opsx:apply`。**

### D15-a：三实测点结论（真实只读探测，2026-07-20，服务器 `192.168.100.49:6666`）

**① 批量/按期间查询——初测部分可行（AP 端有服务器 bug），2026-07-21 复验已修复**
- 通过刻意触发的报错栈确认 `AP/Query` 控制器真实签名：`Query(apiKey, docNo, supplierCode, invoiceNo, itemCode, orgCode, page, pageSize)`——存在 `docNo` 之外的过滤参数，理论支持批量。
- **2026-07-20 首次实测**：`AP/Query` 不传 `docNo` 直接抛 `ArgumentOutOfRangeException`（`docNo` 是实质必填）；传 `supplierCode`/`itemCode`/`invoiceNo` 任一（不带 `docNo`）均抛 `SqlException: 列名 'Supplier_Code'/'ItemInfo_ItemCode'/'InvoiceNo' 无效`——三个过滤参数的 SQL 拼接列名全部写错，是**服务器端真实 bug**，不是我方调用姿势问题。`Purchase/Query`、`GR/Query` 不传 `docNo` 时直接返回全表（分别 25711、26760 行）且分页/`supplierCode` 过滤有效，问题当时集中在 `AP/Query`。已登记 IT 缺口书面跟催陈承（队列 #60/#61，`6-人才与组织/部门AI专员跟进/IT部-陈承-跟进-2026-07-20-*.md`）。
- **✅ 2026-07-21 复验（队列 #61）：已修复**——陈承排查发现根因其实是另一件事（新版本 DLL 把 apiKey 从硬编码改读服务器 `Web.config` 的 `ZP_API_KEY`，部署时该配置项遗漏导致全端点一度 401），修复+`iisreset` 后复验，**`AP/Query` 的 `supplierCode`/`itemCode`/`invoiceNo` 过滤 + 不传 `docNo` 全表分页均已恢复正常**（`test_real_ap_query_batch_filter_now_fixed` 四项全过，`supplierCode=ZA0066`/`itemCode=R01A.0175`/`invoiceNo=26942...` 均返回真实非空结果，全表 `Total>26000`）——推测是同一批 DLL 更新顺带修了 SQL 列名映射，具体是否为同一次修复陈承未明确说明，不深究。
- **结论（更新）**：`AP/Query` 批量过滤能力现已可用，D15-b 当初"MVP 只能 docNo 单号驱动"的前提已不成立。**是否要把 `FeedSource`/连接器改造为批量驱动（如按供应商/按期间自动拉取待对账 AP 单，取代现状"财务专员手工给单号清单"）是一个新的架构决策，本次未做**（Paul 2026-07-21 只要求复验+销行 #61，未要求重新设计取数路径）——留作后续独立评估项，见 tasks.md 11.14。

**② `FinalPriceTC`（PO）vs `TaxPrice`（AP）含税性——均为含税单价，可直接比对，R7 比对基准成立**
- 实测 `ZPCG20251226004`（艾睿）：`ConfirmQty×FinalPriceTC = TotalMnyTC`（价税合计），即 `FinalPriceTC` = 含税单价。
- 实测 `AP-2026030057`：`APQtyTU×TaxPrice = TotalAmtTC`（价税合计）= `NonTaxAmtTC+TaxAmtTC`，即 `TaxPrice` = 含税单价。
- **交叉验证**：AP-2026030057 第 1 行 `SrcPONo=ZPCG20251221001, SrcPOLineNo=240`，回查该 PO 该行 `FinalPriceTC=0.42`，与 AP 行 `TaxPrice=0.42` **完全一致**。
- **结论**：`price_check.py` 现有实现（AP `unit_price` 直接比 PO `unit_price`，无需换算）在真实字段下**口径成立**，`config.AP_PO_PRICE_TOLERANCE_PCT`（±2%）可直接套用真实字段，无需新增税基调整逻辑。

**③ 原币直比可行性——机制成立（架构验证），三家外币供应商专属数值抽样受①的 AP 端限制未能定向核对**
- 两侧单价字段均为 `...TC` 后缀（Trade Currency，交易原币），非强制折算为人民币的独立字段——`②` 的交叉验证已证明同一 `(po_no,line_no)` 关联下 PO/AP 的 `TC` 单价逐位精确相等，即该字段在系统设计上就是"原币对原币"存储，没有汇率折算环节需要我方处理。
- 通过 `Purchase/Query?supplierCode=ZA0066` 验证艾睿（R7 三家之一）有大量真实历史 PO（如 `PO02108010222` 等），`FinalPriceTC` 全部是小数位数值（与人民币供应商同量级字段格式一致，无科学计数法/异常精度），字段机制统一适用。
- **未完成项**：因 `AP/Query` 端无法按 `supplierCode` 批量取数（见①），未能定向抓取艾睿/安富利/英恒任一家的真实 AP 行做"PO↔AP 同笔原币直比"的专属数值核对（仅在 RMB 供应商 ZA0114 上做过精确核对）。
- **结论**：**方案二等价加强（原币对原币直比、汇率不进入比较）机制上成立**，config 层面可直接把 `FOREIGN_CURRENCY_SUPPLIERS` 落真值、`price_check.py` 现有"不分币种统一按 `unit_price` 直比"的实现天然适用（无需分支逻辑）；三家专属数值的最终确认，待 IT 修复①的 bug 或财务侧提供一个已知外币 AP 单号后可即时补验，**不阻塞本次落地**，8 月底真实小样本验证阶段一并覆盖。

### D15-b：真实连接器接入范围与架构落点

**接入范围**：`Purchase/Query`（PO）/ `GR/Query`（GR）/ `AP/Query`（AP）三端点接入 `feed_source.py` 的 `u9c` 源；`Attachment/List`+`Download`（发票源）**继续留桩不实现**（OCR 选型未定，队列 #59 跟催中）——即 `load_invoice`/`load_payment` 对 `u9c` 源**保持无条件 fail-loud**，不因本次改动而变化（Invoice 无结构化 API，只能靠 OCR 读附件；Payment 本场景本就只加载不参与匹配，优先级最低，一并留待 OCR 就绪后统一评估）。

**连接器落点**：新增方法于平台 `zhuopin_platform.shared_tools.erp_connector.connector.ZpConnector`（而非 FI2 场景内自建连接器）——理由：① 复用其已验证的 GET+`apiKey`+JSON 信封解析范式（与 `_stock_query`/`Stock/Query` 同源同构，`{"Success":true,"Data":{"Rows":[...]}}`）；② FI3（付款校验，另起场景）已确认要复用 `Supplier/Query`/`POChange/Query`/`Pay/Trace`/`RE/Query`（队列 #6 回复），提前放平台层可避免 FI3 立项时二次搬迁。新增 `get_purchase_lines(doc_no)`/`get_gr_lines(doc_no)`/`get_ap_lines(doc_no)`（各自 GET 对应端点 + `docNo` 参数，返回校验后的 `list[dict]`；FI2 场景层 `feed_source.py` 沿用既有 Pydantic 边界校验做字段映射到 `POLine`/`GRNLine`/`APLine`，连接器层不重复建模——分工同现有 `_zp_post` 与场景层解析的关系）。

**凭据（Paul 2026-07-20 拍板）**：复用现有 `STOCK_API_BASE`/`STOCK_API_KEY`——Paul 确认本次新增的 7 个接口与既有预测订单（FO）、库存查询（Stock）**同一接口地址、同一 apiKey**，不新开环境变量。连接器新方法与 `_stock_query` 共用同一对 env key，真值只落 `5-平台底座/.env`（gitignore），不入库、不落审计、不落日志。

**批量缺口下的 MVP 调用形态**：鉴于①的结论（AP 端只能按 `docNo` 单查），`FeedSource` 新增构造参数 `ap_doc_nos: list[str] | None`（`u9c` 源下必填，由调用方——真实小样本验证阶段由财务专员提供待核对的 AP 单号清单——显式传入，不做"自动发现全部待对账 AP"）：
1. 对每个 `ap_no` 调 `get_ap_lines(ap_no)` 汇总 `APLine`。
2. 从已获取 AP 行的 `SrcPONo` 去重集合，逐个调 `get_purchase_lines(po_no)` 汇总 `POLine`（作 AP-PO 单价前置参照）。
3. 从已获取 AP 行的 `SrcRcvNo` 去重集合，逐个调 `get_gr_lines(rcv_no)` 汇总 `GRNLine`（本次匹配数学仍不消费，随 D10 既定角色）。

`load_po_lines()`/`load_grn()`/`load_ap_lines()` 三个方法保持**零参数**调用签名不变（现有 `match_engine`/`run.py` 调用方零改动），`ap_doc_nos` 走构造函数注入，内部据此驱动上述三步拉取——与 `ZpConnector.__init__` 里 `srm_connector: object | None = None` 的"可选注入、None 时行为不变"范式一致。未注入连接器（`u9c_connector=None`，现状默认）时，`u9c` 源五个 loader **继续对现有测试 `test_u9c_fail_loud_all_loaders` 保持完全一致的 fail-loud 行为**——本次是纯增量能力，不改默认路径。

### D15-c：R7 外币供应商清单真值落地

`config.FOREIGN_CURRENCY_SUPPLIERS = ("ZA0066", "ZA.0368", "ZA0020")`（艾睿/安富利/上海英恒，唐燕萍团队 07-14 回件，已通过 `Supplier/Query` 真实核实三家均为在库真实供应商）。**注意**：`ZA.0368` 含点号，D14-c 的 `item_normalize.py` 归一化仅作用于 `item_code`（料品编码）聚合 key，不触碰 `SupplierCode`/`FOREIGN_CURRENCY_SUPPLIERS` 比对——不得误把供应商编码里的 `.` 也归一化掉。

### Risks / Trade-offs 追加（D15）

- ~~**[AP 批量查询 SQL bug 阻断"按期自动取数"]**~~ → **✅ 2026-07-21 已由 IT 修复（队列 #61）**，`AP/Query` 批量过滤现已可用；D15-b 的 `ap_doc_nos` 手工清单驱动仍维持不变（未做批量取数重构，是否重构留独立评估，见 tasks.md 11.14），不再是被动受限于服务器 bug，而是主动选择"暂不扩大本次范围"。
- **[外币供应商专属数值未定向核实]** → D15-a③ 机制验证充分但数值样本未覆盖三家外币供应商本身，存在极小概率"三家里有一家的 `TC` 字段填报习惯不同于其余供应商"的未知风险；8 月底真实小样本验证阶段第一批次建议**优先覆盖三家外币供应商的 AP 单**作定向复核，尽早排除。
- **[连接器复用范围先行大于当前需求]** → `get_purchase_lines`/`get_gr_lines`/`get_ap_lines` 落地在平台层是为 FI3 预留，若 FI3 最终排期/范围有变，这三个方法会有一段时间只有 FI2 一个消费方——可接受（同 D1 分层理由，公共连接器方法闲置成本远低于日后跨场景搬迁成本）。

### Open Questions（D15，✅ Paul 2026-07-20 已拍板，全部收口）

- ~~是否批准 D15-b 的连接器落点与 MVP 调用形态~~ → **✅ 批准，按此方案 apply**。
- ~~AP 端批量查询 SQL bug 是否单独出报告跟催~~ → **✅ 立即出报告跟催陈承**（IT 缺口书面留痕 + 机器人直推，见 tasks 11.9）。
- ~~`FI_API_BASE`/`FI_API_KEY` 是否独立命名~~ → **✅ 复用 `STOCK_API_BASE`/`STOCK_API_KEY`**——Paul 确认本次 7 个财务接口与既有预测订单/库存查询同一接口地址、同一 apiKey，不新开环境变量（见 D15-b 凭据段已更正）。

---

## D16：AP 批量自动取数（供应商驱动），取代手工单号清单（2026-07-21，队列 #61 追加，Paul 直接拍板）

> 触发：队列 #61 复验 apiKey 恢复问题时，`test_real_ap_query_batch_filter_now_fixed`（D15-a① 的回归哨兵）意外发现——陈承那批 DLL 更新顺带修复了 `AP/Query` 的 `supplierCode`/`itemCode`/`invoiceNo` 过滤 SQL bug（此前记录在 D15-a①，导致 D15-b 只能"手工给 AP 单号清单"）。Paul 直接拍板"改造成批量自动取数"，无需先出 design 停下等审（口头已定，本节是补记）。

### D16-a：批量维度选型——按供应商（`supplierCode`），不做按期间/按料品

- **可选维度**：`AP/Query` 控制器暴露 `supplierCode`/`itemCode`/`invoiceNo`/`page`/`pageSize`，**没有日期区间参数**（无 `dateFrom`/`dateTo` 之类），AP 明细行本身也没有独立的"单据日期"字段（只有 `InvoiceDate`/`APPDate`，均非 AP 单创建/入账日期）。
- **选按供应商**：① 唯一有真实业务含义、且已验证可用的过滤维度（`itemCode`/`invoiceNo` 虽也修复了，但"按料号找全部相关 AP"或"按发票号找一条"都不是"批量待对账"这个场景的自然驱动方式）；② 与 R7 外币三家供应商的既有关注点吻合，财务实操里"这周处理这家供应商的应付"是真实工作流；③ 全表分页（不传任何过滤）会把 26000+ 历史 AP 全部拉回，包含早已核销结案的陈年单据，噪音远大于信号，不适合作默认批量入口。
- **不做**：按期间自动发现"本月新增 AP"——服务器不支持日期过滤，若要实现只能"全量拉取+客户端按某个代理字段筛选"（如按 AP 单号里的年月编码模式猜测，`AP-2026030057` 形似含日期片段，但未经验证是否所有单据都遵循此命名规则，属不可靠猜测），本次不做这种脆弱实现；留待 IT 后续若肯加日期区间端点参数再重新评估。

### D16-b：实现——`ZpConnector` 分页聚合 + `FeedSource` 双模式并存

- `ZpConnector` 新增 `_fi_request`（单次 GET，返回完整响应体）+ `_fi_query_paginated`（循环 `page`/`pageSize` 直到 `len(rows)>=Total`）+ `get_ap_lines_by_supplier(supplier_code)`（`_fi_query_paginated` 的供应商特化）。既有 `_fi_query`（docNo 单查）改为基于 `_fi_request` 实现，行为不变、零回归（`test_fi_connector.py` 原 7 例全过）。
- `FeedSource` 新增 `ap_supplier_codes` 构造参数，与既有 `ap_doc_nos`（design D15-b 手工模式）并存、二选一——**同时传入时批量模式优先**（`_fetch_u9c_ap_rows` 判断顺序：`ap_supplier_codes` → `ap_doc_nos` → 均缺失则 `ValueError`）。理由：批量模式代表"这次要拉这几家供应商的全部待办"，手工模式代表"这次只想追这几张具体单子"，二者语义不冲突但批量意图更明确时不应被手工清单悄悄限缩范围。
- `load_po_lines`/`load_grn` 复用同一条派生管线不变（从 AP 行的 `SrcPONo`/`SrcRcvNo` 去重后取值），批量模式下 AP 行来源变了（供应商分页 vs 单号精确查），但下游派生逻辑完全一致，无需改动。
- 手工模式（`ap_doc_nos`）**未删除、继续可用**——财务专员只想追一批具体单号时仍是更直接的路径，不因批量能力出现而废弃。

### D16-c：真实验证

- `test_get_ap_lines_by_supplier_*`（`test_fi_connector.py`，3 例，mock 多页响应）验证分页在 `Total` 处正确停止、不多拉一页、URL 不含 `docNo`。
- `test_u9c_real_connector_batch_by_supplier_*`（`test_feed_source.py`，3 例，假连接器）验证批量模式与手工模式共享同一派生管线、缺省二者报错、同时传入批量优先。
- `test_real_get_ap_lines_by_supplier`（`test_real_integration.py`，`FI2_RUN_REAL=1` 门禁）真实验证：分页拉取 ZA0066（艾睿）全部 AP 明细行，条数与 `Total` 精确一致（分页无遗漏/无重复），行行 `SupplierCode` 校验通过——已真实跑通（2026-07-21）。
- 全量回归零漂移：平台 203 passed+1 skip（原 200，+3）、FI2 67 passed+5 skip（原 65，+2 net，含 1 例改名替换）。

### Risks / Trade-offs 追加（D16）

- **[全表拉取仍不可行]** → 若某供应商 AP 单据量极大（远超 848/1183 这类实测量级），`get_ap_lines_by_supplier` 会串行分页拉全量，无上限保护——当前未加安全上限，因为"按供应商"天然是有界的业务维度（不会无限增长到不合理量级），若未来某供应商单据量确实异常巨大，需回头补分页数上限 + 告警，非本次预判范围。
- **[批量模式覆盖面 vs 手工模式的取舍未来可能需要再权衡]** → 若财务实操发现"这周处理的 AP 不完全按供应商切分"（如同一供应商有些单子这周处理、有些下周），批量模式会一次性拉出该供应商全部历史欠账，需要财务人员自行从批量结果中筛选真正待办——这是本次未解决的"如何精确框定待对账范围"问题，日期过滤端点若 IT 后续提供会显著改善此点。

## D17：AP/Query 期间/余额过滤参数解锁——`get_ap_lines_by_supplier` 增补可选窄化条件（2026-07-22，队列 #70 追加）

> 触发：陈承 07-21 群回复——`AP/Query` 服务器端三过滤参数列名映射修复的同一批改动里，另新增了 `dateFrom`/`dateTo`（按立账日期 `AccrueDate` 筛选）+ `minBalance`（按余额下限）两个参数，正式库已同步部署。**D16-a 当时"没有日期区间参数"的结论已过时**——本节更新为最终口径：服务器现支持期间/余额过滤，D16-a 关于"不做按期间"的判断不再成立，但本次仍不做"供应商无关的整期批量取数"（见下）。

### D17-a：真实验证结论

- 用陈承给的测试链接实测三点：① `dateFrom`/`dateTo` 单独可用（`AccrueDate` 落在窗口内）；② 可与 `supplierCode` 组合（窄化到"某供应商某期间"）；③ `minBalance` 语义为**下限**（阈值升高、命中总数单调不增，返回行 `Balance` 均 ≥ 阈值）——不是精确匹配也不是上限，命名虽直观但实测前不能想当然。
- 三过滤参数（`supplierCode`/`itemCode`/`invoiceNo`）列名修复回归复验：`test_real_ap_query_batch_filter_now_fixed`（已于 07-21 落地）+ 本次 `test_real_integration.py` 全量重跑，均绿，属既有修复的再确认，非新发现。

### D17-b：实现范围——只增强 `get_ap_lines_by_supplier`，不新增供应商无关的整期方法

- `get_ap_lines_by_supplier(supplier_code, *, date_from=None, date_to=None, min_balance=None)`：三个新参数均为可选关键字参数，缺省时行为与 D16 完全一致（向后兼容，`supplierCode` 仍是必填主键）。
- **明确不做**：一个"供应商无关、纯按期间"的批量方法（如 `get_ap_lines_by_period`）——本次任务范围是"给 `get_ap_lines_by_supplier` 增补期间参数"，FI2 场景当前也没有"不看供应商、只看期间"的真实调用方（`FeedSource._fetch_u9c_ap_rows` 仍是供应商/单号二选一驱动）。若未来财务实操确实需要"月末全表按期间过一遍、不区分供应商"，应等真实需求出现再评估，避免预先建一个没有调用方的抽象。
- `FeedSource`/`fi2/run.py` 本次**未接线**这三个新参数——`ap_supplier_codes` 目前仍是纯供应商清单，未提供期间/余额窄化入口。这属于场景消费层的后续接入工作（真实小样本对账阶段，8 月排期内按需接入，若财务专员反馈"批量结果范围太宽、想按期间/余额窄化"再做），本次只解锁并验证连接器层能力。

### D17-c：验证与回归

- 单测：`test_fi_connector.py` +3（URL 含新参数/缺省时 URL 不含新参数即向后兼容/三参数互相独立可单独传）。
- 真实集成：`test_real_integration.py` +2（`test_real_ap_query_period_and_balance_params` 裸探测三点结论；`test_real_get_ap_lines_by_supplier_with_period_params` 连接器封装层端到端，分页条数与裸探测 `Total` 一致）。
- 全量回归零漂移：平台 211 passed+1 skip（原 208，+3）、FI2 67 passed+7 skip（原 67+5，+2 真实测试均门禁 skip 默认）。

---

## D18：Round-1 真实数据验证——CSV 快照 + 手工录入解耦 OCR，Attachment 端点首碰真实探测（2026-07-23，队列 #78，🔴 待 Paul 审）

> 触发：Paul 2026-07-22 拍板"全力抢 8 月上旬"（队列 #78，`1-转型规划/FI2真实验证提前排期评估-2026-07-22.md`），六项前置全清。CC 2026-07-23 领活、回填工期评估后，本节为 propose→design 阶段产出——**代码未动**，仅完成只读真实探测（不触碰任何真实数据的写/改），等 Paul 审后再 `/opsx:apply`。8 组真实样本：`AP-2026070036/070035/060004/040083/060073/2025120181/070071/050057`（覆盖外币三家+暂估价）。

### D18-a：Round-1 范围——只验匹配逻辑，OCR 自动直读解耦为独立第二轮

- 目标：用 8 组真实 AP 单跑通一次真实三单匹配，验证"AP vs INV 按料品汇总归集"（D11）+"AP-PO 单价校验"（D12）两条核心算法在真实数据上是否符合预期（有无假阳性"明细错位"、有无遗漏边界情形）。
- **不做**：腾讯云 OCR 自动直读发票集成——独立的第二轮工作（服务对接/准确率实测/陈承实测方案时序），本次完全不碰，不阻塞 round-1。
- **INV 数据来源改为"手工录入"**：round-1 的 8 张发票，经 D18-d 的 Attachment 端点取得扫描件 PDF 后，由 CC 逐张读取 + 手工誊录成 `InvoiceLine` CSV 行（`inv_no/ap_no/item_code/unit/unit_price/inv_qty/untaxed_amount/tax_rate/tax_amount/inv_date`），需在报告/交接材料中显式标注来源"人工誊录·非 OCR·仅供 round-1 验证"——不代表生产环境 OCR 准确率，不建立"AI 读票直接生产使用"的先例。

### D18-b：真实数据落地形态——PO/GR/AP 走真实 u9c 连接器落 CSV 快照，INV 走手工 CSV，合并后以 `data_source=csv` 跑一次

- 复用 design D15/D16 已实现的 `FeedSource(data_source="u9c", u9c_connector=..., ap_doc_nos=[8个AP号])`——`load_po_lines`/`load_ap_lines`/`load_grn` 三个 loader 已支持真实源（**代码已就绪，无需改动**），一次性拉取后落一份 `data/real_round1/{po_lines,ap_lines,grn}.csv`（字段＝ CSV loader 期望的既有五表 schema，即 `_map_u9c_*_row` 输出结果落盘，与 mock/csv 结构完全一致）——`.gitignore` 的 `data/real_*` 规则已覆盖，不入库（真实供应商名/单价/金额，财务红色数据）。
- INV 侧手工誊录一份 `data/real_round1/invoice.csv`（同目录，同规则不入库）。
- `payment.csv`：`run()` 当前不消费 `load_payment()`（`run.py` 从未调用），round-1 落一个仅 header 的空表保持 `csv` loader 完整性即可，不强求真实付款数据。
- 最终执行：`FI2_DATA_SOURCE=csv python -m fi2.run --csv-dir data/real_round1`，产出 `reports/fi2_reconcile_report.json`（同样被 `.gitignore` 覆盖不入库）+ 一份人工核对小结（对照 8 张发票原始扫描件，人工确认分类结果是否合理，尤其关注"明细错位"有无假阳性）。
- **为什么不直接 `--data-source u9c` 一次跑到底**：`load_invoice()` 对 `u9c` 源无条件 fail-loud（design D15-b 既定行为，是"Attachment/OCR 未就绪"的架构真相，刻意为之的红线）。round-1 走"落 CSV 快照 + 手工发票"是**旁路**，不改变、不短路这条不变量。

### D18-c：`run()`/CLI 接线（队列 #78 ①，通用能力，独立于 round-1 具体跑法）

- `fi2/run.py::run()` 新增可选透传参数 `u9c_connector`/`ap_doc_nos`/`ap_supplier_codes`，原样转给 `FeedSource` 构造——现状 `run()` **完全没有**这三个参数（`FeedSource` 支持但从未被接线，2026-07-23 工期评估已核实此为真实缺口，非文档滞后）。
- `main()`/CLI 新增 `--ap-doc-nos`（逗号分隔）/`--ap-supplier-codes`（逗号分隔）；`--data-source u9c` 时二选一，具体校验复用 `FeedSource` 已有逻辑（`main()` 只做透传不重复校验）。
- 这条 wiring 使**未来**任何人可直接 `FI2_DATA_SOURCE=u9c python -m fi2.run --ap-doc-nos AP-xxx,AP-yyy` 跑真实 PO/GR/AP（Invoice 仍会 fail-loud 报错并给出清晰提示——这是预期行为，不是 bug）。round-1 本次实际操作路径仍走 D18-b 的 CSV 快照（因需合并手工发票），但 wiring 本身独立于 round-1 具体打法，是队列 #78 ①项字面要求的通用能力，也是 tasks.md 13.6 遗留缺口的补齐。

### D18-d：新增连接器方法——`Attachment/List` + `Attachment/Download`（首碰新端点，已完成真实只读探测）

**探测结论（2026-07-23，服务器 `STOCK_API_BASE`，8 个真实 AP 单逐一探测，仅 GET 只读，无任何写操作）**：与本项目历史上"首碰新端点必踩服务端 bug"（AP/Query 列名错、Web.config 漏配 401、Stock/Query IsProdCancel SQL bug）的经验不同，这次探测**干净、无 bug**：

- `Attachment/List?docNo=<单号>&docType=AP` → 响应信封与 Purchase/GR/AP/Stock **不同**：`{"Success":true,"Data":[...]}`——`Data` 直接是**数组**（无 `Rows`/`Total` 包裹），每个元素 `{"ID":..., "Title":"<文件名>", "Size":"<如 63KB>"}`。
- `Attachment/Download?docNo=<单号>&docType=AP` → 直接返回**原始文件二进制**（非 JSON 信封），`Content-Type: application/pdf`，`Content-Disposition` 头带文件名。
- 8 个真实 AP 单逐一探测 `Attachment/List`，**每单均恰好 1 个附件**（无 0 附件/多附件情形需要消歧义处理）。
- 结论：两端点均已验证可用、字段/信封结构已探明，本次**不存在**"文档写了但调不通"的风险，无需再为"首碰新端点"预留额外缓冲。

**新增方法**（`ZpConnector`，仿 `_fi_query`/`_fi_request` 既有范式，同一 `STOCK_API_BASE`/`STOCK_API_KEY` 凭据）：

- `list_attachments(doc_no, doc_type) -> list[dict]`：GET `/zp/api/Attachment/List`，返回 `Data` 数组原样。因信封与其余财务端点不同（无 `Rows` 包裹），不能直接复用现有 `_fi_query`（该方法假设 `Data.Rows`），需单独实现——内部仍调 `_fi_request` 取 JSON 后自行读 `Data`，不新增 HTTP 请求逻辑。
- `download_attachment(doc_no, doc_type) -> bytes`：GET `/zp/api/Attachment/Download`，返回原始二进制。`_fi_request` 假设 JSON 响应，不适用于本方法，需单独实现一个"二进制 GET"辅助（可共享 `_fi_credentials()`）。

**落盘**：下载的 PDF 存 `data/real_round1/attachments/<ap_no>.pdf`（`.gitignore` 的 `data/real_*` 已覆盖，不入库——发票扫描件是真实财务凭证原件，含供应商/金额/开票信息，敏感数据不进版本库）。

**审计**：两个新方法复用 `_fi_request`/`_fi_credentials` 既有的 `self._audit.trace(...)` 留痕机制（如已注入 audit），不额外处理。

### D18-e：黄金基准——本次不做真实件替换/扩充合成 golden

- `tasks.md` 7.4 原文"真实小样本核对无静默丢单、无假阳性明细错位，产出真实 golden 替换合成 golden"——round-1 仅 8 个样本，大概率不会覆盖现有合成 golden 的全部五类判定 + 两个明细错位反例，若整体替换会**降低**回归覆盖面。
- **本次改为**：真实验证报告与合成 golden **并存**——合成 golden 继续作为引擎逻辑回归防线（不删不改，`data/golden/` 不变），round-1 真实报告是"这批真实数据人工核对通过"的独立验收记录（存一份 md 小结，不进 `data/golden/`）。真实 golden 的正式替换/追加，留待后续样本量扩大（更多批次真实数据积累）后再评估，不在本次 round-1 范围。

### Non-Goals 追加（D18）

- OCR 自动直读集成（腾讯云）——独立后续任务，不在本次 round-1 范围。
- `Attachment` 端点的多附件消歧义机制——8 个真实样本均恰好 1 附件，本次不做通用化抽象（若未来遇到多附件单据，届时再评估是否需要把 `List` 返回的 `ID` 传给 `Download` 定位具体文件）。
- 真实 golden 替换/扩充合成 golden——见 D18-e，留后续样本量扩大再评估。
- `FeedSource`/`run.py` 对 D17 期间/余额窄化参数（`date_from`/`date_to`/`min_balance`）的透传——round-1 用的是精确 AP 单号清单（`ap_doc_nos`），不需要窄化查询，维持 tasks.md 13.6 既定"待真实需求出现再接入"。

### Risks / Trade-offs 追加（D18）

- **[手工誊录的准确性无法达到生产级 OCR 标准]** → 本次目的仅为"验证匹配逻辑正确性"，誊录数据不进 golden、不代表生产读票能力，报告须显式标注数据来源为人工誊录。
- **[8 样本代表性有限]** → 已知覆盖外币三家 + 暂估价，但仍是小样本，验证结论只能证明"逻辑在这批真实数据上无误"，不能外推为"全量真实数据均无误"；更大批次真实运行仍是常规后续工作（tasks.md 7.4）。
- **[真实财务数据本地落盘期间的暴露面]** → `data/real_round1/`（CSV 快照 + PDF 原件）只在 CC 本机 worktree 存在，`.gitignore` 已覆盖不入库；round-1 收尾后若无需保留可清理（不同于 golden 需长期保留）。

### Open Questions（✅ Paul 2026-07-23 已拍板"按 CC 建议来；批准/apply"，全部收口）

- ~~D18-b 打法确认~~ → **✅ 按建议执行**：落 CSV 快照 + 手工誊录发票 + 合并跑 `csv` 源。
- ~~D18-d 落点确认~~ → **✅ 按建议执行**：`list_attachments`/`download_attachment` 落 `ZpConnector`。
- ~~D18-e 确认~~ → **✅ 按建议执行**：真实数据不替换/不扩充合成 golden，只出独立验证小结。

### D18-f：round-1 实施结果（2026-07-23，apply 完成，见验证报告）

> 全文见 `1-转型规划/FI2-round1真实验证报告-2026-07-23.md`（供财务专线/Paul/唐燕萍/姚祖怡复核）。本节只记对 design 有意义的偏差与新发现，tasks.md §14 记完整任务级明细。

- **样本覆盖 6/8**（非计划内偏差，原因均已查明，非引擎缺陷）：
  - AP-2025120181：`Attachment/Download` **真实服务端 302 重定向到 `localhost:5555`**，外部不可达——本项目历史上第 N 次"首碰新端点踩服务端 bug"，与 D18-d 探测时"8 单逐一探测均正常"的结论不矛盾（探测时只测了 `Attachment/List` 全部 8 单 + `Download` 抽验 1 单，未对全部 8 单做 `Download` 抽验——**方法论教训**：`List`/`Download` 是两个独立行为，`List` 正常不保证 `Download` 也正常，未来同类首碰探测应对每个待用样本都做端到端抽验，不只抽验其中 1 个）。已在验证报告标注需 IT（陈承）跟进，不阻塞 round-1 结论。
  - AP-2026050057：探测为**跨多张 AP 单的合并结算发票**（100 行/8 页，发票金额>该 AP 单独金额）——揭示真实业务存在"一票多结"场景，超出当前 `InvoiceLine.ap_no` 一票一单的口径假设，round-1 范围内未强行处理（手工比对 100 行不可靠），登记为后续设计考量（round-2 OCR 阶段优先覆盖）。
- **核心匹配逻辑（D11）验证结果**：6 组样本、10 个料品，**100% 判定"完全匹配"，零假阳性**（数量/未税金额/税额三维精确吻合人工誊录数据）——round-1 主要验证目标（"AP vs INV 按料品汇总归集"逻辑在真实数据上无误）达成。
- **AP-PO 单价校验（D12/R7）意外发现**：10 个料品中 3 个超差（-6.1%~-44.7%），溯源发现一个**当前 design 未覆盖的真实缺口**——`price_check.py` 只比对 AP 单价与 `Purchase/Query` 的**原始下单价**，未消费 `POChange/Query` 的变更后价格；若 PO 有正式变更单调整过价格，比对基准未跟进更新，可能产生假阳性。三例中 1 例（PO 有 24 次变更记录）符合此假阳性风险，另 2 例（PO 零变更记录）排除此解释、判断为需业务侧核实的真实偏离。**未在本次 round-1 范围内改代码**（只读探测 `POChange/Query` 确认现象，未修 `price_check.py`），登记为独立后续设计评估项（tasks.md 14.13）。
- **实现期间发现并修正一处真实 bug**（非 U9C 端点问题，本项目代码自身）：`ZpConnector.audit=` 参数期望 `zhuopin_platform.shared_tools.connector_audit.ConnectorAudit`（轻量连接器访问痕迹），与业务判定用的 `zhuopin_platform.audit.AuditLogger` 是两个物理分离的类（同 SC8 `run_baoguan_web.py` 范式）；`run.py::main()`/新增 `fi2/dump_u9c_snapshot.py` 最初误传了 `AuditLogger`，真实调用时抛 `AttributeError: 'AuditLogger' object has no attribute 'trace'`（mock 单测覆盖不到，因为单测不触网也不会走到 `_fi_request` 的 `self._audit.trace()` 调用），已在真实拉取时发现并修正。**方法论教训**：涉及审计接线的新代码路径，仅靠 mock 单测不足以捕获这类"类型对不上但两者都叫 audit"的接线错误，需至少跑一次真实（或高保真集成）路径验证。
- **顺带修复一处环境问题**：本 worktree 的 `zhuopin_platform` 全局可编辑安装（无 venv、全局 site-packages）被另一 worktree（`qd-b-release-closure-b1a342`）静默劫持（已知隐患，见跨会话记忆 `project-shared-python-editable-install-collision`），导致临时脚本 `import zhuopin_platform` 解析到错误路径、找不到新增方法；`pip install --force-reinstall --no-deps -e <本worktree路径>` 重新指向本 worktree 后解决。`pytest`（在 `5-平台底座/zhuopin_platform` 目录内跑）本身不受影响（pytest 的 rootdir 插入 sys.path 优先于全局可编辑安装指针），受影响的只是脱离该目录直接跑的独立脚本。
