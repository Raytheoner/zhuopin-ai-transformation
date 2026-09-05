## ADDED Requirements

### Requirement: opener 生成器当日撞号查重
`工具-opener生成.py::generate_opener` SHALL 在字段与骨架硬规则校验通过后、拼装正文之前，扫描 `1-转型规划/` 全树 `.md`，收集当日（`--op-id` 的 `MMDD` 部分）已出现过的编号后缀——全称形态 `OP-MMDD-X` 与短形形态 `[Win]MMDDX-`（仅认此结构锚点）两者皆计入。

若本次 `--op-id` 的后缀已在当日已用集合中，工具 MUST 拒绝生成（不产出任何 opener 文本），并在错误信息中给出当日下一个未使用的空号。

判据 MUST NOT 对短形做全文裸数字子串扫描——只认 `[Win]MMDDX-` 结构锚点，避免把正文中与编号无关的四位数字巧合（日期、金额、行号）误判为已用编号。

#### Scenario: 全称编号当日已被使用，拒绝生成并给出空号
- **WHEN** 调用 `generate_opener(op_id="OP-0905-A", ...)`，而 `1-转型规划/` 树内某份 `.md` 已含 `OP-0905-A`
- **THEN** 工具抛出错误，错误信息含"撞号"字样与下一个空号（如 `OP-0905-B`）

#### Scenario: 短形 session 标题命中同样判撞号
- **WHEN** 调用 `generate_opener(op_id="OP-0905-C", ...)`，而某份 `.md` 内含一行 `标题：[Win]0905C-...`（无任何全称 `OP-0905-C` 出现）
- **THEN** 工具同样拒绝生成，判定为撞号

#### Scenario: 裸数字巧合不算已用（非恒真自证）
- **WHEN** 某份 `.md` 内含字符串 `0905D`，但既非 `OP-0905-D` 全称、也不在 `[Win]MMDDX-` 结构位置
- **THEN** 调用 `generate_opener(op_id="OP-0905-D", ...)` 不因此被拒绝——用于证明判据未做全文裸子串扫描

#### Scenario: 不同日期的相同后缀不冲突
- **WHEN** `1-转型规划/` 树内已存在 `OP-0904-A`，调用 `generate_opener(op_id="OP-0905-A", ...)`
- **THEN** 不判撞号（日期段不同）

### Requirement: 看护件 §三 泳道 dry-run 解析
`工具-泳道看护状态机.py` SHALL 提供 `parse_section_three_lanes(text)` 与 CLI 子命令 `dry-run --file <路径>`，用于解析看护件正文中 `## 三、` 小节下的各 `### A<N>` 泳道条目。

解析判据 MUST 仅依赖两个结构锚点：① `### A<N>` 标题；② 该标题后最近一个围栏代码块内存在至少一行以 `【设置】` 开头。解析 MUST NOT 依赖代码块的行数，MUST NOT 要求块内出现"做什么"或"不做什么"字样——精简为 3 行（首行＋【设置】＋读行）的泳道 opener 与含"做什么/不做什么"小节的旧版本 MUST 被同样正确识别与计数。

`## 三bis` 标题之后的看护者开场词代码块 MUST NOT 被计入泳道列表。

#### Scenario: 3 行精简版泳道被正确计数
- **WHEN** 看护件正文含两条 `### A<N>` 标题，其代码块各只有 3 行（首行、【设置】行、读行）
- **THEN** `parse_section_three_lanes` 返回 2 条记录，均标记为已识别

#### Scenario: 旧长版本（含做什么/不做什么）同样被正确计数（向后兼容）
- **WHEN** 看护件正文含一条 `### A<N>` 标题，其代码块含首行、【设置】行、开工/读行、"做什么"多行、"不做什么"多行
- **THEN** `parse_section_three_lanes` 返回 1 条记录，标记为已识别

#### Scenario: §三bis 看护者开场词不计入泳道
- **WHEN** 正文在若干 `### A<N>` 泳道之后另有一个 `## 三bis` 小节及其代码块
- **THEN** 返回的泳道列表条数等于 `### A<N>` 标题数，不含 `## 三bis` 后的块

#### Scenario: 缺 【设置】 行的泳道被标记未识别
- **WHEN** 某 `### A<N>` 标题后的代码块首行非空，但块内不含任何以 `【设置】` 开头的行
- **THEN** 该条记录 `recognized=False`，并给出原因

### Requirement: opener 子任务泳道／看护者变体默认写入并行与推送口径
`工具-opener生成.py::generate_opener` SHALL 支持 `variant` 参数，取值 `standard`（默认）／`subtask_lane`／`guardian`。

`variant="subtask_lane"` 的产出 MUST NOT 包含 `set_session_title` 调用行，且 MUST 无条件在正文追加两条固定说明：并行上限 4（超出排下一波，错峰 ≥90 秒）；收工只 push 本泳道分支、不碰主仓、不 ff master。

`variant="guardian"` 的产出 MUST 包含 `set_session_title` 调用（标题值格式为 `[Win]MMDDX-看护<短名>`），且 MUST 在正文追加一条面向看护者的说明，指导其用 Task/Agent 起子任务时同样遵守并行上限与不越界 push/ff 的口径。

两种非 `standard` 变体 MUST NOT 用于 `env="Cowork"`。

生成器的自校验（复用 `工具-opener块lint.py::check_block`）在校验 `subtask_lane` 变体产出时 MUST 传入 `is_subtask_lane=True`，使产出正确通过既有形态①（CC opener 缺 set_session_title）判据的结构性排除。

#### Scenario: 子任务泳道变体不含 set_session_title 且带默认口径
- **WHEN** 调用 `generate_opener(variant="subtask_lane", env="CC", ...)`
- **THEN** 产出文本不含 `set_session_title` 子串，且同时含"并行上限 4"与"push"相关的两条默认说明

#### Scenario: 看护者变体含 set_session_title 与看护者视角的默认口径
- **WHEN** 调用 `generate_opener(variant="guardian", env="CC", ...)`
- **THEN** 产出文本含 `set_session_title` 调用与匹配 `[Win]MMDDX-看护<短名>` 的标题值，且含指导其起子任务时遵守并行/push 口径的说明

#### Scenario: 子任务泳道产出通过既有 lint 形态①的结构性排除
- **WHEN** 对 `variant="subtask_lane"` 的产出块调用 `check_block(block, is_subtask_lane=True)`
- **THEN** 不命中形态①（CC opener 缺 set_session_title）

### Requirement: 泳道看护状态机记录并汇总 index.lock 撞击次数
`工具-泳道看护状态机.py` SHALL 提供 `record_lock_hit(batch, wave, lane)` 与 CLI 子命令 `record-lock-hit`，供任一泳道在遭遇 `.git/index.lock` 冲突时留痕一次；`count_lock_hits(batch=None)` SHALL 现取汇总该批次（或全量）的撞击总数。

`summary` 子命令的输出 SHALL 在既有「本批停 N 次」「本批转出 N 项」两行之后，新增一行「本批 index.lock 撞击 N 次」。

本能力仅提供记录入口，MUST NOT 自动侦测 git 锁冲突——记录动作由调用方（看护者或子任务）在真实遭遇撞锁时主动触发。

#### Scenario: 记录后 summary 报出对应次数
- **WHEN** 对同一批次调用 `record_lock_hit` 两次，随后调用 `summary --batch <该批次>`
- **THEN** 输出含「本批 index.lock 撞击 2 次」

#### Scenario: 未记录任何撞击时 summary 报 0 次
- **WHEN** 某批次从未调用过 `record_lock_hit`
- **THEN** `summary --batch <该批次>` 输出含「本批 index.lock 撞击 0 次」

#### Scenario: 计数按批次过滤
- **WHEN** 对批次 B1 记录 1 次撞击、对批次 B2 记录 1 次撞击
- **THEN** `count_lock_hits(batch="B1")` 返回 1，`count_lock_hits(batch="B2")` 返回 1，`count_lock_hits()`（不传 batch）返回 2
