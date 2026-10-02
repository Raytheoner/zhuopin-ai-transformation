## Purpose

确保项目任务驱动构建过程中，用户已经批准的阶段权限完整到达执行模型，失败能够定位到原生会话，并以同一版本的真实证据验证从任务到发布准备的最小闭环。

## ADDED Requirements

### Requirement: Bound stage authorization reaches the implementing model
The workflow SHALL pass the verified current design authorization text and binding to the implementation model without mutating historical intent or widening allowed paths.

#### Scenario: Proposal-only intent followed by explicit implementation approval
- **WHEN** a task has historical proposal-only intent and later verified implementation approval
- **THEN** the model input includes the later approval verbatim, its binding, and explicit stage ordering, including authorized targeted tests

#### Scenario: Missing or changed authorization
- **WHEN** the authorization is missing, changed, or bound to another design
- **THEN** the workflow blocks before model execution

### Requirement: Rejected implementation remains diagnosable
The workflow SHALL distinguish empty changes from unauthorized paths and retain the originating native thread reference on rejected implementation outcomes without exposing private raw logs.

#### Scenario: Model produces no changes
- **WHEN** an implementation produces an empty change set
- **THEN** the task stays blocked with an empty_changes category and its available native thread reference

### Requirement: Explicit per-invocation model choice
The workflow SHALL support an explicit model on one advance invocation without modifying global defaults or silently substituting another model.

#### Scenario: Luna invocation
- **WHEN** an authorized advance selects gpt-6-luna
- **THEN** the provider receives that model as a discrete argument and records the invocation

### Requirement: MVP claims require a native chain and the human-started entry
The workflow SHALL require native implementation, project CI, independent review, release preparation and the human-started guardian connection evidence before claiming the task-driven MVP complete.

#### Scenario: Local chain passes but guardian connection is unverified
- **WHEN** only the single-task native chain is verified
- **THEN** report only that milestone and retain the overall MVP as incomplete

#### Scenario: Release authorization absent
- **WHEN** release preparation succeeds without item-specific fast-forward or production approval
- **THEN** preserve the release request and perform no merge, production deployment or external send
