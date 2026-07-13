## 1. 平台 B3（BOM 版本过滤，含活 bug 修复——优先做，生产环境真实数据错误）

- [x] 1.1 `get_bom_for_products`（或 `_u9c_bom_post` 后处理）新增按 BOM 主记录 `m_effectiveDate ≤ 今天 < m_disableDate` 过滤：先写测试（单版本不变/多版本取当前生效/全不满足 fail-safe 回退三种场景，mock 原始响应，覆盖本 session 抓到的 4 个真实多版本样例 S02Y.0035/S02Y.0162/S04Y.0112/S07Y.0137 的版本区间结构）——`tests/test_bom_version_filter.py`，5 tests
- [x] 1.2 实现过滤逻辑 + fail-safe 回退（取 `m_disableDate` 最大的一条）+ audit 记录异常——`_select_current_bom_version` + `get_bom_for_products`
- [x] 1.3 跑平台/SC1/SC8 现有全量测试，确认零回归——平台151/SC1 53/SC8 143+2skip 全绿

## 2. 平台 A1（在途到货日过滤 + 真实 SRM 确认日期）

- [x] 2.1 `kit_engine.py` 新增 `filter_transit_by_arrival(purchase_orders, cutoff_date, date_field=...)`：先写测试（超期剔除/未超期保留/不调用时零影响）——`tests/test_kit_engine_transit_arrival_filter.py`
- [x] 2.2 实现 `filter_transit_by_arrival`
- [x] 2.3 `get_purchase_orders` 新增按 `(erpNo, supplyCode)` 查询携客云 SRM 确认日期：先写测试（查到用真值/查不到退回 expected_date/部分失败不阻断其他 PO 三种场景）——`tests/test_po_srm_confirmed_date.py`，5 tests
- [x] 2.4 实现 SRM 确认日期查询，写入 `supplier_confirmed_date`（替换现状 `=expected_date` 占位）——`_overlay_srm_confirmed_dates` + `srm_connector` 可选构造参数（默认 None，零风险）
- [x] 2.5 跑 O2/SC7 现有全量测试，确认 `calc_shortage`/`explode_bom`/`get_purchase_orders` 零回归、SC7 黄金基准（35850/640000/675850）精确不漂移——O2 20/SC7 41（含 8 项黄金基准）全绿

## 3. 平台 A2（追料 L/T 分桶）

- [x] 3.1 `bucket_shortage_by_lead_time(shortages, demand_dates, lead_times, today)`：先写测试（临近/未临近/缺 L/T 兜底三种场景）——同 `test_kit_engine_transit_arrival_filter.py`
- [x] 3.2 实现 `bucket_shortage_by_lead_time`
- [x] 3.3 登记 L/T 数据缺口为独立后续任务——跨桌任务队列 `#19` 已追加

## 4. SC8 B2（周期累计供需匹配，范围显著扩大——2026-07-10 会议定稿）

- [x] 4.1 `sc8/sources.py` 新增 SRM 承诺数量提取（按 PO+供应商配对查询当前确认状态）：先写测试——`_extract_board_commitments`/`load_material_commitments`，`tests/test_material_commitments.py` 6 tests
- [x] 4.2 实现周期窗口计算函数（`[上次期望交付日+1, D]`；无"上一次"时按"D 减 1 个自然月"兜底）：先写测试（含 Paul 给的 7/20→6/21~7/20 worked example）——`sc8/period_match.py`
- [x] 4.3 实现周期内累计判定（累计 ≥ 需求量 → 可满足；不足 → 输出需求日当天可满足量 + 逐日累计曲线）：先写测试——`tests/test_period_cumulative_match.py` 7 tests
- [x] 4.4 实现跨周期结转（扣除上一周期已用供应量的游标）：先写测试——`carry_in_balance`/`carry_forward` 参数，同上测试文件覆盖
- [x] 4.5 `sc8/forecast.py`/`sc8/baoguan.py::BaoguanRow` 接入周期累计匹配结果，新增字段承载逐日曲线（不改动现有 `gap_days`/`risk` 字段语义）——`BaoguanRow.period_match` 新字段 + `_period_match_for_so`，`tests/test_baoguan_period_match.py` 3 tests
- [x] 4.6 跑 SC8 现有全量测试，确认零回归

## 5. B4 框架（PMC 优先级占用挂钩点，同时服务 B2 多需求排序）

- [x] 5.1 `sc8` 净额快照计算处新增可选 `priority_resolver` 参数（默认 None）：先写测试（不传时行为不变）——`tests/test_priority_resolver_stub.py` 2 tests
- [x] 5.2 实现挂钩点透传（不实现真实解析器）——`build_dashboard(priority_resolver=None)`，接受但不调用
- [x] 5.3 文档/注释标注"框架桩，PMC 数据源到位后续期实现；同时服务 B2 多需求排序与 B4 现货占用"——已写入 docstring

## 6. 验收与收尾

- [x] 6.1 平台 + O2 + SC7 + SC8 全量测试跑一遍，逐项确认零失败——平台167+1skip/SC1 53/SC7 41/O2 20/SC8 161+2skip，全绿，SC7 黄金基准8项精确不漂移
- [x] 6.2 更新 SC8/O2/SC7/平台各自场景 CLAUDE.md 状态时间线（本次改造摘要，含 B3 活 bug 发现与修复记录）
- [x] 6.3 `openspec archive shortage-baoguan-criteria-v3`
- [x] 6.4 跨桌任务队列 `#17` 状态改"待验收/完成"，回填产出路径（openspec 归档路径 + commit hash）；单独标注 B3 活 bug 发现供 Paul/IT 评估；登记"真实数据 LAN 回归"为独立后续任务（本次未覆盖）
- [x] 6.5 commit（先本地 mock/脱敏跑通，真实库回归另行在 LAN 环境验证，登记为后续任务不阻塞本次交付）
