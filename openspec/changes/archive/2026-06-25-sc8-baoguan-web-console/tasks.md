## 1. 依赖与计算服务底座

- [x] 1.1 SC8 加依赖 `flask`、`waitress`（pyproject/requirements），`pip install -e` 验证可导入
- [x] 1.2 新增 `sc8/baoguan_service.py::compute_snapshot(*, today, status, audit) -> Snapshot`：封装 `load_real_orders + load_real_bom + load_srm_deliveries + build_dashboard`，返回 rows(序列化) + 生成时间 + 四色计数；real 缺端点 fail-loud（复用 sources，不回退 mock）
- [x] 1.3 `SnapshotStore`（内存 + 持久化 `reports/baoguan_snapshot.json`，gitignored）：`get()`/`set()`/启动时从 JSON 恢复；确认 `reports/` 已 gitignore
- [x] 1.4 单测：compute_snapshot 用 mock 源产出 Snapshot 结构正确；SnapshotStore 存取 + 重启恢复（临时目录）

## 2. Flask 服务 + 刷新触发（capability: baoguan-web-service）

- [x] 2.1 `sc8/webapp.py`：`GET /api/ping`（存活+时间）；`GET /api/baoguan`（读 SnapshotStore，无缓存→"尚未刷新"态，不打全量）
- [x] 2.2 `POST /api/refresh`：全局非阻塞 `threading.Lock`，拿到→后台/串行重算并更新缓存；拿不到→返回"刷新进行中"（不并行打携客云）
- [x] 2.3 定时后台守护线程：按 `SC8_BAOGUAN_REFRESH_MIN`(默认 360) 循环重算，与手动共用同一把锁（拿不到则跳过本轮）
- [x] 2.4 `GET /`：服务看板壳页（见 §5）；real fail-loud 时保留上一份有效缓存、绝不以空/假覆盖
- [x] 2.5 测试：ping/baoguan(空缓存态)/refresh(串行锁——并发第二次返回"进行中"不重复取数，用 monkeypatch 计数外部调用)

## 3. 真延期识别 + 去重推送（capability: baoguan-alert-dispatch）

- [x] 3.1 `detect_new_red(curr, prev) -> list`：按稳定键 `(item_code, fo_id, ship_date)` 比对，识别新增 🔴 真延期（既有真延期不算新增）
- [x] 3.2 推送：新增真延期 → 经 §4 案例去重后，对未建案者推企微保供运维群（内部口径：料号/确定瓶颈子件/确定延期天数），写 audit；已推/已建案不重复推
- [x] 3.3 测试：新增真延期触发一次推送（patch wecom 捕获）；同一真延期再次刷新不重复推；推送写 audit

## 4. 保供案例处置中心（capability: baoguan-case-management）

- [x] 4.1 `sc8/case_store.py`：收割 supplychain `delay_case.py` CaseStore 骨架→保供语义；SQLite（cases + events 表，gitignored）；状态机 催货→协调→改期/确认→关闭（enum + NEXT_STATUS + SLA_HOURS 24/48/72）
- [x] 4.2 自动建案：新增真延期且无未关闭案例→建案(初态 催货)+写 audit；已有未关闭案例不重建（与 §3.2 去重统一）
- [x] 4.3 `advance_status`/`resolve`/`get_stale_cases`（超 SLA）/`create_case`(手动)/append-only events；每次状态变更写 audit
- [x] 4.4 路由：`/cases` 列表(待处置/超SLA/已关闭 + 滞留时长)、`/cases/<id>` 详情+推进表单(操作人/备注校验合法顺序)、`/cases/new` 手动建案
- [x] 4.5 测试：自动建案幂等(同键不重建)、状态机合法/非法流转、SLA 滞留标记、手动建案、events 留痕

## 5. 前端壳页（capability: baoguan-web-service）

- [x] 5.1 `render_shell()`：复用现有 `_HTML_STYLE`/`_HTML_JS`，DATA 改为启动时 fetch `/api/baoguan`（非嵌入）；保留筛选/搜索/排序/导出
- [x] 5.2 新增"刷新"按钮(调 `/api/refresh`+loading 态+完成后重 fetch)、"最后更新时间"显示、案例入口链接(🔴 卡片→对应案例)
- [x] 5.3 CLI 静态 `render_html` 保留不动（离线产物仍可用，与壳页共享 style/JS 片段）
- [x] 5.4 测试：壳页含 fetch `/api/baoguan` 引导、刷新按钮、不含嵌入真实数据（壳页本身无客户名）

## 6. AI 草稿（capability: baoguan-case-management）

- [x] 6.1 `sc8/case_draft.py::generate(case, events, *, kind)`：kind=催货/协调=内部直接生成；有 `ANTHROPIC_API_KEY` 调 Claude(最新模型) 否则模板降级（参考 crm_notifier）
- [x] 6.2 对客改期通知草稿：MUST 落 `CUSTOMER_OUTBOUND_ENABLED`(全程 False)——仅入草稿态、绝不自动外发；路由 `/cases/<id>/draft?kind=`
- [x] 6.3 测试：内部草稿生成(无 key→模板)、对客草稿在闸关时不外发(只返回草稿态)

## 7. 启动入口 + 联调 + 收尾

- [x] 7.1 `scripts/run_baoguan_web.py`：载 `.env`、要求 `SC8_DATA_SOURCE=real`、注入 ConnectorAudit/AuditLogger、waitress 绑 `0.0.0.0:PORT`(默认 8090)、Windows GBK→UTF-8 输出
- [x] 7.2 LAN 真实联调（**Paul 现场验收通过 2026-06-25**：手动刷新打真实三源、🔴 真延期推保供运维群、建案+案例推进+草稿均验证）：启动→打开看板→手动刷新出真实四色→验证建案+企微推送(去重)→案例推进+草稿
- [x] 7.3 全套回归：既有 75 → **102 passed / 2 skipped**（+27 新测试全绿，零退化）；`.env`/`reports`/`*.db` 经 git check-ignore 确认不入库
- [x] 7.4 `openspec validate`、更新 CLAUDE.md 进度块 + 待办（#10 外网鉴权随此项；提醒 Paul LAN 跑通后做外网）；commit
- [x] 7.5 **提醒 Paul**：LAN 版跑通后，决策外网访问 + 登录/Token 鉴权（待办 #10，含真实客户名红线）
