# 【Codex】#648 单次 context_stopped 承接：D3 进程终止证据契约

## Why

本包仅修订单次 context_stopped 承接设计中的 D3。当前 `model_provider.py` 的 `process.json` 只有 `pid`、`started_at`，`stop_child()` 未保存 Windows `taskkill /T /F` 的执行结果和父进程的等待结果。因此 `context_stopped` 本身不足以证明旧模型进程树已终止，不能作为启动下一模型进程的凭据。

意图依据为本轮 Shao Peishen 的明确指令；外层驱动已核真实队列 §一 #648、intent 批准及 HEAD。本模型阶段不重复 Probe、不访问 ZHUOPIN_CODEX_STATE 私有目录、不用接力卡或历史队列快照替代实时核验。历史迁移 intent/design/plan 仅作背景，其实施授权不继承到本包。

本次退休哪一个既有守卫：不退休任何守卫。D3 补齐现有终止动作的证据和消费校验，尚不能证明可覆盖并替代现有 context、锁、授权、hook 或阶段闸；不新增常驻巡检。

## What Changes

- 定义生产 provider 如何把直接子进程身份、taskkill 原始结果及其后的 wait 观察写入现有证据载体。
- 定义外层 Workflow 对同一 attempt 的证据绑定、完整性、时序及 fail-closed 判定。
- 明确正例、失败例、异常清理与历史证据缺字段的验证要求。
- 只交付本包 proposal/design/tasks 及 OpenSpec 元数据；不实施，不承接旧 task，不 resume 旧 thread，不读取、修复或重放 v2 失败现场。

## Capabilities

### New Capabilities

无业务 capability。本包为内部工具证据契约设计，采用 `.openspec.yaml` 的 `schema: spec-driven`、`skip_specs: true`，不创建 delta specs。

### Modified Capabilities

无业务规格变更。只限定 D3 的证据生产与消费，不改 context 阈值、单次承接额度、其他设计决策或现有发布门禁。

## Impact

拟议实现影响 `0-学习与工具/codex-handoff/model_provider.py`、Workflow 证据消费接缝及相应测试；具体实现文件须在新 HEAD、设计 SHA256 和 allowed_paths 批准中逐项确定。本包不授权这些路径的修改。

依据现有 `process.json`、`result.json` 扩展字段，不引入新的自动生成文件名形态；故本设计无新增文件名的 `git check-ignore -v` 核验对象。若实现改为独立终止报告或新增日志文件，必须先修订设计并实测忽略规则，不得借本段放行。

全景规划与实施计划第七节的先验证、审计与门禁原则继续适用；不增加业务场景、不调整排期。生产部署程序仅引用 `.agents/skills/zhuopin-lan-closeout/SKILL.md` 正本，不复制部署纪律。

## 知识资产三问（强制，全景规划 §1.4 第 2 条）

1. 默会判断是“停止请求是否成功”和“证据是否足以允许下一次启动”的区分；显性规则为 design D3 的接受谓词、证据边界和反例，不采用模型自述判定。
2. 口径确认持有人为 Shao Peishen；backup 尚无本任务指定依据，不臆造实名或代理授权。进入实现前须确认实际复核责任人；本包不宣称双人制已落实。
3. 方法为 AI 起草、专家批改，并用隔离进程夹具反推失败判例；不得从 v2 失败现场补造成功证据。

## 验收与晋档条件（强制，四档口径）

- 当前仅设计产物，不构成档 1 mock 验证通过，更不构成档 2/3/4 晋档。拟议实现首先以档 1 隔离验证为目标。
- 下一阶段前提：外层 strict 成功并留原文及退出码；书面设计审通过；新 HEAD/hash/allowed_paths 逐项批准；隔离验证责任人确定。实现后再按现时 CI 矩阵逐项目验证、独立 review；生产和外发另闸。
- 风险型指标：缺失、错绑、失败终止证据的放行数必须为 0；正例证明生产写入链可被消费，不能只手写 JSON。基线及业务价值由 Shao Peishen 确认，不虚报节省工时。

## 本阶段交付边界

strict 由外层驱动运行，模型 sandbox 不运行 OpenSpec CLI。设计未经批准，tasks 全部是未来工作。暂不归档：尚待 strict、设计审及另行实现授权。
