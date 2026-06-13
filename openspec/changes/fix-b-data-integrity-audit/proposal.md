## Why

《全盘审计与差距分析报告-2026-06-13》§2/§3 列出一组 **P1 数据正确性与审计强制化**缺陷——多为 SC8 对客 L2 签字前置项。核心风险：**静默吞错让接入"看起来成功"实际残缺**（BOM 单品失败 → 齐套虚低 → 漏报缺料 → 直接威胁对客承诺交期正确性），以及**审计可选注入**让"所有 AI 决策写 audit"红线靠自觉维持。本变更包修复 6 项（B1–B6），独立 PR，**叠在变更包 A 之上**（A 已封死外发旁路 + 第二道总开关，B3 审批人分级建立其上）。

## What Changes

- **B1（报告#5）BOM 拉取静默吞错**（`erp_connector/connector.py:get_bom_for_products`）：单品 `except: return` 改为**收集失败清单**——部分失败返回 `(rows, failed_ids)` + audit 留痕；**全失败抛错**（带失败明细），不返回残缺 BOM。`get_bom()` 的 CSV 回退分支接入 `_fallback_or_failloud` 闸门（消除 real+allow_mock_fallback 下 mock BOM 混入且审计标 `CSV`（而非 `CSV_mock`）的旁路）。
- **B2（报告#6）SRM 承诺交期吞错**（`srm_connector/connector.py:get_confirmed_dates`）：单 PO `except: pass` 改为**区分"查询失败"与"供应商未答交"**——失败 PO 清单返回 + audit error 留痕，使在途三色清单不再漏报延期风险。
- **B3（报告#9）审批授权分级**（`pending_queue.py`）：`approve` 路径已经 A 包的 Notifier 第二道总开关结构性约束；本包补**审批人分级**——重点客户 / 关联金额>50万 / 首次承诺的队列项要求 **VP 级确认人**（白名单走配置文件）；队列项记录"所需审批级别"，approve 校验确认人级别达标才放行。
- **B4（报告#10）审计强制化**：连接器/Notifier `from_env` 生产构造路径 **audit 必传或 fail-loud**（`audit=None` → `warnings.warn`）；SC8 `sources.py` 的 `ZpConnector.from_env`/`XkySrmConnector.from_env` 注入 `ConnectorAudit`；`loaders.py` FO 拉取（`urlopen`）补访问层审计痕迹（`source=FO`）。
- **B5（报告#11）OEM 隔离违规留痕**（`data_isolation_layer/router.py`）：`CrossOEMAccessError` 抛出**前**写 `AuditEvent`（违规企图留痕），消除与 docstring"必须审计"的自相矛盾。规范依据 `3-治理与合规/OEM数据隔离规范.md` §3.2（Cowork 已建，只读参照）。
- **B6（报告#21）kit_engine 在途量盲区**（`agents/kit_engine.py:calc_shortage`）：物料不在库存快照时**在途量被忽略 → 缺口虚高**；改为 `available = 库存项贡献 + 在途`（缺快照时在途仍计入），并对缺快照物料输出**告警清单**。SC5 黄金值金额断言 `pytest.approx(rel=0.01)` → **精确相等**（值为整数和，精确可行）。

## Capabilities

### Modified / Added Capabilities
- `platform-data-connectors`：BOM 部分失败显式信号 + get_bom 回退闸门（B1）；SRM 承诺交期失败/未答交区分（B2）；`from_env` 审计 fail-loud（B4）。
- `delivery-commitment-gate`：审批授权分级（VP 级确认人白名单）（B3）。
- `platform-oem-isolation`：跨 OEM 访问拒绝前写审计（B5）。
- `platform-kit-engine`：在途量盲区修复 + 缺快照告警（B6）。

## Impact

- **平台底座**：`erp_connector`（BOM）、`srm_connector`（承诺交期）、`audit`/`connector_audit`（fail-loud）、`data_isolation_layer/router.py`（留痕）、`agents/kit_engine.py`（在途）。
- **SC8 工程**：`sources.py`/`loaders.py`（注入审计 + FO 访问留痕）、`pending_queue.py`（审批分级）。
- **SC5 工程**：黄金值断言改精确相等（不改业务逻辑）。
- **接口变更**：`get_bom_for_products` 返回签名由 `list[BomRow]` → `(rows, failed_ids)`（影响 `get_bom`/`load_real_bom` + 4 处测试，本包内一并更新）。
- **合规红线**：强化 CLAUDE.md §7.2（决策写 audit）/§7.3（OEM 隔离）/§7.4（L2 分级确认）。
- **off-LAN**：全部以 mock/单测验证；真实 BOM/SRM 部分失败路径用注入式假响应覆盖，不需真实端点。
