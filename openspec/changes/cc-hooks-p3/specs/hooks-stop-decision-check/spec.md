## ADDED Requirements

### Requirement: Stop SHALL 检查末条回复的「需你定夺」小节格式

`Stop` 事件触发时，钩子 SHALL 读取 `transcript_path` 指向的会话记录，取最后一条 `role=assistant` 的文本内容。若该文本中出现「需你定夺」或「需你决策」字样（小节标题级别），MUST 检查同一小节内是否存在至少一个 `(a)` 或 `(b)` 形态的选项标签；缺失 MUST `exit 2` 并反馈"「需你定夺」小节缺选项标签"。

若末条回复完全未出现该字样，MUST 放行（`exit 0`）——"本次无需决策"是合法终态，不属于本判据的拦截对象（见 design 决策点 5）。

#### Scenario: 小节存在但缺选项标签
- **WHEN** 末条回复含"## 需你定夺"标题，正文只有一句话陈述、无 `(a)`/`(b)` 标签
- **THEN** `exit 2`，反馈提示补全选项标签

#### Scenario: 小节格式完整
- **WHEN** 末条回复含"需你定夺"小节，且列出 `(a)`、`(b)` 两个选项
- **THEN** 放行，`exit 0`

#### Scenario: 完全无决策小节
- **WHEN** 末条回复通篇是状态说明，不含"需你定夺"或"需你决策"字样
- **THEN** 放行，`exit 0`（不视为违规）

#### Scenario: 明写"本次无需你决策"
- **WHEN** 末条回复含"本次无需你决策"一句、不含选项标签
- **THEN** 放行——该句本身不触发"需你定夺"字样匹配，不进入选项标签检查

### Requirement: 钩子 MUST 在 `stop_hook_active` 为真时放行以防死循环

stdin JSON 的 `stop_hook_active` 字段为 `true`（本次 Stop 是上一次 Stop 钩子拦截后的重试）时，钩子 MUST 直接 `exit 0`，不得重复判定——防止模型持续修不对格式时陷入无限重试。

#### Scenario: 重试场景直接放行
- **WHEN** `stop_hook_active=true`
- **THEN** 不读取 transcript、不做格式判定，直接 `exit 0`

### Requirement: 钩子 SHALL fail-open 且留痕

`transcript_path` 不存在、不可读或解析失败 MUST `exit 0` 放行，MUST NOT 因钩子自身故障阻塞会话结束；异常摘要 SHALL 写入 `reports/hooks-audit.jsonl`。

每次运行（含放行、含拦截、含 `stop_hook_active` 跳过）SHALL 追加一行审计记录。

#### Scenario: transcript 文件不可读
- **WHEN** `transcript_path` 指向的文件不存在
- **THEN** `exit 0`，审计记录 `verdict=error`

#### Scenario: 拦截留痕可核验
- **WHEN** 一次调用被 `exit 2` 拦截
- **THEN** `reports/hooks-audit.jsonl` 新增一行 `verdict=violation`
