## ADDED Requirements

### Requirement: 孤儿 worktree 扫描报告 SHALL 新增落后列

`工具-孤儿worktree扫描.py` 的报告 SHALL 为每个注册 worktree 增加一列，显示其 `HEAD` 落后 `master` 的**提交数**与其中**触碰 `CLAUDE.md` 的提交数**。

新增列 SHALL 是**纯增列**：MUST NOT 改动任何既有删除判定，MUST NOT 新增桶，MUST NOT 新增删除能力。

落后计数 MUST 使用 git 提交计数，MUST NOT 使用 mtime。

#### Scenario: 三个桶的归属不因新列改变
- **WHEN** 某 worktree 此前被归入「安全可删」桶，本变更后其落后列显示 644
- **THEN** 该 worktree 仍在「安全可删」桶内，归桶结果与本变更前完全一致

#### Scenario: 已对齐的 worktree 显示 0
- **WHEN** 某 worktree 的 `HEAD` 与 `master` 一致
- **THEN** 该行落后列显示 0

### Requirement: 取不到落后数时 MUST NOT 显示为 0

worktree 无有效 `HEAD`（如物理空壳、`HEAD` 为全零）或 git 查询失败时，该列 SHALL 显示可区分的「未取到」标记，MUST NOT 显示 0 或留空。

判定 worktree 身份 SHALL 依据「该目录内 `.git` 条目存在」与「在 `git worktree list --porcelain` 注册项内」两件事，MUST NOT 依据 `git -C <目录>` 的输出——对非注册目录执行 `git -C` 会静默向上找到主工作区的 `.git` 并返回主工作区的状态。

#### Scenario: 物理空壳不被记为已对齐
- **WHEN** 某注册项对应目录内无 `.git` 条目
- **THEN** 该行落后列显示「未取到」，MUST NOT 显示 0

#### Scenario: 不采信 `git -C` 对非注册目录的输出
- **WHEN** 对一个非注册目录执行 `git -C` 返回「分支=master、落后 0、脏 0」
- **THEN** 该输出不被采信为该目录的状态

### Requirement: 边界 SHALL 如实登记

报告 SHALL 保留既有边界披露：本工具只覆盖「经工具走」的路径，直接手敲 `git worktree remove` 仍无拦截。

本变更 MUST NOT 扩大该边界的表述，MUST NOT 表述为已闭合。

#### Scenario: 边界表述不被本变更改写
- **WHEN** 报告生成
- **THEN** 既有边界披露原样保留
