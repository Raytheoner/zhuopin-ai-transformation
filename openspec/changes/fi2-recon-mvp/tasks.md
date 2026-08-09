> **预期观察窗口：30 天**（队列 #314②，2026-08-09 声明，基准日 2026-08-09）——剩余未完成项的主体是等真实数据验证周期（10.13/11.12 明写"真实小样本验证仍按 8 月底排期"、1.5 唐燕萍 R1-R6 规则草案约 2026-08 底交付、7.3/8.3/8.4/10.11b 均为等该规则草案/映射表基建到位后才能推进的下游项），排期锚点为"8 月底"（2026-08-31）；从最近一次改动（2026-08-03）到该锚点约 28 天，取 30 天留 2 天缓冲。⚠️ **如实登记一处不完全吻合**：15.10（真实部署 `.51:8094` + 冒烟）当前仍未勾选 `[x]`，但 15.12 记录"发送前已核对…发送硬前置三条件（代码入master/部署冒烟/真实案例复现，均已满足）"，两者字面矛盾，疑似该项已实质完成但漏勾——本次声明窗口未擅自替其勾选或改判，如后续核实为真漏勾，窗口声明本身不受影响（不改变"仍在等 8 月底真实验证"这一主判断）。14.13（OCR round-2）为独立后续轮，"另行登记后续任务"、不计入本窗口判断范围。超窗未完成则回归"疑似遗忘归档"正常告警流程。

## 1. design 收口与前置（apply 前 Paul 确认 D2-D5；🔴 项阻断真实数据验证，不阻断 mock 开发）

- [x] 1.1 Paul 拍板 D2：临时容差口径采纳 mock 备料稿 strawman 默认（数量±2%或±N个/金额±0.5元行尾差/税率必须一致）—— Paul 认可
- [x] 1.2 Paul 拍板 D3：五类判定边界 + 判定优先级 + "明细错位"跨行配对算法定义 —— Paul 认可
- [x] 1.3 Paul 拍板 D4：L3 建议路由范围（仅四类非完全匹配强制转人工，完全匹配类标建议通过不强制逐笔人工）—— Paul 认可
- [x] 1.4 Paul 拍板 D5：mock 四表结构照抄口径备稿（po_lines/grn/invoice/payment 字段）—— Paul 认可
- [ ] 1.5 前置登记：唐燕萍 R1-R6 规则草案（约 2026-08 底）——交付后仅替换 config.py + 规则注册表，不改引擎
- [ ] 1.6 前置登记：U9C 财务接口 / SRM 发票源 / OCR 选型（7/15 双反馈门）——真实数据验证前置，非 mock 开发阻断项

## 2. fi2-feed-source 数据接入层（mock 先行，先测后实现）

- [x] 2.1 定义 `models.py`：POLine / GRNLine / InvoiceLine / PaymentRecord 数据类（比照 FI1 `models.py` 范式）
- [x] 2.2 定义四表统一加载接口与 `data_source` 三源开关（mock/csv/u9c，依赖注入，仿 FI1 `feed_source.py`）
- [x] 2.3 写测试：mock 加载四表 + Pydantic 边界校验（缺物料编码/数量非法/金额非法显式报错）
- [x] 2.4 写测试：`(po_no, line_no)` 关联 PO↔GRN↔Invoice、`inv_no` 关联 Invoice↔Payment 的正确性
- [x] 2.5 写测试：孤立单据识别（Invoice 找不到对应 PO 行 → 标待处理，不进入四维比对当正常件）
- [x] 2.6 写测试：`u9c` 端点不可达 fail-loud 抛 `RealEndpointNotReadyError`，不回退 mock/csv
- [x] 2.7 实现 mock 加载器 + 四表 mock 夹具（贴口径备稿字段，D5 依赖）
- [x] 2.8 mock 夹具埋根因样本子集（F1有货无票/F2有票无货/F4价格差异/F5数量差异含明细错位配对，覆盖 10 个 PO 行 + 1 张孤立发票；F3/F6/F7/F8/F9 本 MVP 记录但不作专项判定分支，见 design Non-Goals）
- [x] 2.9 实现 `csv` loader（应急桥接，与 mock 同字段/同解析路径）+ `u9c` fail-loud 占位
- [x] 2.10 全部接入层单测绿（test_feed_source.py 13 tests）

## 3. fi2-match-engine 四维匹配纯算法引擎（先测后实现，D2/D3 依赖）

- [x] 3.1 写测试：四维比对（物料编码/数量/金额/税额）全在容差内 / 单维度超容差场景
- [x] 3.2 写测试：判定优先级（无GR支撑 > 明细错位 > 数量金额不符 > 金额微差 > 完全匹配），命中即停不重复归类
- [x] 3.3 写测试："明细错位"正例——同 PO 下两行方向相反超容差 + PO 级总额一致 → 判错位
- [x] 3.4 写测试："明细错位"反例①——单行超容差、无配对行 → 判"数量金额不符"，不得误判错位
- [x] 3.5 写测试："明细错位"反例②——两行同向超容差（非相反）→ 各自判"数量金额不符"，不得误判错位
- [x] 3.6 实现四维比对纯函数（无副作用，config 读容差）
- [x] 3.7 实现判定优先级 + 明细错位跨行配对检测算法
- [x] 3.8 全部匹配引擎单测绿（test_match_engine.py 10 tests）

## 4. fi2-result-classify 五类判定规则注册表（先测后实现，D2 依赖）

- [x] 4.1 设计规则注册表结构（容差条件从 config 注入，分类版本 `RULE_VERSION` 登记）
- [x] 4.2 写测试：五类分类结果（完全匹配/金额微差/明细错位/数量金额不符/无GR支撑）与 D3 判定优先级一致
- [x] 4.3 写测试：仅改 `config.py` 容差常量，分类结果按新配置重算，不改分类函数代码
- [x] 4.4 写测试：差异比例计算（数量差异比例/金额差异比例），不直接输出原始金额绝对值
- [x] 4.5 用临时口径（1.1 拍板结果）填注册表基线
- [x] 4.6 实现分类引擎（按 match_engine 判定结果 + config 容差编排，分类标准不写死代码）+ 规则版本登记
- [x] 4.7 分类单测绿（test_result_classify.py 4 tests）

## 5. fi2-recon-report 聚合 + L3 门禁 + audit + 改判 CLI（先测后实现，D4/D7 依赖）

- [x] 5.1 写测试：报告聚合契约（含 po_no/line_no/物料编码/分类结果/差异比例/报告状态/数据源）
- [x] 5.2 写测试：非完全匹配四类 → `needs_review`；完全匹配 → `l3_suggested_pass`（不自动过账，文案含"未过账"标注）
- [x] 5.3 写测试：审计事件金额脱敏——记差异比例/分类结果，不落原始发票单价/含税金额绝对值
- [x] 5.4 写测试：L3 改判 CLI（`--reason` 必填拒绝空值、同行重复提交幂等）
- [x] 5.5 实现报告聚合 + "AI 建议非终局"标注
- [x] 5.6 实现审计接线：写 `zhuopin_platform.audit.AuditLogger`（`scenario="FI2"`）
- [x] 5.7 实现 `confirm.py` L3 改判 CLI（比照 FI1 `confirm.py`）
- [x] 5.8 聚合/门禁/审计/CLI 单测绿（test_recon_report.py 3 tests + test_confirm.py 3 tests）

## 6. 黄金基准回归（合成）

- [x] 6.1 构造合成四表 golden 样本（覆盖 5 类判定 + 明细错位正例与两个反例 + 孤立发票）存 `data/golden/`（合成可入库）
- [x] 6.2 写黄金回归测试：匹配引擎 + 分类结果对预期零偏差（test_golden.py）
- [x] 6.3 全场景回归绿（32 tests passed，含 `u9c` fail-loud 冒烟）+ 一键运行入口跑通（`python -m fi2.run`，`python -m fi2.confirm` 均已手工验证）

## 7. 真实数据验证（待数据闸：U9C 财务接口 + SRM 发票 + OCR + 唐燕萍 R1-R6；前置 1.5/1.6）

- [x] 7.1 唐燕萍 R1-R6 规则定稿后：替换 `config.py` + 规则注册表临时口径，回归零漂移确认引擎未变——**完成于 2026-07-10/16（design D14），详见第 10 节**
- [x] 7.2 U9C 财务接口/SRM 发票源就绪后：`feed_source` 切 `csv` 或 `u9c` 真实源，小样本真实数据试跑——**完成于 round-1（2026-07-23，design D18/第 14 节）**：PO/GR/AP 走真实 `u9c` 源，Invoice 因 OCR 未就绪改人工誊录 + `csv` 源合并跑，6 组样本 10 料品验证通过
- [ ] 7.3 物料编码映射表就绪后：接入映射逻辑（若 mock 阶段假设不成立需回头修 design）——round-1 用人工对照 AP 配票记录反推映射（非规模化方案），真实映射表基础设施仍未建，见验证报告 §五
- [ ] 7.4 真实小样本核对无静默丢单、无假阳性"明细错位"，产出真实 golden 替换合成 golden——**round-1 已核对**（零假阳性，见验证报告 §一），但**design D18-e 已定"暂不替换/扩充合成 golden"**（8 样本量偏小、会降低回归覆盖面），留待后续批次样本量扩大后再评估

## 8. 收口归档

- [x] 8.1 编写场景 `CLAUDE.md`（六段式：定位/决策/底座/红线/时间线/依赖）
- [x] 8.2 mock MVP 全绿后先 commit（不 archive，待真实验证/唐燕萍口径定稿后再 archive）—— commit `0d19918`（master）
- [ ] 8.3 真实验证通过 + 唐燕萍口径定稿后 `/opsx:archive` → git push
- [ ] 8.4 若实现时间较规划有变，记入场景进度并提示 Paul 通知 Cowork 回填路线图（CC 不自行改规划）

## 9. v3 口径修正（2026-07-09，唐燕萍团队应付会计实操细化 + Paul 三裁决，design D10-D13）

> 唐燕萍团队回传《核实对照表》——应付会计实操细化揭示核对对象是 AP 单 vs INV（非逐 PO 行），Paul 全盘采纳。在本变更包（未归档）内原地调整引擎，不新开变更包（Paul 澄清①）。黄金用例由 CC 按 v3 定稿文档自拟 strawman，唐燕萍后续批改（Paul 澄清②）。R7（AP-PO 单价容差）CC 占位 ±3%（Paul 澄清③）。

- [x] 9.1 design.md 补充 D10-D13（匹配对象/粒度调整、AP-PO 单价校验+R7 占位、命名迁移、黄金用例来源）
- [x] 9.2 `models.py`：新增 `APLine`/`PriceCheckResult`，`InvoiceLine` 改挂 `ap_no`+v3 字段，`LineMatch`→`ItemMatch`（ap_no+item_code 键）
- [x] 9.3 `feed_source.py`：新增 `ap_lines` 加载/解析，`InvoiceLine` 边界校验改 v3 字段，`partition_invoices` 改按 `ap_no` 判孤立
- [x] 9.4 `match_engine.py`：`build_item_matches`（AP 驱动、按 `(ap_no,item_code)` 双向聚合）替代 `build_line_matches`；`detect_misaligned_items`/`assign_category` 随口径调整（无GR支撑→无发票支撑，税率布尔→税额容差，含税金额→未税金额）
- [x] 9.5 新增 `price_check.py`（`check_ap_po_price`/`failed_item_keys`），R7 占位 `config.AP_PO_PRICE_TOLERANCE_PCT=0.03`
- [x] 9.6 `result_classify.py`：`classify_all` 签名改 `(ap_lines, invoice_rows)`，`_NEEDS_REVIEW_CLASSES` 随分类改名更新
- [x] 9.7 `recon_report.py`：聚合单元改料品，合并价格校验结果并强制改写 `needs_review`（分类字段不变），新增 `price_check_alerts`
- [x] 9.8 `run.py`/`confirm.py`：run.py 接入 `ap_lines`+`price_check`；confirm.py 改判键改 `--ap-no`/`--item-code`
- [x] 9.9 `config.py`：新增/改名容差常量（`TAX_AMOUNT_TOLERANCE`/`AP_LEVEL_AMOUNT_TOLERANCE`/`AP_PO_PRICE_TOLERANCE_PCT`），`RULE_VERSION` 升版
- [x] 9.10 重建 mock+golden 四表夹具（新增 `ap_lines.csv`，`invoice.csv` 改 v3 字段），覆盖五类判定+明细错位正反例+价格超差/未超差+多对一/一对多/多对多聚合+孤立发票
- [x] 9.11 重写全部单测（`test_feed_source`/`test_match_engine`/`test_result_classify`/`test_recon_report`/`test_golden`/`test_confirm` + 新增 `test_price_check`），全绿（43 tests）
- [x] 9.12 openspec spec delta 随 v3 改写（`fi2-feed-source`/`fi2-match-engine`/`fi2-result-classify`/`fi2-recon-report` 就地改 ADDED Requirements + 新增 `fi2-price-check`），`proposal.md` 追加 v3 说明
- [x] 9.13 场景 `CLAUDE.md` 更新六段式反映 v3
- [x] 9.14 唐燕萍 R1-R7 规则草案（较原计划提前 7 周，2026-07-10 交付，队列 #14）：`config.py` 临时口径已按真值替换，见第 10 节；黄金用例回归已按真值更新（AP-1010 因 R5 门禁降级 L2），strawman 用例本身待唐燕萍团队批改（见 design D14 Open Questions）

## 10. R1/R5/R7 定稿真值落地 + 料品编码归一化（2026-07-10/16，队列 #14/#16，design D14）

> 唐燕萍团队两份圈改回件 + Paul 三拍板产出《FI2-FI3-规则定稿-交CC-2026-07-10.md》（队列 #14），CC 分支 `feat/fi2-v3-recon-engine` 承接落地（队列 #16）。判定不触发重组循环。

- [x] 10.1 `config.py`：R1 真值（数量 ±0/未税金额比例备用 0.5%/税额随税率）+ R5 门禁阈值（¥1）+ R7 真值（±2%）+ 外币供应商清单占位 + `RULE_VERSION` 升版
- [x] 10.2 新增 `item_normalize.py`（`normalize_item_code`：NFKC 全半角 + 分隔符等价类 + 去空格括号 + 大写化），`match_engine.build_item_matches` 聚合 key 改用归一化结果，展示仍用原始 item_code
- [x] 10.3 `models.py`：`ItemMatch` 新增 `ap_tax_rate` 字段（`build_item_matches` 填，AP 侧有效税率）
- [x] 10.4 `match_engine.py`：`assign_category` 税额判定改按 `AMOUNT_TAIL_TOLERANCE × ap_tax_rate` 动态换算；新增 `_amount_in_tolerance`（未税金额绝对值/比例两者取宽松者）
- [x] 10.5 新增 R5 门禁（`recon_report._l2_gated_ap_docs` + `_po_untaxed_by_ap`）：仅"金额微差"生效，整单（AP 关联 PO 行）未税金额差异总额 ≤¥1 或 ≤0.5% → 降级 `l2_self_resolved`；价格超差优先级高于本门禁
- [x] 10.6 `recon_report.build_report`：新增 `ap_lines`/`po_lines` 可选参数（缺省不计算门禁，向后兼容）；报告新增 `l2_self_resolved` 列表 + `summary.l2_self_resolved` 计数
- [x] 10.7 `run.py` 接入 `ap_lines`/`po_lines` 传参 + 打印摘要新增 L2 计数
- [x] 10.8 单测更新：`conftest.py`/`test_result_classify.py` cfg 夹具更新；`test_match_engine.py` 新增 8 个用例（R1 数量精确匹配/税额随税率×2/未税比例备用×2/料品编码归一化×2）；新增 `test_item_normalize.py`（7 个纯函数用例）；`test_recon_report.py` 新增 4 个 R5 门禁用例；`test_golden.py` 按真值更新 AP-1010 预期（金额微差→L2 自行消化）；`test_price_check.py` 注释更新为真值 ±2%；全量 61 tests 绿，`python -m fi2.run` 手工验证通过
- [x] 10.9 openspec design.md 补充 D14（R1/R5/R7 真值 + R5 门禁范围收紧解读 + 料品归一化 + R7 外币过渡规则/方案一未实现说明 + Open Questions）；本 tasks.md 补第 10 节；specs delta 补 R5 门禁/税额动态容差/归一化 Requirement（见 `specs/fi2-recon-report`、`specs/fi2-match-engine`、`specs/fi2-price-check`）
- [x] 10.10 场景 `CLAUDE.md` 更新状态段
- [x] 10.11a R5 门禁范围是否扩大到"明细错位"——**Paul 2026-07-16 已拍板：不扩大**，D14-b 收紧解读为最终口径，代码无需改动
- [ ] 10.11b 唐燕萍团队批改：R5 分母颗粒度（AP 引用的 PO 行集合 vs 整张 PO 单）——见 design D14 Open Questions，仍待确认
- [x] 10.12 future-work（前置数据未就绪，暂不实现）：R7 外币供应商清单 + "容差内连续 2 次同向偏移推人工抽查"跨运行历史状态机制；R7 方案一（原始外币单价 + 下单日汇率字段）——**Paul 2026-07-16 已确认明确推迟，先上最小 MVP**（当前实现：外币供应商行按人民币同一 ±2% 处理，不触发增量抽查），IT 评估完成 + 唐燕萍团队提供外币供应商清单后另行提交变更包
- [ ] 10.13 真实数据验证仍按 8 月底排期不变（规则提前定稿不等于提前上线，见规则定稿交接文件 §三纪律）

## 11. 真实 U9C 财务接口接入 + R7 外币真值 + 三实测点（2026-07-19/20，队列 #60，design D15，Paul 已拍板）

> 唐燕萍团队 07-17 交付 API 接口文档（财务数据闸实质解除，队列 #6/#47），CC 完成三实测点真实只读探测（结果见 design D15-a），Paul 2026-07-20 三项拍板全部通过（批准方案/立即催 IT/复用 STOCK_API_* 凭据），本节转入 apply。

- [x] 11.1 Paul 审 D15 —— **✅ 全部批准**（2026-07-20）：连接器落点/MVP 调用形态按方案 apply；IT bug 立即出报告跟催；凭据复用 `STOCK_API_BASE`/`STOCK_API_KEY`（不新开 `FI_API_*`）
- [x] 11.2 `ZpConnector` 新增 `get_purchase_lines(doc_no)`/`get_gr_lines(doc_no)`/`get_ap_lines(doc_no)`（GET+`apiKey`，信封同 `Stock/Query`）；凭据复用既有 `STOCK_API_BASE`/`STOCK_API_KEY`，脱敏不入审计/日志——**✅ 完成**，`_fi_query`/`_fi_credentials` 公共实现 + 三方法，7 个单测全绿
- [x] 11.3 `feed_source.py`：`FeedSource` 新增 `u9c_connector`/`ap_doc_nos` 可选构造参数；`u9c` 源下 `load_po_lines`/`load_grn`/`load_ap_lines` 按 D15-b 三步（AP 单号驱动→去重 `SrcPONo`/`SrcRcvNo`→分别拉取）实现；未注入连接器时保持现状 fail-loud（`test_u9c_fail_loud_all_loaders` 零回归）——**✅ 完成**
- [x] 11.4 `load_invoice`/`load_payment` 对 `u9c` 源维持无条件 fail-loud（Attachment/OCR 未就绪，队列 #59 未解锁前不实现）——**✅ 完成**，专门测试覆盖
- [x] 11.5 `config.py`：`FOREIGN_CURRENCY_SUPPLIERS = ("ZA0066", "ZA.0368", "ZA0020")` 落真值——**✅ 完成**
- [x] 11.6 单测：连接器方法用假 HTTP/注入假响应覆盖（不触网）；`FeedSource` 新增用例覆盖"注入假连接器 + `ap_doc_nos`"路径的三步拉取与字段映射；R7 三家供应商配置值守护测试——**✅ 完成**（`test_fi_connector.py` 7 例 + `test_feed_source.py` +3 例 + `test_price_check.py` +1 例）
- [x] 11.7（比照 SC8 `test_real_integration.py` 范式）新增 `tests/test_real_integration.py`，`FI2_RUN_REAL=1` 门禁，CI/默认 pytest 不触网——**✅ 完成且已真正跑通**（2026-07-21，队列 #61 复验）：apiKey 恢复后 4 个真实用例全绿（PO/AP/GR schema + AP 批量过滤已修复复验），`test_real_ap_query_batch_filter_now_fixed` 意外确认 IT 同批修复了批量过滤 bug（见 design D15-a① 更新）
- [x] 11.8 回写跨桌任务队列 #60：三实测点结论 + IT 缺口（AP 端批量查询 SQL bug）+ apply 完成状态 + apiKey 失效风险——**✅ 完成**
- [x] 11.9 IT 缺口书面留痕 + 立即跟催陈承 —— **✅ 完成并已由 IT 修复**（2026-07-20 发出，2026-07-21 陈承回复根因+修复，队列 #61 已复验销行）：`AP/Query` 的 `supplierCode`/`itemCode`/`invoiceNo` 过滤参数均触发 SQL 列名错误，报告 `6-人才与组织/部门AI专员跟进/IT部-陈承-跟进-2026-07-20-AP查询接口批量参数SQL报错.md`（+docx）已机器人直推陈承；陈承定位根因是另一件事（新版本 DLL 改读 `Web.config` 的 `ZP_API_KEY`，部署遗漏配置项导致全端点 401），修复+`iisreset` 后批量过滤 bug 也一并消失
- [x] 11.10 场景 `CLAUDE.md` 更新（状态时间线 + 关键依赖解锁进度）——**✅ 完成**
- [x] 11.11 全量回归零漂移——**✅ 完成**：FI2 65 passed+4 skip（原 61，+4 mock 用例）、平台 200 passed+1 skip（原 193，+7），零回归；2026-07-21 复验后再跑一遍仍 65+4/200+1，零回归
- [ ] 11.12 真实小样本验证仍按 8 月底排期（本次只到"真实源代码可用"，不做批量真实对账跑批）；建议第一批次优先覆盖三家外币供应商 AP 单，补齐 D15-a③ 未定向核实的缺口——~~新增前置：需 apiKey 恢复~~ **✅ apiKey 已恢复**（2026-07-21），此前置已解除
- [x] 11.13 🔴 **apiKey 失效问题（2026-07-20 发现，2026-07-21 已解决，队列 #61 销行）**：共享 `STOCK_API_BASE`/`STOCK_API_KEY` 一度对 `Purchase/GR/AP/Stock` 全部端点返回 `401`——陈承定位根因为新版本 DLL 改读 `Web.config` `ZP_API_KEY`、部署遗漏配置项，已补配置+`iisreset`；陈承确认 SC8 `.51` 保供看板不受影响，CC 复验 `Stock/Query` 真实数据一致确认无误
- [x] 11.14 **✅ 完成（2026-07-21，Paul 当场拍板改造，design D16）**：`AP/Query` 批量过滤 bug 意外一并修复后，Paul 直接拍板"改造成批量自动取数"——`ZpConnector` 新增 `get_ap_lines_by_supplier`（分页聚合，10 单测覆盖）；`FeedSource` 新增 `ap_supplier_codes`，与 `ap_doc_nos` 并存二选一（批量优先），下游 PO/GR 派生管线复用不变；真实端到端验证（`test_real_get_ap_lines_by_supplier`）分页条数与服务器 `Total` 精确一致。手工单号模式（`ap_doc_nos`）未删除，继续可用。全量回归零漂移：平台 203+1skip（+3）、FI2 67+5skip（+2net）

## 12. 批量取数验收补记（design D16，2026-07-21）

- [x] 12.1 `ZpConnector._fi_request`/`_fi_query_paginated`/`get_ap_lines_by_supplier` 实现 + `test_fi_connector.py` 新增 3 例（分页停止条件/空结果/URL 不含 docNo）
- [x] 12.2 `FeedSource.ap_supplier_codes` + `_fetch_u9c_ap_rows` 双模式（批量优先）+ `test_feed_source.py` 新增 3 例（批量驱动同管线/优先级/二者皆缺报错）
- [x] 12.3 `test_real_integration.py` 新增 `test_real_get_ap_lines_by_supplier`，真实验证分页条数与 `Total` 一致 + 供应商字段校验，已真实跑通
- [x] 12.4 design.md 补 D16（批量维度选型理由——为何选 supplierCode 不选按期间/按料品/全表）；本节任务补记
- [x] 12.5 场景 CLAUDE.md 更新；跨桌任务队列 #61 追加批量改造完成状态；全量回归零漂移；commit+push+收工重跑台账

## 13. AP/Query 期间/余额过滤参数解锁验证（design D17，2026-07-22，队列 #70）

- [x] 13.1 三过滤参数列名修复（07-20 报给 IT 的 SQL bug）真实回归复验——`test_real_integration.py` 全量重跑绿，属既有修复再确认
- [x] 13.2 `dateFrom`/`dateTo`/`minBalance` 三个新参数真实探测：单独可用 + 与 `supplierCode` 组合可用 + `minBalance` 下限语义（非精确匹配/上限）已用真实数据验证
- [x] 13.3 `ZpConnector.get_ap_lines_by_supplier` 增补可选 `date_from`/`date_to`/`min_balance` 关键字参数，缺省行为与 D16 完全一致；`test_fi_connector.py` +3 单测
- [x] 13.4 `test_real_integration.py` +2 真实集成用例（裸探测三点结论 + 连接器封装层端到端）
- [x] 13.5 design.md 补 D17；本节任务补记；全量回归零漂移（平台 211+1skip、FI2 67+7skip）
- [ ] 13.6 future-work（本次未做，已在 D17-b 登记原因）：`FeedSource`/`fi2/run.py` 接线新参数（期间/余额窄化批量对账入口）——待真实小样本对账阶段财务专员提出具体需求再评估，避免预先建无调用方的抽象

## 14. Round-1 真实数据验证（design D18，2026-07-23，队列 #78，🔴 apply 前待 Paul 审 D18 Open Questions）

> Paul 07-22 拍板"全力抢 8 月上旬"；CC 07-23 领活+工期评估回填（约 3.5-5 工作日，把握中等偏高）后开工。本节 14.1-14.3 为 propose→design 阶段已完成的只读真实探测（无代码改动），14.4 起为 apply 待办。

- [x] 14.1 真实探测 `Attachment/List`：8 个真实 AP 单逐一探测，确认响应信封（`Data` 为数组，无 `Rows` 包裹）+ 字段（`ID`/`Title`/`Size`）+ 附件数量（均恰好 1 个，无消歧义需求）
- [x] 14.2 真实探测 `Attachment/Download`：确认返回原始二进制（非 JSON 信封）、`Content-Type: application/pdf`、`Content-Disposition` 带文件名；抽验 1 单（AP-2026070036）完整下载成功
- [x] 14.3 design.md 补 D18（a-e 五个子决策 + Risks + Non-Goals + Open Questions）；本节任务补记
- [x] 14.4 Paul 审 D18 Open Questions——**✅ 批准（2026-07-23）**：D18-b/D18-d/D18-e 均按建议方案执行
- [x] 14.5 `ZpConnector` 新增 `list_attachments(doc_no, doc_type)`/`download_attachment(doc_no, doc_type)`（先测后实现，`test_fi_connector.py` +7 单测，mock HTTP 响应覆盖，不触网）
- [x] 14.6 `fi2/run.py::run()` 新增 `u9c_connector`/`ap_doc_nos`/`ap_supplier_codes` 透传参数；`main()`/CLI 新增 `--ap-doc-nos`/`--ap-supplier-codes`（`ZpConnector.from_env()` 走真实 U9C_* 凭据，连接器审计用 `ConnectorAudit`——过程中发现并修正一处真实 bug：`ZpConnector.audit=` 参数期望 `ConnectorAudit` 而非业务 `AuditLogger`，两者物理分离同 SC8 范式，误传会在真实调用时 `AttributeError`，已在 `run.py`/新增 `fi2/dump_u9c_snapshot.py` 中改正）；新增 `test_run_u9c_wiring.py`（6 用例）
- [x] 14.7 真实拉取 6 组样本（8 组中 2 组不适用本轮，见 14.9 备注）PO/GR/AP，落 `data/real_round1/{po_lines,ap_lines,grn}.csv`（新增可复用工具 `fi2/dump_u9c_snapshot.py` + `test_dump_u9c_snapshot.py`，`.gitignore` 已覆盖不入库）——**期间顺带发现并修复本机 worktree 的全局可编辑安装被另一 worktree 静默劫持问题**（`pip install --force-reinstall --no-deps -e` 重新指向本 worktree，[[project-shared-python-editable-install-collision]] 已知隐患）
- [x] 14.8 真实下载发票 PDF 落 `data/real_round1/attachments/`，逐张读取手工誊录 `data/real_round1/invoice.csv`（标注"人工誊录·非OCR"）——**实际 6/8 完成**：AP-2025120181 因 `Attachment/Download` 真实服务端 302 重定向到 `localhost:5555`（不可达）未能下载；AP-2026050057 探测为跨多 AP 单合并结算大票（100行/8页，发票金额大于单张 AP 金额），超出本轮人工誊录合理范围，两者均已登记跟进项，见验证报告 §三
- [x] 14.9 `FI2_DATA_SOURCE=csv python -m fi2.run --csv-dir data/real_round1` 跑通，产出 `reports/fi2_reconcile_report.json`——**6 AP/10 料品，全部"完全匹配"（零假阳性明细错位/数量金额不符），3 项 AP-PO 价格超差**（design D12/R7，-6.1%~-44.7%，真实数据非误判，已溯源，其中 1 例牵出"`price_check` 未消费 `POChange/Query` 变更后价格"的方法论发现，见验证报告 §四）
- [x] 14.10 产出真实验证小结 `1-转型规划/FI2-round1真实验证报告-2026-07-23.md`（供财务专线/Paul/唐燕萍/姚祖怡复核，含数据来源人工誊录声明 + 两组未验证样本原因 + 价格超差溯源 + 下一步分工）
- [x] 14.11 单测：`test_fi_connector.py`（+7）/`test_run_u9c_wiring.py`（新增 8）/`test_dump_u9c_snapshot.py`（新增 2）；全量回归零漂移——见 14.12 数字
- [x] 14.12 场景 `CLAUDE.md` 更新状态段 + 队列 #78 回填结果——见场景 CLAUDE.md 2026-07-23 段；全量回归：平台 218 passed+1 skip（原 211，+7）、FI2 77 passed+7 skip（原 67+7，+10 net）
- [ ] 14.13 OCR（腾讯云）自动直读集成——独立第二轮，不在本节范围，另行登记后续任务；同时登记一项后续：AP-2025120181 的 `Attachment/Download` 302 bug 需 IT（陈承）跟进
- [x] 14.14 `POChange/Query` 纳入 R7 价格比对基准评估（14.9 方法论发现，队列 #80）——**✅ 已评估完成，结论=不采纳**（2026-07-28，CC，独立 worktree 只读真实探测，未改代码）：真实探测证实该端点①过滤参数名是 `PODocNo` 非 `docNo`，传错参数名不报错、静默返回全表（Total=2412），比此前 `AP/Query` 的报错型 bug 更危险；②是 PO 单据级而非行项级，无 `ItemCode`/单价字段，结构上给不出"某料品最新单价"；③决定性交叉验证——`ZPCG20220815002` 全部 25 行 `Purchase/Query.TotalMnyTC` 求和精确等于 `POChange/Query` 最后一条变更记录的"变更后"`TotalAmt`，证明 `Purchase/Query.FinalPriceTC`（`price_check.py` 现用基准）本就是当前生效价、并非"原始下单价"——**不存在需要修的基准过时 bug**，不实现方向 B 的接入方案。详见 design D18-f 补充段、`1-转型规划/session接力-财务域场景落地.md`【第十九轮】、队列 #80。

## 15. 面板真实数据接入·轮1（design D19，2026-08-03，队列 #214/§四#43，🔴 apply 前待 Shao Peishen 审 D19）

- [x] 15.1 Shao Peishen 审 D19（范围 D19-a / 誊录处置 D19-b / 实现范围 D19-c / 验证方式 D19-d / 如实边界 D19-e）——**✅ 已批准（2026-08-03，会话内 AskUserQuestion 明确选择"批准，按D19执行apply"）**
- [x] 15.2 核查 round-1（D18）誊录成果是否可复用——遍历全部现存 worktree + 主工作区，确认 `data/real_round1/` 均不存在（产出 worktree `fi2-web-service-16da2a` 已被此后台面清理删除），结论：不可复用，需重新取数+誊录（如实记录，见 D19-b）
- [x] 15.3 用真实 `STOCK_API_BASE`/`STOCK_API_KEY`（只读 GET，未落代码改动）重新拉取 8 组 AP 单的 `AP/Query`/`Purchase/Query`/`Attachment/List`/`Attachment/Download`——结果与 D18-f 逐字复现：6/8 可用、AP-2025120181 仍 302 到 localhost、AP-2026050057 仍为合并结算大票超出范围
- [x] 15.4 逐张阅读 6 张发票 PDF，人工誊录 `data/real_round1/invoice.csv`（`.gitignore` 已覆盖不入库）；AP-2026060004 一票未按内部料号拆分的处置方式已写入 design D19-b（对半拆分+±0.01 分摊误差如实保留）
- [x] 15.5 `FeedSource` 新增 `invoice_sample_dir` 可选参数（`fi2/feed_source.py`）；`load_invoice()` 分支：u9c 源 + 已提供该参数 → 读取该目录 CSV；未提供 → 维持 fail-loud；`test_feed_source.py` 新增 2 例（正常路径 + 脏数据仍被拒收）
- [x] 15.6 `webapp.py` u9c 模式接线固定指向 `data/real_round1/`（只读展示型开关，非用户自由填路径）+ 面板新增"⚠️ 发票为人工誊录小样，OCR 未接入"标注（`.disclaimer-d19` 样式）+ 数据源行发票列标注 `u9c+人工誊录小样`；`test_webapp.py` 新增 3 例（无小样仍报错/有小样端到端跑通并标注/目录存在但缺CSV仍报错）
- [x] 15.7 全量测试绿 + 零回归：FI2 104 passed+7 skip（原99+5，净+5）；mock 模式路径本轮零改动（`load_invoice` 的新分支仅在 `data_source=="u9c"` 内，webapp 展示层新增分支仅在 `ds["invoice"]==_INVOICE_SAMPLE_LABEL` 时触发，均不可能影响 mock/csv 路径）——既有 `TestRunMockModeV8Panel` 全套结构断言（KPI/免责声明/R7提示/展开收起等）原样通过，构成判据零漂移的显式证明
- [x] 15.8 面板 `u9c` 模式 + 6 组真实 AP 号 + 誊录发票小样端到端跑通（直接调用面板同一入口函数 `webapp._run_with_detail`，真实 `ZpConnector`）：10 料品（8完全匹配+2金额微差已自动L2消化）、3 例 AP-PO 单价超差，**价格超差 3 例与 D18-f 逐位精确一致**（-44.72%/-6.11%/-8.22% vs round-1 记录 -44.7%/-6.1%/-8.2%）；AP-2026060004 两料品判"金额微差"而非 round-1 的"完全匹配"，已查明系本轮誊录 50/50 拆分产生 ±0.01 分摊误差所致（非业务变化/非代码缺陷），详见验证报告 §五
- [x] 15.9 产出 `1-转型规划/FI2-round1真实验证报告-2026-08-03-面板轮1.md`（含 D19-b 誊录方法论摘要 + §五差异说明，供财务专线/Shao Peishen/唐燕萍复核，且不依赖 gitignored 文件留存）
- [ ] 15.10 真实部署 `.51:8094` + 冒烟（`/api/ping`/首页/真实 POST `/run` u9c 模式端到端）
- [ ] 15.11 场景 `CLAUDE.md` 更新状态段；跨桌任务队列 #214 回填结果（本节完工不代表整个变更包 `fi2-recon-mvp` 可归档——14.13 OCR round-2 等既有开放项仍在，归档判断以变更包全部任务而非单节为准，本次不执行 `/opsx:archive`）
- [x] 15.12 交付后回请唐燕萍复核，信中明确告知"这是第一轮，发票侧待 OCR（#82 round-2）到位后还有第二轮"——**✅ 财务部#10 已发送（2026-08-04 00:10 UTC）**，机器人私信+docx附件+财务部群webhook精简通报；发送前已核对串行原则（#9 已回件已回灌）与发送硬前置三条件（代码入master/部署冒烟/真实案例复现，均已满足）
