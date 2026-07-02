# sc5-purchase-agent Specification

## Purpose
TBD - created by archiving change sc5-purchase-recommendation. Update Purpose after archive.
## Requirements
### Requirement: 场景入口执行
Agent SHALL通过 mock CSV connector 调用引擎，输出采购建议，写 L1/L2 分桶 audit。

#### Scenario: 正常执行
- **WHEN** 以 mock CSV 目录调用 `run_sc5(mock_dir, today)`
- **THEN** 返回 `list[dict]` 采购建议清单，且写入 SC5 audit 事件

#### Scenario: L1 audit（可自动下单）
- **WHEN** review_status="可自动下单" 的建议汇总
- **THEN** audit 事件：scenario=SC5, action=purchase_recommendation_eval, automation_level=L1, decision 含 auto_count / auto_total

#### Scenario: L2 audit（待人工审核）
- **WHEN** review_status="待人工审核" 的建议汇总
- **THEN** audit 事件：scenario=SC5, action=purchase_recommendation_eval, automation_level=L2, decision 含 review_count / review_total / human_required=True / triggered_rules 摘要

#### Scenario: IATF 合规
- **WHEN** automation_level=L2
- **THEN** mock 阶段 human_required=True 标记，不自动执行下单；ensure_ascii=False 保证中文可读

