## Context

本包为§四#261新增恢复输入机制的设计候选，原#658 task/设计/11路径实施批准继续有效；B-1005失败批原位保留。本包不改变原封存OpenSpec包。

## Decisions

唯一设计正本为主仓 `docs/superpowers/specs/2026-10-05-recovery-input-261-design.md`，通过其SHA与本包一起审阅。该文完整规定外部输入/批准schema、接口、生命周期、恢复指纹v4与reasoning v3兼容、一次launch消费、失败矩阵、有限范围、发布前置与验收。

推荐外部已批准恢复输入经正式advance/Guardian入口进入prompt，不改旧批准或从watch自动注入。不带输入的历史调用与fingerprint保持不变。

## Risks / Trade-offs

增加CLI/provider/Guardian接缝；原#658执行版本不一定能直接读取新机制，因此发布/执行版本绑定必须另核，不能加载替代runner。输入送达仍无法保证模型遵循。逐项复核、版本漂移拒绝及后续实际人审继续。

## Migration Plan

设计审→独立机制实施计划/实施审→隔离建造/逐项目CI/review→ff/入口切换另审→原批退役另审→新恢复件与单次派发另审。当前批不退役、不重派。

## Open Questions

执行版本与原source封存兼容在实施准备定向核验，若不能兼容须先提正式迁移设计；本候选不授予迁移权限。具体node-id/签名与逐文件实现顺序留给设计获批后的实施计划。
