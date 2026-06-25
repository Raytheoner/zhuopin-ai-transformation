## Context

成品保供预警看板现状：`sc8.baoguan`（`assess_supply_risk`/`build_dashboard`/四色判级 + `render_html` 静态页）+ `scripts/run_baoguan_dashboard.py`（CLI 跑一次、写 `reports/*.html`）。真实三源已外网可达：FO（`/zp/api/ForecastOrder/Query` apiKey）、BOM（U9C OAuth2）、携客云承诺（OpenAPI，1req/30s 限流）。本次把它升级为常驻前后台服务，模式参考 supplychain `src/web_app.py`（Flask + waitress）与 `src/delay_case.py`（CaseStore）。复用 SC8 现有引擎，不改判级语义。

**约束**：① 含真实客户名 → 缓存/DB 不入库、先 LAN 自用；② real fail-loud；③ 所有动作写平台 audit；④ 对客闸 `CUSTOMER_OUTBOUND_ENABLED` 全程 False；⑤ 携客云限流 → 刷新须串行。

## Goals / Non-Goals

**Goals:**
- 常驻 Flask 服务：看板页 + `/api/baoguan`(读缓存) + `/api/ping` + `/api/refresh`(手动重算)。
- 三合一触发：定时后台刷新 + 手动刷新 + 新增 🔴 真延期去重推企微保供运维群。
- 保供案例处置中心：真延期自动建案、催货→协调→改期/确认状态机、SLA、操作历史、手动建案（SQLite）。
- AI 催货/改期草稿（API 或模板降级），对客草稿落闸。
- 复用 `sc8.baoguan`/`sources`/`loaders`、平台 `audit`/`notifiers`，零改判级引擎。

**Non-Goals:**
- 外网访问 + 登录鉴权（→ 待办 #10，LAN 跑通后做）。
- 对客自动外发（闸全程关，仅草稿入队）。
- 改四色判级口径 / SMT 工时维度（保供只看齐套）。
- 多用户权限体系、并发写扩展（低频内部工具，简单锁即可）。

## Decisions

**D1 — 服务框架 = Flask + waitress（不引 FastAPI）。** 理由：与 supplychain 一致、Paul 熟悉、生产用 waitress 已验证；本场景无高并发/异步需求。备选 FastAPI（async）：收益不抵新栈成本，弃。

**D2 — 重算走进程内调用，不走 subprocess。** 提取 `sc8/baoguan_service.py::compute_snapshot()` 封装 `load_real_orders + load_real_bom + load_srm_deliveries + build_dashboard`，Flask 直接调用。理由：同包可直接 import，免去 supplychain 那种"跑脚本+解析 markdown"的脆弱中间层。备选 subprocess（supplychain 做法，为隔离崩溃）：解析脆弱、慢，弃。崩溃隔离改由 try/except + 保留旧缓存兜底。

**D3 — 缓存 = SnapshotStore（内存 + 持久化 JSON）。** 重算结果存 `reports/baoguan_snapshot.json`（rows + 生成时间 + 四色计数，gitignored），同时驻内存。`/api/baoguan` 读内存快照；服务启动时从 JSON 恢复（重启不丢最近快照）。理由：页面默认读缓存、不每次打全量；JSON 持久化让重启/多 worker 一致。

**D4 — 刷新串行 = 全局非阻塞锁。** `threading.Lock`，刷新前 `try-acquire`；拿不到 → 立即返回"刷新进行中"（不并行打携客云）。定时刷新与手动刷新共用同一把锁，定时任务拿不到锁则跳过本轮。理由：满足"串行 + 不重复打携客云"规格；非阻塞避免请求堆积。

**D5 — 定时刷新 = 后台守护线程 sleep-loop（不引 APScheduler）。** 启动一个 daemon thread，按 `SC8_BAOGUAN_REFRESH_MIN`（默认 360 分钟=6h）循环重算。理由：零新依赖、够用。备选 APScheduler：重、过度。

**D6 — 去重账本 = 案例本身（建案即去重 + 推送时机）。** 真延期稳定键 = `(item_code, fo_id, ship_date)`。每次刷新后：对新增真延期，若**无未关闭案例** → 建案(状态=催货) + 推一次企微；若已有未关闭案例 → 不建、不推。理由：把"是否已通知"与"是否在处置"统一到案例表，天然去重、不重复轰炸；避免再维护一份独立 pushed 集合。

**D7 — 案例状态机 = 催货→协调→改期/确认→关闭（enum + NEXT_STATUS + SLA_HOURS）。** 收割 supplychain `delay_case.py` 的 CaseStore 骨架（SQLite + events 表 + advance/resolve），但状态语义改为保供四态。SLA 每态可配（默认：催货 24h、协调 48h、改期确认 72h）。理由：复用已验证持久化/事件模型，省重写。

**D8 — AI 草稿 = `sc8/case_draft.py`，API 优先模板降级（参考 crm_notifier）。** 内部催货/协调草稿直接生成展示；对客改期通知草稿仅在请求时生成、`CUSTOMER_OUTBOUND_ENABLED=False` 下入草稿态、绝不外发。理由：复用 supplychain 降级模式；对客红线靠现有闸，不新开外发路径。

**D9 — 前端 = 壳页 + fetch（复用现有 `_HTML_STYLE`/`_HTML_JS`）。** 把 `render_html` 的"嵌入 DATA"改造为：服务端返回壳页（结构+样式+JS），JS 启动时 fetch `/api/baoguan` 得到 DATA 再渲染；新增"刷新"按钮（调 `/api/refresh` + loading 态）、"最后更新时间"、案例入口链接。**CLI 静态 `render_html` 保留**（离线产物仍可用），Web 壳页与之共享 style/JS 片段。理由：现有 JS 已数据驱动，改造最小；静态与服务两用并存。

**D10 — 部署 = waitress 绑 0.0.0.0:`PORT`(默认 8090，避开 supplychain 8080)，无鉴权。** 启动入口 `scripts/run_baoguan_web.py`，载 `.env`、要求 `SC8_DATA_SOURCE=real`。Windows GBK 环境强制 UTF-8 输出（同 supplychain）。外网+鉴权 = 待办 #10。

## Risks / Trade-offs

- **长重算阻塞请求** → D2 在后台线程跑重算 + D4 非阻塞锁，页面读缓存；`/api/refresh` 立即返回"已触发/进行中"，前端轮询或读 `/api/baoguan` 时间戳判断完成。
- **携客云限流被并发击穿** → D4 全局锁串行 + D5 定时间隔不过密（默认 6h）；`load_srm_deliveries` 内既有 materials 批处理。
- **真实客户数据泄露** → 缓存 JSON + 案例 SQLite 全部 gitignore；LAN-only 绑定；外网开放前必须先做 #10 鉴权（红线）。
- **SQLite 在 waitress 多线程下写竞争** → 案例写操作经服务层串行（低频人工操作，量小）；连接按需开关 + 短事务；必要时 WAL。
- **重启丢失内存快照** → D3 持久化 JSON，启动恢复。
- **真延期口径变动导致重复建案** → D6 稳定键 `(料号,单号,出货日)` + "未关闭案例存在则不重建"，对刷新幂等。
- **AI 草稿误外发对客** → D8 对客草稿仅入草稿态，靠 `CUSTOMER_OUTBOUND_ENABLED` 闸，无自动发送路径。

## Migration Plan

- 增量、不破坏：`pip install flask waitress`（加入 SC8 依赖）；新增 `sc8/baoguan_service.py`、`sc8/case_store.py`、`sc8/case_draft.py`、壳页模板、`scripts/run_baoguan_web.py`；既有 `baoguan.py`/`run_baoguan_dashboard.py`/CLI 静态产物不动。
- 启动：`SC8_DATA_SOURCE=real python scripts/run_baoguan_web.py`（读 .env，默认 8090）。
- 回滚：服务为纯新增，停服即回到 CLI 静态看板，无数据迁移。
- 上外网前：先在 LAN 跑通验收 → 提醒 Paul（待办 #10）→ 加鉴权再开放。

## Open Questions（已由 Paul 2026-06-24 拍板，采纳全部默认）

- ✅ 定时刷新间隔 = **6h**（`SC8_BAOGUAN_REFRESH_MIN=360`）。
- ✅ 各状态 SLA = **催货 24h / 协调 48h / 改期确认 72h**。
- ✅ 服务端口 = **8090**（避开 supplychain 8080）。
- ✅ 案例"改期/确认"**仅内部记录 + 人工操作，本期不回写 U9C/携客云**。
- 外网访问 + 登录/Token 鉴权 = 待办 #10，LAN 跑通后再做（含真实客户名红线）。
