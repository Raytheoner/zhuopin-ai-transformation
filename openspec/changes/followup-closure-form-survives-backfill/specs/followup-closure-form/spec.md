## ADDED Requirements

> 🔴 本 spec 按 design **推荐选项**（决策点 1(a)／4(a)／5(c)／6(a)）撰写。
> 决策点 1 若改选 (b)「状态列首段化」，本 spec 的落点整段作废、须重写。**签认前不得 apply。**

### Requirement: 跟进信起草时 SHALL 可写下机器可读的「闭环形态」标注
起草一封跟进信时，起草人 SHALL 可在 README「现有跟进信清单」表该行的**「主要事项」列**内
追加一段闭环形态标注，形如 `→ 闭环形态：\`✅ 无需回复\`（依据：…）`。

标注 MUST 只在既有单元格内追加文本，MUST NOT 新增表格列，MUST NOT 改变任何一行的列数
——`_validate_release_structure` 与 `_followup_readme_rows` 的列数/身份校验 MUST 不受影响
（同队列 `#241` `build_target_file_annotation` 已确立的手法）。

标注的**写入**与**解析** MUST 各自只有一份实现：写入走
`readme_table.build_closure_form_annotation()`，解析走同模块的提取函数，
两者 MUST NOT 在消费者侧被复制第二份。

#### Scenario: 起草时写下标注不改变列数
- **WHEN** 一行的「主要事项」列末尾追加了闭环形态标注
- **THEN** 该行列数不变，编辑锁 `release` 的结构校验不报违规

#### Scenario: 未写标注的行行为与今天逐字相同
- **WHEN** 一行的「主要事项」列不含闭环形态标注
- **THEN** 起草、批准、投递、回填、闸判定的全部行为与本变更前逐字相同

---

### Requirement: 闭环形态标注的取值 SHALL 限定枚举，越界 MUST fail-loud
标注取值 MUST 是 `followup_gate.CLOSED_STATUS_PREFIXES`（闭环四态）之一，
且 MUST 附一段非空的依据文本。

判据 MUST 从 `zhuopin_platform.shared_tools.followup_gate` 取权威值，
MUST NOT 在 `readme_table`／编辑锁／闸查询任一消费者侧自持第二份取值清单。
判据 MUST NOT 退化为布尔开关——那等于在消费者侧悄悄复制一份口径。

取值不在枚举内、或依据文本为空时，该标注 MUST 被报出来（fail-loud），
并 MUST 按「无标注」处理（＝闸仍锁，保守方向）。MUST NOT 静默忽略。

#### Scenario: 合法标注被识别
- **WHEN** 标注为 `→ 闭环形态：\`✅ 无需回复\`（依据：正文三要素表明写「不用回」）`
- **THEN** 解析成功，取值 `✅ 无需回复`，依据文本非空

#### Scenario: 越界取值报出来且按无标注处理
- **WHEN** 标注为 `→ 闭环形态：\`✅ 大概不用回\`（依据：…）`
- **THEN** 报出一条可见的判据违规说明，且该行按无标注处理，闸仍锁

#### Scenario: 缺依据文本同样报出来
- **WHEN** 标注为 `→ 闭环形态：\`✅ 无需回复\`` 且无依据文本
- **THEN** 报出说明，该行按无标注处理

---

### Requirement: 串行闸 SHALL 采信「发出时快照」，MUST NOT 采信事后追加的标注
串行闸判据在判断「该收信人最近一封是否已闭环」时，对已发出的信 MUST 只读
**发送回填写入状态格的闭环形态快照**（见 `followup-status-backfill-preservation`），
MUST NOT 回头读「主要事项」列的标注。

⇒ 一封信发出之后再往「主要事项」列补写标注，对闸 MUST 零效果。
这条约束 MUST 由数据流保证，MUST NOT 通过新增一道拒绝写入的门禁实现。

当「主要事项」列的标注与状态格里的快照**不一致**时，
`工具-跟进闸查询.py` MUST 明确报出该不一致并声明「以快照为准」，MUST NOT 静默取其一。

#### Scenario: 发出后补写标注不开闸
- **WHEN** 某行状态为 `✅ 已推送 …`（无快照），事后有人在「主要事项」列补写
  `→ 闭环形态：\`✅ 无需回复\`（依据：…）`
- **THEN** 闸对该收信人仍锁

#### Scenario: 两者不一致时报出来
- **WHEN** 状态格快照为 `✅ 无需回复`，而「主要事项」列标注已被改成别的取值
- **THEN** 闸查询输出含不一致说明，且判定按快照走

#### Scenario: 起草时即有标注、发出后闸开
- **WHEN** 标注在批准前即存在，信已发出且快照已写入状态格
- **THEN** 闸对该收信人放行，且**不需要** `串行豁免：` 逃生阀

---

### Requirement: 历史行 MUST NOT 被追改
本变更 MUST 只回改 `质量部#7` 一行（把其「主要事项」列已有的散文式判定归一化为标注、
撤掉「发送状态」列里的人工两态并列留痕）。

其余 53 行 MUST NOT 被补标注、MUST NOT 被反推、MUST NOT 被改写——根 `CLAUDE.md` §1
「历史记录不追改」。

历史行的闭环形态覆盖率 MUST 被如实登记为永久 0%，MUST NOT 表述为「逐步补齐」。

#### Scenario: 只动一行
- **WHEN** 本变更包 apply 完毕
- **THEN** README 表格中被修改的数据行**有且仅有** `质量部#7` 一行
