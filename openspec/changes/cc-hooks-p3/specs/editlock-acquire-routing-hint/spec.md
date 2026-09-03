## ADDED Requirements

### Requirement: `acquire` 成功回显 SHALL 按触碰区关键词追加路由提示

`cmd_acquire`（含其 `_acquire_locked` 分支）在占锁成功后，SHALL 对 `--file` 解析后的绝对路径与 `--note` 原文做子串匹配，命中根 `CLAUDE.md` §4 路由表任一行的关键词时，追加打印一行「命中根 §4 路由表 → 先读 `.claude/rules/<对应文件>`」提示；同一次调用命中多条规则文件 MUST 去重、每份规则文件只提示一次。

关键词→规则文件映射 MUST 与根 `CLAUDE.md` §4 路由表逐行对应（见 design 决策点 4 的映射表），MUST NOT 另拟一套独立判据。

命中 0 条时 MUST NOT 打印任何路由提示行（沉默是合法输出，不是异常）。

#### Scenario: note 含跟进信关键词
- **WHEN** `acquire --who "Cowork-财务专线" --note "起草IT部#7跟进信"`
- **THEN** 输出含"→ 先读 `.claude/rules/跟进信与专员.md`"

#### Scenario: --file 指向场景目录
- **WHEN** `acquire --file "4-数字员工/采购部/SC7/CLAUDE.md" --who "CC" --note "改场景逻辑"`
- **THEN** 输出含"→ 先读 `.claude/rules/场景建造与合规.md`"

#### Scenario: 同时命中多条规则文件去重
- **WHEN** `--note` 同时含"跟进信"与"openspec"两个关键词
- **THEN** 输出恰好两行提示（跟进信与专员.md、场景建造与合规.md 各一次），不重复

#### Scenario: 默认队列编辑不触发自我指向
- **WHEN** `acquire` 未指定 `--file`（默认队列系统目标），`--note` 不含任何路由表关键词
- **THEN** 不输出任何路由提示行（队列与落库纪律不需要提示"去读队列与落库"）

### Requirement: 路由提示 SHALL 不改变 `acquire` 既有返回码与既有输出

新增提示 MUST 是追加输出，MUST NOT 改变函数既有的返回值（0/1）、既有打印内容的顺序与既有字段。

#### Scenario: 既有回归不受影响
- **WHEN** 对不命中任何路由关键词的既有测试用例重跑
- **THEN** 输出与改动前逐字节一致（新增逻辑对其零输出）
