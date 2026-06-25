# Spec: baoguan-web-service

## Purpose

成品保供预警看板的常驻内网 Web 服务（SC8）：看板壳页 + JSON API + 健康检查 + 手动/定时刷新，
进程内复用 baoguan 四色引擎，缓存快照（reports/JSON），real 源 fail-loud。LAN 内部用，不对客。

---

## Requirements

### Requirement: 看板页与 JSON API
服务 SHALL 提供 `GET /` 返回成品保供预警看板页（壳页），并提供 `GET /api/baoguan` 返回当前缓存快照的 JSON（含成品行数组 + 生成时间戳 + 四色计数）。前端 SHALL 通过 fetch `/api/baoguan` 渲染，复用既有筛选/搜索/排序/导出交互，不重算判级。

#### Scenario: 打开看板页读缓存
- **WHEN** 用户浏览器访问 `GET /`
- **THEN** 返回看板壳页，且页面加载后 fetch `GET /api/baoguan` 取到最近一次缓存快照（含生成时间），不触发实时全量重算

#### Scenario: 无缓存时的首次状态
- **WHEN** 服务刚启动、尚无任何缓存快照
- **THEN** `GET /api/baoguan` 返回空数据 + 明确的"尚未刷新"状态，页面提示用户点击刷新或等待定时刷新，而非报错或返回 mock

### Requirement: 健康检查
服务 SHALL 提供 `GET /api/ping` 返回服务存活状态与当前时间。

#### Scenario: 健康探测
- **WHEN** 调用 `GET /api/ping`
- **THEN** 返回 `{"status":"ok"}` 与时间戳

### Requirement: 手动刷新与限流串行保护
服务 SHALL 提供 `POST /api/refresh` 触发一次重算（FO+BOM+携客云 → build_dashboard）。重算 MUST 串行执行：当一次刷新进行中时，并发的刷新请求 MUST 不并行打携客云（受 1req/30s 限流），而是返回"刷新进行中"或排队，且 MUST 不因并发触发重复外部调用。

#### Scenario: 触发手动刷新
- **WHEN** 用户点击刷新、发起 `POST /api/refresh`
- **THEN** 服务串行执行重算，完成后更新缓存快照与生成时间，并返回新快照或成功状态

#### Scenario: 刷新进行中的并发请求
- **WHEN** 一次刷新尚未完成、又来一个 `POST /api/refresh`
- **THEN** 服务不并行发起第二次外部取数，返回"刷新进行中"状态（不重复打携客云）

### Requirement: 定时后台自动刷新与缓存
服务 SHALL 支持后台定时自动刷新（间隔可配置），每次刷新 MUST 将结果缓存为 JSON 快照并记录生成时间戳。页面与 `GET /api/baoguan` 默认读缓存，MUST NOT 每次请求都打全量外部源。

#### Scenario: 定时刷新更新缓存
- **WHEN** 到达配置的刷新间隔
- **THEN** 后台自动重算并写入新缓存快照 + 时间戳，无需用户操作

### Requirement: 真实源 fail-loud 与数据红线
real 模式下任一真实源（FO/BOM/携客云）不可达时，刷新 MUST fail-loud（记录错误 + 不外发 mock 数据冒充真实），且 MUST 保留上一份有效缓存而非以空/假数据覆盖。缓存快照含真实客户名，MUST 仅落 gitignore 的 `reports/`，绝不入库。

#### Scenario: 刷新时真实源不可达
- **WHEN** 一次刷新中 FO 或 BOM 或携客云调用失败
- **THEN** 该次刷新报错并记录，保留上一份有效缓存快照，绝不用 mock 数据覆盖，也不对外返回伪造数据
