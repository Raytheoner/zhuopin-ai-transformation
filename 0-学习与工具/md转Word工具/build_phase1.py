import sys; sys.path.insert(0,'/tmp')
import md2docx_house as H
m={"cross-dept-agent（联动编排":"arch","无外部阻塞":"phase1_dep"}
H.build("/sessions/loving-pensive-hamilton/mnt/企业AI转型/1-转型规划/Phase1-基础设施与智能体架构设计.md",
 "/tmp/Phase1-基础设施与智能体架构设计.docx",
 "Phase 1 — 基础设施与智能体架构设计","工程落地设计草案 · House 默认 Word 式样",
 m,"/sessions/loving-pensive-hamilton/mnt/outputs")
