"""FI3 命令行入口（档 1）：跑一遍 mock 付款申请，输出 L3 旁路校验清单（Markdown）并写审计 JSONL。

    python -m fi3_payment_validation.run [--source mock] [--today 2026-09-17] [--out reports/fi3_checklist.md]
"""
from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

# —— 平台底座路径引导（队列 #345 收拢；唯一被允许的样板，实现见
# `5-平台底座/zhuopin_platform/zhuopin_platform/bootstrap.py`）。必须放在本文件任何
# zhuopin_platform / 场景包 import 之前。下方五行只负责让 bootstrap 自身可被 import、
# 不含任何判断分支；开发机 monorepo 与 `.51` 扁平部署两种布局的分歧由 ensure_paths 处理。——
_HERE = Path(__file__).resolve()
for _p in _HERE.parents:
    if (_p / "5-平台底座" / "zhuopin_platform").is_dir():
        sys.path.insert(0, str(_p / "5-平台底座" / "zhuopin_platform"))
        break
from zhuopin_platform.bootstrap import ensure_paths  # noqa: E402
ensure_paths(__file__, _HERE.parent.parent)  # noqa: E402

from zhuopin_platform.audit import AuditLogger  # noqa: E402
from zhuopin_platform.audit.sinks import JsonlSink  # noqa: E402

from fi3_payment_validation import config, dashboard, feed_source, validation_engine  # noqa: E402

_ROOT = _HERE.parent.parent


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="FI3 付款申请自动校验（L3 旁路清单）")
    ap.add_argument("--source", default=config.DATA_SOURCE_DEFAULT)
    ap.add_argument("--today", default=date.today().isoformat())
    ap.add_argument("--out", default=str(_ROOT / "reports" / "fi3_checklist.md"))
    ap.add_argument("--audit", default=str(_ROOT / "reports" / "fi3_audit.jsonl"))
    a = ap.parse_args(argv)

    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    logger = AuditLogger(JsonlSink(a.audit))
    ctx = feed_source.load_context(a.source, today=date.fromisoformat(a.today), audit_logger=logger)
    reqs = feed_source.load_payment_requests()
    verdicts = validation_engine.validate_batch(reqs, ctx)
    md = dashboard.render_markdown(verdicts)
    Path(a.out).write_text(md, encoding="utf-8")
    print(md)
    print(f"清单已写 {a.out}；审计 {a.audit}；跟踪清单 {len(ctx.tracking_list)} 条")
    return 0


if __name__ == "__main__":
    sys.exit(main())
