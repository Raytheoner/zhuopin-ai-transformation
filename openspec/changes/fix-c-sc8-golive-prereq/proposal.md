## Why

《全盘审计与差距分析报告-2026-06-13》§3.3 列出 SC8 对客上线检查表的两项**未达成**前置（P1-D / P1-E）——SOP《SC8上线前置门禁》第 3 节明确：在它们修复前**不得开启对客外发开关**：

- **C1（报告#7，检查表第 4 项）偏差监控未实现**：全仓只有常量 `DEVIATION_ALERT_DAYS=3`，**无任何消费代码**。SOP §4.3（VP 2026-06-11 签字）要求"预测交付日 vs 实际进展偏差 > 3 天 → 自动告警 + 触发重算"。
- **C2（报告#8，检查表第 1 项）真实黄金回归未生效**：`test_golden_real.py` 因 `data/golden/real_frozen/expected.json` 夹具不存在而**整组 skip**；需回 LAN/VPN 跑 `scripts/build_golden_real.py` 生成冻结夹具激活。

本变更包叠在 A（PR#10）/ B（PR#11）之上。**C1 off-LAN 用 mock 数据写完整逻辑与测试**；**C2 受 LAN/VPN 阻塞**（off-LAN 不可达真实 FO/U9C 端点）→ 本会话**标注"待 LAN 执行"、不伪造夹具**。

## What Changes

- **C1 · 偏差监控（新模块 `sc8/deviation.py`）**：消费 `config.DEVIATION_ALERT_DAYS=3`——对一条已承诺交期与最新"实际进展"推算交付日比对，偏差 > 阈值（或最新无法预测）→ ① 告警（产出告警对象/可入队更正草稿）；② 触发重算（回调 `on_breach`，默认接 `compute_forecasts` 重跑）；③ 写 audit `delivery_deviation_alert` 留痕（含 so_id/承诺日/实际日/偏差天数）。对应 SOP §4.3 与上线检查表第 4 项。完整逻辑 + 测试 off-LAN 用 mock 数据写就。
- **C2 · 真实黄金回归激活（`tests/test_golden_real.py`）**：
  - LAN/VPN 可达 → 运行 `scripts/build_golden_real.py` 生成 `data/golden/real_frozen/expected.json` 入库，使该测试脱离 skip；
  - **本会话 off-LAN 不可达** → 保持现有"夹具缺失即 skip"机制不变，在 PR/文档标注"**待 LAN 执行**"，**不伪造夹具**。仅核验 skip 机制完好（夹具就位即生效）。

## Capabilities

### Added Capabilities
- `delivery-deviation-monitor`：承诺交期偏差监控（阈值告警 + 触发重算 + 审计）（C1）。

## Impact

- **SC8 工程**：新增 `sc8/deviation.py` + `tests/test_deviation.py`；不改既有预测/门禁逻辑。
- **上线门禁**：C1 完成补齐检查表第 4 项；C2 待 LAN 执行补齐第 1 项。两者 + A 包 P0-A 全部完成前，对客外发开关不得开启（与 SOP 第 3 节一致）。
- **合规红线**：强化 CLAUDE.md §7.2（决策写 audit）；偏差告警/重算全程留痕。
- **off-LAN 边界**：C1 全 mock 验证；C2 真实夹具生成明确标"待 LAN"，不假装验证。
