# CLAUDE.md — 企微智能机器人双向通道服务（场景级记忆）

> 本文件是本服务的本地记忆/进度笔记，隔离于其他场景。
> 项目级上下文见仓库根 `CLAUDE.md`；权威规划见 `openspec/changes/wecom-aibot-channel/`
> （proposal.md/design.md/specs/tasks.md）+ `1-转型规划/开场prompt-企微智能机器人双向通道-CC建造交接.md`。
> 本服务 = CC 建造车间产物；**不改规划文档**（那是 Cowork 的活）。

## 1. 定位

- **不是**某个部门场景（不像 SC1-SC8/FI1-FI10 归属单一部门），是**平台侧独立常驻服务**，
  服务四域专员（采购姚祖怡/财务唐燕萍/质量陈忱/销售泓钦）的企微双向通道基础设施。
- v1 两场景：①推送跟进信（`aibot_send_msg`，md+docx）②收专员反馈自动归档（R6 自动化）。
- 与现有 webhook 群机器人（`0-学习与工具/发企微.py` + 平台 `wecom.py`，只发不收）**并存不改**。

## 2. 关键决策记录（design.md 完整版，此处摘要）

| 决策 | 结论 | 依据 |
|------|------|------|
| D1：代码归属 | 连接器薄封装入 `zhuopin_platform/shared_tools/notifiers/wecom_aibot.py`；常驻服务独立目录 `5-平台底座/wecom-aibot-service/`（不挂靠任何部门场景） | 服务四域，非单一部门场景 |
| D1：部署位置 | LAN 服务器 192.168.100.51（已跑 SC8 保供看板），纯出站 WS 客户端、无入站端口/防火墙 | Paul 2026-07-11 拍板 |
| D2：单连接看门狗 | 三道防线：①Windows 计划任务 `-MultipleInstances IgnoreNew`（主防）②SDK 断线均审计留痕（无法精确识别"被踢"，见下）③三级重启退避 1min/5min/15min（`start-aibot-service.ps1` 自实现，Task Scheduler 原生不支持分级） | B 段读 SDK 源码核实修正 |
| D3：心跳/重连 | 采纳官方 SDK 内置默认（心跳 30s/2次未响判死；重连指数退避，**封顶硬编码 30s，非早前设想的可配 5min**）；`max_reconnect_attempts=6`，累计约 90s 耗尽交部署层 | 读 `aibot` SDK `ws.py` 源码核实 |
| D4：WS 库选型 | 采纳官方 SDK `wecom-aibot-python-sdk`（PyPI，v1.0.2）；outbound 素材上传 SDK 未封装，自行按官方文档三步协议（`aibot_upload_media_init/_chunk/_finish`）实现，复用 SDK 内部 `send_reply` ack 原语 | 实测源码，无需退化 `websockets` |
| D7：部门映射 | `department_mapping.yaml` 静态配置（姚祖怡→采购部/唐燕萍→财务部/陈忱→质量部/泓钦→销售部）；持有人 Paul、backup 孙涛；未命中 fail-closed 归 `7-外部文档/待分拣/`，队列行领取方=Paul | Paul 2026-07-11 三问拍板确认 |
| D8：门禁① | 结构性——`pyproject.toml` 依赖清单不含 `erp_connector`/`srm_connector`；`intake.py` 代码路径仅归档/登记/回执三类，无第四条路径；有单测 AST 扫描 + 依赖清单文本扫描双重核查 | design.md，不得放宽 |
| D8：门禁② | `delivery.py` 推送前强制断言 README 目标行「发送状态」列严格等于 `🆕 待发`，非此值一律拒绝 | design.md，不得放宽 |
| Non-Goal | 场景①不做自动扫描触发——推送由调用方显式指定具体某一行，服务只负责"断言+发送+回填" | 换取门禁②实现简单可靠 |

## 3. 复用底座资产

- **AibotConnector**（`zhuopin_platform.shared_tools.notifiers.wecom_aibot`）：连接生命周期事件转发 + `send_markdown`/`send_file`/`upload_media`/`download_file`；底层官方 SDK 懒加载（`client_factory` 可注入测试替身，未装 `[aibot]` extra 时模块仍可导入）。
- **SecretsProvider**：`zhuopin_platform.shared_tools.secrets.EnvSecretsProvider`，读 `WECOM_AIBOT_BOTID`/`WECOM_AIBOT_SECRET`（服务本地 `.env`，不入库）。
- **AuditLogger**：`zhuopin_platform.audit.AuditLogger.jsonl("reports/wecom_aibot_audit.jsonl")`，`scenario="wecom-aibot"`，`automation_level="L1"`（本服务无 L2 人工确认环节，专员均内部人员，见 proposal.md Impact）。
- **告警兜底**：`scripts/alert_webhook.py` 借道既有 `wecom.py` webhook（`WECOM_WEBHOOK_URL`，与本服务自身 BotID/Secret 是两套凭据）。

## 4. 红线（建造时守住）

> ⚠️ 两道门禁写死进代码结构，Paul 拍板不得放宽（见 §2 D8）。

- 🔴 归档服务（`intake.py`）**不得**依赖任何 ERP/SRM/CRM 连接器——`pyproject.toml` 刻意不含这些 extra，缺依赖即 `pip install` 失败，结构性拦截。
- 🔴 推送服务（`delivery.py`）**仅**发送 README 已标记"🆕 待发"（已定稿）的跟进信，草稿一律拒绝。
- 先 mock 跑通（`AibotConnector(client_factory=fake)` 全套单测）→ 再接真实凭据（F 段，待 Paul 完成队列 §四#10 前置动作）。
- 全部收发/归档动作写平台 `audit`（append-only，`AuditLogger.jsonl`）。
- OEM 隔离：本服务不涉及研发/OEM 技术数据，不适用。
- L2 门禁：不适用（专员均内部人员，`CUSTOMER_OUTBOUND_ENABLED` 不涉及本服务）。

## 5. 状态时间线

| 日期 | 状态 |
|------|------|
| 2026-07-11 | A 段完成：openspec `wecom-aibot-channel` 四件套（proposal/design/specs/tasks）产出，`validate --strict` 通过，Paul 审核批准（3 个 Open Questions 拍板：backup=孙涛/告警走现有项目群/待分拣兜底=Paul）。 |
| 2026-07-11 | B/C/D 段完成（同日）：连接层 MVP（`wecom_aibot.py`，读官方 SDK 源码核实心跳/重连/单连接边界的真实能力，design.md 已同步修正三处不准确的早期假设）+ 场景①推送跟进信（`delivery.py`/`readme_table.py`）+ 场景②反馈归档（`intake.py`/`frame_parsing.py`/`department_mapping.py`/`queue_appender.py`）+ 两道门禁（`gates.py`，含结构性静态核查单测）。平台+本服务全量回归：157 + 41 = 198 passed，2 skipped，零回归（含修复 `zhuopin_platform/tests/conftest.py` 的 Windows `asyncio.run()` self-pipe 回环误伤问题）。部署脚本（`deploy-server.ps1`/`sync-to-server.ps1`/`alert_webhook.py`/部署文档）完成，照抄 SC8 模式适配纯出站服务。 |
| 2026-07-13 | §四#10 解除：Paul 转真实 BotID/Secret（IT 已建智能机器人长连接模式），写入 `5-平台底座/.env`（gitignore 已核实覆盖，凭据未入任何 commit/日志/audit 明文）。`scripts/check_connection.py` 验证 `aibot_subscribe` 认证成功；`scripts/echo_test.py`（独立诊断脚本）在真实测试群收到 `@测试机器人` 消息并成功原样回声（企微截图确认），tasks.md 7.1 完成。抓到真实 WsFrame，确认 `sender=body.from.userid`/`chatid=body.chatid`，与代码原假设一致；design.md 对应 Risk 项标"已解决"。同日续：Paul 提供四位专员真实 userid（`YaoZuYi`=姚祖怡/`tangyanping`=唐燕萍/`ChenChen`=陈忱/`Hongqin.Wang`=王泓钦），`department_mapping.yaml` 中文名占位已换真实 userid + 单测同步更新，场景②对四域专员现已生效。 |
| 2026-07-13 | 生产路径真实联调（Paul 认可后跑 `run_aibot_service.py`，非诊断脚本）：ShaoPeiShen（未命中→待分拣）+ tangyanping（命中→财务部）共 5 条真实消息，`connection_established`/`authenticated`/`archived`/`mapping_unmatched`/`queue_appended` 全链路审计留痕核验通过，tasks.md 7.3 完成。**过程中发现并修复两个真实 bug**：① `intake.py` 归档文件名原按日期粒度，同人同天多条消息互相覆盖（真实测试 3 条只剩最后一条内容）——改按 `msgid` 消歧；② `queue_appender.py` 插入位置/编号计算无章节边界，越界跑进 §四（4 列表格、独立编号）、还把归档文件的**本机绝对路径**写进正式队列——改为限定 §一 范围内 + 队列指针改仓库相对路径。两处均补齐回归测试（`test_intake.py`/`test_queue_appender.py`），修复后重新真实验证一次行为正确；测试期间产生的错误队列行已清理。全量回归 43(本服务)+157(平台)=200 passed。tasks.md §8.1（拉进真实群）/8.4（场景②文本路径）完成；8.2（.51 出站实测）/8.3（场景①真实推送）/8.5（满周灰度）+ 7.2（断网重连自愈）仍未做；场景②**文件附件**路径仍未验证（唐燕萍发送文件时收到的始终是纯文本消息，未见 `msgtype="file"` 帧，怀疑是企微 UI"@+附件"组合发送方式的问题，待换发送方式重试）。 |
| 2026-07-13 | 场景①真实推送 + 素材上传 bug 修复：新增 `scripts/push_followup_letter.py`（此前设计缺失的场景①操作入口，D 段实现只有库函数没有 CLI）。用专造的测试用跟进信真实推送，首次调用即暴露 `upload_media` 请求体字段名错误——早期实现按不准确的网页摘要猜的 `filename`/`total_size`/`chunk_count`，真实 API 返回 `errcode=40058 body.type missing`；回查官方文档原文 JSON 示例后修正为 `type`(file/image/voice/video 枚举，必填)/`total_chunks`/`base64_data`/`md5`（可选，已补上）。修正后重新真实推送：markdown 正文 + docx 附件（真三步分片上传）均送达真实测试群，README 状态列正确回填，tasks.md 8.3 完成。单测同步更新为正确字段名，全量回归 200 passed。 |
| 2026-07-13 | inbound 文件路径验证 + 第四个 bug 修复：群聊"@提及+附件"组合确认不生效（多次尝试均只收到纯文字），改**私聊（1:1）发文件**成功——真实 `msgtype="file"` 帧下载解密成功。首次真实归档暴露 `_verify_no_corruption` 对所有归档文件不分文本/二进制一律做 UTF-8 解码校验的 bug：一份完好的真实 docx（ZIP 二进制）被误判"写入损坏"（早期 mock 单测的假字节巧合全落 ASCII 范围没测出来）。修复：新增 `expected_size` 参数，file 类改比对字节数；补充真·非 UTF-8 二进制内容的回归测试。修复后私聊重发验证：`archived`+`queue_appended` 正常，tasks.md 8.4 全部完成。全量回归 44(本服务)+157(平台)=201 passed。 |
| **当前** | **场景①②（文本+文档路径，含 outbound 推送与 inbound 归档）+连通性+echo+部门映射+审计+队列追加，均已在开发环境用真实数据验证通过；四个真实生产 bug 已发现并修复**（归档文件覆盖/队列越界写入/素材上传字段名错误/二进制归档误判损坏）。仍待：断网重连自愈（7.2）、满周灰度（8.5）。**.51 正式发布部署是场景模块开发完成后的独立后续动作**（见 §6 范围澄清），不计入本轮待办。未 `/opsx:archive`（tasks 未全 [x]）。 |

## 6. 关键依赖/前置（解锁条件）

> **范围澄清（Paul 2026-07-13）**：192.168.100.51 是**正式发布服务器**，本节以下条目全部在**开发环境构建系统**（本机）完成验证，与 .51 无关；.51 部署是场景模块开发完成、Paul 验收通过后的独立后续发布动作，另行安排时间。

- ~~🔴 队列 §四#10：Paul 企微后台建智能机器人 + BotID/Secret 交 CC~~ **✅ 2026-07-13 已解除**，`aibot_subscribe` 连通性+真实群 echo 双向收发均验证通过。
- ~~🔴 **`department_mapping.yaml` 需换真实 userid**~~ **✅ 2026-07-13 已换**：Paul 提供四位专员真实 userid（`YaoZuYi`/`tangyanping`/`ChenChen`/`Hongqin.Wang`），已替换中文名占位并同步更新单测，场景②对四域专员现已生效。
- ~~🟡 开发环境本机对 `wss://openws.work.weixin.qq.com` 的实际出站可行性~~ **✅ 已验证**（`scripts/check_connection.py` + 生产路径均通过）。.51 上的复测归入日后正式发布流程，不在本变更包范围。
- ~~🟡 场景②的企微消息发送人字段路径（userid vs 显示名）未经真实抓包验证~~ **✅ 已确认**：`sender=body.from.userid`、`chatid=body.chatid`，与代码假设一致。
- ~~🟡 素材上传三步协议（`upload_media`）未经真实凭据验证~~ **✅ 已验证**（2026-07-13）：首次真实调用暴露请求体字段名错误（`type`/`total_chunks`/`base64_data`/`md5`），修正后 docx 附件真三步分片上传+发送成功，见 tasks.md §8.3。
- ~~🟡 生产路径（`connection.py`/`intake.py`/`delivery.py` 的审计+归档+队列追加全链路）未跑通~~ **✅ 已跑通**（2026-07-13，Paul 认可后用 `run_aibot_service.py` 真实验证，非诊断脚本），过程中发现并修复归档文件覆盖 + 队列越界写入两个 bug，见 tasks.md 7.3。
- ~~🟡 **inbound 文件附件路径仍未验证**~~ **✅ 已验证**（2026-07-13）：群聊"@+附件"组合确认不生效，改**私聊发文件**成功；过程中发现并修复 `_verify_no_corruption` 对二进制文件误判损坏的第四个 bug，见 tasks.md §8.4。
- 🟡 断网重连自愈（tasks.md 7.2）与满周灰度（8.5）仍未做。
- 运行：`python scripts/run_aibot_service.py`（读 `.env`，本机/服务器均可跑）；测试：`pytest`（全程 mock，不触真实企微端点）。
