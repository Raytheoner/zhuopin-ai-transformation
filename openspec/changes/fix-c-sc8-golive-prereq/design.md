# Design — 变更包 C：SC8 对客上线前置 P1

> 审 design 重点：**【需 Paul 拍板 C1】** 偏差监控的输入契约与"触发重算"实现方式。C2 为 LAN 阻塞项，无代码决策。
> 分支 `fix/c-sc8-golive-prereq` 叠在 B（PR#11）之上。

## C1 · 偏差监控（`sc8/deviation.py`）

### SOP 依据（§4.3，VP 2026-06-11 签字）
"预测交付日 vs 实际进展偏差 > 3 天 → 自动告警 + 触发重算"。触发重算的信号（§1.2）：供应商交期反馈更新、齐套日变化、委外排期变化、实际到货与预测偏差超阈值。

### 设计
新模块 `sc8/deviation.py`，纯函数 + 依赖注入（与 pipeline 风格一致，off-LAN mock 可完整验证）：

```python
DEVIATION_ALERT = config.DEVIATION_ALERT_DAYS  # 3

@dataclass
class DeviationResult:
    so_id: str
    customer_name: str
    committed_date: date           # 此前对客承诺的交付日
    actual_date: date | None       # 最新"实际进展"推算交付日（None=现已无法预测）
    deviation_days: int | None     # abs 天数差；None=无法预测
    breached: bool                 # 是否超阈值（或无法预测）
    requires_recompute: bool

def evaluate_deviation(committed_date, actual_date, *, threshold_days=DEVIATION_ALERT) -> DeviationResult:
    # actual_date 为 None（最新无法预测）→ breached=True（保守，按重大偏差处理）
    # 否则 deviation = abs((actual_date - committed_date).days)；> threshold → breached

def monitor_deviation(committed_date, actual_date, *, so_id, customer_name,
                      threshold_days=DEVIATION_ALERT, audit=None, on_breach=None) -> DeviationResult:
    res = evaluate_deviation(...)
    if res.breached:
        if audit is not None:
            audit.record(AuditEvent(scenario="SC8", action="delivery_deviation_alert",
                automation_level="L2", decision={so_id, committed, actual, deviation_days, threshold}))
        if on_breach is not None:
            on_breach(res)          # 触发重算（如重跑 compute_forecasts），由调用方注入
    return res
```

- **告警**：`breached=True` 即告警信号；调用方（PMC/采购侧编排）据此决定是否生成更正草稿（更正草稿走既有 `notify.build_correction_draft` + L2 门禁，本模块不直接发客户）。
- **触发重算**：以注入回调 `on_breach` 实现（默认 None=只告警+留痕）。生产编排注入"重跑 compute_forecasts 并 record_correction"的回调；测试注入 stub 验证被调用。
- **留痕**：`delivery_deviation_alert` 写平台 audit（IATF §7.2）。

> **【需 Paul 拍板 C1】** "实际进展"的输入口径，本期 off-LAN 取哪种？
> - **选项 A（推荐）**：本模块只接 `(committed_date, actual_date)` 两个日期 + 注入回调，**不耦合数据源**。"actual_date" 由编排层用最新数据重跑 `compute_forecasts` 得到的 `forecast_date` 喂入（real 接通后即真实；off-LAN 用 mock 序列测试）。模块纯函数、最易测、最稳。
> - **选项 B**：本模块内部直接拉最新 SRM/BOM 重算。耦合连接器、off-LAN 不可测、与"纯函数依赖注入"基调相悖。
>
> 推荐 **A**。tasks 按 A 写。"触发重算"用注入回调，不在本模块内硬接 compute_forecasts。

> **【需 Paul 拍板 C1-b】** 最新"无法预测"（actual_date=None，物料又不齐了）是否按"超阈值告警"处理？
> - **选项 A（推荐）**：是——视为重大偏差，`breached=True`、`requires_recompute=True`（承诺过的单子现在算不出交期，必须告警人工介入）。
> - **选项 B**：仅当能算出 actual_date 且差值 > 阈值才告警；None 不告警（会漏掉"承诺后变不可预测"的危险态）。
>
> 推荐 **A**。

## C2 · 真实黄金回归激活（`tests/test_golden_real.py`）

### 现状（已正确结构化）
`test_golden_real.py` 已用 `pytest.mark.skipif(not (GOLDEN_DIR/"expected.json").exists())` 控制：夹具在 → 跑确定性零漂移回归；夹具缺 → skip，不阻塞 mock 套件。`scripts/build_golden_real.py` 负责 FO 在线时生成冻结夹具。

### 本会话处理（off-LAN）
- **不可达真实 FO/U9C 端点** → 无法运行 `build_golden_real.py` 生成 `expected.json`。
- 按任务要求：**不伪造夹具**。保持 skip 机制原样，核验"夹具就位即自动生效"的机理（可用 `SC8_GOLDEN_DIR` 指向临时目录 + 合成最小夹具验证 replay 路径不报错，但**不**把合成夹具当真实黄金入库）。
- PR 描述与收尾清单标注 **C2 = 待 LAN 执行**：回 LAN/VPN 后跑 `build_golden_real.py` → 提交 `data/golden/real_frozen/` → 该测试脱离 skip。

> 无代码决策点。C2 不在本会话"完成"，仅交付"机制就绪 + 待 LAN 清单"。

## 不在本包范围
报告 §7 其余 P1/P2；A 包 P0（PR#10）、B 包数据/审计（PR#11）。
