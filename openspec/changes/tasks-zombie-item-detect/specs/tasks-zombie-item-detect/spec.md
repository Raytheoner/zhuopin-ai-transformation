## ADDED Requirements

### Requirement: 僵尸未勾项检出 SHALL 分强弱两档，弱判据 MUST NOT 致 CI 失败
工具 SHALL 把判据分为两档：**强判据**（J-A 前置矛盾、J-C 前置项无下游引用）判为违规并 SHALL 以非零退出码结束；**弱判据**（J-B 节内乱序、J-D 基线回显）SHALL 仅输出供人工复核的清单，**MUST NOT** 影响退出码，无论命中多少条。

弱判据的输出措辞 MUST 为「请复核」语义，**MUST NOT** 使用「疑似已完成」「可以勾除」一类暗示结论的措辞——弱判据实测精度为 4/5，其唯一误报正是一条真未决的开放口径项，把它误勾的代价大于漏勾。

#### Scenario: 弱判据命中不致失败
- **WHEN** 扫描发现 7 条 J-B 命中而 J-A／J-C 均为 0
- **THEN** 工具以退出码 0 结束，并在输出中列出 7 条待复核项

#### Scenario: 强判据命中即失败
- **WHEN** 某变更包内一项已 `[x]`，而其所在节标题声明的前置项仍 `[ ]`
- **THEN** 工具以非零退出码结束并指出该对项号

### Requirement: J-A 前置矛盾 SHALL 同时识别两种前置声明来源
前置关系 SHALL 从两处提取：⑴ 节标题内的「前置 N.M」（可含 `/`、`、`、`,`、`，` 分隔的多个）；⑵ 条目正文内的「前置 N.M」。两处 MUST 都被识别，MUST NOT 只认其一。

被引用的前置项号在本文件内不存在时，工具 MUST 发出可见提示并跳过该条引用，MUST NOT 静默忽略。

#### Scenario: 节标题声明的前置被识别
- **WHEN** 节标题为 `## 7. 真实数据验证（…；前置 1.5/1.6）`，且该节内 `7.1` 已 `[x]` 而 `1.5` 仍 `[ ]`
- **THEN** 判为 J-A 违规，输出 `7.1 → 1.5`

#### Scenario: 引用了不存在的项号
- **WHEN** 某项正文写「前置 9.9」而本文件不存在 `9.9`
- **THEN** 输出可见提示，且不因此判违规

### Requirement: J-C SHALL 守住 J-A 的失效面
工具 SHALL 检出「正文含『前置登记』字样、却无任何项以『前置 N.M』引用它」的项，并判为强判据违规。

理由 SHALL 记录在实现注释内：J-A 的全部效力建立在「有人写了前置引用」之上；不写即 J-A 对该项结构性失效，且失效不产生任何信号。

工具 SHALL 打印本次扫描发现的前置声明总数，使该数降为 0（即 J-A 整体失效）这一情况可被看见。

#### Scenario: 前置登记项无人引用
- **WHEN** 某包存在 `- [ ] 1.6 前置登记：…`，而全文无任何「前置 1.6」
- **THEN** 判为 J-C 违规

#### Scenario: 前置声明总数回显
- **WHEN** 扫描完成
- **THEN** 输出包含「本次扫描共发现 N 个前置声明」一行

### Requirement: 扫描面 SHALL 排除已归档变更包
扫描面 SHALL 为 `openspec/changes/*/tasks.md`，**MUST NOT** 包含 `openspec/changes/archive/**`。

#### Scenario: archive 下的 tasks.md 不进扫描
- **WHEN** `openspec/changes/archive/2026-08-07-fi2-tax-export-ingest/tasks.md` 存在且含未勾项
- **THEN** 该文件不出现在任何输出中

### Requirement: 工具 SHALL 为纯只读
工具 MUST NOT 写入任何文件——不产锁文件、快照、状态文件、日志或备份副本，输出只经 stdout。

#### Scenario: 运行后工作区无变化
- **WHEN** 在干净工作区运行本工具
- **THEN** `git status --porcelain` 输出为空
