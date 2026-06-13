## MODIFIED Requirements

### Requirement: 首道对客承诺一律入待审批队列
SC8 `submit_commitment`（对客交付承诺首道提交）SHALL **一律**把承诺草稿入待审批队列、绝不自动外发，与门禁风险等级及全局对客外发总开关是否开启**无关**。删除"高置信+非首次+不晚于目标日 → 低风险自动放行外发"旁路。真正外发只能由 L2 责任人经 `FilePendingQueue.approve(item_id, confirmed_by)` 二次放行触发。门禁 `evaluate` 给出的真实风险（`requires_confirmation`/`severity`/`reasons`）MUST 如实写入草稿与审计，不得因 policy 恒入队而掩盖真实低风险判定。

#### Scenario: 低风险预测首道也入队不外发
- **WHEN** 对一条高置信、非首次、不晚于目标日的预测调用 `submit_commitment`（无 `confirmed_by`）
- **THEN** 结果 `sent is False`、草稿入待审批队列、底层发送函数未被调用；`CommitmentResult.requires_confirmation` 仍如实反映门禁真实风险（低风险为 `False`）

#### Scenario: 经人工 approve 后才外发
- **WHEN** 入队项被 L2 责任人以非空 `confirmed_by` 调 `approve`，且对客外发总开关已开启
- **THEN** 草稿经 `Notifier` 外发，队列项原子标记 `sent`（幂等）
