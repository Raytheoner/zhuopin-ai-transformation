## Why

成品保供预警看板当前是**静态产物**：每次要在命令行跑 `run_baoguan_dashboard.py` 重算、再手动打开 HTML，预警是"拉"出来的、非"推"过来的。供应链运维需要一个**常驻的前后台服务**：随时看最新齐套预警、一键触发重算、出现 🔴 真延期能主动推送，并把每个真延期跟踪到闭环（催货→协调→改期→确认）。这正是 supplychain 预警中心已验证的模式，现 FO/BOM/携客云三源均已外网可达，具备做成常驻服务的条件。

## What Changes

- **新增内网 Web 服务**（Flask + waitress，仿 supplychain `web_app.py`）：浏览器访问看板页，复用现有 `baoguan` 四色引擎与前端交互（筛选/搜索/排序/导出），不改判级语义。
- **看板页改为"壳页 + JSON API"**：`render_html` 演化为服务端壳页 + `GET /api/baoguan` 返回 JSON，前端 fetch 渲染（现有 JS 已是数据驱动，改造小）。
- **三合一刷新/触发**：① 定时后台自动刷新（重算并缓存 JSON+时间戳）；② 手动 `POST /api/refresh` 按钮（受携客云 1req/30s 限流，串行+提示）；③ 新增 🔴 真延期相比上次快照 → 去重后自动推企微保供运维群。页面默认读缓存，不每次开页打全量。
- **保供案例处置中心**：每个 🔴 真延期自动建案，**催货→协调→改期/确认**状态机 + SLA 滞留追踪 + 操作历史 + 手动建案，持久化到 SQLite。
- **AI 草稿**：为案例生成"催供应商答交 / 改期协调"草稿（有 Claude API 用、无则模板降级）。**对客改期通知草稿落对客闸 `CUSTOMER_OUTBOUND_ENABLED`（全程 False，仅生成入队、不外发）**。
- **不改**：`sc8.baoguan`（assess_supply_risk/build_dashboard/四色判级）、`sources`/`loaders` 取数语义；本次只在其上加服务/触发/案例/草稿层。

## Capabilities

### New Capabilities
- `baoguan-web-service`: 内网 Web 服务——服务看板壳页、`GET /api/baoguan`（读缓存 JSON）、`GET /api/ping` 健康检查、`POST /api/refresh` 手动重算、定时后台自动刷新 + 缓存（JSON+生成时间戳）、携客云限流的串行保护。
- `baoguan-alert-dispatch`: 真延期预警推送——每次刷新后比对上次快照，识别**新增** 🔴 真延期，去重（已推过/已建案的不重复推），推企微保供运维群（内部运维，非对客）。
- `baoguan-case-management`: 保供案例处置中心——🔴 真延期自动建案、催货/协调/改期/确认状态机、SLA 滞留追踪、操作历史、手动建案，SQLite 持久化；AI 催货/改期草稿生成（对客草稿落对客闸）。

### Modified Capabilities
<!-- 无：本次不改 baoguan 四色判级等既有规格行为，只在其上新增服务层 -->

## Impact

- **新增代码**（均在 `sc8/` 与 `scripts/`）：`webapp.py`（Flask 路由/服务/缓存/调度）、`case_store.py`（SQLite CaseStore + 状态机）、`case_draft.py`（AI/模板草稿）、看板壳页模板、案例页模板；`scripts/run_baoguan_web.py`（启动入口）。
- **复用/收割**：参考 supplychain `src/delay_case.py`（CaseStore 模式）与 `src/crm_notifier.py`（草稿 + API 降级）；复用 `sc8.baoguan`、`sc8.sources`、平台 `audit`、`notifiers/wecom`。
- **新依赖**：`flask`、`waitress`（生产 WSGI）；定时刷新用后台线程或 `APScheduler`（design 定）。
- **数据/红线**：缓存 JSON + 案例 SQLite **含真实客户名 → gitignore 不入库**；real 模式缺端点 **fail-loud**；所有保供/催货/状态变更写平台 `audit`（IATF 可追溯）；对客外发闸 `CUSTOMER_OUTBOUND_ENABLED` 全程 False。
- **运行/访问**：先 **LAN 自用**（绑 0.0.0.0，不加登录，内网信任）；**外网访问 + 鉴权列为后续待办 #10**（含真实客户名，外网必须加登录/Token）。
- **回归**：不改既有 `baoguan`/`sources`/`loaders` 语义，现有 75 测试不应退化；新增服务/案例/推送/草稿各自补测试。
