## ADDED Requirements

### Requirement: 关键路径函数内不得出现宽异常捕获
`工具-落库sweep.py` SHALL 维护一份具名的「关键路径函数清单」常量——判据为「**该函数会自己写 git 历史**」（直接调用 `git commit`／`git push`／`git rebase`／`git merge`／`git reset`）。清单范围由 design 决策点⑤ 拍板。

清单内的函数体内 MUST NOT 出现 `except Exception`、`except BaseException` 或裸 `except`。

该约束 SHALL 由**单测中的静态守卫**执行（形态由 design 决策点⑥ 拍板），实现范式 MUST 沿用本文件已有的同款先例 `LocalOnlyCommitGuardTests::test_本类不做任何git写动作`（源码文本切片 ＋ `ast.parse` ＋ `ast.walk` 断言），MUST NOT 另起一套机制。

🔴 **本 Requirement 是回归守卫，不是缺陷修复**：propose 期 AST 全量扫描实测，清单候选内的 7 个函数（`_reconcile_with_origin_and_push`／`_push_any_unpushed_commits`／`_pop_reconcile_autostash`／`_commit_uncovered_queue_changes`／`_strike_off_rows`／`_process_normal_batch`／`_rerun_ledger`）**今天 except 分支数全部为 0**。本条锁的是"明天还成立"。

本 Requirement MUST NOT 用于改动任何既有的宽异常捕获——`main()` 的通用兜底（`#198(a)`）、告警／推送路径、动态加载降级路径、以及 `#136` 裁定原文要求的 fail-open，全部**维持现状**。

#### Scenario: 清单内函数新增宽捕获时守卫报红
- **WHEN** 在清单内任一函数体内加入 `except Exception`
- **THEN** 守卫单测失败，失败信息点名该函数与该 except 所在行

#### Scenario: 清单外函数的既有宽捕获不受影响
- **WHEN** 全量测试在未改动任何既有宽捕获的情况下运行
- **THEN** 守卫单测通过 —— 本条用于证明本 Requirement 不隐含"要求现存 31 处宽捕获全部收窄"

#### Scenario: 反向检查——写 git 历史的函数漏进清单时报出
- **WHEN** 新增一个会调用 `git commit`／`git push` 的函数但未把它登记进清单常量
- **THEN** 守卫单测失败并点名该函数 —— 本条防的是"清单本身漂移"，即判据看得见的范围随代码演进悄悄缩小

### Requirement: 兜底告警须点名失败发生在哪一个流水线步骤
`main()` SHALL 在进入每一个关键流水线步骤时更新一个"当前步骤"标记（起跑前置／队列孤儿改动提交／批次落库／遗留尾巴补销／台账重跑／收尾段对齐并推送／常驻状态检测）。

通用异常兜底产生的日志行与告警推送文案 MUST 点名该标记，使「本轮跑完了」与「本轮跑到第 N 步没做完」在日志与告警上不再同形。

理由（判据，非说明）：§四 `#126` 裁决另立的真风险原文为「sweep 说自己跑完了、实际某一步没做」——**"哪一步"决定了人工处置动作**（批次没提交 ⇒ 下一轮自动重试；提交了没推送 ⇒ 须人工核查本地提交），而现状的兜底文案只给异常类型与 traceback 尾行，要读者自行反推。

#### Scenario: 关键步骤抛异常时告警点名该步骤
- **WHEN** 收尾段对齐并推送这一步抛出未预期异常
- **THEN** 本轮日志与企微告警文案中出现该步骤名，退出码仍为既有的 `UNEXPECTED_EXIT_CODE`（本条只加信息、不改退出码语义）

#### Scenario: 正常收尾不产生步骤告警
- **WHEN** 本轮全部步骤正常结束
- **THEN** 不产生任何步骤相关的额外告警，日志格式与本变更前保持兼容

### Requirement: 守卫的覆盖边界须如实措辞
本守卫锁的是**源码形状**，不是运行时语义。

工具注释、单测文档字符串与本变更包的任何汇报措辞 MUST 表述为「**清单内函数不会出现宽捕获**」一类的受限断言，MUST NOT 表述为「关键路径此后不会被静默吞掉」一类的全覆盖断言。

已知不覆盖的形态 MUST 在守卫单测的文档字符串中逐条写明，至少包含：① 把关键逻辑挪进清单外的小函数再宽捕获；② `except OSError`／`except subprocess.SubprocessError` 一类**窄但同样吞掉真问题**的捕获；③ 用返回值而非异常表达失败、调用方不看返回值。

#### Scenario: 守卫单测自陈其覆盖边界
- **WHEN** 阅读该守卫单测的文档字符串
- **THEN** 其中逐条列出了上述三类已知不覆盖的形态
