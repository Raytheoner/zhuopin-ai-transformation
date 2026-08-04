# platform-service-auth-gate Specification

## Purpose
TBD - created by archiving change retroactive-mechanism-specs. Update Purpose after archive.
## Requirements
### Requirement: 门禁按环境变量存在性生效，未配置时透明直通
`install_flask_gate` SHALL 仅在环境变量 `ZP_GATE_PASSWORD`（或调用方指定的 `env_var`）取值非空时装配门禁逻辑；该变量未设置或为空字符串时 MUST 原样返回传入的 Flask app、不拦截任何请求。本地开发环境与既有测试套件因此无需为每个 `create_app()` 调用点显式关闭门禁——只有生产 `.env` 显式配置了口令，门禁才真正生效。

#### Scenario: 未配置口令时门禁不生效
- **WHEN** 环境变量 `ZP_GATE_PASSWORD` 未设置或为空，调用 `install_flask_gate(app, ...)`
- **THEN** 返回的 app 与传入的 app 行为一致，任意路径均不被拦截

#### Scenario: 配置口令后门禁生效
- **WHEN** 环境变量 `ZP_GATE_PASSWORD` 设置为非空字符串，调用 `install_flask_gate(app, ...)`
- **THEN** 未携带有效 Cookie 或 `X-Auth-Token` 的请求被拦截（GET/HEAD 重定向至登录页，其余方法返回 401）

### Requirement: 程序化访问路径豁免清单
门禁 SHALL 对健康检查路径（默认 `/api/ping`，可由调用方通过 `exempt_paths` 扩展）与门禁自身的登录/登出路径（`/_gate/login`、`/_gate/logout`）豁免拦截，MUST NOT 要求这些路径携带 Cookie 或 `X-Auth-Token`，以保证既有 `deploy-server.ps1` 健康检查、部署脚本探活等程序化调用不因门禁上线而中断。

#### Scenario: 健康检查路径豁免放行
- **WHEN** 门禁已生效，对 `/api/ping` 发起请求且不携带任何鉴权凭据
- **THEN** 请求正常放行，不经门禁拦截

#### Scenario: 登录与登出路径豁免放行
- **WHEN** 门禁已生效，对 `/_gate/login` 或 `/_gate/logout` 发起请求
- **THEN** 请求正常放行（否则用户将无法访问登录页完成鉴权，陷入死锁）

### Requirement: 双通道鉴权判据——Cookie 会话与程序化 Token
`is_authorized` SHALL 接受两种独立通过路径，满足其一即视为已授权：① `X-Auth-Token` 请求头值与口令字面一致（`hmac.compare_digest` 常量时间比较），供脚本/curl 等程序化访问使用；② `zp_gate` Cookie 值经 HMAC-SHA256 签名校验且未过期，供浏览器会话使用。

#### Scenario: X-Auth-Token 命中即放行
- **WHEN** 请求头 `X-Auth-Token` 的值与配置的口令字面一致
- **THEN** `is_authorized` 返回 True，不依赖 Cookie

#### Scenario: 有效 Cookie 即放行
- **WHEN** 请求携带签名校验通过且未过期的 `zp_gate` Cookie
- **THEN** `is_authorized` 返回 True，不依赖 `X-Auth-Token`

#### Scenario: 两者均未命中则拒绝
- **WHEN** 请求既无有效 `X-Auth-Token` 也无有效 `zp_gate` Cookie
- **THEN** `is_authorized` 返回 False

### Requirement: Cookie 跨端口共享、一次登录全通
Cookie 签发 SHALL 使用 `Path=/` 且不绑定特定端口——浏览器按 host（不含端口）隔离 Cookie，故部署在同一主机不同端口的多个服务，登录任意一个后其余服务凭同一 Cookie 直接放行，无需重复登录。

#### Scenario: 单一服务登录后其余同主机服务凭同一 Cookie 放行
- **WHEN** 在服务 A（如 8091 端口）完成登录取得 `zp_gate` Cookie，随后携带该 Cookie 访问同主机的服务 B（如 8092 端口）
- **THEN** 服务 B 的门禁校验通过，无需再次登录

### Requirement: 已知残余风险不得表述为已解决
本门禁是临时止血、非正式身份鉴权，MUST 在登录页与相关文档中如实声明其局限：① 口令在 LAN 内以 HTTP 明文传输；② 不提供人员级访问审计（不记录"谁访问了什么"）；③ 单一共享口令一旦泄露即全部服务同时失效；④ 不区分访问者身份。这些局限 MUST NOT 被界面或文档表述为"已解决"或等同于正式鉴权；正式身份与权限鉴权（企微 OAuth SSO）是独立的后续工作，与本能力是替代关系而非本能力的功能扩展。

#### Scenario: 登录页标注非正式身份鉴权
- **WHEN** 用户访问门禁登录页
- **THEN** 页面文案标注"本页仅做基础访问限制，非正式身份鉴权"等等价说明

