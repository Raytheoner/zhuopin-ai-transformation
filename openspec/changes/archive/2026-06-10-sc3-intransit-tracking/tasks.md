## 1. 分支与脚手架

- [x] 1.1 新建分支 `feat/sc3-intransit-tracking`
- [x] 1.2 创建 `4-数字员工/采购部/SC3-供应商在途跟踪与绩效/` 目录结构（pyproject.toml + sc3_intransit/ + tests/）
- [x] 1.3 编写 `pyproject.toml`（依赖 zhuopin_platform，对齐 O2 模式）
- [x] 1.4 `pip install -e ../../../5-平台底座/zhuopin_platform && pip install -e .` 验证安装成功

## 2. compute_dos 放置（待 Paul 拍板 D2 后执行）

- [x] 2.1 【A路线】将 compute_dos 放入 `sc3_intransit/intransit_engine.py` 场景本地
- [ ] 2.1 【B路线】在底座新建 `zhuopin_platform/shared_tools/supply_metrics.py`，export compute_dos；更新 O2 的 import；底座 tests 全绿

## 3. mock CSV Fixture

- [x] 3.1 从 supplychain/data/mock/logistics/ 复制 purchase_orders.csv / inventory.csv / bom.csv / production_plan.csv 到 `tests/mock_data/`
- [x] 3.2 验证列名与平台 csv_connector 期望一致（如有差异修正 CSV，不改引擎）

## 4. 先写测试（TDD，测试先于实现）

- [x] 4.1 编写 `test_intransit_engine.py`：三色分级逻辑（high/medium/low 各边界值）
- [x] 4.2 编写等价对照用例：与 supplychain test_supplier_tracking.py 的 Golden Baseline 场景等价（PO-001 逾期→high, PO-002 4天→medium, PO-003 21天→low, PO-004 双触发→high, PO-005 7天→medium, PO-006 received→跳过，总数5笔，排序 high→medium→low）
- [x] 4.3 编写 srm_dates 覆盖测试（PO-001 延后到6月→变low）
- [x] 4.4 编写 `test_sc3_agent.py`：agent 执行后 audit JSONL 有 SC3 事件，details 字段含风险计数

## 5. 引擎实现

- [x] 5.1 在 `sc3_intransit/intransit_engine.py` 实现 `SupplierRisk` + `_classify_risk` + `analyze`（原样收割，不重写）
- [x] 5.2 按 D2 决策放置 `compute_dos`（场景本地，D2=A）
- [x] 5.3 确认无任何 `from supplychain` / `sys.path` 残留

## 6. Agent 实现

- [x] 6.1 在 `sc3_intransit/agent.py` 实现 `run_sc3(mock_dir, today)` 调用引擎
- [x] 6.2 写 audit：scenario=SC3, action=in_transit_risk_eval, automation_level=L1, details 含风险计数
- [x] 6.3 添加 `__main__` 入口，可命令行快速验证（`python -m sc3_intransit.agent`）

## 7. 验证与收尾

- [x] 7.1 `pytest tests/ -v` 全绿，含等价对照用例
- [x] 7.2 检查 import：`grep -r "supplychain\|sys.path" sc3_intransit/ tests/`，确认零残留
- [x] 7.3 验证 audit JSONL 有实际写入（cat 审计文件，确认 SC3 事件存在）
- [x] 7.4 `/opsx:archive` 更新 tasks 状态
- [ ] 7.5 `git add` + `git commit` + `git push`
