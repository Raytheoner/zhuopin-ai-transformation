# Proposal: SC7 标准化批量数量证据入口

## Why

SC7 的共享 `Supplier` 输入当前以 `moq=1`、`mpq=1` 构造，而 #125/#403 已批准这两个字段采用料品级 ERP `purchaseBatchQty`。需要先证明标准化物料批量值可以无歧义地映射到既有 Supplier 记录，并能留下可复核的合成证据。此增量不假设 ERP 原始响应结构，不连接真实接口，也不改变生产采购建议。

## What Changes

- 新增 SC7 私有的标准化批量映射能力：从显式 synthetic 的 `Mapping[str, int]` 取值，复制 Supplier 新对象并令 `moq == mpq`。
- 增加独立 Stage 0 证据入口：必填 synthetic evaluator，固定记录 fixture/revision/source 标签，完整七字段快照和三层非自引用 hash；调用方提供独立空 JSONL sink，写后严格回读本次唯一事件并核链 ok/total=1，无法持久证明审计时不返回成功。
- 对缺 key、多余 key、非法 key/value、输入 Supplier 不可安全规范化等情况 fail-closed；不补默认值、不改调用方对象。
- K2 本次只列为后续依赖：复用现有历史交期统计器和统计定义，不修改 `lead_time_days=30`，不运行真实统计。

## Capabilities

### New Capabilities

- `sc7-batch-quantity-evidence`: 在隔离的合成证据入口中校验标准化料品批量映射、产生 Supplier 副本并持久记录审计证据。

### Modified Capabilities

- 无。既有 SC7 引擎、供应商规则、UI 和 K2 统计器本增量均不修改。

## Impact

- 候选新增代码：`4-数字员工/采购部/SC7-库存优化建议/sc7_inventory/batch_quantity.py`。
- 候选新增测试：`4-数字员工/采购部/SC7-库存优化建议/tests/test_batch_quantity.py`；实际路径和白名单须由独立实施计划批准。
- 不接入共享 `get_suppliers()`、`run_sc7()` 或旧运行时默认值；不触碰共享 `Supplier` 模型、采购公式、SC2 receipt connector 逻辑。
- 真实 ItemMaster query/parser、组织/权限、字段类型/单位/缺值含义仍等待 IT 证据及独立设计；K2 的真实数据、数据卫生和采购专业签认另设阶段。

## Approval Boundary

本 proposal 复用 #125/#403 已答业务口径，属于 SC7 深化增量；本件为待本人书面审阅的正式候选，不构成实施批准。Stage 0 代码建造只有在书面 design 批准且具体实施计划批准后才能开始。合成审计只证明结构映射和证据入口运行，不构成采购建议、真实 ERP 能力或专业签认。整体暂不归档，后续实际阶段按证据收口。
