# change-completion-classification Specification

## Purpose
TBD - created by archiving change auto-archive-substantive-complete. Update Purpose after archive.
## Requirements
### Requirement: 未勾项按「是否为 archive 动作本身」精确分类，不用完成率代理

变更包的完工形态 SHALL 由 `tasks.md` 里未勾项的**性质**决定，MUST NOT 由完成率（`done/total`）推断。

判据（两条须同时满足，宁严勿宽）：一条未勾项被判为「archive 动作本身」当且仅当该行同时含
`archive`（大小写不敏感）与 `/opsx:archive`／`openspec archive`／「归档」三者之一。

据此产出四态之一：未勾项为 0 且有复选框 ⇒ `complete`；无任何复选框 ⇒ `no-tasks`；
未勾项**全部**为 archive 动作 ⇒ `substantively-complete`；否则 ⇒ `incomplete`。

#### Scenario: 只差自身归档步骤的包判为实质完工
- **WHEN** 一个包共 31 条 task，唯一未勾的是 `- [ ] 6.5 \`/opsx:archive\``
- **THEN** 判为 `substantively-complete`

#### Scenario: 只差一条真活的包不得判为实质完工
- **WHEN** 一个包共 48 条 task，唯一未勾的是 `- [ ] 8.3 真实主工作区验证……`
- **THEN** 判为 `incomplete`，且**不得**因「只差 1 条」而被归入实质完工

#### Scenario: 只含「归档」二字而无 archive 命令的下游工作不算归档动作
- **WHEN** 未勾项为 `- [ ] 6.2 归档后回填队列 §一 #361`
- **THEN** 该条不算 archive 动作，所在包判为 `incomplete`

#### Scenario: 无 tasks.md 的包显式记名而非静默略过
- **WHEN** 一个变更包目录下没有 `tasks.md`
- **THEN** 判为 `no-tasks` 并出现在输出清单中，MUST NOT 被静默跳过

### Requirement: 「实质完工」须同时覆盖 N/N 与「未勾项全为 archive」两条

「实质完工」SHALL 定义为下列两条**任一**命中：⑴ 未勾项数 ＝ 0（N/N）；
⑵ 未勾项 ≥1 且全部为 archive 动作本身。只要存在一条非 archive 的未勾项即 MUST NOT 命中。

🔴 **⑴ MUST NOT 被当作「已无欠账、无需关注」而排除在外。** 一个变更包从勾完最后一条
到跑完 archive 之间必然经过 N/N；实测 `openspec/changes/archive/` 下 50 个已归档包里
**39 个在归档时是 N/N** ⇒ 它是最常见的形态，且是**最纯的真遗忘归档**（连一条未勾项都
没有，除归档外无事可做）。

#### Scenario: N/N 的在途包判为实质完工
- **WHEN** 一个在途变更包 31 条 task 全部已勾、无任何未勾项
- **THEN** 判为实质完工

#### Scenario: N/N 的在途包告警措辞为「只差归档这一步」
- **WHEN** 上述 N/N 包命中滞留条件并进入告警
- **THEN** 措辞为「只差归档这一步」，且**不得**出现「尚有 0 条真未完项」或「它没完工」

#### Scenario: 含一条非 archive 未勾项的包仍不判实质完工
- **WHEN** 一个包 47 条已勾、1 条未勾且该条不是 archive 动作
- **THEN** 不判为实质完工

### Requirement: 未勾项上「有人留了话」按形态判别，不做自然语言理解

系统 SHALL 判别一条未勾的 archive 项上是否附有人写的说明——判据 MUST 只依据**形态**
（剥掉复选框、任务编号、反引号代码段与命令词后是否仍有实词字符；或其下方是否存在缩进更深的
非复选框子项），MUST NOT 依据「本次不做」「暂缓」等自然语言措辞做模糊匹配。

理由：模糊匹配会让降噪变成默认——随手一句「本次不做」即可绕过，而要求一个特定字符串
（`暂不归档`）正是该机制有价值的地方。形态判别不解析语义，只回答「这里有没有人留了话」。

#### Scenario: 光秃的归档行判为无人留话
- **WHEN** 未勾项为 `- [ ] 9.4 \`/opsx:archive editlock-chokepoint-six-fixes -y\``
- **THEN** 判为无人留话

#### Scenario: 行内带说明的归档行判为有人留话
- **WHEN** 未勾项为 `- [ ] 8.4 \`/opsx:archive\`——**本次不执行，前置条件未满足，如实留置**。未闭合项：`
- **THEN** 判为有人留话

#### Scenario: 说明写在缩进子项里同样判为有人留话
- **WHEN** 未勾的归档行本身光秃，但其下一行是缩进更深的非复选框子项（如 `  - 🔴 本轮不做，前置条件确实不满足……`）
- **THEN** 判为有人留话

### Requirement: 滞留告警按三类各自措辞，「疑似遗忘归档」只用于真遗忘

落库 sweep 对命中滞留条件的在途变更包 SHALL 按上述分类分三类各自措辞，MUST NOT 一律称
「疑似遗忘归档」：

1. `substantively-complete` 且无人留话 ⇒ 「只差归档这一步」，属真遗忘，照旧升级告警；
2. `substantively-complete` 且有人留话 ⇒ 「作者已写明理由，但未用机器认得的入口」；
3. `incomplete` ⇒ 「已 X 天无改动，尚有 N 条真未完项」，MUST NOT 称其为遗忘归档。

告警正文 SHALL 逐条回显命中的包名、判定结论与判定理由，使判据可被现场证伪。

#### Scenario: 尚有真未完项的包不被称为遗忘归档
- **WHEN** 一个 21/23 的包命中滞留条件，其未勾项含一条非 archive 的真未完项
- **THEN** 告警正文对该包使用「尚有真未完项」措辞，且不含「疑似遗忘归档」字样

#### Scenario: 只差归档且无人留话的包仍按遗忘归档升级
- **WHEN** 一个包判为 `substantively-complete` 且无人留话并命中滞留条件
- **THEN** 告警正文对该包使用「只差归档这一步」措辞并按原有路径升级推送

### Requirement: 作者已写理由却未用机器入口时，告警须给出三条可执行出口

对第 2 类（有人留话但未用机器认得的入口）的告警，正文 SHALL 同时列出三条现成入口：
文本标记 `暂不归档`、`预期观察窗口：N 天`、以及 `--ack-stale-change <包名> --note <依据>`。

理由：该类的根因是「有理由没声明」——作者把理由写得比机制要求的还详细，只是没写在机器认得的
地方。告警若只指出「你没声明」而不给出声明方式，等于把同一个缺口留在原地。

#### Scenario: 该类告警含全部三条入口
- **WHEN** 某包被判为「有人留话但未用机器入口」并进入告警
- **THEN** 告警正文中同时出现 `暂不归档`、`预期观察窗口`、`--ack-stale-change` 三个字样

### Requirement: 判定只在主工作区进行，linked worktree 拒绝执行

判定入口 SHALL 在开始判定前确认当前 checkout 是主工作区；位于 linked worktree 时
MUST 抛出拒绝执行异常，且异常文案须说明原因。

判定 MUST 复用 `工具-落库sweep.py` 既有的 `MAIN_WORKSPACE` 常量与
`_assert_not_a_linked_worktree`，MUST NOT 另写第二套主工作区判定。

理由：worktree 副本的 `tasks.md` 可能停在分支点——同一个相对路径、两个不同的事实，
两边都读得出结果、都不报错。（实测：本变更包建造用的 worktree 里存在 2 个主工作区
根本不存在的空「幽灵包」目录，系 `git merge` 拉入归档提交后删文件留空目录所致。）

#### Scenario: linked worktree 拒绝判定
- **WHEN** 在 linked worktree 中调用判定入口
- **THEN** 抛出拒绝执行异常，异常文案含拒绝原因

#### Scenario: 幽灵空目录判为 no-tasks 而非被静默忽略
- **WHEN** `openspec/changes/` 下存在一个不含任何文件的空目录
- **THEN** 该目录判为 `no-tasks` 并出现在清单中

