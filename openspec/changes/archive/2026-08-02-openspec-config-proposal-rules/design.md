## Context

见 proposal.md - Why。补充两点 proposal 未展开的技术底细，是本设计取舍的依据：

1. **根因已用源码定位到字节级**：本机全局包 `@fission-ai/openspec` v1.7.0 的 `dist/core/update.js`（全文 774 行）里，全部 `writeFile`/`rm`/`unlink` 动作只落在两类目标——`skillFile`（`<tool>/skills/*/SKILL.md`）与 `commandFile`（`.claude/commands/opsx/*`）。`openspec/config.yaml` 与 `openspec/schemas/` 在该文件内零命中，即两者**结构性地**不会被 `openspec update` 覆盖（不是"目前恰好没覆盖"，是这条升级流水线的写入范围根本不包含它们）。
2. **`rules` 是运行时读取，不是构建时烘焙**：`dist/core/artifact-graph/instruction-loader.js::generateInstructions()` 在每次 `openspec instructions <artifact> --change <name> --json` 被调用时，现读 `openspec/config.yaml`，把 `rules[artifactId]` 作为独立 JSON 字段 `rules`（字符串数组）返回，与 `template`/`instruction`/`context` 并列。即：`.claude/commands/opsx/propose.md`（一个静态命令文件）本身不携带这两个强制节的内容，它只是指导 agent 去读并遵守这个运行时字段。

## Goals / Non-Goals

**Goals：**
- 让"proposal.md 必须含《知识资产三问》《验收与晋档条件》两节"这条治理要求，在下一次 `openspec update` 之后依然生效——不再依赖"没人跑 update"或"跑完 update 有人记得复检"。
- 保持两节的语义内容（问什么、填什么）完全不变，只搬运载体，不重新设计门禁本身。

**Non-Goals：**
- 不为"升级后自动检测定制内容是否丢失"建自动化机制（例如 CI 校验、pre-commit 钩子）——本次只解决"载体本身不会被覆盖"，检测机制是另一个量级的投入，留给后续按需评估，不在本变更包范围。
- 不排查/迁移本仓库其他可能有同类风险的定制点（如 `.claude/agents/*.md`、`hooks.json`、其余 `.claude/commands/opsx/*` 命令文件里是否也有类似硬编码定制段）——#206 只盯 proposal.md 这一个已实锤的点，其余点若存在需另开变更包，本设计末尾的 Open Questions 里留一句观察但不处理。
- 不改动 `openspec/templates/proposal-template.md`（项目历史遗留的人工参考文档，供 Paul 审 proposal 时对照用）——该文件从未被 CLI 消费（CLI 实际消费的模板路径是包内 `schemas/spec-driven/templates/proposal.md`，两者路径不同），保留原状不影响本次修复，继续作为人工参考存在。

## Decisions

### 决策 1：载体选 `openspec/config.yaml` 的 `rules.proposal`，不选项目本地 schema

**做法**：`rules.proposal` 存 4 条字符串规则（MANDATORY 总纲 + 两节各自的具体填写要求 + 一条显式反转"rules 不进产出"默认语义的元说明），`.claude/commands/opsx/propose.md` 只保留一行 HTML 注释指针，不再含门禁正文。

**为什么不是自建项目本地 schema**（`openspec/schemas/spec-driven/templates/proposal.md`，把两节直接写进 `template` 骨架）：
- 环境保障线前置取证已确认这条路径存在且同样不受 `openspec update` 覆盖，理论上比 `rules` 更"结构性"（agent 被明确指示"用 template 作为骨架填充"，而不是"把 rules 当约束应用"）。
- 但代价是**永久性地与上游 schema 分叉**：一旦自建 `openspec/schemas/spec-driven/`，此后包内置 spec-driven schema 的任何升级（模板措辞改进、新增 section、instruction 文案修订）都不会再自动应用到本项目，需要人工逐次比对合并——这本身就是"自建镜像与真身脱节"的老问题（同 #188 记录的形态），且这个成本是**永久性、逐版本累加**的，不是一次性的。
- **决定性因素是 A1 的实测结果**：两次独立、不知情的子代理（盲测，均未被告知"这是在测试 rules 机制"）仅凭 `openspec instructions proposal --json` 返回的标准 JSON，就正确生成了两个完整强制节，且第二次测试在 propose.md **完全不含**任何本项目定制注释的情况下依然成功（详见"验证结果"）。既然更轻量、无分叉代价的方案已经跑通，没有理由为了"理论上更结构性"去承担自建 schema 的永久维护成本。**若未来实测发现 rules 合规率不稳定，或 openspec 某个版本开始覆盖 config.yaml，应重新评估自建 schema。**

### 决策 2：propose.md 保留一行指针注释，但明确它是防御性冗余，不是机制必需项

**做法**：注释只说明"两节要求已迁至 config.yaml"+"若某条 rule 要求产出含特定章节，'不得复制进产出'不豁免这个要求"，不包含门禁正文本身（正文只活在 config.yaml 一处，避免双份维护、避免注释本身过时）。

**理由**：第二次盲测（propose.md 不含任何本项目注释）依然成功，证明该注释对机制本身不是必需的——`rules` 字段配合 propose.md 自带的标准 Guardrails 语句已经足够。保留它是为了：① 人类维护者读 propose.md 时能立刻理解"为什么这个文件比上游版本少了一大段、门禁去哪了"；② 万一未来某次 `openspec update` 升级改变了 `rules` 语义的措辞强度，这行注释能提示 agent 优先信任 config.yaml 的显式要求。**即便这行注释被下一次 `openspec update` 重新删除（因为它仍物理位于 commandFile 内），核心门禁不会跟着失效**——这正是本次修复要达成的性质：commandFile 层面的任何丢失都只是"体验降级"（少一句人类可读的解释），不再是"机制失效"。

## 验证结果（对应 proposal.md「验收与晋档条件」第 1、4 条）

- ✅ `openspec instructions proposal --change <name> --json` 返回的 `rules` 数组内容与 `config.yaml` 原文一致（2026-08-02 实测，见变更目录构建过程留痕）。
- ✅ 盲测 1（propose.md 含指针注释）：独立子代理在不知情的情况下，仅按标准流程执行，生成的 proposal.md 完整包含两个强制节，内容详实、非机械复制规则原文。产出即本变更包自己的 proposal.md。
- ✅ 盲测 2（propose.md **不含**任何定制内容，纯上游默认文案 + config.yaml rules）：独立子代理依然正确生成两个强制节，且在回复中明确指出并正确解决了"通用 rules 不进文件"与"本条 rules 显式要求成文"之间的语义张力，倾向于更具体的指令。该测试变更包（`test-rules-only-probe`）验证后已清理删除，不保留在 `openspec/changes/`。
- ⏳ 未做（留给 C3，需要真跑一次 `openspec update`）：确认再升级一次 OpenSpec 后，`config.yaml` 的 `rules.proposal` 与 propose.md 的指针注释是否原样保留。这是本变更包能否视为"根治"而非"换个坑"的最终判据，必须在 apply 阶段做完才能归档。

## Risks / Trade-offs

- **[风险] rules 机制仍是"指令遵循"性质，非机械强制** → 两次盲测均通过，且这与修复前（门禁正文硬写在 propose.md 里）依赖的可靠性是同一量级——本次没有降低可靠性，只是消除了"被工具升级静默物理删除"这一种新增失效模式。不追加自动化校验（见 Non-Goals），接受此残余风险。
- **[风险] 本次修复只在当前 worktree 生效，需合并进 master 后其他 3 个长驻 worktree 才能拿到**（`musing-pascal-68d14e`／`qd-b-grayscale-improvements-9dbe6f`／`wecom-service-home`，均落后 master 若干提交）→ 在合并前，这些 worktree 内如果独立跑 `openspec update`，仍会命中 #206 描述的旧漏洞（因为它们的 propose.md 还是"13行硬编码+3行警示注释"版本）。这是正常的分支传播延迟，不是本次修复引入的新风险；对齐时机随各自任务自然带入（同 #207 处置方式），不在本变更包内特意同步。
- **[风险] `openspec/templates/proposal-template.md`（人工参考文档）与 `config.yaml` 的 rules 文本现在是两份独立维护的等价内容** → 若未来只改其中一份，两者会措辞漂移。已知取舍：`proposal-template.md` 面向人类（Paul 审阅时的检查单），`rules` 面向 CLI/agent，服务对象不同，暂不合并为单一来源。若后续发现漂移造成实际混淆，可评估让 `rules` 内容改为引用/生成自 `proposal-template.md`（目前无自动化手段，标记为未来可选项，不在本次范围）。

## Migration Plan

1. ✅ `openspec/config.yaml` 新增 `rules.proposal`（本次已做）。
2. ✅ `.claude/commands/opsx/propose.md` 硬编码门禁段 → 一行指针注释（本次已做）。
3. ✅ 双盲测验证两节确实出现在产出中（对应 C2，本次已做，见上「验证结果」）。
4. ✅ C3：真跑一次 `openspec update --force`（strong 版，比普通 `openspec update` 更严格——后者见"已是最新版本"直接跳过不写文件，`--force` 才真正触发重写，等价于一次真实版本升级会做的事）。结果：`openspec/config.yaml` 更新前后 SHA256 哈希**完全一致**（`ead451a9...`），`.claude/commands/opsx/propose.md` 的指针注释被删除（预期内，已在设计决策 2 中说明其为防御性冗余、非机制必需），已重新补回。**C3 通过，新载体确认不被覆盖。**
5. CC 自行 commit + push；完工即归档（`/opsx:archive`）。
6. 合并进 master 后，3 个现存长驻 worktree 按各自任务节奏自然同步（不在本变更包内特意提前对齐，见 Risks 第二条）。

## Open Questions

- 本仓库是否还有其他 `.claude/commands/opsx/*.md` 命令文件（如 `apply.md`/`archive.md`/`explore.md`/`sync.md`）存在类似"硬编码定制段、会被 update 静默吞掉"的风险点？**C3 执行 `openspec update --force` 时顺带得到部分答案**：这次强制重写同时触碰了 apply.md/archive.md/explore.md/sync.md 及 5 个 `.claude/skills/openspec-*/SKILL.md` 文件，`git diff` 显示除 propose.md（本次改动）外，其余文件**均无内容差异**（只有 LF/CRLF 换行符提示）——即证实**截至本次 C3 时点，本仓库只有 propose.md 一处带定制内容，其余同类文件当前是纯上游副本，暂无同类风险**。这是"现状确认"，不是"未来免疫"承诺——后续若在其他 opsx 命令文件里加定制内容，仍需照本次方案（迁 config.yaml 而非硬写命令文件）处理。因非本次改动范围，不在本变更包内补文档，留作观察项供后续需要时引用。
