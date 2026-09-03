## ADDED Requirements

### Requirement: UserPromptSubmit SHALL 从根 `CLAUDE.md` 抓取常驻五条并注入

每轮 `UserPromptSubmit` 事件，钩子 SHALL 读取根 `CLAUDE.md`，按行内锚点 `<!-- UPS5:1 -->` … `<!-- UPS5:5 -->` 提取对应五行正文（称呼纪律／禁推断性别／需你定夺格式／粘贴端标注／默认项两前提），拼接为 ≤300 字节摘要，通过 `hookSpecificOutput.additionalContext` 注入。

提取 MUST 直接读取根 `CLAUDE.md` 当前正文，MUST NOT 在脚本内维护一份硬编码副本——正文变更后下一轮注入 MUST 自动反映新文本，不需要同步改脚本。

#### Scenario: 五条锚点齐全
- **WHEN** 根 `CLAUDE.md` 含全部 5 个 `UPS5:n` 锚点
- **THEN** 注入内容含 5 条摘要，且与当前正文逐字一致（截断规则见下一条）

#### Scenario: 正文变更后自动同步
- **WHEN** 根 `CLAUDE.md` 中 `UPS5:1` 锚点行的措辞被改写
- **THEN** 下一轮 `UserPromptSubmit` 注入内容反映新措辞，无需改动本钩子脚本

### Requirement: 锚点命中数 SHALL 被断言，漂移 MUST 可见不得静默

若命中的 `UPS5:n` 锚点数量不等于 5（缺失或重复），钩子 MUST 仍然 `exit 0`（fail-open，不阻断正常使用），但 MUST 在注入内容与 `reports/hooks-audit.jsonl` 中同时标注"预期 5、实得 N"，MUST NOT 静默按实得数量拼接摘要而不报告差异。

#### Scenario: 锚点缺失一处
- **WHEN** 根 `CLAUDE.md` 只剩 4 个 `UPS5:n` 锚点（其中一处被误删）
- **THEN** 钩子仍 `exit 0`，注入内容含"⚠ 常驻五条锚点异常：预期 5、实得 4"，审计记录 `verdict=undetermined`

#### Scenario: 锚点重复
- **WHEN** 根 `CLAUDE.md` 中 `UPS5:2` 出现两次
- **THEN** 注入内容含锚点异常提示，`findings` 字段记录重复的锚点编号

### Requirement: 每条摘要 SHALL 截断至可控长度且总量 ≤300 字节

每条单独摘要 MUST 截断到不超过 80 字节（超出部分以"…"标注被截断），五条总长度 MUST 不超过 300 字节，避免每轮注入过量挤占上下文预算。

#### Scenario: 单条过长被截断
- **WHEN** `UPS5:3` 锚点行正文长度 200 字节
- **THEN** 注入内容中该条被截断至 80 字节以内并以"…"结尾

### Requirement: 钩子 SHALL fail-open 且每轮留痕

根 `CLAUDE.md` 不可读或解析异常 MUST `exit 0`，注入内容含"常驻五条不可用：<原因>"，MUST NOT 静默注入空内容而不说明。

每次运行（含正常、含锚点异常、含读取失败）SHALL 向 `reports/hooks-audit.jsonl` 追加一行。

#### Scenario: 根文件读取失败
- **WHEN** 根 `CLAUDE.md` 路径不存在
- **THEN** `exit 0`，注入"常驻五条不可用：<原因>"，审计记录 `verdict=error`
