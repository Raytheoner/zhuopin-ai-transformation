## Why

SC8 MVP 已完成内部闭环，真实数据切换（6/12 后）前须完成平台底座 P2 加固：当前审计日志可篡改、连接器无边界 Schema 校验（脏数据静默流入预测引擎）、SRM 多实例并发会触发携客云 30s 限流、凭证无抽象层（未来接 Vault/K8s 需改连接器代码）。这四项均为《SC8 上线前置门禁》的切库前置条件，不阻塞 mock，可先行。

## What Changes

- **审计防篡改**：`JsonlSink` 写入时在每条记录里嵌入「上一条哈希」（SHA-256 链），提供 `verify_chain()` 函数检测任意行被篡改；保持 `AuditEvent` 接口不变，SC1/SC8 无需改动。
- **连接器 Pydantic 边界校验**：`XkySrmConnector` 与 `ZpConnector` 的 API 响应在进入内部 dataclass 前经 Pydantic 模型强校验，字段缺失/类型不符抛 `ConnectorValidationError`，不漏入下游场景。
- **SRM 令牌桶 + 指数退避**：`XkySrmConnector._post()` 加进程级令牌桶（1 req/30s per endpoint）+ 指数退避（最多 3 次，base 30s），尊重携客云红线：30s 重复限制、查询跨度 ≤60 天、错误码 900301。
- **SecretsProvider 凭证抽象**：引入 `SecretsProvider` Protocol（`get(key) -> str`），提供 `EnvSecretsProvider`（`.env` / 环境变量实现）；连接器 `from_env()` 改为接受可选的 `SecretsProvider`，为 Vault/K8s Secrets 预留接口，不改现有 `.env` 用法。
- **顺手修复 P3-#9**：`ConnectorAudit.trace()` 写入由 `AccessTrace` 传 `AuditSink.write(AuditEvent)` 改为写独立 `access_trace` JSONL，消除静态类型不匹配。

## Capabilities

### New Capabilities

- `audit-hash-chain`：JsonlSink hash-chain 防篡改写入 + `verify_chain()` 校验函数
- `connector-schema-validation`：SRM / zp ERP 连接器 Pydantic 边界 Schema 校验
- `srm-rate-limiting`：SRM 令牌桶限流 + 指数退避（覆盖携客云红线）
- `secrets-provider`：SecretsProvider Protocol 凭证抽象（EnvSecretsProvider 实现 + Vault 预留）

### Modified Capabilities

- `platform-data-connectors`：连接器新增 Schema 校验行为 + 限流退避 + 凭证注入接口（需求级变更：新增 ConnectorValidationError / RateLimitError 错误语义）

## Impact

- **平台底座**：`audit/sinks.py`（hash-chain）、`shared_tools/srm_connector/connector.py`（限流 + 校验）、`shared_tools/erp_connector/connector.py`（Pydantic 校验）、新增 `shared_tools/secrets.py`（SecretsProvider）、`shared_tools/connector_audit.py`（P3-#9 类型修复）。
- **现有场景**：SC1 / SC8 的 `AuditLogger` 调用接口不变；从 `from_env()` 迁移到 `SecretsProvider` 为可选向后兼容改动，默认行为不变。
- **测试**：所有改动先写测试再实现（全 mock，不连真实库）；SC1/SC8 已有测试须仍全绿。
- **依赖**：新增 `pydantic>=2.0`（pyproject extras 或直接依赖）。
