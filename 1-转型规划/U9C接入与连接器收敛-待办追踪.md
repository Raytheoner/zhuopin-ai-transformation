# U9C 接入与连接器收敛 —— 待办与决策追踪

> 用途：跟踪 U9C 真实接入过程中悬而未决的安全 / 架构 / 接入项，避免散落丢失。
> 背景：2026-06-11 探活确认 U9C 外网 webApi 鉴权=OAuth2（client_id/secret→JWT，无需 admin 密码）；外网代理仅暴露 `/webapi/OAuth2/AuthLogin` + `/webapi/BOM/Query`，`CommonEntity/Query` 外网 404。凭据应填入本仓库 `.env`（不入库），不再依赖已归档的 supplychain/.env。
> 更新：状态变化时手动更新本表；项目级进展见 CLAUDE.md。

---

## 待办项

| # | 项 | 类型 | 责任 | 优先级 | 状态 | 下一步 |
|---|----|------|------|--------|------|--------|
| 1 | **轮换 U9C client_secret** —— 明文写死在 `supplychain/scripts/spike_u9c_api.py`，已推 GitHub（归档仓 history 仍含），属暴露中的**活凭据**，能读真实 ERP | 安全 | IT（Paul 催办） | 🔴 最急 | ✅ 已完成（2026-06-22）—— secret 已轮换，新值生效、旧值已作废，暴露风险解除（信道 A1 TLS 校验已在 master，钥匙两道全落） | 冒烟全通：① 新值已填本仓库 `.env`（git check-ignore 确认未跟踪）；② CC 在 LAN 跑 `OAuth2/AuthLogin` 拿 JWT(540 字符)+`BOM/Query` S02Y.0162 = 117 行精确命中、failed=[]；旧 secret(`6ea9…682b`) 试登 = `认证失败:参数错误`（已废）。**剩余仅卫生项（可选，未阻塞）**：删 `supplychain/scripts/spike_u9c_api.py` 第 ~CLIENT_SECRET 默认值写死行（归档仓 history 仍含旧值，但旧值已作废、无危害） |
| 2 | **ZpConnector / U9CConnector 收敛**（方案 A：ZpConnector 唯一规范、退役 U9CConnector） | 架构 | — | — | ✅ 已完成（PR #9 合 master，2026-06-11） | 删 U9CConnector+4骨架测试、实体映射迁附录A、U9C_DATA_SOURCE 开关、real 模式 fail-loud（RealEndpointNotReadyError）、审计按端点分标；116 passed+1 skipped、SC8 回归零退化 |
| 3 | **外网代理开放 CommonEntity/Query + 专用端点** —— 决定 U9C 全量 cutover 能否离网做（库存 WhQoh / PO+Receivement / MO / 价格表 IQueryPurPriceListSRV 均走 CommonEntity，外网现 404） | 接入 | IT 评估 | 🟡 中 | ⬜ 待评估 | Paul 评估是否请 IT 在外网反代开放；否则这些 get_* 走 LAN/VPN。**注（2026-06-24）**：预测订单 FO **不靠开 CommonEntity 解决**——FO 实体名 U9C 文档全集亦无，开了通道也无从查；FO 的解是建卓品视图（见 #6 `ZpViewForecast`）。CommonEntity 外网开放仍只对库存/PO/MO/价格那几路有意义 |
| 4 | **DB 直连（192.168.6.2 / airead 弱口令）** —— 本轮外网不碰，到 LAN/VPN 阶段再启用并轮换弱口令 | 安全/接入 | IT/DBA | ⚪ 后置 | ⬜ 后置 | LAN/VPN 阶段提醒轮换 airead 口令 |
| 5 | **ZpConnector → ErpConnector 改名** —— 收敛后 ZpConnector 实为 U9C/ERP 规范连接器，名字有潜在混淆；触及 SC8 + 3 测试 import，本轮跳过避免 churn/撞 PR | 架构/可维护 | CC | ⚪ 后置 | ⬜ 后置 | 低峰期单独小 PR；同时清理仍提 u9c_connector 的文档引用（U9C-ERP-MCP接口申请.md、收割策略表①） |
| 6 | **正式库 FO 取数无外网路 → 请 IT 建卓品视图 `ZpViewForecast`**（根因已更正，2026-06-24） —— **更正前的误判**：原以为 FO 来自内网服务 `192.168.100.51:8800`（陈旧 5 月数据），并据此打算让 IT「刷新视图」。**Paul 澄清后的真相**：`192.168.100.49/.51` 是 **supplychain 验证库**，与本项目无关；AI-Tran 正式库（外网 `erp.equalitytec.com:4443` / 内网 `192.168.6.2:5555`）**只有 U9C webapi 一个面，没有直连 SQL 的 FO 服务**。而正式库 webapi **根本没有"查询预测订单"接口**（已扫 U9C 接口文档全集 100+ 接口，无 FO 查询接口；CommonEntity 外网 404 且 FO 实体名文档亦无；`/zp` 面无 FO 视图）。故 **SC8 旧 `.env` 把 `FO_API_BASE` 指到验证库 192.168.100.51:8800，取的是验证库 5 月数据——口径错了**。 | 接入 | Paul→IT | 🔴 高（阻塞保供看板接正式库真实 FO） | ✅ **已接通（2026-06-24）** —— IT 同日交付正式库接口（**实际形态与需求文档略异、更省事**：`GET /zp/api/ForecastOrder/Query`，鉴权用 **apiKey 走 URL query**、非 OAuth2、非 POST），全参数过滤 `docNo/itemCode/dateFrom/dateTo/status/page`，Swagger `/zp/swagger/ui/index`。CC 已改造 loaders（新端点/apiKey/分页/`Data.Rows`/字段名 `ItemCode·ItemName·CustomerName`，apiKey 不入异常日志、fail-loud），`.env` 改 `FO_API_BASE=https://erp.equalitytec.com:4443`+`FORECAST_API_KEY`（gitignore）。**真实跑通**：FO2026060001/2 共 126 行/36 成品（status=2 已审核）、携客云承诺覆盖 341/1042。保供看板四色口径上线（🔴 真延期 49/🟠 待催 77）。 | 收尾：① **apiKey 是只读 key**，留意是否需轮换（早前占位误贴已纠，现为真实值）；② FO 健康告警（接口 4xx/5xx 监控）仍待做，随对客上线前补；③ `ForecastOrder/Query` 的 `orgCode` 参数暂未传（默认组织即可），如需多组织再补 |
| 7 | **SC1 历史准时率数据源**（2026-06-18 定向，Paul 采纳）—— SC1 交付准时率（35% 权重、唯一 SRM 维度）应取"历史按时收货率"，但 SRM 供应计划看板是前瞻视图（窗口=今天→未来，未交付订单→0% 假象）、且查 >7 天前报 300234，**结构上做不到历史**。当前 0% 假象把供应商推成高风险（ZB0022→5 级极高失真） | 接入/正确性 | CC + IT | 🔴 高 | 🟡 过渡修正已实施（待真实源） | **过渡修正已实施（2026-06-18，commit cabc2e0）**：SC1 交付维度数据不足→不评分+其余权重重新归一化，ZB0022 5级→4级、0% 假象消除。**真实历史准时率仍待 U9C ERP 收货历史（Receivement）MCP（7/1 申请）接入** |
| 8 | XkySrmConnector.get_demand_orders 字段 bug —— 读 pdrNo，看板真实字段是 poErpNo → customer_order 恒空，影响 SC1"需求单→客户订单"映射 | 正确性/架构 | CC | 🟡 中 | ✅ 已修（PR #14，commit 7785c00，2026-06-18） | get_demand_orders 优先读 poErpNo（pdrNo 兜底兼容）；旧测试夹具也用 pdrNo 与 bug 同错而"通过"，已改真实字段 + 加 #8 回归；调用方排查无退化（get_pending_demands 仅用 status、get_customer_order_mapping 修后正确无外部调用方）；平台 138 全绿 |
| 9 | openspec sc5-purchase-recommendation 校验失败 —— spec 缺 SHALL/MUST 规范关键词，openspec validate 不通过 | 规范/技术债 | CC | ⚪ 低（非阻塞，预先存在，非本轮引入） | ⬜ 待办 | 下次触及 sc5 时结合需求意图补规范关键词（勿机械插入），使 validate 通过 |
| 10 | **保供看板 Web 化外网访问 + 鉴权**（Paul 2026-06-24 定）—— 保供预警 Web 服务先做 **LAN 自用**（不加登录）；待 LAN 跑通后，需开外网访问。因看板含**真实客户名**，外网开放**必须加登录/口令鉴权**（红线）。三源（FO apiKey / U9C BOM OAuth2 / 携客云）均已外网可达，服务本身可脱 VPN 跑，缺的只是鉴权层 | 接入/安全 | CC（Paul 跑通后触发） | 🟡 中（LAN MVP 之后） | 🔧 **LAN 版代码已落地（2026-06-24，openspec `sc8-baoguan-web-console` apply 完成）**：Flask+waitress 服务（`sc8/webapp.py`+`scripts/run_baoguan_web.py`，默认 `0.0.0.0:8090` 无鉴权）、进程内 compute_snapshot+SnapshotStore 缓存、手动刷新(非阻塞锁串行)+6h 定时后台刷新、🔴 真延期去重推保供运维群、保供案例处置中心(催货→协调→改期/确认→关闭,SQLite)、AI 催货/协调/对客草稿(对客落闸不外发)。**102 passed/2 skipped**，reports/*.db/*.json/.env 均 gitignore。**未结**：① 7.2 LAN 真实联调 = Paul 现场验收（手动刷新打真实三源、🔴 会推企微运维群）；② 验收通过后 **提醒 Paul** → 加登录/Token 鉴权再开外网（含真实客户名红线） |

---

## 已确认（不再是待决策）

- 鉴权方式 = **OAuth2（client_id/secret → JWT → header token）**，无需 U9C_API_PASSWORD。
- 外网 `BOM/Query` 可拉真实 BOM（样例母件 S02Y.0162，117 行直接子件已验证）。
- U9C 凭据归位本仓库 `.env`（**base 为 host-only `https://erp.equalitytec.com:4443`，不带 `/U9C`** —— 收敛到 ZpConnector 后由它自拼 `/U9C` 与 `/zp`，带 `/U9C` 会双拼 404），`.env` 已 gitignore、无 `.env` 被 git 跟踪。
- 收敛方案 = A（ZpConnector 唯一规范 ERP 连接器，退役并删除 U9CConnector 骨架；实体映射迁入 ZpConnector CommonEntity TODO / 收敛设计附录 A）。
- 审计来源按实际端点分标：BOM=`U9C_webapi`、PO/物料=`zp_ERP`、回退=`CSV_mock`，不混一个。
- **real 模式策略：缺真实端点的方法默认 fail-loud（不静默回退 mock）**；CSV 回退仅用于整体 `U9C_DATA_SOURCE=mock`；混合需显式 opt-in 且对客/L2 路径禁吃 mock。
- **SC8 承诺交期取数口径（2026-06-18，Paul 采纳）**：分层取数——主源 `/purchase/answer` 按 PO（权威承诺交期）、辅助看板、兜底"无反馈+30"启发式。起因：黄金基准真实跑发现看板仅覆盖 15-29% 子件→全低置信。详见《SC8上线前置门禁》§4.6。（2026-06-18 已实施+验证，commit cabc2e0：分层取数提覆盖 9/90→58/90 等；暴露 S02Y.0188 瓶颈子件真实承诺 2026-11-30 → 延期 +61→+184，纠正看板低估，作真实风险信号待 PMC 核）。
- **SC1 历史准时率源（2026-06-18，Paul 采纳）**：弃用 SRM 看板（前瞻视图 + 查 >7 天前报 300234，做不到历史）；目标源 = U9C ERP 收货历史（Receivement，等 U9C MCP）；过渡期数据不足"不评分/剔除维度重新归一化"，不用 0% 假象。详见待办 #7。

---

*关联：`openspec/changes/sc8-real-data-cutover/`、CC 记忆 project-u9c-external-webapi、CLAUDE.md §7 红线、`0-学习与工具/U9C-ERP-MCP接口申请.md`。*
