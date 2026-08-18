"""
SC1 供应商风险初筛 — 主程序入口

用法：
  python main.py evaluate          # 交互式评估一个供应商
  python main.py query <供应商名称>  # 查询历史评估记录
  python main.py verify            # 审计日志完整性自检
  python main.py demo              # 生成演示报告（不调用 AI）
"""
import argparse
import sys
from pathlib import Path

# —— worktree 隔离引导（队列 #300／#313 补漏）：把本 worktree 的平台底座路径插到
# sys.path 最前，使 import 结果与全局 editable 安装当前指向谁无关。必须放在本文件
# 任何 zhuopin_platform / 场景包 import 之前（`src.audit_log`/`src.data_providers`
# 均在模块或函数内 import zhuopin_platform，本引导同样覆盖）。——
_HERE = Path(__file__).resolve()
for _p in (_HERE, *_HERE.parents):
    if (_p / "5-平台底座" / "zhuopin_platform").is_dir():
        for _entry in (_p / "5-平台底座" / "zhuopin_platform", _HERE.parent):
            if str(_entry) not in sys.path:
                sys.path.insert(0, str(_entry))
        break
else:
    # 🔴 找不到仓库根标记时**不得硬失败**（2026-08-18 实测事故，队列 #345）：#300 要防的是
    # "N 个平等 worktree 共用一套全局 site-packages、谁装的 editable 指针谁说了算"——
    # **该前提只在开发机成立**。`.51` 的部署布局是扁平的 `C:/<svc>/app` ＋
    # `C:/<svc>/zhuopin_platform`（后者已由 deploy 脚本 pip install -e 进 venv，全机唯一
    # 一份、无歧义），**没有也不需要 `5-平台底座/` 这层目录**。原实现在此直接 raise，等于
    # 把入口在生产布局上钉死（现象：计划任务 LastResult=0 但进程秒退、端口无监听）。
    # ⇒ 找到标记 → 按 #300 前插（开发机，确定性优先）；找不到 → 只插自身包路径、平台底座
    # 交由环境解析（生产机，唯一一份）。**不引入静默失败**：环境里也没有 zhuopin_platform
    # 时仍然明确报错。——
    if str(_HERE.parent) not in sys.path:
        sys.path.insert(0, str(_HERE.parent))
    from importlib.util import find_spec
    if find_spec("zhuopin_platform") is None:
        raise RuntimeError(
            f"既未找到仓库根标记 5-平台底座/zhuopin_platform（从 {_HERE} 向上查找），"
            "环境中也没有可导入的 zhuopin_platform——请检查部署或安装平台底座包")

import config
from src.audit_log import SC1AuditAdapter as AuditLogger
from src.data_providers import get_delivery_data
from src.input_wizard import run_wizard
from src.scoring import RiskScoringEngine


def cmd_evaluate():
    """完整评估流程：SRM 拉取 → 录入向导 → 评分 → AI 文本 → 报告 → 日志。"""
    # 1. 尝试 SRM 拉取（此时尚不知供应商名称，先获取名称再拉）
    print("\n正在启动供应商风险初筛...")
    supplier_name_hint = input("请先输入供应商名称（用于 SRM 查询）: ").strip()
    supplier_code_hint = input("供应商编码（可选，直接回车跳过）: ").strip()

    srm_rate = None
    srm_note = ""
    try:
        data = get_delivery_data(supplier_name_hint, supplier_code_hint)
        srm_rate = data.rate
        if srm_rate is not None:
            srm_note = f"SRM 已获取交付准时率: {srm_rate:.1f}%"
        else:
            srm_note = "SRM 数据不可用"
    except Exception as e:
        srm_note = f"SRM 查询异常: {e}"

    if srm_rate is not None:
        print(f"\n[SRM 自动] {srm_note}")
    else:
        print(f"\n[提示] {srm_note}，将转为人工录入")

    # 2. 录入向导
    wizard = run_wizard(srm_delivery_rate=srm_rate)

    # 确定最终交付数据
    if wizard.delivery_override_rate is not None:
        final_delivery_rate = wizard.delivery_override_rate
        delivery_source = wizard.delivery_override_source
    elif srm_rate is not None:
        final_delivery_rate = srm_rate
        delivery_source = "SRM自动"
    else:
        final_delivery_rate = None
        delivery_source = "数据不足"

    # 3. 评分
    engine = RiskScoringEngine()
    result = engine.evaluate(
        delivery_rate=final_delivery_rate,
        iqc_rate=wizard.iqc_rate,
        registered_capital_wan=wizard.registered_capital_wan,
        years_established=wizard.years_established,
        single_source_option=wizard.single_source_option,
    )

    print(f"\n评分完成：综合评分 {result.composite_score:.2f} / 风险等级 {result.risk_level} 级（{result.risk_label}）")

    # 4. AI 文本生成
    risks = ["[AI 分析不可用 - 请采购经理手动填写]"]
    actions = ["[AI 建议不可用 - 请采购经理手动填写]"]
    ai_hash = ""

    if config.DEEPSEEK_API_KEY:
        print("正在调用 AI 生成风险描述和建议...")
        try:
            from src.ai_generator import generate_ai_text
            risks, actions, ai_hash = generate_ai_text(
                result, wizard.supplier_name, config.DEEPSEEK_API_KEY,
                config.LLM_MODEL, config.DEEPSEEK_BASE_URL,
            )
            print("AI 文本生成完成。")
        except Exception as e:
            print(f"[警告] AI 生成失败: {e}，使用占位文本。")
    else:
        print("[提示] 未配置 ANTHROPIC_API_KEY，跳过 AI 文本生成。")

    # 5. 生成报告
    report_path_str = "FAILED"
    report_error = ""
    try:
        from src.report_generator import generate_report
        report_path = generate_report(
            result=result,
            supplier_name=wizard.supplier_name,
            supplier_code=wizard.supplier_code,
            evaluator=wizard.evaluator,
            remark=wizard.remark,
            delivery_source=delivery_source,
            risk_descriptions=risks,
            action_items=actions,
            reports_dir=config.REPORTS_DIR,
            iqc_source=wizard.iqc_source,
            financial_source=wizard.financial_source,
            single_source_source=wizard.single_source_source,
        )
        report_path_str = str(report_path)
        print(f"\n报告已生成: {report_path_str}")
    except Exception as e:
        report_error = str(e)
        print(f"[错误] 报告生成失败: {e}")

    # 6. 写审计日志
    logger = AuditLogger(config.AUDIT_LOG_PATH)
    logger.append_record(
        evaluator=wizard.evaluator,
        supplier_name=wizard.supplier_name,
        supplier_code=wizard.supplier_code,
        result=result,
        delivery_source=delivery_source,
        ai_text_hash=ai_hash,
        report_path=report_path_str,
        error=report_error,
    )
    print(f"审计日志已记录: {config.AUDIT_LOG_PATH}")

    print("\n评估流程完成。请采购经理查看报告并签字确认。")


def cmd_query(supplier_name: str):
    """按供应商名称查询历史评估记录。"""
    logger = AuditLogger(config.AUDIT_LOG_PATH)
    records = logger.query_by_supplier(supplier_name)

    if not records:
        print(f"未找到供应商 '{supplier_name}' 的历史评估记录。")
        return

    print(f"\n供应商 '{supplier_name}' 的历史评估记录（共 {len(records)} 条）：\n")
    print(f"{'时间':<26}  {'风险等级':<8}  {'综合评分':<8}  {'评估人'}")
    print("-" * 60)
    for r in sorted(records, key=lambda x: x["timestamp"]):
        ts = r["timestamp"][:19].replace("T", " ")
        level = f"{r['risk_level']} 级"
        score = f"{r['composite_score']:.2f}"
        print(f"{ts:<26}  {level:<8}  {score:<8}  {r['evaluator']}")


def cmd_verify():
    """审计日志完整性自检。"""
    logger = AuditLogger(config.AUDIT_LOG_PATH)
    result = logger.verify_integrity()

    print("\n========== 审计日志完整性自检 ==========")

    if result["status"] == "empty":
        print("日志文件不存在或为空，尚无评估记录。")
        return

    print(f"总记录数：   {result['total']}")
    print(f"有效记录：   {result['valid']}")
    print(f"异常记录：   {result['invalid']}")
    print(f"最早记录：   {result['earliest'][:19] if result['earliest'] else '—'}")
    print(f"最新记录：   {result['latest'][:19] if result['latest'] else '—'}")
    print(f"涉及供应商： {len(result['suppliers'])} 家")

    if result["recent_10"]:
        print("\n最新 10 条记录摘要：")
        print(f"  {'时间':<22}  {'供应商':<20}  {'等级':<6}  {'评分':<6}  {'评估人'}")
        print("  " + "-" * 70)
        for r in result["recent_10"]:
            ts = r["timestamp"][:19].replace("T", " ")
            print(f"  {ts:<22}  {r['supplier']:<20}  {r['risk_level']} 级   {r['score']:.2f}  {r['evaluator']}")

    if result["invalid_lines"]:
        print(f"\n⚠ 发现 {result['invalid']} 条异常记录，请检查：")
        for lineno, preview in result["invalid_lines"]:
            print(f"  第 {lineno} 行: {preview}")
        print("\n⚠ 发现异常记录，请检查")
    else:
        print("\n✓ 审计日志完整性校验通过")


def cmd_demo():
    """生成演示报告（不需要 SRM/AI，适合首次验证报告格式）。"""
    from src.scoring import RiskScoringEngine
    from src.report_generator import generate_report

    engine = RiskScoringEngine()

    demo_cases = [
        dict(
            name="优质供应商示例",
            delivery_rate=96.0, iqc_rate=99.2,
            capital=5000.0, years=12.0, ss_option=1,
            delivery_src="SRM自动",
        ),
        dict(
            name="中等风险供应商示例",
            delivery_rate=83.0, iqc_rate=95.5,
            capital=300.0, years=4.0, ss_option=3,
            delivery_src="人工录入",
        ),
        dict(
            name="高风险供应商示例",
            delivery_rate=65.0, iqc_rate=88.0,
            capital=50.0, years=1.5, ss_option=5,
            delivery_src="数据不足",
        ),
    ]

    print("\n生成演示报告...")
    for case in demo_cases:
        result = engine.evaluate(
            delivery_rate=case["delivery_rate"],
            iqc_rate=case["iqc_rate"],
            registered_capital_wan=case["capital"],
            years_established=case["years"],
            single_source_option=case["ss_option"],
        )
        path = generate_report(
            result=result,
            supplier_name=case["name"],
            supplier_code="DEMO",
            evaluator="演示用户",
            remark="演示报告，非真实数据",
            delivery_source=case["delivery_src"],
            risk_descriptions=[
                "此为演示报告，风险描述由 AI 生成（演示模式已跳过 AI 调用）",
                "实际使用时将调用 claude-sonnet-4-6 生成真实风险分析",
            ],
            action_items=[
                "演示模式：请配置 ANTHROPIC_API_KEY 后运行真实评估",
            ],
            reports_dir=config.REPORTS_DIR,
        )
        print(f"  [{result.risk_level}级] {case['name']} → {path.name}")

    print(f"\n演示报告已保存到: {config.REPORTS_DIR}")
    print("请用浏览器或 VS Code 打开报告文件查看格式。")


def main():
    parser = argparse.ArgumentParser(
        prog="SC1 供应商风险初筛",
        description="AI 辅助供应商风险评估工具（L2 自动化）",
    )
    subparsers = parser.add_subparsers(dest="command")

    subparsers.add_parser("evaluate", help="交互式评估一个供应商")

    query_parser = subparsers.add_parser("query", help="查询供应商历史评估记录")
    query_parser.add_argument("supplier_name", help="供应商名称")

    subparsers.add_parser("verify", help="审计日志完整性自检")
    subparsers.add_parser("demo", help="生成演示报告（不调用 AI）")

    args = parser.parse_args()

    if args.command == "evaluate":
        cmd_evaluate()
    elif args.command == "query":
        cmd_query(args.supplier_name)
    elif args.command == "verify":
        cmd_verify()
    elif args.command == "demo":
        cmd_demo()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
