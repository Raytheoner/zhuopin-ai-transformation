## Why

采购域 v2.3 全景重排（2026-07-06，总线执行完成，见 `1-转型规划/0-全景路线图/采购域重排-移交全景路线图Task.md`）已将 SC3（供应商在途跟踪与绩效）、SC5（采购建议与供应商遴选）从采购目录中退役——**场景编号退役，功能与已合 master 的引擎不退役**。SC3 的答交可信度判据并入 SC8（客户订单交期智能承诺）作为内部子功能，SC5 的采购建议/供应商遴选并入新场景 SC7（库存优化建议）。移交单 §六风险1 将"已建引擎的归档/迁移"列为 CC 的小 openspec 任务，本变更即执行该项，避免退役场景的已验证代码（SC3 29 tests / SC5 41 tests，含黄金基准 35850/640000/675850）随场景目录一起失踪。

## What Changes

- 将 `4-数字员工/采购部/SC3-供应商在途跟踪与绩效/sc3_intransit/`（引擎 + agent，29 tests）迁移为 SC8 内部子模块 `sc8/answer_confidence_engine.py` + `sc8/answer_confidence.py`，作为 SC8 未来置信度 2→3 级化的判据源（本次只搬移，不接线到 SC8 现有承诺/置信度流水线——接线是"随 SC8 深化"的后续任务）。
- 新建场景目录 `4-数字员工/采购部/SC7-库存优化建议/`（此前不存在），承接 SC5 `sc5_purchase/`（引擎 + business_rules + agent，41 tests）迁移为 `sc7_inventory/`；**黄金基准 auto_total=35850 / review_total=640000 / grand_total=675850 原样保留，精确相等断言不放宽**。
- import 路径改名（不可避免的搬移代价，非功能重写）：`sc3_intransit.*` → `sc8.*`；`sc5_purchase.*` → `sc7_inventory.*`。
- 审计 `scenario` 标签更新：迁入部分的 audit 事件 `scenario` 字段由退役编号（"SC3"）改标存续场景（"SC8"），避免未来审计追溯指向一个已不存在的场景编号；SC5→SC7 部分同理（"SC5"→"SC7"）。计算逻辑、判定阈值、数据结构一律不变。
- 旧场景目录 `SC3-供应商在途跟踪与绩效/`、`SC5-采购建议与供应商遴选/` 只保留一个 `README.md` 指针文件（说明"功能已并入 SC8/SC7，2026-07-06 v2.3 重排"），其余源码/测试/pyproject/egg-info 移除；对应 Python 包从当前环境卸载（`pip uninstall`）。
- SC8、SC7 的 `CLAUDE.md` 按仓库六段式规范（定位/决策/底座/红线/时间线/依赖）更新（SC8）或新建（SC7）。
- **不变更**：`zhuopin_platform/agents/kit_engine.py`（底座件，O2/SC8/SC7 仍共同复用）、任何风险分级/DOS/采购量/供应商遴选/L1-L2 门禁阈值的计算逻辑。

## Capabilities

### New Capabilities

- `sc8-answer-confidence-engine`：SC8 内部子模块的算法层，供应商在途订单风险评估（沿用 SC3 引擎原始算法：剩余天数 + DOS 双触发三色分级），作为 SC8 交期承诺置信度未来 2→3 级化的判据来源；本次只落地计算逻辑，不接入 SC8 现有承诺/置信度主流程。
- `sc8-answer-confidence-agent`：SC8 内部子模块的入口层，调用上述算法并写审计留痕（`scenario="SC8"`）。
- `sc7-purchase-engine`：SC7（库存优化建议）场景内采购建议生成与供应商遴选的算法层（沿用 SC5 引擎原始算法：MOQ/MPQ 采购量计算、最低价已认证供应商遴选、R1 金额阈值/R2 无认证供应商门禁评估）；SC7 场景本身此前不存在，本变更是其第一批落地内容。
- `sc7-purchase-agent`：SC7 采购建议子能力的入口层，L1/L2 分桶写审计留痕（`scenario="SC7"`）。

### Modified Capabilities

（无——`sc5-kit-engine-platform` 描述的是 `zhuopin_platform/agents/kit_engine.py` 底座本体的需求，其条款文本本就未点名具体消费场景编号，SC5 退役、SC7 起步不改变该底座件的任何需求，故本次不产生该 capability 的 delta。）

### Removed Capabilities

- `sc3-intransit-engine` / `sc3-intransit-agent`：SC3 场景编号退役，能力原样迁移为 `sc8-answer-confidence-engine` / `sc8-answer-confidence-agent`（见上）。
- `sc5-purchase-engine` / `sc5-purchase-agent`：SC5 场景编号退役，能力原样迁移为 `sc7-purchase-engine` / `sc7-purchase-agent`（见上）。

> **实现说明**：openspec CLI 的 delta 机制不支持"REMOVE 掉一个 capability 的全部 requirement"（rebuild 后会因"spec 必须至少有一条 requirement"而拒绝写入），故本变更不为这 4 个退役 capability 提交 REMOVED delta，而是在 `openspec archive` 完成新增 capability 的写入后，直接删除 `openspec/specs/sc3-intransit-engine/`、`sc3-intransit-agent/`、`sc5-purchase-engine/`、`sc5-purchase-agent/` 四个目录（内容已 100% 由新 capability 承接，非静默丢弃）。

## Impact

- **受影响代码**：`4-数字员工/采购部/SC3-供应商在途跟踪与绩效/`（清空为 README 指针）、`4-数字员工/采购部/SC5-采购建议与供应商遴选/`（清空为 README 指针）、`4-数字员工/采购部/SC8-客户订单交期智能承诺/`（新增 `sc8/answer_confidence*.py` + 对应测试）、`4-数字员工/采购部/SC7-库存优化建议/`（全新场景工程）。
- **不受影响**：`zhuopin_platform/`（底座包零改动）、O2 场景（kit_engine 消费方不变）、SC8 既有承诺/置信度/保供看板功能（本次不接线）。
- **Python 环境**：`pip uninstall sc3-intransit-tracking sc5-purchase-recommendation`；新增 `pip install -e 4-数字员工/采购部/SC7-库存优化建议`。
- **依赖方**：全仓 grep 确认无其他场景 import `sc3_intransit` / `sc5_purchase`（仅各自 openspec 归档文档引用，历史快照不回溯改写）。

## 知识资产三问（强制，全景规划 §1.4 第 2 条）

- **本流程哪些判断是人脑默会经验？**：本变更不产生新的业务判断——迁移的两套引擎本身的默会知识（在途风险分级阈值 3/7 天 + DOS 5/10 天；采购审核 R1 金额 50 万阈值 + R2 认证供应商判定）已在原 SC3/SC5 变更包（2026-06-10 / 2026-07-02）显性化为代码常量，本次搬移不新增判断，也不重新征询业务专家。
- **由谁显性化？**：不适用（无新判断需要显性化）。原判据的持有人与 backup 仍是采购专员姚祖怡（+ 卓品智能 AI 转型项目团队 backup），迁移后判据归属随场景走（答交可信度归 SC8、采购建议归 SC7），持有人不变。
- **用什么方法提取？**：不适用（机械代码迁移，非知识提取任务）。

## 验收与晋档条件（四档口径）

- **本变更包交付后场景所处档位**：SC8 维持档 3（内部服务，保供看板 LAN 可用，`answer_confidence` 子模块新增但未接线，不改变 SC8 现有档位）；SC7 落地为档 1（mock 验证，沿用 SC5 CSV mock 数据与黄金基准，尚无真实 SRM/ERP 接入，也无新场景专属真实数据验证任务）。
- **晋下一档的条件**：
  - SC8 的 `answer_confidence` 子模块若要真正参与置信度 2→3 级化决策（即从"代码已迁入"到"实际影响 SC8 输出"），前提是 SC8 深化任务显式设计"如何加权"（本变更不做设计决策，只做代码归位）。
  - SC7 从档 1 → 档 2（真实数据跑通）的前提：接入真实 SRM（供应商价格/认证状态）+ 真实 ERP MRP 需求数据，与 SC5 原定前提一致（不因迁移而改变，见 SC5 原 CLAUDE.md §6）。
- **价值指标**：本变更不引入新价值指标（工时型/质量型/风险型基线不变）——迁移的价值是"避免已验证代码随场景编号退役而丢失"，不是新增业务价值；SC7/SC8 各自的价值指标仍以其场景原定 KPI（全景规划 §2.1.2 采购段）为准。
