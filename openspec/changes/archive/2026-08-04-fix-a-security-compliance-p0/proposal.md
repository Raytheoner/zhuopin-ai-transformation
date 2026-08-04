## Why

《全盘审计与差距分析报告-2026-06-13》§0/§2/§3 列出 **3 个 P0 安全/合规缺陷**，全部是 SC8 对客上线的硬前置，且第 1 项必须**先于** IT 轮换 U9C `client_secret`（红线日 6/20）合入——否则换了新钥匙仍走不校验证书的裸信道：

1. **TLS 证书校验被全局关闭**（`erp_connector/connector.py:71-73`，`ssl.CERT_NONE`）——携带 `client_secret` 的 AuthLogin 及全部 U9C 公网请求可被中间人截获。
2. **`submit_commitment` 低风险自动对客外发旁路**（`sc8/commitment.py`）——高置信+非首次+不晚于目标日的预测 `requires_confirmation=False` → 平台 `Notifier` 直接外发，**全程不查** `CUSTOMER_OUTBOUND_ENABLED`，违反已签字 SOP §4.1/§4.2。当前生产入口 `run.py` 走 `route_forecast`（安全），此旁路是**休眠炸弹**，且被 `test_low_risk_auto_sends` 正向固化。
3. **审计哈希链 genesis 绕过**（`audit/sinks.py:156-159`）——"无 `prev_hash` 字段即合法 genesis"的兼容逻辑对**任意行**生效，删光全文件 `prev_hash` 重写后 `verify_chain` 仍 `ok=True`，IATF"防篡改"名存实亡。

本变更只做这 3 项（surgical），不顺手重构、不碰无关测试。报告 §7 P1/P2 项归后续变更包 B/C。

## What Changes

- **A1 · TLS 校验恢复（`shared_tools/erp_connector/connector.py`）**：删除全局 `ssl.CERT_NONE`；默认走 `ssl.create_default_context()`（证书+主机名校验开启，与 `srm_connector` 一致）；提供 `U9C_TLS_INSECURE=1` **显式逃生开关**，开启时 `warnings.warn` 并经注入的 `ConnectorAudit` 写留痕（`source=TLS_INSECURE`），默认关闭。
- **A2 · 封死对客自动外发旁路**：
  - `sc8/commitment.py submit_commitment` 改为**首道一律入待审批队列**（绝不自动外发），删除"低风险 → 直发"路径；门禁真实风险（`requires`/`severity`/`reasons`）仍如实写入草稿与审计。
  - 平台 `notifiers/dispatch.py Notifier.send` 增加**第二道结构性闸门** `outbound_enabled`（注入式策略，默认放行——不影响内部企微/通用通知）；SC8 对客 `build_notifier` 把它接到 `config.CUSTOMER_OUTBOUND_ENABLED`，使**即便人工 approve、总开关关闭时也不外发**（入队留痕 `customer_outbound_disabled`）。
  - 改写 `test_low_risk_auto_sends` 语义为"低风险也入队"（不为保测试通过保留旁路）；同步调整依赖"approve→真发"的 SC8 门禁/队列测试，使其显式开启 `outbound_enabled` 验证放行机制本身。
- **A3 · 审计链 genesis 绕过修复（`audit/sinks.py verify_chain`）**：无 `prev_hash` 字段的豁免**只对第 1 行（`idx==1`）生效**；第 2 行起任何缺 `prev_hash` 的行判 `ok=False, broken_at=idx`。新增"剥光 prev_hash 攻击被检测"测试，修正 `test_audit_hash_chain.py` 既有 genesis 边界测试语义。链尾哈希外部锚定方案**仅在 PR 描述中给建议**（不在本包实现）。

## Capabilities

### Modified Capabilities
- `platform-data-connectors`：连接器默认开启 TLS 校验 + 显式不安全逃生开关（A1）。
- `delivery-commitment-gate`：首道对客承诺一律入队，删除低风险自动外发旁路（A2）。
- `platform-notification-channels`：`Notifier.send` 第二道对客外发总开关结构性闸门（A2）。
- `audit-hash-chain`：`verify_chain` genesis 豁免限定第 1 行（A3）。

## Impact

- **平台底座**：`shared_tools/erp_connector/connector.py`（TLS）、`shared_tools/notifiers/dispatch.py`（第二道闸门）、`audit/sinks.py`（genesis）。
- **SC8 工程**：`sc8/commitment.py`（首道入队）、`sc8/tests/test_commitment_gate.py`（语义改写）、相关队列测试。
- **合规红线**：CLAUDE.md §7.2（决策写 audit）/§7.4（L2 人工确认）；本变更**强化**红线，不放松。
- **上线门禁**：A1/A2/A3 全部完成、测试覆盖前，SC8 对客外发开关不得开启（与 SOP 门禁文档第 3 节一致）。
- **执行地**：A1 含真实端点（证书 pin 需 IT 配合），代码默认校验改动可 off-LAN 完成与单测；真实握手验证待 LAN/VPN。
