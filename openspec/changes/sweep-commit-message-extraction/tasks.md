# tasks — sweep-commit-message-extraction

> 🔴 **design 未审前不得开跑**（场景固定流程第 3 步）。以下任务在 Shao Peishen 拍板决策点 1-5 之后按序执行。

## 1. 先写测试（红）

- [ ] 1.1 在 `0-学习与工具/test_工具-落库sweep.py` 新增 `ExtractCommitMessageTests`，覆盖 spec 第一条 Requirement 的 5 个场景：完全包裹 / 无反引号 / 反引号在正文中间 / 首尾是反引号但内部另有 / 多段行内代码
- [ ] 1.2 以本次真实事故为回归夹具：把 `B-0906_SC7env` 的原始 message 格原文作为输入，断言结果**不等于** `.env` 且包含 `docs(队列#354)` 与 `零回归` 两端
- [ ] 1.3 覆盖第二条 Requirement 的 3 个场景（空格 / 一对空反引号 / 空信息批次不阻断同轮其它批次）——第三个走 `SweepTestBase` 的端到端夹具，前两个走纯函数单测
- [ ] 1.4 覆盖第三条 Requirement：断言 `_resolve_batch_files` 对多路径文件清单的行为逐字不变（防"顺手合并两列解析"）
- [ ] 1.5 确认 1.1-1.4 全部**先红后绿**——先跑一次，确认失败原因正是待修语义，而不是夹具写错

## 2. 改实现（绿）

- [ ] 2.1 按 design 决策点 1(a) 重写 `_extract_commit_message`（三条规则，含 `count("\`") == 2` 判据）
- [ ] 2.2 按决策点 2(a) 在 `_process_normal_batch` 加空信息拒绝分支：不提交、不销行、写日志、不抛异常打断本轮其它批次
- [ ] 2.3 `--dry-run` 打印路径同步走新语义（5013 行调用点），保证 dry-run 与真跑显示一致
- [ ] 2.4 跑 `python -m pytest "0-学习与工具/test_工具-落库sweep.py" -q`，全绿且**无新增失败**

## 3. 退休那条人守（one-in-one-out）

- [ ] 3.1 改写 `0-学习与工具/skills源码/huijian-chaijian-patrol/SKILL.md:75` 的「不得裸反引号」：缩到「文件清单列」，并加一行指针说明 message 列内反引号已无特殊语义（决策点 5(a)）
- [ ] 3.2 确认另两条禁令（路径不得速记「同上」／清单内不得裸竖线）**逐字保留**

## 4. 回归与收口

- [ ] 4.1 全量跑 `python -m pytest "0-学习与工具" -q`，与 apply 前的基线逐条比对——**已知基线含 3 条既有失败**（`test_发企微` 8.3 短名、`test_工具-CLAUDE进度段lint` 两条，见 `1-转型规划/0-全景路线图/CI长期红-逐job根因取证-2026-09-06.md` §三），本包不修它们，只需确认**不新增**失败
- [ ] 4.2 真实验证：造一个 message 正文含反引号的 §二 批次，`--dry-run` 跑一轮，确认打印出的提交信息是整格原文而非首个跨度
- [ ] 4.3 `openspec validate sweep-commit-message-extraction --strict` 通过
- [ ] 4.4 队列 `#398` ⑹ 回写：apply 结果 ＋ commit ＋ 「修好后它会在什么情况下发出信号」的说明（＝空信息批次留待处理并见日志；截断已不可能发生，故无需告警）
- [ ] 4.5 `/opsx:archive sweep-commit-message-extraction -y`（tasks 全 [x] 后当场归档，不得跨 session）

## 明确不做

- 不追改历史 11 条被截断的 commit（决策点 4(a)）
- 不在写入侧加 message 形态守卫（决策点 3(a)）
- 不动 `#398` 第 ⑸ 处 `_strike_off_rows()` 的 release 返回码问题（另行立项）
