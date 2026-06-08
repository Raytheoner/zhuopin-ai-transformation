# -*- coding: utf-8 -*-
import subprocess
F='Droid Sans Fallback'; OUT='/sessions/loving-pensive-hamilton/mnt/outputs/'
dot=f'''digraph G{{
 rankdir=LR; bgcolor=white; compound=true; nodesep=0.28; ranksep=0.7;
 node[shape=box style="rounded,filled" fontname="{F}" fontsize=11 margin="0.16,0.10"];
 edge[color="#5a6b7a" arrowsize=0.8];
 subgraph cluster_now{{ label="无外部阻塞 · Phase 1 立即开工" fontname="{F}" fontsize=13 style="rounded,filled" fillcolor="#eaf5ee" color="#7fbf95";
   P0A[label="平台底座 zhuopin_platform\\n(audit/doc_parser/srm/isolation 骨架)" fillcolor="#d8efe0"];
   P0B[label="SC1 任务9.1 真实数据验证\\n→ v1.0 上线" fillcolor="#d8efe0"];
   P0C[label="IATF 审计 Hook（JSONL）" fillcolor="#d8efe0"];
 }}
 subgraph cluster_unlock{{ label="解依赖动作（Phase 1 必须并行启动）" fontname="{F}" fontsize=13 style="rounded,filled" fillcolor="#fff7e6" color="#e0b84d";
   U1[label="U9C ERP MCP 接口申请\\n★ 7月1日提交 IT" fillcolor="#fff0cc" color="#cc3333" penwidth=2];
   U2[label="外部芯片/物流 API 选型（8月）" fillcolor="#fff3d6"];
   U3[label="知识库建设派任务\\n客诉库/立项黄金标准/标准条款库" fillcolor="#fff3d6"];
   U4[label="OEM 数据隔离方案（8月）" fillcolor="#fff3d6"];
   U5[label="ISO 26262 AI 规范专题（7月启动）" fillcolor="#fff3d6"];
 }}
 subgraph cluster_w2{{ label="解依赖后按序上线（原型可先行）" fontname="{F}" fontsize=13 style="rounded,filled" fillcolor="#eef3f8" color="#9bb4cc";
   FI1[label="FI1 仓库对账" fillcolor="#dce9f6"];
   SC6[label="SC6 芯片预警" fillcolor="#dce9f6"];
   Q1[label="Q1 客诉分流" fillcolor="#dce9f6"];
   SC2[label="SC2 采购周报" fillcolor="#dce9f6"];
   Q6[label="Q6 立项门禁（建议维持后置）" fillcolor="#dce9f6"];
 }}
 P0A->P0B;
 P0A->FI1; P0A->SC6; P0A->Q1; P0A->SC2; P0A->Q6;
 U1->FI1; U1->SC2; U2->SC6; U3->Q1; U3->Q6; U3->FI1; U4->Q1;
 graph[label=<<FONT POINT-SIZE="16" COLOR="#1F4E79"><B>Phase 1 依赖关系：什么能现在干，什么被卡住</B></FONT>> labelloc=t fontname="{F}"];
}}'''
open('/tmp/phase1_dep.dot','w',encoding='utf-8').write(dot)
subprocess.run(['dot','-Tpng','-Gdpi=150','/tmp/phase1_dep.dot','-o',OUT+'phase1_dep.png'],check=True)
subprocess.run(['dot','-Tsvg','/tmp/phase1_dep.dot','-o',OUT+'phase1_dep.svg'],check=True)
print('phase1_dep ok')
