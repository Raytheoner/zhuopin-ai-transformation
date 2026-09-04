## ADDED Requirements

### Requirement: `PreToolUse` SHALL 拦截 Read/Grep 直接命中队列真身或归档件

当 `PreToolUse` 事件的 `tool_name` 为 `Read` 且 `tool_input.file_path`，或 `tool_name` 为 `Grep` 且 `tool_input.path`，解析后的绝对路径精确等于两份队列真身之一，或位于队列目录下且文件名匹配 `跨桌任务队列-归档-*.md`，钩子 MUST `exit 2` 拒绝本次调用，反馈提示改用 `工具-队列查询.py` 的 `--row`/`--digest`/`--grep`。

判定 MUST 仅基于结构化目标字段的精确路径比较，MUST NOT 基于目录归属、内容扫描等模糊启发式。`Grep` 未提供 `path` 参数时 MUST NOT 判定为命中（记为"无法判定"而非"未违规"）。

#### Scenario: Read 精确命中机制环境真身
- **WHEN** `Read` 的 `file_path` 解析后等于机制环境队列文件绝对路径
- **THEN** `exit 2`，反馈含改用查询工具的提示

#### Scenario: Read 精确命中归档件
- **WHEN** `Read` 的 `file_path` 位于队列目录、文件名匹配归档命名规则
- **THEN** `exit 2`

#### Scenario: Grep 的 path 精确命中业务场景真身
- **WHEN** `Grep` 的 `path` 解析后等于业务场景队列文件绝对路径
- **THEN** `exit 2`

#### Scenario: Grep 的 path 为目录不拦
- **WHEN** `Grep` 的 `path` 是包含队列文件的目录本身，而非文件精确路径
- **THEN** 放行，`exit 0`

#### Scenario: Grep 未传 path 视为无法判定
- **WHEN** `Grep` 的 `tool_input` 不含 `path` 字段
- **THEN** 放行，`exit 0`，审计记录标记为"无法判定"而非"pass"

#### Scenario: 非受保护文件放行
- **WHEN** 目标路径不匹配任一受保护清单项
- **THEN** 放行，`exit 0`

### Requirement: `PreToolUse(Bash)` SHALL 在命令文本同时命中读命令名与目标文件名时拦截

当 `tool_name` 为 `Bash` 时，钩子 MUST 检查 `tool_input.command` 文本：若同时包含至少一个具名读命令词（`Get-Content`/`cat`/`grep`/`Select-String`，词边界匹配、大小写不敏感）与至少一个受保护目标的文件名（两份真身的文件名，或匹配归档命名正则的片段），MUST `exit 2` 拒绝。仅命中读命令词或仅命中文件名 MUST NOT 拒绝。

#### Scenario: cat 直击机制环境真身文件名
- **WHEN** `command` 含 `cat "跨桌任务队列-机制环境.md"`
- **THEN** `exit 2`

#### Scenario: grep 直击归档件文件名
- **WHEN** `command` 含 `grep <关键词> 跨桌任务队列-归档-202608.md`
- **THEN** `exit 2`

#### Scenario: 仅命中读命令词不拦
- **WHEN** `command` 为 `python -m pytest -k grep`（不含任何受保护文件名）
- **THEN** 放行，`exit 0`

#### Scenario: 仅命中文件名、命令非四个读命令之一不拦
- **WHEN** `command` 为 `git log -- 跨桌任务队列-机制环境.md`
- **THEN** 放行，`exit 0`

#### Scenario: 词边界防止子串误判
- **WHEN** `command` 含单词 `concatenate`（包含子串 `cat` 但非独立命令词）且同时含受保护文件名
- **THEN** 放行，`exit 0`（`cat` 判据须使用词边界匹配，不得按子串匹配）

### Requirement: 机制工具白名单 SHALL 优先于读命令+文件名判据

当 `Bash` 的 `command` 文本包含以下任一机制工具脚本路径子串时，MUST 无条件放行，不再检查读命令词+目标文件名组合：`工具-共享文档编辑锁.py`、`工具-队列查询.py`、`工具-落库sweep.py`、`工具-队列结构lint.py`。

#### Scenario: 队列查询工具自带 --grep 参数不被自身反噬
- **WHEN** `command` 为 `python 0-学习与工具/工具-队列查询.py --digest --grep <关键词> --file <归档件路径>`（字面同时含"grep"与归档文件名）
- **THEN** 因命中白名单而放行，`exit 0`

#### Scenario: 编辑锁工具调用放行
- **WHEN** `command` 调用 `工具-共享文档编辑锁.py` 的任意子命令
- **THEN** 放行，`exit 0`

#### Scenario: sweep 与队列结构 lint 工具调用放行
- **WHEN** `command` 调用 `工具-落库sweep.py` 或 `工具-队列结构lint.py`
- **THEN** 放行，`exit 0`

### Requirement: 钩子 SHALL fail-open 且留痕

解析 `tool_input` 异常或必要字段缺失 MUST 视为"无法判定"，MUST `exit 0` 放行，不得因钩子自身故障阻塞正常调用。每次触发（含放行、含拦截、含无法判定）SHALL 追加一行审计记录至 `reports/hooks-audit.jsonl`，含 `verdict`（`pass`/`violation`/`undetermined`/`error`）、`tool`、`sessionId`、`detail`。非 `Read`/`Grep`/`Bash` 的工具调用 MUST 防御性放行且不留痕。

#### Scenario: Bash 缺 command 字段
- **WHEN** `tool_name` 为 `Bash` 但 `tool_input` 不含 `command` 字段
- **THEN** `exit 0`，审计记录 `verdict=undetermined`

#### Scenario: 拦截留痕可核验
- **WHEN** 一次调用被 `exit 2` 拦截
- **THEN** `reports/hooks-audit.jsonl` 新增一行 `verdict=violation`，含钩子名 `pretooluse-queue-read-guard`

#### Scenario: 非管辖工具不留痕
- **WHEN** `tool_name` 为 `Write`（不在 `Read`/`Grep`/`Bash` 之列）
- **THEN** `exit 0`，且不追加审计记录
