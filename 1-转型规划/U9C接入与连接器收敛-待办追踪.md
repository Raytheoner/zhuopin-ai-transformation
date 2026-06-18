# U9C 接入与连接器收敛 —— 待办与决策追踪

> 用途：跟踪 U9C 真实接入过程中悬而未决的安全 / 架构 / 接入项，避免散落丢失。
> 背景：2026-06-11 探活确认 U9C 外网 webApi 鉴权=OAuth2（client_id/secret→JWT，无需 admin 密码）；外网代理仅暴露 `/webapi/OAuth2/AuthLogin` + `/webapi/BOM/Query`，`CommonEntity/Query` 外网 404。凭据应填入本仓库 `.env`（不入库），不再依赖已归档的 supplychain/.env。
> 更新：状态变化时手动更新本表；项目级进展见 CLAUDE.md。

---

## 待办项

| # | 项 | 类型 | 责任 | 优先级 | 状态 | 下一步 |
|---|----|------|------|--------|------|--------|
| 1 | **轮换 U9C client_secret** —— 明文写死在 `supplychain/scripts/spike_u9c_api.py`，已推 GitHub（归档仓 history 仍含），属暴露中的**活凭据**，能读真实 ERP | 安全 | IT（Paul 催办） | 🔴 最急 | ⬜ 待办 | Paul 找 IT 轮换旧值（删脚本行不够，history 还在）；轮换后更新本仓库 `.env` |
| 2 | **ZpConnector / U9CConnector 收敛**（方案 A：ZpConnector 唯一规范、退役 U9CConnector） | 架构 | — | — | ✅ 已完成（PR #9 合 master，2026-06-11） | 删 U9CConnector+4骨架测试、实体映射迁附录A、U9C_DATA_SOURCE 开关、real 模式 fail-loud（RealEndpointNotReadyError）、审计按端点分标；116 passed+1 skipped、SC8 回归零退化 |
| 3 | **外网代理开放 CommonEntity/Query + 专用端点** —— 决定 U9C 全量 cutover 能否离网做（库存 WhQoh / PO+Receivement / MO / 价格表 IQueryPurPriceListSRV 均走 CommonEntity，外网现 404） | 接入 | IT 评估 | 🟡 中 | ⬜ 待评估 | Paul 评估是否请 IT 在外网反代开放；否则这些 get_* 走 LAN/VPN |
| 4 | **DB 直连（192.168.6.2 / airead 弱口令）** —— 本轮外网不碰，到 LAN/VPN 阶段再启用并轮换弱口令 | 安全/接入 | IT/DBA | ⚪ 后置 | ⬜ 后置 | LAN/VPN 阶段提醒轮换 airead 口令 |
| 5 | **ZpConnector → ErpConnector 改名** —— 收敛后 ZpConnector 实为 U9C/ERP 规范连接器，名字有潜在混淆；触及 SC8 + 3 测试 import，本轮跳过避免 churn/撞 PR | 架构/可维护 | CC | ⚪ 后置 | ⬜ 后置 | 低峰期单独小 PR；同时清理仍提 u9c_connector 的文档引用（U9C-ERP-MCP接口申请.md、收割策略表①） |
| 6 | **FO 服务 LAN-only + 健康监控** —— FO（客户订单）是内网服务 `192.168.100.51:8800`，仅 LAN/VPN 可达（独立于 U9C/SRM 外网）；SC8 黄金基准真实跑取数需回 LAN/VPN。且 FO 502 会让对客上线后悄悄断供 | 接入/运维 | Paul→IT | 🟡 中 | ✅ 黄金基准已跑（2026-06-18，FO 恢复后全真实跑通、偏差0）；FO 健康告警仍待办 | FO 告警：作为带 mock 的单独小 PR（内部运维告警推采购/值班群，非对客，低风险），下轮 CC 做 |
| 7 | **SC1 历史准时率数据源**（2026-06-18 定向，Paul 采纳）—— SC1 交付准时率（35% 权重、唯一 SRM 维度）应取"历史按时收货率"，但 SRM 供应计划看板是前瞻视图（窗口=今天→未来，未交付订单→0% 假象）、且查 >7 天前报 300234，**结构上做不到历史**。当前 0% 假象把供应商推成高风险（ZB0022→5 级极高失真） | 接入/正确性 | CC + IT | 🔴 高 | 🟡 过渡修正已实施（待真实源） | **过渡修正已实施（2026-06-18，commit cabc2e0）**：SC1 交付维度数据不足→不评分+其余权重重新归一化，ZB0022 5级→4级、0% 假象消除。**真实历史准时率仍待 U9C ERP 收货历史（Receivement）MCP（7/1 申请）接入** |
| 8 | XkySrmConnector.get_demand_orders 字段 bug —— 读 pdrNo，看板真实字段是 poErpNo → customer_order 恒空，影响 SC1"需求单→客户订单"映射。SC8 分层已直接读 poErpNo 绕开，连接器未改 | 正确性/架构 | CC | 🟡 中 | ⬜ 待办 | 单独小 PR：改 get_demand_orders→poErpNo + 排查所有调用方 + 加回归测试，确认无退化 |

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
