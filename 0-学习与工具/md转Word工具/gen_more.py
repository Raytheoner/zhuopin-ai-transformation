# -*- coding: utf-8 -*-
import subprocess
F='Droid Sans Fallback'
OUT='/sessions/loving-pensive-hamilton/mnt/outputs/'
def render(name, dot):
    open('/tmp/%s.dot'%name,'w',encoding='utf-8').write(dot)
    subprocess.run(['dot','-Tpng','-Gdpi=150','/tmp/%s.dot'%name,'-o',OUT+name+'.png'],check=True)
    subprocess.run(['dot','-Tsvg','/tmp/%s.dot'%name,'-o',OUT+name+'.svg'],check=True)
    print('ok',name)

# ---------- 启动 整体架构总览：阶段泳道 ----------
months=['7月','8月','9月','10月','11月','12月']
COL={'采购':'#2f6db0','研发':'#7a5ba6','质量':'#b0506a','财务':'#2e8b8b','销售':'#b07d2f','运营':'#6a8f3a'}
swim_rows=[
 ('采购部','采购',[('基建期',1),('试点期',1),('深化期',1),('扩展期',1),('全面试点',1),('成熟运营',1)]),
 ('工程研发','研发',[('',1),('',1),('',1),('R1 需求分析',1),('R2·R3 配置/审查',1),('R4·R5 用例/文档',1)]),
 ('质量部','质量',[('',1),('',1),('',1),('Q1 客诉分流',1),('Q2 8D 报告',1),('Q3 FMEA',1)]),
 ('财务部','财务',[('',1),('',1),('FI1 仓库对账',1),('',1),('FI2 月结加速',1),('',1)]),
 ('销售/BD','销售',[('',1),('',1),('S1 销售日报',1),('S2 拜访助手',1),('S3 RFQ 响应',1),('S4 技术文档',1)]),
 ('运营/制造','运营',[('',1),('',1),('',1),('O2 物料齐套',1),('O1·O3 排程/物流',1),('O4 预测维护',1)]),
]
h='<TABLE BORDER="0" CELLBORDER="0" CELLSPACING="4" CELLPADDING="6">'
h+='<TR><TD></TD>'+''.join('<TD><FONT POINT-SIZE="12" COLOR="#444"><B>%s</B></FONT></TD>'%m for m in months)+'</TR>'
for name,ck,cells in swim_rows:
    h+='<TR><TD ALIGN="RIGHT"><FONT POINT-SIZE="13"><B>%s</B></FONT></TD>'%name
    for label,span in cells:
        if label:
            h+='<TD BGCOLOR="%s"><FONT POINT-SIZE="11" COLOR="white"><B>%s</B></FONT></TD>'%(COL[ck],label)
        else:
            h+='<TD BGCOLOR="#f4f6f9"> </TD>'
    h+='</TR>'
h+='</TABLE>'
render('phase_timeline', f'digraph G{{bgcolor=white; graph[fontname="{F}" label=<<FONT POINT-SIZE="16" COLOR="#1F4E79"><B>采购先行 → 六部门并行（2026年7-12月）</B></FONT>> labelloc=t]; node[shape=plaintext fontname="{F}"]; g[label=<{h}>];}}')

# ---------- 全景 §5 第一阶段 7-12月 路线图（月份卡片）----------
def roadmap(name, title, cols):
    # cols: list of (month, headline, color, [items])
    cells=[]
    for month,head,color,items in cols:
        inner='<TABLE BORDER="0" CELLBORDER="0" CELLSPACING="0" CELLPADDING="4">'
        inner+=f'<TR><TD BGCOLOR="{color}"><FONT POINT-SIZE="12" COLOR="white"><B>{month}</B></FONT></TD></TR>'
        inner+=f'<TR><TD BGCOLOR="{color}"><FONT POINT-SIZE="9" COLOR="white">{head}</FONT></TD></TR>'
        for it in items:
            inner+=f'<TR><TD ALIGN="LEFT" BGCOLOR="#f4f6f9"><FONT POINT-SIZE="10">• {it}</FONT></TD></TR>'
        inner+='</TABLE>'
        cells.append(f'<TD VALIGN="TOP">{inner}</TD>')
    tbl='<TABLE BORDER="0" CELLBORDER="0" CELLSPACING="6" CELLPADDING="2"><TR>'+''.join(cells)+'</TR></TABLE>'
    render(name, f'digraph G{{bgcolor=white; graph[fontname="{F}" label=<<FONT POINT-SIZE="16" COLOR="#1F4E79"><B>{title}</B></FONT>> labelloc=t]; node[shape=plaintext fontname="{F}"]; g[label=<{tbl}>];}}')

roadmap('roadmap_h2','第一阶段：加速并行（2026年7-12月）',[
 ('7-8月','采购筑基','#2f6db0',['SC1 已上线','SC2 周报 ★','AI 基础设施','U9C MCP 申请','ISO26262 专题']),
 ('9月','SC3+三部门启动','#2f6db0',['SC3 绩效看板','FI1 仓库对账','S1 销售日报','O2 齐套预警']),
 ('10月','SC4+六部门入轨','#2f6db0',['SC4 合同提取','R1 需求分析','Q1 客诉分流','S2 拜访助手']),
 ('11月','SC5+各部门深化','#2f6db0',['SC5 供应商评分','FI2 月结加速','R2 AUTOSAR','O1 排程优化','Q2 8D 报告']),
 ('12月','SC6+持续推进','#2f6db0',['SC6 芯片预警','O3 物流追踪','R3 代码审查','Q3 FMEA','S3 RFQ / S4 文档']),
])
roadmap('roadmap_2027','第二阶段：跨部门协同（2027年1-3月）',[
 ('1月','SC7+跨部门协同','#7a5ba6',['SC7 库存优化','FI3 费用报销','R4 测试用例','Q4 PPAP 审核','S5 竞品监控','跨部门协同设计']),
 ('2月','SC8+联动试点','#7a5ba6',['SC8 交期承诺','FI4 异常交易','R5 技术文档','Q5 IATF 准备','S6 销售预测','Agent 联动灰度']),
 ('3月','SC9+联动推开','#7a5ba6',['SC9 OEM 预测','FI5 预算监控','Q6 立项门禁','跨部门 Agent 全面推开']),
])

# ---------- 全景 战略重心转移（3阶段）----------
strat=f'''digraph G{{rankdir=LR; bgcolor=white; node[shape=box style="rounded,filled" fontname="{F}" fontsize=12 margin="0.22,0.16"];
 edge[color="#5a6b7a"];
 A[label="2026年7-12月\\nAI 让现有工作更快\\n＋六部门场景全覆盖\\n（快速见效）" fillcolor="#dce9f6" color="#9bb4cc"];
 B[label="2027年1-6月\\n跨部门 Agent 协同\\n＋AI CoE 建立\\n（系统集成）" fillcolor="#e7dff2" color="#b3a0d6"];
 C[label="2027年7-12月\\nAI 改变工作方式本身\\n＋AI-First 工作模式\\n（战略差异化）" fillcolor="#d8efe0" color="#8fce9f"];
 A->B->C;
 graph[label=<<FONT POINT-SIZE="15" COLOR="#1F4E79"><B>战略重心转移：从效率工具到核心能力</B></FONT>> labelloc=t fontname="{F}"];
}}'''
render('strat_shift', strat)

# ---------- 全景 三类人才建设 ----------
talent=f'''digraph G{{rankdir=TB; bgcolor=white; node[shape=box style="rounded,filled" fontname="{F}" fontsize=11 margin="0.22,0.16"];
 edge[style=invis];
 A[label="A · AI Champion（每部门 1-2 人）\\n目标：能用 AI 解决本部门问题\\n培训：工具实操 8h ＋ 场景实践 4 周\\n激励：晋升加分 ＋ 内部讲师" fillcolor="#dce9f6" color="#9bb4cc"];
 B[label="B · AIOps 工程师（IT，2-3 人）\\n目标：开发与维护数字员工\\n培训：Claude API / MCP 40h ＋ 跟做首批\\n激励：专项奖金 ＋ 外部培训预算" fillcolor="#d8efe0" color="#8fce9f"];
 C[label="C · AI 战略顾问（VP ＋ 管理层）\\n目标：战略层决策 AI 投资与方向\\n培训：商业落地案例 ＋ 竞品跟踪 ＋ 外部交流" fillcolor="#fdeede" color="#e6c79a"];
 A->B->C;
 {{rank=same;A;B;C}}
 graph[label=<<FONT POINT-SIZE="15" COLOR="#1F4E79"><B>三类人才建设路径</B></FONT>> labelloc=t fontname="{F}"];
}}'''
render('talent', talent)

# ---------- 全景 跨部门联动场景 ----------
link=f'''digraph G{{rankdir=LR; bgcolor=white; node[shape=box style="rounded,filled" fontname="{F}" fontsize=10.5 margin="0.18,0.12"];
 edge[color="#b0506a" fontname="{F}" fontsize=9];
 subgraph cluster0{{label="① 供应链-质量联动" fontname="{F}" color="#ddd"; a1[label="采购 Agent\\n发现供应商风险下降" fillcolor="#dce9f6"]; a2[label="质量 Agent\\n生成物料风险评估" fillcolor="#fdeaee"]; a1->a2;}}
 subgraph cluster1{{label="② 研发-供应链联动" fontname="{F}" color="#ddd"; b1[label="研发识别\\n新芯片选型" fillcolor="#e7dff2"]; b2[label="采购检查\\n供货状态" fillcolor="#dce9f6"]; b3[label="高风险→\\n推替代方案" fillcolor="#fff3d6"]; b1->b2->b3;}}
 subgraph cluster2{{label="③ OEM 订单三联动" fontname="{F}" color="#ddd"; c1[label="销售测\\n大批量订单" fillcolor="#fdeede"]; c2[label="研发查\\nECU 版本" fillcolor="#e7dff2"]; c3[label="采购提前\\n拉动备料" fillcolor="#dce9f6"]; c1->c2->c3;}}
 subgraph cluster3{{label="④ 立项门禁全联动" fontname="{F}" color="#ddd"; d1[label="各部门\\n提交立项" fillcolor="#eee"]; d2[label="质量 Agent\\n自动门禁审核" fillcolor="#fdeaee"]; d3[label="通过→评审\\n否则→退回" fillcolor="#fff3d6"]; d1->d2->d3;}}
 graph[label=<<FONT POINT-SIZE="15" COLOR="#1F4E79"><B>跨部门 Agent 协同场景（2027 Q1）</B></FONT>> labelloc=t fontname="{F}"];
}}'''
render('linkage', link)
print('ALL DONE')
