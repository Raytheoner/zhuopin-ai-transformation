# Design: O2 物料齐套预警

## Context

supplychain 的 `kit_analysis.py`（80 行，两个纯函数）已在真实 BOM/库存/在途数据上验证齐套算法，精度达标。底座 `zhuopin_platform.shared_tools.models` 已有完全匹配的四个 dataclass（BomRow / InventoryRow / PurchaseOrder / ProductionPlan），收割只需改一行 import。O2 是运营部第一个数字员工，本次为 mock-only MVP，不连真实库。

## Goals / Non-Goals

**Goals**
- 收割齐套引擎（原样迁移，零业务逻辑改动）
- import 全走底座，消除 supplychain 跨工程依赖
- 审计接入：齐套决策写 `AuditLogger`（P2 hash-chain 配套）
- mock 夹具验证：两成品 × 三层 BOM，黄金对照偏差 < 1%

**Non-Goals**
- 真实 BOM/库存/在途连接（后续任务）
- 企微推送/告警通知（O2 v2 范围）
- SC5 采购建议复用（不在本 PR）

## ⚡ 架构决策（需 Paul 拍板）

**D1：齐套引擎放哪？**

| 选项 | 位置 | 优点 | 缺点 |
|------|------|------|------|
| **A（推荐）** | `O2-物料齐套预警/o2_kit_shortage/kit_engine.py`（场景本地） | 零过早抽象；SC5 需求未明确前不预判；与 SC8 forecast 一致（Paul 已拍板的范式） | 若 SC5 确实需要，届时需提取 |
| B | `zhuopin_platform/agents/kit_engine.py`（底座共享） | 一份代码两场景复用 | SC5 采购建议尚未设计，不知道它的 API 形状；共享引擎与 O2 的场景特性（运营视角）不一定匹配；YAGNI 风险 |

**我的建议：A（场景本地）**

理由：
1. SC5 还没有 design.md，不知道它消费的 API 形状（是 `shortages dict` 还是 `KitAlertResult`？）；用真实的第二个使用者来设计共享接口，比猜 API 强。
2. 引擎只有 80 行 + 2 个函数，重复代价极低；过早提升到底座反而锁死接口，增加变更成本。
3. 与 SC8 `forecast.py` 在场景本地的既定范式一致。
4. CLAUDE.md 原则：三行雷同也比过早抽象好。

**→ 请 Paul 确认 A，或选 B 并说明 SC5 会如何使用这个引擎。**

---

## Decisions（其余，确认后生效）

**D2：收割方式 = 复制 + 改 import，不包装**

直接把 `kit_analysis.py` 的两个函数复制到 `kit_engine.py`，仅改第一行 import。不加 class 包装、不改函数签名、不加 kwargs——保留已验证的算法原样。

**D3：数字员工入口 `run_kit_alert()` 薄包装**

```python
# o2_kit_shortage/agent.py
def run_kit_alert(
    bom: list[BomRow],
    plans: list[ProductionPlan],
    inventory: list[InventoryRow],
    purchase_orders: list[PurchaseOrder],
    audit_logger: AuditLogger | None = None,
) -> KitAlertResult:
    gross = explode_bom(bom, plans)
    shortages = calc_shortage(gross, inventory, purchase_orders)
    result = KitAlertResult(...)
    if audit_logger:
        audit_logger.log(AuditEvent(event_type="kit_shortage_analysis", ...))
    return result
```

审计可选（None = 静默），便于单测不依赖 sink。

**D4：mock 夹具内嵌 tests/fixtures/，不用 CSV**

inline Python dict 夹具，三层 BOM（FIN001 → SUB001 → MAT001/MAT002；FIN002 → MAT003），手工计算结果写在注释里，黄金测试对照用。

**D5：pyproject.toml 只依赖 `zhuopin_platform`**

与 SC8 一致，`pip install -e ../../../5-平台底座/zhuopin_platform` 后全走底座。

## Risks / Trade-offs

- [如果 D1 选 A，SC5 来了还要复制一次] → 届时有两份具体实现参考，提取共享接口更有据可依，成本可控
- [引擎保留 loss_rate=0 时的 ×1.0 乘法] → 无副作用，保持算法原样更安全

## Migration Plan

1. `git checkout -b feat/o2-kit-shortage-alert`
2. 新建目录 + pyproject + 先写测试 + 实现
3. 全绿 → openspec archive → git commit + push → 停下报结果

## Open Questions

1. **D1 架构决策**（等 Paul 拍板，其余可先进行）
