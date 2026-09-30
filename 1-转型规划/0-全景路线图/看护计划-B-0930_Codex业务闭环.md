---
status: 在办
---
# B-0930_Codex业务闭环 · 人守看护件

当前批准：六入口设计 SHA256 723dccc1eedc8e06346a2765dc52e405887f30f06490570cbfab22c537f0b9d7；原v5 design SHA256 bd1b310f03c5b52c64f9ee2980ed9f19fa77e5987c8557e6df877d2a9b5e9d61。
本批只有 A1，零依赖、本地构建，不要求 LAN。固定源基线 245b0ea4aea114797eb1506b53081e01a0a6bd24；目标工作树已由原生工具建立，不从 master 重建。以下生成器模板的默认起点/自主push/心跳措辞，在本次 Guardian 正式执行中以此已批准外层绑定为准：模型只写阶段产物，外层负责提交、状态心跳和发布准备；不 push、不 ff。routine 为模板路由标签，实际派生模型由新版共享driver强制 gpt-6-luna。
实施只允许 0-学习与工具/codex-handoff/workflow_driver.py 与 0-学习与工具/codex-handoff/tests/test_workflow_driver.py。旧任务与设计批准原件不变。生产消费者/自动化、部署、外发和 L2 不在本批执行范围。

### A1 ·【Codex】新引擎闭环——队列 #648
▶ 粘贴端：Codex
泳道：op0930z-workflow-v5-mvp

```
[OP-0930-Z]【Codex】新引擎闭环
【设置】执行环境：Codex ｜ 分支：master（从 master 起 `codex/op0930z-workflow-v5-mvp`） ｜ worktree：☑（workflow-v5-mvp，保留不自删） ｜ 工作区：无 ｜ session：新开 ｜ 派出线：Codex迁移收口 B-0930_Codex业务闭环 ｜ 模型：routine
读 ① `openspec/changes/codex-business-entry-closure-0930/design.md` → ② `CLAUDE.md` 恢复上下文，按下述执行。本件为 A 类（口径已定、判据已写死），无需再问澄清，直接开工。

做什么：
1. 承接#648已批准v5，proposal原字节复制原包，核哈希后实施、CI、独立review、release-prep；所有模型子任务显式gpt-6-luna。
2. 使用既有工作树 C:/Users/Paul Shao/.codex/worktrees/workflow-v5-mvp/zhuopin-ai，不重建。

不做什么：
- 不ff、不启用生产消费者或自动化、不部署、不外发、不代L2；旧v5现场保留。
🔴 并行上限 4，超出排下一波，错峰 ≥90 秒（构建环境瘦身第三轮方案 P4）。
🔴 心跳一律跑命令写、不自己拼路径：开工 1 分钟内 `python 0-学习与工具/工具-泳道看护状态机.py heartbeat --lane op0930z-workflow-v5-mvp --text "已开工"`；每里程碑追加一行（等待 >10 分钟须补写「仍在等 X，预计还要 N 分钟」）；收工 `python 0-学习与工具/工具-泳道看护状态机.py heartbeat --lane op0930z-workflow-v5-mvp --done --batch B-0930_Codex业务闭环 --text "产出落点：<落点>"`——不带 `--batch` 该泳道不计入任何批（`heartbeat --done` 不带它就不计入任何批次的 `summary`，已实测撞过 8 条历史泳道）；它没有 `--repo-root`／`--heartbeat-file` 两个参数，别给（队列 §一 `#565`）。
🔴 自测只跑受影响测试类（node-id `pytest <文件>::<类名>`，禁 `-k`，禁跑整份回归——那是 ff 六关④的活，泳道再跑一遍＝同一件事做三遍）；测试输出一律重定向到文件、只读结论行；长任务不起后台任务轮询等待收尾，改用哨兵文件、大间隔探测，不逐分钟 tail（队列 §一 `#627`）。
🔴 收工只 push 本泳道分支，不碰主仓、不 ff master——主仓 ff 由看护者收工时串行做，或经『已授权待合』登记处由 `工具-待合分支巡检.ps1` 机器做；sweep 不做 ff（构建环境瘦身第三轮方案 P4，`#553` 更正）。
🔴 收工前自己跑 `git diff --name-only master...HEAD`，把输出原样贴进收工报告；期望产出点名的文件只要有一个不在清单里，就必须改以 `OPENER_PARTIAL` 收尾（不许判定为收工完成）——看护者按同一条命令机器核，不看哨兵自陈。本批若新增常驻状态告警类，须同批自陈「是否影响其它沙箱测试、用什么核的」（队列 §一 `#627`）。
🔴 新增常驻状态告警类须同批给出其它测试的沙箱夹具要求（哪些用例要补桩／改夹具，不能等上线后测试全红才回头查）；收工报告自陈「本次新增告警类是否影响其它沙箱测试、用什么核的」，只有结论没有手段不算（队列 §一 `#627` B 面）。
🔴 收工以顶格一行 `OPENER_DONE` 收尾；命中 🟡/🔴 决策点则以 `OPENER_PARTIAL: 停在<档位>决策点——<在等什么>` 收尾（`工具-opener批处理执行v2.ps1` 判成败双指标之一，缺它做完的活也会被判 NO-SENTINEL；队列 §一 `#550`）。
```

## 三bis 看护opener

本批由当前已获批准的 Codex 会话使用 Guardian 正式入口前台看护；前面的 A1 是子任务泳道，不另开看护者会话，不设置父任务标题。
