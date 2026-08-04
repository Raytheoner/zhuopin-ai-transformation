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

队列 #108①（外部第二次交叉审核采纳项）：源路径原硬编码本机绝对路径，改为
环境变量 `SALES_CRM_DATA_PATH` 可覆盖，未设置时回落原硬编码默认值（现状
零改变，仅新增可覆盖口）。
"""
import json
import os
import sys
from pathlib import Path

DEFAULT_SOURCE = Path(r"C:\Users\Paul Shao\OneDrive\Projects\SalesMarketing\crm_data\dashboard_data.json")
SOURCE = Path(os.environ.get("SALES_CRM_DATA_PATH", str(DEFAULT_SOURCE)))
TARGET_DIR = Path(__file__).resolve().parent / "data"
TARGET = TARGET_DIR / "sales_dashboard_data.json"

MASK = "已脱敏"
PII_FIELDS = ("contact", "phone", "email")


def desensitize_leads(leads):
    """对 high_risk_leads 列表逐条脱敏 PII_FIELDS，原地修改并返回同一个列表。

    队列 #108③ 边界单测覆盖的脏数据形态：
    - 列表中混入非 dict 条目（脏 JSON）——该条目原样保留，不强行脱敏、不中断
      其余合法条目的处理；
    - 某条目缺 PII_FIELDS 中的某个/全部字段——沿用既有 `if field in lead` 判据，
      缺字段即跳过，不补空字段；
    - PII 字段值本身是嵌套结构（如 `{"phone": {"mobile": "123"}}`，嵌套异常）——
      整个字段值直接替换为 MASK 字符串，不递归探查嵌套内容，从根源避免脱敏
      逻辑本身泄露嵌套结构里的敏感字段。
    """
    for lead in leads:
        if not isinstance(lead, dict):
            continue
        for field in PII_FIELDS:
            if field in lead:
                lead[field] = MASK
    return leads


def main() -> int:
    if not SOURCE.exists():
        print(f"[错误] 源文件不存在：{SOURCE}", file=sys.stderr)
        print("       请先确认 SalesMarketing 项目的同步脚本是否已跑过。", file=sys.stderr)
        return 1

    data = json.loads(SOURCE.read_text(encoding="utf-8"))

    leads = data.get("high_risk_leads", [])
    if not isinstance(leads, list):
        # 脏 JSON：high_risk_leads 字段存在但类型不对（如被写成字符串/对象），
        # 不强行遍历导致崩溃，按"本次无高危线索"处理，其余字段正常落盘。
        leads = []
    leads = desensitize_leads(leads)
    data["high_risk_leads"] = leads

    TARGET_DIR.mkdir(parents=True, exist_ok=True)
    TARGET.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    sync_time = data.get("sync_time", "(未知)")
    print(f"已同步：{TARGET}")
    print(f"  源数据 sync_time：{sync_time}")
    print(f"  高危线索已脱敏：{len(leads)} 条")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
