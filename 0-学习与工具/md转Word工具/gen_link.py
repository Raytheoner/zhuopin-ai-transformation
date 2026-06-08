# -*- coding: utf-8 -*-
import subprocess
F='Droid Sans Fallback'; OUT='/sessions/loving-pensive-hamilton/mnt/outputs/'
# 定义顺序反转（④③②①），使输出自上而下为 ①②③④
link=f'''digraph G{{rankdir=LR; bgcolor=white; node[shape=box style="rounded,filled" fontname="{F}" fontsize=10.5 margin="0.18,0.12"];
 edge[color="#b0506a"];
 subgraph cluster3{{label="④ 立项门禁全联动" fontname="{F}" color="#cccccc"; d1[label="各部门\\n提交立项" fillcolor="#eeeeee"]; d2[label="质量 Agent\\n自动门禁审核" fillcolor="#fdeaee"]; d3[label="通过→评审\\n否则→退回" fillcolor="#fff3d6"]; d1->d2->d3;}}
 subgraph cluster2{{label="③ OEM 订单三联动" fontname="{F}" color="#cccccc"; c1[label="销售测\\n大批量订单" fillcolor="#fdeede"]; c2[label="研发查\\nECU 版本" fillcolor="#e7dff2"]; c3[label="采购提前\\n拉动备料" fillcolor="#dce9f6"]; c1->c2->c3;}}
 subgraph cluster1{{label="② 研发-供应链联动" fontname="{F}" color="#cccccc"; b1[label="研发识别\\n新芯片选型" fillcolor="#e7dff2"]; b2[label="采购检查\\n供货状态" fillcolor="#dce9f6"]; b3[label="高风险→\\n推替代方案" fillcolor="#fff3d6"]; b1->b2->b3;}}
 subgraph cluster0{{label="① 供应链-质量联动" fontname="{F}" color="#cccccc"; a1[label="采购 Agent\\n发现供应商风险下降" fillcolor="#dce9f6"]; a2[label="质量 Agent\\n生成物料风险评估" fillcolor="#fdeaee"]; a1->a2;}}
 graph[label=<<FONT POINT-SIZE="15" COLOR="#1F4E79"><B>跨部门 Agent 协同场景（2027 Q1）</B></FONT>> labelloc=t fontname="{F}"];
}}'''
open('/tmp/linkage.dot','w',encoding='utf-8').write(link)
subprocess.run(['dot','-Tpng','-Gdpi=150','/tmp/linkage.dot','-o',OUT+'linkage.png'],check=True)
subprocess.run(['dot','-Tsvg','/tmp/linkage.dot','-o',OUT+'linkage.svg'],check=True)
print('linkage fixed')
