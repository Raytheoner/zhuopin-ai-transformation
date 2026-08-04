## ADDED Requirements

### Requirement: 待审批队列审批授权分级
SC8 待审批队列 SHALL 对队列项标注所需审批级别（`required_level` ∈ {`vp`, `l2`}）：命中 重点客户 / 首次承诺 / 关联金额>50万（可得时）任一 → `vp`，否则 `l2`。`approve` MUST 校验确认人级别——`required_level=="vp"` 且 `confirmed_by` 不在 VP 白名单（`VP_APPROVERS`）→ 拒绝放行（返回 False、保持 pending、写 `approval_denied_insufficient_level` 审计）。白名单与重点客户清单走配置（改 config 不改逻辑）。本要求叠加于"对客外发总开关"结构性闸门之上，二者独立。

#### Scenario: 非 VP 确认人放行重点客户项被拒
- **WHEN** 一个 `required_level=vp` 的队列项被不在 `VP_APPROVERS` 的确认人 `approve`
- **THEN** 返回 False、项保持 pending、写 `approval_denied_insufficient_level` 审计、不外发

#### Scenario: VP 确认人放行（总开关开启时）
- **WHEN** 同一项被 `VP_APPROVERS` 中的确认人 `approve` 且对客外发总开关已开启
- **THEN** 正常外发并原子标记 `sent`（幂等）

#### Scenario: 普通项 L2 即可
- **WHEN** 一个 `required_level=l2` 的队列项被任意非空确认人 `approve`（总开关开启）
- **THEN** 正常外发（不要求 VP 白名单）
