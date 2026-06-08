# -*- coding: utf-8 -*-
import subprocess
F='Droid Sans Fallback'; OUT='/sessions/loving-pensive-hamilton/mnt/outputs/'
months=['1月','2月','3月','4月','5月','6月']
COL={'Agent':'#7a5ba6','研发':'#2f6db0','质量':'#b0506a','其他':'#6a8f3a'}
rows=[
 ('跨部门 Agent','Agent',['协同设计启动','联动试点','联动全面推开','AI CoE 试运行','AI CoE 成立','年度复盘+规划']),
 ('工程研发部','研发',['R1 深化运行','R2 助手试点','R3 全量上线','R4 上线','R5 上线','研发 AI 成熟']),
 ('质量部','质量',['Q1·Q2 运行','稳定运行','Q3 深化·Q4 试点','Q4 上线·Q5','Q5 上线·Q6','质量 AI 成熟']),
 ('其他四部门','其他',['深化运行','覆盖率提升','自动化 L2→L3','高阶场景上线','全场景覆盖','降本增效']),
]
h='<TABLE BORDER="0" CELLBORDER="0" CELLSPACING="4" CELLPADDING="6">'
h+='<TR><TD></TD>'+''.join('<TD><FONT POINT-SIZE="12" COLOR="#444"><B>%s</B></FONT></TD>'%m for m in months)+'</TR>'
for name,ck,cells in rows:
    h+='<TR><TD ALIGN="RIGHT"><FONT POINT-SIZE="12.5"><B>%s</B></FONT></TD>'%name
    for c in cells:
        h+='<TD BGCOLOR="%s"><FONT POINT-SIZE="10.5" COLOR="white">%s</FONT></TD>'%(COL[ck],c)
    h+='</TR>'
h+='</TABLE>'
dot=f'digraph G{{bgcolor=white; graph[fontname="{F}" label=<<FONT POINT-SIZE="16" COLOR="#1F4E79"><B>第二阶段：深化扩展 + 跨部门 Agent 协同（2027年1-6月）</B></FONT>> labelloc=t]; node[shape=plaintext fontname="{F}"]; g[label=<{h}>];}}'
open('/tmp/roadmap_2027.dot','w',encoding='utf-8').write(dot)
subprocess.run(['dot','-Tpng','-Gdpi=150','/tmp/roadmap_2027.dot','-o',OUT+'roadmap_2027.png'],check=True)
subprocess.run(['dot','-Tsvg','/tmp/roadmap_2027.dot','-o',OUT+'roadmap_2027.svg'],check=True)
print('roadmap_2027 swimlane rebuilt')
