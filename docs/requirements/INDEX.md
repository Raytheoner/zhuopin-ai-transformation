# 六部门需求与规格索引

本索引是新需求进入 OpenSpec propose 前的登记池。行为契约以 `openspec/specs/` 为第一真源；业务意图以所属域 PRD 为第二真源；已确认的 `intent.md` 记录决策与口径，为第三真源。出现冲突时先停在 design 审，不以索引改写业务事实。

新场景须先在本表登记场景 ID、部门、档位与规划状态，再经 `zhuopin-requirement-grill` 确认同目录 `intent.md`，随后走 `openspec-propose`。深化优化用 refinement 仍需同步 delta spec 与 pytest。无业务证据的档位标“待业务核实”，不推定晋档。

## 表一：能力与主规格索引

| 能力/场景ID | 部门/域 | 档位 | openspec/specs/路径 | 对应子项目 pytest 测试路径 | 状态 |
|---|---|---|---|---|---|
| `Q2` | 质量 | 待业务核实 | `openspec/specs/q2-portal-display/spec.md` | `4-数字员工/质量部/Q2-8D报告AI判定/tests/test_webapp.py` | 已入规格池 |
| `q2-portal-display` | 质量 | 待业务核实 | `openspec/specs/q2-portal-display/spec.md` | `4-数字员工/质量部/Q2-8D报告AI判定/tests/test_webapp.py` | 主规格已建 |
| `SC1` | 采购 | 待业务核实 | `openspec/specs/sc1-audit-platform-bridge/spec.md` | `4-数字员工/采购部/SC1-供应商风险初筛/tests/test_audit_log.py` | 已入规格池 |
| `SC2` | 采购 | 待业务核实 | `openspec/specs/sc2-anomaly-review/spec.md` | `4-数字员工/采购部/SC2-采购周报自动生成/tests/test_review.py` | 已入规格池 |
| `SC4` | 采购 | 待业务核实 | `openspec/specs/sc4-clause-extraction/spec.md` | `4-数字员工/采购部/SC4-合同条款自动提取与审核/tests/test_clause_extract.py` | 已入规格池 |
| `SC7` | 采购 | 待业务核实 | `openspec/specs/sc7-purchase-agent/spec.md` | `4-数字员工/采购部/SC7-库存优化建议/tests/test_sc7_agent.py` | 已入规格池 |
| `SC8` | 采购 | 待业务核实 | `openspec/specs/sc8-answer-confidence-agent/spec.md` | `4-数字员工/采购部/SC8-客户订单交期智能承诺/tests/test_answer_confidence_agent.py` | 已入规格池 |
| `SC10` | 采购 | 待业务核实 | `openspec/specs/sc10-bom-review-facts/spec.md` | `4-数字员工/采购部/SC10-BOM评审与物料库管控/tests/test_review_facts.py` | 已入规格池 |
| `SC11` | 采购 | 待业务核实 | `openspec/specs/sc11-transfer-planning/spec.md` | `4-数字员工/采购部/SC11-库存智能调拨/tests/test_pmc_gate.py` | 已入规格池 |
| `O1` | 运营 | 待业务核实 | `openspec/specs/o1-smt-schedule-agent/spec.md` | `4-数字员工/运营部/O1-生产排程智能优化/tests/test_o1_agent.py` | 已入规格池 |
| `O2` | 运营 | 待业务核实 | `openspec/specs/o2-kit-shortage-alert/spec.md` | `4-数字员工/运营部/O2-物料齐套预警/tests/test_kit_shortage.py` | 已入规格池 |
| `O3` | 运营 | 规划中 | — | — | 规划中·待 propose |
| `O4` | 运营 | 规划中 | — | — | 规划中·待 propose |
| `R1` | 工程研发 | 规划中 | — | — | 暂缓 |
| `R2` | 工程研发 | 规划中 | — | — | 暂缓 |
| `R3` | 工程研发 | 规划中 | — | — | 暂缓 |
| `R4` | 工程研发 | 规划中 | — | — | 暂缓 |
| `R5` | 工程研发 | 规划中 | — | — | 暂缓 |
| `Q4` | 质量 | 规划中 | — | — | 规划中·待 propose |
| `Q6` | 质量 | 规划中 | — | — | 规划中·待 propose |
| `FI1` | 财务 | 待业务核实 | `openspec/specs/fi1-feed-source/spec.md` | `4-数字员工/财务部/FI1-供应链仓库对账/tests/test_feed_source.py` | 已入规格池 |
| `FI2` | 财务 | 待业务核实 | `openspec/specs/fi2-feed-source/spec.md` | `4-数字员工/财务部/FI2-三单匹配自动对账/tests/test_feed_source.py` | 已入规格池 |
| `FI3` | 财务 | 规划中 | — | — | 规划中·待 propose |
| `FI4` | 财务 | 规划中 | — | — | 规划中·待 propose |
| `FI5` | 财务 | 待业务核实 | `openspec/specs/fi5-budget-guard/spec.md` | `4-数字员工/财务部/FI5-费用报销智能审核/tests/test_scaffold.py` | 已入规格池 |
| `FI6` | 财务 | 待业务核实 | `openspec/specs/fi6-case-library/spec.md` | `4-数字员工/财务部/FI6-异常交易实时检测/tests/test_scaffold.py` | 已入规格池 |
| `FI7` | 财务 | 规划中 | — | — | 规划中·待 propose |
| `FI8` | 财务 | 待业务核实 | `openspec/specs/fi8-forecast-engine/spec.md` | `4-数字员工/财务部/FI8-现金流预测与智能预警/tests/test_scaffold.py` | 已入规格池 |
| `FI9` | 财务 | 待业务核实 | `openspec/specs/fi9-aux-ledger-and-filing/spec.md` | `4-数字员工/财务部/FI9-研发费用归集与高新认定/tests/test_scaffold.py` | 已入规格池 |
| `FI10` | 财务 | 待业务核实 | `openspec/specs/fi10-alerting-and-provision/spec.md` | `4-数字员工/财务部/FI10-存货跌价智能分析/tests/test_intake.py` | 已入规格池 |
| `S1` | 销售 | 规划中 | — | — | 暂缓 |
| `S2` | 销售 | 规划中 | — | — | 暂缓 |
| `S3` | 销售 | 规划中 | — | — | 暂缓 |
| `S4` | 销售 | 规划中 | — | — | 暂缓 |
| `S5` | 销售 | 规划中 | — | — | 暂缓 |
| `S6` | 销售 | 规划中 | — | — | 暂缓 |
| `Q1` |  | 规划中 | — | — | 规划中·待 propose |
| `Q3` |  | 规划中 | — | — | 规划中·待 propose |
| `Q5` |  | 规划中 | — | — | 规划中·待 propose |
| `Q7` |  | 规划中 | — | — | 规划中·待 propose |
| `Q8` |  | 规划中 | — | — | 规划中·待 propose |
| `aibot-decision-reminder` | 机制/平台 | 不适用 | `openspec/specs/aibot-decision-reminder/spec.md` | `5-平台底座/wecom-aibot-service/tests/test_decision_reminder.py` | 主规格已建 |
| `aibot-liveness-heartbeat` | 机制/平台 | 不适用 | `openspec/specs/aibot-liveness-heartbeat/spec.md` | `5-平台底座/wecom-aibot-service/tests/test_liveness.py` | 主规格已建 |
| `aibot-liveness-inprogress-alert` | 机制/平台 | 不适用 | `openspec/specs/aibot-liveness-inprogress-alert/spec.md` | `5-平台底座/wecom-aibot-service/tests/test_disconnect_inprogress_alert.py` | 主规格已建 |
| `aibot-queue-append-lock-deferral` | 机制/平台 | 不适用 | `openspec/specs/aibot-queue-append-lock-deferral/spec.md` | `5-平台底座/wecom-aibot-service/tests/test_queue_appender.py` | 主规格已建 |
| `aibot-queue-domain-routing` | 机制/平台 | 不适用 | `openspec/specs/aibot-queue-domain-routing/spec.md` | `5-平台底座/wecom-aibot-service/tests/test_queue_appender_domain_routing.py` | 主规格已建 |
| `aibot-queue-pairing-invariant` | 机制/平台 | 不适用 | `openspec/specs/aibot-queue-pairing-invariant/spec.md` | `5-平台底座/wecom-aibot-service/tests/test_queue_appender.py` | 主规格已建 |
| `audit-hash-chain` | 机制/平台 | 不适用 | `openspec/specs/audit-hash-chain/spec.md` | `5-平台底座/zhuopin_platform/tests/test_audit_hash_chain.py` | 主规格已建 |
| `baoguan-alert-dispatch` | 采购 | 待业务核实 | `openspec/specs/baoguan-alert-dispatch/spec.md` | `4-数字员工/采购部/SC8-客户订单交期智能承诺/tests/test_baoguan_alert.py` | 主规格已建 |
| `baoguan-case-management` | 采购 | 待业务核实 | `openspec/specs/baoguan-case-management/spec.md` | `4-数字员工/采购部/SC8-客户订单交期智能承诺/tests/test_baoguan_case_draft.py` | 主规格已建 |
| `baoguan-partial-kit-display` | 采购 | 待业务核实 | `openspec/specs/baoguan-partial-kit-display/spec.md` | `4-数字员工/采购部/SC8-客户订单交期智能承诺/tests/test_baoguan_partial_kit.py` | 主规格已建 |
| `baoguan-substitute-material` | 采购 | 待业务核实 | `openspec/specs/baoguan-substitute-material/spec.md` | `4-数字员工/采购部/SC8-客户订单交期智能承诺/tests/test_baoguan_substitute_merge.py` | 主规格已建 |
| `baoguan-web-service` | 采购 | 待业务核实 | `openspec/specs/baoguan-web-service/spec.md` | `4-数字员工/采购部/SC8-客户订单交期智能承诺/tests/test_baoguan_service.py` | 主规格已建 |
| `change-completion-classification` | 机制/平台 | 不适用 | `openspec/specs/change-completion-classification/spec.md` | `0-学习与工具/test_工具-变更包自动归档.py` | 主规格已建 |
| `connector-schema-validation` | 机制/平台 | 不适用 | `openspec/specs/connector-schema-validation/spec.md` | `5-平台底座/zhuopin_platform/tests/test_erp_connector_validation.py` | 主规格已建 |
| `delivery-commitment-gate` | 采购 | 待业务核实 | `openspec/specs/delivery-commitment-gate/spec.md` | `4-数字员工/采购部/SC8-客户订单交期智能承诺/tests/test_commitment_gate.py` | 主规格已建 |
| `delivery-date-forecast` | 采购 | 待业务核实 | `openspec/specs/delivery-date-forecast/spec.md` | `4-数字员工/采购部/SC8-客户订单交期智能承诺/tests/test_forecast.py` | 主规格已建 |
| `delivery-deviation-monitor` | 采购 | 待业务核实 | `openspec/specs/delivery-deviation-monitor/spec.md` | `4-数字员工/采购部/SC8-客户订单交期智能承诺/tests/test_forecast.py` | 主规格已建 |
| `editable-pth-blindspot-guard` | 机制/平台 | 不适用 | `openspec/specs/editable-pth-blindspot-guard/spec.md` | `0-学习与工具/test_hooks-pretooluse-queue-read-guard.py` | 主规格已建 |
| `editlock-assertion-gate-scope` | 机制/平台 | 不适用 | `openspec/specs/editlock-assertion-gate-scope/spec.md` | `0-学习与工具/test_工具-共享文档编辑锁.py` | 主规格已建 |
| `editlock-credential-shape-guard` | 机制/平台 | 不适用 | `openspec/specs/editlock-credential-shape-guard/spec.md` | `0-学习与工具/test_工具-共享文档编辑锁.py` | 主规格已建 |
| `editlock-dual-queue-routing` | 机制/平台 | 不适用 | `openspec/specs/editlock-dual-queue-routing/spec.md` | `0-学习与工具/test_工具-共享文档编辑锁.py` | 主规格已建 |
| `editlock-followup-hold-consistency-guard` | 机制/平台 | 不适用 | `openspec/specs/editlock-followup-hold-consistency-guard/spec.md` | `0-学习与工具/test_工具-共享文档编辑锁.py` | 主规格已建 |
| `editlock-mechanism-wip-guard` | 机制/平台 | 不适用 | `openspec/specs/editlock-mechanism-wip-guard/spec.md` | `0-学习与工具/test_工具-共享文档编辑锁.py` | 主规格已建 |
| `editlock-mutex-stale-cleanup-resilience` | 机制/平台 | 不适用 | `openspec/specs/editlock-mutex-stale-cleanup-resilience/spec.md` | `0-学习与工具/test_工具-共享文档编辑锁.py` | 主规格已建 |
| `editlock-opener-guard` | 机制/平台 | 不适用 | `openspec/specs/editlock-opener-guard/spec.md` | `0-学习与工具/test_工具-共享文档编辑锁.py` | 主规格已建 |
| `editlock-person-attribute-lint` | 机制/平台 | 不适用 | `openspec/specs/editlock-person-attribute-lint/spec.md` | `0-学习与工具/test_工具-共享文档编辑锁.py` | 主规格已建 |
| `editlock-queue-number-reservation` | 机制/平台 | 不适用 | `openspec/specs/editlock-queue-number-reservation/spec.md` | `0-学习与工具/test_工具-共享文档编辑锁.py` | 主规格已建 |
| `editlock-registration-completeness` | 机制/平台 | 不适用 | `openspec/specs/editlock-registration-completeness/spec.md` | `0-学习与工具/test_工具-共享文档编辑锁.py` | 主规格已建 |
| `editlock-section-append-guard` | 机制/平台 | 不适用 | `openspec/specs/editlock-section-append-guard/spec.md` | `0-学习与工具/test_工具-共享文档编辑锁.py` | 主规格已建 |
| `editlock-section-leading-status-guard` | 机制/平台 | 不适用 | `openspec/specs/editlock-section-leading-status-guard/spec.md` | `0-学习与工具/test_工具-共享文档编辑锁.py` | 主规格已建 |
| `fi1-feed-source` | 财务 | 待业务核实 | `openspec/specs/fi1-feed-source/spec.md` | `4-数字员工/财务部/FI1-供应链仓库对账/tests/test_feed_source.py` | 主规格已建 |
| `fi1-recon-report` | 财务 | 待业务核实 | `openspec/specs/fi1-recon-report/spec.md` | `4-数字员工/财务部/FI1-供应链仓库对账/tests/test_recon_report.py` | 主规格已建 |
| `fi1-reconcile-engine` | 财务 | 待业务核实 | `openspec/specs/fi1-reconcile-engine/spec.md` | `4-数字员工/财务部/FI1-供应链仓库对账/tests/test_reconcile_engine.py` | 主规格已建 |
| `fi1-variance-classify` | 财务 | 待业务核实 | `openspec/specs/fi1-variance-classify/spec.md` | `4-数字员工/财务部/FI1-供应链仓库对账/tests/test_variance_classify.py` | 主规格已建 |
| `fi10-alerting-and-provision` | 财务 | 待业务核实 | `openspec/specs/fi10-alerting-and-provision/spec.md` | `4-数字员工/财务部/FI10-存货跌价智能分析/tests/test_intake.py` | 主规格已建 |
| `fi10-inventory-intake` | 财务 | 待业务核实 | `openspec/specs/fi10-inventory-intake/spec.md` | `4-数字员工/财务部/FI10-存货跌价智能分析/tests/test_intake.py` | 主规格已建 |
| `fi10-nrv-writedown-engine` | 财务 | 待业务核实 | `openspec/specs/fi10-nrv-writedown-engine/spec.md` | `4-数字员工/财务部/FI10-存货跌价智能分析/tests/test_intake.py` | 主规格已建 |
| `fi2-feed-source` | 财务 | 待业务核实 | `openspec/specs/fi2-feed-source/spec.md` | `4-数字员工/财务部/FI2-三单匹配自动对账/tests/test_feed_source.py` | 主规格已建 |
| `fi2-match-engine` | 财务 | 待业务核实 | `openspec/specs/fi2-match-engine/spec.md` | `4-数字员工/财务部/FI2-三单匹配自动对账/tests/test_match_engine.py` | 主规格已建 |
| `fi2-price-check` | 财务 | 待业务核实 | `openspec/specs/fi2-price-check/spec.md` | `4-数字员工/财务部/FI2-三单匹配自动对账/tests/test_price_check.py` | 主规格已建 |
| `fi2-recon-report` | 财务 | 待业务核实 | `openspec/specs/fi2-recon-report/spec.md` | `4-数字员工/财务部/FI2-三单匹配自动对账/tests/test_recon_report.py` | 主规格已建 |
| `fi2-result-classify` | 财务 | 待业务核实 | `openspec/specs/fi2-result-classify/spec.md` | `4-数字员工/财务部/FI2-三单匹配自动对账/tests/test_result_classify.py` | 主规格已建 |
| `fi2-tax-export-ingest` | 财务 | 待业务核实 | `openspec/specs/fi2-tax-export-ingest/spec.md` | `4-数字员工/财务部/FI2-三单匹配自动对账/tests/test_tax_export_ingest.py` | 主规格已建 |
| `fi5-budget-guard` | 财务 | 待业务核实 | `openspec/specs/fi5-budget-guard/spec.md` | `4-数字员工/财务部/FI5-费用报销智能审核/tests/test_scaffold.py` | 主规格已建；测试仅脚手架 |
| `fi5-expense-report` | 财务 | 待业务核实 | `openspec/specs/fi5-expense-report/spec.md` | `4-数字员工/财务部/FI5-费用报销智能审核/tests/test_scaffold.py` | 主规格已建；测试仅脚手架 |
| `fi5-policy-rules` | 财务 | 待业务核实 | `openspec/specs/fi5-policy-rules/spec.md` | `4-数字员工/财务部/FI5-费用报销智能审核/tests/test_scaffold.py` | 主规格已建；测试仅脚手架 |
| `fi5-risk-grading` | 财务 | 待业务核实 | `openspec/specs/fi5-risk-grading/spec.md` | `4-数字员工/财务部/FI5-费用报销智能审核/tests/test_scaffold.py` | 主规格已建；测试仅脚手架 |
| `fi6-case-library` | 财务 | 待业务核实 | `openspec/specs/fi6-case-library/spec.md` | `4-数字员工/财务部/FI6-异常交易实时检测/tests/test_scaffold.py` | 主规格已建；测试仅脚手架 |
| `fi6-escalation-and-report` | 财务 | 待业务核实 | `openspec/specs/fi6-escalation-and-report/spec.md` | `4-数字员工/财务部/FI6-异常交易实时检测/tests/test_scaffold.py` | 主规格已建；测试仅脚手架 |
| `fi6-pattern-detectors` | 财务 | 待业务核实 | `openspec/specs/fi6-pattern-detectors/spec.md` | `4-数字员工/财务部/FI6-异常交易实时检测/tests/test_scaffold.py` | 主规格已建；测试仅脚手架 |
| `fi8-forecast-engine` | 财务 | 待业务核实 | `openspec/specs/fi8-forecast-engine/spec.md` | `4-数字员工/财务部/FI8-现金流预测与智能预警/tests/test_scaffold.py` | 主规格已建；测试仅脚手架 |
| `fi8-gap-alerting` | 财务 | 待业务核实 | `openspec/specs/fi8-gap-alerting/spec.md` | `4-数字员工/财务部/FI8-现金流预测与智能预警/tests/test_scaffold.py` | 主规格已建；测试仅脚手架 |
| `fi8-whatif-engine` | 财务 | 待业务核实 | `openspec/specs/fi8-whatif-engine/spec.md` | `4-数字员工/财务部/FI8-现金流预测与智能预警/tests/test_scaffold.py` | 主规格已建；测试仅脚手架 |
| `fi9-aux-ledger-and-filing` | 财务 | 待业务核实 | `openspec/specs/fi9-aux-ledger-and-filing/spec.md` | `4-数字员工/财务部/FI9-研发费用归集与高新认定/tests/test_scaffold.py` | 主规格已建；测试仅脚手架 |
| `fi9-capitalization-rules` | 财务 | 待业务核实 | `openspec/specs/fi9-capitalization-rules/spec.md` | `4-数字员工/财务部/FI9-研发费用归集与高新认定/tests/test_scaffold.py` | 主规格已建；测试仅脚手架 |
| `fi9-cost-collection` | 财务 | 待业务核实 | `openspec/specs/fi9-cost-collection/spec.md` | `4-数字员工/财务部/FI9-研发费用归集与高新认定/tests/test_scaffold.py` | 主规格已建；测试仅脚手架 |
| `followup-readme-archive` | 机制/平台 | 不适用 | `openspec/specs/followup-readme-archive/spec.md` | `0-学习与工具/test_工具-跟进信README归档.py` | 主规格已建 |
| `followup-readme-read-guard` | 机制/平台 | 不适用 | `openspec/specs/followup-readme-read-guard/spec.md` | `0-学习与工具/test_工具-跟进信README归档.py` | 主规格已建 |
| `followup-readme-registry` | 机制/平台 | 不适用 | `openspec/specs/followup-readme-registry/spec.md` | `0-学习与工具/test_工具-跟进信README归档.py` | 主规格已建 |
| `followup-readme-row-length-guard` | 机制/平台 | 不适用 | `openspec/specs/followup-readme-row-length-guard/spec.md` | `0-学习与工具/test_工具-跟进信README归档.py` | 主规格已建 |
| `global-memory-inspection` | 机制/平台 | 不适用 | `openspec/specs/global-memory-inspection/spec.md` | `0-学习与工具/test_工具-落库sweep.py` | 主规格已建 |
| `kit-shortage-engine` | 运营 | 待业务核实 | `openspec/specs/kit-shortage-engine/spec.md` | `4-数字员工/运营部/O2-物料齐套预警/tests/test_kit_shortage.py` | 主规格已建 |
| `lane-clearpool` | 机制/平台 | 不适用 | `openspec/specs/lane-clearpool/spec.md` | `0-学习与工具/test_工具-泳道看护状态机.py` | 主规格已建 |
| `o1-smt-schedule-agent` | 运营 | 待业务核实 | `openspec/specs/o1-smt-schedule-agent/spec.md` | `4-数字员工/运营部/O1-生产排程智能优化/tests/test_o1_agent.py` | 主规格已建 |
| `o1-smt-schedule-engine` | 运营 | 待业务核实 | `openspec/specs/o1-smt-schedule-engine/spec.md` | `4-数字员工/运营部/O1-生产排程智能优化/tests/test_schedule_engine.py` | 主规格已建 |
| `o2-kit-shortage-alert` | 运营 | 待业务核实 | `openspec/specs/o2-kit-shortage-alert/spec.md` | `4-数字员工/运营部/O2-物料齐套预警/tests/test_kit_shortage.py` | 主规格已建 |
| `opener-batch-archive-precheck` | 机制/平台 | 不适用 | `openspec/specs/opener-batch-archive-precheck/spec.md` | `0-学习与工具/test_工具-opener生成.py` | 主规格已建 |
| `platform-data-connectors` | 机制/平台 | 不适用 | `openspec/specs/platform-data-connectors/spec.md` | `5-平台底座/zhuopin_platform/tests/test_u9c_data_source.py` | 主规格已建 |
| `platform-env-anchor` | 机制/平台 | 不适用 | `openspec/specs/platform-env-anchor/spec.md` | `5-平台底座/zhuopin_platform/tests/test_env_anchor.py` | 主规格已建 |
| `platform-kit-engine` | 机制/平台 | 不适用 | `openspec/specs/platform-kit-engine/spec.md` | `5-平台底座/zhuopin_platform/tests/test_kit_engine.py` | 主规格已建 |
| `platform-notification-channels` | 机制/平台 | 不适用 | `openspec/specs/platform-notification-channels/spec.md` | `5-平台底座/zhuopin_platform/tests/test_notifications.py` | 主规格已建 |
| `platform-oem-isolation` | 机制/平台 | 不适用 | `openspec/specs/platform-oem-isolation/spec.md` | `5-平台底座/zhuopin_platform/tests/test_oem_isolation_audit.py` | 主规格已建 |
| `platform-path-bootstrap` | 机制/平台 | 不适用 | `openspec/specs/platform-path-bootstrap/spec.md` | `5-平台底座/zhuopin_platform/tests/test_bootstrap_ensure_paths.py` | 主规格已建 |
| `platform-repo-root-resolution` | 机制/平台 | 不适用 | `openspec/specs/platform-repo-root-resolution/spec.md` | `5-平台底座/zhuopin_platform/tests/test_smoke.py` | 主规格已建 |
| `platform-service-auth-gate` | 机制/平台 | 不适用 | `openspec/specs/platform-service-auth-gate/spec.md` | `5-平台底座/wecom-aibot-service/tests/test_gates.py` | 主规格已建 |
| `pmc-priority-allocation` | 采购 | 待业务核实 | `openspec/specs/pmc-priority-allocation/spec.md` | `4-数字员工/采购部/SC8-客户订单交期智能承诺/tests/test_priority_resolver_stub.py` | 主规格已建 |
| `portal-access-log` | 机制/平台 | 不适用 | `openspec/specs/portal-access-log/spec.md` | `5-平台底座/unified-portal-gateway/tests/test_access_log.py` | 主规格已建 |
| `portal-gateway-routing` | 机制/平台 | 不适用 | `openspec/specs/portal-gateway-routing/spec.md` | `5-平台底座/unified-portal-gateway/tests/test_routing.py` | 主规格已建 |
| `portal-permission-model` | 机制/平台 | 不适用 | `openspec/specs/portal-permission-model/spec.md` | `5-平台底座/unified-portal-gateway/tests/test_permissions.py` | 主规格已建 |
| `portal-wecom-sso` | 机制/平台 | 不适用 | `openspec/specs/portal-wecom-sso/spec.md` | `5-平台底座/wecom-aibot-service/tests/test_gates.py` | 主规格已建 |
| `qd-a-calibrate` | 质量 | 待业务核实 | `openspec/specs/qd-a-calibrate/spec.md` | `4-数字员工/质量部/QD-A-8D不良分析/tests/test_calibrate.py` | 主规格已建 |
| `qd-a-doc-reader` | 质量 | 待业务核实 | `openspec/specs/qd-a-doc-reader/spec.md` | `4-数字员工/质量部/QD-A-8D不良分析/tests/test_doc_reader.py` | 主规格已建 |
| `qd-a-field-extractor` | 质量 | 待业务核实 | `openspec/specs/qd-a-field-extractor/spec.md` | `4-数字员工/质量部/QD-A-8D不良分析/tests/test_field_extractor.py` | 主规格已建 |
| `qd-a-scrubber` | 质量 | 待业务核实 | `openspec/specs/qd-a-scrubber/spec.md` | `4-数字员工/质量部/QD-A-8D不良分析/tests/test_scrubber.py` | 主规格已建 |
| `qd-b-intake-parser` | 质量 | 待业务核实 | `openspec/specs/qd-b-intake-parser/spec.md` | `4-数字员工/质量部/QD-B-立项审核门禁/tests/test_parser.py` | 主规格已建 |
| `qd-b-portal-display` | 质量 | 待业务核实 | `openspec/specs/qd-b-portal-display/spec.md` | `4-数字员工/质量部/QD-B-立项审核门禁/tests/test_webapp_ui_contract.py` | 主规格已建 |
| `qd-b-review-gate` | 质量 | 待业务核实 | `openspec/specs/qd-b-review-gate/spec.md` | `4-数字员工/质量部/QD-B-立项审核门禁/tests/test_webapp_gate.py` | 主规格已建 |
| `qd-b-rule-engine` | 质量 | 待业务核实 | `openspec/specs/qd-b-rule-engine/spec.md` | `4-数字员工/质量部/QD-B-立项审核门禁/tests/test_manual_class_rules.py` | 主规格已建 |
| `qd-b-semantic-judge` | 质量 | 待业务核实 | `openspec/specs/qd-b-semantic-judge/spec.md` | `4-数字员工/质量部/QD-B-立项审核门禁/tests/test_semantic_placeholder.py` | 主规格已建 |
| `queue-authoritative-path-resolution` | 机制/平台 | 不适用 | `openspec/specs/queue-authoritative-path-resolution/spec.md` | `0-学习与工具/test_工具-队列查询.py` | 主规格已建 |
| `queue-claim-time-preregistration` | 机制/平台 | 不适用 | `openspec/specs/queue-claim-time-preregistration/spec.md` | `0-学习与工具/test_工具-队列查询.py` | 主规格已建 |
| `queue-dual-file-topology` | 机制/平台 | 不适用 | `openspec/specs/queue-dual-file-topology/spec.md` | `0-学习与工具/test_工具-队列查询.py` | 主规格已建 |
| `queue-query-archive-lookup` | 机制/平台 | 不适用 | `openspec/specs/queue-query-archive-lookup/spec.md` | `0-学习与工具/test_工具-队列查询.py` | 主规格已建 |
| `queue-row-domain-field` | 机制/平台 | 不适用 | `openspec/specs/queue-row-domain-field/spec.md` | `0-学习与工具/test_工具-队列查询.py` | 主规格已建 |
| `queue-row-status-field` | 机制/平台 | 不适用 | `openspec/specs/queue-row-status-field/spec.md` | `0-学习与工具/test_工具-队列查询.py` | 主规格已建 |
| `queue-table-shared-parser` | 机制/平台 | 不适用 | `openspec/specs/queue-table-shared-parser/spec.md` | `0-学习与工具/test_工具-队列查询.py` | 主规格已建 |
| `resident-carrier-realign` | 机制/平台 | 不适用 | `openspec/specs/resident-carrier-realign/spec.md` | `0-学习与工具/test_工具-落库sweep.py` | 主规格已建 |
| `sc1-audit-platform-bridge` | 采购 | 待业务核实 | `openspec/specs/sc1-audit-platform-bridge/spec.md` | `4-数字员工/采购部/SC1-供应商风险初筛/tests/test_audit_log.py` | 主规格已建 |
| `sc1-srm-platform-connector` | 采购 | 待业务核实 | `openspec/specs/sc1-srm-platform-connector/spec.md` | `4-数字员工/采购部/SC1-供应商风险初筛/tests/test_srm_platform.py` | 主规格已建 |
| `sc10-bom-review-facts` | 采购 | 待业务核实 | `openspec/specs/sc10-bom-review-facts/spec.md` | `4-数字员工/采购部/SC10-BOM评审与物料库管控/tests/test_review_facts.py` | 主规格已建 |
| `sc11-transfer-planning` | 采购 | 待业务核实 | `openspec/specs/sc11-transfer-planning/spec.md` | `4-数字员工/采购部/SC11-库存智能调拨/tests/test_pmc_gate.py` | 主规格已建 |
| `sc2-anomaly-review` | 采购 | 待业务核实 | `openspec/specs/sc2-anomaly-review/spec.md` | `4-数字员工/采购部/SC2-采购周报自动生成/tests/test_review.py` | 主规格已建 |
| `sc2-feed-source` | 采购 | 待业务核实 | `openspec/specs/sc2-feed-source/spec.md` | `4-数字员工/采购部/SC2-采购周报自动生成/tests/test_sources.py` | 主规格已建 |
| `sc2-metric-engine` | 采购 | 待业务核实 | `openspec/specs/sc2-metric-engine/spec.md` | `4-数字员工/采购部/SC2-采购周报自动生成/tests/test_metrics.py` | 主规格已建 |
| `sc2-report-delivery` | 采购 | 待业务核实 | `openspec/specs/sc2-report-delivery/spec.md` | `4-数字员工/采购部/SC2-采购周报自动生成/tests/test_report.py` | 主规格已建 |
| `sc2-weekly-report` | 采购 | 待业务核实 | `openspec/specs/sc2-weekly-report/spec.md` | `4-数字员工/采购部/SC2-采购周报自动生成/tests/test_report.py` | 主规格已建 |
| `sc4-clause-extraction` | 采购 | 待业务核实 | `openspec/specs/sc4-clause-extraction/spec.md` | `4-数字员工/采购部/SC4-合同条款自动提取与审核/tests/test_clause_extract.py` | 主规格已建 |
| `sc5-kit-engine-platform` | 采购 | 待业务核实 | `openspec/specs/sc5-kit-engine-platform/spec.md` | `5-平台底座/zhuopin_platform/tests/test_kit_engine.py` | 主规格已建 |
| `sc7-purchase-agent` | 采购 | 待业务核实 | `openspec/specs/sc7-purchase-agent/spec.md` | `4-数字员工/采购部/SC7-库存优化建议/tests/test_sc7_agent.py` | 主规格已建 |
| `sc7-purchase-engine` | 采购 | 待业务核实 | `openspec/specs/sc7-purchase-engine/spec.md` | `4-数字员工/采购部/SC7-库存优化建议/tests/test_purchase_engine.py` | 主规格已建 |
| `sc8-answer-confidence-agent` | 采购 | 待业务核实 | `openspec/specs/sc8-answer-confidence-agent/spec.md` | `4-数字员工/采购部/SC8-客户订单交期智能承诺/tests/test_answer_confidence_agent.py` | 主规格已建 |
| `sc8-answer-confidence-engine` | 采购 | 待业务核实 | `openspec/specs/sc8-answer-confidence-engine/spec.md` | `4-数字员工/采购部/SC8-客户订单交期智能承诺/tests/test_answer_confidence_engine.py` | 主规格已建 |
| `secrets-provider` | 机制/平台 | 不适用 | `openspec/specs/secrets-provider/spec.md` | `5-平台底座/zhuopin_platform/tests/test_secrets_provider.py` | 主规格已建 |
| `serial-test-first-construction` | 机制/平台 | 不适用 | `openspec/specs/serial-test-first-construction/spec.md` | `0-学习与工具/codex-handoff/tests/test_feedback_workflow.py` | 主规格已建；原泳道回归仍保留 |
| `srm-rate-limiting` | 机制/平台 | 不适用 | `openspec/specs/srm-rate-limiting/spec.md` | `5-平台底座/zhuopin_platform/tests/test_srm_rate_limiting.py` | 主规格已建 |
| `stock-inventory-source` | 机制/平台 | 不适用 | `openspec/specs/stock-inventory-source/spec.md` | `5-平台底座/zhuopin_platform/tests/test_stock_inventory.py` | 主规格已建 |
| sweep-alert-lifecycle-guard | 机制/平台 | 不适用 | openspec/specs/sweep-alert-lifecycle-guard/spec.md | 0-学习与工具/test_工具-落库sweep.py | 主规格已建 |
| `sweep-batch-status-classification` | 机制/平台 | 不适用 | `openspec/specs/sweep-batch-status-classification/spec.md` | `0-学习与工具/test_工具-落库sweep.py` | 主规格已建 |
| `sweep-claude-md-size-guard` | 机制/平台 | 不适用 | `openspec/specs/sweep-claude-md-size-guard/spec.md` | `0-学习与工具/test_工具-落库sweep-根CLAUDE超阈值拒绝.py` | 主规格已建 |
| `sweep-commit-message-extraction` | 机制/平台 | 不适用 | `openspec/specs/sweep-commit-message-extraction/spec.md` | `0-学习与工具/test_工具-落库sweep.py` | 主规格已建 |
| `sweep-fork-alert` | 机制/平台 | 不适用 | `openspec/specs/sweep-fork-alert/spec.md` | `0-学习与工具/test_工具-落库sweep.py` | 主规格已建 |
| `sweep-manifest-coverage-guard` | 机制/平台 | 不适用 | `openspec/specs/sweep-manifest-coverage-guard/spec.md` | `0-学习与工具/test_工具-落库sweep.py` | 主规格已建 |
| `sweep-resident-carrier-autosync` | 机制/平台 | 不适用 | `openspec/specs/sweep-resident-carrier-autosync/spec.md` | `0-学习与工具/test_工具-落库sweep.py` | 主规格已建 |
| `sweep-resident-service-alert` | 机制/平台 | 不适用 | `openspec/specs/sweep-resident-service-alert/spec.md` | `0-学习与工具/test_工具-落库sweep.py` | 主规格已建 |
| `sweep-startup-resilience` | 机制/平台 | 不适用 | `openspec/specs/sweep-startup-resilience/spec.md` | `0-学习与工具/test_工具-落库sweep.py` | 主规格已建 |
| `sweep-sync-reconciliation` | 机制/平台 | 不适用 | `openspec/specs/sweep-sync-reconciliation/spec.md` | `0-学习与工具/test_工具-落库sweep.py` | 主规格已建 |
| `wecom-aibot-connector` | 机制/平台 | 不适用 | `openspec/specs/wecom-aibot-connector/spec.md` | `5-平台底座/wecom-aibot-service/tests/test_local_outbox_connector.py` | 主规格已建 |
| `wecom-feedback-intake` | 机制/平台 | 不适用 | `openspec/specs/wecom-feedback-intake/spec.md` | `5-平台底座/wecom-aibot-service/tests/test_intake.py` | 主规格已建 |
| `wecom-followup-auto-dispatch` | 机制/平台 | 不适用 | `openspec/specs/wecom-followup-auto-dispatch/spec.md` | `5-平台底座/wecom-aibot-service/tests/test_dispatch.py` | 主规格已建 |
| `wecom-followup-delivery` | 机制/平台 | 不适用 | `openspec/specs/wecom-followup-delivery/spec.md` | `5-平台底座/wecom-aibot-service/tests/test_delivery.py` | 主规格已建 |
| `wecom-followup-review-state` | 机制/平台 | 不适用 | `openspec/specs/wecom-followup-review-state/spec.md` | `5-平台底座/wecom-aibot-service/tests/test_followup_readme_bridge.py` | 主规格已建 |
| `worktree-import-bootstrap` | 机制/平台 | 不适用 | `openspec/specs/worktree-import-bootstrap/spec.md` | `0-学习与工具/test_工具-worktree体检.py` | 主规格已建 |
| `worktree-scan-claude-md-lag-column` | 机制/平台 | 不适用 | `openspec/specs/worktree-scan-claude-md-lag-column/spec.md` | `0-学习与工具/test_工具-worktree体检.py` | 主规格已建 |

规划中无主规格的场景保留空路径；它们尚未被表述为已建能力。存量主规格若缺可证实的对应 pytest，明确标为待补，禁止借其它场景测试充数；新增/触碰的包必须补齐对应测试。


## 表二：在途变更包四态表

<!-- 原 workflow 三接口任务 #711：会话转交文档与企微回件共用原拆件/队列，不自动生成业务授权。 -->

| 变更包名 | 部门/域 | 模式 (feature/refinement) | 四态标签 | tasks 进度 | 外部卡点/队列行指针 |
|---|---|---|---|---:|---|
| `mechanism-publication-prerequisites-1116` | 机制/平台 | refinement | archive | 2/2 | 已批发布必要前置：精确公开协议标签分类；原强模式/写侧判据不变；仅隔离验证；归档：`openspec/changes/archive/2026-11-16-mechanism-publication-prerequisites-1116/`。 |
| `portal-q2-ui` | 质量 | feature | frozen_by_prd | 16/18 | 发布候选保留远端基线，未移植Q2业务候选及后续结案；非原业务现时状态改判。 |
| `watch-write-before-build-1115` | 机制/平台 | refinement | archive | 3/3 | #715；仅原消费/认领/预登记链，模拟与自然实跑分列；#563/#636/#670不接管 |
| `aibot-group-alert-route-1115` | 机制/平台 | refinement | archive | 3/3 | 本地943 passed/1 skipped，6场景accepted；归档2026-11-15-aibot-group-alert-route-1115。原#387留现役接纳及本人真实冒烟，见387本地修正验收.md。 |
| `lane-watch-serial-test-first-1014` | 机制/平台 | feature | archive | 10/10 | 10/10、无暂缓，OpenSpec validate --strict 通过；2026-11-14 已归档并同步主规格 |
| `feedback-workflow-interfaces-1114` | 机制/平台 | refinement | archive | 4/4 | #711；归档 `2026-11-14-feedback-workflow-interfaces-1114`；原回件fixture全链通过，完整回归683 passed/4项原有权限skip，exit 0 |
| `queue-driven-daily-routine-1114` | 机制/平台 | refinement | archive | 5/5 | #712；`openspec/changes/archive/2026-11-14-queue-driven-daily-routine-1114/`；短入口、需求验收、原事件链及160行整理完成；周期拆件巡逻继续停用 |
| `queue-prerequisite-context-1115` | 机制/平台 | refinement | archive | 4/4 | #454；原158逐项前置/157指针读回、#670保留原写方；短入口19定向/完整714pass、5场景mock已验并归档；不新增执行器或业务权限 |
| `sweep-partial-report-1114` | 机制/平台 | refinement | archive | 3/3 | #422；本地报告/精确去重/回执修复已验收；归档 `openspec/changes/archive/2026-11-14-sweep-partial-report-1114`；现役接纳与真实LAN尾项仍归原行 |
| `requirement-alert-alignment-1115` | 机制/平台 | refinement | archive | 4/4 | #713；本地治理补缝已验，12:17自然轮23受控/异常0；归档2026-11-15-requirement-alert-alignment-1115 |
| `sc7-feedback-1112-refinement` | 采购 | refinement | blocked_external | 9/10 | #670；1115KH-LAN-4技术实交702pass，六仓/GR/单位与2968物料预警已齐；2.2只留发货计划/调入期间源及专业验收，IT17已发。采购27收件销号不等于本包归档；反馈保护/周期提报及周五刷新已按本次具体批准在sc7-27-feedback-guard-1115串行构建 |
| `sc7-27-feedback-guard-1115` | 采购 | refinement | archive | 10/10 | #670；LAN5/UI1及741测试/225源hash/5186真实只读调用/三Excel与audit已验收，采购28正文Word及四链已发；归档`openspec/changes/archive/2026-11-15-sc7-27-feedback-guard-1115/`、主spec已同步；本封通知ff例外，无产品Git或专业代签 |
| `aibot-inbound-whitelist-li-jiaolong` | 机制/平台 | refinement | blocked_external | 17/21 | 李姣龙首触发、真实回复与人在场验证；#380、#379、#70 |
| `aibot-outbox-relay` | 机制/平台 | feature | frozen_by_prd | 41/47 | 自 2026-09-15 起无该包提交或未提交改动，达到 60 天冻结线；#394、#361、#282 |
| `aibot-queue-sync-checkout-guard` | 机制/平台 | feature | frozen_by_prd | 10/13 | 自 2026-09-15 起无该包提交或未提交改动，达到 60 天冻结线；#287、#280、#281 |
| aibot-receipt-route-by-source-group | 机制/平台 | refinement | frozen_by_prd | 32/37 | 自 2026-09-15 起无该包提交或未提交改动，达到 60 天冻结线；#387、#279、#385  #387已销号（06:34本人核收一条）；同车#380等仍按原闸。；本发布候选保留基线版本，不移植业务实施/结案，不改变原任务现态。 |
| `audit-retention-archive` | 机制/平台 | feature | frozen_by_prd | 0/37 | 自 2026-09-15 起无该包提交或未提交改动，达到 60 天冻结线；#358、#126 |
| `batch-registration-precheck` | 机制/平台 | feature | frozen_by_prd | 24/26 | 自 2026-09-15 起无该包提交或未提交改动，达到 60 天冻结线；#381 |
| `cc-hooks-p3` | 机制/平台 | feature | frozen_by_prd | 43/53 | 四态复核2026-11-15；#561；包完整内容指纹见原triage报告，变化重报；自 2026-09-15 起无该包提交或未提交改动，达到 60 天冻结线 |
| `ci-junit-648` | 机制/平台 | feature | frozen_by_prd | 0/21 | 包内已有暂不归档/观察窗口声明，当前暂缓推进；#648 |
| `ci-junit-review-fix-648` | 机制/平台 | feature | frozen_by_prd | 0/14 | 包内已有暂不归档/观察窗口声明，当前暂缓推进；#648 |
| `claude-progress-section-lint` | 机制/平台 | feature | frozen_by_prd | 78/86 | 四态复核2026-11-15；#561；包完整内容指纹见原triage报告，变化重报；自 2026-09-15 起无该包提交或未提交改动，达到 60 天冻结线 |
| `codex-business-entry-closure-0930` | 机制/平台 | feature | active_mvp | 8/17 | 本轮有近期提交或既有未提交工作，保留在建位；未勾项仍须逐项完成；#648 |
| `codex-mechanism-migration` | 机制/平台 | feature | frozen_by_prd | 15/15 | 包内已有暂不归档/观察窗口声明，当前暂缓推进；#648 |
| `coverage-point-ledger` | 机制/平台 | feature | active_mvp | 14/34 | 本轮有近期提交或既有未提交工作，保留在建位；未勾项仍须逐项完成；#114、#343、#59 |
| `criteria-signoff-platform` | 机制/平台 | feature | frozen_by_prd | 27/31 | 四态复核2026-11-15；#561；包完整内容指纹见原triage报告，变化重报；包内已有暂不归档/观察窗口声明，当前暂缓推进 |
| `discipline-eval-suite` | 机制/平台 | feature | active_mvp | 26/50 | 本轮有近期提交或既有未提交工作，保留在建位；未勾项仍须逐项完成；#440、#438、#308 |
| `editlock-aibot-registration-completeness-exemption` | 机制/平台 | refinement | frozen_by_prd | 19/21 | 自 2026-09-15 起无该包提交或未提交改动，达到 60 天冻结线；#416、#333 |
| `editlock-append-row-highwater-writeback` | 机制/平台 | refinement | frozen_by_prd | 28/29 | 自 2026-09-15 起无该包提交或未提交改动，达到 60 天冻结线；#505、#169、#170 |
| `editlock-hold-scope-and-wip-block` | 机制/平台 | refinement | frozen_by_prd | 33/34 | 四态复核2026-11-15；#561；包完整内容指纹见原triage报告，变化重报；自 2026-09-15 起无该包提交或未提交改动，达到 60 天冻结线 |
| `editlock-waiver-time-scoped` | 机制/平台 | feature | frozen_by_prd | 52/56 | 四态复核2026-11-15；#561；包完整内容指纹见原triage报告，变化重报；自 2026-09-15 起无该包提交或未提交改动，达到 60 天冻结线 |
| `editlock-write-column-integrity` | 机制/平台 | feature | frozen_by_prd | 0/34 | 自 2026-09-15 起无该包提交或未提交改动，达到 60 天冻结线；#455、#324、#454 |
| `editlock-write-guard-hardening` | 机制/平台 | feature | frozen_by_prd | 30/33 | 自 2026-09-15 起无该包提交或未提交改动，达到 60 天冻结线；#455、#306、#307 |
| `editlock-write-side-date-guard` | 机制/平台 | feature | frozen_by_prd | 0/31 | 自 2026-09-15 起无该包提交或未提交改动，达到 60 天冻结线；#381、#58、#322 |
| `fi1-warehouse-reconcile` | 财务 | feature | frozen_by_prd | 28/40 | 近期有历史活动，但本轮未有核实的在建写方；按 WIP 容量暂缓；#196 |
| `fi10-inventory-writedown-mvp` | 财务 | feature | frozen_by_prd | 34/55 | 包内已有暂不归档/观察窗口声明，当前暂缓推进；#474、#463、#475 |
| `fi11-project-budget-evidence-pc-mock` | 财务 | feature | blocked_external | 4/5 | 本地技术片已完成；剩余真实源、业务签认、发布或权限闸见 tasks 未勾项 |
| `fi12-budget-version-evidence-pc-mock` | 财务 | feature | blocked_external | 4/5 | 本地技术片已完成；剩余真实源、业务签认、发布或权限闸见 tasks 未勾项 |
| `fi13-policy-evidence-pc-mock` | 财务 | feature | blocked_external | 4/5 | 本地技术片已完成；剩余真实源、业务签认、发布或权限闸见 tasks 未勾项 |
| `fi15-receivable-receipt-link-pc-mock` | 财务 | feature | blocked_external | 4/5 | 本地技术片已完成；剩余真实源、业务签认、发布或权限闸见 tasks 未勾项 |
| `fi16-intercompany-evidence-pc-mock` | 财务 | feature | blocked_external | 4/5 | 本地技术片已完成；剩余真实源、业务签认、发布或权限闸见 tasks 未勾项 |
| `fi2-recon-mvp` | 财务 | feature | frozen_by_prd | 123/129 | 四态复核2026-11-15；#561；包完整内容指纹见原triage报告，变化重报；自 2026-09-15 起无该包提交或未提交改动，达到 60 天冻结线 |
| `fi2-source-inversion` | 财务 | feature | frozen_by_prd | 0/58 | 自 2026-09-15 起无该包提交或未提交改动，达到 60 天冻结线；#372、#92、#59 |
| `fi3-payment-validation-mvp` | 财务 | feature | active_mvp | 25/37 | 本轮有近期提交或既有未提交工作，保留在建位；未勾项仍须逐项完成；#605、#603、#602 |
| `fi5-expense-audit-mvp` | 财务 | feature | frozen_by_prd | 15/44 | 近期有历史活动，但本轮未有核实的在建写方；按 WIP 容量暂缓；#470、#463、#16 |
| fi6-anomaly-detect-mvp | 财务 | feature | active_mvp | 19/45 | 本轮有近期提交或既有未提交工作，保留在建位；未勾项仍须逐项完成；#471、#463、#373；本发布候选保留基线版本，不移植业务实施/结案，不改变原任务现态。 |
| `fi7-catalog-intake-pc-mock` | 财务 | feature | blocked_external | 4/5 | 本地技术片已完成；剩余真实源、业务签认、发布或权限闸见 tasks 未勾项 |
| `fi7-nonproject-budget-evidence-pc-mock` | 财务 | feature | blocked_external | 4/5 | 本地技术片已完成；剩余真实源、业务签认、发布或权限闸见 tasks 未勾项 |
| `fi8-cashflow-forecast-mvp` | 财务 | feature | frozen_by_prd | 23/47 | 包内已有暂不归档/观察窗口声明，当前暂缓推进；#472、#463 |
| `fi9-rd-cost-mvp` | 财务 | feature | active_mvp | 21/51 | 本轮有近期提交或既有未提交工作，保留在建位；未勾项仍须逐项完成；#473、#463 |
| `finance-pc-trial-release` | 财务 | feature | frozen_by_prd | 8/11 | 包内已有暂不归档/观察窗口声明，当前暂缓推进；#569 |
| `followup-approval-cooldown-5min` | 机制/平台 | refinement | frozen_by_prd | 0/20 | 自 2026-09-15 起无该包提交或未提交改动，达到 60 天冻结线；#17 |
| `followup-closure-evidence-gate` | 机制/平台 | feature | frozen_by_prd | 0/42 | 自 2026-09-15 起无该包提交或未提交改动，达到 60 天冻结线；#366、#10、#19 |
| `followup-closure-form-survives-backfill` | 机制/平台 | feature | frozen_by_prd | 34/36 | 自 2026-09-15 起无该包提交或未提交改动，达到 60 天冻结线；#353、#241 |
| `followup-decision-point-gate` | 机制/平台 | refinement | frozen_by_prd | 12/27 | 近期有历史活动，但本轮未有核实的在建写方；按 WIP 容量暂缓；#436、#381 |
| `followup-letter-state-single-source` | 机制/平台 | feature | frozen_by_prd | 46/51 | 四态复核2026-11-15；#561；包完整内容指纹见原triage报告，变化重报；自 2026-09-15 起无该包提交或未提交改动，达到 60 天冻结线 |
| `followup-reply-pairing-latest-letter` | 机制/平台 | feature | frozen_by_prd | 31/34 | 四态复核2026-11-15；#561；包完整内容指纹见原triage报告，变化重报；自 2026-09-15 起无该包提交或未提交改动，达到 60 天冻结线 |
| `followup-serial-gate-hardening` | 机制/平台 | feature | blocked_external | 42/42 | 质量部#13 状态人裁、业务队列回写等外部事项；42/42 仅代表复选框完成；#482、#124、#90 |
| `followup-status-metadata-gates` | 机制/平台 | feature | frozen_by_prd | 19/34 | 自 2026-09-15 起无该包提交或未提交改动，达到 60 天冻结线；#447、#10、#439 |
| `followup-supplement-channel` | 机制/平台 | feature | frozen_by_prd | 33/35 | 自 2026-09-15 起无该包提交或未提交改动，达到 60 天冻结线；#399、#400、#18 |
| `lan-closeout-skill` | 机制/平台 | feature | frozen_by_prd | 5/8 | 自 2026-09-15 起无该包提交或未提交改动，达到 60 天冻结线；#138、#419、#354 |
| `lane-watch-deploy-extension` | 机制/平台 | feature | frozen_by_prd | 35/39 | 四态复核2026-11-15；#561；包完整内容指纹见原triage报告，变化重报；自 2026-09-15 起无该包提交或未提交改动，达到 60 天冻结线 |
| `lane-watch-heartbeat-visibility` | 机制/平台 | feature | frozen_by_prd | 30/34 | 四态复核2026-11-15；#561；包完整内容指纹见原triage报告，变化重报；自 2026-09-15 起无该包提交或未提交改动，达到 60 天冻结线 |
| `lane-watch-heartbeat-wiring` | 机制/平台 | feature | active_mvp | 27/33 | 本轮有近期提交或既有未提交工作，保留在建位；未勾项仍须逐项完成；#565、#550、#487 |
| `lane-watch-mode` | 机制/平台 | feature | frozen_by_prd | 22/30 | 自 2026-09-15 起无该包提交或未提交改动，达到 60 天冻结线；#452、#308、#328 |
| `lane-watch-notify-ops-default` | 机制/平台 | feature | active_mvp | 12/14 | 本轮有近期提交或既有未提交工作，保留在建位；未勾项仍须逐项完成；#492、#452、#284 |
| `mechanism-wip-staleness-gate` | 机制/平台 | refinement | frozen_by_prd | 29/34 | 四态复核2026-11-15；#561；包完整内容指纹见原triage报告，变化重报；自 2026-09-15 起无该包提交或未提交改动，达到 60 天冻结线 |
| `o4-single-class-maintenance` | 运营 | feature | frozen_by_prd | 11/21 | 包内已有暂不归档/观察窗口声明，当前暂缓推进 |
| `oem-audit-fail-closed` | 机制/平台 | refinement | frozen_by_prd | 27/28 | 四态复核2026-11-15；#561；包完整内容指纹见原triage报告，变化重报；近期有历史活动，但本轮未有核实的在建写方；按 WIP 容量暂缓 |
| `oem-chroma-ownership-rejudge` | 机制/平台 | refinement | frozen_by_prd | 30/35 | 包内已有暂不归档/观察窗口声明，当前暂缓推进；#374、#88、#328 |
| `oem-general-collections-readonly` | 机制/平台 | refinement | frozen_by_prd | 24/27 | 四态复核2026-11-15；#561；包完整内容指纹见原triage报告，变化重报；自 2026-09-15 起无该包提交或未提交改动，达到 60 天冻结线 |
| `open-pool-assigned-field-and-opener-env-filter` | 机制/平台 | feature | frozen_by_prd | 18/19 | 自 2026-09-15 起无该包提交或未提交改动，达到 60 天冻结线；#435、#312、#381 |
| `open-pool-reminder-dual-file-and-staleness` | 机制/平台 | feature | frozen_by_prd | 21/23 | 四态复核2026-11-15；#561；包完整内容指纹见原triage报告，变化重报；自 2026-09-15 起无该包提交或未提交改动，达到 60 天冻结线 |
| `open-pool-shared-criteria` | 机制/平台 | feature | frozen_by_prd | 13/17 | 自 2026-09-15 起无该包提交或未提交改动，达到 60 天冻结线；#312、#439、#440 |
| `opener-id-claim-semantics` | 机制/平台 | feature | frozen_by_prd | 21/23 | 四态复核2026-11-15；#561；包完整内容指纹见原triage报告，变化重报；自 2026-09-15 起无该包提交或未提交改动，达到 60 天冻结线 |
| `orchestration-guards` | 机制/平台 | feature | frozen_by_prd | 19/22 | 自 2026-09-15 起无该包提交或未提交改动，达到 60 天冻结线；#487 |
| `plan-backpressure-scanner` | 机制/平台 | feature | frozen_by_prd | 47/55 | 四态复核2026-11-15；#561；包完整内容指纹见原triage报告，变化重报；自 2026-09-15 起无该包提交或未提交改动，达到 60 天冻结线 |
| `portal-sc2-ui` | 采购 | feature | blocked_external | 6/7 | 本地技术片已完成；剩余真实源、业务签认、发布或权限闸见 tasks 未勾项；#538 |
| `portal-sc8-ui` | 采购 | feature | blocked_external | 6/7 | 本地技术片已完成；剩余真实源、业务签认、发布或权限闸见 tasks 未勾项；#538 |
| `procurement-ops-pc-mvp-1017` | 采购 | feature | active_mvp | 0/18 | 本轮有近期提交或既有未提交工作，保留在建位；未勾项仍须逐项完成 |
| `procurement-seven-mvp-closeout-1017` | 采购 | feature | frozen_by_prd | 0/8 | 包内已有暂不归档/观察窗口声明，当前暂缓推进；#667 |
| `project-hooks-write-time-sentinels` | 机制/平台 | feature | frozen_by_prd | 36/48 | 自 2026-09-15 起无该包提交或未提交改动，达到 60 天冻结线；#433、#398、#14 |
| `q2-8d-review-verdict-mvp` | 质量 | feature | active_mvp | 10/15 | 本轮有近期提交或既有未提交工作，保留在建位；未勾项仍须逐项完成；#612、#328 |
| `q2-mock-upload-report-pc-1015` | 质量 | feature | frozen_by_prd | 12/13 | 包内已有暂不归档/观察窗口声明，当前暂缓推进；#612、#652、#661 |
| `q2-real-document-pc-1015` | 质量 | feature | active_mvp | 0/11 | 本轮有近期提交或既有未提交工作，保留在建位；未勾项仍须逐项完成；#612、#652、#656 |
| `qd-b-cross-module-tier3` | 质量 | refinement | frozen_by_prd | 30/31 | 包内已有暂不归档/观察窗口声明，当前暂缓推进；#340、#112、#83 |
| `queue-domain-routing` | 机制/平台 | refinement | frozen_by_prd | 19/21 | 四态复核2026-11-15；#561；包完整内容指纹见原triage报告，变化重报；自 2026-09-15 起无该包提交或未提交改动，达到 60 天冻结线 |
| `queue-domain-strict-routing` | 机制/平台 | refinement | frozen_by_prd | 8/25 | 自 2026-09-15 起无该包提交或未提交改动，达到 60 天冻结线；#341、#336、#328 |
| `queue-lint-appellation-guard` | 机制/平台 | feature | frozen_by_prd | 28/34 | 自 2026-09-15 起无该包提交或未提交改动，达到 60 天冻结线；#352、#345、#392 |
| `queue-lint-restate-package-progress` | 机制/平台 | feature | frozen_by_prd | 8/32 | 自 2026-09-15 起无该包提交或未提交改动，达到 60 天冻结线；#456、#439、#452 |
| `queue-read-write-guards` | 机制/平台 | feature | frozen_by_prd | 27/33 | 四态复核2026-11-15；#561；包完整内容指纹见原triage报告，变化重报；自 2026-09-15 起无该包提交或未提交改动，达到 60 天冻结线 |
| `queue-reserve-unfilled-release` | 机制/平台 | refinement | frozen_by_prd | 0/51 | 自 2026-09-15 起无该包提交或未提交改动，达到 60 天冻结线；#487、#480、#498 |
| `queue-row-blocker-field` | 机制/平台 | feature | frozen_by_prd | 0/33 | 自 2026-09-15 起无该包提交或未提交改动，达到 60 天冻结线；#435、#142、#312 |
| `recovery-input-261` | 机制/平台 | feature | active_mvp | 0/9 | 本轮有近期提交或既有未提交工作，保留在建位；未勾项仍须逐项完成；#261、#658、#634 |
| `review-approval-context-648` | 机制/平台 | feature | frozen_by_prd | 0/22 | 包内已有暂不归档/观察窗口声明，当前暂缓推进；#648 |
| `sc10-bom-review-material-governance` | 采购 | feature | frozen_by_prd | 17/36 | 包内已有暂不归档/观察窗口声明，当前暂缓推进；#468、#470、#474 |
| `sc11-inventory-transfer` | 采购 | feature | frozen_by_prd | 22/42 | 包内已有暂不归档/观察窗口声明，当前暂缓推进；#469、#470、#474 |
| `sc2-autopush-friday` | 采购 | refinement | frozen_by_prd | 30/33 | 四态复核2026-11-15；#561；包完整内容指纹见原triage报告，变化重报；自 2026-09-15 起无该包提交或未提交改动，达到 60 天冻结线 |
| `sc2-biztype316-receipts` | 采购 | feature | frozen_by_prd | 15/26 | 包内已有暂不归档/观察窗口声明，当前暂缓推进；#667、#654、#538 |
| `sc2-procurement-monitor-v24` | 采购 | feature | active_mvp | 0/15 | 本轮有近期提交或既有未提交工作，保留在建位；未勾项仍须逐项完成 |
| `sc4-contract-clause-extraction` | 采购 | feature | frozen_by_prd | 17/34 | 包内已有暂不归档/观察窗口声明，当前暂缓推进；#467、#463 |
| `sc7-batch-quantity-mapping` | 采购 | feature | frozen_by_prd | 7/10 | 包内已有暂不归档/观察窗口声明，当前暂缓推进；#125、#403 |
| `sc8-atp-batch2-closeout` | 采购 | refinement | frozen_by_prd | 11/72 | 包内已有暂不归档/观察窗口声明，当前暂缓推进；#118、#14、#65 |
| `sc8-kit-date-rule1-start` | 采购 | refinement | active_mvp | 32/37 | 本轮有近期提交或既有未提交工作，保留在建位；未勾项仍须逐项完成；#401、#15、#344 |
| `sc8-material-board-view` | 采购 | feature | blocked_external | 35/37 | 四态复核2026-11-15；#334/#561；包完整内容指纹见原triage报告，变化重报；姚祖怡串行闸及 SC2 判例包前置，跟进信不得擅发 |
| `sc8-real-producer-portal-bridge` | 采购 | feature | active_mvp | 22/24 | 本轮有近期提交或既有未提交工作，保留在建位；未勾项仍须逐项完成；#349、#350、#27 |
| `single-guarded-copy` | 机制/平台 | feature | frozen_by_prd | 1/33 | 近期有历史活动，但本轮未有核实的在建写方；按 WIP 容量暂缓；#503 |
| status-triage-resident-round | 机制/平台 | feature | frozen_by_prd | 34/36 | 近期有历史活动，但本轮未有核实的在建写方；按 WIP 容量暂缓；#454、#394、#326；本发布候选保留基线版本，不移植业务实施/结案，不改变原任务现态。 |
| `sweep-manifest-scoped-stage` | 机制/平台 | feature | frozen_by_prd | 34/38 | 四态复核2026-11-15；#561；包完整内容指纹见原triage报告，变化重报；自 2026-09-15 起无该包提交或未提交改动，达到 60 天冻结线 |
| `sweep-startup-nonblocking` | 机制/平台 | refinement | frozen_by_prd | 25/26 | 四态复核2026-11-15；#561；包完整内容指纹见原triage报告，变化重报；自 2026-09-15 起无该包提交或未提交改动，达到 60 天冻结线 |
| `tasks-zombie-item-detect` | 机制/平台 | feature | frozen_by_prd | 20/24 | 四态复核2026-11-15；#561；包完整内容指纹见原triage报告，变化重报；自 2026-09-15 起无该包提交或未提交改动，达到 60 天冻结线 |
| unified-docx-checkbox-reader | 机制/平台 | feature | frozen_by_prd | 28/31 | #481/#133；2026-11-15八文件master同内容/平台646pass；原行政前置已补，主spec同步并归档，无ff/业务变更；本发布候选保留基线版本，不移植业务实施/结案，不改变原任务现态。 |
| `wecom-listener-macos-migration` | 机制/平台 | feature | frozen_by_prd | 7/37 | 自 2026-09-15 起无该包提交或未提交改动，达到 60 天冻结线；#90、#196、#69 |
| `workflow-context-ci-gate-fix-op-0929-x-v2` | 机制/平台 | feature | frozen_by_prd | 0/15 | 包内已有暂不归档/观察窗口声明，当前暂缓推进；#648 |
| `workflow-context-continuation-op-0929-x-v3` | 机制/平台 | feature | frozen_by_prd | 0/13 | 包内已有暂不归档/观察窗口声明，当前暂缓推进；#648 |
| `workflow-mvp-closure-0930` | 机制/平台 | feature | frozen_by_prd | 0/14 | 包内已有暂不归档/观察窗口声明，当前暂缓推进；#648 |

当前表二登记计数（含归档记录）：archive 6；blocked_external 13；frozen_by_prd 77；active_mvp 15。冻结包保留原文件，仅退出活跃池。

逐包本地未完项与外部卡点分账见 `reports/openspec-triage-20261113.json`。本表的状态是需求池与 WIP 管理结果，不授予真实源、ff、生产、外发或专业签认权限。

## 表三：全景规划与原队列承接

与registry/权威总览排期同源；这里只登记原任务与需求验收边界，不声明业务已达标。表一覆盖主规格/测试，实际构建仍逐包check-acceptance和完整pytest。O2现有规格/项目的原真实源/v2尾项已补#714追溯承接，不虚构新增业务需求或派业务建造。

| 场景ID | 部门/域 | 权威排期 | 原队列/暂缓依据 | 构建与验收边界 |
|---|---|---|---|---|
| SC1 | 采购 | 2026-07 | #699 | 需求/专业/真实与发布验收沿原任务，不以规格存在代完成 |
| SC2 | 采购 | 2026-08 | #654/#667/#538/#499 | 需求/专业/真实与发布验收沿原任务，不以规格存在代完成 |
| SC4 | 采购 | 2026-11 | #467 | 本月份不构成承诺；实际启动＝前置到位＋8天；需求/专业/真实与发布验收沿原任务，不以规格存在代完成 |
| SC7 | 采购 | 2026-09／2027-01 | #670 | 1115KH-LAN-4技术实交702pass，六仓/GR/单位已齐；仅发货计划/调入期间源、专业验收及已列具体增量留#670；采购27收件闭环与业务验收分账 |
| SC8 | 采购 | 2026-07 | #660/#671/#118 | 需求/专业/真实与发布验收沿原任务，不以规格存在代完成 |
| SC10 | 采购 | 2027-03 | #468 | 本月份不构成承诺；实际启动＝前置到位＋8天；需求/专业/真实与发布验收沿原任务，不以规格存在代完成 |
| SC11 | 采购 | 2027-04 | #469 | 本月份不构成承诺；实际启动＝前置到位＋8天；需求/专业/真实与发布验收沿原任务，不以规格存在代完成 |
| O1 | 运营 | 2026-09 | #403 | 需求/专业/真实与发布验收沿原任务，不以规格存在代完成 |
| O2 | 运营 | 2026-09 | #714 | 既有mock与真实源/v2留步分账；仅补原未完项，真实/专业/发布待核，不新增业务授权 |
| O3 | 运营 | 2026-10 | #508 | 需求/专业/真实与发布验收沿原任务，不以规格存在代完成 |
| O4 | 运营 | 2027-01 | #509 | 需求/专业/真实与发布验收沿原任务，不以规格存在代完成 |
| R1 | 工程研发 | 2027-07 | #463 | 研发域暂缓·Shao Peishen 2026-09-02 明令「研发和销售域场景依然暂缓等我通知再排序」（来源 #463，2026-09-02）；仅规划承接，不恢复业务 |
| R2 | 工程研发 | 2027-08 | #463 | 研发域暂缓·Shao Peishen 2026-09-02 明令（来源 #463，2026-09-02）；仅规划承接，不恢复业务 |
| R3 | 工程研发 | 2027-09 | #463 | 研发域暂缓·Shao Peishen 2026-09-02 明令（来源 #463，2026-09-02）；仅规划承接，不恢复业务 |
| R4 | 工程研发 | 2027-10 | #463 | 研发域暂缓·Shao Peishen 2026-09-02 明令（来源 #463，2026-09-02）；仅规划承接，不恢复业务 |
| R5 | 工程研发 | 2027-11 | #463 | 研发域暂缓·Shao Peishen 2026-09-02 明令（来源 #463，2026-09-02）；仅规划承接，不恢复业务 |
| Q2 | 质量 | 2026-10 | #612/#652 | 需求/专业/真实与发布验收沿原任务，不以规格存在代完成 |
| Q4 | 质量 | 2027-04 | #510 | 需求/专业/真实与发布验收沿原任务，不以规格存在代完成 |
| Q6 | 质量 | 2026-10 | #340 | 需求/专业/真实与发布验收沿原任务，不以规格存在代完成 |
| FI1 | 财务 | 暂缓（2026-07-06 财务域 v2） | #698/#403 | 原条件复启暂缓保留；#698不解除FI1暂停 |
| FI2 | 财务 | 2026-09 | #657/#390 | 需求/专业/真实与发布验收沿原任务，不以规格存在代完成 |
| FI3 | 财务 | 2026-09 | #613/#615 | 需求/专业/真实与发布验收沿原任务，不以规格存在代完成 |
| FI4 | 财务 | 2026-11 | #511 | 需求/专业/真实与发布验收沿原任务，不以规格存在代完成 |
| FI5 | 财务 | 2026-10 | #470 | 需求/专业/真实与发布验收沿原任务，不以规格存在代完成 |
| FI6 | 财务 | 2026-10 | #471 | 需求/专业/真实与发布验收沿原任务，不以规格存在代完成 |
| FI7 | 财务 | 2026-12 | #512 | 需求/专业/真实与发布验收沿原任务，不以规格存在代完成 |
| FI8 | 财务 | 2026-11 | #472 | 需求/专业/真实与发布验收沿原任务，不以规格存在代完成 |
| FI9 | 财务 | 2027-06 | #473 | 本月份不构成承诺；实际启动＝前置到位＋8天；需求/专业/真实与发布验收沿原任务，不以规格存在代完成 |
| FI10 | 财务 | 2026-11 | #474 | 需求/专业/真实与发布验收沿原任务，不以规格存在代完成 |
| S1 | 销售 | 2027-07 | #463 | 销售域暂缓·Shao Peishen 2026-09-02 明令「研发和销售域场景依然暂缓等我通知再排序」（来源 #463，2026-09-02）；仅规划承接，不恢复业务 |
| S2 | 销售 | 2027-08 | #463 | 销售域暂缓·Shao Peishen 2026-09-02 明令（来源 #463，2026-09-02）；仅规划承接，不恢复业务 |
| S3 | 销售 | 2027-09 | #463 | 销售域暂缓·Shao Peishen 2026-09-02 明令（来源 #463，2026-09-02）；仅规划承接，不恢复业务 |
| S4 | 销售 | 2027-10 | #463 | 销售域暂缓·Shao Peishen 2026-09-02 明令（来源 #463，2026-09-02）；仅规划承接，不恢复业务 |
| S5 | 销售 | 2027-11 | #463 | 销售域暂缓·Shao Peishen 2026-09-02 明令（来源 #463，2026-09-02）；仅规划承接，不恢复业务 |
| S6 | 销售 | 2027-12 | #463 | 销售域暂缓·Shao Peishen 2026-09-02 明令（来源 #463，2026-09-02）；仅规划承接，不恢复业务 |

域PRD增量继续由原财务队列承接（不反改总纲排期）：FI11/FI12/FI13/FI15/FI16→#698，FI14→#678/#698；表一保留对应spec/pytest，实际业务验收逐包守原闸。
