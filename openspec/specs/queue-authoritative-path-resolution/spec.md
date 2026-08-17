# queue-authoritative-path-resolution Specification

## Purpose

定义 `zhuopin_platform.shared_tools.queue_table` 承载的双文件路径解析权威实现，收拢队列 #313/#315 已实测发现的硬编码消费者，替代各消费者各自独立维护队列文件路径字面量。

## Requirements

### Requirement: 权威路径常量
`queue_table` 模块 SHALL 提供 `QUEUE_MECHANISM_PATH_REL` 与 `QUEUE_BUSINESS_PATH_REL` 两个仓库相对路径常量，取值分别为 `queue-dual-file-topology` 能力定义的两份物理文件路径。

#### Scenario: 常量值与拓扑定义一致
- **WHEN** 读取 `queue_table.QUEUE_MECHANISM_PATH_REL` 与 `queue_table.QUEUE_BUSINESS_PATH_REL`
- **THEN** 两者取值分别为 `1-转型规划/0-全景路线图/跨桌任务队列-机制环境.md` 与 `1-转型规划/0-全景路线图/跨桌任务队列-业务场景.md`

### Requirement: 按域解析路径
`queue_table` SHALL 提供 `resolve_queue_path(domain)` 函数，`domain` 取值 `"机"`/`"业"` 时返回对应物理文件的仓库相对路径；`domain` 取其它值时 MUST 抛出异常，不得静默返回默认路径。

#### Scenario: 非法域值 fail-loud
- **WHEN** 调用 `resolve_queue_path("其它")`
- **THEN** 抛出异常，不返回任何一份文件的路径

### Requirement: 遍历全部队列文件
`queue_table` SHALL 提供 `iter_queue_paths()` 函数，返回两份物理文件的仓库相对路径列表，供需要"读取全部队列内容"的消费者（如 sweep 起跑段扫描、台账生成、值周巡检）使用，替代此前假设"只有一份队列文件"的遍历逻辑。

#### Scenario: 消费者遍历两份文件
- **WHEN** 消费者调用 `iter_queue_paths()` 并逐一读取返回的路径
- **THEN** 两份物理文件的内容均被读到，不遗漏任一份

### Requirement: 已知硬编码消费者切换
以下既有硬编码队列文件路径变量 SHALL 改为从本模块读取或委托本模块解析：`工具-落库sweep.py::QUEUE_REL`（队列 #313 当时明确排除在收拢范围外的第 4 处遗留）、`工具-共享文档编辑锁.py::DEFAULT_TARGET`、`工具-队列查询.py::DEFAULT_TARGET`、`工具-文档台账生成.py::QUEUE_PATH`、`wecom-aibot-service/aibot_service/repo_paths.py::DEFAULT_QUEUE_RELATIVE_PATH`。

#### Scenario: sweep 不再使用独立硬编码路径
- **WHEN** 检查 `工具-落库sweep.py` 中队列文件路径的来源
- **THEN** 该路径经由 `queue_table.iter_queue_paths()` 或 `queue_table.resolve_queue_path()` 获得，不是模块内独立定义的字符串字面量
