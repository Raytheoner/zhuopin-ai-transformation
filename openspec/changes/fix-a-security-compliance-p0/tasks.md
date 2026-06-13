# Tasks — 变更包 A（安全与合规 P0）

> 工作流：先写/改测试，再实现（SuperPowers）。每段做完跑相关测试。全包绿 + 黄金值不漂移后 commit + push。
> 顺序：A3（最独立）→ A1 → A2（牵涉测试最多，放最后）。

## A3 · 审计链 genesis 绕过（`audit/sinks.py`）
- [ ] 1.1 改写 `test_audit_hash_chain.py`：新增 `test_verify_stripped_prev_hash_attack_detected`（≥3 条链删光 prev_hash 字段 → `ok=False, broken_at==2`）；既有 `test_verify_genesis_boundary_no_prev_hash_field` 加注释"仅首行豁免"。
- [ ] 1.2 `verify_chain`：`stored_prev is None` 豁免限定 `idx == 1`，否则 `ok=False, broken_at=idx`。
- [ ] 1.3 跑 `tests/test_audit_hash_chain.py` 全绿。

## A1 · TLS 校验恢复（`shared_tools/erp_connector/connector.py`）
- [ ] 2.1 先写测试（`tests/test_erp_connector_tls.py` 或并入既有校验测试）：默认实例 context `verify_mode == CERT_REQUIRED` 且 `check_hostname is True`；`U9C_TLS_INSECURE=1` 时 `CERT_NONE` 且触发 `UserWarning` + audit 留 `TLS_INSECURE` 痕迹。
- [ ] 2.2 删除模块级 `_CTX` 的 `check_hostname=False`/`CERT_NONE`；按 env 在 `__init__` 计算 `self._ctx`（默认安全，`U9C_TLS_INSECURE` 才放行 + warn + audit.trace）。
- [ ] 2.3 三处 `urlopen(context=_CTX)`（`_http_get`/`_zp_post`/`_u9c_bom_post`）改用 `self._ctx`。
- [ ] 2.4 （依 Paul A1 决定）real 模式禁用逃生开关：`data_source=real` + `U9C_TLS_INSECURE` → 抛错或强制校验。
- [ ] 2.5 可选 `U9C_TLS_CAFILE` 证书 pin 接口位（`load_verify_locations`），缺省不启用。
- [ ] 2.6 跑连接器测试全绿。

## A2 · 封死对客自动外发旁路
- [ ] 3.1 平台 `notifiers/dispatch.py`：先写测试 `test_l2_gate_hardening.py` 增 `outbound_enabled` 用例（默认放行；callable/bool 注入；关闭时即便 `confirmed_by` 也拦截入队、reason=`customer_outbound_disabled`）。
- [ ] 3.2 `Notifier.__init__` 加 `outbound_enabled: bool | Callable[[],bool] = True`；`send()` 拦截判定叠加 `not outbound_ok`；`_record`/入队 reason 区分两类拦截。
- [ ] 3.3 SC8 `commitment.py`：`submit_commitment` 首道建草稿 `requires_confirmation=True`（policy 恒入队），`severity`/`reasons` 取 gate 真值；`CommitmentResult.requires_confirmation` 仍记 gate 真实风险。
- [ ] 3.4 SC8 `build_notifier`（依 Paul A2 决定，选项 A）：默认 `outbound_enabled=lambda: config.CUSTOMER_OUTBOUND_ENABLED`，新增可选参数透传。
- [ ] 3.5 改写 `test_commitment_gate.py::test_low_risk_auto_sends` → "低风险也入队"（`res.sent is False`、队列+1、`sends==[]`、`res.requires_confirmation is False`）。
- [ ] 3.6 调整 `test_blocked_then_approved_sends` / `_seed_prior_send` / `test_pending_queue.py` 放行用例：注入 `outbound_enabled=True`（或 monkeypatch config）验证 approve→发机制。
- [ ] 3.7 新增 `test_outbound_switch_blocks_even_approved`：总开关关闭 → approve 带确认人仍不外发、入队 `customer_outbound_disabled`。
- [ ] 3.8 跑 SC8 全测 + 平台 notifier 测试全绿。

## 收尾
- [ ] 4.1 全仓回归：平台 + O2 + SC5 + SC3 + SC8 + SC1 全绿；黄金值 auto_total=35850 / review_total=640000 不漂移。
- [ ] 4.2 `openspec validate fix-a-security-compliance-p0 --strict`（若 CLI 可用）。
- [ ] 4.3 commit（message 引用 A1/A2/A3 条目编号）+ push；PR 描述附"链尾哈希外部锚定"建议 + 提醒 6/20 催 IT 轮换 secret。
