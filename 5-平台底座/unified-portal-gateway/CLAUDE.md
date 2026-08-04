# CLAUDE.md — 统一门户网关（场景级记忆）

> 本文件是本服务的本地记忆/进度笔记，隔离于其他场景。
> 项目级上下文见仓库根 `CLAUDE.md` §5「新场景一律不新起端口」硬约束；权威架构决策见
> `3-治理与合规/统一门户架构决策件-SSO与权限-2026-07-29.md`；openspec 变更包
> `openspec/changes/unified-portal-gateway-sso/`（proposal/design/specs/tasks）。
> 本服务 = CC 建造车间产物；**不改规划文档**（那是 Cowork 的活）。

## 1. 定位

- **不是**某个部门场景（不像 SC1-SC8/FI1-FI10/QD-B 归属单一部门），是**平台侧独立常驻服务**——
  决策件 §六线②"地基线"的正式落地，在既有四个业务服务（保供看板8091/命令中心8092/
  QD-B8093/FI2 8094）**前面加一层**，不改任何后端服务代码。
- 队列 #162。四项能力：① 反向代理 + 统一路由（`/{域}/{场景}`）；② 企微 OAuth2 SSO；
  ③ 三层权限判定（公开只读/域成员/域管理员）；④ 访问日志（承接队列 #112 使用率埋点）。
- **本次交付范围（design.md 决策3）**：只做网关能力本身 + 一个低风险试点路由——
  门户首页（`/` → 8092）。**8091/8093/8094 三个业务服务本次不接入路由表**，继续维持
  现状（`simple_gate` 口令直连）——决策件线③"存量收编"是后续独立任务，顺序
  财务→质量→采购，8091 最后动。

## 2. 关键决策记录（design.md 完整版，此处摘要）

| 决策 | 结论 | 依据 |
|------|------|------|
| 网关技术选型 | Flask + `requests` 白名单反向代理（不选 nginx/IIS ARR） | 与团队既有 Python 技术栈一致，避免新增 IIS 运维面；白名单式路由表从设计上排除 SSRF 类风险 |
| 监听端口 | 8090（新对外唯一入口），8091-8094 保留作应急直连 | 内部工具无需特权端口；沿用既有 809x 序列 |
| 首个真实收编试点 | 门户首页（8092），非任一业务服务 | 数据敏感度最低（销售数据已脱敏）、复杂度最低，避免网关工程进度与业务口径耦合 |
| 会话机制 | 延续 `simple_gate` 的 HMAC 签名 Cookie 范式，但新增独立 `zp_portal_sso` Cookie，**不复用/不修改 `zp_gate`** | `zp_gate` 语义是"知道口令"，SSO 语义是"这是谁"，两套 Cookie 短期并存 |
| 部门映射 | 手工表（`department_mapping.yaml`），未登记 userid 一律 fail-closed 为公开只读 | 决策件 §五决策1，不取企微通讯录 `contact` 权限 |
| 代理已启用 `simple_gate` 的后端 | 注入 `X-Auth-Token` 避免双重拦截 | 命中 `simple_gate` 的程序化访问通过路径，员工不必二次输口令 |
| 进程守护 | Windows 计划任务（SYSTEM + AtStartup），同 SC8/QD-B/命令中心惯例 | 已验证可靠，不引入 supervisor/pm2 等新工具 |
| **企微 OAuth 凭据（apply 阶段实际拍板，2026-08-04）** | **选 (b) 未注册，先 mock 登录打通链路，真实凭据走队列 #240 另行申请** | Shao Peishen 拍板：路由/权限/日志三项不因等凭据停工；真实 OAuth 代码已按官方文档实现（`sso.py`），凭据到位后 `.env` 配置即可切换，无需改代码 |

## 3. 复用底座资产

- **AuditLogger**：`zhuopin_platform.audit.AuditLogger.jsonl("reports/portal_access.jsonl")`，
  `scenario="portal-gateway"`，承接访问日志能力（`access_log.py`），免费获得 hash-chain
  防篡改与 IATF 可追溯，同时是队列 #112 使用率埋点的数据源（无需二次埋点）。
- **不使用**：连接器（网关不连 SRM/ERP）、Notifier（网关本身不对外发通知）。
- **场景本地**：`portal_gateway/sso.py`（会话签发+企微OAuth+mock/应急登录）、
  `portal_gateway/permissions.py`（三层权限判定+部门映射加载）、
  `portal_gateway/routing.py`（白名单反向代理）、`portal_gateway/webapp.py`（Flask 串联）。

## 4. 红线（建造时守住）

- 🔴 **mock 登录（`PORTAL_GATEWAY_MOCK_LOGIN`）是开发/试点期的已知妥协，不是安全能力**——
  任意 userid 直接签发会话，不做任何身份核验。**真实企微 OAuth 凭据到位后必须显式移除
  该环境变量**，否则任何人都能自称任意身份获得对应权限。当前风险可接受的唯一原因是
  试点路由（8092）零敏感数据；**收编 8091/8093/8094 之前，必须先关闭 mock 登录或已切换
  真实 OAuth**，绝不允许 mock 模式与敏感路由同时暴露。
- 🔴 **应急本地口令通道**（`PORTAL_GATEWAY_EMERGENCY_PASSWORD`）不允许调用方自报任意身份——
  核验通过后固定签发 `PORTAL_GATEWAY_EMERGENCY_USERID`（默认 `ShaoPeiShen`）的会话，
  不得改成"输入口令+自选身份"的形式（那会退化成 mock 登录的等价物）。该通道**不得**在
  任何用户可见页面（登录选择页等）出现链接，仅 Shao Peishen 与运维知悉 URL。
- 🔴 `PORTAL_GATEWAY_SESSION_SECRET` 未配置时网关**拒绝启动**（fail loud），不同于
  `simple_gate` 的"未配置即不生效"——会话签名密钥是身份鉴别的信任根，缺失时决不能
  fail open。
- 凭据（会话密钥/OAuth Secret/应急口令/已收编后端的 `simple_gate` 口令）只进服务器
  本地 `.env`（`.gitignore` 已覆盖），不写入任何会被提交入库的文件。
- 访问日志只记录"谁在何时访问了什么资源"元信息，不记录敏感字段具体取值（`access_log.py`
  函数签名从结构上就不接受任何页面内容/字段值参数）。
- 反向代理仅转发到路由表白名单内的已知后端（`routing.py`），不做通用透明代理。
- OEM 隔离：本服务不涉及研发/OEM 技术数据，不适用。
- L2 门禁：不适用（网关本身不做业务判定，只做身份/权限判定）。

## 5. 状态时间线

| 日期 | 状态 |
|------|------|
| 2026-08-04 | **propose+design 交付**（独立 worktree `unified-portal-design-8a2ce3`）：openspec 变更包 `unified-portal-gateway-sso`——4 个新 capability spec（`portal-gateway-routing`/`portal-wecom-sso`/`portal-permission-model`/`portal-access-log`）+ design.md 7 项技术决策 + tasks.md 7 组任务，`openspec validate --strict` 通过。 |
| 2026-08-04 | **design 审通过（Shao Peishen）**：三项拍板——① 企微凭据未注册，选先 mock 登录、凭据走队列 #240 另行申请；② 首个真实收编试点=门户首页 8092，认可；③ design 整体批准进入 apply。 |
| 2026-08-04 | **apply 完成，真实部署 `.51:8090`**（同一 worktree/分支续跑）：`sso.py`/`permissions.py`/`routing.py`/`access_log.py`/`webapp.py` 全部落地，TDD 全程先红后绿，全量回归 84 tests 零回归。会话密钥、mock 登录开关随部署脚本直接写入服务器 `.env`（未入库）。详见 §7 部署状态。 |

## 6. 关键依赖/前置（解锁条件）

- 🟡 **企微 OAuth 网页授权凭据（CorpID/AgentID/Secret）尚未申请**——见队列 #240。
  现有企微机器人走 BotID+WebSocket 体系，与网页授权是企微后台两套独立注册。
  凭据到位后：① 写入 `.env` 的 `WECOM_GATEWAY_CORP_ID`/`WECOM_GATEWAY_AGENT_ID`/
  `WECOM_GATEWAY_SECRET` 三个变量；② 移除 `PORTAL_GATEWAY_MOCK_LOGIN`；
  ③ 真实登录走一次 `/portal/_sso/oauth/start` 全链路验证——`sso.py` 代码本身
  无需改动（`load_wecom_oauth_config()` 自动切换）。
- 🟡 **决策件线③存量收编**（8091/8093/8094 正式接入路由表）——条件触发：各域业务
  数据对准 + 专员验收通过，顺序财务→质量→采购，8091 最后动。本服务当前路由表只有
  门户首页一条，收编时按 `routing.Route` 结构追加条目即可，`webapp.py`/鉴权链路
  均无需改动。
- 🟡 **解植雅/汤易水/朱映桦/李姣龙 四人 userid 尚未收集**——决策件 §五决策3 点名
  为域管理员，但 `department_mapping.yaml` 暂缺其真实企微 userid，如实留白不臆造
  （同 2026-07-22 陈承/IT 补入 `wecom-aibot-service` 的先例）。
- 运行：`python scripts/run_gateway.py`（读 `.env`）；测试：`pytest`（全程 mock 外部
  企微 API 调用，不触真实端点）。

## 7. 部署状态（2026-08-04，apply 完成，队列 #162）

- **地址**：http://192.168.100.51:8090/ （新增唯一对外入口，LAN 全网段）
- **服务**：Flask+waitress，`portal_gateway/webapp.py`（SSO+权限+反向代理）+
  `scripts/run_gateway.py` 启动入口；计划任务 `UnifiedPortalGateway`（SYSTEM + AtStartup，
  失败重启3次，同 SC8/QD-B/命令中心惯例）；防火墙 `UnifiedPortalGateway-8090`（LAN 全网段）。
- **凭据**：`PORTAL_GATEWAY_SESSION_SECRET`（32 字节随机值，部署时生成，仅服务器 `.env`
  持有，未入库、未出现在任何 commit/日志）；`ZP_GATE_PASSWORD` 从命令中心（8092）既有
  `.env` 原样复制一份到网关 `.env`（同一份口令，决策6 X-Auth-Token 注入用，服务器内部
  操作完成，值未在本会话终端明文出现）；`PORTAL_GATEWAY_MOCK_LOGIN=1`（试点期，企微
  OAuth 凭据未到位，见 §6）。
- **冒烟结果（真实 LAN 访问，非仅服务器 loopback）**：
  - `/api/ping` 200，`{"service":"统一门户网关","status":"ok"}`；
  - 未登录访问 `/` → 302 跳转 `/portal/_sso/login`（spec「会话过期后重新引导登录」验证）；
  - 登录选择页只显示"开发/试点登录"链接，**不显示** OAuth 链接（未配置）、**不显示**
    应急登录链接（spec「应急通道不作为常规入口对外公示」真实验证）；
  - mock 登录（userid=YaoZuYi）→ 签发 `zp_portal_sso` Cookie → 携带 Cookie 再访问 `/` →
    **200，真实返回命令中心首页内容**（标题"卓品智能 · AI 运营指挥中心"），反向代理+
    X-Auth-Token 免二次登录（决策6）端到端验证通过；
  - 访问日志 `reports/portal_access.jsonl` 真实落盘，`unauthenticated`/`authorized` 两类
    事件字段完整（userid/path/domain/tier/allowed/period="开发期"），逐字节核验
    `evaluator="(未登录)"` 编码无损（UTF-8 11 字节，终端显示乱码系控制台代码页问题、非
    数据损坏）；
  - **应急通道不影响生产**：`/portal/_sso/emergency-login` 未配置口令时 POST 恒 401（生产
    环境 `.env` 未设 `PORTAL_GATEWAY_EMERGENCY_PASSWORD`，通道当前实际不可用，符合预期）；
  - **8092 原端口仍可直连**（应急直连通道验证，其自身 `simple_gate` 302 行为不变、证明
    本次部署未触碰该服务）；
  - **程序化访问不中断**：8091/8093/8094 三服务 `/api/ping` 均 200，确认本次新增网关部署
    未影响同机其余服务。
- **未做（真实验证受限，如实登记）**：企微 OAuth 真实登录（凭据未到位，见 §6/队列 #240，
  代码已实现但仅经单测覆盖，非真实企微账号验证）；8091/8093/8094 正式收编进路由表
  （决策件线③，条件触发，本次不在范围）；`/api/ping` 之外的其余细分程序化访问路径
  （命令中心自身 `sync_sales_data.py` 定时刷新）本次未逐一触发验证，仅确认服务健康。
- **回滚**：`schtasks /End /TN UnifiedPortalGateway`（停）；
  `schtasks /Delete /TN UnifiedPortalGateway /F`（注销）——回滚后四个既有业务服务的直连
  访问方式完全不受影响（网关是新增的前置层，未修改任何后端服务）。
