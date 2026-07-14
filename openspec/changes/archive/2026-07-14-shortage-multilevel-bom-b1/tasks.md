## 1. 平台 kit_engine：逐层现货抵扣函数（已实现，本次未接入 SC8，留作未来增强）

- [x] 1.1 `explode_bom_with_netting`：先写测试（半成品现货充足不展开/净缺口展开/无现货记录兜底/叶子件不抵扣/不调用时零影响）——`tests/test_explode_bom_with_netting.py`，8 tests
- [x] 1.2 实现 `explode_bom_with_netting`
- [x] 1.3 跑平台/O2/SC7 全量测试，确认 `explode_bom`/`calc_shortage` 零回归、SC7 黄金基准不漂移

## 2. 方案迭代：改用无条件展开（撤销开关+净额方案，2026-07-13 会话内定稿）

- [x] 2.1 发现工作区预写测试规格 `tests/test_bom_multilevel_explosion.py`，与已实现的开关方案冲突
- [x] 2.2 与 Paul 确认：采用预写规格的简化方案（无条件展开、复用 `explode_bom`、不做净额）
- [x] 2.3 撤销 `sc8/config.py::multilevel_bom_enabled()`、`baoguan.py::_multilevel_leaf_components`、`forecast.py::components_override`
- [x] 2.4 删除/重写对应的过渡测试文件（`test_multilevel_bom_config.py`/`test_components_override.py` 删除，`test_baoguan_multilevel.py` 重写为无开关版本）

## 3. SC8 接入：_gross_need / estimate_material_arrivals 复用 explode_bom

- [x] 3.1 `sc8/baoguan.py::_gross_need` 改为复用 `kit_engine.explode_bom`
- [x] 3.2 `sc8/forecast.py::estimate_material_arrivals` 的 `components` 推导改为复用 `explode_bom`
- [x] 3.3 修复预写测试规格里的浮点精度断言（`pytest.approx`，不改算法）
- [x] 3.4 `test_bom_multilevel_explosion.py`（9 tests）+ `test_baoguan_multilevel.py`（2 tests，含姚祖怡 S02Y.0035/R02A.0019 端到端场景）全过
- [x] 3.5 跑 SC8 全量测试，确认零回归（170 passed, 2 skipped）

## 4. 验收与收尾

- [x] 4.1 平台+O2+SC7+SC8 全量回归：平台175+1skip / SC1 53 / O2 20 / SC7 41(黄金基准精确不漂移) / SC8 170+2skip，零回归
- [x] 4.2 更新 SC8 CLAUDE.md 状态时间线
- [x] 4.3 `openspec archive shortage-multilevel-bom-b1`
- [x] 4.4 跨桌任务队列登记（真实 LAN 验证为独立后续任务；`explode_bom_with_netting` 何时接入为独立评估）
- [x] 4.5 commit + push（沿用 B-系列同一批次流程，注意工作区分支状态）
