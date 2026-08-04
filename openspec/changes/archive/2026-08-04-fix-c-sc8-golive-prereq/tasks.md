# Tasks — 变更包 C（SC8 对客上线前置 P1）

> 先写测试再实现。分支叠在 B（PR#11）。

## C1 · 偏差监控（`sc8/deviation.py`）
- [x] 1.1 测试 `tests/test_deviation.py`：
  - 偏差 ≤ 3 天 → 不告警（breached=False、不写 audit、不调 on_breach）；✅
  - 偏差 > 3 天 → breached=True、写 `delivery_deviation_alert`、调 on_breach（stub 记录被调）；✅
  - actual_date=None（现已无法预测）→ breached=True（依 Paul C1-b）；✅ test_unpredictable_is_major_deviation
  - 边界：恰好 = 3 天不告警（> 严格大于）；✅ test_exactly_threshold_no_alert
  - audit=None / on_breach=None 时不报错（仅返回结果）。✅ test_no_audit_no_callback_does_not_raise
  （test_deviation.py 6 passed，2026-07-02 验证）
- [x] 1.2 实现 `evaluate_deviation` + `monitor_deviation`（纯函数 + 依赖注入，消费 `config.DEVIATION_ALERT_DAYS`）。（deviation.py L37-92，2026-07-02 代码核实）
- [x] 1.3 跑 `tests/test_deviation.py` + SC8 全套绿。（SC8 108 passed 2 skipped，2026-07-02 验证）

## C2 · 真实黄金回归（`tests/test_golden_real.py`）— 待 LAN
- [x] 2.1 核验 skip 机制：`SC8_GOLDEN_DIR` 指向临时合成最小夹具 → replay 路径可跑通（仅验证机理，合成夹具不入库）。（test_golden_real.py 1 passed：real_frozen/ 不存在时 skip 机制生效；build_golden_real.py 存在于 scripts/，2026-07-02 验证）
- [x] 2.2 标注 **待 LAN 执行**：回 LAN/VPN 跑 `scripts/build_golden_real.py` 生成 `data/golden/real_frozen/`（FO/BOM/SRM 冻结 + expected.json）→ 提交 → 测试自动脱离 skip。**本会话不伪造夹具**。（CLAUDE.md 记录 2026-06-18 LAN 回归真实跑通，确定性偏差=0；real_frozen/ 不入库，gitignore 保护）

## 收尾
- [x] 3.1 全仓回归全绿；黄金值不漂移。（2026-07-02 验证：平台138/SC8 108/SC5 41/O2 20/SC3 29/SC1 53）
- [x] 3.2 `openspec validate fix-c-sc8-golive-prereq --strict` ✅ 通过（2026-08-04 CC 复核，队列 #196；原注"无 specs delta"已过时——本包实际有 1 个 specs delta 文件）
- [x] 3.3 commit + push ✅ 已完成——`ecd41f0 fix(sc8-golive): 变更包C SC8对客上线前置P1 — C1偏差监控 / C2真实黄金回归(待LAN)`（2026-06-13）+ `d77ef4c fix(sc8-golive): 变更包C C2 真实黄金回归落地(LAN) + SC1 SRM真实验证发现`（2026-06-18），均已在 origin/master
- [x] 3.4 CLAUDE.md 当前进度追加 A/B/C 状态行 ✅ **已存在，无需新增**——`1-转型规划/0-全景路线图/进度编年-CHANGELOG.md` 行 19（"代码修复 A/B/C 已全量并入 master（2026-06-18...）"）已完整记录 A1-A3/B1-B6/C1-C2 逐项状态、PR 号、commit 引用，2026-07-07 R5 瘦身时随旧段落一并迁入该文件；2026-08-04 CC 核实内容准确、不重复登记（队列 #196）
