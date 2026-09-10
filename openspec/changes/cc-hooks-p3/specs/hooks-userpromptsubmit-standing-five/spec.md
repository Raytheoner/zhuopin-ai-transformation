## ADDED Requirements

> 🔴 **2026-09-10 修订（队列 §一 `#537`，CC `OP-0910-D`）**：原「锚点命中数恒等于 5」判据已改判为「锚点集自洽」。成因＝2026-09-09 往根 `CLAUDE.md` §5 合法新增第 6 条常驻纪律（`UPS5:6`）后，旧判据每轮打「预期 5、实得 6」、且第 6 条**从未被注入**（旧实现只遍历 1..5），并让一条单测长期常红——常红掩盖真红。把 5 改成 6 只是把同一颗定时炸弹推后一格（同族＝ §一 `#535` 夹具硬编码日期跨零点转红）：**任何「写死的数量／日期」都会在下一次变化时自动转红。** 原文措辞保留在 git 历史，本文件为当前生效判据。

### Requirement: UserPromptSubmit SHALL 从根 `CLAUDE.md` 抓取常驻纪律并注入

每轮 `UserPromptSubmit` 事件，钩子 SHALL 读取根 `CLAUDE.md`，按行内锚点 `<!-- UPS5:n -->`（n 从 1 起递增，**条数不写死**）提取对应各行正文（称呼纪律／禁推断性别／需你定夺格式／粘贴端标注／默认项两前提／代执行优先…），拼接为 ≤300 字节摘要，通过 `hookSpecificOutput.additionalContext` 注入。

提取 MUST 直接读取根 `CLAUDE.md` 当前正文，MUST NOT 在脚本内维护一份硬编码副本——正文变更后下一轮注入 MUST 自动反映新文本，不需要同步改脚本。

注入 MUST 按锚点编号**升序输出全部命中条目**，MUST NOT 按固定区间 `1..N` 遍历——固定区间会把编号大于 N 的条目整条丢掉且不产生任何信号。

注入前缀中的条数 MUST 取实得条数（`📌 常驻纪律 <N> 条：`），MUST NOT 写死字面量，避免展示层自身失真。

#### Scenario: 锚点集连续齐全
- **WHEN** 根 `CLAUDE.md` 的 `UPS5:n` 锚点编号构成 1..max 的连续整数集且无重复
- **THEN** 注入内容含全部 max 条摘要，与当前正文逐字一致（截断规则见下），无异常提示，审计记录 `verdict=pass`

#### Scenario: 合法新增一条常驻纪律
- **WHEN** §5 新增第 6 条并插入 `UPS5:6` 锚点，编号集变为 1..6
- **THEN** 注入内容含第 6 条，且 MUST NOT 出现任何锚点异常提示（合法增删不得产生噪声）

#### Scenario: 正文变更后自动同步
- **WHEN** 根 `CLAUDE.md` 中 `UPS5:1` 锚点行的措辞被改写
- **THEN** 下一轮 `UserPromptSubmit` 注入内容反映新措辞，无需改动本钩子脚本

### Requirement: 锚点集自洽性 SHALL 被断言，漂移 MUST 可见不得静默

钩子 MUST 校验锚点集自身自洽，判据三族、**与总条数无关**：① **缺号**——命中的合法编号 MUST 构成 1..max 的连续整数集；② **重复**——同一编号 MUST NOT 出现多次；③ **非法编号**——编号 MUST ≥1。另：**一条锚点都未命中** MUST 判为异常（"结果太干净"形态，见 CLAUDE.md §5「工具静默回退」纪律），MUST NOT 当作"空集自洽"放行。

任一命中时钩子 MUST 仍然 `exit 0`（fail-open，不阻断正常使用），但 MUST 在注入内容与 `reports/hooks-audit.jsonl` 中同时点名该差异（缺哪一号／重复哪一号／非法哪一号），MUST NOT 静默按实得条目拼接摘要而不报告。

锚点编号解析 MUST 支持多位数（正则 `\d+`），MUST NOT 只吃一位数——否则 `UPS5:10` 会被整条无视且不产生信号。

#### Scenario: 中间缺号
- **WHEN** 根 `CLAUDE.md` 的锚点编号为 1、2、4、5（3 被误删）
- **THEN** 钩子仍 `exit 0`，注入内容含"⚠ 常驻纪律锚点异常（缺号：3…）"，已命中的条目仍照常展示，审计记录 `verdict=undetermined`

#### Scenario: 编号不从 1 开始
- **WHEN** 锚点编号为 2、3、4
- **THEN** 报"缺号：1"，审计记录 `verdict=undetermined`

#### Scenario: 非法编号
- **WHEN** 出现 `UPS5:0`
- **THEN** 报"非法编号：0"，审计记录 `verdict=undetermined`

#### Scenario: 一个锚点都没有
- **WHEN** 根 `CLAUDE.md` 存在但不含任何 `UPS5:n` 锚点
- **THEN** 报"未命中任何 UPS5:n 锚点"，审计记录 `verdict=undetermined`

#### Scenario: 锚点重复
- **WHEN** 根 `CLAUDE.md` 中 `UPS5:2` 出现两次
- **THEN** 注入内容含"重复编号：2"，审计记录 `verdict=undetermined`

### Requirement: 每条摘要 SHALL 截断至可控长度且总量 ≤300 字节

每条单独摘要 MUST 截断到不超过 80 字节（超出部分以"…"标注被截断），全部条目总长度 MUST 不超过 300 字节，避免每轮注入过量挤占上下文预算。

预算分配 MUST 按实得条数均分（扣除分隔符开销）后与 80 字节硬顶取较小值，使**每一条都在**、长短随条数自适应；MUST NOT 先各截 80 字节再整体截 300 字节——那会让尾部条目整条消失。

#### Scenario: 单条过长被截断
- **WHEN** `UPS5:3` 锚点行正文长度 200 字节
- **THEN** 注入内容中该条被截断至 80 字节以内并以"…"结尾

#### Scenario: 多条均超长
- **WHEN** 全部锚点行正文均远超预算
- **THEN** 每一条都仍出现在注入内容中（各自更短），MUST NOT 有条目整条消失

### Requirement: 钩子 SHALL fail-open 且每轮留痕

根 `CLAUDE.md` 不可读或解析异常 MUST `exit 0`，注入内容含"常驻纪律不可用：<原因>"，MUST NOT 静默注入空内容而不说明。

每次运行（含正常、含锚点异常、含读取失败）SHALL 向 `reports/hooks-audit.jsonl` 追加一行。

#### Scenario: 根文件读取失败
- **WHEN** 根 `CLAUDE.md` 路径不存在
- **THEN** `exit 0`，注入"常驻纪律不可用：<原因>"，审计记录 `verdict=error`
