# -*- coding: utf-8 -*-
import sys; sys.path.insert(0,'/tmp')
import md2docx_house as H
BASE="/sessions/loving-pensive-hamilton/mnt/企业AI转型"
IMG="/sessions/loving-pensive-hamilton/mnt/outputs"
pano_map={"更快的 NRE 报价":"levers","Level 1 (探索)":"maturity","MCP 工具编排层":"arch_full","知识库实例 A":"oem_iso","SC1 SC2 SC3":"gantt","采购筑基":"roadmap_h2","降本增效":"roadmap_2027","供应链-质量联动":"linkage","AI 让现有工作更快":"strat_shift","三类人才建设":"talent"}
H.build(BASE+"/1-转型规划/卓品智能AI转型全景规划.md", "/tmp/卓品智能AI转型全景规划.docx",
        "卓品智能 AI 转型全景规划", "总纲 · House 默认 Word 式样", pano_map, IMG)
H.build(BASE+"/2-试点项目/从采购部启动.md", "/tmp/从采购部启动.docx",
        "AI 转型试点路线图 — 从采购部启动", "试点路线图 · House 默认 Word 式样", {"高价值 ▲":"matrix","基建期":"phase_timeline"}, IMG)
print("DONE")
