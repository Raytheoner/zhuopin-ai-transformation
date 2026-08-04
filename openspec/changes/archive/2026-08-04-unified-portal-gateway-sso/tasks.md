## 1. 前置确认（apply 开工前）

- [x] 1.1 向 Shao Peishen/IT 确认企微自建应用（OAuth 网页授权）凭据（CorpID/AgentID/Secret）是否已在企微管理后台注册；未注册则先提交申请（参考 CLAUDE.md 记录的 U9C MCP 申请先例），并记录预计到位时间——**Shao Peishen 2026-08-04 拍板：选 (b) 未注册，走队列 #240 另行申请；apply 阶段先做 mock userid 联调，不因等凭据停工**
- [x] 1.2 核对 `.51` 上端口占用表，确认 8090 未被占用；若冲突另选端口并同步更新 design.md 决策 2——8090 未被占用，`Register-ZhuopinFirewallRule` 首次注册成功
- [x] 1.3 新建独立 worktree/分支（一任务一分支一 worktree，队列协议〇.5），把本变更包收尾时的实现代码限定在该 worktree——沿用 propose+design 阶段的 `unified-portal-design-8a2ce3` worktree/`claude/unified-portal-design-8a2ce3` 分支续跑（Shao Peishen 明示不新建）

## 2. 网关骨架与反向代理路由（对应 spec `portal-gateway-routing`）

- [x] 2.1 新建网关服务目录（Flask app + `requests` 反向代理），路由表用显式白名单配置（域/场景 → 后端 base URL），初始只含 `/`（占位，尚未接入 8092）——`5-平台底座/unified-portal-gateway/portal_gateway/routing.py::default_route_table()`
- [x] 2.2 实现流式转发：请求方法/头/body（含 multipart 文件上传）原样转发到目标后端，响应流式返回——`routing.py::forward_request`（`stream=True`），本次试点路由（8092 静态文件）未触发真实文件上传场景，multipart 转发逻辑已实现但仅经单测覆盖，未经真实大文件上传验证
- [x] 2.3 实现 `/api/ping` 健康检查端点，豁免鉴权——`webapp.py`，真实部署验证 200
- [x] 2.4 实现应急直连说明（仅内部文档/注释记录，不在员工可见页面暴露 8091-8094 直连地址）——`sso.py`/`webapp.py` 模块注释 + 本 CLAUDE.md §4 红线；真实验证登录选择页不含任何直连端口链接
- [x] 2.5 编写单测：新增路由映射后端零改动即生效、单个后端异常不影响其余路由、健康检查豁免鉴权——`tests/test_routing.py`（14 项）

## 3. 企微 OAuth SSO（对应 spec `portal-wecom-sso`）

- [x] 3.1 实现 OAuth2 网页授权跳转与回调，用 `code` 换取 userid（依赖任务 1.1 的凭据到位）——`sso.py::build_wecom_authorize_url`/`exchange_code_for_userid` + `webapp.py::/portal/_sso/oauth/*`，**按官方文档实现完整，但凭据未到位（见 1.1），仅经 mock HTTP 响应单测覆盖，未经真实企微账号验证**；`.env` 配齐三项凭据即可自动切换，代码零改动
- [x] 3.2 实现 `zp_portal_sso` Cookie 签发与校验（HMAC-SHA256，含 userid + 过期时间，无服务端 session 存储，风格对齐 `simple_gate.py`）——`sso.py::make_session_cookie_value`/`verify_session_cookie_value`
- [x] 3.3 实现会话过期重新引导登录、主动登出立即失效——`webapp.py::_proxy`（未登录/过期重定向）+ `/portal/_sso/logout`
- [x] 3.4 实现应急本地口令通道（仅 Shao Peishen 与运维知悉，独立于 `zp_gate`/`zp_portal_sso`），配置来源与部署方式待定（沿用环境变量惯例）——`sso.py::verify_emergency_password` + `webapp.py::/portal/_sso/emergency-login`，固定签发预配置身份（不允许自报身份）；生产环境未配置该口令（通道当前实际不可用，符合"仅需要时启用"设计）
- [x] 3.5 编写单测：OAuth 成功/失败路径、userid 与既有 `whitelist.py` 命名空间一致、会话过期与登出、应急通道独立生效（可 mock 企微接口）——`tests/test_sso.py`（28 项）+ `tests/test_webapp.py` 集成用例

## 4. 三层权限判定（对应 spec `portal-permission-model`）

- [x] 4.1 新建部门映射表文件（userid → 域 → 层级），初始录入决策件 §五决策3 已列出的人员（姚祖怡/唐燕萍/陈忱 + 解植雅/汤易水/朱映桦/李姣龙 等）——`portal_gateway/department_mapping.yaml`；**姚祖怡/唐燕萍/陈忱/王泓钦/ShaoPeiShen 五人真实 userid 已录入，解植雅/汤易水/朱映桦/李姣龙四人真实 userid 未经任何既有系统收集到，如实留白不臆造（文件内注释登记待补，同陈承/IT 先例）**
- [x] 4.2 实现三层权限判定中间件：公开只读/域成员/域管理员，映射表未命中 fail-closed 为公开只读——`permissions.py::resolve_tier`/`has_access`
- [x] 4.3 实现敏感字段判据的应用方式（判定辅助函数/装饰器，供各路由标注哪些字段/操作需要域管理员及以上）——`permissions.py::is_sensitive_field_visible`（本次试点路由无敏感字段场景，函数已实现待收编阶段实际调用）
- [x] 4.4 编写单测：三层各自可见范围、非域成员跨域访问被拒绝、映射表未命中 fail-closed、敏感字段对域成员隐藏对域管理员可见——`tests/test_permissions.py`（12 项）

## 5. 访问日志（对应 spec `portal-access-log`）

- [x] 5.1 设计访问日志字段（userid/域场景路径/时间戳/鉴权结果），与队列 #112 使用率埋点需求对齐，避免字段返工——`access_log.py::build_access_event`，复用 `zhuopin_platform.audit.AuditLogger`
- [x] 5.2 实现日志落盘（含鉴权通过与拒绝两种情形均留痕），确认不记录敏感字段明文——真实部署验证：`unauthenticated`/`authorized` 两类事件均已落盘
- [x] 5.3 实现"开发期"标记逻辑，对齐《价值度量指标口径表》§〇bis 起算日规则——`access_log.py::is_development_period`（未配置起算日默认视为开发期）
- [x] 5.4 编写单测：通过/拒绝请求均留痕、敏感字段不进日志正文、开发期标记与起算日判定——`tests/test_access_log.py`（10 项）

## 6. 首个真实收编试点：门户首页（8092）（对应 design 决策 3）

- [x] 6.1 把根路径 `/` 接入网关路由表，代理至命令中心（8092）——`routing.py::default_route_table()`
- [x] 6.2 端到端验证：**mock userid 登录**（真实企微账号登录待凭据到位，见任务 3.1）→ 公开只读权限可访问首页 → 访问日志留痕——真实 LAN 环境验证：mock 登录 YaoZuYi → 携带会话访问 `/` → 200，返回真实命令中心首页内容，访问日志正确记录
- [x] 6.3 程序化访问逐项验证不中断：命令中心自身的 `sync_sales_data.py`、`deploy-server.ps1` 健康检查、任何既有只读取证脚本（对照决策件 §八风险4"最易翻车处"）——`/api/ping` 及 8091/8093/8094 三服务健康检查均验证 200；`sync_sales_data.py` 定时刷新等细分路径未逐一真实触发验证（如实登记，非阻塞项，风险低——该脚本走本机文件写入+scp，不经过网关）
- [x] 6.4 验证网关不可用时，8092 仍可通过原直连端口访问（应急通道生效）——真实验证：8092 直连端口在网关部署后行为不变（其自身 `simple_gate` 302 响应照旧）

## 7. 部署与收口

- [x] 7.1 网关注册 Windows 计划任务（`SYSTEM` + `AtStartup`，同 SC8/QD-B/命令中心既有惯例），配失败重启——`UnifiedPortalGateway`
- [x] 7.2 真实部署 `.51`，冒烟三件套（`/api/ping`、门户首页 200、一次真实登录+权限判定验证）+ 回滚 SOP（`schtasks /End` + 员工回退旧端口直连）——见 CLAUDE.md §7 部署状态
- [x] 7.3 更新平台底座 CLAUDE.md / AI 运营指挥中心相关文档，补充网关章节，说明其与 `simple_gate.py` 的共存关系与后续收编计划指针——新建 `5-平台底座/unified-portal-gateway/CLAUDE.md`
- [x] 7.4 队列 #162 回写产出路径 + 状态改"待验收/完成"；在 §四 或队列行内追加线③存量收编（财务→质量→采购）后续任务为"待领"行
- [x] 7.5 提交 Shao Peishen 审阅本次真实部署与试点验证结果（非仅 design.md 文本审），确认后再评估是否需要正式把 8091/8093/8094 排入线③——随收工报告提交
- [x] 7.6 `/opsx:archive` 归档本变更包；commit + push + 收工重跑文档台账
