# Workflow MVP Closure Implementation Plan

Goal: 打通阶段授权传递和可取证的本地构建闭环。Architecture: 复用现有driver/provider/state/guardian，通过四文件有界自举修复入口。Tech Stack: Python、pytest、Codex原生CLI/app-server。Spec: 本目录design.md。
执行采用executing-plans/TDD；Luna worker只改明确分配文件，不能覆盖其他人修改。独立review另用只读原生thread。

## 1. 授权传播与提示边界
- [ ] 1.1 在test_workflow_driver.py新增test_implementation_receives_bound_authorization，先证明proposal-only旧intent和新授权不能同时清楚传入；定点node-id留红色证据。
- [ ] 1.2 在driver把已验证context传到implement prompt，包含原文/哈希/路径与阶段时序，明确定点测试已授权、tasks.md不得改；保持原intent字节。
- [ ] 1.3 运行新增node-id及既有批准缺失/漂移/越界负例，全部应绿，缺绑定时模型调用计数为0。

## 2. 拒绝证据与模型路由
- [ ] 2.1 新增test_blocked_implementation_retains_native_reference和空diff/额外文件参数化用例，先红后绿；结果仍blocked，旧记录不回填，敏感日志不进入摘要。
- [ ] 2.2 在driver最小拒绝分支增加同次原因与原生定位；不放宽原pathguard准入，完整v5诊断按旧设计另由v5阶段产出。
- [ ] 2.3 在test_handoff.py新增CLI模型透传用例，在driver测试新增provider模型参数用例；先红后绿。为handoff advance提供--model并逐层传递，不改provider源码/全局配置。

## 3. 自举验证与审查
- [ ] 3.1 从codex-handoff子项目cwd运行隔离Python完整pytest；保存真实argv/cwd/exit/JUnit/stdout/stderr/HEAD；不根目录混跑。
- [ ] 3.2 独立只读review核四文件diff、授权时序、路径与模型参数、失败元数据；修复必须有回归用例。记录自举commit及哈希。

## 4. 原生单任务验收
- [ ] 4.1 从修复后的控制器入口先status核v5及冻结批准，确认未占用/HEAD一致/工作树干净；不直接读state。
- [ ] 4.2 使用原已封存批准文件与--model gpt-6-luna调用advance，实施v5两文件；失败先原生thread/read取证，同因最多两次，不清理或改写现场。
- [ ] 4.3 实施成功后连续advance运行受影响项目CI、另一原生thread只读review；缺证即保持失败，不拿自陈代替报告。
- [ ] 4.4 release仅生成待审发布请求；对候选整合HEAD重新核必要回归/原生链，旧报告不能覆盖新HEAD。

## 5. Guardian与交付
- [ ] 5.1 依已批准intent-deploy设计做人守入口、停点/恢复、单消费者/重复触发拒绝及off/unknown LAN留步联验，不改guardian代码、不新增调度器。
- [ ] 5.2 逐条给出MVP证据和未闭合项；队列登记沿专用工具/编辑锁；ff/.51/外发/L2分别等待实际对象授权。

暂不归档：全部实施和验收仍待本补充批准；本清单不修改v5封存tasks。
