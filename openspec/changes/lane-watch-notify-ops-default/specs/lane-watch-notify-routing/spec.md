## Purpose

固化泳道看护决策提示（`pause`／`transfer-out`／`check-heartbeat`）的**默认推送受众归属**：这些提示的主题一律是「一个内部机制在等待 Shao Peishen 决策」，故 SHALL 默认发往运维逃生通道（Shao Peishen ＋ IT 陈承二人群），MUST NOT 默认发往任何业务部门群，且目标缺失或发送失败时 MUST NOT 回落业务部门群。判据来源＝`3-治理与合规/通知通道架构决策件-webhook退役与aibot单一出口-2026-08-06.md` §4.2 与队列 `#492`（`#284` 计数⑨两次真实事故的处置）。

## ADDED Requirements

### Requirement: 泳道决策提示的默认去向为运维逃生通道且不得回退业务群

`工具-泳道看护状态机.py` 的 `pause`／`transfer-out`／`check-heartbeat` 三个命令，在未显式跳过通知（如 `--no-notify`）时，其推送去向 SHALL 默认取自运维逃生通道的环境变量键 `WECOM_WEBHOOK_URL_OPS`，MUST NOT 依赖调用方额外传参才能避免发往业务部门群。

该取值 MUST NOT 在 `WECOM_WEBHOOK_URL_OPS` 缺失或为空时回退到裸 `WECOM_WEBHOOK_URL`——裸键指向业务部门群，回退命中即为发错群，而"发错群"正是本 requirement 要消灭的事（`#284` 计数⑨记录的两次真实事故）。

去向键 SHALL 由**单一常量**承载；模块内任何位置引用该键名时 MUST 从该常量派生，MUST NOT 出现该键名的字面量副本。

#### Scenario: 未传任何通知相关参数时默认发往运维通道

- **WHEN** 调用方以最简参数调用 `pause`（不传 `--no-notify`），且 `.env` 中 `WECOM_WEBHOOK_URL_OPS` 有非空值
- **THEN** 该决策提示经该值对应的 webhook 发出，调用方无需额外传参即达成"不发业务群"

#### Scenario: 只有业务群裸键时视同未配置，绝不回退

- **WHEN** `.env` 中只有裸 `WECOM_WEBHOOK_URL` 有值、`WECOM_WEBHOOK_URL_OPS` 缺失
- **THEN** 取值结果为"未配置"，本次通知被跳过并标记，**不得**使用裸键的值发送

#### Scenario: 两者并存时只取运维键

- **WHEN** `.env` 中 `WECOM_WEBHOOK_URL` 与 `WECOM_WEBHOOK_URL_OPS` 同时有值
- **THEN** 只取 `WECOM_WEBHOOK_URL_OPS`，业务群那条永不被选中

#### Scenario: 键名前缀匹配不得跨键误命中

- **WHEN** `.env` 中同时存在 `WECOM_WEBHOOK_URL=` 与 `WECOM_WEBHOOK_URL_OPS=` 两行
- **THEN** 按 `<键名>=` 精确前缀匹配，取到的是所配键自己那一行，不因两键互为前缀而误读另一行

### Requirement: 通知目标缺失或发送失败 SHALL fail-closed 并落状态标记，不得回落默认群、不得中断调用方

`WECOM_WEBHOOK_URL_OPS` 缺失、或发送过程本身抛出异常（网络失败、企微返回非零 errcode、脚本加载失败等），泳道看护状态机 SHALL 跳过本次发送并在触发失败的那个泳道的状态记录里追加一条失败标记，MUST NOT 因此回落到默认业务群，MUST NOT 使调用方（`pause_lane`／`transfer_out_lane`／`check_heartbeat`）的状态落盘或返回值受到影响。

该标记 SHALL 可被 `summary`（收工汇总）现取汇总报出，供 Shao Peishen 事后核实 OPS 配置或网络状况；`check-heartbeat` 自身触发的通知失败 SHALL 在其自身运行时的留痕输出中同样体现。

#### Scenario: OPS 未配置时通知失败不影响状态落盘

- **WHEN** `.env` 中未配置 `WECOM_WEBHOOK_URL_OPS`，某泳道命中 🟡/🔴 决策点触发 `pause`
- **THEN** 该泳道的暂停状态照常写入状态文件，通知本身被跳过，该泳道的状态记录里新增一条失败标记，函数不抛出异常

#### Scenario: 发送过程异常时同样标记且不影响返回值

- **WHEN** `WECOM_WEBHOOK_URL_OPS` 已配置，但发送过程抛出异常（网络异常/企微非零 errcode）
- **THEN** 该异常被捕获，状态记录追加一条失败标记，调用方函数正常返回，不将异常向上传播

#### Scenario: 收工汇总现取报出通知失败次数

- **WHEN** 执行 `summary` 子命令
- **THEN** 输出中包含本批（或全部，视 `--batch` 过滤）通知失败的次数，不需人工翻查各泳道历史记录逐条清点
