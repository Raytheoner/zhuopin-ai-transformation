# CLAUDE.md — FI2 三单匹配自动对账（场景级进度笔记）

> 本文件是 FI2 场景的本地记忆/进度笔记，与 FI1/采购(SC*)/质量(QD*)场景分开。
> 项目级上下文见仓库根 `CLAUDE.md`；FI2 规划权威见全景规划 §2.1.4 FI2 块、实施计划 §一财务表、
> 跨场景前置数据总表 FI2 行、`1-转型规划/FI2-三单匹配口径-mock备料.md`、
> `1-转型规划/FI4-三单匹配-就绪清单与MVP细化.md`（编号 FI4 即 FI2 内容，同一份口径）。
> 本场景 = CC 建造车间产物；**不改规划文档**（那是 Cowork 的活）；排期若变只在此记并提示 Paul 通知 Cowork。

## 定位（Paul 2026-07-07 拍板；口径 2026-07-09 v3 修正）
- FI2 = 财务/采购交叉场景，**2026-09 启动**。财务域 2026 年唯一按期落地场景（FI1 因需求变更暂缓封存）。
- 自动化等级 **L3**（建议/预警，人工确认，不自动过账）；L4（自动过账/拦截）待查准/查全率达标后另行晋级。
- **MVP 范围（v3 口径）**：FI2-1 数据准备与完整性校验 + FI2-2 **AP 单 vs INV 按料品汇总归集匹配**（PO 降级为 AP-PO 单价前置参照，非逐行匹配主体），四维＝料品/数量/未税金额/税额，结果分五类（🟢完全匹配/🟡金额微差/🔴明细错位/🔴数量金额不符/🔴无发票支撑）；**新增 AP-PO 单价强制比对**（堵配票改金额控制漏洞）。**"明细错位"检出仍是核心价值点**（总额对、料品间错位的成本失真场景，粒度从 PO 行改料品）。
- **明确不做·二期**：FI2-3 税率专项 / FI2-4 查重 / FI2-5 容差专项收口 / FI2-6 退单（初期仅拦截通知，闭环后置）/ FI2-7 考核 / FI2-8 学习。FI3（付款校验）为独立场景，不在本次范围。
- OEM 隔离【不适用】：FI2 读供应商/ERP 内部数据（PO/GRN/AP/发票/付款凭证），按根 CLAUDE.md §4 不强加 OEM 路由。

## Design 决策（Paul 2026-07-07 拍板 D2-D5 + 2026-07-09 v3 补充 D10-D13，详见 `openspec/changes/fi2-recon-mvp/design.md`）
1. **D2 临时容差口径**：数量 ±2% 或 ±N 个（两者取宽松者）/ 未税金额尾差 ±0.5 元/料品 / 税额尾差 ±0.5 元/料品（v3：原"税率必须一致"布尔维度改数值容差）。全部落 `config.py`，唐燕萍 R1-R7 规则草案（约 2026-08 底）定稿后只替换配置/规则版本号，不改引擎。
2. **D3/D11 五类判定边界 + 判定优先级 + "明细错位"算法（v3：粒度从 PO 行改料品）**：判定优先级（命中即停）＝ 无发票支撑 > 明细错位 > 数量金额不符 > 金额微差 > 完全匹配。"明细错位"＝同一 `ap_no` 下 ≥2 个料品未税金额差异同时超尾差容差、方向相反（一多一少）、且该 AP 单总额差异在 AP 级容差内——单料品超容差或同向超容差均不判错位（避免假阳性）。
3. **D4 L3 建议路由**：仅四类非完全匹配（金额微差/明细错位/数量金额不符/无发票支撑）强制标 `needs_review` 转人工；完全匹配类标 `l3_suggested_pass`（AI 建议通过，**未过账**），不强制逐笔人工，可批量抽查。
4. **D5 mock 五表结构**：`po_lines`/`grn`/`ap_lines`（v3 新增）/`invoice`（v3 改字段）/`payment`，接口通后 loader 换真实源、字段映射在接入层做，不改 `match_engine.py`/`result_classify.py`。
5. **D10 核对对象调整（v3）**：实际配票流程核对对象是 **AP 单 vs INV**（PO 降级为价格前置参照）；GR 保留加载，本次匹配数学暂不消费（供未来 FI2-1 完整性校验用）。
6. **D11 匹配粒度调整（v3）**：按 `(ap_no, item_code)` 双向聚合 AP/INV（天然吸收多对一/一对多/多对多），四维改「料品+数量+未税金额+税额」；迭代方向 AP 驱动（AP 是即将触发付款的一方，核验 INV 是否支撑）。
7. **D12 新增 AP-PO 单价强制比对（v3）**：独立模块 `price_check.py`，R7 容差占位 ±3%（唐燕萍授权定稿），报告聚合层合并——完全匹配料品若价格超差仍强制 `needs_review`（分类字段不变）。
8. **D13 黄金用例来源（v3）**：CC 按 v3 定稿文档自拟 strawman，唐燕萍 R1-R7 交付后批改，非专家定稿。
9. **D14 R1/R5/R7 定稿真值落地（2026-07-10/16）**：数量容差改精确匹配 ±0；未税金额新增比例备用 ≤0.5%；税额容差改按料品有效税率动态换算（非独立固定值）；**新增 R5 门禁**（整单差异总额分级 L2/L3，仅对"金额微差"生效，**Paul 2026-07-16 已拍板不扩大到"明细错位"，为最终口径**）；R7 真值 ±2%（外币过渡规则/方案一升级位因缺前置数据未实现，**Paul 2026-07-16 已确认明确推迟**，列 future-work，待清单到位后再评估）；新增料品编码归一化预处理（`item_normalize.py`，覆盖空格/全半角/括号/"-"vs"/"）。详见 `openspec/changes/fi2-recon-mvp/design.md` D14。

## 复用底座资产（照搬 FI1 场景模式）
- **数据接入三源统一接口**：`fi2/feed_source.py`，`data_source="mock"|"csv"|"u9c"`，切源不改匹配引擎；`u9c` 未就绪时抛 `zhuopin_platform.shared_tools.connector_errors.RealEndpointNotReadyError`（fail-loud，不静默回退）。
- **审计**：`zhuopin_platform.audit.AuditLogger`（`scenario="FI2"`，append-only hash-chain，IATF 3 年）。每料品匹配判定写 `action="item_match"`（v3 改名，原 `line_match`）；L3 改判写 `action="l3_override"`。
- **L3 改判 CLI**：`fi2/confirm.py`（比照 FI1 `confirm.py`），v3 改判键 `--ap-no`/`--item-code`（原 `--po-no`/`--line-no`），`--reason` 必填、幂等、写审计。
- **金额脱敏纪律（design D7，延伸至 D12）**：审计/报告只记 `qty_diff_pct`/`untaxed_amount_diff_pct`/`tax_amount_diff_pct`/`price_diff_pct`（差异比例）与分类结果，**不落原始发票/AP 单价、未税金额、税额绝对值**；比对运算过程中金额参与内存计算，不持久化明细金额。

## 红线（建造时守住）
- 先 mock 跑通逻辑，再切真实库（`csv`/`u9c` 接口就绪后另行提交变更包晋档 2）。
- 每料品匹配判定/分类写平台 `audit`（append-only，金额脱敏，见上）。
- L3 门禁：四类非完全匹配 + AP-PO 价格超差 均强制人工确认，不自动过账；MVP 无 L4 自动执行入口。
- AI 结论恒为"建议/预警"，结案在财务人员——报告 disclaimer 显式标注"未过账"。

## 状态
- 2026-07-07：场景工程 scaffold + OpenSpec propose（D2-D5 Paul 认可）+ `/opsx:apply` 完成 **v1 MVP**（`models`/`feed_source`/`match_engine`/`result_classify`/`recon_report`/`confirm`/`run` 七模块，32 tests 全绿），commit `0d19918` 入库 master（未 archive）。
- **2026-07-09（v3 口径修正，CC）**：唐燕萍团队回传应付会计实操细化（核对对象 AP vs INV/料品汇总归集/发票源 U9C 附件/AP-PO 单价校验），Paul 全盘采纳。在本变更包内原地调整（未新开变更包）：
  - `models.py` 新增 `APLine`/`PriceCheckResult`，`InvoiceLine` 改挂 `ap_no`，`LineMatch`→`ItemMatch`（`(ap_no,item_code)` 键）。
  - `feed_source.py` 新增 `ap_lines` 加载，`partition_invoices` 改按 `ap_no` 判孤立。
  - `match_engine.py` 重写为 `build_item_matches`（AP 驱动料品汇总）+ `detect_misaligned_items`（料品级配对）+ `assign_category`（无发票支撑/明细错位/数量金额不符/金额微差/完全匹配）。
  - 新增 `price_check.py`（AP-PO 单价强制比对，R7 占位 ±3%）。
  - `result_classify.py`/`recon_report.py`/`run.py`/`confirm.py` 随口径同步调整；`recon_report` 新增价格超差强制 `needs_review` 的合并路由。
  - 重建 mock+golden 五表夹具（新增 `ap_lines.csv`），覆盖五类判定+明细错位正反例+价格超差/未超差+多对一/一对多/多对多聚合+孤立发票。
  - 全部单测重写，**43 tests 全绿**（含黄金基准零偏差回归、价格校验覆盖、`u9c` fail-loud 冒烟）；`python -m fi2.run`/`python -m fi2.confirm` 手工验证通过；`openspec validate fi2-recon-mvp --strict` 通过。
  - 落分支 `feat/fi2-v3-recon-engine`（未合 master，待 Paul 审）。
  - **下一步（2026-07-10 已由唐燕萍团队提前交付，见下条）**：① ~~唐燕萍 R1-R7 规则草案交付（约 2026-08 底）~~；② U9C 财务接口/OCR 就绪（7/15 双反馈门）后切 `csv`/`u9c` 真实源；③ 真实验证通过后 `/opsx:archive`。
  - **未做（组 7 待数据闸，组 8.2-8.4 待真实验证/黄金用例专家批改）**：真实数据验证、`/opsx:archive`、strawman 黄金用例专家批改。
- **2026-07-10/16（R1/R5/R7 定稿真值落地，队列 #14/#16，design D14，CC）**：唐燕萍团队 R1-R7 规则草案较原计划提前 7 周交付（《FI2-FI3-规则定稿-交CC-2026-07-10.md》），在同一分支 `feat/fi2-v3-recon-engine` 原地落地：
  - `config.py` 替换真值：数量 ±0（精确匹配）/未税金额新增比例备用 ≤0.5%/税额改按料品有效税率动态换算（不再是独立固定容差）/R7 人民币 ±2%；`RULE_VERSION` 升版 `fi2-v3-tangyanping-2026-07-10`。
  - **新增 R5 门禁**（`recon_report._l2_gated_ap_docs`）：整单（AP 关联 PO 行）未税金额差异总额 ≤¥1 或 ≤0.5% → "金额微差"降级 `l2_self_resolved`（AP 自行消化）；仅对"金额微差"生效——CC 从紧解读（"无发票支撑"/"明细错位"/"数量金额不符"三类不因总额小而降级），**Paul 2026-07-16 已拍板确认不扩大到"明细错位"，此范围为最终口径**（design D14-b）。价格超差优先级高于本门禁。报告状态由二态扩为三态，`summary` 新增 `l2_self_resolved`。
  - 新增 `item_normalize.py`（料品编码归一化预处理：去空格/全半角/括号/"-"与"/"等价类），接入 `match_engine.build_item_matches` 聚合 key；**不含**模糊匹配/置信度分档/自学习长线机制（留待真实数据接入）。
  - `models.ItemMatch` 新增 `ap_tax_rate` 字段（税额动态容差换算用）。
  - R7 外币供应商过渡规则（"容差内连续 2 次同向偏移推人工抽查"）与"方案一"原始外币单价+汇率升级位均**未实现**（缺供应商清单 + 跨运行历史状态两个前置），已登记 future-work（`tasks.md` 10.12），未来另行提交变更包。
  - 单测：`test_match_engine.py`/`test_recon_report.py` 各新增用例覆盖 R1/R5 新行为，新增 `test_item_normalize.py`（7 用例），`test_golden.py` 按真值更新（AP-1010 金额微差→L2 自行消化）；**全量 61 tests 全绿**，`python -m fi2.run` 手工验证通过。
  - openspec design.md 补 D14、tasks.md 补第 10 节、三份 spec delta（match-engine/recon-report/price-check）补 Requirement，均已同步。
  - **未做**：R5 门禁分母颗粒度（"整单"取 AP 引用的 PO 行集合 vs 整张 PO 单）仍待唐燕萍团队批改（design D14 Open Questions，门禁范围本身 Paul 已拍定不再是开放项）；R7 外币过渡规则/方案一升级位（Paul 07-16 已确认明确推迟，future-work，待外币供应商清单到位后再评估）；真实数据验证仍按 8 月底排期不变。
- **2026-07-16（Paul 两拍板，收口 D14 遗留开放点，CC）**：① **R5 门禁范围不扩大到"明细错位"**——D14-b 的 CC 收紧解读即为最终口径，不等唐燕萍团队批改这一项了（分母颗粒度仍待）。② **R7 外币过渡规则/方案一明确推迟**——Paul 认可"先上最小 MVP"，当前实现（外币供应商行按人民币同一 ±2% 处理、不触发增量抽查）维持不变，待 IT/唐燕萍团队提供外币供应商清单后再评估是否要做"连续 2 次同向偏移推人工抽查"的跨运行历史状态机制。两项均为**文档口径确认，代码无需改动**（此前实现已是这两条的目标状态）；design D14 Open Questions/tasks.md/proposal.md/spec delta 已同步落字。
- **2026-07-20（真实 U9C 财务接口接入 + R7 外币真值 + 三实测点，队列 #60，design D15，CC）**：唐燕萍团队 07-17 交付 API 接口文档（财务数据闸实质解除，队列 #6/#47），财务数据整备正式开工。
  - **三实测点真实只读探测**（服务器 `192.168.100.49:6666`）：①批量查询——`Purchase/Query`/`GR/Query` 不传 docNo 即返回全表+分页/`supplierCode` 过滤均有效；**`AP/Query` 服务器端有真实 SQL bug**（`supplierCode`/`itemCode`/`invoiceNo` 三个过滤参数均触发"列名无效"异常），只能 docNo 单查，已书面跟催 IT（陈承，`6-人才与组织/部门AI专员跟进/IT部-陈承-跟进-2026-07-20-*.md`，机器人已推送）；②`FinalPriceTC`(PO)与`TaxPrice`(AP)均为含税单价，同 `(po_no,line_no)` 实测精确一致，R7 比对基础成立，`price_check.py` 无需改动；③原币直比机制验证成立（`...TC` 字段本就是原币存储非折算字段），三家外币供应商专属数值样本受①限制未定向核实，留 8 月真实小样本阶段优先覆盖。
  - **真实连接器接入**（design D15-b，Paul 拍板：连接器落平台 `ZpConnector`、复用 `STOCK_API_BASE`/`STOCK_API_KEY`）：`ZpConnector` 新增 `get_purchase_lines`/`get_gr_lines`/`get_ap_lines(doc_no)`（GET+apiKey，信封同 `Stock/Query`）。`fi2/feed_source.py` 的 `FeedSource` 新增 `u9c_connector`/`ap_doc_nos` 可选构造参数，`u9c` 源下 `load_po_lines`/`load_grn`/`load_ap_lines` 按"AP 单号驱动→去重 `SrcPONo`/`SrcRcvNo`→分别拉取"三步实现（同实例内缓存 AP 行，避免重复网络调用）；未注入连接器时维持现状 fail-loud（`test_u9c_fail_loud_all_loaders` 零回归）。`load_invoice`/`load_payment` 对 `u9c` 源继续无条件 fail-loud（Attachment/OCR 未就绪，队列 #59）。
  - **R7 外币供应商真值落地**：`config.FOREIGN_CURRENCY_SUPPLIERS = ("ZA0066", "ZA.0368", "ZA0020")`（艾睿/安富利/上海英恒，唐燕萍团队 07-14 回件，已用 `Supplier/Query` 真实核实三家均为在库真实供应商）。
  - **新增测试**：`test_fi_connector.py`（连接器方法，7 用例，全 mock/monkeypatch 不触网）+ `test_feed_source.py` 新增 3 用例（假连接器覆盖三步拉取/字段映射/缓存复用、缺 `ap_doc_nos` 报错、Invoice/Payment 仍 fail-loud）+ `test_price_check.py` 新增 1 用例（R7 三家配置值守护）+ 新增 `tests/test_real_integration.py`（比照 SC8 范式，`FI2_RUN_REAL=1` 门禁，默认跳过不触网，含"IT bug 修复回归哨兵"用例）。平台 200 passed+1 skip（新增 7）、FI2 65 passed+4 skip（新增 4 mock 用例 + 4 gated 真实用例），零回归。
  - **⚠️ 发现一个影响面更广的问题（2026-07-20 当场发现，已知会 Paul）**：Paul 确认财务三单接口与既有库存/预测订单**同一 apiKey**后，用该 key 做真实活连通验证时发现**该 apiKey 当前对`Purchase/GR/AP/Stock`全部端点均返回 `401 Invalid api-key`**——而同一 key 数小时前（本 session 内）在这些端点上还能正常查询真实数据。因为 `Stock/Query` 正是 SC8 保供看板 `.51` 部署依赖的实时库存源，此 key 失效**可能正在影响 SC8 生产服务**，已作为独立风险单独上报（不在本次 #60 范围内处理，超出 FI2 场景）。
  - **未做**：真实小样本对账验证仍按 8 月底排期（本次只到"真实源代码可用"，未做批量真实跑批，因 AP 批量参数缺口 + apiKey 当前失效两个原因均未能跑通端到端真实小样本）；`test_real_integration.py` 待 apiKey 问题解决后首次真正执行验证（当前仅用有效历史 key 做过一次性 ad-hoc 手工验证，非 pytest 自动化跑通）。

## 关键依赖/前置（解锁条件）
- ~~🔴 唐燕萍（财务 AI 专员）R1-R7 规则草案~~ ✅ 已交付（2026-07-10，较原计划提前 7 周）——真值已落 `config.py`（见上）；黄金用例专家批改仍待唐燕萍团队（strawman 用例本身未经批改）。
- ~~🔴 U9C 财务接口（PO/GR/AP 配票）~~ ✅ 已接入（2026-07-20，design D15）——三端点真实连接器代码就绪；**新增阻塞**：apiKey 当前失效（`401 Invalid api-key`，见上，影响面超出 FI2），需 IT 排查恢复后才能真正跑通真实小样本。OCR 选型仍未就绪（队列 #59 跟催中）——发票源（Invoice）晋档 2 前置。
- 🟡 **AP 端批量查询 SQL bug**（`AP/Query` 的 `supplierCode`/`itemCode`/`invoiceNo` 过滤参数服务器端列名映射错误）——已书面跟催陈承（2026-07-20），修复前"按期批量取待对账 AP 单"只能靠财务专员手工给单号清单（`FeedSource.ap_doc_nos`），不阻断现有交付。
- 🟡 料品↔INV规格型号/项目名称映射表（v3 改名，原"物料编码映射表"）——真实场景前置，本次仅落地"归一化预处理"子项（`item_normalize.py`），模糊匹配/置信度分档/自学习长线机制仍待真实映射表来源确认。
- ~~🟡 R7 外币供应商清单~~ ✅ 已落真值（2026-07-20，见上）；跨运行历史状态机制（"连续 2 次同向偏移推人工抽查"过渡规则）**Paul 2026-07-16 已确认推迟**，未就绪前按人民币同一 ±2% 处理，不算阻塞项。
- 🟡 FI3（付款校验）依赖本场景结果——FI2 先行，FI3 另起场景。
