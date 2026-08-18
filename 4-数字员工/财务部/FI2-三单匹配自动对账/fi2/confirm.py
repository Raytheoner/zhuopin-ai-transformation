"""FI2 L3 改判录入 CLI — 财务人员对 needs_review 匹配项的人工结案入口。

v3 口径修正（2026-07-09）：改判定位键从 po_no+line_no 改 ap_no+item_code（核对对象改
AP 单 vs INV，料品汇总归集后匹配单元是料品，见 design D11）。

用法::

    python -m fi2.confirm \\
        --ap-no    AP-2026-0001 \\
        --item-code B001 \\
        --conclusion "已核实：供应商折让未及时录入 PO，发票金额正确" \\
        --reason  "对照供应商折让通知单核实，金额差异属正常业务调整"

约束（IATF 16949 可追溯）：
- ``--reason`` 必填且不可为空，缺失或空字符串拒绝执行。
- 每次 confirm 写一条 AuditEvent 到 ``reports/fi2_audit.jsonl``（与 run.py 同源）。
- 幂等：同 ap_no+item_code 已有 confirm 记录则打印警告，不重复写（exit 0）。
- confirm.py 只负责留痕；AI 结论永远是"建议"，结案在财务人员——L3 阶段不实现自动过账。
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

# —— worktree 隔离引导（队列 #300／#313 补漏）：把本 worktree 的平台底座与场景自身路径插到
# sys.path 最前，使 import 结果与全局 editable 安装当前指向谁无关。必须放在本文件
# 任何 zhuopin_platform / 场景包 import 之前。——
_HERE = Path(__file__).resolve()
for _p in (_HERE, *_HERE.parents):
    if (_p / "5-平台底座" / "zhuopin_platform").is_dir():
        for _entry in (_p / "5-平台底座" / "zhuopin_platform", _HERE.parent.parent):
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
    if str(_HERE.parent.parent) not in sys.path:
        sys.path.insert(0, str(_HERE.parent.parent))
    from importlib.util import find_spec
    if find_spec("zhuopin_platform") is None:
        raise RuntimeError(
            f"既未找到仓库根标记 5-平台底座/zhuopin_platform（从 {_HERE} 向上查找），"
            "环境中也没有可导入的 zhuopin_platform——请检查部署或安装平台底座包")

from zhuopin_platform.audit import AuditEvent, AuditLogger

_ROOT = Path(__file__).resolve().parent.parent
_AUDIT_PATH = _ROOT / "reports" / "fi2_audit.jsonl"


def _already_confirmed(audit: AuditLogger, ap_no: str, item_code: str) -> bool:
    """检查同 ap_no + item_code 是否已有改判记录。"""
    existing = audit.query_by(scenario="FI2", action="l3_override")
    for r in existing:
        d = r.get("decision", {})
        if d.get("ap_no") == ap_no and d.get("item_code") == item_code:
            return True
    return False


def confirm(
    ap_no: str,
    item_code: str,
    conclusion: str,
    reason: str,
    evaluator: str = "L3",
    audit: AuditLogger | None = None,
) -> int:
    """录入 L3 改判，返回 0=成功 / 1=失败。

    供测试与 CLI 共用；``audit`` 为 None 时自动初始化至默认路径。
    """
    if not reason or not reason.strip():
        print("错误：--reason 不可为空（IATF 要求改判原因留档）", file=sys.stderr)
        return 1

    if audit is None:
        _ROOT.joinpath("reports").mkdir(exist_ok=True)
        audit = AuditLogger.jsonl(_AUDIT_PATH)

    if _already_confirmed(audit, ap_no, item_code):
        print(
            f"警告：ap_no={ap_no!r} item_code={item_code!r} 已有改判记录，"
            "跳过重复写入（幂等）。如需修订，请联系 AI 系统管理员手工追加。"
        )
        return 0

    event = AuditEvent(
        scenario="FI2",
        action="l3_override",
        evaluator=evaluator,
        automation_level="L3",
        decision={
            "ap_no": ap_no,
            "item_code": item_code,
            "conclusion": conclusion,
        },
        data_sources={"input": "human"},
        override_reason=reason.strip(),
    )
    audit.record(event)
    print(f"✓ L3 改判已记录：ap_no={ap_no!r} item_code={item_code!r}")
    print(f"  结论：{conclusion}")
    print(f"  理由：{reason.strip()}")
    return 0


def main() -> None:
    ap = argparse.ArgumentParser(
        description="FI2 L3 改判录入 — needs_review 匹配项人工结案（审计留痕）"
    )
    ap.add_argument("--ap-no", required=True, help="应付单号")
    ap.add_argument("--item-code", required=True, help="料品编码")
    ap.add_argument("--conclusion", required=True, help="人工结论（简短描述，入审计报告）")
    ap.add_argument("--reason", required=True, help="改判原因（必填，知识资产台账用）")
    ap.add_argument("--evaluator", default="L3", help="责任人姓名（IATF 可归责，默认'L3'）")
    args = ap.parse_args()

    sys.exit(confirm(
        ap_no=args.ap_no,
        item_code=args.item_code,
        conclusion=args.conclusion,
        reason=args.reason,
        evaluator=args.evaluator,
    ))


if __name__ == "__main__":
    main()
