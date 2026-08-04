# platform-repo-root-resolution Specification

## Purpose
TBD - created by archiving change retroactive-mechanism-specs. Update Purpose after archive.
## Requirements
### Requirement: 仓库根解析优先级——显式覆盖 > 动态 git 解析 > 调用方回落
`resolve_repo_root` SHALL 按以下优先级解析某个锚点路径实际所属的 git 仓库根：① 环境变量 `WECOM_AIBOT_REPO_ROOT` 非空时直接采用其值；② 否则以锚点路径所在目录为起点执行 `git -C <目录> rev-parse --show-toplevel` 动态解析；③ 前两者均不可用（环境变量未设置且 git 解析失败，如目录不在任何 git 工作树内）时才回落调用方传入的 `fallback` 值。MUST NOT 信任调用方仅凭 `__file__` 反推出的仓库根作为首选依据——同一份代码在不同 checkout（独立 worktree/主工作区）中执行时，`__file__` 反推会解出不同但都"合法"的错误结果。

#### Scenario: 环境变量覆盖优先生效
- **WHEN** 设置了 `WECOM_AIBOT_REPO_ROOT` 环境变量
- **THEN** `resolve_repo_root` 直接返回该环境变量指定的路径，不执行 git 解析

#### Scenario: git 解析成功时采用其结果
- **WHEN** 未设置覆盖环境变量，锚点路径确实位于某个 git 工作树内
- **THEN** `resolve_repo_root` 返回该工作树的实际根路径（`git rev-parse --show-toplevel` 的结果）

#### Scenario: 解析失败时回落 fallback
- **WHEN** 未设置覆盖环境变量，且锚点路径不在任何 git 工作树内（git 命令返回非 0）
- **THEN** `resolve_repo_root` 返回调用方传入的 `fallback` 路径

### Requirement: 常驻服务与一次性脚本共用同一套落点计算
`resolve_audit_path`、`resolve_pending_queue_appends_path`、`resolve_pending_queue_lock_appends_path` SHALL 均基于同一个已解析的 `repo_root` 计算各自的相对路径。当常驻服务（运行于独立 worktree checkout）与一次性脚本（运行于主工作区 checkout）均以同一个稳定锚点（如队列文件相对路径）调用 `resolve_repo_root` 时，MUST 解析到同一个仓库根，从而落盘到同一份物理文件，不再因两侧独立反推仓库根而导致审计留痕与暂存文件分裂成互不可见的两份。

#### Scenario: 常驻服务与一次性脚本解析到同一审计文件路径
- **WHEN** 常驻服务（独立 worktree checkout）与一次性脚本（主工作区 checkout）均以队列文件的相对路径为锚点调用 `resolve_audit_path`
- **THEN** 两者返回完全相同的绝对路径

