# fi1-recon-report Specification

## Purpose
TBD - synced from change fi1-warehouse-reconcile (change remains active, not yet archived; §1 前置收口项与真实数据验证仍未定稿，见 tasks.md). Update Purpose after archive.

## Requirements

### Requirement: 逐料号库存对账差异报告

系统 SHALL 生成逐料号的库存对账差异报告，每行含：料号/名称、理论净用量、标准损耗基线、实际投料、总差异、差异率、分类档、是否需人工干预、所用 BOM/规则版本与数据源标记。报告 MUST 标注 **"AI 对账建议，结案在财务+供应链经理"**。

#### Scenario: 正常报告输出
- **WHEN** 对账引擎 + 分类完成
- **THEN** 输出逐料号差异明细 + 汇总（需人工项数/各分类档计数），并标注非终局声明

#### Scenario: BOM 残缺/无理论基准料号单列
- **WHEN** 某料号 BOM 残缺或理论净用量为 0
- **THEN** 该料号单列"待人工核"区，不混入可自动建议结案集合

### Requirement: L2 异常门禁（超阈值不自动结案）

系统 SHALL 对每料号过 L2 门禁：差异金额或差异比例超阈值（configurable，对接人定稿）→ 标 `需人工确认`，**MUST NOT 自动结案**；阈值内 → 标 `AI 建议通过`，仍待经理复核。AI 结论 MUST NOT 作为终局自动放行。

#### Scenario: 超阈值标需人工确认
- **WHEN** 某料号差异比例超过配置阈值
- **THEN** 标 `需人工确认`、计入异常清单，不自动结案

#### Scenario: 阈值内仍待复核
- **WHEN** 某料号差异在阈值内
- **THEN** 标 `AI 建议通过`，但报告仍声明结案需经理确认

### Requirement: 全链审计（数量为主，金额脱敏）

系统 SHALL 把每笔对账判定与差异分类写平台 `AuditLogger`（`scenario="FI1"`，`action="warehouse_reconcile"`/`"variance_classify"`，`automation_level="L2"`，含责任人、决策结构、数据源）。审计 decision MUST 以数量/差异率为主；金额若折算 MUST 仅存聚合或脱敏值，原始单价 MUST NOT 落 AI 侧。

#### Scenario: 每笔判定留痕
- **WHEN** 生成一料号的对账判定与分类
- **THEN** 写一条 append-only 审计记录，含理论/实际/差异/分类/是否需人工 + BOM/规则版本 + 数据源标记

#### Scenario: 财务红色金额脱敏
- **WHEN** 审计或报告涉及金额
- **THEN** 仅记录聚合/脱敏金额，原始单价不进审计 payload、不落 AI 侧
