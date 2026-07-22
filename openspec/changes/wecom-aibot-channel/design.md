# 企微智能机器人双向通道服务 · Design

## Context

- 现状：`0-学习与工具/发企微.py` + 平台 `zhuopin_platform/shared_tools/notifiers/wecom.py` 是纯 webhook 群机器人，只发不收，跑在 Paul 本机（对公网 HTTPS 出站，off-LAN 可用）。
- 目标：新增「智能机器人」双向通道，接收模式用 WebSocket 长连接（`wss://openws.work.weixin.qq.com`），承接 v1 两场景：①推送跟进信（发+回填）②收专员反馈自动归档（R6 自动化）。
- Paul 已拍板三项部署决策（不再作为本 design 的决策点，直接采纳）：
  1. 常驻监听服务**最终**跑在 **LAN 服务器 192.168.100.51**（已跑 SC8「保供看板」`baoguan-web-service`，Windows 计划任务常驻）。**2026-07-13 Paul 澄清定位**：.51 是**正式发布服务器**；场景模块开发/联调阶段在**开发环境构建系统**（笔记本，本变更包 B-D 段的全部真实凭据联调均在此完成）进行，与 .51 无关——**部署到 .51 是场景模块开发完成后的正式发布动作，不属于本次开发验证范围**。见下方"部署位置澄清"。
  2. v1 只接现有一个项目群，不含专员单聊。
  3. 现有 webhook 通道保留并存，不做替代。
- 关键先例：SC8 `4-数字员工/采购部/SC8-客户订单交期智能承诺/` 是仓库里唯一的"真正常驻进程"先例——独立 `pyproject.toml` + 业务包 + `scripts/` 入口 + `deploy-server.ps1`（服务器端建 venv/装包/防火墙/注册计划任务）+ `sync-to-server.ps1`（笔记本端推代码热重启）+ 部署说明 md，纯 Windows 计划任务、无 Docker/systemd。其部署文档明确写出：三源（FO/U9C/企微 webhook）全走公网 HTTPS，`.51 只需出网，不需内网 6.x 子库`——即 **.51 已验证可对公网发起出站 HTTPS 请求**。
- 本服务与 SC8 的关键差异：SC8 是入站 HTTP 看板（LAN 内网访问，需开防火墙入站 8091），本服务是**纯出站 WebSocket 客户端**（不需要任何入站监听/端口/防火墙放行），风险面更小。

## Goals / Non-Goals

**Goals**：
- 建立稳定的企微智能机器人长连接（订阅/心跳/断线重连/单连接看门狗）。
- 场景①：按需推送指定跟进信（md+docx），成功后回填 README 状态列。
- 场景②：被动接收专员消息/文件，全自动按 R6 规则归档 + 登记 + 追加队列待领行。
- 两道门禁写死进代码结构（而非仅靠配置开关），最小化误触发面。
- 收发全量动作写平台 `AuditLogger`。

**Non-Goals**（v1 明确不做）：
- 不做专员单聊接入（留 F 段真实群灰度一周后评估）。
- 不做"自动定时扫描 README 触发推送"——场景①的推送动作由调用方（CC/专线人工判断某封信已就绪）显式触发指定某一封信，服务只负责"发送 + 回填"，不自主决定发哪封。这样门禁②（仅定稿可发）退化为一次简单的状态列断言，而不需要任何语义判断。
- 不做任何 LLM 语义分类（发送人→部门映射用静态配置表，归档命名用确定性规则，不引入 AI 摘要/分类判断）。
- 不改造现有 webhook 通道 `wecom.py`，不做迁移。
- 不接入 ERP/SRM/CRM——本服务的依赖清单里**结构性不包含**任何业务系统连接器（见下方门禁①实现）。

## Decisions

### D1. 目录归属：平台侧独立服务目录，不挂靠任何部门场景

**决策**：新建 `5-平台底座/wecom-aibot-service/`（与 `zhuopin_platform/` 同级），结构照抄 SC8 先例：
```
5-平台底座/wecom-aibot-service/
├── pyproject.toml              # 依赖 zhuopin_platform（pip install -e）+ WS 客户端库
├── aibot_service/
│   ├── connection.py           # 长连接生命周期：订阅/心跳/重连/看门狗
│   ├── delivery.py             # 场景①：推送 + README 回填
│   ├── intake.py                # 场景②：归档 + 登记 + 队列追加
│   ├── department_mapping.yaml # 发送人→部门静态配置（非代码）
│   └── gates.py                 # 两道门禁的显式断言函数
├── scripts/run_aibot_service.py  # 入口：读 .env → 建连接 → 阻塞运行
├── deploy-server.ps1            # 照抄 SC8：建 venv/装包/注册计划任务（无需开防火墙，纯出站）
├── sync-to-server.ps1           # 照抄 SC8：笔记本端推代码 + 热重启
├── tests/
└── 部署到长开服务器-企微智能机器人.md
```

**理由（对比考虑）**：
- 方案 A（选定）：独立平台服务目录。理由：本服务服务四域专员，不属于任何单一部门场景（不像 SC8 归采购部），塞进 `4-数字员工/<部门>/` 会造成"采购部目录里跑着财务/质量/销售专员的归档逻辑"的错位归属，日后交接/CLAUDE.md 场景说明会混乱。
- 方案 B（否决）：直接塞进 `zhuopin_platform/` 包内部（如 `zhuopin_platform/aibot_service/`）。否决理由：`zhuopin_platform` 定位是"可编辑安装的库"，被动导入、无自己的部署/常驻概念；把一个需要 `deploy-server.ps1`/计划任务/长期运行的进程混进库目录，会破坏"库 vs 服务"的边界，且每次场景 `pip install -e` 平台包时会连带装入这个服务的 WS 依赖（污染所有场景的依赖树）。
- 方案 C（否决）：挂靠 SC8 目录（因为都跑在 .51、可复用部署脚本）。否决理由：SC8 目录的 CLAUDE.md/README 明确是"客户订单交期智能承诺"场景说明，混入企微机器人会让该场景文档失焦；两者仅"同机部署"这一点相似，不构成"同目录"的理由。
- 连接器 SDK 薄封装（`aibot_subscribe`/`aibot_send_msg`/素材上传的函数级封装，无状态、可被其他场景直接调用）单独放 `zhuopin_platform/shared_tools/notifiers/wecom_aibot.py`，与现有 `wecom.py` 同目录同风格——这部分确实是"库"性质（纯函数，无长连接状态），符合平台底座定位，`wecom-aibot-service` 依赖它而不重复实现协议细节。

**部署位置澄清（Paul 2026-07-13 补充定位，不是新决策，只是把"哪个阶段用哪台机"说清楚）**：
- **开发环境构建系统**（笔记本/当前工作机）：场景模块（本变更包）开发、单测、**以及本次全部真实凭据联调**（B-D 段代码、连接层验证、场景①②真实推送/归档验证，均在此机器完成，用真实 BotID/Secret+真实测试群）都在这里做，与 .51 无关。
- **192.168.100.51（正式发布服务器）**：SC8 保供看板等**已完成开发、进入正式运行**的场景才部署在这里。本服务要等"场景模块开发完成"（即 tasks.md 全部 [x]、Paul 验收通过）之后，才轮到照抄 SC8 模式部署到 .51——这是**独立于本次开发的后续发布动作**，`deploy-server.ps1`/`sync-to-server.ps1`/部署文档已提前备好，但**执行时机由 Paul 在场景模块验收后另行安排**，不在本变更包 tasks.md 的验收范围内。

### D2. 单连接看门狗：Windows 计划任务"不启动新实例" + 企微侧踢旧连接兜底两道防线

**决策**：
1. 计划任务层（第一道防线，主防）：`schtasks` 注册时设置"如任务已在运行，不再启动新实例"（对应 SC8 `BaoguanWebServer` 计划任务已有类似防重复配置，照抄）——同一时刻 .51 上只应有一个 `run_aibot_service.py` 进程，从源头避免双实例互踢。
2. 应用层（第二道防线，退化处理，**经 D4 SDK 源码核实修正**）：官方 SDK 的 `disconnected` 事件只给通用 `reason: str`（WebSocket 关闭帧原因字符串），**不区分"被新连接踢下线"与其他断线原因**——应用层无法精确识别"是否被踢"，故不采用"识别到被踢就退出不重连"的精确策略，改为：`max_reconnect_attempts` 设为**有限值**（6 次，而非 SDK 默认的 10 或无限的 -1），耗尽后 SDK 放弃重连并触发 `error` 事件，服务进程记审计后退出，把"是否要恢复"的判断交还给下一道防线（计划任务重启退避）——本质是用"重连预算耗尽即认输"代替"精确识别被踢"，效果等价（都能避免无限抢连接），但不依赖 SDK 未提供的精细信号。累计耗时见 D3（约 1-2 分钟即耗尽，非早前估计的 15-20 分钟——见 D3 对 SDK 重连上限的修正）。
3. 计划任务失败重启策略（第三道防线）：故障重启退避 = 1 分钟 / 5 分钟 / 15 分钟三级（区别于 SC8 固定"失败重启3次"，本服务加大退避间隔是为了避免频繁重连撞上 `aibot_subscribe` 的频率保护）；三次退避后仍失败 → 停止重启并**通过现有 webhook 通道**（`wecom.py`，非本服务自身）发一条告警到项目群——自身故障时不能指望自己的通道通知，这是把 webhook 保留并存的额外价值。

### D3. 心跳与重连退避（**经 D4 SDK 源码核实修正数值**）

**决策**：
- 心跳：官方 SDK 内置，默认 30 秒一次，连续 2 次未收到 pong 判定连接失效并主动断开（`ws.py::_send_heartbeat`，`_max_missed_pong=2`），采纳默认值不额外改造。
- 重连退避：官方 SDK 内置指数退避，基础延迟可配（`reconnect_interval`，本服务设 2000ms），倍增，**但封顶硬编码 30 秒**（`ws.py::_reconnect_max_delay=30000`，非早前设想的可配 5 分钟——已读源码确认此值不经 `WSClientOptions` 暴露，不做侵入式 monkeypatch 覆盖私有属性，接受 SDK 默认封顶）。配合 D2 的 `max_reconnect_attempts=6`：2s→4s→8s→16s→30s(封顶)→30s，累计约 **90 秒**耗尽重连预算，随即交给计划任务重启退避（D2 第三道防线）接手，比早前估计的"15-20 分钟耗尽"快得多——即"应用层快速认输、部署层兜底"，两层退避总窗口反而更短更可控。
- 官方文档未给出 `aibot_subscribe` 频率限制的具体数值阈值，上述参数为工程保守估计，**F 段真实群灰度联调时观察实际限流表现后可调**（不视为需要重新过 design 审的架构变更，允许作为参数微调）。

### D4. WS 客户端库选型：采用官方 SDK，素材上传自行按文档协议补齐

**决策（B 段已验证，结论落定）**：官方 SDK `wecom-aibot-python-sdk`（v1.0.2，PyPI，MIT，2026 年内维护中）已封装：WSS 长连接建立、`aibot_subscribe` 自动认证、心跳保活（默认 30s，连续 2 次未收到 pong 判定连接失效）、断线重连（默认指数退避 1s→2s→4s→…→30s 封顶，`max_reconnect_attempts` 可配，默认 10 次）、`aibot_send_msg` 主动发送（markdown/template_card）、inbound 文件下载+AES-256-CBC 解密（`download_file`）、消息类型分发（text/image/mixed/voice/file 均触发对应事件）。**采纳该 SDK，不再手工实现协议层**，理由：实测其 `ws.py`/`client.py` 源码（非仅读文档）质量扎实、依赖合理（`websockets`+`aiohttp`+`pyee`+`cryptography`），比自行实现心跳/重连/串行回复 ACK 队列风险低得多。

**已知缺口（SDK 未覆盖，需在 `wecom_aibot.py` 里自行补齐）**：
1. **outbound 素材上传未封装**——SDK 的 `send_message` 仅支持 `markdown`/`template_card` body，无文件/图片上传能力；`WeComApiClient` 也只有 `download_file_raw`（inbound）。官方文档另有 `aibot_upload_media_init`/`aibot_upload_media_chunk`/`aibot_upload_media_finish` 三个 WS cmd（单分片 ≤512KB、最多 100 分片、初始化后 30 分钟内传完、素材 3 天有效），SDK 未实现。我们在 `wecom_aibot.py` 里补一个 `upload_media(ws_client, file_bytes, filename, media_type="file")` 函数，复用 `WSClient` 内部 `_ws_manager.send_reply(req_id, body, cmd)` 这个通用"发帧+等 ACK"原语（与 SDK 自身 `send_message` 的实现模式一致，非破坏性 hack）实现三步分片协议，返回 `media_id` 供 `send_message({"msgtype":"file","file":{"media_id":...}})` 引用。**✅ 已用真实凭据验证通过（2026-07-13）**：首次真实调用时 `aibot_upload_media_init` 请求体字段名猜错（早期按不准确的网页摘要写的 `filename`/`total_size`/`chunk_count`，被真实 API 拒绝 `errcode=40058 body.type missing`）——回查官方文档原文 JSON 示例后修正为 `type`（必填，file/image/voice/video 枚举）/`filename`/`total_size`/`total_chunks`/`md5`（可选，已补上），分片帧字段名同步修正 `data`→`base64_data`。修正后真实端到端测试：markdown 正文 + docx 附件（三步分片上传）均成功送达真实测试群，README 状态列正确回填。单测同步更新为正确字段名。
2. **被踢下线无独立信号**——SDK 的 `disconnected` 事件只给通用 `reason: str`（WebSocket 关闭帧原因），不区分"被新连接踢下线"与"网络异常断开"，故 D2 的"被踢即退出不重连"策略在 SDK 层无法精确实现（SDK 收到任何断线都会走同一套重连逻辑）。**调整**：不在应用层区分断线原因，转而把"防止双实例互踢"的责任完全放在部署层（D2 的 Windows 计划任务单实例保证）；同时把 `max_reconnect_attempts` 设为**有限值（而非 -1 无限）**，超过后交还给计划任务的三级重启退避（D2），避免应用层重连与计划任务重启形成双重循环。此为 D2/D3 的实现层修正，不改变"心跳+重连退避+单实例看门狗"的既定架构。

### D5. 凭据管理

**决策**：复用平台既有 `zhuopin_platform/shared_tools/secrets.py` 的 `SecretsProvider` Protocol，`EnvSecretsProvider` 从服务本地 `.env` 读取 `WECOM_AIBOT_BOTID`/`WECOM_AIBOT_SECRET`。`.env` 只存在于 .51 服务器本地（`deploy-server.ps1` 建服务时手工放置一次，不随代码同步/不入库/不走 OneDrive），与 SC8 `.env` 管理方式一致。

### D6. 审计集成

**决策**：复用 `zhuopin_platform/audit/logger.py` 的 `AuditLogger.jsonl(...)`，独立日志文件 `reports/wecom_aibot_audit.jsonl`（服务目录本地）。记录事件类型覆盖：连接建立/断开/被踢、心跳异常、消息接收（场景②触发）、归档动作（成功/失败+落档路径）、队列追加、发送尝试（场景①，含门禁②拒绝原因）、README 回填。全部经 `AuditEvent`（`scenario="wecom-aibot"`, `automation_level` 按门禁语境标注）落链式哈希留痕，不重建审计骨架。

### D7. 发送人→部门映射配置

**决策**：`aibot_service/department_mapping.yaml`，键值对形式（企微字段→部门），非代码硬编码、可被 Paul/CC 直接编辑：
```yaml
# 键：企微消息 from 字段（B 段联调时抓包确认具体用 userid 还是显示名，见 Open Questions）
姚祖怡: 采购部
唐燕萍: 财务部
陈忱: 质量部
泓钦: 销售部
```
未命中映射表的发送人 → **fail-closed 归入 `7-外部文档/待分拣/`**（不猜测部门），并在 audit 记 `mapping_unmatched`，同时向跨桌任务队列追加一条"待领"行、**领取方=Paul 本人**（Paul 2026-07-11 拍板，作为兜底责任人定期清理），而不是静默丢弃或误归档到错误部门。映射表持有人=Paul，backup=**孙涛**（Paul 2026-07-11 确认，随 §5 决策代理纪律）。

### D8. 两道门禁的代码级实现（写死，非配置开关）

- **门禁①（场景②，只归档/登记/通知）**：结构性保证——`wecom-aibot-service` 的 `pyproject.toml` 依赖清单中**不包含**任何 ERP/SRM/CRM 连接器（`zhuopin_platform.shared_tools.erp_connector`/`srm_connector` 均不引入）。`intake.py` 的函数签名只允许返回三种动作：写文件（归档）、追加队列行、调用 `wecom_aibot.send_msg` 发确认收讫回执——没有第四条代码路径。即使未来误改代码试图接入业务系统，也会在 `pip install` 阶段因缺少对应连接器包而直接失败，形成结构性拦截而非仅靠 code review 自觉。
- **门禁②（场景①，仅定稿可发）**：`delivery.py` 的推送函数强制要求调用方传入 README 表格行引用，函数内部**读取该行状态列**、断言其值严格等于 `"🆕 待发"`（README 既有约定值）——非此值一律拒绝并记 audit `reason="not_finalized"`，不发送。发送成功后原子写回状态列为 `"✅ 已推送 <时间戳>"`。

### D18. 归档链路健壮性补强——并发覆盖修复 + 对账哨兵 + IT 部门映射（2026-07-22，队列 #69/#70）

**触发**：2026-07-21 唐燕萍那条归档，审计日志确认 `archived`+`queue_appended` 两个事件均记录成功，但对应队列行从未出现在任何一次 git 提交里——只能靠总线人工事后补登（队列 #69）。

**根因**：`queue_appender.append_pending_task` 此前是纯粹的 `read_text` → 内存计算 → `write_text`，全程无冲突检测。本文件同时被①机器人进程直接写、②人工/Cowork/CC 会话通过 Read+Edit/Write 编辑，两者共享同一份磁盘文件、没有锁、没有版本号。若某个编辑会话在机器人追加之前读入内存、在追加之后才写回（哪怕只是改动文件里完全无关的另一处），就会拿着不含该追加行的旧内容整体覆盖磁盘，静默丢弃机器人的写入——丢失发生在任何 git 提交之前，无法从版本历史精确回溯是哪一次编辑造成，但机制本身可稳定复现（见 `test_queue_appender.py` 的并发模拟用例）。

**决策**：不引入真正的跨进程文件锁（对这种人工节奏的低频编辑场景，锁的复杂度/收益不成正比——需要处理锁残留、Windows 文件锁语义、跨 worktree 场景等）。改用两层防线：
1. **乐观并发重试**（根治写手自身）：`append_pending_task` 在最终写入前重新读一次磁盘，若与本轮计算所依据的初始内容不一致，放弃本轮结果、按最新磁盘内容重新计算插入点与编号再试（`max_retries` 默认 5 次，耗尽后显式 `RuntimeError` 而非静默吞掉或死循环）。仍无法做到 100% 消除竞态（重读核验和最终写入之间仍有微秒级窗口），但把原来"整个函数调用期间"的竞态窗口收窄到"最后一次读+写之间"，对本场景是数量级的收窄。
2. **归档↔队列对账哨兵**（兜底捕获其他路径的类似丢失，`queue_reconcile_sentinel.py`）：每次连接成功后（与 `gap_alert` 同一触发点）扫描近 7 天的 `archived` 审计事件，逐条核对其归档文件名（含消歧哈希后缀）是否整串出现在当前队列文件全文里——出现即视为已覆盖，不解析表格结构、不做更精细的行级匹配，避免哨兵自身的解析逻辑成为新的误判来源。发现疑似漏行时，**只私信 Paul 一条汇总报告**（列出全部漏行的文件名+发送人+时间戳），**本次不自动写队列**：自动补行本身依赖对表格结构又一次解析/编号计算（可能再引入 bug 或再次撞上并发写），且"归档了但没进队列"里可能包含合理例外（如 `append_pending_task` 本身抛错但被上层吞掉），不宜不问青红皂白就自动补一行。观察一段时间（建议 1-2 周）确认误报率可接受后，自动补行留作二期，登记跨桌任务队列待领行。

**顺带处理**：`department_mapping.yaml` 补入陈承（IT，userid `2023458`）→ `IT`——此前陈承虽在白名单里（2026-07-16 起），但不在部门映射表，命中白名单后仍落"待分拣"；本次起直接归档进 `7-外部文档/IT/`。IT 不是 Cowork 的四域专线之一，`intake.py::DEPARTMENT_TO_QUEUE_OWNER` 未新增 "IT" 项，队列行领取方按现有 fail-closed 逻辑落回默认值 Paul（与"完全未命中发送人"共用同一默认值），不臆造一个不存在的"IT专线"角色。

**验证**：`test_queue_appender.py` +2（模拟并发写手插队、验证重算不覆盖 / 持续竞态耗尽重试后报错）、新增 `test_queue_reconcile_sentinel.py`（12 例）、`test_department_mapping.py`/`test_connection.py`/`test_intake.py` 同步更新覆盖 IT 映射新行为。全量回归零漂移。

## Risks / Trade-offs

- ~~**[风险] .51 是否能对 `wss://openws.work.weixin.qq.com` 完成 WebSocket 握手未实测**~~ **✅ 已解决（2026-07-13）**：在开发机上用真实 BotID/Secret 完成端到端连通性测试（`aibot_subscribe` 认证成功、心跳正常 30s 一次、真实测试群双向收发+echo 全部验证通过）。**注**：该测试跑在本机而非 .51，.51 的出站可行性仍类推自 SC8 webhook 出站正常的先例，未单独在 .51 上验证——F 段实际部署到 .51 时建议用同一支 `scripts/check_connection.py` 复测一次，成本很低。
- **[风险] 官方文档未给出 `aibot_subscribe` 频率限制的具体数值**，重连退避参数为工程估计，联调时若仍触发限流，服务会陷入"越重连越被限流"的恶性循环。→ **缓解**：D2 的"重连预算耗尽即认输"+D3 指数退避（SDK 封顶 30s），双重降低重连频率；发生限流时 audit 会留下 `disconnected`/`connection_error` 记录可追溯诊断。
- ~~**[风险] 部门映射依赖企微消息实际携带的发送人字段格式**（userid vs 显示名 vs 企业通讯录 ID），B 段前不可验证。~~ **✅ 已完全解决（2026-07-13）**：字段路径确认 `sender = body.from.userid`、`chatid = body.chatid`（群聊场景），与 `frame_parsing.py` 原实现假设一致，代码未改。**`department_mapping.yaml` 已换成 Paul 提供的四位专员真实 userid**（`YaoZuYi`=姚祖怡→采购部 / `tangyanping`=唐燕萍→财务部 / `ChenChen`=陈忱→质量部 / `Hongqin.Wang`=王泓钦→销售部），场景②对四域专员现已生效，单测同步更新。
- **[Trade-off] 场景①不做自动扫描触发**（Non-Goal 已声明），意味着"推送"仍需人工/专线显式调用，未达到"完全免手工"，但换来门禁②实现简单可靠（一次状态断言 vs 语义判断"是否已定稿"）。后续若需要全自动，可在 v2 加一个显式的"人工点击确认发送"UI 环节，而不是靠代码猜测。
- **[风险，源码核实新发现] SDK 的重连计数在 TCP+TLS 握手成功时即重置**（`ws.py::connect()`），不是在"认证成功"或"稳定运行一段时间"后才重置——若出现"握手成功但立即被断开"的病态场景（如认证失败但底层连接短暂建立），`max_reconnect_attempts` 的封顶可能被反复重置而形同虚设。→ **缓解**：不改造 SDK 内部逻辑（风险更高），而是让部署层（D2 第一道防线）从根本上避免"同时存在两个尝试连接的实例"这个病态场景的触发条件；另在 `connection.py` 里对 `authenticated` 事件与 `disconnected` 事件的时间差做旁路计数（应用层自己再叠加一层"认证从未成功次数"熔断，与 SDK 内部计数器独立），双保险。

## Migration Plan

1. B 段：.51 建虚拟环境 → `pip install -e 5-平台底座/zhuopin_platform` + `pip install -e 5-平台底座/wecom-aibot-service` → 装 WS 依赖 → 用**测试群**假凭据/或 Paul 完成前置动作后的真实测试群凭据做最小连接测试（仅 echo，不接两个业务场景）。
2. C/D 段：接入两个业务场景逻辑，单元测试覆盖两道门禁（mock 连接层，不依赖真实企微）。
3. `deploy-server.ps1` 注册计划任务 `WecomAibotService`（照抄 SC8 命名风格），`sync-to-server.ps1` 走笔记本→服务器代码同步。
4. F 段：Paul 完成前置动作（真实 BotID/Secret+拉进真实项目群）后灰度一周，验收清单见 proposal.md「晋下一档的条件」。
5. **回滚**：`schtasks /End /TN WecomAibotService` 停止计划任务即可完全下线，不影响现有 webhook 通道（两者代码独立、无共享状态），零回归风险。

## Open Questions（供 Paul 拍板）—— ✅ 已于 2026-07-11 全部拍板，design 审核通过

1. ~~**部门映射表 backup 持有人**：D7 映射表持有人=Paul，是否确认 backup=孙涛（随 §5 决策代理纪律）？~~ **✅ 确认，backup=孙涛。**
2. ~~**服务自身故障告警去向**：D2 三级退避耗尽后的告警，默认发到现有项目群（借道 webhook 通道）——是否需要改发到 Paul 个人企微或其他渠道？~~ **✅ 确认，维持默认方案：发到现有项目群（借道 webhook）。**
3. ~~**`7-外部文档/待分拣/` 的后续处理责任人**：D7 未命中映射的文件落"待分拣"后，是否需要指定一个默认兜底责任人？~~ **✅ 确认，兜底责任人=Paul 本人**（D7 补记：`待分拣` 目录追加的队列待领行领取方=Paul，定期清理无长期堆积）。
