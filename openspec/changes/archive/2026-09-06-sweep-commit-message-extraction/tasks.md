# tasks — sweep-commit-message-extraction

> ✅ **design 已审**：Shao Peishen 2026-09-06 答「A 全批」——5 个决策点全部按推荐项通过。以下按序执行。

## 1. 先写测试（红）

- [x] 1.1 在 `0-学习与工具/test_工具-落库sweep.py` 新增 `ExtractCommitMessageTests`，覆盖 spec 第一条 Requirement 的 5 个场景：完全包裹 / 无反引号 / 反引号在正文中间 / 首尾是反引号但内部另有 / 多段行内代码
- [x] 1.2 以本次真实事故为回归夹具：把 `B-0906_SC7env` 的原始 message 格原文作为输入，断言结果**不等于** `.env` 且包含 `docs(队列#354)` 与 `零回归` 两端
- [x] 1.3 覆盖第二条 Requirement 的 3 个场景（空格 / 一对空反引号 / 空信息批次不阻断同轮其它批次）——第三个＝新增 `EmptyCommitMessageEndToEndTests`（走 `SweepTestBase` 真实 git + 真实 CLI），前两个走纯函数单测
- [x] 1.4 覆盖第三条 Requirement：新增 `ExtractCommitMessageNonRegressionTests`，断言 `_resolve_batch_files` 对多路径文件清单的行为逐字不变（防"顺手合并两列解析"）
- [x] 1.5 **先红后绿已实证**：改实现前跑 `ExtractCommitMessageTests` ＝ **7 failed, 4 passed**，且真实事故夹具精确复现出 `got == '.env'`——失败原因正是待修语义。端到端那条另做了一次**停用守卫复验**（把守卫条件临时改为恒假）：`git commit -m ''` 退出码 1 并**拖垮整轮**（同轮合法批次也没落库），与决策点 2 的预判一致，复验后立即还原

## 2. 改实现（绿）

- [x] 2.1 按 design 决策点 1(a) 重写 `_extract_commit_message`（三条规则，含 ``count("`") == 2`` 判据），并在 docstring 里留下取证基线与"不得与 `_resolve_batch_files` 合并"的边界
- [x] 2.2 按决策点 2(a) 加空信息拒绝分支：置于批次分发循环内（与既有"文件清单解析不出片段"同一处置形态与同一位置 `continue`，不进 `touched_paths`），不提交、不销行、写日志、不打断同轮其它批次
- [x] 2.3 `--dry-run` 打印路径同步走新语义——`_process_normal_batch` 的 dry-run 分支与真跑共用同一个 `_extract_commit_message`，且空信息在进入该函数前就被拦下并 `[dry-run]` 打印
- [x] 2.4 `python -m pytest "0-学习与工具/test_工具-落库sweep.py" -q` 全绿且无新增失败

## 3. 退休那条人守（one-in-one-out）

- [x] 3.1 改写 `0-学习与工具/skills源码/huijian-chaijian-patrol/SKILL.md` 的「不得裸反引号」：三条禁令收为两条并明写只约束「文件清单」列，加 🔻 退休说明（message 列内反引号已无特殊语义）
- [x] 3.2 另两条禁令（路径不得速记「同上」／清单内不得裸竖线）逐字保留，仅补「均只约束文件清单列」的限定

## 4. 回归与收口

- [x] 4.1 与 apply 前基线逐条比对——**已知基线含 3 条既有失败**（`test_发企微` 8.3 短名、`test_工具-CLAUDE进度段lint` 两条，见 `1-转型规划/0-全景路线图/CI长期红-逐job根因取证-2026-09-06.md` §三），本包不修它们，只确认**不新增**失败
- [x] 4.2 真实验证：以形态 C 的 message 格走真实 `_process_normal_batch(dry_run=True)`，打印出的提交信息是**整格原文**（`docs(队列#354): 判据二 \`.env\` 锚定存量清零回写 —— SC7 \`leadtime_median.py\` 收拢进 \`env_anchor.load_env\``）而非首个跨度 `.env`
- [x] 4.3 `openspec validate sweep-commit-message-extraction --strict` 通过
- [x] 4.4 队列 `#398` ⑹ 回写：apply 结果 ＋ commit ＋ 「修好后它会在什么情况下发出信号」＝空信息批次留待处理并在日志出现「提交信息为空」；截断已不可能发生，故不新增告警
- [x] 4.5 `openspec archive sweep-commit-message-extraction -y`（tasks 全 [x] 后当场归档，不跨 session）

## 明确不做

- 不追改历史 11 条被截断的 commit（决策点 4(a)）
- 不在写入侧加 message 形态守卫（决策点 3(a)）
- 不动 `#398` 第 ⑸ 处 `_strike_off_rows()` 的 release 返回码问题（另行立项）
