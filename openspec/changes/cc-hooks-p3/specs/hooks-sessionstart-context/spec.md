## ADDED Requirements

### Requirement: SessionStart SHALL 注入本机双标时刻与仓库健康摘要

CC 会话开场时（`SessionStart` 事件），钩子 SHALL 打印：本机当前时刻的**本地与 UTC 双标**（形如 `2026-09-04 09:04 本地 / 2026-09-04 01:04 UTC`）、`git fsck --connectivity-only` 的结果摘要（无输出即"仓库连通性正常"；有输出即原文摘录前 5 行）、`origin/master..master` 与 `master..origin/master` 的双向提交计数。

该内容 MUST 通过 `hookSpecificOutput.additionalContext` 注入，不得只打印到 stdout（`additionalContext` 才会被带入模型上下文）。

#### Scenario: 正常仓库开场
- **WHEN** 会话开场，本地仓库与 `origin/master` 无分叉、`fsck` 无输出
- **THEN** 注入内容含本地/UTC 双标时刻、"仓库连通性正常"、`ahead=0 behind=0`

#### Scenario: 存在分叉
- **WHEN** `master` 领先 `origin/master` 2 个提交
- **THEN** 注入内容含 `ahead=2 behind=0`

### Requirement: SessionStart SHALL 摘要本线待领队列行

钩子 SHALL 读取 `1-转型规划/0-全景路线图/跨桌任务队列-机制环境.md`，摘取 §一中状态为 `[S:open]` 且正文不以 🛑 起首的前 5 行标题（编号 ＋ 任务列首句，每条截断至 60 字符），拼入注入内容。

队列文件不可读或解析失败时，MUST 输出"待领队列摘要不可用：<原因>"，MUST NOT 静默省略该段或假装"无待领任务"。

#### Scenario: 队列可读且有待领行
- **WHEN** 队列文件存在且含 3 条 `[S:open]` 非 🛑 行
- **THEN** 注入内容列出这 3 条的编号与截断标题

#### Scenario: 队列文件读取失败
- **WHEN** 队列文件路径不存在或读取抛异常
- **THEN** 注入内容含"待领队列摘要不可用：<原因>"，不包含任何假装成功的空列表

### Requirement: 钩子 SHALL fail-open 且自证在岗

任何步骤抛出异常 MUST 被捕获，钩子 MUST 以 `exit 0` 结束，不得阻塞会话启动；异常摘要 SHALL 写入 `reports/hooks-audit.jsonl` 一行（`sentinel="sessionstart-context"`, `verdict="error"`）。

每次运行（含正常与异常）SHALL 向 `reports/hooks-audit.jsonl` 追加一行 JSON（含时刻、`sentinel`、`verdict`、`sessionId`）。

#### Scenario: git 命令不可用
- **WHEN** `git` 不在 PATH 或子进程调用抛异常
- **THEN** 钩子 `exit 0`，注入内容含"仓库健康信息不可用：<原因>"，审计追加一行 `verdict=error`

#### Scenario: 正常运行也留痕
- **WHEN** 本次运行一切正常、无异常
- **THEN** `reports/hooks-audit.jsonl` 仍追加一行 `verdict=pass`
