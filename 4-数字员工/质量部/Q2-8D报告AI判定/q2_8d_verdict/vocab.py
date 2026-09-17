"""词表层：V3.2 判定逻辑里点名的关键词，逐条抄自规则 `criteria` 原文（不扩写、不猜近义）。"""
from __future__ import annotations

import re

DATE_RE = re.compile(r"(20\d{2}[-/.年]\s?\d{1,2}[-/.月]\s?\d{1,2}日?)|(20\d{2}[-/.年]\d{1,2}月?)")
PHASE_WORDS = ("DV阶段", "PV阶段", "SOP", "试制", "量产", "样件", "小批", "EVT", "DVT", "PVT")
NUMBER_RE = re.compile(r"\d+(\.\d+)?\s*(%|pcs|PCS|件|个|台|次|批|ppm|PPM|mm|MHz|kHz|Hz|V|A|mA|Ω|℃|°C|h|min|s)")
WHY_RE = re.compile(r"为什么|为何|WHY", re.IGNORECASE)

# D1 跨职能（通用：任意 2 个领域；研发 D1-R1：软件/硬件/测试/系统/质量 ≥3）
FUNCTIONS_MFG = ("质量", "生产", "工程", "采购")
FUNCTIONS_RND = ("软件", "硬件", "测试", "系统", "质量")
FUNCTIONS_ALL = tuple(dict.fromkeys(FUNCTIONS_MFG + FUNCTIONS_RND + ("工艺", "研发", "制造", "SQE", "PE", "QE")))
ROLE_WORDS = FUNCTIONS_ALL + ("工程师", "经理", "主管", "组长", "技术员", "操作员", "负责人", "部")
# 「姓名／部门或角色」配对：`张三（质量）` `质量：张三` `张三/质量工程师` `张三 - 生产` ；表格行 `| 张三 | 质量 |`
NAME_ROLE_PAIR_RE = re.compile(
    r"([一-龥]{2,4})\s*[（(/\-—:：|｜]\s*[^\n）)|｜]{0,12}?(" + "|".join(ROLE_WORDS) + r")"
    r"|(" + "|".join(ROLE_WORDS) + r")[^\n]{0,6}?[:：/\-—|｜]\s*([一-龥]{2,4})"
)

# D2 What / Where / Who（M10(a)：通用条用并集，场景条用各自表）
OBJECT_WORDS_MFG = ("零件号", "产品型号", "工序", "件号", "料号", "P/N", "PN")
OBJECT_WORDS_RND = ("ECU", "软件版本", "硬件版本", "SW", "HW", "控制器")
LOCATION_WORDS_MFG = ("产线", "工位", "工序", "仓库", "客户端", "线体")
LOCATION_WORDS_RND = ("台架", "HIL", "实车", "道路测试", "EMC", "整车")
WHO_WORDS = ("客户", "供应商", "车型", "平台", "项目", "部门", "责任部门", "主机厂")
SCRUB_TOKEN_RE = re.compile(r"【(客户|供应商|平台|项目)[A-Z0-9]*】|\[(CUST|SUPP|OEM)_[A-Z0-9]+\]")
TRACE_WORDS_MFG = ("件号", "料号", "P/N", "批次", "Lot", "LOT")
POSITION_WORDS_MFG = ("产线", "工位", "工序")
SW_VERSION_WORDS = ("版本号", "SW Version", "软件版本", "分支", "Branch", "基线", "Baseline")
HW_VERSION_WORDS = ("HW Version", "硬件版本", "BOM", "原理图版本", "PCB版本")
RND_EVIDENCE_WORDS = ("故障码", "DTC", "CAN log", "CAN日志", "示波器", "波形", "log文件", "测试数据")

# D3 遏制范围
CONTAIN_SCOPE_MFG = ("在制品", "在途", "在库", "客户端", "原材料")
CONTAIN_SCOPE_RND = ("已发布", "在研", "在测", "已装车", "已OTA")
# 判例 4 子字段（客户端＋供应商端各 8 项）
D3_SUBFIELDS = ("区域", "数量", "措施", "结果", "负责人", "计划日", "完成日", "状态")
D3_SUBFIELD_ALIASES = {
    "区域": ("区域", "范围", "地点"), "数量": ("数量", "数", "pcs", "件"), "措施": ("措施", "对策", "动作"),
    "结果": ("结果", "效果"), "负责人": ("负责人", "责任人", "执行人"), "计划日": ("计划日", "计划完成", "计划日期"),
    "完成日": ("完成日", "实际完成", "完成日期"), "状态": ("状态", "进度", "已完成", "进行中"),
}
D3_SIDES = ("客户端", "供应商端")

# D4
TOOL_WORDS = ("5Why", "5 Why", "五个为什么", "鱼骨图", "FTA", "DOE", "故障注入", "代码走查", "静态分析", "故障树", "因果图")
M5E1_DIMS = {
    "人": ("人员", "人为", "操作员", "人/"), "机": ("设备", "机器", "机台", "机/"), "料": ("材料", "物料", "来料", "料/"),
    "法": ("方法", "工艺", "SOP", "法/"), "环": ("环境", "温湿度", "环/"), "测": ("测量", "检测", "量具", "测/"),
}
SURFACE_CAUSE_WORDS = ("操作失误", "疏忽", "不小心", "代码bug", "代码 bug", "硬件故障", "程序错误", "电路故障", "人为失误", "员工失误")
VERIFY_WORDS = ("验证", "再现", "复现", "对比", "试验", "走查", "仿真", "统计", "数据对比")

# D6 / D7
UPDATE_WORDS = ("更新", "修订", "修改", "新增", "已完成", "升版", "版本", "增加", "变更")
FILLED_N_RE = re.compile(r"(FMEA|PFMEA|DFMEA|控制计划|CP|Control Plan)[^\n]{0,15}?[:：|｜\s]\s*(N|否|无|不适用|N/A)\b", re.IGNORECASE)
DOC_WORDS_MFG = ("SOP", "作业指导书", "检验标准", "巡检表", "作业规范")
DOC_WORDS_RND = ("设计规范", "编码规范", "需求文档", "测试规范")
FMEA_WORDS = ("FMEA", "PFMEA", "DFMEA", "控制计划", "Control Plan", "CP更新")
CP_WORDS = ("控制计划", "Control Plan", "CP更新", "防错", "Poka-Yoke", "防呆")
TRAIN_WORDS = ("培训", "宣贯", "教育", "考核")
REGRESSION_WORDS = ("回归测试", "Regression Test", "全量测试", "自动化测试")
TESTCASE_WORDS = ("测试用例补充", "补充测试用例", "边界条件", "异常场景", "故障注入测试", "新增用例")
STATIC_WORDS = ("静态分析", "代码扫描", "Coverity", "QAC", "MISRA")
RND_FIX_WORDS = ("FMEA", "DFMEA", "测试用例", "设计规范", "编码规范")


def hits(text: str, words: tuple[str, ...]) -> list[str]:
    """命中的关键词（大小写不敏感，去重保序）。"""
    low = text.lower()
    return [w for w in dict.fromkeys(words) if w.lower() in low]
