## ADDED Requirements

### Requirement: 子任务泳道 opener 正文 MUST 内嵌心跳约定

`工具-opener生成.py` 以 `--variant subtask_lane` 拼装的 opener 正文，MUST 无条件包含一条心跳约定提醒（含完整命令模板：`--lane`／`--text`／收工 `--done --batch <批次>`），不得仅存在于看护者自行阅读的规则正本（`zhuopin-lane-watch/SKILL.md`）或看护件「硬边界继承」段——这两处 MUST NOT 被视为已满足本要求，因为它们不在被派发给 Task/Agent 子任务的 opener 正文范围内。

该提醒 MUST 由生成器强制注入，MUST NOT 仅依赖起草人手写骨架时记得复述；`1-转型规划/0-全景路线图/opener骨架.md`【CC · 子任务泳道】节 MUST 与生成器常量逐字一致（同锚，防「正本改了生成器没跟」或反之的漂移）。

心跳提醒的收工命令示例 MUST 包含 `--batch <批次>` ——缺失该参数会导致该次心跳不计入任何批次的 `summary` 统计（工具行为：`--batch` 为可选参数、缺省时静默退化为"批次归属未知"，不报错）。

系统 MUST 提供一道静态复核判据（`工具-opener块lint.py` 形态⑩），对任一「子任务泳道」opener 块（判定同既有形态⑥／⑧／⑨的收窄口径：看护件含 `## 三bis` 小节、块出现在该小节之前）缺少心跳约定行的情况予以标记；该判据 MUST NOT 覆盖非子任务泳道块（标准【CC】／【Cowork】／guardian 变体不经批处理器的心跳看门狗，不适用本要求）。

#### Scenario: 生成器产出的子任务泳道 opener 含心跳约定

- **WHEN** 调用 `工具-opener生成.py --variant subtask_lane` 生成 opener
- **THEN** 成品正文 MUST 含心跳约定行，且该行 MUST 出现在并行上限提醒之后、push-only 提醒之前

#### Scenario: 心跳提醒的收工示例带 `--batch`

- **WHEN** 读取心跳约定行的收工命令模板
- **THEN** 该模板 MUST 含 `--batch <批次>`，MUST NOT 仅示例 `--done` 而不带 `--batch`

#### Scenario: 骨架正本与生成器常量逐字一致

- **WHEN** 分别读取 `opener骨架.md`【CC · 子任务泳道】节的心跳约定行与生成器常量 `SUBTASK_HEARTBEAT_NOTE`
- **THEN** 两者字符 MUST 完全相同（占位符除外），改一处不改另一处 MUST 被单测检出

#### Scenario: 子任务泳道块缺心跳约定行被 lint 标记

- **WHEN** 某看护件含 `## 三bis` 小节，其之前的某个 `### A<N>` 泳道 opener 代码块不含心跳约定行
- **THEN** `工具-opener块lint.py` MUST 报出形态⑩，且说明须指向生成器重出路径与骨架对应行

#### Scenario: 非子任务泳道块不受本要求约束

- **WHEN** 某 opener 块为标准【CC】／【Cowork】变体，或为看护者 `## 三bis` 之后的开场词块
- **THEN** 心跳约定缺失 MUST NOT 被判为形态⑩违规——这些块不经批处理器的心跳看门狗

#### Scenario: 心跳工具本身在 worktree 隔离下正常工作（非本要求覆盖，但记录于此作为前提事实）

- **WHEN** 子任务在 `isolation: "worktree"` 环境内调用 `工具-泳道看护状态机.py heartbeat`
- **THEN** 心跳文件 MUST 落在主工作区（`REPO_ROOT` 经 `git rev-parse --git-common-dir` 解析），与 `lane-watch-heartbeat-visibility` 已确认的读写同锚结论一致——本要求解决的是"调用侧是否被告知要调用"，不是"调用后写到哪里"
