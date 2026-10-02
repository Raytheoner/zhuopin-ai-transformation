# 子任务 Luna 路由补充（用户新指令，2026-09-30）

用户原文：所有Session确保所有子任务使用luna模型。

该新指令覆盖此前设计的 Guardian 继承 Astra 例外，以及四文件自举 D4 的未指定时继承默认约定。两个已批准 design.md 原字节及哈希保留，不回改历史批准。

实施仍限原已授权 workflow_driver.py 与 tests/test_workflow_driver.py：_run_model 在未指定模型时显式传 gpt-6-luna；非 Luna 或 inherit 别名在调用 provider 前拒绝。Guardian 的实际派生模型经同一 driver 自动适用，无需增加 Guardian 参数、不改 provider、全局父会话模型、生产消费者开关或调度状态。CLI 显式 Luna 继续有效。所有子代理与子会话也必须显式选 Luna。

验证：临时回归反例已在旧实现产生 1 failed（未传 model，50.58s）。修改默认路由持久测试，新增非 Luna 四个拒绝输入；执行模型路由及超时相关回归，独立只读审查。先前完整回归 473 passed/4 skipped（full-v3）覆盖首次timeout保锁修复，但不冒称覆盖本补充后的最终代码；最终候选 CI 仍需全套复核。

计划：实现与定点回归→独立审查→入口说明同步→最终原生 Guardian 链逐阶段核 requested_model/actual_model；若真实回执模型不为 Luna，停止依赖步骤并保留证据。不静默回退。
