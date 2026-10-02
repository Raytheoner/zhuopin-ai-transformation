# Codex workflow MVP 收口补充提案

## Why

#648 v5 已获设计批准与实施授权，但原生 implement thread 01a0effb-6b9c-7d82-abca-32723b19ad7c 明确因输入同时包含 proposal-only 禁令与实施指令而停下。通过 Codex app-server thread/list、thread/read 取得原生末答；项目阶段 status 只保留泛化路径错误。新增提案并不能修复运行中的驱动。需要一次有界自举修复，再用原阶段接口完成同一任务的真实链路。

本次不退休权限、路径、独立review或CI守卫：这些约束仍必要；退休的是“空改动也只能报越权”这一不区分原因的诊断形式，保留 legacy reason 兼容同时补原因码。

## What Changes

1. 向实施模型传递已校验的后续授权正文及task/design/hash/paths绑定，原始intent与旧证据不改。
2. 实施拒绝保留原生thread ID、工具失败计数、attempt/evidence定位及有限原因分类，不把模型末答当成功。
3. 单次 Workflow advance 增加可选 --model，显式选择 gpt-6-luna并传到现有provider；不改全局设置。
4. 在独立工作树先做小范围引擎自举修复；后续仍经项目阶段接口推进，不手改运行状态。已有v5授权继续有效，不重新生成v5 proposal。
5. MVP验收为人守启动、会话内阶段推进、原生实施→受影响项目CI→独立只读review→release-prep、拒绝及停点恢复。生产发布单列。

## Capabilities

### New Capabilities
- `workflow-stage-authorization-delivery`: 阶段授权传递、失败定位、单次模型选择与真实链路验收。

### Modified Capabilities
无其他能力口径修改。

## Impact

代码仅四文件：0-学习与工具/codex-handoff/workflow_driver.py、handoff.py、tests/test_workflow_driver.py、tests/test_handoff.py。本提案目录为设计与计划产物。v5原封存包和旧任务不改；主仓、全局配置、provider/state/guardian实现、生产服务不在本次修复范围。
本变更不新增工具自动生成文件名形态：复用既有request/result/attempt字段与外部授权证据，测试使用已有临时目录fixture。人工验收摘要另置Temp，不新增锁/日志协议。

## 知识资产三问（强制，全景规划 §1.4 第 2 条）

默会判断是阶段授权时序、失败证据粒度和MVP完成尺度；由Shao Peishen已作裁定，Codex依据真实失败案例显性化；方法为历史案例反推与专家批改。本包沿用#648 pathguard专项no-backup，不要求或任命backup，不改变通用双人制，独立只读review保留。

## 验收与晋档条件（强制，四档口径）

本包为机制验证档1，不代表业务真实数据或生产服务晋档。晋后续实际运行需最终候选源码真实链路证据、逐项ff授权及相应生产前置。质量指标为同一任务完整证据链、零越权文件、授权不漂移、拒绝可解释；不承诺未测量工时百分比。
