## ADDED Requirements

> 🔴 本 spec 对应 design **决策点 3**（须签认，无默认）。**签认前不得 apply。**
> 决策点 2（回填时是否顺手写闭环态）**未在本 spec 中预设任何一边**——见末节。
> 🟩 **2026-09-12 签认后落字**（Shao Peishen 回 `P3：…2a，3a…`，经 `OP-0912-E` 转达；apply 泳道 `OP-0912-AB`）：决策点 3 ＝ (a)、决策点 2 ＝ (a)＋三条护栏，末节已按签认改写为「SHALL」正文；「快照不影响两态语义拦截」场景按实测**如实更正**（见该场景注）。

### Requirement: 发送回填 MUST NOT 整格覆盖「发送状态」列
`delivery.py::push_followup` 推送成功后的回填 MUST 保留状态格内既有内容，
MUST NOT 用 `write_status()` 做整格替换。

保留形态 MUST 沿用 S4 桥一 `followup_readme_bridge.build_reply_arrived_status()`
**已在生产上运行**的范式：新状态前缀在最前（闭环判据一律按前缀比对），
既有内容以 `　━━━　` 分段接在其后。MUST NOT 新造第二种分段范式。

#### Scenario: 回填保留人写的暂缓理由
- **WHEN** 一行状态格为 `⏸ 暂缓（依据：…）`，其后被恢复为 `🆕 待发` 并成功推送
- **THEN** 回填后的状态格首段为 `✅ 已推送 <UTC>`，且原有理由文本仍可在格内读到

#### Scenario: 空状态格回填后与今天逐字相同
- **WHEN** 一行状态格恰为 `🆕 待发`（无附加内容）且成功推送
- **THEN** 回填后状态格为 `✅ 已推送 <UTC>`，与本变更前逐字相同（不多出空分隔符）

---

### Requirement: 回填 SHALL 把闭环形态标注快照进状态格
回填时，若该行「主要事项」列含合法的闭环形态标注，
回填结果 MUST 在状态格内写入一段**发出时快照**，明确标识其为快照
（如 `　━━━　闭环形态（发出时快照）━━━　…`）。

快照 MUST 是回填那一刻的值。此后「主要事项」列被如何修改，MUST NOT 改变已写入的快照。

无标注时 MUST NOT 写入任何快照段——回填结果与本变更前逐字相同。

#### Scenario: 快照写入
- **WHEN** 「主要事项」列含 `→ 闭环形态：\`✅ 无需回复\`（依据：…）`，该信成功推送
- **THEN** 状态格内含首段 `✅ 已推送 <UTC>` 与一段标识为「发出时快照」的闭环形态

#### Scenario: 快照冻结
- **WHEN** 快照已写入后，有人改动了「主要事项」列的标注
- **THEN** 状态格内的快照文本不变

---

### Requirement: 快照 MUST 兼容既有全部状态判据
写入快照后的状态格 MUST 仍能被下列既有判据正确处理，MUST NOT 出现回归：

- `followup_gate.classify_status` / `normalize_status` / `is_closed_status` /
  `is_reply_arrived_status` —— 均按**前缀匹配 + 归一化**判定，格内后缀 MUST NOT 影响结论。
- `followup_readme_bridge.build_reply_arrived_status` —— 第九态 MUST 把整个原状态
  （含快照）原样接在其后，快照 MUST 能一路活到第九态与闭环态。
- `工具-共享文档编辑锁.py` 的串行闸与两态语义两处校验 —— MUST NOT 因格内多出分段而误判。

🔴 本要求 MUST 配反例单测：把「写了快照的状态格」喂给上述每一条既有判据，
断言结论与「未写快照的同一状态」一致。

#### Scenario: 快照不影响第九态转态
- **WHEN** 一行状态格含 `✅ 已推送 <UTC>　━━━　闭环形态（发出时快照）━━━　✅ 无需回复（…）`，
  且该信的回件到达
- **THEN** 桥一正常打第九态，且快照文本在新状态格内仍可读到

#### Scenario: 快照不影响两态语义拦截（🟩 2026-09-13 签认放宽后成立）
- **WHEN** 一个**新增**行的状态格写有 `🆕 待发` 加任意快照段
- **THEN** 编辑锁仍判其为「新建即终态」违规（该拦截按首段判定，不因分段而失效）
  ——🟩 **Shao Peishen 2026-09-13 回「第 5 项选 a」＝签认放宽编辑锁两处等值比较**
  （两态语义 ＋ `_validate_followup_hold_consistency` ⑥），由「整格等值」改为「取首段后再等值」，
  首段切分口径只此一份＝`followup_gate.leading_status_segment`（隔离环境走 `_FollowupGateFallback`
  逐条镜像，`FollowupSerialGateIdentityFallbackTests` 双跑钉住）。用例：
  `test_4_4_新增行终态加快照段_两态语义按首段判_与不带快照结论一致`／
  `test_4_4_既有草稿行转终态加快照段_与不带快照同样放行`／
  `test_4_4_hold_row_readme_pending_with_snapshot_segment_blocks_release`／
  `test_4_4_两态语义首段判_带快照与不带快照结论一致_权威与回落双跑`（CC 泳道 `OP-0913-C`）。
  🔴 **只放宽这两处**：`gates.assert_finalized`（design D8 门禁②红线）／`readme_table.assert_draft_pending_review`／
  `dispatch.py` 三处／`dispatch_followup_letters.py` 仍为整格等值，不在签认范围内、一字未动。
  历史：2026-09-12 apply 时此场景曾如实更正为「实测不成立、本包不得改」并由
  `test_新增行终态加快照段_两态语义等值拦截不命中_如实钉住` 钉住，该用例已被上列用例取代。
  串行闸那一处校验（`_followup_status_is_closed` → 前缀）**与未写快照的同一状态结论一致**，已配用例。

---

### Requirement: 标注为 `✅ 无需回复` 时回填首段 SHALL 直接写闭环态（决策点 2 ＝ (a)，Shao Peishen 2026-09-12 签认）
> 原文「本 spec 不预设」段已由签认取代：Shao Peishen 2026-09-12 回 `2a`（IATF 显式签认红线，
> 未获明确答复前 MUST 留空——现已获明确字母，tasks 4.5 落字）。**(a) 与下列三条护栏同时生效，缺一即退回 (b)。**

「主要事项」列含**合法**闭环形态标注且取值为 `✅ 无需回复` 时，`delivery.py` 回填 SHALL 把状态格首段
写成闭环态 `✅ 无需回复 <UTC>`，串行闸当场开——与补件表通知型（队列 `#399` 决策点 5 (b)）
**同一语义、同一函数内分支**（`resolve_backfill`），MUST NOT 另写一份口径。

三条护栏（MUST 全部成立）：
1. **只认批准那一刻已存在的标注**：回填读的是门禁② `assert_finalized` 通过时那一次读取的行
   （状态仍为 `🆕 待发`），并把标注**快照**进状态格；此后闸判据只读状态格、不回读「主要事项」列
   ⇒ 发出后再补写标注对闸 MUST 零效果（由数据流保证，不新增门禁）。
2. **取值只认 `followup_gate.CLOSED_STATUS_PREFIXES` 枚举**：越界或缺依据 MUST 按「无标注」处理
   ——首段仍写 `✅ 已推送 <UTC>`、不写快照、闸仍锁（保守方向），且 MUST 报出来
   （审计 `followup_closure_form_rejected`）。枚举另三态（`📥`／`📨`／`❌`）在起草时不可能成立
   ⇒ 只快照、不开闸。
3. **保留 `✅ 已推送 <UTC>` 作为快照后段**，使「何时推送」这个事实不丢：
   `✅ 无需回复 <UTC>　━━━　闭环形态（发出时快照） ━━━　✅ 无需回复（依据：…）　━━━　✅ 已推送 <UTC>`
   （与补件表直接写 `✅ 无需回复` 不带时刻的差别：主表是串行闸的判据来源、补件表不是）。

#### Scenario: 合法 `✅ 无需回复` 标注 ⇒ 发出即闭环
- **WHEN** 「主要事项」列含 `→ 闭环形态：\`✅ 无需回复\`（依据：…）`，该信经门禁②推送成功
- **THEN** 状态格首段为 `✅ 无需回复 <UTC>`，格内含「发出时快照」段与 `✅ 已推送 <UTC>` 后段；
  `followup_gate.classify_status` 判 `closed`，起草下一封 `release` 直接放行、不需 `串行豁免：`

#### Scenario: 越界取值 ⇒ 仍写 `✅ 已推送`、闸仍锁、审计报出
- **WHEN** 「主要事项」列含 `→ 闭环形态：\`✅ 大概不用回\`（依据：…）`，该信推送成功
- **THEN** 状态格为 `✅ 已推送 <UTC>`（与无标注逐字相同、无快照段），审计含一条
  `followup_closure_form_rejected`（`treated_as=no_annotation`），`classify_status` 判 `in_flight`

#### Scenario: 发出后补写标注 ⇒ 闸零效果
- **WHEN** 一行状态为 `✅ 已推送 <UTC>`（无快照），事后有人在「主要事项」列补写合法标注
- **THEN** 编辑锁串行闸与 `工具-跟进闸查询.py` 对该收信人仍锁；闸查询报「事后追认……以快照为准」
