# aibot-outbox-relay Tasks

> 🔴 **暂不归档**（供 `工具-变更包自动归档.py` 读取）：§6 的真实送达与人眼反查
> 是**人在场才能做**的动作，本次为无人在场的无头批处理会话，一律留步。
> 判它已通的唯一判据 ＝ **姚祖怡在群里真的看到了那条周报**，不是 tasks 打满勾。

## 1. 记录契约（场景无关）

- [x] 1.1 定义通道常量 `aibot_group_chatid` / `aibot_direct`，与 `sc2/outbox.py` 写侧逐字对齐
- [x] 1.2 `msgtype` 只认 `markdown`；出现别的值 ⇒ 跳过并告警，**不猜**
- [x] 1.3 八种「投不出去」各有**自己的**原因码，不合并（单测逐条钉死）
- [x] 1.4 🔴 O-10：契约**不含**按 `scenario` 分流的字段消费；`scenario` 只进留痕

## 2. 硬约束①：不得再抄一份 chatid

- [x] 2.1 `resolve_target()` 的群 chatid **只**从传入的映射取，模块内零 chatid 字面量
- [x] 2.2 部门名**精确匹配**，不做近似（`IT` ≠ `IT部`、`采购部` ≠ `PMC部`）
- [x] 2.3 **源码层断言**：中继源码不得出现真实 chatid 字面量，且必须 import 权威 yaml 的加载函数
- [x] 2.4 **源码层断言**：不得出现 `== "SC2"` / `== "FI2"` 一类按场景取值的分支（钉住 O-10）

## 3. 硬约束②：投递成功才置 delivered

- [x] 3.1 「成功」判据直接复用 `delivery._assert_ack_accepted`，**不另写第二套**（决策点 8）
- [x] 3.2 单测正面：成功 ⇒ 置 `delivered:true` ＋ `delivered_at_utc`/`delivered_to`/`delivered_ack`
- [x] 3.3 单测反面：传输失败 ⇒ 留在 outbox，下一轮重试成功
- [x] 3.4 单测反面：**企微回非零 `errcode`** ⇒ 绝不置 `delivered`（走真实 `AibotConnector` ＋ 假客户端）
- [x] 3.5 已投递的记录第二轮不再扫到（不重发）
- [x] 3.6 结构性投不出去的记录**留在 outbox**、不丢弃；同一 `(文件,行,原因)` 只告警一次
- [x] 3.7 损坏行原样保留、不投递、告警，且**不影响同文件其余行**

## 4. 并发与回写安全（决策点 5）

- [x] 4.1 乐观并发校验：记住物理行号 ＋ 原文，回写时逐字比对才替换
- [x] 4.2 🔴 单测：**读与写之间写侧追加的新行不得丢失**
- [x] 4.3 🔴 单测：校验不过 ⇒ `mark_failed` ＋ 告警，**绝不强行覆盖、绝不假装标成功**
- [x] 4.4 临时文件 ＋ `os.replace` 原子回写；单测断言不留 `.relaytmp` 残留
- [x] 4.5 发一条标一条（不攒批），把「已发未标」窗口压到最小

## 5. 可观测性（决策点 6/决策点 4）

- [x] 5.1 🔴 outbox 读不到 ⇒ `OutboxReadError`，**MUST NOT** 读成「没有待发」
- [x] 5.2 读不到**每轮都告警**（不去重）；一份读不到不阻塞其余几份
- [x] 5.3 🔴 「中继关着」与「中继在跑但没消息」各记一条可区分的审计事件、各打印一行
- [x] 5.4 只读体检 CLI `check_outbox_relay.py`（无发送路径），退出码 0/1/2 三档
- [x] 5.5 **对真实 `department_group_chatid_mapping.yaml` 实跑过一次体检**：采购部解析出真实 chatid、`PMC部` 报「不在映射表」、缺文件报「读不到 ≠ 没有待发」，退出码 1 —— 三档行为逐条对上

## 6. 🔴 真实送达与人眼反查（留步，本次未做）

- [ ] 6.1 **L1**：笔记本在 LAN 内时实跑「`.51` 写、笔记本读」，坐实文件通路（design 探测项 P6）
- [ ] 6.2 **L1**：据此配置 `WECOM_AIBOT_OUTBOX_PATHS`，重启常驻服务，确认打印「已启动」而非「中继关闭」
- [ ] 6.3 **L2**：首条真实送达 —— 发出后**对着采购部群看一眼**（chatid 采集只证明「机器人收到过来自该 chatid 的消息」，**不证明它就是采购部群**）
- [ ] 6.4 **L2**：同批反查 1:1 私信是否真的到了姚祖怡
- [ ] 6.5 **L3**：确认 outbox 积压回落到 0，据此销 `#394`

## 7. 回归

- [x] 7.1 服务全量：**606 passed / 1 skipped**（基线 569 collected，新增 38，零漂移）
- [x] 7.2 平台全量：**380 passed / 1 skipped**（零漂移）
- [x] 7.3 `connection.py`／`delivery.py`／`group_notify.py`／映射表／`sc2/` **一行未改**
- [x] 7.4 openspec `validate --all --strict` 绿：**117 passed / 0 failed**

## 8. 收口

- [x] 8.1 场景 `CLAUDE.md` 状态时间线补一行
- [x] 8.2 队列 `#394` 回写（**不销号**，销号判据是 6.5）＋ 登记 §二 批次
- [ ] 8.3 归档（待 §6 全勾）

## 9. 🔴 队列 `#556` 修法（决策点 9，2026-09-12 apply，`OP-0912-C2`）

> `OP-0912-C2`：design 决策点 9 已由 Shao Peishen 2026-09-12 答 `1a` 签认
> （`OP-0910-H` 代回写），按原案 apply。本节 9.1-9.7／9.9／9.10 已完成；
> **9.8 部分完成，如实登记**——本次变更包触碰区仅 `5-平台底座/
> wecom-aibot-service/`，`0-学习与工具/工具-落库sweep.py` 不在其内，故只
> 交付了 sweep 可消费的纯函数（`list_persistently_unreadable`），**未把它
> 接进 `工具-落库sweep.py` 的值周巡检**——那是另一件事，留给专门的后续
> 任务（已在队列 `#556` 回写里点名，不假装本次已接好）。
>
> `OP-0913-A`（2026-09-13）：**9.8 残余已补齐**——`工具-落库sweep.py` 新增
> **第 18 类**常驻状态告警 `_check_outbox_relay_unreadable_visibility`：读
> `reports/outbox_relay_unreadable_state.json`、子进程调正本纯函数
> `list_persistently_unreadable`（sweep 侧不另抄判据）、`first_failed_at`
> 距今 > 24 小时的路径点名进值周清单（`reports/sweep-commit.log`）＋ 运维
> 逃生通道 24 小时节流告警；`--dry-run` 只回显不写不推。单测
> `0-学习与工具/test_工具-落库sweep-中继持续不可读.py` 14 条＋3 组变异检验。

- [x] 9.1 新增 `reports/outbox_relay_unreadable_state.json` 读写（路径级 `first_failed_at`／`last_alert_at`），gitignore 覆盖，同 `decision_reminder_ack.json` 先例——见 `aibot_service/repo_paths.py::resolve_outbox_relay_unreadable_state_path`、`aibot_service/outbox_relay.py::load_unreadable_state`/`save_unreadable_state`
- [x] 9.2 `relay_once()` 读失败分支改判：转入 ⇒ 立即告警；持续态未到复报周期 ⇒ 只记审计不告警；到复报周期 ⇒ 告警并回填 `last_alert_at`；恢复 ⇒ 告警并清除状态——见 `outbox_relay.py::_handle_unreadable_scan`/`_handle_recovered_scan`
- [x] 9.3 新增环境变量 `WECOM_AIBOT_OUTBOX_UNREADABLE_REALERT_SECONDS`（默认 `21600` ＝ 6 小时），`run_aibot_service.py` 已接线
- [x] 9.4 新增可区分审计事件：`outbox_relay_scan_unreadable_started` / `_persisting` / `_recovered`（`outbox_relay_scan_failed` 原样保留、每轮照记不变）
- [x] 9.5 单测：首次转入必告警／节流期内不告警但审计照记／超过周期复报／恢复后告警并清状态／状态跨进程重启不重置（用临时文件模拟重启，MUST NOT 复现「首次转入」告警）——`tests/test_outbox_relay.py` 决策点 9 段，18 条新用例
- [x] 9.6 `scripts/check_outbox_relay.py`：读不到时追加打印状态文件里的 `first_failed_at` 与距今时长（不改动既有退出码语义），已实跑冒烟（`--path` 指一个不存在的路径，退出码仍为 1）
- [x] 9.7 🔴 源码层断言：中继不得出现任何 `socket`/`Test-NetConnection`/`subprocess.run` 一类网络自检代码——`test_relay_source_contains_no_network_self_check`
- [x] 9.8 `outbox_relay.list_persistently_unreadable()` 纯函数已交付＋单测覆盖（`OP-0912-C2`）；接入 `工具-落库sweep.py` 值周清单＝第 18 类 `_check_outbox_relay_unreadable_visibility`（`OP-0913-A`，2026-09-13，子进程调纯函数、不另抄判据；单测 14 条＋变异 3 组各转红复绿）
- [x] 9.9 队列 `#556` 回写＋登记 §二 批次
- [x] 9.10 apply 完成后回归：服务 **847 passed / 1 skipped / 2 failed**（2 处失败与本次改动无关——`test_ps1_orphan_cr_guard.py` 两条，纯 master `2882bfa` 同命令复跑逐条复现，零回归）／平台 **619 passed / 1 skipped**（零漂移）／openspec `validate --all --strict` **191 passed 0 failed**
