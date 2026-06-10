## 1. 基础准备

- [x] 1.1 新建 git 分支 feat/o2-kit-shortage-alert
- [x] 1.2 创建场景目录 `4-数字员工/运营部/O2-物料齐套预警/` 及 Python 包结构（pyproject.toml / o2_kit_shortage/__init__.py）
- [x] 1.3 确认 `pip install -e` 平台底座可正常 import `zhuopin_platform.shared_tools.models` 与 `zhuopin_platform.audit`

## 2. 先写测试（SuperPowers 先测后实现）

- [x] 2.1 写 `tests/test_kit_engine.py`：覆盖 explode_bom 单层/多层/多成品合并/循环引用四个场景
- [x] 2.2 写 `tests/test_kit_shortage.py`：覆盖 calc_shortage 库存充足/不足/无记录三个场景
- [x] 2.3 写 `tests/test_o2_agent.py`：覆盖 run_kit_alert 端到端、审计写入、无缺口三个场景
- [x] 2.4 写 `tests/test_golden.py`：两成品 × 三层 BOM 黄金对照测试，手工预算值内联注释，偏差 < 1%

## 3. 实现齐套引擎（kit_engine.py）

- [x] 3.1 创建 `o2_kit_shortage/kit_engine.py`，复制 explode_bom + calc_shortage 原样，仅改第一行 import 指向 `zhuopin_platform.shared_tools.models`
- [x] 3.2 跑 test_kit_engine.py + test_kit_shortage.py，确认全绿

## 4. 实现数字员工入口（agent.py）

- [x] 4.1 创建 `o2_kit_shortage/agent.py`，实现 `KitAlertResult` dataclass 和 `run_kit_alert()` 薄包装
- [x] 4.2 审计接入：调用 `AuditLogger.record(AuditEvent(scenario="O2", action="kit_shortage_analysis", ...))`
- [x] 4.3 跑 test_o2_agent.py，确认全绿

## 5. 黄金对照测试与集成验证

- [x] 5.1 完善 tests/fixtures.py（两成品 FIN001/FIN002 × 三层 BOM，内联手工预算），跑 test_golden.py 确认偏差 < 1%
- [x] 5.2 跑全部测试 `pytest tests/ -v`，确认全绿
- [x] 5.3 确认无 `from supplychain` / `from src.` 残留 import（grep 验证）

## 6. 收尾

- [x] 6.1 git commit（feat/o2-kit-shortage-alert 分支）
- [x] 6.2 停下报告 Paul 测试结果（测试数/覆盖场景/齐套精度对照结论），等待审查
