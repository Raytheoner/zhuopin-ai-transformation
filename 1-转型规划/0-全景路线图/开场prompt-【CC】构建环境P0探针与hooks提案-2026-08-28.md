---
title: "开场prompt-【CC】构建环境 P0 探针与 hooks 提案（OP-0828-P）"
created: 2026-08-28
执行方: CC（构建环境方向，队列 #433 棒 A1）
来源: 构建环境自动纠错与上下文治理-方案-2026-08-28.md（Shao Peishen 2026-08-28 拍板 1a/2a）
status: 待执行
编号: OP-0828-P
---

### P ·【CC】P0 五探针＋hooks 变更包 openspec 提案（P1，建议 48h 内开工）——队列 #433

> 与 OP-0828-Q（Cowork 瘦身棒）触碰区不重叠，**可并行**；本棒不部署任何 hook，只探针＋提案。

**开场词（复制即用，▶ 粘贴端：CC）**：

```
P0探针-OP0828P
【设置】执行环境：CC ｜ CC session：☑ 新建 ｜ worktree：☐ 不新建（此「不」只管 worktree——复用主仓 master 工作区；CC session 仍须新建） ｜ 分支：master ｜ 工作区：无（不触碰 .51 与常驻服务；openspec 产物落 openspec/ 常规路径） ｜ 派出线：Cowork 构建环境方案线（OP-0828）
🔴 开工第一件事：把本会话名设为 P0探针-OP0828P。工具＝mcp__ccd_session_mgmt__set_session_title，session_id 传字面量 "self"；该工具延迟加载，须先 ToolSearch 取 schema；返回值带出旧标题，据此确认已生效。
读 C:\Dev\zhuopin-ai\1-转型规划\0-全景路线图\开场prompt-【CC】构建环境P0探针与hooks提案-2026-08-28.md ＋ CLAUDE.md 当前进度恢复上下文，按文件执行；开干前按文件内预置的 3 个选择题问我澄清。
```

## 背景一分钟

Shao Peishen 2026-08-28 拍板《构建环境自动纠错与上下文治理》方案全案推进（1a）且支柱二 hooks 走 openspec design 审（2a）。本棒＝方案的 P0 期：**五个探针把二手信息全部换成本机实测**，再把 P1 三哨兵（H1 日期／H3 乱码／H4 代词）打包成 openspec 变更包出 design 稿交审。**本棒不实现、不部署任何 hook。**

## 权威依据（只指针）

① `1-转型规划/0-全景路线图/构建环境自动纠错与上下文治理-方案-2026-08-28.md` §五（探针清单与判定目标）、§四支柱二（六哨兵定义）、§九（合规判定）——本棒唯一需求正本
② `C:\Users\Paul Shao\.claude\settings.json` 与 `~\.claude\hooks\pretooluse-guard.ps1`——现有 hooks 范式参照（stdin JSON→exit 2、fail-open、timeout）
③ 根 `CLAUDE.md` §5「机制/工具类模块的 openspec 触发门槛」——变更包立项依据
④ 队列 §一 #433（本棒＝A1 子项）

## 开工前置步

1. **先取 §二 批次 `B-0828_17_OP0828PQ_构建环境方案落地` commit+push 销行**（Cowork 侧五件落库，清干净工作区再开探针）。
2. 按触碰区关键词（hooks／CLAUDE.md 瘦身／`.claude`）grep **两份队列真身＋《跨桌任务队列-归档-202608.md》**，确认无他人在办重叠；#433 状态列用 edit-row `--append` 登记「A1 已认领（日期）」。

## 任务分段

**A. 五探针（验收＝每项一段书面判定＋取证命令原文，「不可用」也是合格结论）**
- P0-1 hooks 在 Cowork 会话是否触发：请 Shao Peishen 在 Cowork 里做一次受控 Edit，查当日 `~\.claude\audit-*.log` 有无该 session_id；判定支柱二收益覆盖一桌还是两桌。
- P0-2 `.claude/rules/` paths 作用域：建最小试验件（用后即删），新 CC session 验证是否按 glob 注入；判定方案支柱一手段 D 成立与否。
- P0-3 auto-memory 是否存在/默认开启：/memory 实查；若在，写清其写入路径与 Desktop memory 容器的关系，**只报告、不启停**（裁定权在 Shao Peishen）。
- P0-4 子目录 CLAUDE.md 注入时机：/context 对比动与不动 `6-人才与组织/` 的差异，量化手段 C 收益。
- P0-5 H1 日期哨兵误拦风险面：不装 hook，只统计近两周队列/接力/README 的日期写入形态（grep 采样），估 warn 期误报面。
- 产出：`1-转型规划/0-全景路线图/构建环境P0探针报告-<当日Get-Date>.md`（🔴 日期本机重取，勿照抄本文件日期）。

**B. openspec 变更包（propose＋design，不实现）**
- 范围＝H1/H3/H4 三哨兵＋公共框架（脚本落 `0-学习与工具/hooks/`、项目 `.claude/settings.json` 挂接、fail-open＋timeout 10s、warn→block 节奏、audit-blocks 留痕、protected-paths 联动）；H2/H5/H6 写进 design 的「后续扩展」不进本包 scope。
- design.md 须含：每哨兵的判据来源（根 CLAUDE.md 对应人守条目）、误拦对策、Cowork 生效性按 P0-1 结论写入。
- 验收＝openspec validate 绿；收工报告注明「design 待 Shao Peishen 审，🛑 审过前不得开工实现」。

**C. 收工**：#433 回写 A1 子项（状态列 edit-row --append，✅/🟡 写在增量开头）；新增产出登 §二 新批次并自行 commit+push；重跑文档台账；探针五结论各一句进收工报告。

## 纪律段（指针）

跨桌任务队列开工必读/收工必写；编辑锁 acquire→写→release 两步查 `$LASTEXITCODE`；取号一律 `--reserve` 且先并入审核；状态头 ✅ 写在开头、有未完成写 🟡；三条静默失败写法禁令；时间戳写侧一律本机 `Get-Date` 重取；乱码哨兵开工收工各查一次；🔴 本棒红线＝**不改 `~\.claude\settings.json` 生产配置、不部署 hook、不动 `.51`**——protected-paths 拦 `.claude/settings.json` 属设计内行为，提案阶段不得绕。

## 预置澄清（开干前问，选择题）

1. 探针顺序：(a) P0-1 先行（它决定 design 里 Cowork 生效性结论，推荐）｜(b) 按 1-5 顺序。
2. 变更包范围：(a) H1/H3/H4＋框架（P1 范围，推荐）｜(b) 六哨兵全量入包。
3. 若 P0-1 证实 Cowork 不吃 hooks：(a) 照常出 design，收益面如实写「仅 CC」（推荐）｜(b) 暂停回报再议。
