## ADDED Requirements

> **本 spec 按 design D4 的推荐值 (a)「只检测＋只告警＋给可粘贴命令」撰写。** design 审若改判取 (b)（自动追加 §四 行），本文件须整体重写「决策台账缺口」一节——那是一次写盘路径变更，不是同一份 spec 的参数调整。

### Requirement: 状态分诊候选 SHALL 由常驻轮次扫描，MUST NOT 只在 WIP 超限时触发

分诊候选的产出 SHALL 由 `工具-落库sweep.py` 的每小时轮次调用，且 **MUST NOT** 以 `_count_mechanism_wip() > cap` 为前置条件。

扫描面 SHALL 覆盖**两份队列**的 §一，**MUST NOT** 只覆盖机制环境队列——业务场景队列的可动机制 WIP 恒为 0，以 WIP 为触发条件时该队列的候选结构性不可达。

`_suggest_status_reclassification()` 与 `STALE_STATUS_PHRASES` **MUST NOT** 被修改，且 sweep 侧 **MUST NOT** 复制第二套等价判据。

#### Scenario: WIP 未超限时候选仍被产出
- **WHEN** 机制类可动 WIP 为 21、上限为 22（未超限），而两份队列 §一 共存在 8 条命中措辞的行
- **THEN** 本轮扫描仍产出全部 8 条候选，并进入分档与回显

#### Scenario: 业务场景队列的候选被覆盖
- **WHEN** 业务场景队列 §一 存在命中措辞的 `[D:业]` 行
- **THEN** 该行出现在候选清单中，且清单标明其所属队列文件

### Requirement: 候选 SHALL 分强弱两档，弱档 MUST NOT 推送

工具 SHALL 把候选分为两档：**强档** ＝ 命中措辞且命中片段未命中「否定词表」且行状态非 `blocked`；**弱档** ＝ 其余命中行。

强档 SHALL 推送至企微运维群；弱档 **MUST NOT** 推送，只进 `sweep-commit.log` 回显。

否定词表 SHALL 只用于**降档**，**MUST NOT** 用于剔除——被降档的行 SHALL 仍在日志中逐条列出。

否定词表内每一条 SHALL 附一个真实来源行号；新增措辞的门槛 SHALL 低于删除措辞的门槛（同 `STALE_STATUS_PHRASES` 既有「可增不可删」口径）。

#### Scenario: 已解除的历史留步被降档
- **WHEN** 某行状态列写「上一条留步的 ⑤……已由 Shao Peishen 当日答 `G-6 = (a)` 批准……依赖解除」
- **THEN** 该行判为弱档，不进企微推送，但出现在日志回显里

#### Scenario: 真实待拍板行保持强档
- **WHEN** 某行状态列写「是否 ff 进 master 待 Shao Peishen 拍板，未合入前不归档」且不含任何否定词
- **THEN** 该行判为强档并进入推送

#### Scenario: 降档条数每轮回显
- **WHEN** 本轮有 5 条候选被降档
- **THEN** 日志中出现本轮降档条数，使否定词表写宽导致的失效可被看见

### Requirement: 回测 SHALL 达标方可 apply

否定词表定稿后 SHALL 对 2026-09-06 实测的 8 条候选逐条回测，须满足：4 条亚型 B（`#340`／`#470`／`#471`／`#472`）全部降至弱档，3 条真阳性（`#455`／`#394`／`#418`）全部保持强档。

未达标 **MUST NOT** apply。

#### Scenario: 回测不达标即阻断
- **WHEN** 回测中 `#455` 被误降为弱档
- **THEN** 判为词表不合格，变更包不得 apply

### Requirement: 告警正文 SHALL 原样附命中片段且反引号 MUST 成对

告警与日志正文 SHALL 附上命中片段作为上下文（不少于命中措辞前后各 60 字）。

引文中的反引号 **MUST** 成对闭合；无法成对时 **MUST** 整体去除反引号。**MUST NOT** 输出反引号数为奇数的片段。

告警措辞 SHALL 为「请复核／建议改判」语义，**MUST NOT** 使用「应改为」「可以改判」一类暗示结论的措辞。

#### Scenario: 截断落在反引号中间
- **WHEN** 按长度截取的片段含奇数个反引号
- **THEN** 输出前去除该片段全部反引号，或向外扩展至成对为止

### Requirement: 告警 key SHALL 含命中措辞

告警节流 key SHALL 由「队列文件 ＋ 行号 ＋ 命中措辞」三者构成，节流窗口 SHALL 为 24 小时。

#### Scenario: 同一行换一条措辞
- **WHEN** `#455` 此前以「待 Shao Peishen」告警过、24 小时内改写为命中「留步」
- **THEN** 产生一个新 key 并再次告警，不被旧 key 的静默窗吞掉

### Requirement: 决策台账缺口 SHALL 被检出并给出可粘贴命令，MUST NOT 自动写入 §四

工具 SHALL 检出「§一 行状态列自陈在等 Shao Peishen 一次动作、且该行号未被任何 §四 行正文以 `#N` 提及」的行，并推送为告警。

该检测的扫描面 SHALL 独立于分诊候选：**MUST** 覆盖 `blocked` 状态的行（实测 16 条自陈行中 13 条为 `blocked`），**MUST NOT** 沿用 `_suggest_status_reclassification()` 的 open/partial 限制。

「已被 §四 覆盖」的判定 SHALL 含已结案的 §四 行——已拍板的 §四 行正是「他已看见并答过」的证据。

工具 **MUST NOT** 向任何队列写入任何内容，**MUST NOT** acquire 任何编辑锁。告警正文 SHALL 给出可直接粘贴的 `append-row --section 四` 命令草稿，由人执行。

#### Scenario: blocked 行的台账缺口被检出
- **WHEN** `#337` 状态为 `blocked`、自陈「待 Shao Peishen …」，且机制队列 §四 全表无任何行提及 `#337`
- **THEN** 该行进入台账缺口告警，正文含一条可粘贴的 `append-row --section 四` 草稿命令

#### Scenario: 已结案的 §四 行算作已覆盖
- **WHEN** `#96` 自陈「待 Shao Peishen …」，且 §四 某已拍板行正文提及 `#96`
- **THEN** 该行不进缺口清单

#### Scenario: 运行后队列零改动
- **WHEN** 本类检测在一轮 sweep 中完整跑完
- **THEN** 两份队列文件的内容逐字节不变，且本轮未产生任何编辑锁 acquire 记录

#### Scenario: 业务域缺口的跨文件登记须点明
- **WHEN** 缺口行来自业务场景队列（该文件不存在 §四 分区）
- **THEN** 草稿命令指向机制环境队列 §四，且告警正文明确指出这是一次跨文件登记、请人确认归属

### Requirement: 本类 SHALL 每轮回显且 MUST NOT 影响退出码

无论候选数与缺口数是否为零，本类 SHALL 每轮在 `sweep-commit.log` 打印一行结果，零命中 **MUST NOT** 省略。

本类的任何异常 **MUST** 被捕获并记入日志，**MUST NOT** 影响 sweep 主流程与本轮退出码。

#### Scenario: 零候选零缺口
- **WHEN** 本轮候选与缺口均为 0
- **THEN** 日志中仍出现本类的回显行

#### Scenario: 判据不可用不得判为零
- **WHEN** 取候选的子进程调用失败
- **THEN** 告警「判据不可用」，**MUST NOT** 据此在日志或推送中宣称本轮零候选

### Requirement: release 校验 ⑨ 的候选接线 SHALL 被退休

`工具-共享文档编辑锁.py` 的 release 校验 ⑨ **MUST NOT** 再调用 `_suggest_status_reclassification()`，`_mechanism_wip_over_cap_violations()` **MUST NOT** 再接收候选清单。

`_suggest_status_reclassification()`／`_render_reclassification_candidates()` 两函数与 `STALE_STATUS_PHRASES` **MUST** 原样保留在该模块，既有单测 **MUST** 保留。

#### Scenario: 超限拒绝文案不再含候选清单
- **WHEN** 机制类可动 WIP 超限、release 被拒绝
- **THEN** 拒绝文案含 WIP 计数与既有「两条出路」，不含改判候选清单

#### Scenario: 判据仍只有一份
- **WHEN** 检索全仓 `STALE_STATUS_PHRASES` 的定义处
- **THEN** 只在 `工具-共享文档编辑锁.py` 命中一处
