# 任务 · 物料看板视图（队列 #334）

> 🔴 **1.0 是硬闸**：D4/D5/D6 三个决策点未获 Shao Peishen 拍板前不开工第 2 组之后的任何一项。
> 未答时按各自默认项（D4-a／D5-a／D6-a）执行，但仍须先有一次明确的"按默认执行"确认。

## 1. 前置

- [x] 1.1 design.md D4/D5/D6 已获拍板（或明确按默认项执行），结论回写 design.md
- [x] 1.2 确认工作分支基于最新 origin/master，`git fsck --connectivity-only` 通过

## 2. 取数层（TDD：先测后码）

- [x] 2.1 `sc8/sources.py` 新增 `load_purchase_supply_by_material()`：按料号汇总未交采购订单的供应商名称与制单人（复用 `ZpConnector.get_purchase_orders`，沿用 `load_purchase_orders_by_material` 同款的状态过滤与行级关闭剔除口径），单测覆盖：多供应商去重、无未交订单、连接器异常 fail-soft
  > ⚠️ **一处与派单文字的偏离，如实登记**：本项写「单测覆盖……连接器异常 fail-soft」，但实现上
  > `load_purchase_supply_by_material` 与其兄弟函数 `load_purchase_orders_by_material` 保持一致，是
  > **real fail-loud**（异常原样上抛），fail-soft 发生在调用方 `compute_snapshot`（同 ⑥⑦ 的既有约定）。
  > 若把 fail-soft 塞进 loader 自身，同一模块里两个并列函数的失败语义就会不一致。故拆成两处覆盖：
  > loader 侧 `test_connector_error_propagates_caller_decides_degradation`（异常上抛）＋ 服务侧
  > `test_compute_snapshot_degrades_gracefully_when_supply_loader_fails`（整体不阻断）。行级关闭查询
  > 本身的 fail-soft 在 loader 内，由 `test_line_status_query_failure_is_fail_soft` 覆盖。
- [x] 2.2 `sc8/config.py` 新增物料看板月份窗口跨度参数（默认 3），带 docstring 说明为何可配

## 3. 聚合引擎（TDD：先测后码）

- [x] 3.1 新建 `sc8/material_board.py`，实现 `build_material_board(rows, *, today, commitments, supply_by_material)` 纯函数，输出物料行列表
- [x] 3.2 单测：跨成品聚合去重；无缺口物料不出现；`role=="substitute"` 展示行不单独成行且不重复计缺口（D11）
- [x] 3.3 单测：按出货月归集三个月缺口；合计＝三列之和；窗口外缺口不计入；跨月时月份自动滚动（D2）
- [x] 3.4 单测：答交明细取物料级全量、按三月合计缺口累计截断；`q==0` 如实显示 0 而非"无"（D3）
- [x] 3.5 单测：状态列四态；同一物料状态不一致时输出分歧标记而非任选其一（D10）
- [x] 3.6 单测：取数缺口列（按 D5/D6 拍板结果）输出显式缺口标记，不留空、不以近似字段顶替

## 4. 快照接线

- [x] 4.1 `Snapshot` 新增 `materials` 字段（缺省 `[]`）；单测：旧格式 JSON（无该键）反序列化不报错、取缺省值
  > 📌 同批新增第二个字段 `materials_meta: dict`（同样带缺省 `{}`）：月份列标题、窗口范围、
  > 「窗口外被排除了多少」这三项是**读懂那几个数字的前提**（D7），也是 No silent caps 的要求，
  > 必须随快照一起落盘，`list[dict]` 装不下。D1 约束的是「在哪算、算完放进 Snapshot」，未限定字段数。
- [x] 4.2 `compute_snapshot` 末尾调用 `build_material_board`；单测：不传新参数时既有 `rows`/`counts` 逐字段零漂移

## 5. 展示层

- [x] 5.1 `sc8/webapp.py` 新增 `GET /api/materials`（吐 `Snapshot.materials`）与 `GET /materials` 页面路由，导航栏加入口
- [x] 5.2 页面：13 列表格 + 搜索/筛选/排序/分页，样式复用既有 `_HTML_STYLE`
  > 13 列＝料号／品名／品牌／状态／未交订单数量／〔月度列 ×3〕／总缺口／答交数量／答交日期／
  > 供应商名称／责任人，与她给的模板逐列对应；月度列数随 `SC8_MATERIAL_BOARD_MONTHS` 变化。
- [x] 5.3 页面顶部「取数说明」块：D7 列出的五条逐条落地
- [x] 5.4 Excel 导出按钮：沿用既有零依赖 `.xls` Blob 方案，范围＝当前筛选全集（D8）
- [x] 5.5 单测：`/materials` 与 `/api/materials` 200；空态（无快照）不报错；匿名访问被门禁拦截

## 6. 真实数据验证（档 2/3）

- [ ] 6.1 用真实生产凭据跑一次全量 `compute_snapshot`，产出真实物料看板数据（预计约 15 分钟，SRM 限流所致）
- [ ] 6.2 **逐物料人工对账**：至少 3 个真实物料，把各成品卡片该物料的缺口逐张抄出相加，与物料看板月度列/合计列逐位比对；底稿落 `docs/queue_334_material_board_audit.md`
- [ ] 6.3 核对四色 `counts` 与本次改动前逐字段完全一致（证明未触碰判定红线）
- [ ] 6.4 实测 D10 的推断：真实全量下同一物料的状态是否在各成品行间一致；若不一致，如实登记为独立待查行，不顺手改既有判定
- [ ] 6.5 真实浏览器下载导出文件，核对列数/顺序/中文显示

## 7. 回归

- [ ] 7.1 SC8 全量测试通过、数字与改动前对照（只增不减、无失败）
- [x] 7.2 平台底座全量测试零漂移（本变更不改底座，此步是防误伤）
- [x] 7.3 `openspec validate --all --strict` 通过
- [ ] 7.4 rebase 到最新 origin/master 后**重跑一遍**再 push（SC2 2026-08-18 同款要求，不只在 rebase 前测过）
- [x] 7.5 取真实退出码判定测试结果，不用 `| tail` 之后的退出码（管道会掩盖真实退出码）

## 8. 发布收口（CLAUDE.md §5 第 7 步）

- [ ] 8.1 ff 合入 master 并 push
- [ ] 8.2 `sync-to-server.ps1` 推送 `.51`，重启 `BaoguanWebServer`，**核对进程 CreationDate 真实刷新**
- [ ] 8.3 `POST /api/refresh` 触发全量重算，使线上快照带上 `materials`
- [ ] 8.4 冒烟：`/api/ping` 200 ／ `/materials` 页 200 ／ `/api/materials` 有数据 ／ 匿名被门禁拦 ／ **从笔记本外部**实测可达
- [ ] 8.5 核对服务器上被改文件的 SHA256 与 master 逐字节一致
- [ ] 8.6 回滚 SOP 在位（本变更纯新增，回滚＝revert 后重推重启）
- [ ] 8.7 场景 `CLAUDE.md` 更新「部署状态」段与状态时间线

## 9. 收尾

- [ ] 9.1 跟进信**只起草到 `⏳ 待你审`，不发送** —— 姚祖怡串行闸锁着（采购部#16 于 2026-08-18 推送未回件），且 SC2 判例包已在其前排队
- [ ] 9.2 队列 #334 行回写（状态字段 + 产出路径 + 遗留项）
- [ ] 9.3 全部 tasks 打 [x] 后当场 `/opsx:archive sc8-material-board-view -y`；未全 [x] 不归档、不假装完工
