# -*- coding: utf-8 -*-
import subprocess, os
F='Droid Sans Fallback'

levers=f'''digraph G{{
 rankdir=TB; bgcolor=white; node[shape=box style="rounded,filled" fontname="{F}" fontsize=12 margin="0.2,0.12"];
 edge[style=invis];
 t[label="AI 转型的三重战略杠杆" shape=plaintext fontname="{F}" fontsize=15 fontcolor="#1F4E79"];
 subgraph cluster0{{label="" color=white;
  A[label="竞争护城河\\n────────\\n更快的 NRE 报价\\n更精准的 APQP 管理\\n更短的 DV/PV 周期\\n差异化服务能力" fillcolor="#dce9f6" color="#9bb4cc"];
  B[label="运营效率\\n────────\\n供应链自动化决策\\n财务异常实时检测\\n研发文档自动生成\\n质量报告自动化" fillcolor="#d8efe0" color="#bcdcc6"];
  C[label="风险韧性\\n────────\\n芯片短缺预警\\n供应商风险早发现\\n客诉根因 AI 分析\\n单源替代方案智能推荐" fillcolor="#fdeede" color="#e6c79a"];
 }}
 t->A; A->B[constraint=false]; B->C[constraint=false];
 {{rank=same;A;B;C}}
}}'''

maturity=f'''digraph G{{
 rankdir=LR; bgcolor=white; node[shape=box style="rounded,filled" fontname="{F}" fontsize=12 margin="0.2,0.14"];
 edge[fontname="{F}" fontsize=10 color="#5a6b7a"];
 L1[label="Level 1 · 探索\\n（当前位置）\\n────────\\n个人使用 AI 工具\\n无标准流程 / 无 ROI 量化\\n无专职团队" fillcolor="#f0f0f0" color="#cccccc"];
 L2[label="Level 2 · 规模化试点\\n（2026年12月）\\n────────\\n4+ 部门有数字员工\\n统一治理框架\\nROI 可量化 / 有 AIOps" fillcolor="#dce9f6" color="#9bb4cc"];
 L3[label="Level 3 · 体系化运营\\n（2027年12月）\\n────────\\nAI 融入核心业务流程\\n跨部门 Agent 协同\\nAI CoE 建立" fillcolor="#d8efe0" color="#bcdcc6"];
 L1->L2->L3;
}}'''

arch=f'''digraph G{{
 rankdir=TB; bgcolor=white; compound=true; nodesep=0.3; ranksep=0.55;
 node[shape=box style="rounded,filled" fontname="{F}" fontsize=11 margin="0.16,0.09" color="#9bb4cc"];
 edge[color="#5a6b7a" arrowsize=0.8];
 subgraph cluster_sec{{ label="安全边界（数据安全层）"; fontname="{F}"; fontsize=13; style="rounded,filled"; fillcolor="#f7f9fc"; color="#c7d6e6";
  subgraph cluster_ai{{ label="AI 平台层"; fontname="{F}"; fontsize=12; style="rounded,filled"; fillcolor="#eef3f8"; color="#c7d6e6";
   AG1[label="工程研发\\nAgent" fillcolor="#dce9f6"]; AG2[label="采购供链\\nAgent" fillcolor="#dce9f6"];
   AG3[label="质量管理\\nAgent" fillcolor="#dce9f6"]; AG4[label="财务销售\\nAgent" fillcolor="#dce9f6"];
   ORC[label="MCP 工具编排层（工具调用 / 权限控制）" fillcolor="#fff3d6" color="#e0b84d"];
   subgraph cluster_kb{{ label="企业知识层 (RAG)"; fontname="{F}"; fontsize=11; style="rounded,filled"; fillcolor="#eaf5ee"; color="#bcdcc6";
    K1[label="技术知识库\\nAUTOSAR/MISRA" fillcolor="#d8efe0"]; K2[label="供应商库\\n风险评级/历史" fillcolor="#d8efe0"];
    K3[label="质量案例库\\n8D/FMEA/客诉" fillcolor="#d8efe0"]; K4[label="财务规则\\n账务规则" fillcolor="#d8efe0"];
   }}
   AG1->ORC; AG2->ORC; AG3->ORC; AG4->ORC; ORC->K1[lhead=cluster_kb];
  }}
 }}
 subgraph cluster_data{{ label="数据集成层"; fontname="{F}"; fontsize=12; style="rounded,filled"; fillcolor="#f0f0f0"; color="#cccccc";
  D1[label="ERP\\n(SAP/用友)" shape=cylinder fillcolor="#e6e6e6"]; D2[label="PLM (PDM)" shape=cylinder fillcolor="#e6e6e6"];
  D3[label="MES" shape=cylinder fillcolor="#e6e6e6"]; D4[label="CRM" shape=cylinder fillcolor="#e6e6e6"]; D5[label="外部 API" shape=cylinder fillcolor="#e6e6e6"];
 }}
 K1->D1[ltail=cluster_kb lhead=cluster_data];
}}'''

oem=f'''digraph G{{
 rankdir=TB; bgcolor=white; node[shape=box style="rounded,filled" fontname="{F}" fontsize=12 margin="0.18,0.12"];
 edge[color="#5a6b7a"];
 A[label="客户 A（比亚迪）\\n知识库实例 A\\n需求文档 A / ECU规格 A" fillcolor="#f9dada" color="#cc3333"];
 B[label="客户 B（上汽）\\n知识库实例 B\\n需求文档 B / ECU规格 B" fillcolor="#f9dada" color="#cc3333"];
 C[label="客户 C（理想）\\n知识库实例 C\\n需求文档 C / ECU规格 C" fillcolor="#f9dada" color="#cc3333"];
 P[label="统一 AI 平台（跨客户隔离）\\n⚠ 查询须显式指定客户上下文，自动路由对应知识库，禁止跨库查询" fillcolor="#fff3d6" color="#e0b84d"];
 A->P; B->P; C->P;
 {{rank=same;A;B;C}}
}}'''

matrix=f'''digraph G{{
 rankdir=TB; bgcolor=white; node[shape=box style="rounded,filled" fontname="{F}" fontsize=11 margin="0.2,0.14"];
 edge[style=invis];
 HV1[label="【9-10月】高价值·低难度\\n自动供应商评分\\n合同条款自动提取" fillcolor="#d8efe0" color="#bcdcc6"];
 HV2[label="【11-12月】高价值·高难度\\n需求预测辅助\\n库存优化建议" fillcolor="#dce9f6" color="#9bb4cc"];
 LV1[label="✅【7月】低价值·低难度\\n供应商风险初筛\\n（低难度、快见效）" fillcolor="#eaf5ee" color="#7fbf95"];
 LV2[label="【8-9月】低价值·高难度\\n采购周报自动生成\\n供应商绩效看板" fillcolor="#f3f3f3" color="#cccccc"];
 HV1->HV2; LV1->LV2;
 {{rank=same;HV1;HV2}} {{rank=same;LV1;LV2}}
 HV1->LV1;
 xlab[label="← 低难度          高难度 →" shape=plaintext fontname="{F}" fontsize=11 fontcolor="#666"];
 LV1->xlab[style=invis];
}}'''

diags={'levers':levers,'maturity':maturity,'arch_full':arch,'oem_iso':oem,'matrix':matrix}
for name,src in diags.items():
    open(name+'.dot','w',encoding='utf-8').write(src)
    subprocess.run(['dot','-Tpng','-Gdpi=150',name+'.dot','-o',name+'.png'],check=True)
    subprocess.run(['dot','-Tsvg',name+'.dot','-o',name+'.svg'],check=True)
    print('rendered',name)
