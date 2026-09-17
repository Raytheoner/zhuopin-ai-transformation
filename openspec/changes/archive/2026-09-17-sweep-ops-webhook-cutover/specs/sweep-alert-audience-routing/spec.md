## Purpose

固化落库 sweep 机制类告警的**受众归属**：这些告警的主题一律是「某个自动化机制自己出问题了」，故 SHALL 发往运维逃生通道（Shao Peishen ＋ IT 陈承二人群），MUST NOT 发往任何业务部门群。判据来源＝`3-治理与合规/通知通道架构决策件-webhook退役与aibot单一出口-2026-08-06.md` §4.2 与队列 §一 `#282` 拍板⑵。

## ADDED Requirements

### Requirement: sweep 机制告警的去向键为运维逃生通道且不得回退业务群

`工具-落库sweep.py` 全部机制类告警（分叉告警／分叉解除通知／孤儿脏文件告警及其解除通知／部署留痕提示／常驻服务部署提示／定时任务镜像差异告警／凭据拦截告警／场景 spec 缺口告警／在途包滞留告警／未预期异常告警等）的 webhook 去向 SHALL 取自运维逃生通道的环境变量键 `WECOM_WEBHOOK_URL_OPS`。

该取值 MUST NOT 在 `WECOM_WEBHOOK_URL_OPS` 缺失或为空时回退到裸 `WECOM_WEBHOOK_URL`——裸键指向业务部门群，回退命中即为发错群，而"发错群"正是本 requirement 要消灭的事。

去向键 SHALL 由**单一常量**承载；模块内任何位置（含日志文案与 docstring）引用该键名时 MUST 从该常量派生，MUST NOT 出现该键名的字面量副本。

#### Scenario: 配置了运维键时告警发往运维通道

- **WHEN** 环境/`.env` 中 `WECOM_WEBHOOK_URL_OPS` 有非空值，sweep 触发任一机制类告警
- **THEN** 该告警经该值对应的 webhook 发出

#### Scenario: 只有裸键时视同未配置，绝不回退

- **WHEN** 环境/`.env` 中只有裸 `WECOM_WEBHOOK_URL` 有值、`WECOM_WEBHOOK_URL_OPS` 缺失
- **THEN** 取值结果为"未配置"，该轮告警被跳过并留痕，**不得**使用裸键的值发送

#### Scenario: 两者并存时只取运维键

- **WHEN** 环境/`.env` 中 `WECOM_WEBHOOK_URL` 与 `WECOM_WEBHOOK_URL_OPS` 同时有值（本机开发环境即如此）
- **THEN** 只取 `WECOM_WEBHOOK_URL_OPS`，业务群那条永不被选中

#### Scenario: 键名前缀匹配不得跨键误命中

- **WHEN** `.env` 中同时存在 `WECOM_WEBHOOK_URL=` 与 `WECOM_WEBHOOK_URL_OPS=` 两行
- **THEN** 按 `<键名>=` 精确前缀匹配，取到的是所配键自己那一行，不因两键互为前缀而误读另一行

#### Scenario: 日志文案与实际读取的键名一致

- **WHEN** 去向键未配置，sweep 就此写出跳过告警的留痕日志
- **THEN** 该日志中出现的键名与代码实际读取的键名**同源同值**，不存在二者不一致的可能

### Requirement: 告警去向缺失不得影响 sweep 自身退出码

机制类告警取不到去向（键缺失/为空）或推送本身失败（网络异常、webhook 拒绝、企微返回非零 errcode 等）时，sweep SHALL 仅降级为"跳过该条告警并记入运行日志"，MUST NOT 因此改变 `main()` 本应返回的退出码，MUST NOT 中止本轮其余流程。

告警是对 sweep 运行结果的**播报**，不是 sweep 的**工作内容**；播报失败不得掩盖 sweep 本身已完成（或已按其他原因失败）的事实。

#### Scenario: 去向键缺失时 sweep 仍返回其本应返回的退出码

- **WHEN** `WECOM_WEBHOOK_URL_OPS` 未配置，且本轮 sweep 触发了某类机制告警
- **THEN** 该告警被跳过并留痕，sweep 仍以其本应返回的退出码正常结束本轮

#### Scenario: 推送失败时 sweep 仍返回其本应返回的退出码

- **WHEN** 去向键已配置但推送过程抛出异常（网络失败或企微返回非零 errcode）
- **THEN** 异常被降级记入运行日志，sweep 仍以其本应返回的退出码正常结束本轮
