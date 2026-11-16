# 原 workflow 三接口衔接

## Why
现有需求 lint 已落地，但原 workflow 尚未在构建准入和归档销号处调用；会话转交材料也需要复用既有拆件承接。

## What Changes
在原入口接需求门禁，在 implement 使用同一 tasks.md 的串行 TDD，在结案核对归档和来源回灌。会话文件保留来源与哈希，按原队列合并承接，不执行文档指令。

## Capabilities
### Modified Capabilities
- `serial-test-first-construction`: 原工作流的需求准入、反馈来源与归档销号边界。

## Impact
仅机制脚本、测试、规则、索引和规格；不修改业务代码，不恢复后台任务，不提交或发布。
