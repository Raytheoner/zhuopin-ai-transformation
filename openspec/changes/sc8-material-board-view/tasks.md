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

- [x] 6.1 用真实生产凭据跑一次全量 `compute_snapshot`，产出真实物料看板数据（预计约 15 分钟，SRM 限流所致）
  > 生产 `.51` 真实全量重算 2026-08-20 12:07→12:14:52（**约 8 分钟**，比 design 预估的 15 分钟快——
  > 该次走的是服务端已有的 firm 承诺 6 小时缓存 `SC8_SRM_ANSWER_TTL_MIN=360`）。产出 **596 个缺料物料**。
  > ⚠️ **本机另跑过一次全量（11:41→12:00）但口径不同、不作为验收依据**：仓库根 `.env` 里没有
  > `SC8_NET_INVENTORY`（它只配在 `.51` 的 `.env`），故本机那次净额开关是 **OFF**、`gap_qty` 恒为 None、
  > 走「退回本项目毛需求」的兜底分支 ⇒ 得到 1493 个物料、`counts` 也不同（`red:105`）。
  > **验收一律以生产那份为准**；本机那次的价值只是「代码在真实数据上跑得通、不崩」这个前置冒烟。
- [x] 6.2 **逐物料人工对账**：至少 3 个真实物料，把各成品卡片该物料的缺口逐张抄出相加，与物料看板月度列/合计列逐位比对；底稿落 `docs/queue_334_material_board_audit.md`
- [x] 6.3 核对四色 `counts` 与本次改动前逐字段完全一致（证明未触碰判定红线）
  > 底稿 `4-数字员工/采购部/SC8-客户订单交期智能承诺/docs/queue_334_material_board_audit-2026-08-20.md`
  > （**落 tracked 的 `docs/`、不落 gitignored 的 `reports/`** —— #267 事故即审计报告随 worktree 删除而永久丢失）。
  > 结果：`{red:99, gap:0, yel:0, grn:6}` **逐字段与部署前基线完全一致**。
- [x] 6.4 实测 D10 的推断：真实全量下同一物料的状态是否在各成品行间一致；若不一致，如实登记为独立待查行，不顺手改既有判定
- [x] 6.5 真实浏览器下载导出文件，核对列数/顺序/中文显示
  > 在**真实浏览器**（Browser pane 的 Chromium）里点了导出按钮，拦下它真正生成的 Blob 逐项核对：
  > `application/vnd.ms-excel`／文件名 `物料看板_2026-08-20.xls`／**表头 13 列顺序与页面逐字一致**／
  > 正文每行 13 列／中文完好／**首三字节 `EF BB BF` ＝ UTF-8 BOM**（Excel 靠它判编码，缺了就是乱码）／
  > 制单人未泄漏进导出。
  > ⚠️ **如实登记未做的那一半**：**没有把文件落盘再用 Excel 真打开看一眼** —— 本机没有可驱动的 Excel，
  > 且沙箱浏览器的下载落点不可靠。**导出机制与姚祖怡每天在用的成品看板导出是同一套实现**
  > （同一 HTML-table ＋ `.xls` Blob 路径），故判定风险可接受；真正的 Excel 打开由他首次使用时验证。

## 7. 回归

- [x] 7.1 SC8 全量测试通过、数字与改动前对照（只增不减、无失败）
- [x] 7.2 平台底座全量测试零漂移（本变更不改底座，此步是防误伤）
- [x] 7.3 `openspec validate --all --strict` 通过
  > 87 passed / 2 failed（89 项）。**两条失败与本变更无关，且已证明是存量**：
  > `editlock-mutex-stale-cleanup-resilience` 与 `queue-dual-file-split`（均为他线的机制类变更包，缺 specs delta）。
  > **验证方式不是「我没碰它们」这种推断** —— 用 `git archive origin/master openspec` 抽出纯净的 master
  > 副本单独跑这两条，同样失败。本变更自身 `openspec validate sc8-material-board-view --type change --strict` 通过。
- [x] 7.4 rebase 到最新 origin/master 后**重跑一遍**再 push（SC2 2026-08-18 同款要求，不只在 rebase 前测过）
- [x] 7.5 取真实退出码判定测试结果，不用 `| tail` 之后的退出码（管道会掩盖真实退出码）

## 8. 发布收口（CLAUDE.md §5 第 7 步）

- [x] 8.1 ff 合入 master 并 push
- [x] 8.2 `sync-to-server.ps1` 推送 `.51`，重启 `BaoguanWebServer`，**核对进程 CreationDate 真实刷新**
- [x] 8.3 `POST /api/refresh` 触发全量重算，使线上快照带上 `materials`
- [x] 8.4 冒烟：`/api/ping` 200 ／ `/materials` 页 200 ／ `/api/materials` 有数据 ／ 匿名被门禁拦 ／ **从笔记本外部**实测可达
- [x] 8.5 核对服务器上被改文件的 SHA256 与 master 逐字节一致
- [x] 8.6 回滚 SOP 在位（本变更纯新增，回滚＝revert 后重推重启）
  > **实测过，不是照抄 design 那句「纯新增、回滚无风险」**：回滚后旧版 `Snapshot` 反序列化新格式快照
  > 会抛 `TypeError: unexpected keyword argument 'materials'` —— 但 `SnapshotStore._load` 的既有
  > `try/except` 会吞掉它并置 `_snap=None`，**服务不崩，退化为空态**。
  > ⇒ **回滚 SOP（三步，第 ③ 步是 design 原文漏掉的）**：① `git revert ca6b668 327a5ae` 并 ff push；
  > ② `sync-to-server.ps1` 推送并重启；③ **立刻 `POST /api/refresh`** —— 否则成品看板会空着，
  > 直到下一次整点后台重算（最长 1 小时）才恢复。无数据迁移、无不可逆动作。
- [x] 8.7 场景 `CLAUDE.md` 更新「部署状态」段与状态时间线

## 9. 收尾

- [ ] 9.1 🔴 **未做，且是刻意不做、不是遗漏** —— 跟进信**连起草都不被允许**。原文：跟进信只起草到 `⏳ 待你审`，不发送 —— 姚祖怡串行闸锁着（采购部#16 于 2026-08-18 推送未回件），且 SC2 判例包已在其前排队
  > **派单件（opener 与本项原文）说「起草到 `⏳ 待你审`」，但根 CLAUDE.md 的串行原则说的是「不得起草」** ——
  > 两处冲突，本 session 按**上位规则**执行，不自行放宽。原文判据：「查 README 该收信人**最近一封**的
  > 发送状态列是否已到『已回件并回灌』；未到即**不得起草下一封**，改为在队列登记一行『待前信闭环后发』
  > 并写明拟发内容要点」。
  > **实测该判据**：采购部#16 状态列 ＝ `✅ 已推送 2026-08-18 10:36 UTC`，且该行 2026-08-19 追记明写
  > 「**姚祖怡串行闸仍锁着，SC2 判例包（拟采购部#17）仍不能起草**」。⇒ 本信排在 SC2 判例包之后，
  > 最早也只能是 采购部#18。
  > 🔴 **不只是「规矩上不该」，是机器闸物理上也拦着**：`_validate_followup_readme_release` 只认 `📥` 前缀，
  > 往 README 加新行会被 `release` 拒绝，除非写 `串行豁免：` —— 而这里**没有任何一条合法的豁免理由**
  > （前信既非 `❌ 已作废`、也非 `✅ 无需回复`、也非 `📨 已确认闭环`）。为过闸而编一条豁免，
  > 就是拿逃生阀去绕它本来要拦的那件事。
  > **⇒ 已按规则的替代动作执行**：拟发要点写进队列 §一 #334 行（见该行「拟发跟进信要点」段），
  > **不预先写出信件放着** —— skill 明写「写好的信会被后来的 session 当成『可以发了』」。
- [x] 9.2 队列 #334 行回写（状态字段 + 产出路径 + 遗留项）
- [ ] 9.3 🔴 **不归档**（9.1 未完成 ⇒ tasks 未全 [x]，**不假装完工**）。原文：全部 tasks 打 [x] 后当场 `/opsx:archive sc8-material-board-view -y`；未全 [x] 不归档、不假装完工
