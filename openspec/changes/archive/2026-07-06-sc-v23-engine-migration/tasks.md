## 1. SC7 场景工程骨架（新场景，先建骨架再搬内容）

- [x] 1.1 新建 `4-数字员工/采购部/SC7-库存优化建议/` 目录 + `pyproject.toml`（project name `sc7-inventory-optimization`，package `sc7_inventory*`，testpaths=tests，同 SC5 依赖 `zhuopin_platform`）
- [x] 1.2 新建 `sc7_inventory/__init__.py`
- [x] 1.3 新建 `tests/__init__.py` + `tests/mock_data/`（从 SC5 `tests/mock_data/*.csv` 复制：bom/inventory/production_plan/purchase_orders/suppliers）

## 2. SC5 引擎搬入 SC7（只搬移不重写）

- [x] 2.1 复制 `sc5_purchase/business_rules.py` → `sc7_inventory/business_rules.py`（内容不变，仅模块 docstring 补一行迁移出处）
- [x] 2.2 复制 `sc5_purchase/purchase_engine.py` → `sc7_inventory/purchase_engine.py`，import 改 `from sc5_purchase.business_rules import` → `from sc7_inventory.business_rules import`，逻辑不变
- [x] 2.3 复制 `sc5_purchase/agent.py` → `sc7_inventory/agent.py`：import 改 `sc5_purchase.*` → `sc7_inventory.*`；函数 `run_sc5` 改名 `run_sc7`；audit `scenario="SC5"` 改 `scenario="SC7"`；`__main__` 块路径与函数名同步更新
- [x] 2.4 复制 `tests/test_purchase_engine.py` → SC7 `tests/test_purchase_engine.py`，import 改 `sc5_purchase.*` → `sc7_inventory.*`，测试断言（含黄金基准 35850/640000/675850）逐字不变
- [x] 2.5 复制 `tests/test_sc5_agent.py` → SC7 `tests/test_sc7_agent.py`，import/函数名改 `run_sc5`→`run_sc7`，audit 断言 `scenario == "SC5"` 改 `scenario == "SC7"`，其余断言不变
- [x] 2.6 `pip install -e "4-数字员工/采购部/SC7-库存优化建议"`，`cd` 进该目录跑 `pytest -q`，41 个测试（含黄金基准三项）全绿

## 3. SC3 引擎搬入 SC8（内部子模块，不接线）

- [x] 3.1 复制 `sc3_intransit/intransit_engine.py` → `4-数字员工/采购部/SC8-客户订单交期智能承诺/sc8/answer_confidence_engine.py`（内容不变，仅模块 docstring 补一行迁移出处 + 说明"尚未接入 SC8 现有置信度流水线"）
- [x] 3.2 复制 `sc3_intransit/agent.py` → SC8 `sc8/answer_confidence.py`：import 改 `.intransit_engine` → `.answer_confidence_engine`；函数 `run_sc3` 改名 `run_answer_confidence`；audit `scenario="SC3"` 改 `scenario="SC8"`；默认 audit 路径改为 `Path(__file__).resolve().parents[1] / "reports" / "answer_confidence_audit.jsonl"`（原 SC3 版本的 parents 层级是按其自身目录深度算的，直接照搬到 SC8 目录会指错路径，需按新位置重新计算——这不是逻辑变更，是路径挂载点必须跟着物理位置调整）
- [x] 3.3 新建 SC8 `tests/mock_data_answer_confidence/`，复制 SC3 `tests/mock_data/*.csv`（bom/inventory/production_plan/purchase_orders，SC3 无 suppliers.csv 故不涉及）
- [x] 3.4 复制 `tests/test_intransit_engine.py` → SC8 `tests/test_answer_confidence_engine.py`，import 改 `sc3_intransit.intransit_engine` → `sc8.answer_confidence_engine`，`MOCK_DIR` 指向 `mock_data_answer_confidence`，断言逐字不变
- [x] 3.5 复制 `tests/test_sc3_agent.py` → SC8 `tests/test_answer_confidence_agent.py`，import/函数名改 `run_sc3`→`run_answer_confidence`，`MOCK_DIR` 指向 `mock_data_answer_confidence`，audit 断言 `event["scenario"] == "SC3"` 改 `"SC8"`，其余断言（total_pos/high_count 等）不变
- [x] 3.6 SC8 目录下跑 `pytest -q`，确认新增 answer_confidence 相关测试（原 29 个）全绿，且 SC8 既有测试（commitment/forecast/baoguan 等）零回归——**不触碰 `sc8-real-data-cutover` 变更包涉及的文件**

## 4. 旧场景目录清空为 README 指针 + 环境卸载

- [x] 4.1 `4-数字员工/采购部/SC3-供应商在途跟踪与绩效/` 删除 `sc3_intransit/`、`tests/`、`pyproject.toml`、egg-info、`.pytest_cache`，只留 `README.md`（指向 SC8 `sc8/answer_confidence*.py` + 本变更包路径）；CLAUDE.md 改写为退役说明（保留六段式但内容改为"已并入 SC8"）
- [x] 4.2 `4-数字员工/采购部/SC5-采购建议与供应商遴选/` 同上处理（README 指向 SC7 `sc7_inventory/` + 本变更包路径），CLAUDE.md 改写为退役说明
- [x] 4.3 `pip uninstall sc3-intransit-tracking sc5-purchase-recommendation -y`
- [x] 4.4 `pip list | grep -i "sc3\|sc5\|sc7\|sc8"` 确认环境状态：sc3/sc5 已卸载，sc7 已装，sc8 仍是原 editable（新增文件自动生效，无需重装）

## 5. SC8/SC7 场景 CLAUDE.md 六段式更新

- [x] 5.1 SC8 CLAUDE.md：§3（复用底座资产）补一条"答交可信度子模块（迁自 SC3）"；§5（状态时间线）加 2026-07-06 迁移记录；§6（依赖）补"答交可信度接入置信度 2→3 级化——随 SC8 深化，独立后续任务"
- [x] 5.2 新建 SC7 CLAUDE.md（六段式：定位/决策/底座/红线/时间线/依赖），定位写明"承接原 SC5 采购建议/遴选功能 + v2.3 未来深化（动态安全库存等，2027-01 二期）"，决策记录原样迁移 SC5 的黄金基准/L2 门禁裁决，红线延续 R1≥50万/R2 无认证供应商门禁

## 6. 全量回归 + 收尾

- [x] 6.1 全仓 grep `sc3_intransit|sc5_purchase` 确认零残留（历史 openspec archive 文档除外，按项目惯例不回溯改写）
- [x] 6.2 SC7 目录 `pytest -q`：41 passed；SC8 目录 `pytest -q`：全绿（原有 + 新增 answer_confidence 测试）
- [x] 6.3 `openspec archive` 落盘 `openspec/specs/`：新增 4 个 capability（sc7-purchase-engine/agent、sc8-answer-confidence-engine/agent）；4 个退役 capability（sc3-intransit-\*/sc5-purchase-\*）因 CLI 不支持"REMOVE 全部 requirement"改为归档后手工删除对应 `openspec/specs/` 目录（见 proposal.md 实现说明）
- [x] 6.4 `git add` 变更（含新增 SC7 目录、SC8 新文件、SC3/SC5 清空后的 README、openspec 变更包），commit `8d8bde7`（未纳入本会话另一处非本变更包产生的未提交改动 `1-转型规划/session接力-财务域场景落地.md`）
- [x] 6.5 `/opsx:archive sc-v23-engine-migration -y`（完工即归档纪律，不拖延）——归档至 `openspec/changes/archive/2026-07-06-sc-v23-engine-migration/`
- [x] 6.6 更新 `session接力-Phase1收口.md`：C 段完成状态回填
