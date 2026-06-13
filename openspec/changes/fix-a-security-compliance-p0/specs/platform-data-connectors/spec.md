## ADDED Requirements

### Requirement: U9C/ERP 连接器默认开启 TLS 证书校验
平台 `ZpConnector`（U9C/ERP 唯一规范连接器）SHALL 对所有公网请求（含携带 `client_secret` 的 OAuth2 `AuthLogin`、`zp` 视图查询、`U9C/webapi/BOM/Query`）默认启用 TLS 证书与主机名校验（`ssl.create_default_context()`，`verify_mode=CERT_REQUIRED`、`check_hostname=True`）。MUST NOT 全局关闭证书校验。

#### Scenario: 默认实例启用证书校验
- **WHEN** 未设置 `U9C_TLS_INSECURE` 构造 `ZpConnector`
- **THEN** 其 SSL context `verify_mode == ssl.CERT_REQUIRED` 且 `check_hostname is True`

### Requirement: 不安全 TLS 仅经显式逃生开关并留痕
连接器 SHALL 仅在显式设置环境变量 `U9C_TLS_INSECURE=1`（或 `true`/`yes`）时关闭证书校验，作为 IT 提供受信证书前的 LAN 应急通道。开启逃生开关时 MUST 触发 `UserWarning`，并在注入 `ConnectorAudit` 时写一条 `source="TLS_INSECURE"` 痕迹（无 audit 时至少 warn）。`real` 数据源（对客权威路径）下逃生开关 MUST NOT 生效（强制证书校验）。

#### Scenario: 逃生开关关闭校验并告警留痕
- **WHEN** 设置 `U9C_TLS_INSECURE=1` 且注入 audit 构造连接器
- **THEN** SSL context `verify_mode == ssl.CERT_NONE`，触发 `UserWarning`，且 audit 收到 `source="TLS_INSECURE"` 痕迹

#### Scenario: real 模式拒绝不安全逃生
- **WHEN** `data_source="real"` 且设置 `U9C_TLS_INSECURE=1`
- **THEN** 连接器强制证书校验（拒绝以不安全模式连接对客权威路径）
