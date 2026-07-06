# SC3 供应商在途跟踪与绩效 — 已退役（2026-07-06 v2.3 重排）

采购域 v2.3 场景重排（2026-07-06，见 `1-转型规划/0-全景路线图/采购域重排-移交全景路线图Task.md`）后，
**SC3 场景编号退役**，答交可信度评分能力原样迁移为 SC8 内部子模块：

- 新家：`4-数字员工/采购部/SC8-客户订单交期智能承诺/sc8/answer_confidence_engine.py` + `sc8/answer_confidence.py`
- 测试：`SC8-客户订单交期智能承诺/tests/test_answer_confidence_engine.py` + `test_answer_confidence_agent.py`（原 29 tests 原样迁移，逐一对应）
- 迁移变更包：`openspec/changes/archive/2026-07-06-sc-v23-engine-migration/`（归档后路径）
- 迁移设计记录：见该变更包 `design.md` 决策 1/3

本目录只保留本 README 与 `CLAUDE.md`（已改写为退役说明），源码/测试/pyproject 已移除。
历史沿革见本目录 `CLAUDE.md` 与 `openspec/changes/archive/2026-06-10-sc3-intransit-tracking/`。
