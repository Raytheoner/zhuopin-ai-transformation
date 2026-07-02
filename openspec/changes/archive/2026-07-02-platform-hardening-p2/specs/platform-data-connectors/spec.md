## ADDED Requirements

### Requirement: 连接器边界强 Schema 校验
平台连接器 SHALL 在输入/输出边界对外部数据（U9C ERP、携客云 SRM）做强 Schema 校验（Pydantic），字段缺失/类型不符/上游改字段 MUST 被挡下并以 `ConnectorValidationError` 显式报错，不得让脏数据流入预测引擎。

#### Scenario: 上游脏数据被边界拦截
- **WHEN** U9C/SRM 返回缺字段或类型不符的记录
- **THEN** 连接器在边界校验失败、抛出 `ConnectorValidationError`，脏数据不进入下游预测

### Requirement: 携客云 SRM 限流退避
平台 SRM 连接器 SHALL 遵守携客云限流约束（30s 重复查询限制、查询跨度≤60 天、错误码 `900301`）：以令牌桶限流（进程级，1 req/30s per endpoint）+ 指数退避重试（最多 3 次），避免多实例并发超限导致拉黑。`900301` MUST 触发退避，不静默丢失。

#### Scenario: 命中限流时退避重试
- **WHEN** SRM 返回限流错误码 `900301` 或触发 30s 重复限制
- **THEN** 连接器按退避策略延迟重试，不立即重发、不静默丢失请求

### Requirement: 凭证通过 SecretsProvider 注入
平台连接器 SHALL 通过 `SecretsProvider` 协议读取凭证，不直接硬编码或直接调用 `os.environ`。`from_env()` 默认行为不变（向后兼容），同时支持注入自定义 `SecretsProvider`（如 Vault 实现）。

#### Scenario: 默认 from_env() 行为保持不变
- **WHEN** 调用 `XkySrmConnector.from_env()` 且环境变量已设置
- **THEN** 连接器正常构造，凭证从环境变量读取，与修改前行为一致
