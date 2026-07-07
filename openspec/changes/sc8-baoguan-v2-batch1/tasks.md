# sc8-baoguan-v2-batch1 Tasks

## 1. 看板窗口过滤（一.1，最先做·低风险）✅

- [x] 1.1 `build_dashboard` 增 `ship_before`（默认 `config.baoguan_ship_before()`=2026-10-31，读 `SC8_BAOGUAN_SHIP_BEFORE`）；出货日 > 窗口的成品行过滤掉
- [x] 1.2 单测 `test_ship_before_window_filter`：窗口内保留、窗口外剔除；SC8 全回归 143 passed 零漂移

## 2. 未答复子件全展开（一.2·展示层）

- [ ] 2.1 `row_to_dict`/`render_markdown`/`render_html` 展示全部 `no_feedback_materials`（不只瓶颈）
- [ ] 2.2 单测：25 未答复全列出

## 3. PO 多行答交核实（二.2·数据正确性）

- [ ] 3.1 正式库真实核 R01F.0005（PO ZPCG20260509006 行40/50）：`/purchase/answer` 是否漏行
- [ ] 3.2 若漏行 → `load_srm_deliveries` 遍历全部 PO 行取最早有效答交 + 回归；不漏则记录结论

## 4. 递归展开 + 逐层半成品净额（五 + 二.4·核心引擎）

- [ ] 4.1 `load_real_bom` 支持递归 `max_depth`（>1）拉多层 BOM（防环/深度上限）
- [ ] 4.2 保供多层齐料：自顶向下算净需求（毛需求 − 白名单仓现货）；半成品净≤0 齐备不下钻、净>0 按净需求下钻
- [ ] 4.3 齐料日多层滚动：叶到货 → 半成品可得日(=其净需求子件最晚到货，暂不含加工工时) → 成品齐料日；瓶颈=叶级关键路径
- [ ] 4.4 挂 `SC8_NET_INVENTORY` 门：OFF 退化现单层无净额逻辑（零漂移）
- [ ] 4.5 单测：F→S 下钻、半成品净额（1264−264=1000）、多层瓶颈定位、防环、OFF 零漂移

## 5. 回归与真实抽验

- [ ] 5.1 全回归：平台/O2/SC5/SC8 全绿；SC8 现黄金 flag OFF 零漂移
- [ ] 5.2 正式库真实抽验专员案例（S02Y.0035/0120/0166、F02N.0226）：递归瓶颈、半成品净额、窗口过滤正确
- [ ] 5.3 出"净额+多层 前后对比"给采购专员黄金重核（与 stock-api 一并签字）
- [ ] 5.4 `openspec validate` 通过；`git commit`；`/opsx:archive`（专员签字后翻 `SC8_NET_INVENTORY` 属部署，不在本包）
