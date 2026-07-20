---
status: 在办
title: "Claude Code Desktop 开场 Prompt — SDD 流程收口 + SC1 工作区迁移（治理类，非新场景）"
created: 2026-07-02
来源: Cowork 对 skill 配置环境 + OpenSpec/SuperPowers 流程落地情况的全盘审计（2026-07-02）
用法: 在 Claude Code Desktop 新开 session，确认已打开 `企业AI转型` 文件夹后，复制下方整段粘贴。本次不需要 supplychain 文件夹（不碰真实库/新业务代码，纯治理收口）。
---

# 开场 Prompt（复制下方整段）

```
角色：你是卓品智能（汽车ECU Tier 1供应商）AI转型的首席AI架构师。我是分管供应链与质量的VP（Paul）。全程中文、代码中文注释。

第一步——恢复上下文（读完先别动手）：
1. 项目根目录 CLAUDE.md
2. 本文件所在目录的 0-学习与工具/Claude_Code开场Prompt-SDD流程收口与SC1迁移.md（就是你正在读的这份，包含全部任务清单）
读完用几句话回我你的理解，我确认后再开始。

本次任务性质：这不是新数字员工场景开发，是 Cowork 做的一次 SDD 配置与流程审计后的收口修补，全部在治理/工具层面，不新增业务逻辑。全部改动放一个分支 `chore/sdd-hygiene-2026-07`，每个阶段跑完测试、独立 commit，全部完成且回归全绿后再开 PR 合 master，不要一次性糊在一个大 commit 里。

审计原始发现（供你核对用，不要盲信，逐条自己验证一遍再动手）：
- 根目录 openspec/changes/ 下 o2-kit-shortage-alert（tasks.md 17/17 已勾）、platform-hardening-p2（27/27 已勾）已100%完工但从未 /opsx:archive。
- sc5-purchase-recommendation（26/28）剩的两个任务本身就是"8.5 archive、8.6 commit+push"，功能早完工，只差收尾。
- fix-a-security-compliance-p0（tasks.md 0/20）、fix-b-data-integrity-audit（0/22）、fix-c-sc8-golive-prereq（0/9）三个安全整改包，CLAUDE.md 里写着已经修复合并（对应 git log commit 30962ec / e606526 / ecd41f0+d77ef4c），但 tasks.md 一条都没勾，跟实际进度完全脱节。
- SC1（4-数字员工/采购部/SC1-供应商风险初筛/）有一整套独立的 .claude/commands/opsx、.claude/skills/openspec-*、openspec/（含自己的 config.yaml、changes/archive/2026-06-06-sc1-supplier-risk-screening、changes/sc1-platform-align 16/16已完工未归档、specs/{audit-log,manual-data-input,risk-report-generator,risk-scoring-engine}），跟其余场景共用根目录 openspec 工作区的模式不一致——这是SC1作为第一个场景时的历史遗留。
- 场景级 CLAUDE.md（Hermes L2）目前只有 SC1、FI1 两个场景有，SC3/SC5/SC8/O2/QD-B 没有。

Paul 已经拍板的两项决策（不需要再讨论，直接执行）：
① SC1 独立 openspec 工作区立即迁移合并进根目录，退休本地副本。
② 补齐 SC3/SC5/SC8/O2/QD-B 五个场景的 CLAUDE.md。

请按下面顺序做，每阶段做完停下报告结果，不要连着往下跑：

── 阶段1：归档已100%完工的变更（低风险，机械操作）──
按创建时间顺序逐个处理，每个都单独 openspec archive + validate + 回归测试 + commit，不要并批：
1. platform-hardening-p2（created 2026-06-10）
2. o2-kit-shortage-alert（created 2026-06-10）
3. sc5-purchase-recommendation（先补完 8.5/8.6 两个收尾任务，即本身就是这步）
每归档一个，跑一次 `openspec validate`，确认 openspec/specs/ 下出现了预期的新条目（platform-hardening-p2 应产出 audit-hash-chain/connector-schema-validation/secrets-provider/srm-rate-limiting 等；o2 应产出 kit-shortage-engine 相关；sc5 应产出 sc5-purchase-engine/sc5-kit-engine-platform 等），再跑一次相关测试确认没有回归，再 commit。如果 openspec archive 或 validate 报错/产生你没预期的 spec 合并冲突，停下来问我，不要自己猜着强行解决。

── 阶段2：补齐 fix-a/b/c 三个整改包的 tasks.md ──
这三个不是简单勾完就行——CLAUDE.md 说已经合并的内容要你自己逐条核实（读对应代码文件、跑对应测试），不是无脑照抄进度笔记直接打勾。核实口径：
- fix-a-security-compliance-p0：对照 CLAUDE.md 里 "A 安全 P0（已修，PR#10）" 那段描述（A1 TLS校验+逃生开关、A2 submit_commitment 首道入队+Notifier总开关、A3 verify_chain genesis豁免限定第1行），逐条核实代码里是否真的这样实现、对应测试是否存在且通过。
- fix-b-data-integrity-audit：对照 "B 数据正确性+审计强制化（已修，PR#11）"（B1 BOM失败不静默、B2 SRM区分失败与未答交、B3 审批分级、B4 from_env无audit→warn、B5 OEMRouter留痕、B6 kit_engine在途盲区+SC5黄金值精确相等）。
- fix-c-sc8-golive-prereq：对照 "C SC8上线前置（PR#12）"（C1偏差监控 sc8/deviation.py、C2真实黄金回归 build_golden_real.py）。
每一条只有你亲自验证过（代码存在+行为符合+有测试覆盖）才打 [x]；验证不了或发现名不副实的，保留未勾选并单独列出来告诉我，不要为了让清单好看瞎打勾——这份清单以后要当真相来源用。全部核实完、能归档的就归档（同阶段1的流程：archive→validate→测试→commit）。

── 阶段3：SC1 openspec 工作区迁移进根目录（Paul已拍板）──
目标：SC1 以后和 SC3/SC5/SC8/O2 一样，用根目录共享的 openspec 工作区，不再有自己独立一套。
具体做：
1. 把 SC1 本地 openspec/changes/archive/2026-06-06-sc1-supplier-risk-screening 作为历史记录原样迁入根目录 openspec/changes/archive/（保留原目录名，不要改内容，纯历史存档）。
2. 把 SC1 本地 openspec/changes/sc1-platform-align（16/16已完工）迁入根目录 openspec/changes/，然后在根目录跑 /opsx:archive 走正常归档流程，让它的 specs/ delta 正确合并进根目录 openspec/specs/（这样 audit-log、manual-data-input、risk-report-generator、risk-scoring-engine 这几个能力才会进入根目录的活规格库）。
3. 确认合并后没有 spec 命名冲突（根目录目前没有同名条目，理论上不会冲突，但你验证一遍）。
4. 删除 SC1 场景目录下的本地副本：.claude/commands/opsx/、.claude/skills/openspec-*/、openspec/ 整个目录（含它自己的 config.yaml）。SC1 本地 .claude/settings.local.json 里如果有根目录 settings.local.json 没覆盖到的有用 bash 权限，合并进根目录那份，否则也删掉——SC1 目录退化成一个普通的场景源码目录，不再有自己的 .claude。
5. 验证：从 SC1 场景目录里跑 openspec status，确认它能正确解析到根目录的工作区（而不是报错找不到 openspec）；跑 SC1 现有测试全绿；跑一次根目录 `openspec list`，确认能看到 SC1 历史变更。
这一步涉及删除文件，做完截图/贴一下 SC1 目录现在的样子给我确认，再继续阶段4。

── 阶段4：补齐场景级 CLAUDE.md（Paul已拍板）──
为这5个场景各建一份 CLAUDE.md：
- 4-数字员工/采购部/SC3-供应商在途跟踪与绩效/CLAUDE.md
- 4-数字员工/采购部/SC5-采购建议与供应商遴选/CLAUDE.md
- 4-数字员工/采购部/SC8-客户订单交期智能承诺/CLAUDE.md
- 4-数字员工/运营部/O2-物料齐套预警/CLAUDE.md
- 4-数字员工/质量部/QD-B-立项审核门禁/CLAUDE.md
模板照抄 4-数字员工/财务部/FI1-供应链仓库对账/CLAUDE.md 的结构（定位/关键决策记录/复用底座资产/红线/状态时间线/关键依赖前置六段式），内容来源：
- 根目录 CLAUDE.md 里关于该场景的进度叙述段落（把相关内容摘出来改写，不是复制粘贴大段文字）
- 该场景对应 openspec 变更的 design.md 里 "Paul 拍板" 部分
- 该场景 tasks.md 完成度 + git log 里该场景相关的 commit
- SC8 的还要标注清楚 CUSTOMER_OUTBOUND_ENABLED 现在是 False、对客外发闸门没开，这是最容易被后续会话忽略而踩坑的点，务必写进"红线"段。
- QD-B 的要标注质量域的 OEM 隔离边界扩展（含OEM信息的8D/客诉按客户隔离）。
写完后可以考虑：根目录 CLAUDE.md 里对应这几个场景的大段进度叙述是否可以精简、改成指向新场景CLAUDE.md的一句话摘要——这个不强制，你觉得根目录CLAUDE.md现在读起来是否已经过于臃肿，自己判断要不要顺手瘦身，瘦身的话要跟我说一声改了哪几段、原文对应挪去了哪个场景CLAUDE.md，别默默删掉。

── 阶段5：把"归档纪律"写进根目录 CLAUDE.md §5 ──
在 §5 工作流"每个场景固定流程"那五步后面，加一条明确纪律，大意是：任务全部勾选完成后，/opsx:archive 当次立即执行，不允许拖到下一个 session；如果因故做不到，收工前必须在 CLAUDE.md 或接力文件里显式写清楚"未归档 + 原因 + 谁跟进"，不能让"功能做完但变更游离在外"的情况无声堆积（这次审计就是因为这样堆了至少5个：o2/platform-hardening-p2/sc5/fix-a/fix-b/fix-c，还有SC1那个）。你可以用你自己的措辞写，风格贴合 CLAUDE.md 现有的口吻。

── 阶段6：声明 SuperPowers 项目域依赖（Cowork建议，把隐性全局依赖显式化）──
背景：OpenSpec 的 skill/命令已经在仓库里（.claude/commands/opsx、.claude/skills/openspec-*），任何人 clone 仓库都能直接用；但 SuperPowers（test-driven-development 等技能，本项目"先写测试再实现"纪律的来源）目前只装在当前机器的全局插件里，仓库里完全没有痕迹——换机器、来新人、甚至我换电脑，这条纪律会悄悄消失，git 里连个提示都没有。
具体做：
1. 去 code.claude.com/docs/en/plugins-reference 核对当前版本项目域插件声明的确切语法（不要凭空猜），大致方向是在根目录 .claude/settings.json 里加 extraKnownMarketplaces（指向 obra/superpowers-marketplace）+ enabledPlugins 声明启用 superpowers 插件。**注意**：官方仓库有已知 issue，enabledPlugins 写在 settings.local.json 里会被静默忽略——必须确认写进会被提交进 git 的 settings.json，不是 settings.local.json；另外即便声明了，外部来源插件也不会被自动装上，团队成员 clone 后还是要手动确认安装一次，这条声明的作用是"Claude Code 主动提示"，不是"自动拉起来"，如果你发现现在的 Claude Code 版本这个机制不稳定/有 bug，如实告诉我，不用勉强让它工作。
2. 在 CLAUDE.md 里（或你判断更合适的话新开 0-学习与工具/环境依赖清单.md）人话写清楚：本项目依赖 SuperPowers（obra/superpowers，版本以你机器上实际装的为准，Hermes_SuperPowers_协作架构.md 里记的是 v5.1.0）+ 具体依赖它的哪几个技能（test-driven-development / writing-plans / subagent-driven-development / requesting-code-review / executing-plans / dispatching-parallel-agents）+ 一行安装命令。这是兜底：万一①的项目域声明因为已知 bug 不生效，至少有人话版本让新人照着手动装对，不用重新发现一遍这个隐性依赖。
这一步不改任何代码/openspec变更，纯配置+文档，可以独立于阶段1-5之外随时做，不影响其他阶段的分支/commit节奏。

── 收尾 ──
全部阶段完成、测试全绿后，汇总一份简短报告：哪些变更被归档了、fix-a/b/c 里哪些任务验证后打了勾哪些没打（如果有）、SC1迁移后目录现在什么样、5份场景CLAUDE.md都建好了没有、SuperPowers项目域声明是否成功声明/有没有踩到已知bug、环境依赖清单写在哪了。开 PR 前先停下来给我看这份报告，我确认再合 master——这类改动虽然是治理性质，但触碰面广（openspec/specs 全局规格库 + 多个场景目录 + 插件配置），我想过一遍再合并。

明确不要动的东西（这些是我确认过、当前状态是对的，不要碰）：
- sc8-real-data-cutover（剩2个任务在等我审核偏差数据，不要归档，不要动）
- qd-b-project-gate-review（还在开发中，不要归档）
- fi1-warehouse-reconcile（财务专员反馈需求有变，暂停中，不要动）

现在开始：先读根目录 CLAUDE.md，回我理解，我确认后你再开始阶段1。
```

---

## 背景（给我自己看，不用念给CC）

这份 Prompt 对应的是 2026-07-02 Cowork 那次审计的全部发现和结论，原话见对话记录。核心问题是 OpenSpec 的"唯一可信源"价值在几个地方已经失效：变更完工了但没归档，导致活规格库(`openspec/specs/`)跟生产代码脱节；tasks.md 的勾选进度跟 CLAUDE.md 里手写的进度笔记两条线各说各话；SC1 因为是第一个场景，工作区没跟上后来确立的"共享根目录"惯例，一直游离在外。

两项已经拍板不用再讨论：SC1 工作区迁移、场景级 CLAUDE.md 补齐。其余（阶段1/2/5/6）是我给的建议，CC 执行过程中如果发现和预期不符（比如 fix-a/b/c 里真有没做完的任务、或者阶段6的插件声明机制根本不工作），应该如实报告，不是硬着头皮打勾/凑合过去。

阶段6是后续追加的（2026-07-02 同日，Paul 问"OpenSpec仓库域、SuperPowers全局域，这样有问题吗"引出的讨论）：结论不是要把两者强行拉到同一作用域——OpenSpec 的 CLI 本身也是全局装的，仓库里那套是它生成的项目数据，理应跟代码一起进 git 版本控制；SuperPowers 给的是没有项目数据的纯方法论技能，全局装本来就合理。真正的问题是 SuperPowers 这条依赖在仓库里"零留痕"，换机器/换人会无声失效——阶段6是补这个留痕，不是重新架构。

## 用完这份 Prompt 之后

这是一次性收口，不是新的常态流程，做完不需要再重复。往后只要 CLAUDE.md §5 加的那条"归档当次做"纪律被遵守，理论上不会再堆积。如果几个月后想再抽查一次，直接用同样的方法扫一遍 `openspec/changes/*/tasks.md` 完成度 vs 是否在 archive/ 目录里就行，不需要重新做全盘审计。
