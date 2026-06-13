## ADDED Requirements

### Requirement: Notifier 对客外发总开关第二道结构性闸门
平台 `Notifier` SHALL 支持注入式对客外发总开关 `outbound_enabled`（`bool` 或 `Callable[[], bool]`，默认放行以不影响内部/通用通知）。当 `outbound_enabled` 求值为 `False` 时，`send()` MUST 拒绝实际外发——**即便带非空 `confirmed_by`（人工已确认）也不外发**——并记审计 `sent=False`。拦截入队仅对**首道拦截**（无 `confirmed_by`）生效（草稿否则无处留存），reason 区分 `customer_outbound_disabled` 与 `awaiting_L2_confirmation`；带 `confirmed_by` 的复发（队列 `approve` 二次放行）被拦时 MUST NOT 重复入队（草稿已在队列中，且避免持锁复发经 `enqueue` 重入队列锁死锁）。此为独立于 L2 人工门禁的第二道结构性闸门。

#### Scenario: 总开关关闭时即便已确认也不外发且不重复入队
- **WHEN** `outbound_enabled` 求值为 `False`，对一条带非空 `confirmed_by` 的消息调用 `send()`
- **THEN** 返回 `False`、底层发送函数未被调用、**不重复入队**、审计记 `sent=False`

#### Scenario: 首道拦截 + 总开关关闭 → 草稿入队留痕
- **WHEN** `outbound_enabled` 求值为 `False`，对一条无 `confirmed_by` 的消息调用 `send()`
- **THEN** 返回 `False`、草稿入待审批队列（reason=`customer_outbound_disabled`）

#### Scenario: 默认放行不影响内部通知
- **WHEN** 未注入 `outbound_enabled`（默认）构造 `Notifier`，发送一条低风险已确认消息
- **THEN** 正常外发（默认 `outbound_enabled=True`）
