# Tasks — queue-read-write-guards

> 建造授权已由队列 §一 `#381` 子项⑸ⓗ 原文（2026-09-04 追加）给出，本包 propose/design 与 apply 同批进行。
> 🔴 **§5 降指针、§4.1 settings.json 实际注册均不在本次范围**——超出本 CC session 的可控范围（`protected-paths.json` 拦截；降指针依赖真实验活）。

## 0. 前置

- [x] 0.1 `--digest --grep` 核两份队列触碰区无重叠（`工具-队列查询.py`／`工具-共享文档编辑锁.py`），命中的在办行（#448/#452/#454/#455/#464/#480/#482 等）逐一核实均为不同函数/不同关注面，或本身待领未开工，无真实并发冲突
- [x] 0.2 openspec propose：proposal.md／design.md／tasks.md／三份 spec delta

## 1. ⓗ1 `工具-队列查询.py --grep`（✅ 已完成）

- [x] 1.1 `--digest` 基础上新增 `_GREP_TASK_INDEX`/`_GREP_TOUCH_ZONE_INDEX` 常量与 `--grep` 参数
- [x] 1.2 过滤逻辑：任务列／触碰区列不区分大小写匹配，触碰区命中时附加提示片段
- [x] 1.3 误用 fail-loud：配 `--row` 使用、空白关键词均报错退出
- [x] 1.4 单测：`test_工具-队列查询.py::GrepModeTests`（9 条，含反引号内竖线的行——沿用既有 `queue_table.split_row_cells` 反引号感知切列，`--grep` 不引入第二套切列实现）＋ `DigestDualFileTests::test_grep_merges_hits_from_both_files`（双文件真实 git 仓库黑盒），单文件测试 46 passed
- [x] 1.5 验活：对真实生产队列跑 `--digest --grep 编辑锁`（命中 25/143 行）与错误路径三例（无 `--digest`／空白关键词／零命中），见收工报告

## 2. ⓗ3 编辑锁 release 校验族 ⑪ 行长上限（✅ 已完成）

- [x] 2.1 `ROW_LENGTH_CAP_BYTES`/`ROW_LENGTH_BLOCK_FROM`/`ROW_LENGTH_WAIVER_MARKER` 常量 ＋ `_row_length_warnings_and_violations`
- [x] 2.2 接入 `_validate_release_structure` 循环（§一/§四 各自列索引），docstring 补 ⑪ 段
- [x] 2.3 阻断日期切换（字符串字典序比较）＋ 逃生阀 `行长豁免：<理由>`
- [x] 2.4 单测：`test_工具-共享文档编辑锁.py::ReleaseStructuralValidationTests`（6 条：阈值内/告警/阻断/逃生阀/§四/历史行不追溯，含冻结 `datetime.now` 的子类桩）
- [x] 2.5 全量回归：`test_工具-共享文档编辑锁.py` 322 passed, 8 subtests passed

## 3. ⓗ2 `PreToolUse(Read|Grep|Bash)` 队列读侧门禁（✅ 建造+单测完成，⏳ 交付待人工注册）

- [x] 3.1 写 `0-学习与工具/hooks/hooks-pretooluse-queue-read-guard.ps1`
- [x] 3.2 Read/Grep 结构化字段精确匹配（含归档命名正则）
- [x] 3.3 Bash 命令文本"读命令词 + 目标文件名"双命中判据（词边界，四个具名动词）
- [x] 3.4 机制工具白名单（编辑锁／队列查询／sweep／队列结构 lint）
- [x] 3.5 fail-open + `reports/hooks-audit.jsonl` 留痕（复用 `hooks-common.ps1::Add-HooksAuditLine`，不新造日志形态）
- [x] 3.6 单测：`test_hooks-pretooluse-queue-read-guard.py`（26 条，含白名单撞车反例、词边界反例、Grep 目录/未传 path 反例，`ZHUOPIN_SENTINEL_REPO_ROOT` 隔离沙箱、不触碰生产 `reports/`）
- [x] 3.7 手动冒烟：对真实仓库路径跑 12 组 stdin JSON（Read×3／Grep×3／Bash×6），全部符合预期，审计行落在主仓 `reports/hooks-audit.jsonl`（`Get-SentinelRepoRoot` 按 `--git-common-dir` 解析，worktree 会话审计与主仓共享，同既有三枚 P3 钩子行为一致，已用 `git check-ignore -v` 确认该路径不产生 git 可见变更）
- [ ] 3.8 交付：`.claude/settings.json` `PreToolUse` 第二条目（matcher `Read|Grep|Bash`）注册片段 + 验活命令（随收口一并整理，见收工报告）

## 4. 收口

- [x] 4.1 `openspec validate --strict` 绿
- [x] 4.2 三处交付物（代码改动/单测结果/注册片段/验活命令）汇总进收工报告
- [ ] 4.3 §二 批次行登记（本次实际文件清单与 commit message）
- [ ] 4.4 §一 `#381` 子项⑸ⓗ 状态列回填三项完成情况，ⓗ2 注册前置条件如实注明
- [ ] 4.5 push 分支

## 5. 生产验活与降指针（🔴 不在本 session 范围，前置条件未满足）

- [ ] 5.1 Shao Peishen／Cowork 瘦身线完成 `.claude/settings.json` `PreToolUse` 第二条目人工注册
- [ ] 5.2 ⓗ2 在真实 session 里真实触发一次（含放行与拦截各一次），`reports/hooks-audit.jsonl` 贴对应行进验收记录；ⓗ1／ⓗ3 已在本包内对生产文件验活（见 §1.5／§2.5），无需二次验活
- [ ] 5.3 ⓗ3 阻断分支需等到本机本地日期达 2026-09-11 后，在真实超限行上验证一次真实拒绝（此前只有告警分支可验，已验）
- [ ] 5.4 `.claude/rules/队列与落库.md`「读侧禁通读」条目末句"机器守…待落地，落地前本条人守"降为一句判据＋指针（仅在 5.2/5.3 完成后执行）
- [ ] 5.5 `/opsx:archive queue-read-write-guards -y`
