# openspec-config-proposal-rules Proposal

## Why

`.claude/commands/opsx/propose.md` 里硬编码了两个 proposal 强制门禁段（《知识资产三问》《验收与晋档条件》，2026-07-04 起生效，来源全景规划 §1.4 + Antigravity 评审整改项④）。2026-08-02 本仓库 OpenSpec CLI 从 1.4.1 升级到 1.7.0（`openspec update`）时，这两段被**整段静默删除**——无提示、无报错，混在 10 个文件的上游 diff 里，若非逐文件核对中文行增删计数会被 sweep 直接 commit 吞掉（详见跨桌任务队列 #205/#206）。本次升级已靠事后核对手工还原，但只要门禁规则还硬编码在会被 `openspec update` 重写的命令文件里，下一次升级就可能再次静默失效而无人察觉——这与 IATF 16949"AI 辅助决策须有完整审计轨迹可追溯"的要求相悖：门禁如果只是文档声称存在、实际可能已被吞掉，就不能算真实存在。需要把这两节的规则搬到 `openspec update` 不会覆盖的位置。

## What Changes

- 把 `propose.md` 中两个强制门禁段的**规则文本**迁移到 `openspec/config.yaml` 的 `rules.proposal` 字段（4 条机器可读规则，`openspec instructions proposal --json` 会把它们放进返回 JSON 的 `rules` 数组）。
- `.claude/commands/opsx/propose.md` 对应位置改为一行**指针注释**，说明规则已迁至 `config.yaml`、迁移原因（`openspec update` 会静默删除本文件里的定制段，`config.yaml` 不受影响）、以及"rules 是约束你不得复制进产出"这条通用准则不代表可以不满足这两节的结构性要求。
- 门禁本身的语义/内容**不变**——两个强制节（`## 知识资产三问`、`## 验收与晋档条件`）要求的问题、选项原样保留，只是承载位置从"硬编码进 AI 命令文件正文"改为"config.yaml 的结构化 rules 字段"。
- 属工具链/机制类变更（本仓库 OpenSpec 工作流自身的定制配置），不引入新的产品能力，不改变任何已发布 capability 的运行时行为。

## Capabilities

### New Capabilities

无。

### Modified Capabilities

无——本变更不改变 `openspec/specs/` 下任何已存在能力的需求；改的是本仓库 `/opsx:propose` 这一 AI 工作流命令自身产出结构约束的存放位置，不是任何产品/场景对外行为。因零 capability delta，`openspec/changes/openspec-config-proposal-rules/.openspec.yaml` 应补 `skip_specs: true`（当前尚未设置，留作本变更包 tasks 阶段动作，不在本次 proposal 编写范围内）。

## 知识资产三问（强制，全景规划 §1.4 第 2 条）

1. **本流程哪些判断是人脑默会经验？**
   - "`openspec update` 会覆盖/删除哪些位置的定制内容、保留哪些位置不动"——目前只在本次实证中确认了两个点：`.claude/commands/opsx/*.md` 命令文件会被升级重写、`openspec/config.yaml` 不会被重写（2026-08-02 队列 #205/#206 实证）。尚未系统排查 `.claude/agents/*.md`、`.claude/skills/**`、`hooks.json` 等其他可能同样"看似定制安全、实则会被工具升级吞掉"的位置。
   - "什么类型的定制内容该放 config.yaml、什么仍该留在命令文件正文"——目前的经验判据是：会被 `openspec instructions --json` 的 `rules`/`context` 字段结构化读出的机器可读约束放 `config.yaml`；纯提示词/操作步骤描述仍留在命令文件本身。这条边界目前只存在于本次处置该问题的会话经验里，未沉淀成本仓库通用的判据文档。
   - "升级后如何验证定制内容未被吞掉"——本次是靠 Shao Peishen 逐文件核对中文行增删计数（2026-08-02 #205-A 实证做法）人工发现的，没有自动化检测手段。
2. **由谁显性化？**
   - 持有人：**Shao Peishen**（本类机制/工具链变更的拍板与验收人，见本项目 CLAUDE.md"环境保障线的派单边界"细化铁律一：全局 npm 包/插件/CLI 的安装升级与 `openspec update` 一类会重写生成物的命令一律归 CC 协同本线处置，逐文件过目 diff）。
   - backup：**Claude Code（CC）**——负责此后每次 `openspec update` 前后按同一判据（版本三处交叉核验 + 受影响目录/文件基线 + 逐文件 diff 过目）复核，并把新发现的脆弱点持续写进本仓库 CLAUDE.md/跨桌任务队列，不只停留在单次 session 的临时记忆里。
3. **用什么方法提取？**
   - **历史案例反推**：本次规则本身就是由 2026-08-02 #205-A 真实踩坑（升级静默删段）倒推出"哪些位置对升级安全、哪些不安全"，而非预先设计。
   - 后续每次 `openspec update` 的真实复核结果将继续以判例形式累积，逐步补全"还有哪些定制点需要同样迁移"的清单（组合使用历史案例反推，暂不涉及 AI 起草·专家批改或 L2 改判判例，因本变更不是业务判断类场景）。

## 验收与晋档条件（强制，四档口径）

- **本变更包交付后场景所处档位**：本变更是工具链/机制类变更，不是面向部门业务的数字员工场景，四档口径（档1 mock验证 / 档2 真实数据跑通 / 档3 内部服务 / 档4 对客交付）不直接适用产品场景语义。做近似映射说明：`openspec/config.yaml` 的规则改动一旦落盘即对本仓库所有后续 `/opsx:propose` 调用实时生效、无需额外部署，效果上相当于产品场景的"档3 内部服务"级别；但如实说明这只是类比，不强行套用四档定义本身。
- **晋下一档的条件**（此处指"本机制被充分验证、可视为长期可信"的条件，逐条）：
  1. 已验证 `openspec instructions proposal --json` 返回的 `rules` 字段确实带出新规则内容（本次 proposal 编写前已实测通过，见变更目录内 JSON 输出留痕）。
  2. 需要经历**下一次真实 `openspec update` 版本升级**，核对升级后 `openspec/config.yaml` 的 `rules.proposal` 字段是否原样保留、未被覆盖——当前只是"预期不会被覆盖"，尚未有第二次真实升级验证，不能算已验证完毕。
  3. `propose.md` 的指针注释本身也需要在下一次升级后核对是否被静默删除（指针注释同样是本文件内的定制内容，若上游 diff 覆盖整个 Artifact Creation Guidelines 区块，指针注释也可能被一并吞掉，需与规则本体一起复核）。
  4. 实跑一次 `/opsx:propose` 真实生成新变更包的 proposal.md，确认 AI 依旧能据 `rules` 字段写出两个强制节、内容不漂移（行为零回归）。
- **价值指标**：**风险型**——消除"OpenSpec 版本升级静默吞掉治理门禁而无人察觉"的合规风险，使 IATF 16949 要求的"AI 辅助决策门禁真实存在、可追溯"不再只是文档声称。基线：本次之前已确认发生过至少一次静默删除（2026-08-02 实证，1.4.1→1.7.0 升级触发）；目标：此后任意一次 `openspec update` 之后，`openspec instructions proposal --json` 返回的 `rules` 字段均可验证强制门禁仍在，不再需要靠人工逐文件比对中文行数才能发现丢失。

## Impact

- **受影响文件**（均为本仓库 OpenSpec 工作流自身配置，非产品代码）：
  - `.claude/commands/opsx/propose.md`——移除硬编码的两段门禁正文，替换为一行指针注释。
  - `openspec/config.yaml`——新增 `rules.proposal` 字段，承载原硬编码在 `propose.md` 里的门禁规则。
- **不影响**任何已发布的产品 capability、场景代码（`4-数字员工/**`）、真实数据管线（U9C/SRM/FO）或已部署到 `.51` 的服务；不新增第三方依赖；不改变 OpenSpec CLI 本身的调用方式（`openspec instructions`/`openspec update` 等命令用法不变）。
- **红线核对**：mock先行——不适用（无业务数据流）；audit留痕——本变更过程与背景已如实登记进跨桌任务队列 #205/#206 与本项目 CLAUDE.md（2026-08-02 段），满足可追溯要求；OEM隔离——不适用；L2门禁——不适用（本变更不涉及采购金额/新供应商/交付预测等 L2 场景）；ISO26262——不适用（非 ECU 安全相关代码）。
- **遗留待办**（不在本 proposal 范围内，供后续 tasks 阶段处理）：`.openspec.yaml` 补 `skip_specs: true`；下一次真实 `openspec update` 后按"验收与晋档条件"第 2、3 项复核规则与指针注释是否仍在。
