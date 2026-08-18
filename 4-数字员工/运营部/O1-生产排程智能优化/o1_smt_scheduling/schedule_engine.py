"""
SMT 排产引擎 —— 收割自 supplychain `src/agents/smt_scheduling.py`（2026-08-18）。

职责：根据物料到货日和 SMT 工时对照表，计算 SMT 最早完工日。

核心函数：
  schedule_smt(product_id, material_arrivals, lead_time_map) -> date | None

算法（档 1 简化版，与被收割实现一致）：
  SMT 完工日 = max(所有物料到货日) + SMT 工时天数（自然日）

收割说明（openspec 变更包 o1-smt-scheduling-mvp，design D2）：
  - `schedule_smt` / `load_smt_lead_time` 两个签名逐字保留，不包装、不改形状，
    使被收割实现的原测试可原样迁入充当回归网。
  - 相对被收割实现只加了两件事，均由 spec 要求、design D4 拍板：
      ① CSV 支持 `#` 注释行，用于承载「本表是占位数据」的声明块；
      ② 工时列非法的行**跳过并告警**，而非让 int() 抛错或静默视为 0。

⚠️ 口径待复核（晋档 2 前置）：
  - 按自然日计算，**不跳过周末/节假日**。该简化来自 supplychain MVP 阶段业务方
    的一次口头确认，**未记录确认人与日期**；正式口径须由运营部 PMC 书面复核。
  - SMT 工时来自 `fixtures/smt_lead_time.csv`（携客云 SRM 无排产 API，2026-05-22
    经 `spike_mvp_t5_smt.py` 探查 11 个候选端点后坐实）。
  - 🔴 随附工时表 46 行工时值**全为占位常数 7**，非真实工时。调用方须经
    `is_placeholder_lead_time()` 判断后再决定该结果可否外用。
"""
import csv
import warnings
from datetime import date, timedelta
from pathlib import Path

_LEAD_TIME_CSV = Path(__file__).parent / "fixtures" / "smt_lead_time.csv"

# 声明块里的机器可读标记，形如 `# @placeholder: true`
_PLACEHOLDER_MARKER = "@placeholder:"


def _data_lines(path: Path):
    """产出 CSV 的数据行，剔除 `#` 注释行（声明块由此得以与数据同住一个文件）。"""
    with open(path, encoding="utf-8-sig", newline="") as f:
        for line in f:
            if not line.lstrip().startswith("#"):
                yield line


def is_placeholder_lead_time(csv_path: Path | str | None = None) -> bool:
    """该工时表是否为占位数据（非实测工时）。

    读声明块中的 `# @placeholder: true|false` 标记。**无标记时返回 True** ——
    缺省偏保守：来路不明的工时表不得被默认当作真实数据使用。
    """
    path = Path(csv_path) if csv_path else _LEAD_TIME_CSV
    with open(path, encoding="utf-8-sig", newline="") as f:
        for line in f:
            stripped = line.lstrip()
            if not stripped.startswith("#"):
                break                                   # 注释块结束，不再往下找
            if _PLACEHOLDER_MARKER in stripped:
                value = stripped.split(_PLACEHOLDER_MARKER, 1)[1].strip().lower()
                return value != "false"
    return True


def load_smt_lead_time(csv_path: Path | str | None = None) -> dict[str, int]:
    """
    从 CSV 加载 SMT 工时对照表。

    工时列为空或非整数的行**跳过并告警**，不计入结果——如此该产品随后排产会
    如实返回「无法排产」，而不是被当成 0 天算出一个假完工日。

    Returns:
        dict: { product_id: smt_lead_days }
    """
    path = Path(csv_path) if csv_path else _LEAD_TIME_CSV
    result: dict[str, int] = {}
    skipped: list[str] = []
    for row in csv.DictReader(_data_lines(path)):
        product_id = (row.get("product_id") or "").strip()
        lead_days = (row.get("smt_lead_days") or "").strip()
        if not product_id or not lead_days:
            if product_id:
                skipped.append(product_id)
            continue
        try:
            result[product_id] = int(lead_days)
        except ValueError:
            skipped.append(product_id)
    if skipped:
        warnings.warn(
            f"SMT 工时表 {path.name} 有 {len(skipped)} 行工时非法已跳过（"
            f"{'、'.join(skipped)}）；这些产品将无法排产，不会按 0 天估算",
            UserWarning, stacklevel=2,
        )
    return result


def schedule_smt(
    product_id: str,
    material_arrivals: dict[str, date],
    lead_time_map: dict[str, int],
) -> date | None:
    """
    计算 SMT 最早完工日。

    Args:
        product_id:        成品/半成品料号，如 "F02N.0040"
        material_arrivals: 各物料的预计到货日 { material_id: arrival_date }
        lead_time_map:     SMT 工时对照表 { product_id: lead_days }

    Returns:
        SMT 完工日（date），或 None（产品无工时配置 / 无物料到货记录）
    """
    # 产品未在工时表中 → 无法估算完工日
    if product_id not in lead_time_map:
        return None

    # 没有任何物料到货记录 → 无法排产
    if not material_arrivals:
        return None

    # 取所有物料中最迟的到货日（齐料日）
    latest_arrival = max(material_arrivals.values())

    # 完工日 = 齐料日 + SMT 加工天数（自然日，不跳周末/节假日）
    lead_days = lead_time_map[product_id]
    return latest_arrival + timedelta(days=lead_days)
