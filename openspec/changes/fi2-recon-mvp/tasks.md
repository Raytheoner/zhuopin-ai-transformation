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

- [ ] 7.1 唐燕萍 R1-R6 规则定稿后：替换 `config.py` + 规则注册表临时口径，回归零漂移确认引擎未变
- [ ] 7.2 U9C 财务接口/SRM 发票源就绪后：`feed_source` 切 `csv` 或 `u9c` 真实源，小样本真实数据试跑
- [ ] 7.3 物料编码映射表就绪后：接入映射逻辑（若 mock 阶段假设不成立需回头修 design）
- [ ] 7.4 真实小样本核对无静默丢单、无假阳性"明细错位"，产出真实 golden 替换合成 golden

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
