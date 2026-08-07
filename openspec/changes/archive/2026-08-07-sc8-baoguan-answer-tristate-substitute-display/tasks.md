# sc8-baoguan-answer-tristate-substitute-display Tasks

## 前置真实探测（已在 design 阶段完成，此处登记留痕）
- [x] 真实穷举 `get_receive_board` 全字段（record/item/poLine 三层），确认三态无独立字段
- [x] 真实统计 `answerQty is None` vs `answerQty == 0` 分布（223 vs 669，365 天窗口）
- [x] 真实测算 `_chunk_date_windows` 180→365 天段数变化（3→6 段）

## #296 答交口径 v4 + 三态判据
- [x] `sources._extract_board_commitments`：None/0 区分修复（D2a）
- [x] `baoguan._component_supply_status`：状态列改挂 `material_commitments`（D2b，含
      `material_commitments is None` 降级兜底路径）
- [x] `config.material_commitment_lookahead_days()` 默认值 180→365
- [x] 新增/更新测试：`test_material_commitments.py`（None/0 区分）、
      `test_baoguan_po_transit.py`（状态列改挂+降级兜底）、`config` 相关测试
- [x] 🔴 真实端到端验证过程中额外发现并修复：`_cumulative_confirmed_batches`
      自身也有 `if q<=0: continue`，D2a 修复后仍会重新丢弃 `answerQty=0` 记录
      （同族第二层缺陷，见 `docs/queue_296_*.md` §2.3），已修复+补 2 个回归测试
- [x] 真实端到端复现：`R01D.0015` 答交数量修复前 `cb=[]`（显示"无"，错误）→
      修复后 `cb=[{"d":"2026-08-20","q":0.0},{"d":"2026-09-20","q":0.0}]`
      （显示"0、0"，正确）；`R02A.0019` 状态显示 `transit_unconfirmed`
      "有未交订单无答交"（非"已答交"）
- [x] 全量真实数据口径复核，产出 `docs/queue_296_material_commitment_tristate_audit.md`
      （107张真实订单/5819行BOM缺口清单，113个料号的cb曾因该bug全为"无"）

## #297 替代料并列展示
- [x] `ComponentSupplyStatus` 新增 `role` 字段
- [x] `_component_supply_status` 内联追加替代料展示行（沿用主料 `need`，独立算
      status/avail/gap/answer）
- [x] 前端 `componentStatusHtml`：`role` → "（主料）"/"（替代料）" 文案
- [x] 新增测试：单主料无替代/单替代/多替代/需求量沿用主料/独立 avail-gap 计算/
      JSON 序列化/HTML 渲染（`test_baoguan_substitute_display.py`，12 例）
- [x] 真实端到端复现：`F02N.0242`（她的原始订单，今日已不在活跃 FO 快照）→改用
      同一组真实物料 `R01A.1459`/`R01A.1545` 在今日活跃订单 `F02N.0254` 下复现，
      替代料真实可用现货=254，与她截图数字完全一致
- [x] 全量真实数据口径复核，产出 `docs/queue_297_substitute_display_audit.md`
      （222主料/222替代料展示行，63组成品×主料真实组合，30组抽样对照表）
- [x] **黄金基准重跑 counts 不变的显式证明**：两轮真实全量快照
      `{"red":102,"gap":0,"yel":0,"grn":5}` 逐字段完全一致

## 收口
- [x] 全量回归零漂移（SC8 377passed+4skip/平台259+1skip/SC1 53/SC7 41黄金基准精确/O2 20）
- [ ] openspec 归档
- [ ] 场景 CLAUDE.md 更新
- [ ] 部署 `.51:8091` + 冒烟三件套（`/api/ping`/关键页 200/`POST /api/refresh` 全量重算）
      + 核验新进程 `CreationDate` 真刷新
- [ ] 给姚祖怡起草跟进信（README 只写 `⏳ 待你审`，含 §四#55 索签决策点），
      提交 Shao Peishen 审——**发送前须三条硬前置全过**（ff 合入 master + `.51`
      部署冒烟通过 + 用她原始举证案例端到端复现）
- [ ] commit + push
- [ ] 队列 #296/#297 两行回写（协议〇.7 编辑锁，✅ 写在状态列开头）
- [ ] 收工重跑文档台账
