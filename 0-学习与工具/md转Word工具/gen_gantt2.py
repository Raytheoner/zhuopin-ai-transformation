# -*- coding: utf-8 -*-
import subprocess
months=['7月','8月','9月','10月','11月','12月','1月','2月','3月','4月','5月','6月']
rows=['基建','采购/供应链','财务部','销售/BD','运营/制造','工程研发','质量']
colors={'基建':'#8a8f99','采购/供应链':'#2f6db0','财务部':'#2e8b8b','销售/BD':'#b07d2f','运营/制造':'#6a8f3a','工程研发':'#7a5ba6','质量':'#b0506a'}
TAIL='#dcdcdc'
data={r:{} for r in rows}
def put(r,c,label,kind='m'): data[r][c]=(label,kind)
put('基建',0,'AI基建');put('基建',1,'U9C申请★')
for i,sc in enumerate(['SC1','SC2','SC3','SC4','SC5','SC6','SC7','SC8','SC9']): put('采购/供应链',i,sc)
put('采购/供应链',10,'深化运营','t');put('采购/供应链',11,'全面成熟','t')
fi={2:'FI1',4:'FI2',6:'FI3',7:'FI4',8:'FI5',9:'FI6',10:'FI7',11:'FI8'}
for c,l in fi.items(): put('财务部',c,l)
for i,s in zip([2,3,4,5,6,7],['S1','S2','S3','S4','S5','S6']): put('销售/BD',i,s)
put('销售/BD',9,'深化→成熟','t')
for c,l in {3:'O2',4:'O1',5:'O3',6:'O4⚠'}.items(): put('运营/制造',c,l)
put('运营/制造',9,'深化→成熟','t')
for c,l in {3:'R1',4:'R2',5:'R3',6:'R4',7:'R5'}.items(): put('工程研发',c,l)
put('工程研发',9,'研发AI成熟','t')
for c,l in {3:'Q1',4:'Q2',5:'Q3',6:'Q4',7:'Q5',8:'Q6'}.items(): put('质量',c,l)
put('质量',10,'质量AI成熟','t')

def cell(content_bg_fg_size):
    return content_bg_fg_size
html=[]
html.append('<TABLE BORDER="0" CELLBORDER="0" CELLSPACING="4" CELLPADDING="6">')
# year header
html.append('<TR><TD></TD>'
            '<TD COLSPAN="6"><FONT POINT-SIZE="14"><B>2026 年</B></FONT></TD>'
            '<TD COLSPAN="6"><FONT POINT-SIZE="14"><B>2027 年</B></FONT></TD></TR>')
# months
mr='<TR><TD></TD>'
for m in months: mr+=f'<TD><FONT POINT-SIZE="12" COLOR="#444444">{m}</FONT></TD>'
mr+='</TR>'; html.append(mr)
# dept rows
for r in rows:
    row=f'<TR><TD ALIGN="RIGHT"><FONT POINT-SIZE="13"><B>{r}</B></FONT></TD>'
    for c in range(12):
        if c in data[r]:
            label,kind=data[r][c]
            bg=colors[r] if kind=='m' else TAIL
            fg='white' if kind=='m' else '#555555'
            sz=13 if (kind=='m' and len(label)<=3) else (10 if len(label)>4 else 11)
            bold='<B>' if kind=='m' else ''; boldc='</B>' if kind=='m' else ''
            row+=f'<TD BGCOLOR="{bg}"><FONT POINT-SIZE="{sz}" COLOR="{fg}">{bold}{label}{boldc}</FONT></TD>'
        else:
            row+='<TD BGCOLOR="#f4f6f9"> </TD>'
    row+='</TR>'; html.append(row)
html.append('</TABLE>')
table=''.join(html)
dot=f'''digraph G {{
 bgcolor="white"; rankdir=TB;
 graph [fontname="Droid Sans Fallback" label=<<FONT POINT-SIZE="17" COLOR="#1F4E79"><B>六部门并行时间线（2026年7月 → 2027年6月）</B></FONT>> labelloc="t"];
 node [shape=plaintext fontname="Droid Sans Fallback"];
 grid [label=<{table}>];
}}'''
open('/tmp/gantt.dot','w',encoding='utf-8').write(dot)
subprocess.run(['dot','-Tpng','-Gdpi=150','/tmp/gantt.dot','-o','/sessions/loving-pensive-hamilton/mnt/outputs/gantt.png'],check=True)
subprocess.run(['dot','-Tsvg','/tmp/gantt.dot','-o','/sessions/loving-pensive-hamilton/mnt/outputs/gantt.svg'],check=True)
print('ok')
