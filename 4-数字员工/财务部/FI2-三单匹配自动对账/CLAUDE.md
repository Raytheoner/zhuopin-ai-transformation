# CLAUDE.md — FI2 三单匹配自动对账（场景级进度笔记）

> 本文件是 FI2 场景的本地记忆/进度笔记，与 FI1/采购(SC*)/质量(QD*)场景分开。
> 项目级上下文见仓库根 `CLAUDE.md`；FI2 规划权威见全景规划 §2.1.4 FI2 块、实施计划 §一财务表、
> 跨场景前置数据总表 FI2 行、`1-转型规划/FI2-三单匹配口径-mock备料.md`、
> `1-转型规划/FI4-三单匹配-就绪清单与MVP细化.md`（编号 FI4 即 FI2 内容，同一份口径）。
> 本场景 = CC 建造车间产物；**不改规划文档**（那是 Cowork 的活）；排期若变只在此记并提示 Paul 通知 Cowork。

## 定位（Paul 2026-07-07 拍板）
- FI2 = 财务/采购交叉场景，**2026-09 启动**。财务域 2026 年唯一按期落地场景（FI1 因需求变更暂缓封存）。
- 自动化等级 **L3**（建议/预警，人工确认，不自动过账）；L4（自动过账/拦截）待查准/查全率达标后另行晋级。
- **MVP 范围**：FI2-1 三单数据准备与完整性校验 + FI2-2 PO+GR+INV 明细行级四维匹配（物料编码/数量/金额/税额），结果分五类（🟢完全匹配/🟡金额微差/🔴明细错位/🔴数量金额不符/🔴无GR支撑）。**"明细错位"检出是核心价值点**（总额对、明细行错位的成本失真场景）。
- **明确不做·二期**：FI2-3 税率专项 / FI2-4 查重 / FI2-5 容差专项收口 / FI2-6 退单 / FI2-7 考核 / FI2-8 学习。FI3（付款校验）为独立场景，不在本次范围。
- OEM 隔离【不适用】：FI2 读供应商/ERP 内部数据（PO/GRN/发票/付款凭证），按根 CLAUDE.md §4 不强加 OEM 路由。

## Design 决策（Paul 2026-07-07 拍板 D2-D5，详见 `openspec/changes/fi2-recon-mvp/design.md`）
1. **D2 临时容差口径**：采纳 mock 备料稿 strawman 默认——数量 ±2% 或 ±N 个（两者取宽松者）/ 金额尾差 ±0.5 元/行 / 税率必须一致。全部落 `config.py`，唐燕萍 R1-R6 规则草案（约 2026-08 底）定稿后只替换配置/规则版本号，不改引擎。
2. **D3 五类判定边界 + 判定优先级 + "明细错位"算法**：判定优先级（命中即停）＝ 无GR支撑 > 明细错位 > 数量金额不符 > 金额微差 > 完全匹配。"明细错位"＝同一 `po_no` 下 ≥2 行金额差异同时超尾差容差、方向相反（一多一少）、且该 PO 号总额差异在 PO 级容差内——单行超容差或同向超容差均不判错位（避免假阳性）。
3. **D4 L3 建议路由**：仅四类非完全匹配（金额微差/明细错位/数量金额不符/无GR支撑）强制标 `needs_review` 转人工；完全匹配类标 `l3_suggested_pass`（AI 建议通过，**未过账**），不强制逐笔人工，可批量抽查。
4. **D5 mock 四表结构**：照抄口径备稿 `po_lines`/`grn`/`invoice`/`payment` 四表字段，接口通后 loader 换真实源、字段映射在接入层做，不改 `match_engine.py`/`result_classify.py`。

## 复用底座资产（照搬 FI1 场景模式）
- **数据接入三源统一接口**：`fi2/feed_source.py`，`data_source="mock"|"csv"|"u9c"`，切源不改匹配引擎；`u9c` 未就绪时抛 `zhuopin_platform.shared_tools.connector_errors.RealEndpointNotReadyError`（fail-loud，不静默回退）。
- **审计**：`zhuopin_platform.audit.AuditLogger`（`scenario="FI2"`，append-only hash-chain，IATF 3 年）。每行匹配判定写 `action="line_match"`；L3 改判写 `action="l3_override"`。
- **L3 改判 CLI**：`fi2/confirm.py`（比照 FI1 `confirm.py`），`--reason` 必填、幂等、写审计。
- **金额脱敏纪律（design D7）**：审计/报告只记 `qty_diff_pct`/`amount_diff_pct`（差异比例）与分类结果，**不落原始发票单价/含税金额绝对值**；四维比对运算过程中金额参与内存计算，不持久化明细金额。

## 红线（建造时守住）
- 先 mock 跑通逻辑，再切真实库（`csv`/`u9c` 接口就绪后另行提交变更包晋档 2）。
- 每行匹配判定/分类写平台 `audit`（append-only，金额脱敏，见上）。
- L3 门禁：四类非完全匹配强制人工确认，不自动过账；MVP 无 L4 自动执行入口。
- AI 结论恒为"建议/预警"，结案在财务人员——报告 disclaimer 显式标注"未过账"。

## 状态
- 2026-07-07：场景工程 scaffold（`4-数字员工/财务部/FI2-三单匹配自动对账/`，包名 `fi2`）+ `pip install -e` 平台底座验证通过。
- 2026-07-07：OpenSpec propose 完成（proposal/design/4 个 spec delta/tasks），Paul 审 design D2-D5 通过。
- 2026-07-07：`/opsx:apply` 完成 **MVP 全部核心模块**（先写测试后实现）——`models`/`feed_source`/`match_engine`/`result_classify`/`recon_report`/`confirm`/`run` 七模块 + **32 tests 全绿**（含黄金基准零偏差回归、`u9c` fail-loud 冒烟、审计金额脱敏校验）；`python -m fi2.run`（mock）+ `python -m fi2.confirm`（L3 改判）均手工验证通过。任务组 2-6 全部完成；组 1（design 拍板）D2-D5 已获 Paul 认可，1.5/1.6（唐燕萍规则草案 + 数据闸）为外部前置，非本次阻断项。
  - **下一步**：① 唐燕萍 R1-R6 规则草案交付（约 2026-08 底）后替换 `config.py` 临时口径，回归零漂移验证引擎未变；② U9C 财务接口/SRM 发票源/OCR 就绪（7/15 双反馈门）后切 `csv`/`u9c` 真实源，小样本真实数据试跑；③ 真实验证通过 + 唐燕萍口径定稿后 `/opsx:archive` → git push。
  - **未做（组 7 待数据闸，组 8.2-8.4 待真实验证）**：真实数据验证、`/opsx:archive`。mock MVP 已可先 commit（未 archive）。

## 关键依赖/前置（解锁条件）
- 🔴 唐燕萍（财务 AI 专员）R1-R6 规则草案（约 2026-08 底）——晋档 2 前置，替换 `config.py` 临时口径，不改引擎。
- 🔴 U9C 财务接口（PO/GR）+ SRM 发票源（解 900401）+ OCR 选型（7/15 双反馈门）——晋档 2（真实数据跑通）前置，非 mock 开发阻断项。
- 🟡 物料编码映射表（供应商编码↔我方编码）——真实场景前置，mock 阶段假设编码已统一，来源待对接人+采购确认。
- 🟡 FI3（付款校验）依赖本场景结果——FI2 先行，FI3 另起场景。
