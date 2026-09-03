## Purpose

在报销单**提交时**按（部门 × 科目 × 期间）查预算余额并判定是否超预算，超限即拦截并通知上级。
它存在的理由是把"超预算"这件事从月末结账提前到费用发生前——现流程要到月末才发现，那时钱已经花掉了。

## ADDED Requirements

### Requirement: 提交时预算余额校验与超预算拦截

系统 SHALL 在报销单**提交时**按（部门 × 科目 × 期间）查预算余额并判定是否超预算，拦截发生在提交环节而非月末结账。判定阈值 `L2_BUDGET_BLOCK_PCT` 须财务侧签认，未签认时 MUST fail-loud。

> 这是本场景的价值点所在：现流程要到月末结账才发现超预算，那时费用已经发生。

#### Scenario: 提交即拦截
- **WHEN** 一张报销单提交，其占用额使对应预算余额突破签认阈值
- **THEN** 该单被拦截、不进入后续审批流，并通知申请人上级

#### Scenario: 阈值未签认
- **WHEN** `L2_BUDGET_BLOCK_PCT` 为空
- **THEN** 引擎抛出显式异常，MUST NOT 以"超 0 即拦"或任何其他默认口径代替签认阈值

#### Scenario: 预算行缺失
- **WHEN** 对应的（部门 × 科目 × 期间）在预算快照中不存在
- **THEN** 标记需人工复核并说明缺哪一行，MUST NOT 视作"余额充足"放行

### Requirement: 通知复用平台通道

系统 SHALL 复用 `zhuopin_platform.shared_tools.notifiers` 发送拦截通知，MUST NOT 自建通知通道。

#### Scenario: 拦截通知走平台通道
- **WHEN** 发生超预算拦截
- **THEN** 经平台 notifier 通知上级，通知内容含单号、科目、超出额与所用 `RULE_VERSION`
