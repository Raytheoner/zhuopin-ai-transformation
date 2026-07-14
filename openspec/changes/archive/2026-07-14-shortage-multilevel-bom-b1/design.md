## Context

`kit_engine.explode_bom` 已支持多层递归展开（O2/SC7 已验证使用）。SC8 `baoguan.py::_gross_need` 与 `forecast.py::estimate_material_arrivals` 各自独立实现了"只取直接子件（level==1）"的浅层逻辑，从未复用 `explode_bom`，导致半成品子件（如 S02Y.0198）从不被继续分解，其下真实原材料需求（如 R02A.0019）完全不进入任何计算。

**本 design 记录一次会话内的方案迭代**：最初设计（详见本文件历史/proposal 说明）是新增 `SC8_MULTILEVEL_BOM` 开关 + 逐层现货抵扣（半成品有货则不深挖子件），并已实现、测试通过（`kit_engine.explode_bom_with_netting`，8 tests）。开发过程中发现工作区已有一份预先写好、未提交的测试规格 `tests/test_bom_multilevel_explosion.py`，描述了更简单的方案（无条件展开、复用 `explode_bom`、不做净额）。经 Paul 确认，改用该简化方案；`explode_bom_with_netting` 保留在底座作为未来可选增强，未被撤销。

## Goals / Non-Goals

**Goals：**
- `sc8/baoguan.py::_gross_need` 与 `sc8/forecast.py::estimate_material_arrivals` 改为复用 `kit_engine.explode_bom`，无条件递归展开半成品至叶子件。
- 单层 BOM（无半成品）场景结果与改造前完全一致（向后兼容）。
- 半成品不再被误当作"待供应商答交物料"查 SRM。

**Non-Goals：**
- 不新增开关（与最初设计相反的最终决定）——多层展开视为结构正确性修复，无条件生效。
- 不做逐层现货抵扣（`explode_bom_with_netting` 暂不接入 SC8，留作未来增强）——避免与仍在审的 `SC8_NET_INVENTORY` 净额问题（姚祖怡批改指出现货判断本身有 bug）搅在一起。
- 不改 `explode_bom`/`calc_shortage` 现有签名（O2/SC7 零影响）。
- 不做真实 U9C 多层取数的性能/限流验证（独立后续任务）。
- 不解决 C-1（主料替代料）、B4（PMC 多需求优先级）。

## Decisions

### D1（最终）：`_gross_need`/`estimate_material_arrivals` 无条件复用 `explode_bom`
- **决策**：`_gross_need(so, bom)` 内部构造单个 `ProductionPlan(product_id=so.item_code, planned_qty=so.qty, ...)`，调用 `explode_bom(bom, [plan])` 返回叶子件毛需求字典。`estimate_material_arrivals` 同样用 `explode_bom(bom, [dummy_plan(qty=1)])` 取 `.keys()` 作为 `components`（数量无关，只要叶子件集合）。
- **为什么放弃开关+净额**（相对最初设计的变更）：① 更简单，改动面小，风险低；② 与净额开关（`SC8_NET_INVENTORY`）问题解耦——姚祖怡批改还指出现货净额判断本身有 bug（S02Y.0035 瓶颈子件按期误判），净额本身还在等她回复，此时不宜再引入一层新的"逐层现货判断"逻辑，容易把两件事搅在一起；③ Paul 确认的复用现成测试规格已明确是"无条件展开，不做净额"。
- **已放弃但保留的备选**：`explode_bom_with_netting`（逐层现货抵扣）留在 `kit_engine.py`，测试齐全（8 tests），未来若要做"半成品有货就不深挖"，可直接复用。

### D2：浮点精度处理
- 预写测试规格里发现一处浮点精度断言过严（`100*1.0*1.1` 在 Python 里是 `110.00000000000001` 非 `110.0`，是浮点乘法固有特性、非本次逻辑引入）——已改用 `pytest.approx`，不改算法本身（算法与原 `_gross_need` 表达式完全同构）。

## Risks / Trade-offs

- **[风险] 无条件生效意味着影响面立即体现，无渐进灰度**（相对开关方案的取舍）→ 已确认 Paul 接受（"尽量提前"明确指示），且改动本身是修复缺陷而非新业务判断，风险可控；建议部署后近期观察真实看板的分类变化是否符合预期。
- **[风险] 真实 U9C 环境多层递归取数的 API 调用量上升** → `get_bom_for_products` 已有缓存机制；真实验证为独立后续任务，登记跨桌任务队列。
- **[风险] 半成品若被误建模为"可采购件"（如 SRM 里意外存在其承诺记录）** → 现状代码结构下，半成品不再出现在 `components` 里，不会查询 SRM，此风险已消除（正是本次修复的目的）。

## Migration Plan

1. `_gross_need`/`estimate_material_arrivals` 复用 `explode_bom`（已完成，见预写测试规格 `test_bom_multilevel_explosion.py` 9 tests 全过）。
2. `baoguan.py` 端到端验证（`test_baoguan_multilevel.py`，含姚祖怡 S02Y.0035/R02A.0019 场景）。
3. 平台+O2+SC7+SC8 全量回归，SC7 黄金基准核验（已完成，零回归）。
4. `openspec archive`；跨桌任务队列登记；commit+push。
5. **后续（不在本次范围）**：真实 LAN 环境验证多层取数性能/限流；`explode_bom_with_netting`（逐层现货抵扣）何时接入是独立评估。

## Open Questions

无——本次方案迭代已在会话内与 Paul 确认定稿（AskUserQuestion 选择"改成现成测试文件的简单方案"）。
