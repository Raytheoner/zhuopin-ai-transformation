## ADDED Requirements

### Requirement: setuptools `.pth` 纯路径形态须被判据覆盖
`工具-落库sweep.py` 第 6 类常驻告警（`_check_editable_install_targets`）SHALL 在扫描 `EDITABLE_FINDER_GLOB`（`__editable___*_finder.py`，import-finder 形态）的同时，并列扫描 `EDITABLE_PTH_GLOB`（`__editable__*.pth`）——setuptools `--config-settings editable_mode=compat` 只产出这种纯路径 `.pth`、不产出任何 finder 模块的形态。

对每份 `.pth` 文件，工具 MUST 按 CPython `site.py` 定义的 `.pth` 语义逐行分类（空行与 `#` 开头行忽略；`import ` 开头行只取模块名、不执行；其余非空行视为待加入 `sys.path` 的目录），且该分类过程 MUST NOT 执行文件中的任何一行（同既有 finder 形态判据"零执行、零导入"纪律，判据不得与被检对象共享失败模式）。

对分类出的纯路径行，工具 MUST 复用既有 `_classify_editable_target` 判定其形态（幽灵 import／断链／健康），判定结果的告警 key MUST 从 `.pth` 文件名切出、MUST 切掉版本号，且 MUST NOT 与既有 finder 形态判据共用同一份告警通道的写入语义——若两路径产生相同 key，MUST 合并两条详情文本而不是让后写入的一条覆盖先写入的一条。

#### Scenario: compat 形态指向 worktree 副本，判为幽灵 import
- **WHEN** 一份 `__editable__.<dist>-<ver>.pth` 文件内的纯路径行指向某个 `.claude/worktrees/...` 路径
- **THEN** 判据报该 key 为「幽灵import」，回显文案含该路径

#### Scenario: compat 形态目标路径不存在，判为断链
- **WHEN** `.pth` 纯路径行指向的目录在磁盘上不存在
- **THEN** 判据报该 key 为「断链」

#### Scenario: compat 形态指向主工作树，零告警但仍逐项回显
- **WHEN** `.pth` 纯路径行指向的目录存在且不在 worktree 段路径下
- **THEN** 不计入异常，但该 key 仍出现在逐条回显的日志中（同既有第 6 类告警"零告警不省略回显"纪律）

#### Scenario: `.pth` 与 finder 形态产生同一 key 时合并详情
- **WHEN** 一次扫描中 finder 形态判据与 `.pth` 形态判据对同一个 key 各自产出一条异常详情
- **THEN** 两条详情文本被合并保留在同一 key 下，后写入的一条 MUST NOT 覆盖先写入的一条

#### Scenario: `.pth` 解析过程零执行
- **WHEN** 判据读取一份内容含 `import os; os.system('...')` 等潜在副作用代码的 `.pth` 文件
- **THEN** 判据的分类结果不受该行实际执行与否影响——判据本身 MUST NOT 触发该行代码运行

### Requirement: 零命中的 compat 形态不得与"没有 editable 安装"外观相同
本判据的核心失效模式是：当 site-packages 内只有 compat 形态而现行实现只扫 finder glob 时，会打出「分发 0 个、异常 0 条」，与"本机没有任何 editable 安装"完全无法区分。本 Requirement 存在的目的即消除这一外观混淆。

工具 MUST 在日志中显式回显 `.pth` 扫描到的文件总数、其中判定异常的条数、以及判据不可用（解析失败）的条数——三个数字均为独立计数，MUST NOT 用其它计数字段相减推导得出（相减推导在两条扫描路径合流后会产生错误结果）。

#### Scenario: 本机确实零 compat 安装时如实回显零
- **WHEN** 本机 site-packages 内不存在任何 `__editable__*.pth` 文件
- **THEN** 日志显式打印"`.pth` 直挂 0 条"，而不是省略这一行

#### Scenario: 存在 compat 安装但恰好全部健康
- **WHEN** 本机存在若干 `.pth` 文件且全部指向健康路径
- **THEN** 日志显式打印"`.pth` 直挂 N 条：正常 N 条、指向异常 0 条"，逐条列出而非只报总数

### Requirement: hook 形态 `.pth` 引用的 finder 缺失须判为判据不可用
一份 `.pth` 文件内容若只含 `import <module>; <module>.install()` 一类 hook 引用（无纯路径行），工具 MUST 核对该 `<module>` 对应的 finder 文件是否存在于同一目录。

若该 finder 文件不存在，工具 MUST 将此情形计入既有 `EDITABLE_FORM_UNREADABLE`（判据不可用）标签，MUST NOT 计为"零异常"——此时 finder 扫描路径会因文件缺失而找不到该模块、判据看起来"干净"，而实际 import 该模块会产生 `ModuleNotFoundError`。

#### Scenario: hook 形态 `.pth` 存在但引用的 finder 文件已被删除
- **WHEN** 一份 `.pth` 文件内容为 `import __editable___x_finder; __editable___x_finder.install()`，而 `__editable___x_finder.py` 不在同一目录
- **THEN** 判据报该 key 为「判据不可用」，回显中说明是"引用的 finder 模块不存在"，而非静默跳过

#### Scenario: hook 形态 `.pth` 引用的 finder 正常存在
- **WHEN** hook 形态 `.pth` 引用的 finder 文件存在
- **THEN** 该 `.pth` 不重复计入 `.pth` 直挂的分发计数——它的实际指向已由 finder 那一路判据覆盖，避免同一份安装被计两次

### Requirement: 覆盖边界须被如实声明
本能力新增的判据 MUST 被如实限定为"发现 `.pth` 纯路径与 hook 引用缺失这两类装配时错误"，MUST NOT 被表述为覆盖了既有第 6 类告警文件头注释中已声明的边界之外的场景——具体地：MUST NOT 覆盖"装对了但代码内容漂移"（仍需目录哈希比对，不在本能力范围）；MUST NOT 覆盖非本解释器 site-packages 的其它 Python 安装；本判据仍然只能挂本机常驻任务，放入 CI 环境中运行永远不具备判定意义。

#### Scenario: 目录内容漂移不被本能力发现
- **WHEN** 某 editable 安装的 `.pth` 指向路径存在且不在 worktree 段下，但该目录内的源码已被后续修改到与预期不一致的状态
- **THEN** 本判据不对此判定异常——这类情形不在本能力声明的覆盖范围内
