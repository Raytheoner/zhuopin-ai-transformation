## 1. 真实数据字段验证（先做，design.md Open Question #1/#2，仿 C-1 既有验证方法论）

- [ ] 1.1 生产 `BOM/Query` 只读实测：抽样口径定稿 §2 C-1·① 已确认存在替代料的母件，探测其 `m_bOMCompSubstituteDTO4CreateSv` 列表内每个元素的字段结构——是否自带独立 `m_usageQty`/`m_scrap`，`m_itemMaster` 是否与主件行同构；记录结论到本任务备注，供 1.3 实现依据
- [ ] 1.2 探测同项次多主料/多替代料的边界情况（`m_subSeq` 是否被真实数据用上；是否存在一组多替代的真实样本）
- [ ] 1.3 若替代料字段结构与 design.md D2 假设不符，更新 design.md 决策记录后再继续；若相符，直接进入第 2 节

## 2. 平台：BomRow 新增字段 + BOM 取数提取替代料关系

- [ ] 2.1 `BomRow` 新增 `sequence: str = ""`、`is_substitute: bool = False` 两个默认值字段：先确认现有 O2/SC7/SC8 测试全部沿用无关键字参数构造仍通过（回归探测，不新增测试）
- [ ] 2.2 `get_bom_for_products` 主件行提取 `sequence`（`m_sequence`）与 `is_substitute`（`m_componentType==0`）：先写测试（mock 原始 BOM 响应，覆盖主件行字段正确映射）——`tests/test_bom_substitute_extraction.py`
- [ ] 2.3 `get_bom_for_products` 读取 `m_bOMCompSubstituteDTO4CreateSv`，为每条替代料生成对等 `BomRow`（`is_substitute=True`，`sequence` 继承主件行）：先写测试（有替代料/无替代料/替代料字段按 1.1 验证结论取值三种场景）——同上测试文件
- [ ] 2.4 跑平台/O2/SC7/SC1 现有全量测试，确认零回归（新增字段默认值不影响现有调用方）

## 3. SC8：C-1 替代料等价合并判缺料

- [ ] 3.1 `sc8/baoguan.py` 新增料位分组函数（按 `product_id`+`sequence` 分组，识别主料/替代料）：先写测试（单料位无替代/单料位含替代/同项次多替代场景）——`tests/test_baoguan_substitute_merge.py`
- [ ] 3.2 实现分组内毛需求归一（只计主料一份）+ 现货合计判齐逻辑，接入 `_gross_need`/`_covered_by_stock`/`assess_supply_risk`：先写测试（替代料现货补足缺口/合计仍不足/等价合并无优先级顺序三种场景）——同上测试文件
- [ ] 3.3 `BaoguanRow` 新增 `substitute_groups: dict[str, list[str]]` 字段，`assess_supply_risk` 填充：先写测试（含替代料/不含替代料两种场景断言字段值）——同上测试文件
- [ ] 3.4 跑 SC8 现有全量测试，确认零回归（尤其 `test_baoguan.py`/`test_baoguan_multilevel.py`/`test_baoguan_netting.py`/`test_baoguan_period_match.py`）

## 4. SC8：C-2 部分齐套显示

- [ ] 4.1 `sc8/baoguan.py` 新增可齐套套数计算函数（`min(floor(子件可用现货÷单机用量))`，全部直接子件参与）：先写测试（现货数据齐全/现货数据缺失返回 None/多子件取最紧瓶颈三种场景）——`tests/test_baoguan_partial_kit.py`
- [ ] 4.2 `BaoguanRow` 新增 `kittable_qty`/`kittable_bottleneck`/`kittable_shortfall` 三字段，接入 `assess_supply_risk`（仅当 `inventory` 有效时计算，否则恒为 `None`，与净额开关耦合，design.md D4）：先写测试——同上测试文件
- [ ] 4.3 确认 `kittable_shortfall` 计算口径（design.md Open Question #3，推荐"凑够 `kittable_qty+1` 套所需缺口"）——若需与姚祖怡确认，随后续显示层抽验一并问，不单独开会阻塞
- [ ] 4.4 验证部分齐套不改变现有四色判定：先写测试（存在缺口且可齐套>0 时风险等级不变为 🟢；建议动作文案追加"可先齐 X 套"）——同上测试文件
- [ ] 4.5 跑 SC8 现有全量测试，确认零回归

## 5. SC8：看板显示（webapp.py）

- [ ] 5.1 `row_to_dict` 新增 `substitute_groups`/`kittable_qty`/`kittable_bottleneck`/`kittable_shortfall` 字段透传：先写测试——`tests/test_baoguan_webapp.py` 补充用例
- [ ] 5.2 `render_html`（`_HTML_JS`/卡片渲染）新增"可齐套 X/总需求"徽标 + 悬浮瓶颈文案 + "含替代料 Rxx"标注；字段为空时不显示对应徽标（向后兼容旧数据/无替代料/净额关闭场景）
- [ ] 5.3 跑 SC8 现有全量测试，确认零回归（尤其 `test_baoguan_webapp.py`）

## 6. 验收与收尾

- [ ] 6.1 平台 + O2 + SC7 + SC1 + SC8 全量测试跑一遍，逐项确认零失败；SC7 黄金基准（35850/640000/675850）精确不漂移
- [ ] 6.2 真实数据抽验（姚祖怡）：覆盖口径定稿验证样本中的替代料组（15 母件/56 组）与至少若干部分齐套场景，确认判定结果符合预期——对应本变更包"验收与晋档条件"档2 真实数据跑通
- [ ] 6.3 更新 SC8 CLAUDE.md 状态时间线（本次改造摘要）；如平台 `BomRow`/连接器有对外可见行为变化，同步更新根 CLAUDE.md 相关索引（如适用）
- [ ] 6.4 `openspec archive sc8-baoguan-substitute-partial-kit`
- [ ] 6.5 跨桌任务队列 `#31` 状态改"待验收/完成"，回填产出路径（openspec 归档路径 + commit hash + 姚祖怡抽验结论）
- [ ] 6.6 commit + push（本地 mock/脱敏 + LAN 真实数据验证均通过后再提交；若受时间限制先提交 mock 验证通过版本，真实验证独立登记为后续任务，需在 commit message 与队列行中明确标注未完成项）
