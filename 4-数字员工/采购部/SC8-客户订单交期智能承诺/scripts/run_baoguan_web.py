"""成品保供预警看板 —— 内网 Web 服务启动入口（design D10）。

启动：
  SC8_DATA_SOURCE=real python scripts/run_baoguan_web.py        # 默认 0.0.0.0:8090
  SC8_BAOGUAN_PORT=9000 SC8_DATA_SOURCE=real python scripts/run_baoguan_web.py

环境（仓库根 .env 自动读入）：
  FO_API_BASE / FORECAST_API_KEY        FO 预测订单接口（apiKey）
  U9C_* / XKY_*                          BOM（U9C OAuth2）/ 携客云承诺（分层取数）
  WECOM_WEBHOOK_URL 或 SC8_BAOGUAN_OPS_WEBHOOK_URL   真延期推送的保供运维群
  SC8_BAOGUAN_REFRESH_MIN（默认 60=1h）   定时后台刷新间隔（缓存新鲜度；看板读缓存秒开）
  SC8_SRM_ANSWER_TTL_MIN（默认 360=6h）   firm 承诺交期缓存有效期（提速立即重算；未答交始终重查）
  SC8_FO_STATUS（默认 2=已审核，all=不过滤）

红线：含真实客户名 → 仅 LAN（0.0.0.0 内网，无登录鉴权；外网访问+鉴权=待办#10）；
real 缺端点 fail-loud；快照/案例 DB 只落 reports/（git-ignored）；对客闸全程关闭。
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

SC8 = Path(__file__).resolve().parent.parent


def _find_env() -> Path | None:
    """从本脚本向上逐级查找最近的 `.env`（布局无关）。

    笔记本(monorepo)命中仓库根 .env；长开服务器扁平布局(C:\\baoguan\\app\\scripts\\…)
    命中 C:\\baoguan\\.env。凭据只在 .env，不入库。"""
    here = Path(__file__).resolve()
    for d in (here.parent, *here.parents):
        cand = d / ".env"
        if cand.exists():
            return cand
    return None


def load_env() -> None:
    """把最近的 .env 读入 os.environ（已存在的不覆盖）。凭据只在 .env，不入库。"""
    env = _find_env()
    if not env:
        return
    for line in env.read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def main() -> int:
    # Windows GBK 环境强制 UTF-8 输出，避免 emoji UnicodeEncodeError（同 supplychain）
    if sys.stdout.encoding and sys.stdout.encoding.lower() in ("gbk", "gb2312", "gb18030"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")

    load_env()

    from sc8 import config
    if config.data_source_mode() != "real":
        print("✗ 需 SC8_DATA_SOURCE=real 才启动真实保供 Web 服务（红线 §7.1）。", file=sys.stderr)
        return 2

    from zhuopin_platform.audit import AuditLogger
    from zhuopin_platform.audit.sinks import JsonlSink
    from zhuopin_platform.shared_tools.connector_audit import ConnectorAudit

    reports = SC8 / "reports"               # **/reports/ 已 gitignore（含真实客户名）
    reports.mkdir(parents=True, exist_ok=True)
    trace = ConnectorAudit(sink=JsonlSink(reports / "baoguan_access_trace.jsonl"))
    audit = AuditLogger(sink=JsonlSink(reports / "baoguan_audit.jsonl"))

    from sc8.baoguan_service import SnapshotStore
    from sc8.case_store import CaseStore
    from sc8.feedback_store import JsonlAppendStore
    from sc8.webapp import create_app, start_background_refresh

    snap_store = SnapshotStore(reports / "baoguan_snapshot.json")
    case_store = CaseStore(reports / "baoguan_cases.db")
    ops_hook = (os.environ.get("SC8_BAOGUAN_OPS_WEBHOOK_URL")
                or os.environ.get("WECOM_WEBHOOK_URL"))
    fo_status = os.environ.get("SC8_FO_STATUS", "2")
    fo_status = None if fo_status.lower() == "all" else fo_status
    refresh_min = int(os.environ.get("SC8_BAOGUAN_REFRESH_MIN", "60"))
    port = int(os.environ.get("SC8_BAOGUAN_PORT", "8090"))
    # firm 承诺缓存有效期（分钟，默认 360=6h）→ 提速立即重算；未答交始终重查
    srm_ttl_sec = int(os.environ.get("SC8_SRM_ANSWER_TTL_MIN", "360")) * 60

    # 队列 #112：轻量访问日志采集（时间/来源IP/动作，不采集个人身份）
    access_log_path = reports / "baoguan_http_requests.jsonl"
    # 队列 #110 Feature A/B：反馈按钮 JSONL + 判例包网页表单化（判例包定义由
    # Cowork 手写 JSON，放 sc8/case_reviews/，见 case_review.py 顶部说明）
    feedback_store = JsonlAppendStore(reports / "baoguan_feedback.jsonl")
    case_review_dir = SC8 / "sc8" / "case_reviews"
    case_review_store = JsonlAppendStore(reports / "case_review_submissions.jsonl")

    app = create_app(snapshot_store=snap_store, case_store=case_store,
                     audit=audit, trace=trace, ops_webhook_url=ops_hook,
                     fo_status=fo_status, cache_dir=reports, srm_ttl_sec=srm_ttl_sec,
                     access_log_path=access_log_path, feedback_store=feedback_store,
                     case_review_dir=case_review_dir, case_review_store=case_review_store)
    start_background_refresh(app, interval_min=refresh_min)

    print("成品保供预警看板 — Web 服务启动中…")
    print(f"  数据源 real · FO 状态过滤={fo_status or 'all'} · 定时刷新 {refresh_min} 分钟")
    print(f"  firm 承诺缓存 {srm_ttl_sec // 60} 分钟（提速立即重算；未答交始终重查）")
    print(f"  缓存/案例：{reports}（git-ignored，含真实客户名）")
    print(f"  真延期推送：{'已配置保供运维群' if ops_hook else '未配置（仅建案不推送）'}")
    print(f"  对客闸 CUSTOMER_OUTBOUND_ENABLED={config.CUSTOMER_OUTBOUND_ENABLED}（全程关闭）")
    print(f"  ⚠️ 仅 LAN 内部访问（无登录鉴权）；外网开放前须先加鉴权（待办#10）")
    try:
        from waitress import serve
        print(f"\n[OK] waitress 生产模式 · http://0.0.0.0:{port}/\n")
        serve(app, host="0.0.0.0", port=port, threads=4)
    except ImportError:
        print(f"\n[!] waitress 未安装，Flask 开发模式 · http://0.0.0.0:{port}/\n")
        app.run(host="0.0.0.0", port=port, debug=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
