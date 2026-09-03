## MODIFIED Requirements

### Requirement: 落库 sweep SHALL 守卫必载 `CLAUDE.md` 与 `.claude/rules/*.md` 的尺寸

每轮 sweep SHALL 量取仓库内 `CLAUDE.md` 与 `.claude/rules/*.md` 的**字节数**并与阈值比对。

覆盖范围 SHALL 为：根 `CLAUDE.md`、`4-数字员工/**/CLAUDE.md`、`5-平台底座/*/CLAUDE.md`、`.claude/rules/*.md`。

阈值 SHALL 为：根文件 **12 KB**（12,288 字节，只降不升的棘轮——见下一条 Requirement）；场景与底座文件 **50 KB**（51,200 字节）；`.claude/rules/` 单份文件 **8 KB**（8,192 字节）。

量取对象 SHALL 是 sweep 自身 `repo_root` 下的文件真身；`.claude/worktrees/**` 下的副本 MUST NOT 被纳入——它们是历史版本，对其告警既无意义又会持续误报。

尺寸 MUST 以字节计，MUST NOT 以字符数或行数替代。

#### Scenario: 根文件超限
- **WHEN** 根 `CLAUDE.md` 字节数 > 12,288
- **THEN** 该文件被判为超限并进入告警集合

#### Scenario: 场景文件超限
- **WHEN** `4-数字员工/财务部/FI2-三单匹配自动对账/CLAUDE.md` 字节数 > 51,200
- **THEN** 该文件被判为超限并进入告警集合

#### Scenario: rules 单份文件超限
- **WHEN** `.claude/rules/场景建造与合规.md` 字节数 > 8,192
- **THEN** 该文件被判为超限并进入告警集合

#### Scenario: worktree 副本不参与判定
- **WHEN** `.claude/worktrees/<任一>/CLAUDE.md` 或 `.claude/worktrees/<任一>/.claude/rules/*.md` 字节数超过任一阈值
- **THEN** 该文件不进入告警集合，且不出现在回显中

## ADDED Requirements

### Requirement: `.claude/rules/*.md` 合计字节数 SHALL 有独立上限

`.claude/rules/` 目录下全部 `*.md` 文件的字节数之和 SHALL 与 30 KB（30,720 字节）比对，超限 SHALL 进入告警集合（告警 key 固定为 `.claude/rules/__total__`，与单份文件超限各自独立判定、互不覆盖）。

该判据 MUST 与单份文件阈值（8 KB）同轮计算，两者均可各自独立触发告警。

#### Scenario: 合计超限但单份均未超
- **WHEN** 5 份 rules 文件各自 6 KB（均 <8 KB），合计 30 KB（>30,720 字节的整数倍边界需以实际字节数判）
- **THEN** 若合计字节数确实 > 30,720，`.claude/rules/__total__` 进入告警集合，5 份单文件均不告警

#### Scenario: 合计与单份同时超限
- **WHEN** 某份 rules 文件 9 KB 且合计 32 KB
- **THEN** 该文件的相对路径与 `.claude/rules/__total__` 同时进入告警集合，各自独立一条

#### Scenario: 全部合规
- **WHEN** 5 份 rules 文件合计 21,165 B（现网实测值），单份均 <8,192 B
- **THEN** 均不进入告警集合，回显仍逐项列出当前值与阈值差额
