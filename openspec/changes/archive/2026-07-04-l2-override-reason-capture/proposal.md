# 变更提案：L2 改判原因采集（l2-override-reason-capture）

> 轻量通道首例（design 以要点清单代替全文，2026-07-04 纠正方案 §四，Paul 已批）

## 需求背景

**来源**：《默会知识瓶颈对照与全方位纠正方案-2026-07-04》§三.4——L2 人工门禁是知识采集入口，改判原因须记录，按月汇总进判例库，驱动规则/阈值迭代升版。

**现状**：L2 改判路径（SC8 approve、FI1 超阈人工结案、QD-B 未来 L2、保供案例处置中心）audit 事件均无 `override_reason` 字段，改判动机不可查，知识流失。

## 方案要点（设计替代 design.md）

1. **平台底座层（`AuditEvent`）**：新增可选字段 `override_reason: str = ""`，位于现有 `error` 字段之前。字段语义：L2 改判时的人工决策依据（自由文本），不填时为空字符串（不影响现有代码）。

2. **SC8 消费方（`pending_queue.approve()`）**：签名加 `override_reason: str = ""`，写入 approve 成功的 audit 事件 `decision["override_reason"]`；approval_denied 事件无需加（未放行，无改判）。

3. **FI1 消费方（`fi1/reconcile_engine.py` 超阈分支）**：预留参数接口，空字符串默认传递（FI1 真实验证前不阻塞）。

4. **不改逻辑**：纯字段透传，不改任何判定流程、门禁规则、幂等保证，不影响对客外发闸门。

5. **月度可导出判例清单**：`audit.query_by(scenario="SC8", action="approve_sent")` 按月过滤 `override_reason` 非空项，输出 `rule_id / decision / override_reason / evaluator` 四列。此步骤为 ops 侧导出操作，本变更包只提供数据基础。

## 验收标准

- `AuditEvent` 字段向后兼容（空字符串默认值，现有测试零改动）
- SC8 approve 一笔带原因的改判 → audit 可查到 `override_reason` 非空
- 平台底座 tests 全绿（含原有审计相关测试）
- SC8 tests 全绿（含 pending_queue 相关）
