# portal-wecom-sso Specification

## Purpose
让员工在企业微信内点开门户链接即可自动完成身份鉴别（OAuth2 网页授权换取 userid），复用现有 userid 体系，无需自建账号密码或额外登录动作；企微服务不可用时提供受限的应急兜底通道。
## Requirements
### Requirement: 企微 OAuth2 网页授权登录换取 userid
门户网关 SHALL 支持企业微信 OAuth2 网页授权流程——员工在企微客户端内点开门户链接后自动带 `code` 跳转，网关用 `code` 换取该员工的企微 userid 并建立会话，全程 MUST NOT 要求员工输入账号密码。

#### Scenario: 员工在企微内点开门户链接自动登录
- **WHEN** 员工在企业微信客户端内点击门户链接
- **THEN** 网关自动完成 OAuth2 授权换取其 userid，并建立会话，员工无需任何手动登录操作

#### Scenario: 授权失败或被拒绝时不建立会话
- **WHEN** 企微 OAuth2 授权过程失败或员工拒绝授权
- **THEN** 网关不建立会话，引导员工重试或说明可用的应急登录方式

### Requirement: userid 与既有白名单体系同源
OAuth 换取到的 userid SHALL 与 `wecom-aibot-service/aibot_service/whitelist.py` 中已在使用的 userid 命名空间一致（如 `YaoZuYi`/`tangyanping`/`ChenChen`/`2023458`/`ShaoPeiShen`），MUST NOT 为门户单独建立一套独立账号标识体系。

#### Scenario: 同一员工在机器人通道与门户呈现同一 userid
- **WHEN** 某员工既通过企微机器人通道发送过消息，又通过门户完成 OAuth 登录
- **THEN** 两处识别到的 userid 字面一致，可用于同一份手工部门映射表

### Requirement: 会话有效期与失效处理
登录会话 SHALL 有明确的有效期；会话过期或员工主动登出后，MUST 重新触发 OAuth 授权流程才能继续访问受保护路由。

#### Scenario: 会话过期后重新引导登录
- **WHEN** 员工的门户会话已过期，尝试访问受保护路由
- **THEN** 网关拦截该请求并重新引导其走 OAuth2 授权流程

#### Scenario: 主动登出立即失效当前会话
- **WHEN** 员工在门户中点击登出
- **THEN** 当前会话立即失效，后续请求需重新登录

### Requirement: 企微服务不可用时的应急本地口令通道
SHALL 提供一条独立于企微 OAuth 的应急本地口令登录通道，仅供 Shao Peishen 与运维人员知悉与使用；企微 OAuth 服务不可用时，MUST 能通过该通道完成登录以维持基本可用性。

#### Scenario: 企微 OAuth 服务不可用时应急通道仍可登录
- **WHEN** 企业微信 OAuth 服务不可用（外部依赖故障）
- **THEN** 知悉应急口令的人员仍可通过应急通道完成登录，访问门户

#### Scenario: 应急通道不作为常规入口对外公示
- **WHEN** 普通员工使用门户的正常登录路径
- **THEN** 不会看到或被引导使用应急本地口令通道；该通道信息仅由 Shao Peishen 与运维掌握

