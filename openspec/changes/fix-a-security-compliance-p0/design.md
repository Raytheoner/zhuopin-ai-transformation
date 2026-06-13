# Design — 变更包 A：安全与合规 P0

> 审 design 重点：本文件标 **【需 Paul 拍板】** 处即 §4 工作流要求的停审点。其余为修复实现细节。

## A1 · TLS 校验恢复

### 现状
`erp_connector/connector.py:70-73`：
```python
_CTX = ssl.create_default_context()
_CTX.check_hostname = False
_CTX.verify_mode = ssl.CERT_NONE
```
模块级单例 `_CTX` 被 `_http_get` / `_zp_post` / `_u9c_bom_post` 三处 `urlopen(..., context=_CTX)` 共用，覆盖**包括携带 `client_secret` 的 AuthLogin 在内**的全部 U9C 公网请求。对照 `srm_connector` 用默认 context（不传 `context=`，即校验开启）——证明默认校验在本环境可行，CERT_NONE 是收割自 supplychain 的遗留。

### 设计
1. 删除 `check_hostname=False` 与 `verify_mode=CERT_NONE`，默认 `ssl.create_default_context()`（校验+主机名校验开启）。
2. 显式逃生开关 `U9C_TLS_INSECURE`（env，默认关）：仅当 `=1/true/yes` 时关闭校验，用于 IT 提供受信证书前的 LAN 应急。开启时：
   - `warnings.warn(..., UserWarning)`（每进程一次即可，避免刷屏）；
   - 经注入的 `ConnectorAudit` 写一条 `source="TLS_INSECURE"` 痕迹（`audit=None` 时仅 warn）——留痕"曾以不安全模式连过 ERP"。
3. **不把 context 做成模块级常量**（否则 env 在 import 时即固化、测试难注入）。改为实例化时按 env 计算 `self._ctx`，三处 `urlopen` 改用 `self._ctx`。
4. 证书 pin（`load_verify_locations` 指向 IT 提供的服务器证书）**留接口位**：`U9C_TLS_CAFILE` env 可选；本包不强制（IT 未必本周给证书），先恢复默认校验这一最关键动作。

> **【需 Paul 拍板 A1】** 逃生开关默认值与告警强度：推荐 **默认安全（校验开）、`U9C_TLS_INSECURE=1` 才放行 + 每次构造 warn + audit 留痕**。是否还要把"不安全模式下禁止 `data_source=real`"也做成硬约束（即 real 模式强制证书校验、逃生开关只在 mock 生效）？推荐**是**（real=对客权威路径，绝不允许裸信道）。

## A2 · 封死对客自动外发旁路

### 现状与根因
- `gate.evaluate` 对高置信+非首次+不晚于目标日的预测返回 `requires_confirmation=False`。
- `submit_commitment` 用该值建草稿后 `notifier.send(draft)`（无 `confirmed_by`）。
- `Notifier.send` 仅拦截 `high_risk and not confirmed_by`；低风险（`requires_confirmation=False` 且 `severity` 非 critical）→ `_is_high_risk=False` → **直发** `_send_fn`，全程不查 `CUSTOMER_OUTBOUND_ENABLED`。
- 生产 `run.py` 走 `route_forecast`（恒入队、不调 `submit_commitment`）→ 旁路休眠；但 `test_low_risk_auto_sends` 正向固化为"低风险自动放行外发"。

### 设计（两道独立闸门，缺一不可）

**闸门①（场景层，policy）—— `submit_commitment` 首道一律入队。**
首道对客承诺**一律**需 L2 人工确认后才可外发，与全局总开关是否开启**无关**（即便将来 `CUSTOMER_OUTBOUND_ENABLED=True`，新承诺仍先入队、经 `approve` 才发）。实现：建草稿时 `requires_confirmation=True`（policy 恒真），`severity`/`reasons` 仍取 `gate.evaluate` 真实值写审计；草稿经 `Notifier.send` 必被 fail-closed 拦截入队。`CommitmentResult.requires_confirmation` 字段保留 gate 的**真实风险判定**（用于审计/展示），与"首道恒入队"的 policy 解耦。

**闸门②（平台层，结构性）—— `Notifier.send` 第二道总开关。**
`Notifier.__init__` 新增 `outbound_enabled: bool | Callable[[], bool] = True`（**默认放行**，不影响内部企微/通用通知器）。`send()` 拦截判定改为：
```python
high_risk = self._is_high_risk(message)
outbound_ok = self._outbound_enabled()        # 注入策略求值（callable 或 bool）
blocked = (high_risk and not confirmed_by) or (not outbound_ok)
```
被拦截时入 `pending_sink`，reason 区分 `awaiting_L2_confirmation` 与 `customer_outbound_disabled`。语义：**总开关关闭 → 即便带 `confirmed_by`（人工 approve）也不外发**，只入队留痕。这正是报告 P1-B（approve 路径不查总开关）的结构性堵口——在平台层一次解决。

> **【需 Paul 拍板 A2】** `build_notifier`（SC8 对客通知器工厂）是否**默认**把 `outbound_enabled` 接到 `config.CUSTOMER_OUTBOUND_ENABLED`？
> - **选项 A（推荐，结构性默认安全）**：`build_notifier` 默认 `outbound_enabled=lambda: config.CUSTOMER_OUTBOUND_ENABLED`。后果：构造任何 SC8 对客通知器都自带总开关，approve 也受其约束——最贴合报告"要结构性、不靠自觉"主旨。代价：验证"approve→真发"机制的门禁/队列测试需显式 `outbound_enabled=True`（或 monkeypatch config）才能跑放行路径——这些是与本审计项**直接相关**的 SC8 门禁测试，改动在 surgical 范围内。
> - **选项 B（改动最小）**：`build_notifier` 默认 `True`，仅生产审批入口显式注入 config 值。后果：测试churn最小（只改 `test_low_risk`），但结构性保证依赖调用方记得注入——偏"靠自觉"，与报告主旨相悖。
>
> 推荐 **A**。下方 tasks 按 A 编写；若选 B，删去对 `test_blocked_then_approved_sends`/`_seed_prior_send`/`test_pending_queue` 的 `outbound_enabled=True` 注入即可。

### 受影响测试（按选项 A）
- `test_low_risk_auto_sends` → **改写**为"低风险也入队"：`res.sent is False`、队列 +1、`sends == []`；保留 `res.requires_confirmation is False`（真实风险仍为低）。
- `test_blocked_then_approved_sends` / `_seed_prior_send` / `test_pending_queue.py` 的"approve→发"用例 → 注入 `outbound_enabled=True`（或 monkeypatch `config.CUSTOMER_OUTBOUND_ENABLED=True`）以验证放行机制本身。
- 新增 `test_outbound_switch_blocks_even_approved`：总开关关闭时，approve 带 `confirmed_by` 仍不外发、入队 reason=`customer_outbound_disabled`。

## A3 · 审计链 genesis 绕过修复

### 现状
`verify_chain`（`sinks.py:154-159`）：任意行 `record.get("prev_hash") is None` → 当合法 genesis 跳过。攻击者删光全文件 `prev_hash` 字段重写 → 每行都被当 genesis → `ok=True`。

### 设计
genesis 豁免**只允许第 1 行**：
```python
stored_prev = record.get("prev_hash")
if stored_prev is None:
    if idx == 1:                      # 仅首行可无 prev_hash（旧文件兼容）
        prev_hash = self._sha256_bytes(raw_line)
        continue
    return ChainVerifyResult(ok=False, total=len(raw_lines), broken_at=idx,
                             error=f"第 {idx} 行缺 prev_hash 字段（疑似篡改）")
if stored_prev != prev_hash:
    return ChainVerifyResult(ok=False, ...)
prev_hash = self._sha256_bytes(raw_line)
```
第 1 行有 `prev_hash` 字段时仍按正常链校验（`prev_hash=""` 起始），不破坏既有行为。

### 受影响测试
- `test_verify_genesis_boundary_no_prev_hash_field`（单行旧文件）→ 仍 `ok=True`（第 1 行豁免保留）。补一句注释说明"仅首行豁免"。
- 新增 `test_verify_stripped_prev_hash_attack_detected`：写 ≥3 条正常链 → 删除全部 `prev_hash` 字段重写 → `verify_chain().ok is False` 且 `broken_at == 2`。

### 链尾哈希外部锚定（仅建议，不在本包实现）
报告指出：限定 genesis 后，持写权限者仍可"整链重算"（删到只剩自己想保留的，重算所有 `prev_hash`）。根治需把**链尾哈希**周期性外锚到独立信任域。零成本方案建议（写入 PR 描述供 Paul 选型）：
- **每日企微播报链尾指纹**：定时任务读 `verify_chain` 后的最末行哈希，推内部审计群（人/群即外部见证），事后重算需同时改历史播报记录——抬高篡改成本。
- 9 月 ClickHouse 迁移时，JsonlSink 与 ClickHouse 双写，跨库比对链尾（与 P1 跨进程并发方案合并设计最经济）。

## 不在本包范围
报告 §7 P1（#5/#6/#9/#10/#11 → 包 B）、P1（#7/#8 → 包 C）、P2（#13/#19/#22 等）。A 包只解 3 个 P0。
