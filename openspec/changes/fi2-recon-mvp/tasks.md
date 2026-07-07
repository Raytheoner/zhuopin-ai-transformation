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
- [ ] 8.2 mock MVP 全绿后先 commit（不 archive，待真实验证/唐燕萍口径定稿后再 archive）
- [ ] 8.3 真实验证通过 + 唐燕萍口径定稿后 `/opsx:archive` → git push
- [ ] 8.4 若实现时间较规划有变，记入场景进度并提示 Paul 通知 Cowork 回填路线图（CC 不自行改规划）
