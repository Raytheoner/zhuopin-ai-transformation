## Why

#261已批准先做恢复输入传递设计、设计另审。#658两次empty_changes尝试的prompt SHA完全相同，Guardian看护更正没有进入模型输入。需要正式入口的可审计追加输入，而不是改旧批准或盲重派。本包只形成设计，不实现。

本次不退休既有守卫：队列封存、批准绑定、K3、互斥、权限、模型、HEAD、CI/review均仍覆盖各自风险；新增输入送达校验不是这些保护的超集，不能替代它们。没有新增告警或调度；既有阶段闸消费失败。

## What Changes

- 定义外部RecoveryInputV1与独立批准件，绑定原失败attempt、设计、工作树与原实施批准。
- 在正式Workflow advance与Guardian中传递、核验、追加输入，公开request封存内容及摘要。
- 新恢复批使用独立fingerprint版本，旧v1/v2与拟议reasoning v3保持原意；不原位升级当前失败批。
- 一次launch消费、防竞争、错误拒绝及送达/遵循/交付分层验收。
- 独立机制实现、发布及原#658恢复分别审批；本轮只出设计。

## Capabilities

### New Capabilities
- `recovery-input-delivery`: 为已终结empty_changes的implement阶段追加获准的、更正用途输入并形成公开证据。

### Modified Capabilities
- 无现有capability spec改写；正式入口的可选接口变化及兼容边界见设计。

## Impact

候选范围仅codex-handoff的recovery_input、handoff、driver、state、provider、Guardian adapter/entry和对应测试。CLI handoff.py超出原#658的11路径，因此独立设计/实施计划与授权；不扩原批准。无业务/OEM数据或生产服务改动。完整设计正本：docs/superpowers/specs/2026-10-05-recovery-input-261-design.md。

## 知识资产三问（强制，全景规划 §1.4 第 2 条）

1. 默会判断包括输入送达与模型遵循的区别、旧封印不可改、批准来源与自由文本不是权限、恢复需验证执行版本。
2. 持有人Shao Peishen；backup沿用根CLAUDE已定决策代理，不赋予新增权限。具名backup为孙涛，仅适用原代理范围。
3. AI起草、人工批改，结合两次相同prompt失败案例反推；保留公开证据和原批准链。

## 验收与晋档条件（强制，四档口径）

1. 本包仅机制设计，目标实施档1 mock/fixture；本轮连mock测试也未执行。
2. 晋档须设计/实施审批、逐项目测试与独立review；正常发布/activation再逐项审批。真实恢复另审，不能据此称业务档2/3/4完成。
3. 风险型指标：输入身份漂移/未授权权限扩张零容忍，送达声明均需公开证据；未建立虚构效率基线。

## 自动伴生文件与忽略覆盖

本轮只有人工编写文档，不自动生成新文件。候选实施复用外部runtime下既有request.json/result.json和attempt记录，输入/批准件沿用外部审批目录，不新增仓库内自动文件名形态。因此本设计不需要新增gitignore；实施若改变产物位置或新增伴生文件，必须先列路径并实测git check-ignore，不得以本段豁免。
