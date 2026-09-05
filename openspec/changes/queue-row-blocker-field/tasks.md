> **本变更包止步于设计阶段**（队列 `#448` opener `OP-0905-F` 授权范围：起草 openspec 变更包并给出 design.md 推荐方案，不代 Shao Peishen 拍板，不进入实现）。以下任务清单是 design 审通过后的完整落地计划，当前 session 只完成「0. design 审前置」之前的起草工作，0 之后各项均未开始，如实登记为待办、不预先勾选。

## 0. design 审前置

- [ ] 0.1 Shao Peishen 审核 design.md 决策点 5（`[B:split]` 是否计入可动 WIP）——本设计推荐"计入 ＋ 限期由值周巡检持续点名"。
- [ ] 0.2 Shao Peishen 审核 design.md 决策点 6（存量补标一次性 vs 渐进）——本设计推荐"值周巡检一次性补标"。
- [ ] 0.3 Shao Peishen 审核决策点 1/2/3/4/7/8 其余技术细节——均已给出默认项，若不答按默认项执行。

## 1. 单测先行（决策点 1/2/3：编辑锁权威实现）

- [ ] 1.1 阻塞源字段解析用例：5 值正确解析（`none`/`person`/`env`/`external`/`split`）、非法值不解析、字段缺失非静默降级、域字段缺省时阻塞源字段仍可独立解析。
- [ ] 1.2 `_suggest_status_reclassification` 改判据来源后的用例：`none` 不产出候选；`person`/`env`/`external` 产出"确认 blocked"候选；`split` 产出"建议拆行"候选且不与"确认 blocked"候选混同；字段缺失时回退旧判据并留痕。
- [ ] 1.3 `_count_mechanism_wip` 新排除条件用例：`person`/`env`/`external` 即便状态为 open/partial/hold 也排除；`none`/`split` 计入；字段缺失时非静默降级、不静默计入或排除。
- [ ] 1.4 `#142` 9 行黄金集回归用例（补标后对照，逐行断言建议结论与人工判定一致）。
- [ ] 1.5 既有回归套件零漂移（编辑锁现有全部用例）。

## 2. 实现：编辑锁权威实现（决策点 1/2/3/4）

- [ ] 2.1 `STATUS_FIELD_RE` 扩展为三段式；新增 `_parse_status_domain_block_fields`（4 元组返回），旧 `_parse_status_domain_fields` 保留为兼容包装（仅消费 status/domain 的调用点不强制迁移）。
- [ ] 2.2 `_suggest_status_reclassification` 切换判据来源；`STALE_STATUS_PHRASES` 标记为待退休（暂不删除，待 2.4 补标 + 消费者切换全部完成后再删，避免过渡期回退分支失去依据）。
- [ ] 2.3 `_count_mechanism_wip` 新增排除条件。
- [ ] 2.4 `_render_reclassification_candidates` 新增"建议拆行"文案分支，与既有"建议改判"候选视觉区分。

## 3. 消费者切换核实与实现（决策点 8）

- [ ] 3.1 `工具-落库sweep.py`：核实其独立实现的消费点（L2823/L3386）不消费 domain/rest，确认新增可选分组不影响其现有正则匹配，无需改动（若核实结论与本设计预判不符，如实更正）。
- [ ] 3.2 `工具-队列查询.py`：展示层新增阻塞源取值输出（`--field all`），供值周巡检读取。
- [ ] 3.3 `decision_reminder.py`／`open_pool_reminder.py`：核实是否消费 `rest`／`domain_value` 做二次判断；按核实结论决定是否需要改动（本设计不预判）。
- [ ] 3.4 `工具-队列结构lint.py`（经 import 复用权威实现）：新增阻塞源字段缺失门禁分支，按决策点 7 前置条件延迟到 4/5 完成后再合入本任务的代码。
- [ ] 3.5 `工具-跟进闸查询.py`：核实其经 import 复用的调用点不受影响。

## 4. 存量补标（决策点 6）

- [ ] 4.1 值周巡检窗口内一次性补标约 45 行机制类 ＋ 23 行业务类在办行，五态归类逐行给出，附一句判断依据（同 `#308` 106 行回填时的"新旧判据分歧清单"惯例，本次记录"补标依据"）。
- [ ] 4.2 补标结果与 `#142` 9 行黄金集逐条核对，产出一致/不一致清单；不一致行须逐条给出人工结论（判据缺陷 vs 黄金集需更新），不得整体标记"完成"了事。
- [ ] 4.3 补标产出的分类分歧（若有）逐条登记，比照 `queue-status-machine-field` 17 处分歧清单的既有处理方式。

## 5. CI 门禁合入（决策点 7）

- [ ] 5.1 确认 2/3/4 全部完成后，`工具-队列结构lint.py` 阻塞源字段缺失门禁与"存量补标完成"状态同批 commit 合入，不拆分为独立后续任务。
- [ ] 5.2 门禁对当前队列文件全量跑绿（含机制/业务两份物理文件）。
- [ ] 5.3 `STALE_STATUS_PHRASES` 常量与其匹配循环整体删除（决策点 2 的退休承诺兑现，proposal.md "本次退休哪一个既有守卫"）。

## 6. 文档

- [ ] 6.1 队列 `#448` 行回填：本变更 design 审结论、补标完成情况、门禁上线情况。
- [ ] 6.2 协议〇.9 措施 C 分母口径说明补充：排除条件新增阻塞源 person/env/external 三态。
- [ ] 6.3 待 `#308`（`queue-status-machine-field`）归档后，补一次 `MODIFIED` 变更包正式登记本变更对 `queue-row-status-field`／`editlock-mechanism-wip-guard` 两个能力的实际修改（proposal.md「Modified Capabilities」信息性说明的后续动作，登记为新队列行，不在本变更范围内完成）。

## 7. 验证

- [ ] 7.1 全量回归：编辑锁、sweep、队列查询、队列结构lint、wecom-aibot-service 均零漂移，均未新增 warning/error。
- [ ] 7.2 `#142` 9 行黄金集回归 9/9 一致，或对不上的行有明确人工结论（判据缺陷已修复 / 黄金集本身需更新）。
- [ ] 7.3 `OP-0901-D` §2 实验数据集（v1/v2 成败案例）作为反例集回归，不得复现"改一个坏一个"模式。
- [ ] 7.4 真实值周巡检至少一轮使用改判后的候选清单完成分诊，未出现"藏活"或"漏拆"真实误报。

## 8. 收工

- [ ] 8.1 `openspec change validate queue-row-blocker-field --strict` 跑绿（本 session 交付前必须完成的最低门槛）。
- [ ] 8.2 `pause --action-key openspec_design_review --waiting-for "design 草案已出，等你审"`（本 session 收工动作，不进入实现）。
- [ ] 8.3 design 审通过、tasks 全部 [x] 后当场 `/opsx:archive queue-row-blocker-field -y`（沿用场景建造与合规规则"完工即归档"纪律，不得跨 1 个 session 悬置）。
