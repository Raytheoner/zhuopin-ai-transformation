# 三个接口的最小接线

批准依据：2026-11-14 本会话 Shao Peishen 明示按已推荐方案落地；本文件是同范围细化。

## 1. 准入
`handoff.prepare` 先核 INDEX 的 task_id、feature/refinement、active_mvp、主规格和测试及容量；新 proposal 输出后调用现有需求 lint 与 OpenSpec strict。共享 INDEX 由原持锁入队方更新，模型阶段只读。旧已批准阶段不重建、不删除；新开始的 proposal 不能使用 skip_specs 绕过 delta。

## 2. 实现
原 implement 中使用同一 tasks.md，明确 executing-plans＋test-driven-development：切片先测后写，受影响项目完整 pytest，失败停依赖动作。保留短 design、已批准路径、独审/安全冻结合同和精确 HEAD 绑定。无逐项 git 授权停在候选，不用默认提交来推进状态。

## 3. 来源与结案
企微回件继续原链；会话转交文档经本地归档入口保留原文件、SHA256、转交来源和场景，仅附到已有队列行。重复内容复用归档；不推断作者或批准。原拆件方列事实、已有决策及其批准来源、待裁决事项、使用反馈，业务构建继续绑定原行/包。无前信关联不改跟进 README；有关联也只有回灌消化完成后按原闸结案。

结案入口先核 N/N、无观察/外部未闭、对应 spec 已同步和真实测试证据，再调用原 OpenSpec archive；确认 archive 目录和 INDEX 后原队列工具销对应行，并留来源回指。归档失败不销号。归档改变 HEAD 时旧证据仍只证明旧 HEAD，需按原 workflow 重验；不伪造 release_ready 或部署完成。

## 验证
复用原回件样本定义和 workflow fixture，在临时仓库做 refinement 的回灌、原队列入队/认领、原 driver 构建、OpenSpec 归档、销号；所有状态修改限定 fixture。真实 SC7 文档本轮只读核对承接需求。
