## 1. 分支与准备

- [x] 1.1 新建分支 `feat/sc5-purchase-recommendation`
- [x] 1.2 确认底座 `zhuopin_platform/agents/` 目录已存在（有骨架 `__init__.py`）

## 2. 底座：kit_engine 提升（先于 SC5，O2 回归必须全绿再继续）

- [x] 2.1 在 `zhuopin_platform/agents/kit_engine.py` 新建文件，从 O2 `o2_kit_shortage/kit_engine.py` 原样搬移 explode_bom + calc_shortage（import 改为底座 models）
- [x] 2.2 在 `5-平台底座/zhuopin_platform/tests/test_kit_engine.py` 新增底座单测（explode_bom 展开 + calc_shortage 缺口 + 防循环引用）18 tests
- [x] 2.3 底座 tests 全绿（`pytest` 在 zhuopin_platform 目录跑）114 passed
- [x] 2.4 O2 `o2_kit_shortage/kit_engine.py` 改为从底座 import（薄转发）
- [x] 2.5 O2 tests 全绿（`pytest` 在 O2 目录跑），确认回归零变更 20 passed

## 3. SC5 脚手架

- [x] 3.1 创建 `4-数字员工/采购部/SC5-采购建议与供应商遴选/` 目录结构（pyproject.toml + sc5_purchase/ + tests/）
- [x] 3.2 编写 `pyproject.toml`（依赖 zhuopin_platform，对齐 O2/SC3 模式）
- [x] 3.3 `pip install -e ../../../5-平台底座/zhuopin_platform && pip install -e .` 验证安装成功

## 4. mock CSV Fixture

- [x] 4.1 从 `supplychain/data/mock/`（主目录，非 logistics）复制 purchase_orders.csv / inventory.csv / bom.csv / production_plan.csv / suppliers.csv 到 `tests/mock_data/`
- [x] 4.2 验证列名与平台 csv_connector + csv_loaders 期望一致（已知一致，快速确认）

## 5. 先写测试（TDD）

- [x] 5.1 编写 `test_purchase_engine.py`：
    - TestCalcPurchaseQty：5 个 MOQ/MPQ 边界用例（对照 supplychain TestCalcPurchaseQty）
    - TestSelectSupplier：M002 选最低价 S001、M015 单一供应商
    - TestCalcOrderDate：M002（2026-05-10，lead=14→2026-04-23）、M015（2026-05-15，lead=60→2026-03-13）
    - TestBusinessRulePolicy：R1 金额触发、R2 无认证供应商触发、可自动下单
- [x] 5.2 编写等价对照用例（Golden Baseline）：端到端 pipeline → 5 条建议 / auto_total≈35850 / review_total≈640000 / M015 在审核桶 / M002 选 S001 自动下单
- [x] 5.3 编写无认证供应商场景测试（等价 supplychain TestUnapprovedSupplierScenario）
- [x] 5.4 编写 `test_sc5_agent.py`：audit JSONL 有 SC5 事件，L1 事件含 auto_count，L2 事件含 review_count + human_required=True

## 6. 引擎实现

- [x] 6.1 在 `sc5_purchase/business_rules.py` 实现 BusinessRulePolicy（R1/R2，原样收割）
- [x] 6.2 在 `sc5_purchase/purchase_engine.py` 实现 build_recommendations + select_supplier + calc_purchase_qty + calc_order_date + calc_material_earliest_dates（原样收割，import 改底座 models + kit_engine）
- [x] 6.3 确认无任何 `from supplychain` / `sys.path` 残留

## 7. Agent 实现

- [x] 7.1 在 `sc5_purchase/agent.py` 实现 `run_sc5(mock_dir, today)` 调用引擎
- [x] 7.2 L1/L2 分桶写 audit：两条事件或一条含分桶摘要；L2 含 human_required=True，ensure_ascii=False
- [x] 7.3 添加 `__main__` 入口，可命令行验证

## 8. 验证与收尾

- [x] 8.1 `pytest tests/ -v` 全绿（SC5 自身）41 passed
- [x] 8.2 确认底座 + O2 tests 仍全绿（三套 pytest 全绿：底座 114 + O2 20 + SC5 41 = 175 passed）
- [x] 8.3 `grep -r "supplychain\|sys.path" sc5_purchase/ tests/` 确认零残留（仅注释引用）
- [x] 8.4 验证 audit JSONL 有实际写入（L1: auto_count=4/auto_total=35850; L2: review_count=1/human_required=True/R1_amount_threshold）
- [ ] 8.5 `/opsx:archive` 更新 tasks 状态
- [ ] 8.6 `git add` + `git commit` + `git push`
