## Purpose

跟进信 README 主表与归档件 SHALL 与两份跨桌任务队列真身受同一套读侧禁通读门禁保护，防止对其执行整文件 Read/Grep 造成单次调用吞掉过大上下文。

## ADDED Requirements

### Requirement: README 主表与归档件纳入保护目标
`hooks-pretooluse-queue-read-guard.ps1` 的保护目标清单 SHALL 扩展为包含跟进信 README 主表精确路径与 `README-归档-*.md` 归档件（按父目录+文件名正则匹配，同队列归档件判据形式），命中时行为与现有两份队列真身一致。

#### Scenario: 直接 Read README 主表被拦截
- **WHEN** 任一会话尝试对 README 主表路径执行 `Read` 全文
- **THEN** 调用被拒绝，提示改用登记 CLI／跟进信 README 查询工具

#### Scenario: 对归档件执行 Grep 被拦截
- **WHEN** 任一会话尝试对某个 `README-归档-YYYYMM.md` 执行整文件 `Grep`
- **THEN** 调用被拒绝，提示改用查询工具的 `--digest --file <归档件>` 用法

#### Scenario: 机制工具白名单整条放行
- **WHEN** 触发保护目标匹配的调用来自登记 CLI／`工具-跟进信README查询.py`／`工具-共享文档编辑锁.py`／sweep／lint 等既有机制工具白名单
- **THEN** 调用整条放行，不受本门禁拦截

### Requirement: 拦截事件留痕审计
每一次因命中 README 保护目标而被拒绝的调用 SHALL 写入一条审计事件到 `reports/hooks-audit.jsonl`，包含目标路径、调用工具名与拒绝原因。

#### Scenario: 拦截事件写入审计
- **WHEN** 一次对 README 主表或归档件的直接 Read/Grep/Bash 调用被本门禁拒绝
- **THEN** `reports/hooks-audit.jsonl` 新增一条对应的拒绝事件记录
