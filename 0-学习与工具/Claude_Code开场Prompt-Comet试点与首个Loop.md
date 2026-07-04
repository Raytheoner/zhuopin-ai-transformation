---
title: "Claude Code Desktop 开场 Prompt — Comet 试点 + 第一个 Loop Engineering 试验（工具引入类，非新场景）"
created: 2026-07-02
状态: "⏸ 暂缓（Paul 2026-07-02 拍板）——不要执行这份 Prompt。原因：项目当前阶段业务场景仍需大量人工判断，且 Comet 框架尚年轻，暂不引入。重启条件：① 项目场景需求收敛（业务判断依赖降低）；② Comet 框架进一步成熟（建议 S2 收口前后，约 2027-05/06，重新评估一次是否具备条件，不是硬性日期，视条件是否成立而定）。现有 SDD（OpenSpec+Superpowers）双星流程原样保留，不受影响。若未来重启，先重新过一遍本文件确认内容是否仍适用（Comet 版本/文章信息可能已过时），不要直接照抄执行。"
来源: Cowork 与 Paul 关于「OpenSpec仓库域/SuperPowers全局域」+「Comet编排层」+「Loop Engineering」的讨论（2026-07-02）
用法: 【暂缓，见上方状态】原计划：在 Claude Code Desktop 新开 session，确认已打开 `企业AI转型` 文件夹后，复制下方整段粘贴。这份 Prompt 建立在 `0-学习与工具/Claude_Code开场Prompt-SDD流程收口与SC1迁移.md` 之上。
---

# 开场 Prompt（复制下方整段）

```
角色：你是卓品智能AI转型的首席AI架构师。我是分管供应链与质量的VP（Paul）。全程中文，代码中文注释。

第一步——恢复上下文（读完先别动手）：
1. 项目根目录 CLAUDE.md
2. 0-学习与工具/Claude_Code开场Prompt-SDD流程收口与SC1迁移.md（阶段1-6的原始任务清单，本次试点就是拿这份工作里的一部分当试验田）
3. 本文件（0-学习与工具/Claude_Code开场Prompt-Comet试点与首个Loop.md）
读完回我理解，我确认后再开始。

本次任务性质：这是一次工具引入试点，不是新场景开发。两个目的：① 评估 Comet（github.com/rpamis/comet，OpenSpec+Superpowers编排层，npm包 @rpamis/comet）能不能安全接进我们的SDD流程；② 把"SDD收口工作"里符合条件的部分，改造成我们的第一个 Loop Engineering 试验——一个有明确机器可验证终止条件、有限范围、失败即停不瞎猜的自动化循环骨架。全部改动放 chore/sdd-hygiene-2026-07 分支（如果还没建），跟原 Prompt 里阶段3/4/5的手工工作分开走、互不阻塞。

为什么要这样拆分（供你理解，不是我瞎拍的，你可以质疑但先按这个来）：
Loop Engineering 只适合"可重复 + 有客观机器可验证通过/失败标准"的任务，明确不适合探索性/需要人工判断的任务——这是"Loop Engineering 完整解读"那篇文章反复强调的边界，我们认可这个边界，不打算突破它。据此：
- 阶段1（归档已100%完工的变更）、阶段2（核实fix-a/b/c并归档）、阶段6（SuperPowers项目域依赖声明）——这三个有客观验证标准（openspec validate 通过/测试全绿/代码确实存在且被测试覆盖），适合当 Comet + Loop 的试验田，本次任务只处理这三个。
- 阶段3（SC1迁移，涉及删文件+目录重组判断）、阶段4（写5份场景CLAUDE.md，创造性写作）——这两个不是"机器可验证正确"的任务，继续按原 Prompt 的手工流程走，每步停下等我确认，**不要**往 Comet/Loop 里塞，这次任务不涉及它们。
- 阶段5（CLAUDE.md加一条纪律）是个小文档编辑，风险低，维持手工做，不单独为它走 Comet。

请严格按下面顺序做，每步做完停下报告，不要连着往下跑：

── 第0步：Comet 尽调（试点前必须做，不能跳过）──
在真正执行 `npm install -g @rpamis/comet` 之前：
1. 读 github.com/rpamis/comet 的 README、package.json、核心脚本（尤其 comet-hook-guard.sh 这个 PreToolUse hook，以及 comet-archive.sh、comet-state.sh、comet-handoff.sh）。确认：没有网络回传/遥测调用、不需要任何外部 API key 或密钥、脚本实际行为跟公开介绍一致、开源协议允许我们这样用在内部工程流程里、最近的 commit/issue 里有没有关于 auto_transition 或 hook 误伤/绕过的已知问题。
2. 把尽调结果（哪怕只有几行结论）报告给我，我确认"可以装"之后你再继续。这一步不装任何东西，纯读代码/文档。

── 第1步：安装 + 在隔离沙盒里验证人工审批门没被削弱 ──
1. `npm install -g @rpamis/comet`，`comet init`（项目域 scope、中文），确认它按介绍自动检测/安装了 OpenSpec skills 和 Superpowers skills，并且检查这会不会跟我们仓库里已有的 `.claude/commands/opsx`、`.claude/skills/openspec-*` 冲突或覆盖——如果会冲突，停下报告我，不要硬装。
2. 建一个完全无关痛痒的测试用 openspec change（例如"给 README 加一句无害说明"这种，绝对不碰任何真实场景代码），走一遍 Comet 的 open→design→build→verify→archive 五阶段，重点验证两件事：
   a. **design 阶段是否真的会停下来等我在对话里明确回复确认，而不是只要 design.md 文件存在就被 auto_transition 自动判定"完成"往下跳**——这是我最担心的地方。如果 auto_transition 会绕开这道人工门，必须找到能强制等待人工确认的配置（比如关掉 auto_transition，或者找到"design 完成"判据里加入"人工确认"这个条件的配置项），不能默认它是安全的，找不到就如实报告，不要凑合。
   b. comet-hook-guard.sh 是否真的拦住了在 open/design/archive 阶段写代码文件的尝试。
   跑完把这个测试 change 清理掉，不留痕迹进正式仓库历史；把这两点的验证结论报告给我。**我确认"人工审批门没被削弱"之后，你才能进入第2步**，这是硬性停止点，不是走过场。

── 第2步：用 Comet 接管"归档已100%完工的变更" ──
对象：platform-hardening-p2、o2-kit-shortage-alert、sc5-purchase-recommendation（这三个的具体情况见原 Prompt 阶段1）。
这几个变更不是 Comet 创建的、也早就过了 open/design 阶段——如果 Comet 支持"接管一个非 Comet 创建的既有 openspec change"（比如直接给它补一份 .comet.yaml、设 phase=verify 然后跑 comet-verify/comet-archive），就用这个路径；**如果 Comet 只支持从 open 阶段开始管理、接不了既有 change，如实告诉我，这三个退回原 Prompt 阶段1的手工 openspec archive 流程走，不要为了"用上 Comet"硬凑一个不适用的流程。** 无论走哪条路径，验收标准不变：openspec validate 通过、出现预期的新 spec 条目、相关回归测试全绿，再 commit。

── 第3步：用 Comet 接管"fix-a/b/c 核实与归档" ──
同上，优先尝试用 Comet 的 verify 阶段承载"逐条核实代码是否真的实现、测试是否真的覆盖"这件事——这正好是 verify 阶段的设计意图。核实口径照抄原 Prompt 阶段2（A1/A2/A3、B1-B6、C1/C2 逐条对照代码和测试）。**验证不了的任务保留未勾选、如实报告，绝不能为了让 Comet 的 verify_result 显示 pass 就放水打勾**——这条纪律比"用没用上 Comet"更重要。

── 第4步：用 Comet 接管"SuperPowers 项目域依赖声明" ──
Comet init 本身会处理 OpenSpec/Superpowers 的技能安装，这一步重点核实：Comet 有没有顺带解决"SuperPowers 全局依赖在仓库里零留痕"这个问题（比如它自己的配置文件里有没有记录"这个项目依赖 Superpowers vX.X.X + 具体哪些技能"这类声明）？如果有，直接用它的机制，不用再单独改 `.claude/settings.json`；如果没有，退回原 Prompt 阶段6的方案（settings.json 项目域声明 + 环境依赖清单文档）。**同时把 Comet 自己也补进环境依赖清单**——它也是个新的全局工具依赖，用同样的标准登记（谁装的、什么版本、干什么用、尽调结论摘要）。

── 第5步：把第2/3步的"归档+核验"动作，收敛成一个可重复调用的 Loop 骨架（这是本次的核心产出）──
不是马上上生产、不接任何定时任务，这一步只是把刚才手工走过的动作，写成一个明确定义了"触发条件+终止条件+失败处理"的可重复脚本/流程，为将来真正自动化打地基。按 Loop Engineering 的要求，必须明确写清楚：
- **触发**：本阶段只做"手动触发"（一条命令/一个脚本，我或你手动跑一次），不接任何 cron/定时任务——这是纪律要求，不是可选项。
- **扫描范围**：`openspec/changes/` 下所有非 archive 目录的变更，逐个检查 tasks.md 完成度。
- **终止条件**（每个变更独立判定，必须机器可验证，不能"AI觉得差不多了"）：100%勾选 → 跑 `openspec archive` + `validate` + 该变更关联的测试 → 全部通过才算成功，且跑一次 `openspec validate` 确认 `specs/` 出现预期条目；任何一步报错或出现没预期的 spec 合并冲突，立即停止处理该项（不重试、不做猜测性修复），记入报告，不影响其它变更的处理。
- **迭代/范围上限**：一次运行只处理当前识别到的清单，不递归发现新工作、不自动创建新的 openspec change、不做任何设计决策——这个 Loop 只负责"关"已经100%完成的门，不负责"开"新的门，这是防止它"自我说服"越界的关键约束。
- **失败/异常处理**：任何一项失败，写入报告；不自行"创造性解决"，不允许把"没验证清楚"包装成"完成"。
- 这个骨架先手动跑 2-3 次，观察是否符合预期、有没有误报/漏报，再决定要不要真正接自动触发。**接自动触发这件事本身需要我另外拍板，不包含在这次任务范围内**；即便以后要接，也应该接在你（Claude Code / 本机自动化）这一侧，**不能接进 Cowork 的 scheduled-tasks**——按项目分工，Cowork 不碰真实库/不写生产代码，这条 Loop 真跑起来是要 commit/push 代码和 openspec 数据的，只能长在建造车间这一侧。

── 收尾 ──
汇总一份报告：Comet 尽调结论、第1步两项门禁验证的结果（design阶段是否真的等人工确认、hook是否真的拦截写代码——如果发现有一项不安全，明确说清楚，不要含糊）、第2/3/4步用 Comet 跑的实际结果（如果发现 Comet 接不了既有 change、退回了手工流程，也如实说）、第5步 Loop 骨架长什么样 + 手动跑了几次结果如何。全部完成后停下来，我看完报告再决定：① 要不要正式采纳 Comet；② 要不要把这个 Loop 骨架继续往前推；③ 阶段3/4/5是否照原 Prompt 单独手工推进。

明确不要做的事：
- 不要把 Comet/Loop 用在阶段3（SC1迁移）、阶段4（场景CLAUDE.md）上——按原 Prompt 手工走。
- 不要给第5步的 Loop 骨架接任何定时/自动触发——这次只做手动可重复调用的骨架。
- 在没跟我确认"design 阶段人工门禁没被削弱"之前，不要用 Comet 处理任何触碰真实场景代码/openspec正式变更的工作。
- sc8-real-data-cutover、qd-b-project-gate-review、fi1-warehouse-reconcile 三个继续不要碰。

现在开始：先读三份文档，回我理解，我确认后再做第0步 Comet 尽调。
```

---

## 背景（给我自己看，不用念给CC）

这份 Prompt 是 2026-07-02 同一天讨论的延续：Paul 读了 Comet（OpenSpec+Superpowers编排层）和 Loop Engineering 两篇文章后，认可"Comet 值得引入、但要先在低风险试验田验证、Loop Engineering 只该用在机器可验证的工程基础设施类任务上，不能碰 L2人工确认/ASIL C-D/OEM隔离这类需要人工判断的高风险决策"这个判断，决定拿已经交给 CC 的"SDD 收口"工作（阶段1/2/6，排除阶段3/4/5）当第一个 Comet + Loop 试点。

核心设计原则：① Comet 是否安全，必须先在无关痛痒的测试 change 上验证"人工审批门没被削弱"，不能默认第三方工具的默认配置就是安全的；② Loop 的范围严格限定在"关闭已100%完成的门"，不允许它自己发现新工作、自己做设计决策；③ 这次只做手动可重复调用的骨架，接不接自动触发是下一次单独拍板的决定，且即便要接也只能接在 Claude Code/建造车间这一侧，不进 Cowork。

## 用完这份 Prompt 之后

如果第0/1步发现 Comet 不安全（人工审批门被 auto_transition 绕开、或 hook 拦不住），就地止损：不采纳 Comet，阶段2/3继续走原 Prompt 的手工 openspec 流程，Loop 骨架部分可以脱离 Comet、纯用 openspec CLI + 脚本实现同样的终止条件设计（Loop Engineering 的价值不依赖 Comet，Comet 只是让它更省事）。如果验证通过，下一步是决定：①是否把 Comet 扩展到其他场景开发（SC3/SC5等，涉及业务判断更多，需要更谨慎）；②这个 Loop 骨架要不要接自动触发、接在哪。这两个决定都需要单独再讨论，不在本次任务范围内自动推进。
