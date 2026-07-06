# sc7-purchase-agent Specification

## Purpose
TBD - created by archiving change sc-v23-engine-migration. Update Purpose after archive.
## Requirements
### Requirement: 场景入口执行
Agent SHALL通过 mock CSV connector 调用引擎，输出采购建议，写 L1/L2 分桶 audit。本能力原为 SC5 场景入口，2026-07-06 v2.3 重排后迁移为 SC7 采购建议子能力入口；audit `scenario` 字段由退役编号 "SC5" 改标存续场景 "SC7"，L1/L2 分桶结构不变。

#### Scenario: 正常执行
- **WHEN** 以 mock CSV 目录调用 `run_sc7(mock_dir, today)`
- **THEN** 返回 `list[dict]` 采购建议清单，且写入 `scenario=SC7` 的 audit 事件

#### Scenario: L1 audit（可自动下单）
- **WHEN** review_status="可自动下单" 的建议汇总
- **THEN** audit 事件：scenario=SC7, action=purchase_recommendation_eval, automation_level=L1, decision 含 auto_count / auto_total

#### Scenario: L2 audit（待人工审核）
- **WHEN** review_status="待人工审核" 的建议汇总
- **THEN** audit 事件：scenario=SC7, action=purchase_recommendation_eval, automation_level=L2, decision 含 review_count / review_total / human_required=True / triggered_rules 摘要

#### Scenario: IATF 合规
- **WHEN** automation_level=L2
- **THEN** mock 阶段 human_required=True 标记，不自动执行下单；ensure_ascii=False 保证中文可读

