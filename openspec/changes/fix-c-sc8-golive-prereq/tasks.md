# Tasks — 变更包 C（SC8 对客上线前置 P1）

> 先写测试再实现。分支叠在 B（PR#11）。

## C1 · 偏差监控（`sc8/deviation.py`）
- [ ] 1.1 测试 `tests/test_deviation.py`：
  - 偏差 ≤ 3 天 → 不告警（breached=False、不写 audit、不调 on_breach）；
  - 偏差 > 3 天 → breached=True、写 `delivery_deviation_alert`、调 on_breach（stub 记录被调）；
  - actual_date=None（现已无法预测）→ breached=True（依 Paul C1-b）；
  - 边界：恰好 = 3 天不告警（> 严格大于）；
  - audit=None / on_breach=None 时不报错（仅返回结果）。
- [ ] 1.2 实现 `evaluate_deviation` + `monitor_deviation`（纯函数 + 依赖注入，消费 `config.DEVIATION_ALERT_DAYS`）。
- [ ] 1.3 跑 `tests/test_deviation.py` + SC8 全套绿。

## C2 · 真实黄金回归（`tests/test_golden_real.py`）— 待 LAN
- [ ] 2.1 核验 skip 机制：`SC8_GOLDEN_DIR` 指向临时合成最小夹具 → replay 路径可跑通（仅验证机理，合成夹具不入库）。
- [ ] 2.2 标注 **待 LAN 执行**：回 LAN/VPN 跑 `scripts/build_golden_real.py` 生成 `data/golden/real_frozen/`（FO/BOM/SRM 冻结 + expected.json）→ 提交 → 测试自动脱离 skip。**本会话不伪造夹具**。

## 收尾
- [ ] 3.1 全仓回归全绿；黄金值不漂移。
- [ ] 3.2 `openspec validate fix-c-sc8-golive-prereq --strict`。
- [ ] 3.3 commit（引用 C1/C2）+ push + PR（base = B 分支，stacked）。
- [ ] 3.4 CLAUDE.md 当前进度追加 A/B/C 状态行（含 C2 待 LAN、A1 后催 IT 6/20 轮换 secret）。
