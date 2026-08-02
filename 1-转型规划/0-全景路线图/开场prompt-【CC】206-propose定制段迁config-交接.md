---
title: "【CC】开场 prompt · #206 把 proposal 强制门禁段迁入 openspec/config.yaml"
created: 2026-08-02
执行方: CC 平台（建造车间）
执行环境: CC
来源: 队列 #206（Shao Peishen 2026-08-02 拍板选「选项 A」：走 openspec 变更包 + design 审）
status: 待执行
---

# 【CC】开场 prompt · #206 proposal 强制门禁段迁 config

## 【开场词（复制即用）】

```
【设置】执行环境：CC ｜ 分支：新建 feat/openspec-config-proposal-rules ｜ worktree：☑ ｜ 工作区：🔴 影响全项目所有 session 与 3 个长驻 worktree——见「工作区字段」段

读 1-转型规划/0-全景路线图/开场prompt-【CC】206-propose定制段迁config-交接.md ＋ CLAUDE.md 当前进度恢复上下文，按文件执行。
🔴 本件须走 openspec 变更包 + design 审（Shao Peishen 已拍板，理由见文件）；A 段的可行性验证若结论为"rules 语义不匹配"，那也是合格交付，不要硬做。
开干前先答 §五 的两个澄清问题（均为带推荐项的选择题）。
```

---

## 背景一分钟

- 2026-07-04 Antigravity 评审整改项 ④ 落地：**每份 `proposal.md` 必须含《知识资产三问》与《验收与晋档条件》两个强制节，缺任一节不进 design 审**。
- 当时的接线方式是**把这段中文说明直接写进 `.claude/commands/opsx/propose.md`**（commit `e4dd9e1`）。
- 🔴 **2026-08-02 实证：该文件是 `openspec update` 的生成物**——升级 OpenSpec 1.4.1→1.7.0 后跑 `openspec update`，**这 13 行被整段删除、零提示零报错**，混在 10 个文件的上游 diff 里（判据＝中文行增删计数：删 13、增 0、且仅此一文件）。当场还原并加了 3 行 HTML 警示注释，**但那只是把同一颗雷埋回原处**。
- **Shao Peishen 拍板走「选项 A」根治**，明确没选"停在还原+注释"那个零成本档，理由：**靠"下次有人记得看注释"不成立**（本项目 2026-08-02 一天之内四次证明"靠人记住"失效，全部由 sweep 安全门或事后自检兜住）。

---

## 「工作区」字段（协议〇.1 第四字段）

**自检一问：本次改动，有没有任何一份"正在跑的副本"不在我改的这个 checkout 里？**

🔴 **有，而且是全项目范围**：`openspec/` 与 `.claude/commands/opsx/` 的内容**被每一个 session（CC 与 Cowork）、每一个 worktree 读取**。

- ~~**五个长驻 worktree 的状态（2026-08-02 实测）**：`musing-pascal-68d14e`／`qd-b-grayscale-improvements-9dbe6f`／`wecom-service-home` 与 `sweep-criteria-sync-fix-7eb8a7` 已由 #207 刷新至当前 master；**仅 `fi2-validation-prep-66ed2c` 仍停在旧基线（落后 338 提交），其清理已并入 #165**。~~ ← **本条已于 2026-08-02 晚过时，勿据以执行**
- ✅ **现状（2026-08-02 15:45 本地 / 07:45Z，本机 `git worktree list` 实测）——#165 执行后由 5 降至 3**：`musing-pascal-68d14e`（`claude/queue-numbering-alert-criteria-855665`）／`qd-b-grayscale-improvements-9dbe6f`（detached HEAD）／`wecom-service-home`（`ops/wecom-service-home`）。**`fi2-validation-prep-66ed2c` 已随 #165 整体删除**——即原先那个"仍缺警示注释、落后 338 提交"的 worktree **已不存在，本件不再有该前置依赖**。另有 `sweep-criteria-sync-fix-7eb8a7` 一个**0 文件空壳目录**（git 已不认、`worktree list` 无此条，因句柄占用未删，待 #98 下期体检顺手清），**不是 checkout、不读取 openspec 配置、与本件无关**。
- **含义（改写）**：**本件落地后即达成全项目一致，无须再等任何 worktree**；#206 行内原要求的"写明该 worktree 尚未同步"**已因该 worktree 被删而自然消解**。**但请注意另一件事**：三个现存 worktree 当前停在 `fa9c5b8`、**落后 master 17 提交**（属 linked worktree 的正常漂移，非缺陷），故**它们读到的 `openspec/`＋`.claude/commands/opsx/` 仍是旧副本**——本件若在独立 worktree 内验证（§五 问题 1 选 (a)），须先确认该 worktree 已快进到含本次改动的 commit，否则验的是旧载体。
- **无常驻服务受影响**（不涉 `.51` 四服务、不涉企微机器人）。

---

## 权威依据清单（只给指针）

1. `1-转型规划/0-全景路线图/跨桌任务队列.md` **#206 行** —— 完整缺陷记录、拍板内容、**三点必须先验证的约束**。协议〇 八条必读。
2. 同上 **#205 行 🅰 段** —— #205-A 的完整执行记录（含本缺陷是怎么被抓到的、"中文行增删计数"判据）。
3. 同上 **#195** —— 机制/工具类模块缺失 openspec capability，与本件同属 openspec 治理，**评估时一并看**（1.7.0 新增的 `skip_specs: true` 与 #195 的判断直接相关）。
4. `.claude/commands/opsx/propose.md` —— **当前状态：定制段已还原 + 顶部有 3 行 HTML 警示注释**。
5. `openspec/templates/proposal-template.md` —— 两个强制节的**完整模板真身**（1934B，未受影响，本次不动它）。
6. 根 `CLAUDE.md` §5 —— **「机制/工具类 openspec 触发门槛」**（本件命中第 ① 条"改变全项目口径"，故须走 design 审）、执行环境标注、完工即归档。

---

## 任务分段

### 🔎 A 段前置：环境保障线已完成的只读源码取证（2026-08-02 晚，**直接用，不要重做**）

> **取证对象＝本机全局包真身** `C:\Users\Paul Shao\AppData\Roaming\npm\node_modules\@fission-ai\openspec`（v1.7.0，`openspec --version` 实测）。**纯只读，未跑任何写命令。**

**🔴 结论一：`config.yaml` 与 `openspec/schemas/` 都不会被 `openspec update` 覆盖——本件"换个坑再跳一次"的风险已排除。**
- 依据＝`dist/core/update.js` **全文 774 行**，**全部写/删动作**（`writeFile`／`rm`／`unlink`）**只落在两类目标**：`skillFile`（`<tool>/skills/*/SKILL.md`）与 `commandFile`（`.claude/commands/opsx/*`）；**`schemas` 与 `config.yaml` 在该文件内零命中**。
- ⇒ 这正面回答了 A2 的验收要求。**#206 的根因也由此坐实**：定制段之所以被删，正因为它被写在**唯一会被 update 重写的那类文件**里。

**🟠 结论二：`rules` 的语义张力真实存在，但"不匹配"这个判断不能只靠读源码下定论——两种读法都成立，必须实跑。**
- `dist/core/templates/workflows/propose.js` 有 **4 处**明写：`rules` 是 *"constraints for you — do NOT include in output"*、*"Apply context and rules as constraints - but do NOT copy them into the file"*。
- 🔴 **但它禁的是"把规则原文复制进产出"，不等于禁"规则要求产出包含某两个小节"**——后者是对**产出结构**的约束，照做的结果是生成那两节，并没有复制规则文本。**两种读法都讲得通，读源码分不出来，必须靠 A 段实跑定。**
- 加载链已核实：`instruction-loader.js` L147-161 按 **artifact id 取 `projectConfig.rules[artifactId]`**，作为**独立字段**传入（注释明写 *"Extract context and rules as separate fields (not prepended to template)"*），并有 `validateConfigRules` 校验 artifact id 合法性。

**🟢 结论三（本次最有价值的发现，原派单件未想到）：还有一个比 `rules` 更强的载体——项目本地 schema。**
- `dist/core/artifact-graph/resolver.js` L74-75 明写解析顺序：**① 项目本地 `<projectRoot>/openspec/schemas/<name>/schema.yaml` → ② 用户级 `${XDG_DATA_HOME}/openspec/schemas/` → ③ 包内置**；`getProjectSchemasDir()` 返回的就是 `<root>/openspec/schemas`。`project-config.js` L23-27 的 zod 描述亦写 `schema` 字段接受 *"project-local schema name"*。
- **包内置 schema 的结构已看过**：`schemas/spec-driven/schema.yaml` 逐 artifact 声明 `generates` / `template`，`templates/proposal.md` **就是产出的小节骨架**（`## Why` / `## What Changes` / `## Capabilities` / `## Impact`）。
- ⇒ **把两个强制节放进项目本地 schema 的 `templates/proposal.md`，它们就成为产出骨架的一部分（结构性），而不是"指望 agent 照做"的指令**——**这比 `rules` 强一个量级，且同样不被 update 覆盖**。
- ⚠️ **代价须一并评估、不要只看好处**：自建 schema 意味着**包内置 schema 的后续升级不再自动惠及本项目**（要手工跟进 diff），**这本身就是另一种"脱节"风险**（同 #188 真身 vs 镜像）。**孰轻孰重由 design 审定，本线不替你决定。**

**📌 顺带一条与 #195/#196 相关**：包内 `templates/proposal.md` 明写——**零 capability 的变更（纯重构/工具/文档）必须在 `.openspec.yaml` 里设 `skip_specs: true`，否则 `openspec validate` 拒绝**；且强调 *"Do not invent a requirement just to satisfy validation"*。**D 段那条"看一眼 #195"照此推进即可。**

### A 段 · 可行性验证（**先做完再动手改，结论为"不可行"也是合格交付**）

**A1 摸清 1.7.0 的 `config.yaml` 语义**
- `openspec doctor` 当前报本库 **root unhealthy: `Missing openspec/config.yaml`** —— 本库 `openspec/` 下只有 `changes`／`specs`／`templates`，**从来没有 config.yaml**，这正是当初被迫把定制硬写进生成物的根因土壤。
- 1.7.0 的 `explore.md`／`propose.md` 均明确读取 `openspec/config.yaml` 的 `context`（项目背景）与 `rules`（**按 artifact id 分键，只在写该 artifact 时生效**）。
- 🔴 **关键疑点必须实测**：`rules` 的官方语义反复强调 **"约束你写什么、但不得复制进产出文件"**；而本项目要的是 **"产出文件里必须出现这两个小节"**。**二者语义可能不匹配。**
- **验收**：给出"匹配／不匹配／部分匹配"的明确结论 + 依据。**不匹配则转 A2。**

**A2 若 `rules` 不匹配，评估替代载体**
- 候选：`openspec/templates/`（本项目已有 `proposal-template.md`）／**项目本地 schema `openspec/schemas/<name>/`（路径与优先级已由上方取证坐实，且其 `templates/proposal.md` 直接就是产出骨架）**。
- ~~**并说明该载体是否同样会被 `openspec update` 覆盖**~~ ← **此项已由上方「结论一」回答（两个候选均不被覆盖，`update.js` 全文零命中）**，A2 只需给出**选定载体与理由**，以及 **`rules` 与项目本地 schema 二选一的取舍论证**（指令性 vs 结构性；自建 schema 会失去包内置 schema 的后续升级红利，须手工跟 diff）。
- 🔴 **A2 的真正待答项改为**：若选项目本地 schema，**如何在"拿到结构性强制"与"不与上游 schema 脱节"之间取舍**——这是 design 审要拍的那一刀，**必须写进 design 的备选方案对比，不能只写选了什么**。

### B 段 · openspec 变更包 + design 审
- 按 §5「机制/工具类 openspec 触发门槛」第 ① 条（改变全项目口径）走完整流程：`/opsx:propose` → **停下等 Shao Peishen 审 design** → `/opsx:apply`。
- ⚠️ **注意递归性**：本件生成的 `proposal.md` **自己也必须包含那两个强制节**——它正是要保护的规则。**这既是自检也是一次真实演练。**
- **验收**：design 获批留痕；变更包完工即归档。

### C 段 · 落地与验证
- **C1** 迁移：两个强制节移入选定载体；`.claude/commands/opsx/propose.md` 内**只留一行指针 + 警示注释**。
- **C2** 🔴 **真跑一次 `/opsx:propose`**，验证两个强制节**确实出现在产出的 `proposal.md` 里**——**不能只看配置写没写**（CLAUDE.md §5「不信工具说成功了」）。
- **C3** 🔴 **再跑一次 `openspec update`**，确认新载体**不会被覆盖**；用**中文行增删计数**判据核 diff（删 N 增 0 即为异常）。
- **验收**：C2 与 C3 各留一份可核验的证据（产出文件片段 / diff 统计）。**C3 未做等于本件没完成**——它才是本件的目的。

### D 段 · 收尾
- 回填 #206。~~若 `fi2-validation-prep-66ed2c` 尚未同步，在行内写明~~ ← **该 worktree 已随 #165 于 2026-08-02 晚整体删除，本条要求作废**；改为：**在行内写明本件落地时三个现存 worktree（`musing-pascal-68d14e`／`qd-b-grayscale-improvements-9dbe6f`／`wecom-service-home`）是否已快进到含本次改动的 commit**，未快进则如实写"读到的仍是旧载体"。
- 顺带看一眼 **#195**：1.7.0 的 `skip_specs: true` 是否能替 #195 的 8 个候选 capability 里的一部分给出"标 skip 而非补 spec"的答案——**只写观察，不在本件里动 #195**。

---

## 开工前置步（认领先于动手）

按触碰区关键词（`propose.md`／`openspec/config.yaml`／`知识资产三问`／`验收与晋档条件`／`#206`／`#195`／`#205`／`e4dd9e1`），**同时 grep 《跨桌任务队列.md》与《跨桌任务队列-归档-YYYYMM.md》**，确认无他人在办行重叠。**归档件必须一起 grep。**

---

## 五、开工前请先答（两个选择题，均带推荐项）

**问题 1 · 若 A1 结论是"`rules` 语义不匹配"，走哪条？**
- **(a) 推荐：转 A2 选自定义 schema 或 template 载体，本件继续。** 代价＝工作量比预想大（要验证新载体的抗覆盖性）；好处＝**这才是本件的目的**，换载体不换目标。
- (b) 本件缩为"只交可行性结论"，根治另立新行。代价＝雷继续埋着，**下次任何人跑 `openspec update` 仍会删掉那 13 行**；好处＝把大决策留给 Shao Peishen。
- (c) 放弃迁移，改为在 `openspec update` 之后加一道"复检 propose.md 定制段是否还在"的人工步骤。**不推荐**——它把机制问题降级成纪律问题，正是本件要消除的形态。

**问题 2 · C3（再跑一次 `openspec update` 验抗覆盖）在哪跑？**
- **(a) 推荐：在本件的独立 worktree 里跑。** 代价＝要确认 worktree 内的 openspec 行为与主工作区一致；好处＝**万一新载体也被覆盖，不污染主工作区**。
- (b) 在主工作区跑。代价＝若被覆盖，主工作区当场出现内容丢失，**得靠 git 恢复**；好处＝结论最真实（主工作区才是常用环境）。
- ⚠️ **无论选哪个，跑之前先固化改前证据**（受影响文件基线 + 中文行计数），这是 #205-A 立下的破例三条件之一，本件同样适用。

---

## 纪律段（只列条目名）

- **机制/工具类 openspec 触发门槛（CLAUDE.md §5）** —— 本件命中第 ① 条「改变全项目口径」，**必须走 design 审**。
- **跨桌任务队列**：开工必读认领 + 登记触碰区；收工必写。
- **编辑锁（协议〇.7）** + **编号取号 `--reserve`（#163）** + **批次须声明变更参数（协议〇.8）**。
- **完工即归档**（tasks 全 [x] 后**当场** `/opsx:archive`，不留中间态）、**不信"工具说成功了"**、**机制优先**。
- 🔴 **改本机工具链＝CC（2026-08-02 新立）** —— 本件若涉及跑 `openspec update`，正属此类，**破例三条件（固化改前证据／逐文件过目 diff／事后登记）同样适用**。

---

## 收工段

1. 回填队列 #206（**C3 的抗覆盖验证结论是核心，必须写**）；#195 的观察另起一句写进 #195 行。
2. **CC 自行 commit + push**；**收工重跑一次文档台账**。
3. 若只做到 A 段，**在行内写清"B/C 段未做及原因"**，不得整体标完成。
4. 会话末按 CLAUDE.md §5 用固定小节「**需你定夺**」罗列决策项：**每项必须是可直接作答的是非题或选择题**（带 `(a)/(b)/(c)` 字母标签 + 每项写清选项间实际差异与代价 + **标注默认项**"若不答我按 (x) 执行"）；**禁止把纯状态汇报混进该小节**，状态另起「状态同步（无需你答）」。
