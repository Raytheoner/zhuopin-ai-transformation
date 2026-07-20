"""销售域实时数据接入 · 数据管道同步脚本

把 SalesMarketing/crm_data/dashboard_data.json 同步到本目录下的
data/sales_dashboard_data.json，供 AI运营指挥中心-框架原型-v0.1.html 内
fetch(SALES_DATA_URL) 读取（同源相对路径，免 CORS）。

隐私：Paul 2026-07-20 拍板——线索联系方式的访问范围（谁能看到真实姓名/电话/
邮箱）尚未与销售域接口人（泓钦）对齐前，落盘前一律脱敏；范围拍板后如需放开，
改这里的 PII_FIELDS/MASK 逻辑即可，其余渲染代码不用动。

范围：本脚本只覆盖"数据管道"这一段（仓库/本机侧）。命令中心本身正式部署到
.51（新端口/服务/计划任务）是另一项独立待办，见跨桌任务队列 #53 备注——
未随本脚本一并做。

用法：
    python sync_sales_data.py
建议节奏：SalesMarketing 自身的 CRM 同步（run_sync.ps1，本机每天 8:00 计划
任务 "销售易数据同步"）跑完之后手动执行一次本脚本即可刷新命令中心快照；
命令中心正式上线后可把本脚本纳入那次部署自己的刷新计划任务。
"""
import json
import sys
from pathlib import Path

SOURCE = Path(r"C:\Users\Paul Shao\OneDrive\Projects\SalesMarketing\crm_data\dashboard_data.json")
TARGET_DIR = Path(__file__).resolve().parent / "data"
TARGET = TARGET_DIR / "sales_dashboard_data.json"

MASK = "已脱敏"
PII_FIELDS = ("contact", "phone", "email")


def main() -> int:
    if not SOURCE.exists():
        print(f"[错误] 源文件不存在：{SOURCE}", file=sys.stderr)
        print("       请先确认 SalesMarketing 项目的同步脚本是否已跑过。", file=sys.stderr)
        return 1

    data = json.loads(SOURCE.read_text(encoding="utf-8"))

    leads = data.get("high_risk_leads", [])
    for lead in leads:
        for field in PII_FIELDS:
            if field in lead:
                lead[field] = MASK

    TARGET_DIR.mkdir(parents=True, exist_ok=True)
    TARGET.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    sync_time = data.get("sync_time", "(未知)")
    print(f"已同步：{TARGET}")
    print(f"  源数据 sync_time：{sync_time}")
    print(f"  高危线索已脱敏：{len(leads)} 条")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
