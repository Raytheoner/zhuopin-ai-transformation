# 批处理测试迁移对应表

现时正本仍为 `0-学习与工具/test_工具-opener批处理执行v2.py`。旧套件由 Git 保存；其中存在临时 PATH 的源端桩、真实主仓 worktree add/remove/prune/branch-D、直接写主仓和源端权限参数断言。本迁移用独立临时 Git 仓库重建行为验证，不运行或保留这些危险夹具执行路径。

原新增 `codex-handoff/tests/test_batch_codex.py` 的30项已纳入原入口并移除重复副本，避免发现两次/执行两次。Linux仍按原套件平台条件跳过，Windows实际运行；没有因失败而加skip。

| 原关注点 | 现时用例/判据 | 说明 |
|---|---|---|
| 解析/dry-run/退出码 | TestBatchValidation + TestBatchCodex | dry-run零进程与零工作树，结果机读 |
| 会话身份/resume | TestNativeBatchIntegration + TestBatchCodex | 原自行生成CLI session_id合同退役；source_id与原生thread分离，补问同thread；两条op唯一身份 |
| Detach/含空格/PS5.1 | TestDetachPaths + TestNativeBatchIntegration | 真实后台PowerShell和旧shell入口，假provider |
| 完成/缺哨兵/补问/超时/失败停泳道 | TestRetainedBatchBehavior + TestBatchValidation | 非零带DONE拒绝，最多一次补问，PARTIAL/NO-SENTINEL分开 |
| FullAuto的旧危险权限开关 | provider TestProvider 安全argv/不受限sandbox拒绝 | 旧acceptEdits/skip-permissions断言退役，不能转成Codex旁路 |
| 模型旧别名与生成器互测 | TestBatchValidation + TestNativeOpener + TestNativeBatchIntegration + provider TestModelRoutes | sonnet/opus合同退役并拒绝；inherit/routine/design明确路由 |
| worktree创建/必需/非法名称 | TestBatchCodex + TestBatchValidation | 临时仓中实际建WT；缺隔离或路径非法不启动模型 |
| 主仓泄漏/旁观者写入 | TestRetainedBatchBehavior | 归因后FAIL并存patch，保留原文件；旁观者不误罚 |
| reports残留回收 | TestRetainedBatchBehavior | 捞回副本，原工作树和原文件保留 |
|150k/250k、软线0与续棒 | TestRetainedBatchBehavior + provider TestContextGuard/TestReviewRegressions | 假进程真实终止/续棒，无补问；原生计量另在provider验证 |
| 并发限额 | TestBatchValidation | 三泳道两并发，实际任务时间区间核最大并发 |

错峰间隔和补问/软线守卫变异试验已补，7项含受影响核心测试通过，见 batch-canonical-guards.txt。队列白名单相关集成仍需补；未写成通过。Windows注册调度、hook与真实模型交付链不属于本隔离套件，仍待端到端验收。
