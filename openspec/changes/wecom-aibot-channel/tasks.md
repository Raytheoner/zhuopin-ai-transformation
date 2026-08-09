> **预期观察窗口：待定**（队列 #314②，2026-08-09 判定，未声明数值窗口）——如实登记：本包剩余未完成项**不是纯被动观察项**，故不套用观察窗口机制，维持现状（正常"疑似遗忘归档"告警流程）。判据：7.2（人为断网重连自愈验证）与 9.1-9.4（场景 `CLAUDE.md` 撰写／队列 #18 回写／文档台账重跑／commit）均是当前即可主动完成的具体工作，非等待外部触发；8.5（真实群运行满一周）虽属观察型，但其观察时钟尚未起算——阻塞点是"在开发环境跑满周还是等 `.51` 正式发布后再计"这一决策，需 Paul 定，与"已在观察、等窗口到期"性质不同；10.5（二期 dry-run 观察）已明写"本次不做，登记后续待领行"，不计入本包当前范围。**⇒ 若要让本包受益于观察窗口机制，须先完成 7.2/9.1-9.4 或补齐 8.5 的前置决策，届时可重新声明窗口**——本次不代为判断或代为拍板，如实登记交后续处理。

## 1. 脚手架

- [x] 1.1 新建 `5-平台底座/wecom-aibot-service/`（`pyproject.toml` 依赖 `zhuopin_platform[aibot]`（`pip install -e`）+ WS 客户端库；`aibot_service/` 包骨架：`connection.py`/`delivery.py`/`intake.py`/`gates.py`/`readme_table.py`/`department_mapping.py`/`frame_parsing.py`/`queue_appender.py`；`scripts/run_aibot_service.py`；`tests/`）
- [x] 1.2 新增 `zhuopin_platform/shared_tools/notifiers/wecom_aibot.py`（连接器 SDK 薄封装，与 `wecom.py` 同目录同风格）

## 2. WS 客户端库选型验证（D4）

- [x] 2.1 试装官方 SDK `wecom-aibot-python-sdk`，评估是否已封装心跳/重连/订阅/素材上传——**结论：采纳**，心跳/重连/订阅/inbound 下载解密均已封装，质量扎实（读源码非仅读文档）；outbound 素材上传未封装，已在 `wecom_aibot.py` 补齐三步协议（复用 SDK 内部 `send_reply` ack 原语）
- [x] ~~2.2 若 SDK 不满足，退化为 `websockets` 库手工实现协议层~~ **N/A（未触发）**：SDK 评估通过，未走退化路径

## 3. 连接层 MVP（对应 spec `wecom-aibot-connector`，D2/D3/D5/D6）

- [x] 3.1 实现订阅凭据经 `SecretsProvider` 注入（`connection.py::build_connector`，`EnvSecretsProvider` 读 `.env`，缺凭据 fail-loud 抛 `KeyError`）
- [x] 3.2 心跳——**采纳 SDK 内置默认值**（30s 间隔，连续 2 次未收到 pong 判定失效），未额外改造
- [x] 3.3 断线重连退避——**采纳 SDK 内置指数退避**，`max_reconnect_attempts` 收窄为 6（`reconnect_base_delay_ms=2000`）；**已核实 SDK 封顶硬编码 30s（非早前设想的可配 5 分钟）**，design.md D3 已同步修正
- [x] ~~3.4 `disconnected_event`（被踢下线）识别 → 记审计 → 进程退出（不重连）~~ **设计已修正（design.md D2 point 2）**：SDK 未提供可区分"被踢"的信号，改为"重连预算耗尽即认输"策略——任意断线原因均审计留痕（`action="disconnected"`），预算耗尽触发 `action="connection_error"`，交部署层计划任务重启退避兜底
- [x] 3.5 实现 `send_markdown`/`send_file`（`aibot_send_msg` 封装）+ `upload_media`（三步分片协议，SDK 未覆盖，自行实现）+ `download_file`（inbound 解密下载）
- [x] 3.6 全部连接生命周期事件（建立/认证/断开/重连中/错误）与收发动作接入 `AuditLogger.jsonl`（`wecom-aibot-service/reports/wecom_aibot_audit.jsonl`）
- [x] 3.7 单测：`zhuopin_platform/tests/test_wecom_aibot.py`（11 tests，mock `AibotClientLike` 替身）+ `wecom-aibot-service/tests/test_connection.py`（5 tests，生命周期事件转审计、凭据缺失、inbound 消息分发）——覆盖发送成功/失败、素材上传单/多分片/超限/缺字段、事件转发、凭据校验

## 4. 场景①推送跟进信（对应 spec `wecom-followup-delivery`，D8 门禁②）

- [x] 4.1 实现 `delivery.py` + `readme_table.py`：接收 README 行匹配函数 → 定位「发送状态」列 → 断言值严格等于 `🆕 待发`
- [x] 4.2 非待发状态一律拒绝发送，抛 `DeliveryNotFinalizedError` + 记审计 `action="delivery_rejected", reason="not_finalized"`
- [x] 4.3 待发状态：读取对应 `.md`/`.docx` → 经连接器推送（markdown + 可选 docx 素材上传/发送）→ 成功后原子回填 README 状态列为 `✅ 已推送 <UTC 时间戳>`
- [x] 4.4 发送成功但回填失败时抛 `BackfillWriteError`（不掩盖"已发送"事实），审计留痕 `followup_delivered`（sent=True）+ `followup_backfill_failed`
- [x] 4.5 单测：`test_delivery.py`（4 tests）——happy path（含/不含 docx）、门禁②拒绝、回填失败仍报错且不吞发送成功事实

## 5. 场景②收专员反馈自动归档（对应 spec `wecom-feedback-intake`，D7/D8）

- [x] 5.1 实现 `intake.py` + `frame_parsing.py`（inbound WsFrame → `InboundMessage` 中间结构，隔离未经真实验证的字段路径假设）：文件类走 `connector.download_file` 解密下载，文本类落 `.md`
- [x] 5.2 实现 `department_mapping.yaml`（姚祖怡→采购部/唐燕萍→财务部/陈忱→质量部/泓钦→销售部，持有人 Paul/backup 孙涛）+ `department_mapping.py` 加载逻辑
- [x] 5.3 未命中映射 fail-closed 归入 `7-外部文档/待分拣/`，记审计 `mapping_unmatched`，队列行领取方标注 Paul（design.md D7 拍板）
- [x] 5.4 按 R4/R6 命名规范（`部门-发送人-回复-日期-事项.ext`）落档至 `7-外部文档/<部门>/`；写后立即读回校验文件名+内容无 U+FFFD，校验失败抛 `ArchiveCorruptionError` + 记审计 `archive_corruption_detected`
- [x] 5.5 归档成功后向 `跨桌任务队列.md` §一追加"待领"行（`queue_appender.py`，领取方按部门映射域专线；待分拣件领取方=Paul）
- [x] 5.6 结构性门禁①核查：`pyproject.toml` 依赖清单不含 `zhuopin_platform[erp]`/`[srm]` 等业务连接器 extra；`intake.py` 代码路径仅归档/登记/（回执由调用方决定）三类动作
- [x] 5.7 单测：`test_intake.py`（5 tests：文本/文件归档、映射未命中、不支持类型、乱码检测）+ `test_gates.py`（4 tests：门禁②断言 + 门禁①依赖清单静态扫描 + intake.py AST 扫描）+ `test_department_mapping.py`（6 tests）+ `test_frame_parsing.py`（5 tests）+ `test_queue_appender.py`（3 tests）+ `test_readme_table.py`（5 tests）

## 6. 部署与运维脚本（D1/D2 迁移计划）

- [x] 6.1 `deploy-server.ps1`（照抄 SC8 模式：.51 建 venv → 装包 → **不开防火墙入站**（纯出站服务）→ 生成 `start-aibot-service.ps1` 三级退避包装 → 注册 Windows 计划任务 `WecomAibotService`，`-MultipleInstances IgnoreNew`"已运行则不启动新实例"）
- [x] 6.2 三级退避耗尽后的告警：`start-aibot-service.ps1` 内实现退避循环（1min/5min/15min），耗尽后调用 `scripts/alert_webhook.py` 经现有 `wecom.py` webhook 通道发送项目群（不依赖本服务自身通道）——**未做**：Windows 计划任务本身的 RestartCount/RestartInterval 不支持真正的分级退避，故改为包装脚本自行实现，已在部署文档说明此差异
- [x] 6.3 `sync-to-server.ps1`（照抄 SC8 模式：笔记本端推代码 + 计划任务热重启；因本服务无端口，重启前清旧实例改用命令行匹配 `wmic` 而非按端口找 PID）
- [x] 6.4 `部署到长开服务器-企微智能机器人.md`（部署说明，含 .51 出站验证结论引用 + 两套凭据并存说明）

## 7. 测试群验收（mock/测试凭据先行，对应 §7-1 先 mock 再切真实）

- [x] 7.1 用测试群真实凭据做最小连接测试：仅 echo（收到 @消息原样回），不接两个业务场景——**2026-07-13 完成**：`scripts/check_connection.py` 确认 `aibot_subscribe` 认证成功；`scripts/echo_test.py`（诊断专用，独立于生产路径）在真实群收到 `@测试机器人 测试一下` 并成功原样回声，企微客户端截图确认。**副产物**：抓到真实 WsFrame，确认 `sender=body.from.userid`（企微 userid，非中文名）/`chatid=body.chatid`，已更新 `frame_parsing.py` 文档注记 + design.md Risks；**✅ 新发现已解决**：Paul 同日提供四位专员真实 userid，`department_mapping.yaml` 已替换 + 单测同步更新
- [ ] 7.2 验证断网重连自愈（人为断网/杀进程观察退避与恢复）——**未做**，本次只验证首次连接+收发，未做断线场景
- [x] 7.3 全程审计留痕核验（`AuditLogger.query_by` 可查得完整生命周期事件链）——**2026-07-13 完成**：Paul 认可后跑通生产路径（`run_aibot_service.py`，非 echo 诊断脚本），真实收到 ShaoPeiShen（未命中，归待分拣）+ tangyanping（命中财务部）共 5 条消息，`connection_established`/`authenticated`/`archived`/`mapping_unmatched`/`queue_appended` 全链路审计事件均在 `reports/wecom_aibot_audit.jsonl` 里查得。**过程中发现并修复两个真实 bug（均已补回归测试）**：① 同发送人同天多条消息归档文件名只到日期粒度，互相覆盖（真实测试 3 条消息只剩最后一条内容）——修复为按 `msgid` 消歧；② `queue_appender.append_pending_task` 插入位置/编号计算未设章节边界，越界跑进了 §四（4 列表格、独立编号），还把归档文件的**本机绝对路径**写进了正式队列——修复为限定在 §一 自己的表格范围内 + 队列指针改仓库相对路径。修复后重新真实验证一次，行为正确（新行落 §一、编号延续 18→19、指针是相对路径）。测试期间产生的 4 条错误队列行已从 `跨桌任务队列.md` 手工清除，本行到 #19 为止是修复验证后的**真实、格式正确**结果

## 8. 开发环境真实联调（依赖 Paul 完成队列 §四#10 前置动作，本任务不得早于该动作完成）

> **范围澄清（Paul 2026-07-13）**：192.168.100.51 是**正式发布服务器**，本节全部在**开发环境构建系统**（笔记本/当前工作机）完成，与 .51 无关；.51 部署是场景模块开发完成、Paul 验收通过后的**独立后续发布动作**，另行安排时间，不在本变更包 tasks.md 验收范围内（原 8.2 的".51 出站实测"已按此改写）。

- [x] 8.1 确认 Paul 已完成：企微后台建智能机器人 → 开长连接模式 → BotID/Secret 交 CC 入 `.env`——**2026-07-13 完成**（写入 `5-平台底座/.env`，开发环境本机）；已拉进真实项目群（"财务部AI保障组"，另含质量/采购群）
- [x] 8.2（原".51 出站实测"，已按范围澄清改写）开发环境本机对 `wss://openws.work.weixin.qq.com` 的实际连接测试——**2026-07-13 完成**（`scripts/check_connection.py` + 生产路径 `run_aibot_service.py` 均验证通过）。**.51 上的出站可行性验证归入日后正式发布流程**，届时用同一支 `scripts/check_connection.py` 复测即可，不在本变更包范围内
- [x] 8.3 真实群跑通场景①一次（既有跟进信推送成功 + README 回填验证）——**2026-07-13 完成**：专造一封测试用跟进信（`财务部-唐燕萍-跟进-2026-07-13-企微双向通道联调测试.md/.docx`，README 标注非真实业务信件，不动真实业务信件）+ 新增手动触发工具 `scripts/push_followup_letter.py`（此前设计里缺失的场景①操作入口，design.md Non-Goal 要求"调用方显式指定"但一直没有 CLI）。首次真实调用即暴露 `upload_media` 请求体字段名错误（见 D4 更新），修正后重新真实推送成功：markdown 正文 + docx 附件（真三步分片上传）均送达真实测试群，README 状态列正确回填"✅ 已推送"
- [x] 8.4 真实群跑通场景②一次（验证落 `7-外部文档/<部门>/` + 队列追加行 + 中文文件名完整）——**2026-07-13 全部完成**：文本消息路径全验证通过（含未命中→待分拣、命中→财务部两条路径，中文文件名读回校验通过）。**inbound 文件路径**：群聊"@ 提及 + 附件"组合确认不生效（唐燕萍多次尝试群里发文件，机器人收到的始终只是纯文字 `msgtype="text"`），改用**私聊（1:1）发文件**成功——真实收到 `msgtype="file"` 帧、下载解密成功。但首次真实归档暴露第四个 bug：`_verify_no_corruption` 对所有归档文件（不分文本/二进制）一律做 UTF-8 解码校验，一份完好的真实 docx（本质 ZIP 二进制）被误判"写入损坏"（`UnicodeDecodeError`）——早期 mock 单测用的假字节巧合全落在 ASCII 范围内所以没测出来。修复：`_verify_no_corruption` 新增 `expected_size` 参数，file 类消息改比对字节数而非做文本解码；补充用真·非 UTF-8 二进制内容的回归测试。修复后重新私聊发送验证：`archived`+`queue_appended` 全部正常，无误判
- [ ] 8.5 真实群运行满一周，观察无误归档/无漏推送/audit 全程可查，产出验收小结供 Paul 签字批准转常驻（对应 proposal.md 晋档条件）——**待定**：是否在开发环境继续跑满周、还是等正式发布 .51 后再计满周，需 Paul 定

## 9. 收尾

- [ ] 9.1 `wecom-aibot-service/CLAUDE.md`（六段式：定位/决策/底座/红线/时间线/依赖）
- [ ] 9.2 `跨桌任务队列.md` #18 状态回写（本 session 完成部分：B/C/D 段代码+单测，非"完成"——6/7/8 段待部署脚本+真实凭据）
- [ ] 9.3 收工重跑文档台账（`0-学习与工具/工具-文档台账生成.py`）
- [ ] 9.4 全部新产出/修改文件 commit（本 worktree 分支，是否 push 待 Paul 确认）
- [ ] 9.5 `/opsx:archive wecom-aibot-channel -y`——**暂不执行**：tasks 未全部 [x]（6/7/8 段阻塞于 Paul 前置动作），按纪律"完工即归档"仅适用于全部 [x] 后，本次收工先不归档

## 10. 归档链路健壮性补强（2026-07-22，队列 #69/#70，design D18）

> 触发：唐燕萍 2026-07-21 那条归档——审计日志确认 `archived`+`queue_appended` 两个事件均记录成功，但对应行从未出现在队列文件的任何一次 git 提交里（总线只能人工补登，见队列 #69）。追查+补强分三部分。

- [x] 10.1 根因排查：`queue_appender.append_pending_task` 此前是纯 read-modify-write，无冲突检测/无锁——推断被另一个并发写手（人工/CC 会话对同一文件的整段改写，读到旧内容、写回时覆盖了 aibot 刚追加的行）静默覆盖；因丢失发生在任何 git 提交之前，无法从版本历史精确定位具体是哪次改写造成，但机制本身已复现验证（见 10.2 测试）
- [x] 10.2 `queue_appender.append_pending_task` 加乐观并发重试（写入前重新读一次核验磁盘未变，变了则放弃本轮计算、按最新磁盘内容重新定位插入点/重新编号；`max_retries` 耗尽后显式 `RuntimeError`，不静默吞、不无限重试）；`test_queue_appender.py` 新增 2 例（模拟并发写手插队后正确重算不覆盖 / 持续竞态耗尽重试后报错）
- [x] 10.3 新增 `queue_reconcile_sentinel.py`（归档↔队列对账哨兵，dry-run）：每次连接成功后扫描近 7 天 `archived` 审计事件，逐条核对归档文件名是否出现在当前队列文件全文里（子串匹配，不解析表格结构）；疑似漏行只私信 Paul 一条汇总报告（列文件清单），**不自动写队列**——自动补行留待观察一段时间误报率后再开启，登记为下一条任务；接入 `run_aibot_service.py::_run_forever`（与 `gap_alert` 同一触发点）；`test_queue_reconcile_sentinel.py` 12 例
- [x] 10.4 `department_mapping.yaml` 补入陈承（IT，userid=2023458）→ `IT`（此前只在白名单里、不在部门映射，落"待分拣"）；`intake.py::DEPARTMENT_TO_QUEUE_OWNER` 未加 "IT" 项，队列行领取方按现有 fail-closed 默认值落 Paul（不臆造"IT专线"角色）；`test_department_mapping.py`/`test_connection.py`（原"落待分拣"用例改写为"落 IT"）/`test_intake.py`（新增"匹配部门但不在专线映射表→默认 Paul"用例）同步更新
- [ ] 10.5 二期（待观察，不在本次范围）：dry-run 观察一段时间（建议 1-2 周）确认误报率可接受后，评估是否开启自动补行——登记跨桌任务队列待领行，本次不做
