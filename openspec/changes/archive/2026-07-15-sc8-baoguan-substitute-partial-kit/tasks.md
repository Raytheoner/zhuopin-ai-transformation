## 1. 真实数据字段验证（先做，design.md Open Question #1/#2，仿 C-1 既有验证方法论）

- [x] 1.1 **已补做（2026-07-15，事后真实验证）**：apply 当时在无 LAN 访问的沙箱环境按 D2 假设实现；同日晚些 Paul 回公司确认在 LAN 后，CC 在能连 U9C 的环境下对 7 母件/20 组替代料做了生产 `BOM/Query` 只读实测。**结论：D2 原假设错误**——替代料 DTO 确实自带 `m_usageQty`/`m_scrap` 字段，但 `m_usageQty` 恒为 1.0（与主件行真实用量 1/2/3/4/9/10/16 等值无关，是占位值，不可采信）。已修正 `get_bom_for_products`：替代料恒继承主件行 `qty_per_unit`/`loss_rate`，忽略自身 `m_usageQty`/`m_scrap`。详见 design.md "2026-07-15 补充"
- [x] 1.2 同批完成：`m_subSeq` 20 组样本恒为 0（无多替代料场景），`m_sequence` 映射稳定无反例，见 design.md 补充段
- [x] 1.3 已按真实验证结论更新 design.md 决策记录（新增补充段，原 Decision D2 保留作历史记录+标注已修正）+ 修正代码 + 修正 `tests/test_bom_substitute_extraction.py`（1 个测试断言方向反转）+ 修正 `openspec/specs/platform-data-connectors/spec.md`，全量回归零漂移

## 2. 平台：BomRow 新增字段 + BOM 取数提取替代料关系

- [x] 2.1 `BomRow` 新增 `sequence: str = ""`、`is_substitute: bool = False` 两个默认值字段；O2/SC7/SC8 现有测试全通过（字段追加不影响现有调用方）
- [x] 2.2 `get_bom_for_products` 主件行提取 `sequence`（`m_sequence`）与 `is_substitute`（`m_componentType`）：`tests/test_bom_substitute_extraction.py` 7 tests 全过
- [x] 2.3 `get_bom_for_products` 读取 `m_bOMCompSubstituteDTO4CreateSv`，为每条替代料生成对等 `BomRow`（`is_substitute=True`，`sequence` 继承主件行；自身有 `m_usageQty`/`m_scrap` 则优先用，无则继承主件行值）：同上测试文件覆盖
- [x] 2.4 平台 193 passed+1 skip / O2 20 / SC7 41（黄金基准精确不漂移）/ SC1 53，零回归

## 3. SC8：C-1 替代料等价合并判缺料

- [x] 3.1 `sc8/baoguan.py::_substitute_groups`（按 `product_id`+`sequence` 分组，识别主料/替代料）：`tests/test_baoguan_substitute_merge.py` 覆盖
- [x] 3.2 `_gross_need` 展开前剔除替代料行（不重复计毛需求）；`_covered_by_stock` 现货合计=主料+全部替代料（等价合并无优先级）；**顺带发现并修复**：`estimate_material_arrivals`/`explode_bom` 不识别 `is_substitute`，替代料行若原样传入会被当成独立"待答交组件"查 SRM（幻影组件），已在 `assess_supply_risk` 调用 `estimate_material_arrivals` 前过滤替代料行修复——8 tests 全过（现货补足缺口/合计仍不足/开关OFF忽略/等价合并无优先级/多替代料合计等场景）
- [x] 3.3 `BaoguanRow` 新增 `substitute_groups: dict[str, list[str]]`，三个 return 分支均已填充，不受净额开关影响（纯展示信息恒定生成）
- [x] 3.4 SC8 全量 177 passed+3 skip，零回归

**⚠️ 已知范围外风险（发现于本次实现，未处理）**：`sc8/pipeline.py`/`forecast.py`（SC8 交付承诺主流程，与 baoguan.py 保供看板是两条不同流水线）同样调用 `estimate_material_arrivals`/`explode_bom`，若未来真实 BOM 数据里出现替代料行，会面临与 3.2 相同的"幻影组件"问题——本变更包 design.md 明确不改 forecast.py/commitment.py 核心流程，此风险留给后续任务处理（届时需要同样过滤或把过滤逻辑上提到更通用的位置）。

## 4. SC8：C-2 部分齐套显示

- [x] 4.1 `sc8/baoguan.py::_kittable_qty`（`min(floor(子件可用现货÷单机用量))`，全部直接子件参与、无例外，含替代料料位用 C-1 合计现货）：`tests/test_baoguan_partial_kit.py` 8 tests 全过
- [x] 4.2 `BaoguanRow` 新增 `kittable_qty`/`kittable_bottleneck`/`kittable_shortfall` 三字段，接入 `assess_supply_risk`（仅当 `inventory and had_bom and net_inventory_enabled()` 时计算，与净额开关同一入口，design.md D4）
- [x] 4.3 `kittable_shortfall` 采用推荐口径"凑够 `kittable_qty+1` 套所需缺口"实现并测试覆盖；**是否符合姚祖怡预期未经专员确认**，随 6.2 真实数据抽验一并问，不单独开会阻塞
- [x] 4.4 验证部分齐套不改变现有四色判定：存在缺口且 kittable_qty>0 时风险等级维持现状（不改判 🟢）、建议动作文案追加"可先齐 X 套"——测试覆盖
- [x] 4.5 SC8 全量 185 passed+3 skip，零回归

## 5. SC8：看板显示（webapp.py 复用的 baoguan.py 渲染层）

- [x] 5.1 `row_to_dict` 新增 `subs`（substitute_groups）/`kq`/`kbn`/`ksf`（kittable 三字段）透传：先写测试——**实际落在 `tests/test_baoguan.py`**（而非原计划 `test_baoguan_webapp.py`——该文件测的是 Flask 层用原始 dict 灌数据，不经过 `row_to_dict`，`test_baoguan.py` 是 `row_to_dict`/`render_html` 现有测试的实际所在地，更贴合）
- [x] 5.2 `_HTML_JS`（webapp.py 的壳页与 `render_html` 的静态页共用同一份 JS）新增 `subsText()` 辅助 + 卡片"可齐套 X/总需求"徽标（`title` 悬浮显示瓶颈子件+还差件数+含替代料标注）+ 瓶颈子件旁"含替代料 Rxx"标注；`kq==null` 时不显示徽标（不以 0 冒充），`subs` 为空时不显示标注——与本变更包实施前完全一致的向后兼容
- [x] 5.3 SC8 全量 188 passed+3 skip，零回归（含 `test_baoguan_webapp.py` 原有用例，其走 Flask 原始 dict 路径不受字段新增影响）

## 6. 验收与收尾

- [x] 6.1 平台193+1skip / O2 20 / SC7 41(黄金基准35850/640000/675850精确不漂移) / SC1 53 / SC8 188+3skip，全量测试跑完逐项零失败
- [ ] 6.2 **未做**：真实数据抽验（姚祖怡）——覆盖口径定稿验证样本中的替代料组与至少若干部分齐套场景，需姚祖怡本人参与判断，非 CC 能独立完成。**2026-07-15 补充**：字段结构验证（design.md D2）已由 CC 事后补做（7 母件/20 组替代料，见 1.1），发现并修正了 D2 假设的一处真实错误（替代料 usageQty 占位值问题）；这 20 组真实样本可直接作姚祖怡抽验素材，不必重新找样本。登记为独立后续任务（跨桌任务队列 `#33`）
- [x] 6.3 已更新 SC8 CLAUDE.md 状态时间线（"3.复用底座资产"新增行 + 07-15 状态时间线行 + "当前"行 + §6 关键依赖新增一行）
- [x] 6.4 `openspec archive sc8-baoguan-substitute-partial-kit`（本次收尾执行）
- [x] 6.5 跨桌任务队列 `#31` 状态回填（apply 完成、mock 全量测试通过零回归，真实数据字段验证+姚祖怡抽验作为新行登记待领）
- [x] 6.6 commit + push——**本次只提交 mock/脱敏验证通过的版本**；真实数据字段验证（tasks.md §1）与姚祖怡真实数据抽验（6.2）均未完成，已在本文件、SC8 CLAUDE.md、跨桌任务队列中明确标注为独立后续任务，不构成"隐藏未完成项"
