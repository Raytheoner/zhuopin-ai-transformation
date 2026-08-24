## Purpose

定义「本次运行该读哪一份 `.env`」的唯一实现契约——把当前手抄 9 份（A 家族，向上找最近的 `.env`）＋ 3 份（B 家族，硬数层级）的凭据定位收拢为一处，使「开发机主工作区」「开发机 linked worktree」「`.51` 扁平部署」三种布局由同一实现覆盖，且**前两者必然解出同一份凭据**。

🔴 **本 spec 的核心约束是一句反直觉的话：代码要就近、凭据要唯一。** `ensure_paths()`（`platform-path-bootstrap` spec）刻意取**最内层** marker，使每份 worktree 测自己的代码；本 spec 的方向相反——worktree 内那份 `.env` 副本正是队列 #354 的病灶。两者**不得**共用查找逻辑。

## ADDED Requirements

### Requirement: 三段锚定，按固定优先级

`.env` 的定位 SHALL 依次尝试三段，命中即停：① 环境变量 `ZP_ENV_FILE` 显式指定的文件；② monorepo 布局——从调用方文件向上找 `5-平台底座/zhuopin_platform` 标记，并将结果规范化到所有 linked worktree 共享的那个仓库根；③ 扁平部署布局——向上找其直接子目录含 `zhuopin_platform` 的祖先目录（部署根）。

MUST NOT 以「向上逐级查找最近的 `.env` 文件」作为任何一段的判据——**那是本 spec 要消灭的形态本身**：它把"凭据在哪"降格为"哪儿碰巧有个文件"，且失败时不产生任何信号。

#### Scenario: 主工作区内的场景脚本

- **WHEN** 调用方位于 `<repo>/4-数字员工/<域>/<场景>/scripts/` 且 `<repo>` 含标记
- **THEN** SHALL 解出 `<repo>/.env`

#### Scenario: linked worktree 内的同一脚本

- **WHEN** 调用方位于 `<repo>/.claude/worktrees/<name>/4-数字员工/<域>/<场景>/scripts/`，且该 worktree 内**同样存在**标记 `5-平台底座/zhuopin_platform`（linked worktree 是完整 checkout，标记必然在）
- **AND** 该 worktree 根下**存在**一份 `.env` 副本
- **THEN** SHALL 解出 `<repo>/.env`（主工作区那份），SHALL NOT 解出 worktree 内的副本

#### Scenario: 中途目录存在同名 `.env` 不得截胡

- **WHEN** 调用方位于 `<repo>/4-数字员工/采购部/SC1-供应商风险初筛/scripts/`，而 `SC1-供应商风险初筛/` 下存在一份 `.env`
- **THEN** 除非该作用域被显式指名（见「显式作用域」），SHALL 解出 `<repo>/.env`，SHALL NOT 因"它更近"而解出场景目录那份

#### Scenario: `.51` 扁平部署

- **WHEN** 调用方位于 `C:/<svc>/app/scripts/`，其任一祖先均不含 `5-平台底座/zhuopin_platform` 标记，而 `C:/<svc>/` 下存在 `zhuopin_platform` 子目录
- **THEN** SHALL 解出 `C:/<svc>/.env`

#### Scenario: 显式覆盖优先于一切

- **WHEN** `ZP_ENV_FILE` 已设置
- **THEN** SHALL 使用该文件，SHALL NOT 进行任何目录搜索，即便该文件不存在也 SHALL NOT 静默改用搜索结果（显式意图不得被自动行为推翻）

### Requirement: 无 git 环境优雅退化

第 ② 段的「规范化到共享仓库根」SHALL 通过 `git rev-parse --path-format=absolute --git-common-dir` 实现（与 `aibot_service/repo_paths.py::resolve_default_queue_anchor` 及 `工具-共享文档编辑锁.py::_resolve_repo_root` 同一语义，不另起实现）。当 `git` 不可用、调用方不在 git 工作树内、或该命令以非零码退出时，SHALL 回落到标记所在目录本身，SHALL NOT 抛出异常。

**理由**：`.51` 生产机上没有 git。把生产入口钉死在一个只有开发机才有的工具上，与队列 #345 的 A 形态（在扁平布局下无条件 raise）是同一个错误。

#### Scenario: 普通 clone（非 linked worktree）

- **WHEN** 仓库是一个普通 clone，不存在 linked worktree
- **THEN** `--git-common-dir` 的父目录 SHALL 等于该 clone 自身的根，解析结果与不做规范化时一致（**行为不变**）

#### Scenario: git 不可执行

- **WHEN** 环境中不存在可执行的 `git`
- **THEN** SHALL 使用标记所在目录，且 SHALL NOT 因此失败或告警——这在 `.51` 上是常态，不是异常

### Requirement: 只回报路径，绝不回显键值

解析与加载 SHALL 向调用方返回**实际命中的 `.env` 绝对路径**（未命中时返回 `None`），使入口可打印/写审计以回答「本次用了哪份凭据」。

🔴 返回值、日志、异常消息与审计记录中 MUST NOT 出现 `.env` 内任何键的**值**，无论截断、掩码还是哈希形式；键**名**可以出现。

#### Scenario: 入口回报命中路径

- **WHEN** 某入口调用加载并打印返回值
- **THEN** 输出 SHALL 包含 `.env` 的路径，且 SHALL NOT 包含该文件内任何键值

#### Scenario: 缺键报错消息

- **WHEN** 声明为必需的键未到位而抛出异常
- **THEN** 异常消息 SHALL 包含缺失的**键名**与已查找过的路径，SHALL NOT 包含任何已成功读到的键的值

### Requirement: 既有加载语义保持不变

将 `.env` 读入进程环境时 SHALL 保持现存 9 份实现的共同语义：以 `utf-8-sig` 解码；跳过空行与 `#` 开头行；按第一个 `=` 切分；剥去值两端空白与成对引号；**以「已存在的不覆盖」方式写入**（`setdefault` 语义）。

**理由**：`.51` 常驻服务与计划任务存在由进程环境直接注入凭据的情形，改为覆盖会让 `.env` 静默压过部署方的显式配置。

#### Scenario: 进程环境已有同名键

- **WHEN** 某键已存在于进程环境，且 `.env` 中也有该键
- **THEN** 进程环境中的原值 SHALL 保持不变

#### Scenario: 无键名的畸形行

- **WHEN** `.env` 中某非注释行不含 `=`
- **THEN** 该行 SHALL 被跳过（与现存实现一致），SHALL NOT 中止整个加载

### Requirement: CI 门禁拦住手抄形态

已跟踪的 `.py` 文件中，凡出现「向上逐级遍历祖先目录、探测其下 `.env` 是否存在」的内联形态，SHALL 被 lint 判为违规。判据 SHALL 锚定在语法结构（AST 节点或结构位置）而非裸子串匹配。

**理由**：裸子串会命中**讲解这个反范式的注释与 docstring 本身**，从而逼着后人删掉解释——同 `#355`（判据初版命中自己的说明散文）与 `#324`（`WIP豁免：` grep 得 10、真实豁免 0）两次已发生的教训。

#### Scenario: 新写的手抄形态被拦

- **WHEN** 某入口新增了一段向上找最近 `.env` 的内联代码
- **THEN** lint SHALL 报出该文件与判据说明

#### Scenario: 讲解该反范式的文字不得被误判

- **WHEN** 某文件的注释或 docstring 中描述了这一反范式（例如本变更包的说明、单测的夹具说明）
- **THEN** lint SHALL NOT 将其判为违规

#### Scenario: 过渡期不阻断

- **WHEN** 存量违规尚未清零且未传 `--enforce`
- **THEN** SHALL 打印告警并以退出码 0 结束——先确认清零、再关门，否则门禁上线第一天就是红的，只会被习惯性忽略
