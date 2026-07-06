# SC5 采购建议与供应商遴选 — 已退役（2026-07-06 v2.3 重排）

采购域 v2.3 场景重排（2026-07-06，见 `1-转型规划/0-全景路线图/采购域重排-移交全景路线图Task.md`）后，
**SC5 场景编号退役**，采购建议生成与供应商遴选能力原样迁移为新场景 SC7（库存优化建议）：

- 新家：`4-数字员工/采购部/SC7-库存优化建议/sc7_inventory/`（business_rules.py / purchase_engine.py / agent.py）
- 测试：`SC7-库存优化建议/tests/test_purchase_engine.py` + `test_sc7_agent.py`（原 41 tests 原样迁移，含黄金基准 auto_total=35850/review_total=640000/grand_total=675850 精确保留）
- `kit_engine`（`zhuopin_platform/agents/kit_engine.py`）不随本次迁移变动，SC7/O2/SC8 继续共同复用
- 迁移变更包：`openspec/changes/archive/2026-07-06-sc-v23-engine-migration/`（归档后路径）
- 迁移设计记录：见该变更包 `design.md` 决策 2/3

本目录只保留本 README 与 `CLAUDE.md`（已改写为退役说明），源码/测试/pyproject 已移除。
历史沿革见本目录 `CLAUDE.md` 与 `openspec/changes/archive/2026-07-02-sc5-purchase-recommendation/`。
