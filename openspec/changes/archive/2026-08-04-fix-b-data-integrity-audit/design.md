# Design — 变更包 B：数据正确性与审计强制化 P1

> 审 design 重点：**【需 Paul 拍板】** 处为停审点（B3 最重，B1/B4 次之）。其余为实现细节。
> 本包分支 `fix/b-data-integrity-audit` 叠在 `fix/a-security-compliance-p0` 之上（含 A 的外发旁路修复与第二道总开关）。

## B1 · BOM 拉取静默吞错（`erp_connector/connector.py`）

### 现状
`get_bom_for_products._fetch`（约 L431）单品 `except Exception: return` → 静默丢弃失败子件，返回**残缺 BOM 无错误信号**；`get_bom()`（约 L475）真实空时直接 `return self._fallback.get_bom()`，**不走** `_fallback_or_failloud` 闸门，real+allow_mock_fallback 下 mock BOM 混入且审计标 `CSV` 而非 `CSV_mock`。

### 设计
1. `_fetch` 捕获异常时把 `code` 计入**失败集合**（线程安全），不再静默吞。
2. `get_bom_for_products` 返回 `(rows, failed_ids)`：
   - 部分失败 → 返回已得 rows + failed_ids，并 `audit.trace(source="U9C_webapi", action="bom_partial_failure")` 留痕；
   - **全部失败**（请求过但无一成功且有失败）→ 抛 `RuntimeError`（带失败明细），绝不返回空当成功。
3. `get_bom()`：真实 rows 为空 → 走 `_fallback_or_failloud("get_bom", self._fallback.get_bom, reason=...)`（real 未 opt-in → fail-loud；opt-in → CSV_mock + warn）。

> **【需 Paul 拍板 B1】** `get_bom_for_products` 返回签名 `list[BomRow]` → `(rows, failed_ids)` 会波及 `get_bom`/`sources.load_real_bom` + 4 处测试。
> - **选项 A（推荐，faithful）**：直接改签名为 `tuple[list, list]`，本包内更新全部 6 处调用方（`get_bom` 解包；`load_real_bom` 解包并对 failed_ids 告警；4 测试解包）。语义最清晰，与报告"部分失败返回 (rows, failed_ids)"一致。
> - **选项 B（少波及）**：保留 `get_bom_for_products()->list`，新增 `get_bom_for_products_checked()->(rows,failed_ids)`，旧方法委托新方法只取 rows。调用面小但留两个口，未来易误用旧的（静默回归）。
>
> 推荐 **A**。tasks 按 A 写。

## B2 · SRM 承诺交期吞错（`srm_connector/connector.py:get_confirmed_dates`）

### 现状
单 PO `except Exception: pass`（L295）→ "查询失败"与"供应商未答交（返回 None）"无法区分，在途三色清单漏报延期。无生产调用方（仅定义），ripple 小。

### 设计
保持返回 `dict[po → date]` 向后兼容，**新增失败清单**：方法返回 `(confirmed: dict, failed_pos: list[str])`，单 PO 异常 → 计入 `failed_pos` + `audit.trace(source="SRM", action="confirmed_date_query_failed", target=po)`；"未答交"（`get_confirmed_date` 返回 None）**不计失败**（正常业务态）。

> 注：与 B1 同理涉及签名变更，但本方法无生产调用方，仅需更新其自身测试（若有）。沿用 (结果, 失败清单) 二元组与 B1 一致风格。

## B3 · 审批授权分级（`pending_queue.py` + SC8 config）

### 现状
`approve(item_id, confirmed_by, notifier)`（L75）只校验 `confirmed_by` 非空，**任意非空字符串**即可放行；SOP 要求重点客户 / 关联金额>50万 / 首次承诺须升 VP 级复核，未落地。A 包已让 approve 经 Notifier 受第二道总开关约束（总开关关→不外发），本包补**确认人级别**校验。

### 设计
- SC8 `config.py` 新增白名单（**配置即策略**，改 config 不改逻辑）：
  - `VP_APPROVERS: set[str]`（VP 级确认人姓名/工号白名单，运营维护）；
  - `KEY_CUSTOMERS: set[str]`（重点客户，默认 OEM：比亚迪/上汽/理想）。
- 队列项新增字段 `required_level`（`"vp"` | `"l2"`）。**入队时**由 SC8 计算并写入：命中 重点客户 / 首次承诺 / 关联金额>50万 任一 → `"vp"`，否则 `"l2"`。
- `approve`：若 `required_level=="vp"` 且 `confirmed_by ∉ VP_APPROVERS` → 拒绝放行（返回 False，保持 pending，audit 记 `approval_denied_insufficient_level`）；否则照常（仍受 A 包总开关与幂等约束）。

> **【需 Paul 拍板 B3-a】** SC8 队列里"关联金额>50万"如何取？SC8 数据面是**交付日期**，`DeliveryForecast`/`SalesOrder` 当前**不带订单金额**。
> - **选项 A（推荐）**：SC8 内 `required_level` 由 **首次承诺 + 重点客户** 两条驱动（均可在 SC8 算）；"关联金额>50万"在 SC8 暂不可得 → 记 `amount_unknown`，留待 IT 补订单金额字段或由 SC5（有金额）侧承接。不臆造金额。
> - **选项 B**：本包给 `SalesOrder`/FO loader 增订单金额字段并贯通（FO API 是否返回金额需确认；范围更大）。
>
> 推荐 **A**（不臆造、不放量）。

> **【需 Paul 拍板 B3-b】** 重点客户范围：默认 `KEY_CUSTOMERS = {比亚迪, 上汽, 理想}`（即所有 OEM 均重点 → 实际上 SC8 对客承诺几乎都要 VP）。是否如此从严？
> - **选项 A（推荐，从严）**：三家 OEM 全列重点 → 对客交付承诺默认都需 VP 确认（符合"对客发送=高风险"基调；反正总开关未开，先把分级骨架立起来）。
> - **选项 B**：`KEY_CUSTOMERS` 先留空（仅"首次承诺"触发 VP），由 Paul 后续填重点客户清单。
>
> 推荐 **A**。VP 白名单 `VP_APPROVERS` 初值建议先放 Paul 一人（运营维护）。

## B4 · 审计强制化（`from_env` + SC8 接入）

### 设计
- `ZpConnector.from_env` / `XkySrmConnector.from_env`：`audit is None` → `warnings.warn("生产构造未注入 audit，连接器访问将不留痕", UserWarning)`（**不抛错**，保留向后兼容与离线测试可用）。
- SC8 `sources.py`：`load_real_bom` / `load_srm_deliveries` 构造连接器时注入 `ConnectorAudit`（sink 指向 SC8 access-trace JSONL）；`loaders.load_forecast_orders_from_api` 增可选 `audit` 参数，`urlopen` 成功/失败后 `audit.trace(source="FO", action="forecast-orders")`。

> **【需 Paul 拍板 B4】** `from_env` audit 缺失时 **warn（推荐）** 还是 **raise**？
> - **选项 A（推荐）warn**：不破坏现有 `from_env()` 无参调用与测试；生产忘注入会在日志告警。报告原文即"至少 warnings.warn"。
> - **选项 B raise**：更硬，但会立即破坏现有多处 `from_env()` 无参调用（含测试），需逐一改造，超出 surgical 范围。
>
> 推荐 **A**。

## B5 · OEM 隔离违规留痕（`data_isolation_layer/router.py`）

### 设计
`OEMRouter.__init__` 增可选 `audit: AuditLogger | None`。`resolve`（未注册 OEM 拒绝）与 `guard`（跨库拒绝）抛 `CrossOEMAccessError` **前**写 `AuditEvent(scenario="DATA_ISOLATION", action="cross_oem_access_denied", decision={oem, collection, reason})`。`resolve` 覆盖"未注册"路径；`guard` 覆盖"跨客户"路径（guard 调 resolve，未注册在 resolve 内已记，避免重复）。无 audit 注入时仅抛错（向后兼容）。

## B6 · kit_engine 在途盲区 + SC5 黄金值（`agents/kit_engine.py` / SC5 测试）

### 现状
`calc_shortage`（L66-71）：`available` 仅当 `inv` 存在才计算，含 `in_transit`；物料**不在库存快照**时 `available=0`，**在途被忽略** → 缺口虚高。`ZpConnector.get_inventory` 真实切换后恒返回 0 库存项 → 必踩。

### 设计
```python
for material_id, need in gross.items():
    inv = inv_index.get(material_id)
    on_way = in_transit.get(material_id, 0)
    if inv is not None:
        available = inv.current_stock - inv.safety_stock + on_way
    else:
        available = on_way            # 缺快照：在途仍计入（不再忽略）
        missing_snapshot.append(material_id)   # 告警清单
    gap = need - available
    if gap > 0:
        shortages[material_id] = gap
```
返回签名：保持 `calc_shortage -> dict[str,float]` 向后兼容；缺快照告警清单通过**新增可选 out 机制**暴露——拟改为返回 `(shortages, missing_snapshot)` 或新增 `calc_shortage_with_warnings`。

> **【需 Paul 拍板 B6】** kit_engine 是底座件（O2 + SC5 两消费方，rule-of-three 已触发）。`calc_shortage` 暴露缺快照告警：
> - **选项 A（推荐）**：改签名 `-> (shortages, missing_snapshot)`，更新 O2/SC5 调用方与测试（本包内）。与 B1 风格一致。
> - **选项 B**：保留 `calc_shortage->dict`，新增 `calc_shortage_checked()->(dict,list)`，旧的委托。少波及但留两口。
>
> 推荐 **A**（一致）。**SC5 黄金值**：`auto_total/review_total/grand_total` 注释即整数和（35850/640000/675850），改 `== 35850` 精确相等可行；若实际算出非整数（浮点累乘）导致无法精确相等，**停下报告原因，不放宽断言**（按任务要求）。

## 不在本包范围
报告 §7 P0（包 A，已 PR#10）、C1/C2（包 C）、P2（#13/#16-#20/#22-#24 等）。
