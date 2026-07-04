"""测试共享夹具 — 合成8D文档（不含真实数据）。"""
from __future__ import annotations

from pathlib import Path

import pytest

SYNTHETIC_8D_TEXT = """\
8D报告 — 案例编号: 8D-2026-031
客户：某工程机械厂

D1: 小组成员
组长：质量工程师张明；成员：计划工程师李华、电子工程师王强。

D2: 问题描述
产品型号 ZK8808（某车型平台-A）在高温环境（≥85°C）下运行约2小时后，
偶发电源模块异常重启（约3次/百小时），料号 ZK-ECU-088 受影响。
现象首次出现日期：2026-04-10；客户工厂-A 现场报告。

D3: 临时对策
2026-04-12已对在线产品实施百分百高温测试（85°C，4h），剔除不良品。
通知供应商-A 暂停发货，已隔离库存约50件。

D4: 根本原因
根本原因（5Why）：
1. 电源模块在高温下重启 → 稳压芯片VCC输出跌落
2. VCC输出跌落 → 电容-A（Y5V材料）高温下容量下降>30%
3. 电容容量下降 → 规格书选料时未考虑工作温度降额
4. 选料未降额 → 物料采购规范缺少高温降额要求
5. 规范缺失 → 制程工艺规范中物料选型章节未更新
根本原因确认：制程/工艺规范缺陷（物料选型规范未包含高温降额要求）。

D5: 纠正措施
修订《物料选型规范》，增加高温降额要求（≥105°C工况器件须降额50%使用）。
对 ZK-ECU-088 电容-A 由Y5V更换为X5R规格，更改BOM版本至Rev.B。

D6: 措施实施
2026-05-10 完成规范修订并发布；BOM修订版本已入ERP系统。
供应商-A 已按新规格打样并通过验证。

D7: 预防措施及有效性验证
更新DFMEA条目 DFMEA-045，新增高温降额失效模式。
2026-06-01 完成30台改版产品高温老化验证（150h，95°C），全部通过，
验证结论：根因验证有效，改版后无复发。

D8: 关闭
结案日期：2026-06-15
8D报告已关闭，纠正措施有效，案例归档。
"""


@pytest.fixture
def synthetic_docx(tmp_path) -> Path:
    """生成合成8D文档（docx格式），用于测试。"""
    from docx import Document  # type: ignore
    doc = Document()
    for line in SYNTHETIC_8D_TEXT.splitlines():
        doc.add_paragraph(line)
    out = tmp_path / "sample_8d.docx"
    doc.save(str(out))
    return out


@pytest.fixture
def golden_csv(tmp_path) -> Path:
    """生成对应的人工黄金样本CSV（与合成8D对应）。"""
    import csv
    out = tmp_path / "golden.csv"
    fields = {
        "案例ID": "8D-2026-031",
        "客户(脱敏)": "OEM-B-01",
        "失效现象描述": "电源模块在高温环境下偶发异常重启，料号ZK-ECU-088受影响",
        "不良分类": "制程",
        "安全相关": "否",
        "临时对策(D3)": "百分百高温测试剔除不良品；隔离库存；通知供应商暂停发货",
        "根本原因(D4)": "物料选型规范缺少高温降额要求；电容Y5V高温容量下降超过30%",
        "纠正/预防(D5-D7)": "修订物料选型规范；BOM更换X5R电容；更新DFMEA",
        "关联FMEA条目": "DFMEA-045",
        "关联物料/供应商": "ZK-ECU-088",
        "结案日期": "2026-06-15",
        "根因验证有效": "是",
    }
    with open(out, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(fields.keys()))
        writer.writeheader()
        writer.writerow(fields)
    return out
