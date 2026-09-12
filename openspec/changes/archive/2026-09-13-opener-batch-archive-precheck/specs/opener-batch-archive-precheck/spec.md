## Purpose

定义 opener 批处理器（v1 串行版与 v2 泳道版）在派出每个 opener 之前，对其关联的跨桌任务队列 §一 行做完成态校验的行为契约——消灭"已完成的活被原样再派一次、且全程不产生任何错误信号"这一族缺陷（实证：2026-08-24 run `20260824-165657` 的 A4 对应 §一 `#368`，该行 2026-08-22 已销号、2026-08-24 已迁归档，仍被照常派出，烧掉一整个 session）。

本规范的**底线取向**：误派会被人发现（有人在读那个 session），**误跳过不会有任何人在场**。故一切模糊地带一律 fail-open。

## ADDED Requirements

### Requirement: 派出前队列态校验
批处理器 SHALL 在解析出 opener 清单并应用 `-Only` 过滤之后、执行任何派出或泳道分组动作之前，对每个 opener 逐一判定其是否应被跳过；判定结果 SHALL 以 `Skip`（布尔）与 `SkipReason`（文本）两个属性附加在该 opener 上，供其后的打印、分组与执行环节共同消费。

#### Scenario: 校验发生在分组之前
- **WHEN** v2 泳道版解析出 opener 清单并完成 `-Only` 过滤
- **THEN** 队列态校验 SHALL 先于泳道分组执行，使泳道成员清单的打印输出只包含实际将被派出的 opener

#### Scenario: 判定结果对 DryRun 可见
- **WHEN** 以 `-DryRun` 运行任一版本的批处理器
- **THEN** 输出 SHALL 对每个被判定跳过的 opener 显示跳过标记与跳过理由，且不启动任何 session

### Requirement: 四态判定
对每个从 opener 标题解析出的 §一 行号，判定 SHALL 按下列四态之一给出结论，并按 A→D 顺序短路求值。

| 态 | 条件 | 结论 |
|---|------|------|
| A | 在任一在办队列文件命中 §一 行，且状态字段非 `done` | 派出 |
| B | 在任一在办队列文件命中 §一 行，且状态列以 `[S:done]` 开头 | 跳过（理由 `live-done`） |
| C | 在办未命中，在任一归档件命中 §一 行 | 跳过（理由 `archived`） |
| D | 在办与归档均未命中 | 派出 ＋ 告警（理由 `unresolved`） |

#### Scenario: 在办且未完成则派出
- **WHEN** 某 opener 关联 §一 `#397`，该行位于 `跨桌任务队列-机制环境.md` 且状态列以 `[S:open]` 开头
- **THEN** 判定为 A 态，该 opener 照常派出

#### Scenario: 在办但已完成亦须跳过
- **WHEN** 某 opener 关联 §一 `#395`，该行仍位于 `跨桌任务队列-机制环境.md`（从未迁入归档）且状态列以 `[S:done]` 开头
- **THEN** 判定为 B 态，该 opener 被跳过——校验 MUST NOT 仅检查归档件，否则将漏掉"已完成但尚未被每周清扫迁走"这一最长可达 7 天的窗口

#### Scenario: 归档命中即视为已完成
- **WHEN** 某 opener 关联 §一 `#368`，该行在在办两份中均不存在，而在 `跨桌任务队列-归档-202608.md` 的一个 §一 表内命中
- **THEN** 判定为 C 态，该 opener 被跳过

#### Scenario: 无法解析时照常派出
- **WHEN** 某 opener 关联的行号在在办与归档全部载体中均未命中
- **THEN** 判定为 D 态，该 opener **SHALL 照常派出**并产生一条告警；判定 MUST NOT 因"查不到"而跳过

### Requirement: 归档命中不解析归档行的状态内容
当行号在归档件的 §一 表内命中时，判定 SHALL 仅依据"该行存在于归档件"这一事实得出"已完成"，且 MUST NOT 读取或依赖该归档行任何单元格的状态语义。

**依据**：迁归档由每周清扫执行，迁移动作本身即经人工复核的完成判定；而归档行的状态列是否被同步更新无任何机制保证。实测反例——`归档-202608.md` 第 583 行 `#368`，其 `cells[1]`（任务列）写 `✅ **[S:done] 整行销号（2026-08-22…）**`，而 `cells[5]`（状态列，机器字段的规范位置）仍为 `[S:open][D:业] 🆕 2026-08-21 立行，未开工`。按状态字段判将得出 `open`，使白跑一字不差地重演。

#### Scenario: 归档行状态列与实际完成态矛盾时仍判为已完成
- **WHEN** 归档件中 `#368` 行的 `cells[5]` 内容为 `[S:open][D:业] 🆕 2026-08-21 立行，未开工`
- **THEN** 判定结果 SHALL 为"已完成、跳过"，且该结果 MUST NOT 因 `cells[5]` 的取值而改变

### Requirement: 行定位判据
一行被认定为目标行，SHALL 同时满足以下三个条件；任一不满足即不算命中。

1. 该行位于一个 §一 章节内——章节标题匹配 SHALL 同时兼容在办侧写法（`## 一、任务看板`）与归档侧写法（`## §一 …` 及 `### §一 …`，含 H2/H3 混用），且 SHALL 支持同一文件内存在多个 §一 表；
2. 单元格切分 SHALL 复用 `queue_table.split_row_cells()`（按 CommonMark 反引号游程规则屏蔽单元格内裸竖线）；
3. `cells[0]` 去空白后与目标行号**数值相等**。

判据 MUST NOT 使用 `#<行号>` 子串检索。

#### Scenario: 子串检索的假阳性被排除
- **WHEN** 在 `归档-202608.md` 中查找 §一 `#368`
- **THEN** 命中结果 SHALL 只有第 583 行（首格为裸 `368`），而第 533/535/902/904/906/912/1028 行——它们在正文中提及 `#368` 但自身是别的行——MUST NOT 被命中

#### Scenario: 跨章节编号不串
- **WHEN** 在归档件中查找 §一 `#88`，而该文件的 §四 章节内存在编号为 `88` 的行
- **THEN** §四 的那一行 MUST NOT 被命中——§一 与 §四 是两套独立编号

### Requirement: 多载体逐份解析后合并
检索 SHALL 对每份载体文件独立解析后合并结果，且 MUST NOT 将多份文件的文本拼接后再解析一次。

归档件发现 SHALL 使用 glob `1-转型规划/0-全景路线图/跨桌任务队列-归档-*.md`；在办文件 SHALL 取自 `queue_table` 既有的双文件路径常量。

#### Scenario: 单文件多个 §一 表全部被扫到
- **WHEN** 解析 `归档-202608.md`（其内含 4 个 §一 表）
- **THEN** 四个表中的行 SHALL 全部进入检索范围，MUST NOT 只取第一个 §一 表

### Requirement: 锚点从 opener 标题解析
行号 SHALL 从 opener 的 `### A<N> · …` 标题行中解析，抽取模式为 `(?:队列|§一)\s*#(\d+)` 的全部匹配；解析前 SHALL 先剥除 `§四 #<数字>` 与 `§二 <批次>` 形态的引用。计划文件格式 MUST NOT 因本能力而新增任何必填字段。

#### Scenario: 只取 §一 引用
- **WHEN** opener 标题为 `### A22 ·【CC】#353 apply：…——队列 #353／§四 #108(a)`
- **THEN** 解析结果 SHALL 只含 `353`，`108` MUST NOT 进入查询

#### Scenario: 多行号取合取
- **WHEN** opener 标题为 `### A27 ·【CC】…——队列 #397／#396`，其中 `#396` 已完成而 `#397` 仍在办
- **THEN** 该 opener SHALL 被派出——只有当全部被引用的 §一 行都已完成时才跳过

#### Scenario: 无行号标题属正常形态
- **WHEN** opener 标题为 `### A2 ·【Cowork】队列每周清扫迁归档（本轮巡检移交件）——协议〇.8／§四 #44`，其中不含任何 §一 引用
- **THEN** 该 opener SHALL 照常派出，并产生一条告警，且该告警文案 SHALL 与"写了行号但查不到"（D 态）可区分

### Requirement: 跳过不得流入哨兵判定
被跳过的 opener SHALL 在执行状态计算之前被短路，MUST NOT 进入 `OPENER_DONE`/`OPENER_PARTIAL` 哨兵检测分支，MUST NOT 被判定为 `NO-SENTINEL`，且 MUST NOT 触发任一版本的 fail-loud 中断。

`SKIPPED` SHALL 作为与 `OK`/`PARTIAL`/`NO-SENTINEL`/`FAIL` 并列的第一等执行状态，出现在汇总表与 `summary.txt` 中，并携带行号与跳过理由。存在跳过项 SHALL NOT 改变进程退出码。

#### Scenario: 跳过不中断串行批次
- **WHEN** v1 串行版中某个 opener 被判定跳过（因此不会产生 `OPENER_DONE` 哨兵）
- **THEN** 该 opener 记为 `SKIPPED`，循环 SHALL 继续执行其后的 opener，MUST NOT 触发 fail-loud `break`

#### Scenario: 跳过不停泳道
- **WHEN** v2 泳道版中某泳道的一个成员被判定跳过
- **THEN** 该泳道的其余成员 SHALL 照常按序执行，泳道 MUST NOT 因此中止

#### Scenario: 整泳道跳空则不启动
- **WHEN** v2 泳道版中某泳道的全部成员均被判定跳过
- **THEN** 该泳道 MUST NOT 被 `Start-Job` 启动，且 MUST NOT 占用并发额度或等待 `-StaggerSec` 错峰间隔

### Requirement: 跳过必留痕
每一次跳过 SHALL 在批次日志与 `summary.txt` 中留下可读记录，含 opener 编号、关联行号、命中载体（文件名）与跳过理由。MUST NOT 静默跳过。

#### Scenario: 跳过记录含命中载体
- **WHEN** `#368` 因归档命中被跳过
- **THEN** 记录 SHALL 指明命中于 `跨桌任务队列-归档-202608.md`，使人可直接复核该判定

### Requirement: 强制派出逃生阀
批处理器 SHALL 提供 `-Force` 开关，使全部跳过判定失效、恢复校验引入前的派出行为。使用该开关 SHALL 在日志中显式留痕。

#### Scenario: Force 绕过校验且留痕
- **WHEN** 以 `-Force` 运行批处理器，且某 opener 关联的行已归档
- **THEN** 该 opener 照常派出，且日志 SHALL 记录一条表明归档校验已被绕过的条目

### Requirement: 校验自身失败时 fail-open
当查询子进程调用失败、超时或返回无法解析的输出时，判定 SHALL 退化为"派出 ＋ 告警"，MUST NOT 退化为跳过。

#### Scenario: 查询进程失败不致误跳过
- **WHEN** 查询子进程返回非预期输出或无法启动
- **THEN** 相关 opener SHALL 照常派出，并产生一条表明校验未能完成的告警
