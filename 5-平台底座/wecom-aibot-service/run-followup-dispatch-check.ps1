# 每日跟进信自动发信启动包装（由 register-followup-dispatch-task.ps1
# 生成，勿手改——重跑注册脚本会覆盖此文件）。绝对路径烘焙进来，不依赖
# 计划任务触发时的运行时 PATH（同落库 sweep/decision_reminder 惯例）。
#
# WECOM_AIBOT_QUEUE_PATH 显式指向主工作区队列文件（同 decision_reminder
# 既有教训）：dispatch_followup_letters.py 默认按自身 __file__ 反推仓库根，
# 若不显式指定，在本 ops/wecom-service-home worktree 里跑会读到**这个
# worktree 自己的 README/队列副本**（需手动同步、可能滞后）而非主工作区
# 实时内容，审计也会写进这个 worktree 自己的 reports/，与其余脚本分裂
# （正是队列 #126 修复过的同类问题）。显式设置后，resolve_repo_root 会
# 以这个路径为锚点动态解析出主工作区根，README/队列内容与审计落点都
# 对齐到唯一权威位置。
$env:WECOM_AIBOT_QUEUE_PATH = "C:\Dev\zhuopin-ai\1-转型规划\0-全景路线图\跨桌任务队列-机制环境.md"
& "C:\Users\Paul Shao\AppData\Local\Programs\Python\Python314\python.exe" "C:\Dev\zhuopin-ai\.claude\worktrees\wecom-service-home\5-平台底座\wecom-aibot-service\scripts\dispatch_followup_letters.py"
exit $LASTEXITCODE
