## ADDED Requirements

### Requirement: WebSocket 长连接建立与订阅
连接器 SHALL 通过 `wss://openws.work.weixin.qq.com` 建立 WebSocket 连接，握手成功后 MUST 立即发送 `aibot_subscribe` 订阅请求（携带 BotID + Secret）完成身份校验；订阅成功/失败 MUST 各记录一条可区分的审计事件。**实现说明（B 段核实，见 design.md D4）**：长连接建立/心跳/订阅/断线重连均由官方 SDK `wecom-aibot-python-sdk` 内部实现，本连接器只做事件转发 + 审计留痕，不重复实现协议细节。

#### Scenario: 订阅成功
- **WHEN** WebSocket 握手完成且 `aibot_subscribe` 请求携带有效 BotID/Secret
- **THEN** 连接进入已认证状态，可开始收发消息，审计依次记录 `action="connection_established"`（TCP+TLS 握手完成）与 `action="authenticated"`（订阅认证成功）

#### Scenario: 订阅凭据无效
- **WHEN** `aibot_subscribe` 返回非成功错误码
- **THEN** 不触发 `authenticated` 事件，审计记录一条 `action="connection_error"`（`error` 字段含错误信息）；连接器不做特殊的"提前放弃"处理，沿用断线重连退避的统一预算耗尽机制（见下一需求）兜底異常凭据场景

### Requirement: 心跳保活与断线重连退避
连接器复用的官方 SDK 内置心跳（默认 30 秒一次，连续 2 次未收到 pong 判定连接失效）与指数退避重连（基础延迟可配、封顶硬编码 30 秒，SDK 侧不可配）。本连接器 MUST 将 `max_reconnect_attempts` 配置为有限值（非默认 10、非 -1 无限），重连预算耗尽后 SDK 触发 `error` 事件、放弃重连，交由部署层（Windows 计划任务重启退避）兜底恢复。

#### Scenario: 断线后按退避序列重连并记审计
- **WHEN** 连接因网络异常等原因断开
- **THEN** 审计依次记录 `action="disconnected"`（含断线原因字符串）与每次 `action="reconnecting"`（含尝试次数）

#### Scenario: 重连预算耗尽后交还部署层
- **WHEN** 重连尝试次数达到配置的 `max_reconnect_attempts` 上限
- **THEN** SDK 触发 `error` 事件，审计记录 `action="connection_error"`；连接器不再自行重连，进程后续行为（是否退出/由计划任务重启）由部署层策略决定，不在本连接器职责范围内

### Requirement: 单连接冲突的处理边界（**已知限制，非精确识别**）
官方 SDK 的 `disconnected` 事件只提供通用 `reason: str`（WebSocket 关闭帧原因字符串），MUST NOT 假设能精确区分"被同 BotID 新连接踢下线"与其他断线原因。本连接器不实现"识别到被踢即停止重连"的精确策略；防止双实例互踢的责任在部署层（同一时刻只允许一个服务进程实例，见 `wecom-aibot-service` 部署文档），本需求只要求断线事件（无论何种原因）均被审计留痕，不丢失可追溯性。

#### Scenario: 任意原因断线均留痕
- **WHEN** 连接器收到 `disconnected` 事件（原因未知或已知）
- **THEN** 审计记录 `action="disconnected"` 且 `decision.reason` 字段保留原始断线原因字符串，供事后诊断是否为双实例冲突

### Requirement: 消息发送
连接器 SHALL 提供 `send_markdown(chatid, content)` 封装 `aibot_send_msg` 接口，用于向指定会话推送 markdown 消息；发送失败 MUST 让异常向上传播（不静默吞错），调用方（如 `wecom-followup-delivery`）负责审计与错误处理。

#### Scenario: 发送成功
- **WHEN** 调用 `send_markdown` 且底层 `send_message` 正常返回
- **THEN** 返回值原样透传给调用方，不额外包装

#### Scenario: 发送失败
- **WHEN** 底层 `send_message` 抛出异常（如网络错误、企微返回错误码）
- **THEN** 异常原样向上传播，不在连接器层吞掉或转成静默失败

### Requirement: 临时素材上传（三步分片协议）
连接器 SHALL 实现 `upload_media(file_bytes, filename)`，按官方文档三步协议（`aibot_upload_media_init`/`_chunk`/`_finish`，单分片 ≤512KB、最多 100 分片）上传素材并返回 `media_id`；官方 SDK 未封装此协议，连接器复用 SDK 内部"发帧+等 ACK"通用原语（`send_raw_frame`）自行实现。

#### Scenario: 单/多分片上传成功
- **WHEN** 调用 `upload_media` 传入任意大小（≤100×512KB）的文件字节
- **THEN** 按 512KB 切片、依次发送 init/chunk×N/finish 三类帧，返回 finish 响应中的 `media_id`

#### Scenario: 文件超过分片上限
- **WHEN** 文件字节数对应分片数超过 100
- **THEN** 连接器在发送任何帧之前直接抛出 `ValueError`，不发起无意义的部分上传

#### Scenario: 初始化/完成响应缺字段
- **WHEN** `aibot_upload_media_init` 响应缺 `upload_id` 或 `aibot_upload_media_finish` 响应缺 `media_id`
- **THEN** 连接器抛出 `RuntimeError` 并携带原始响应内容，不返回伪造的 `media_id`

### Requirement: 临时素材下载解密
连接器 SHALL 提供 `download_file(url, aes_key)` 封装官方 SDK 的下载+AES-256-CBC 解密能力，供场景②归档 inbound 文件消息使用。

#### Scenario: 下载并解密成功
- **WHEN** 调用 `download_file` 传入 inbound 消息体中的 `file.url`/`file.aeskey`
- **THEN** 返回 (解密后的文件字节, 文件名) 二元组，原样透传底层 SDK 结果

### Requirement: 凭据经 SecretsProvider 注入
连接器的 BotID/Secret MUST 经平台 `zhuopin_platform.shared_tools.secrets.SecretsProvider` 注入（在 `wecom-aibot-service` 的 `build_connector` 层完成），不得硬编码、不得直接读取非受控环境变量。

#### Scenario: 凭据缺失
- **WHEN** `SecretsProvider.get()` 对 BotID 或 Secret 键抛出 `KeyError`
- **THEN** 服务启动失败并给出明确错误信息，不得以空值/默认值静默启动

### Requirement: 收发全量审计留痕
连接器的所有连接生命周期事件（建立/认证成功/断开/重连中/错误）与收发动作（发送消息/素材上传/文件下载）MUST 经平台 `zhuopin_platform.audit.AuditLogger` 记录为只追加审计事件。

#### Scenario: 审计记录可查询
- **WHEN** 连接器发生任一生命周期事件或收发动作
- **THEN** 对应事件可通过 `AuditLogger.query_by(scenario="wecom-aibot", ...)` 查得
