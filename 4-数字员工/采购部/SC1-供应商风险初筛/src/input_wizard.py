"""
CLI 数据录入向导 — 供采购经理交互式输入评估数据。

设计决策 D3：运行时交互式输入，原始财务数据不落盘（红色数据保护）。
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Optional


SINGLE_SOURCE_OPTIONS = [
    (1, "有 ≥2 家合格替代供应商"),
    (2, "有 1 家替代供应商（已认证）"),
    (3, "有潜在替代供应商（未认证）"),
    (4, "无替代供应商但已启动开发"),
    (5, "完全单源，无替代计划"),
]


@dataclass
class WizardResult:
    supplier_name: str
    supplier_code: str
    evaluator: str
    remark: str
    iqc_rate: Optional[float]
    iqc_source: str
    registered_capital_wan: Optional[float]
    years_established: Optional[float]
    financial_source: str
    single_source_option: Optional[int]
    single_source_source: str
    delivery_override_rate: Optional[float]
    delivery_override_source: str


def _prompt_required(prompt: str) -> str:
    """循环提示直到用户输入非空字符串。"""
    while True:
        val = input(prompt).strip()
        if val:
            return val
        print("  [必填，请重新输入]")


def _prompt_float_or_skip(prompt: str, min_val: float = 0.0, max_val: float = 100.0,
                           skip_label: str = "跳过") -> Optional[float]:
    """提示输入浮点数，输入空或 's' 跳过返回 None，范围校验。"""
    while True:
        raw = input(f"{prompt} (直接回车={skip_label}): ").strip()
        if not raw:
            return None
        try:
            val = float(raw)
            if min_val <= val <= max_val:
                return val
            print(f"  [请输入 {min_val}–{max_val} 之间的数值]")
        except ValueError:
            print("  [输入无效，请输入数字]")


def _prompt_positive_float_or_skip(prompt: str, skip_label: str = "未知") -> Optional[float]:
    """提示输入正浮点数，空或 's' 跳过。"""
    while True:
        raw = input(f"{prompt} (直接回车={skip_label}): ").strip()
        if not raw:
            return None
        try:
            val = float(raw)
            if val > 0:
                return val
            print("  [请输入大于 0 的数值]")
        except ValueError:
            print("  [输入无效，请输入数字]")


def _prompt_single_source() -> Optional[int]:
    """显示替代供应商状态菜单，返回用户选择的选项编号（1-5）或 None。"""
    print("\n  替代供应商状态（直接回车=跳过，默认视为完全单源）：")
    for opt, label in SINGLE_SOURCE_OPTIONS:
        print(f"    {opt}. {label}")
    while True:
        raw = input("  请选择 [1-5]（直接回车跳过）: ").strip()
        if not raw:
            return None
        if raw in ("1", "2", "3", "4", "5"):
            return int(raw)
        print("  [请输入 1-5 或直接回车]")


def run_wizard(srm_delivery_rate: Optional[float] = None) -> WizardResult:
    """
    运行交互式录入向导，收集所有评估所需数据。

    Args:
        srm_delivery_rate: 已从 SRM 自动获取的交付准时率（None 表示获取失败）
    """
    print("\n" + "=" * 60)
    print("  SC1 供应商风险初筛 — 数据录入")
    print("=" * 60)

    # 1. 基本信息
    print("\n【1/4】供应商基本信息")
    supplier_name = _prompt_required("  供应商名称: ")
    supplier_code = input("  供应商编码（可选，直接回车跳过）: ").strip()
    evaluator = _prompt_required("  评估人姓名: ")
    remark = input("  评估目的/备注（可选）: ").strip()

    # 2. 交付准时率（SRM 优先，支持覆盖）
    print("\n【2/4】交付准时率")
    delivery_override_rate = None
    delivery_override_source = ""

    if srm_delivery_rate is not None:
        print(f"  [SRM 自动获取] 近期交付准时率: {srm_delivery_rate:.1f}%")
        override = input("  是否手动覆盖？（直接回车保留 SRM 数据，输入新数值覆盖）: ").strip()
        if override:
            try:
                rate_val = float(override)
                if 0 <= rate_val <= 100:
                    delivery_override_rate = rate_val
                    delivery_override_source = "人工覆盖"
                    reason = input("  覆盖原因（可选）: ").strip()
                    if reason:
                        delivery_override_source = f"人工覆盖（{reason}）"
                    print(f"  已覆盖为: {delivery_override_rate:.1f}%")
                else:
                    print("  [数值超出范围，保留 SRM 数据]")
            except ValueError:
                print("  [输入无效，保留 SRM 数据]")
    else:
        print("  SRM 数据不可用，请手动录入")
        rate_val = _prompt_float_or_skip("  交付准时率（%，0-100）", skip_label="数据不可用")
        if rate_val is not None:
            delivery_override_rate = rate_val
            delivery_override_source = "人工录入"

    # 3. IQC 合格率
    print("\n【3/4】IQC 合格率（ERP 待接入，请手动录入）")
    iqc_rate = _prompt_float_or_skip("  IQC 合格率（%，0-100）", skip_label="数据不可用")
    if iqc_rate is not None:
        iqc_source = "人工录入"
    else:
        iqc_source = "数据不足"
        print("  [将使用默认分值 2.5]")

    # 4. 财务稳定性
    print("\n【4/4】财务稳定性指标")
    registered_capital_wan = _prompt_positive_float_or_skip("  注册资本（万元）")
    years_established = _prompt_positive_float_or_skip("  公司成立年限（年）")
    if registered_capital_wan is not None or years_established is not None:
        financial_source = "人工录入"
    else:
        financial_source = "数据不足"

    # 单源依赖风险
    print("\n【补充】单源依赖风险")
    single_source_option = _prompt_single_source()
    if single_source_option is not None:
        single_source_source = "人工录入"
    else:
        single_source_source = "未确认（默认完全单源）"
        print("  [未选择，默认视为完全单源，评分=1]")

    print("\n  数据录入完成。\n")

    return WizardResult(
        supplier_name=supplier_name,
        supplier_code=supplier_code,
        evaluator=evaluator,
        remark=remark,
        iqc_rate=iqc_rate,
        iqc_source=iqc_source,
        registered_capital_wan=registered_capital_wan,
        years_established=years_established,
        financial_source=financial_source,
        single_source_option=single_source_option,
        single_source_source=single_source_source,
        delivery_override_rate=delivery_override_rate,
        delivery_override_source=delivery_override_source,
    )
