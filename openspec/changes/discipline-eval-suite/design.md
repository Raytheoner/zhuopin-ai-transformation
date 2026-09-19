# Design — 纪律 eval 套件（一期 3 条）

> ✅ **2026-09-09 design 审已通过**（`OP-0909-I`，队列 `#440`，13 个可答字母项，Shao Peishen 答
> `1a，2a，3a` 全选默认＋两项无默认逐项答）——七个决策点全部已签认，逐点结论见下（标 ✅ **已决**）。
> 本文件从「只给候选、不预定」升级为「记录已决＋把可审形态写具体」。
> 本轮（`OP-0919-N`，2026-09-19）只做**这一件事**：把已决内容落回本包（此前只落在队列行与一份
> 未合并的审读件分支上，openspec 包本身十天未同步），并把 evals/CI/reports 的产出形态写到可审
> 程度。**本轮仍止步于此——不 apply、不建 CI job、不动 `.github/workflows`。**
>
> 🔴 **2026-09-19 复测发现的同步缺口（须在 apply 前解决，本轮不代办）**：
> 09-09 那次决策的两份产出——审读件 `design审读件-discipline-eval-suite-2026-09-09.md`
> （commit `3df08b0`）与 eval-5 靶点纪律的补回（commit `1f484130`，改 `.claude/rules/两桌同步与取证.md`）
> ——**都只存在于分支 `claude/op0909i-eval-suite-review-1a4f02`（本地与 `origin` 均有），从未
> ff 入 `master`**。实测：`git merge-base --is-ancestor 1f484130 origin/master` → `NO`；
> 同一命令对 `3df08b0` → `NO`；本 worktree（分叉自 `origin/master` 09b153d0）两者皆无。
> ⇒ **今天任何从 `master` 起的 apply 泳道，eval-5 仍无靶可打**（`grep -rn "ERRORLEVEL"
> CLAUDE.md .claude/rules/` 本分支复测仍零命中）——晋档 2 第 3 条对 eval-5 那一支**尚未真正解除**，
> 此前queue行「已执行、硬前置解除」的表述**对本分支不成立**。补救＝把该分支 ff 入 `master`（或
> cherry-pick 两个 commit），这是一次 🟡 档 git 操作，本轮按纪律不代办，登记待总线派发。

---

## 0. 本包的形状：一句话

**三道题 ＋ 一份「纪律在库坐标表」 ＋ 一个跑法 ＋ 一道 CI 门禁。**
草案把跑法当成白送的（「复用 skill-creator，只写题不写跑法」），实测不成立；**本包一半的设计
篇幅在跑法上，这是与草案最大的结构差异。**

---

## 1. ✅ 决策点 1（**已决**，本包的技术主干）：eval 用什么跑

**结论：候选 A2 —— `claude plugin eval`，`--ablation none`**（Shao Peishen 2026-09-09 答 `1a`，
审读件第 1 项，队列 `#440`）。放弃自动对照臂（design 建议「A2 起步、A1 作二期」，本次原样采纳）。

### 1.1 先摆事实：草案指定的那件东西跑的不是这件事

`skill-creator/scripts/run_eval.py` 实测（2026-09-08 读源码，非推断）：

| 观察点 | 实测内容 |
|---|---|
| docstring | `"""Run **trigger** evaluation for a skill description. Tests whether a skill's **description** causes Claude to **trigger (read the skill)** for a set of queries."""` |
| CLI 参数 | `--eval-set` ／ `--skill-path` ／ `--description` ／ `--num-workers` ／ `--timeout` ／ `--runs-per-query` ／ `--trigger-threshold` ／ `--model` ／ `--verbose` |
| 执行方式 | 往 `<project_root>/.claude/commands/` 写一个临时命令文件，再 `subprocess.Popen(["claude","-p",query,"--output-format","stream-json",…])`，从流事件里判「有没有读到这个 skill」 |
| 产出 | 触发率（bool 聚合），**不产 `grading.json`，不读 `evals.json`** |

⇒ **它是「description 写得好不好、会不会被加载」的 eval，与「加载之后行为对不对」无关。**

`run_loop.py` 是它的外壳（`from scripts.run_eval import run_eval`），同性质。
`SKILL.md:225` 写明行为评估的跑法是**由 agent 编排**：「spawn a **grader subagent** … reads
`agents/grader.md` … Save results to `grading.json`」——**没有任何脚本把一条 eval 端到端跑完**；
`aggregate_benchmark.py` 只聚合已经存在的 `grading.json`。

⇒ 可复用的实际只有四件（全部实测存在于
`C:/Users/Paul Shao/.claude/plugins/marketplaces/anthropic-agent-skills/skills/skill-creator/`）：
`references/schemas.md`（数据格式）、`agents/grader.md`（判分口径）、
`scripts/aggregate_benchmark.py`（聚合）、`eval-viewer/`（看板）。**编排层必须自己出。**

### 1.2 🆕 一个草案写作时不存在（或未被查到）的第三条路

**`claude plugin eval` 是本机 CLI 的一等命令**（实测 `claude --version` ＝ **2.1.260**，
`claude plugin eval --help` 输出全文已留痕）。要点逐条摘录：

- 读 `<eval dir>/**/case.yaml`，或 `prompt.md` ＋ `graders/*.md`；默认 eval 目录 ＝ `evals/`；
- **`--ablation with-without`**：自带 **no-plugin baseline arm** 并报 score delta ——
  **这正是草案 §9 开放点 3「对照组怎么定义」要的东西，官方已经内置**；
- `--runs <n>`（默认 `case.runs ?? 3`）—— 对应开放点 2 的采样次数；
- **`--threshold <0..1>`：任一 case 低于阈值即 `exit 1`** —— **CI 门禁天然可用，不必自写判定**；
- `--judge-model`（**默认 haiku**）—— 判分成本天然低，呼应全局「机械任务用 Haiku」约定；
- `--max-cost-usd`（**硬成本上限，触顶 `exit 2` 并报部分结果**）—— 直接回答「额度上限与超支行为」；
- `--json` ／ `--report <path>` ／ `--output-dir`；
- `--allow-tools`（Bash/Write/Edit/WebFetch/mcp\_\* 的运营方授权，支持 `Tool(pattern:*)`）；
- `claude plugin eval init --bare <name>` 可脚手架一个空白单 case 模板。

**它与本包的结构性错配（如实登记，不粉饰）**：它评的是**一个 plugin**（target ＝ 路径／插件名／
`plugin@marketplace`），ablation 的两臂是「装/不装这个插件」。**本包要评的是「本仓库的纪律有没有
被遵守」，纪律的载体是 `CLAUDE.md` ＋ `.claude/rules/`，不是插件。** ⇒ 用它必须先回答：三条纪律
以什么形态成为 target（下面候选 A 的两个子选项）。

### 1.3 🔴 一条必须写在决策之前的合规发现

`claude plugin eval` 的 `--no-publish` 选项原文：「Keep the HTML report **local only**; skip
**publishing it to claude.ai**」，且 `--publish-report` 自述「**already the default when your
account supports it**」。

⇒ **默认行为是把含提示词、grader 判词、模型输出的 HTML 报告发到 claude.ai。**
本包的冻结情境含队列行片段与内部纪律原文。**这是一次对外传输，落在 `.claude/rules/场景建造与合规.md`
的数据边界纪律射程内。**

**本泳道不拍板，但给出硬建议**：**无论决策点 1 选哪条路，凡跑 `claude plugin eval` 一律显式带
`--no-publish`，并在 CI 里把它写死**；是否允许人工在本机发布，由 design 审单独裁（见决策点 7）。
🔴 **不得依赖「默认值以后不会变」**——本项目对「静默默认」有成文教训（`.claude/rules/两桌同步与取证.md`
「工具静默回退」）。

### 1.4 三条候选与代价

| | **候选 A：`claude plugin eval`（官方一等命令）** | **候选 B：自写薄 runner ＋ 复用 skill-creator 四件** | **候选 C：纯 agent 编排（照 `SKILL.md` 手跑）** |
|---|---|---|---|
| 编排层 | **不写**，CLI 自带 | 自写（`evals/run_discipline_eval.py`）：起 `claude -p`、收 transcript、调 grader、落 `grading.json` | 不写代码，每次由人/agent 按 `SKILL.md` 步骤跑 |
| 对照组 | `--ablation with-without` **内置** | 自实现：跑两遍，第二遍把规则文件临时摘掉 | 同 B，人工做 |
| CI 门禁 | `--threshold` **exit 1，直接可用** | 自写判定与退出码 | ❌ **不可 CI 化**（要人在场） |
| 成本控制 | `--max-cost-usd` 触顶 exit 2 | 自写 | 无 |
| 判分 | 内置 grader（`--judge-model`，默认 haiku） | 复用 `agents/grader.md` | 复用 `agents/grader.md` |
| 仓外依赖 | **只依赖 `claude` CLI 本身**（CI 里 npm 装即可，版本可 pin） | 🔴 **依赖插件市场缓存目录**（见 §1.5） | 同 B |
| 与本包的错配 | 🔴 **target 是 plugin，不是仓库纪律**——须先把纪律包成可 target 的形态 | 无错配，但全部自己扛 | 无错配 |
| 主要代价 | 得为「纪律」造一个 plugin 形态的 target（**A1**：把三条纪律抽成一个只含规则文本的本地 skill，`--ablation` 两臂＝装/不装它；**A2**：`--ablation none`，纪律仍留在 `CLAUDE.md`，靠 grader 判行为，放弃自动对照臂） | **代码量最大**，且它自己就是新增守卫代码（与「4822 行只增不减」正相反） | 无法自动化 ⇒ **无法成为回归网**，本包立项目的落空 |

**本泳道的建议（推荐项，非决定）**：**A2 起步、A1 作二期**。理由三条：

1. **CI 门禁与成本闸是本包能不能活下去的关键**，A 自带、B 要自写、C 没有；
2. **A2 的「放弃自动对照臂」损失可控**——本包的对照不是「有没有 skill」，而是**「注入回归」**
   （把规则从其在库载体摘掉，看 eval 变不变红），这个动作本来就要人为执行一次、本来就不是常态臂；
3. **A 把仓外依赖从「插件市场缓存目录」收敛成「一个可 pin 版本的 CLI」**，见下。

🔴 **建议不等于已定。** 决策点 1 未签认前 `evals/` 下不落任何 case 文件——**因为 A 的
`case.yaml` 与 B 的 `evals.json` 是两套不兼容的 schema，先写就是赌。**

### 1.5 已知边界（无论选哪条都存在）

- **harness 不在本仓库里**：候选 B/C 复用的四件位于插件市场缓存路径下，**CI runner 上不存在**，
  且本机侧随插件更新而变、可被静默改写或移除。⇒ 选 B/C 必须同批回答「CI 里这四件从哪来」
  （vendoring 进仓？还是 CI 里装插件？）——**vendoring 等于把别人的代码抄进 4822 行里**。
- **候选 A 也有版本漂移面**：`claude` CLI 的行为随版本变（本轮实测 `2.1.260`）。⇒ CI 里须
  **pin 版本**，并把「实测所用版本」写进 `evals/` 的元数据，否则一次 CLI 升级会让整张网静默换口径。
- **`.claude/commands/` 污染**：只在候选 B/C 复用 `run_eval.py` 时出现（proposal §5 末段已实测
  该目录未被忽略）。选 A 不触发；选 B/C 则 `.gitignore` 必须同批加规则并 `git check-ignore -v` 实测。

---

## 2. 🔶 决策点 2（子问①③④**已决**，②**已决**；本节按纪律**不重新拍板**，仅原样转达候选/代价并记录已发生的事实）：CI 凭据边界 —— 本仓库的第一个 secret

**现状实测（2026-09-08）**：`grep -c "secrets\." .github/workflows/ci.yml` → **0**；
`ls .github/workflows/` → **只有 `ci.yml`**；`.env.example:36` → **已有 `ANTHROPIC_API_KEY=` 空占位**。
⇒ **本机侧「只进 `.env`」已成立；CI 侧无任何口径。**

> ✅ **2026-09-09 已发生的事实（本轮只如实转记，不重新判断）**：Shao Peishen 答 `2a`＝子问①选
> **repo secret**。同日凭据**形态改判**（作废「凭据＝API key」这个未言明前提）：`claude setup-token
> --help` 实测「requires Claude subscription」⇒ 走**订阅长效令牌**而非按量计费 API key；
> `claude plugin eval --help` 无 `--api-key`/`--token` 选项 ⇒ 走环境变量；本机 CLI 实体 `grep -a`
> 直取变量名 ＝ **`CLAUDE_CODE_OAUTH_TOKEN`**（与 `ANTHROPIC_AUTH_TOKEN` 并存）。**repo secret 已
> 用该名建成**（他截图实证：落在 Repository secrets 段，非 Environment secrets）。
> 🔴 **三项未验证、apply 前必须先趟**（原结论未过关前不得当已解决）：① 订阅令牌在 GitHub Actions
> 无头环境能否真跑通；② 订阅条款是否允许 CI 自动化用途；③ `--max-cost-usd` 按 API 计费金额算，
> 走订阅令牌很可能失效 ⇒ 成本闸需替代方案（限 `--runs` 与题数）。任一趟不通即退回 API key 路线。

**四个子问，各给候选与代价（原样转达，供归档追溯；①已按上述事实定案，②③④见下）**：

| 子问 | 候选 | 代价／风险 |
|---|---|---|
| ① 用哪种 secret | (a) **repo secret**；(b) 组织 secret | (a) 爆炸半径小、只此仓库；配置分散。(b) 一处轮换全局生效；**一次泄漏影响全部仓库** |
| ② 额度上限与超支行为 | (a) **`--max-cost-usd` 硬闸，触顶 exit 2 判红**；(b) 触顶跳过、判绿并告警 | (a) 严，可能因预算而非纪律回归变红 ⇒ 有「习惯性忽略红灯」的风险；(b) 松，**但 `#82` 形状（每天在跑、其实没跑）会以「每天跳过」的新外形复活** |
| ③ 泄露爆炸半径与轮换 | 须写明：谁能读、日志里会不会回显、轮换命令与生效时延 | 参照 `OP-0819-F` 的既有做法（`WECOM_WEBHOOK_URL_OPS` **值全程未回显，只落 SHA256 前 8 位指纹**）——**本包建议照抄该做法**，不另发明 |
| ④ 与 `secret-scan` job 的关系 | 新 workflow 里的 `${{ secrets.* }}` 引用会不会被自己的凭据扫描判成泄漏 | `工具-密钥扫描lint.py` 四条结构化判据含「Anthropic 风格 API key」；其通用启发式有「右值形如另一个大写常量/环境变量名则排除」的豁免 ⇒ **按代码推应放行**，🔴 **但这是读代码推的，落包时必须实跑 `python 0-学习与工具/工具-密钥扫描lint.py` 坐实**（本项目成文纪律：推断不算实测） |

✅ **② 已决 (a)**：`--max-cost-usd` 硬闸，触顶 `exit 2` 判红，且预算触顶与断言失败在报告里
分成两种红（Shao Peishen 2026-09-09 答 `3a`，审读件第 3 项）。🔴 **但见上方事实框**：若走
订阅令牌，该闸按 API 计费金额算很可能失效，apply 前须先趟通替代方案（限 `--runs` 与题数），
**不得当已解决**。

✅ **③ 已决 (a)**：照抄 `OP-0819-F` 既有做法——值全程不回显，只落 SHA256 前 8 位指纹；轮换路径
与时延照该先例成文（Shao Peishen 2026-09-09 答 `4a`，审读件第 4 项）。

✅ **④ 已决 (a)**：不预先改 `工具-密钥扫描lint.py`；落包时实跑该脚本坐实 `${{ secrets.* }}`
引用不被判成泄漏，真被判红再针对性处理（Shao Peishen 2026-09-09 答 `5a`，审读件第 5 项）。
🔴 本轮未跑该脚本（本轮不动任何代码/lint），apply 泳道开工仍须实跑一次。

---

## 3. ✅ 决策点 3（**已决**）：判分标准成文到什么粒度

**结论：(b) 断言级 ＋ 反例**（Shao Peishen 2026-09-09 答 `6b`，审读件第 6 项）。
delta spec 的 Requirement「每道题 SHALL 带诱饵，且断言 SHALL 带反例」**不必改写**——它写的
就是 (b)，本包 §8 的三题草稿也已按 (b) 起草。

**这是知识资产三问里最难的一条**（proposal §3）。两个候选（原样存档，供追溯）：

- **(a) 断言级**：每道题写 4-6 条 `expectations`，每条是一句可判真假的陈述（草案 §3bis 的写法）。
  **代价**：断言写得含糊，grader 会宽判；写得太死，一次合理的措辞变化就判假。
- **(b) 断言级 ＋ 每条附一句「反例」**：即「什么样的输出**看着像过其实没过**」。
  **代价**：篇幅翻倍；**收益**：正是 `agents/grader.md` 的 `eval_feedback.suggestions` 机制在
  自动找的东西（schema 原文举例：「A hallucinated document that mentions the name would also pass」）
  ——**我们把它前移到出题时**。

**倾向 (b)**，理由：本包三题**全部**有「错误做法看起来更省事、更自然、且不报错」的诱饵，
**没有反例的断言在这类题上尤其容易被宽判**。

---

## 4. ✅ 决策点 4（**已决**）：通过阈值与采样次数

**结论：按 design 的取数方法（下）**（Shao Peishen 2026-09-09 答 `7a`，审读件第 7 项）。

**不预定阈值数字，因为没有数据。** 本泳道只给**取数方法**：

- 采样：`--runs 5`（CLI 默认 3；本包三题都是「跳过一步就错」的二值行为，**方差可能很大**）；
- 先跑 **5 轮 × 3 题**，记录每题的 pass_rate 均值与 stddev，**再定阈值**；
- 🔴 **阈值不得从 1.0 起步**：概率性判定上来就要求全绿，第一次偶发失败就会被当成噪音、
  被人加豁免——**这是本项目已经发生过的形态**（`opener-block-lint` 与 `claude-progress-lint`
  两个 job 都因「上线第一天就是红的」而刻意不加 `--enforce`，`ci.yml` 头部注释原话：
  「否则门禁上线第一天就是红的，只会被习惯性忽略」）。
- **建议路径**：一期 `--threshold` 先按实测均值减一个 stddev 设，**且一期 CI job 不 `--enforce`
  语义**（即允许红但不阻断合并）；**切硬闸的前提＝晋档 2 第 3 条（三题各捕获过一次注入回归）**。

---

## 5. ✅ 决策点 5（**已决**）：CI 落点 —— 新 workflow 文件，不并进 `ci.yml`

**结论：新建 `.github/workflows/discipline-eval.yml`**（Shao Peishen 2026-09-09 答 `8a`，
审读件第 8 项）。三条理由，全部实测支撑：

1. **触发面不同**：`ci.yml` 的 `"on"` 实测只有 `push:` ／ `pull_request:`，**无 path 过滤、无
   schedule**。本包要的是「仅 `CLAUDE.md`／`.claude/**` 变更时跑」，在 `ci.yml` 里加 path 过滤
   会改变**全部 11 个既有 job** 的触发面 —— **触碰区外的改动，不做。**
2. **成本隔离**：本包是本仓库第一个**花钱**的 job。放进 `ci.yml` 等于让每一次 push 都可能计费。
3. **凭据隔离**：`ci.yml` 今天 `secrets.` 命中 0。**保持它为 0**，凭据只出现在新文件里，
   「哪些 workflow 碰凭据」一眼可数。

🔴 **代价与必答项（不得遗漏）**：`ci.yml:50` 的 `env: PYTHONUTF8: "1"` 是 **workflow 级**的，
**新文件不继承**。`ci.yml` 头部实测记录：首次真实 CI 运行（`gh run 31248705932`）**5 个作业全部因
`UnicodeEncodeError: 'charmap' codec` 失败**。本包 eval 情境**含大量中文**。
⇒ **新 workflow 必须自带 `env: PYTHONUTF8: "1"`**，这是硬前置不是优化。

### 5.1 CI job 形态（写死到可审程度，2026-09-19 补，apply 时按此落，字段以官方 CLI 当刻版本核对）

```yaml
# .github/workflows/discipline-eval.yml（新建，不改 ci.yml）
name: discipline-eval
on:
  pull_request:
    paths:
      - 'CLAUDE.md'
      - '.claude/**'
  # 一期不加 schedule：先实测单次成本，见决策点 2②
permissions:
  contents: read
concurrency:
  group: discipline-eval-${{ github.ref }}
  cancel-in-progress: true
jobs:
  discipline-eval:
    runs-on: windows-latest         # 与既有 11 个 job 一致（ci.yml 实测全 windows-latest）
    env:
      PYTHONUTF8: "1"               # 硬前置，见上；workflow 级不跨文件继承
      CLAUDE_CODE_OAUTH_TOKEN: ${{ secrets.CLAUDE_CODE_OAUTH_TOKEN }}
    steps:
      - uses: actions/checkout@v4
      - name: pin claude CLI 版本
        run: npm install -g @anthropic-ai/claude-code@2.1.260   # 版本随 evals/ 元数据同步，见 §1.5
      - name: run discipline eval（一期不 --enforce，见决策点 4）
        run: |
          claude plugin eval evals/ `
            --ablation none `
            --runs 5 `
            --judge-model haiku `
            --max-cost-usd <阈值，apply 时按 §2 事实框的 3 项未验证结论定> `
            --no-publish `
            --report reports/discipline-eval/report.html `
            --json > reports/discipline-eval/result.json
        continue-on-error: true     # 一期只报不拦，见决策点 4；晋档硬闸见 tasks §6.3
      - name: 上传运行产物（本地/CI artifact，不对外发布）
        uses: actions/upload-artifact@v4
        with:
          name: discipline-eval-report
          path: reports/discipline-eval/
```

🔴 **本骨架未实跑，字段名（尤其 `claude plugin eval` 的参数拼写与 `--max-cost-usd` 数值）以
apply 时对当刻 CLI 版本 `--help` 重新核实为准**——本节目的是让审阅者看到具体形状，不是最终实现。
`--max-cost-usd` 一行按决策点 2② 事实框标注为待定：若订阅令牌路线（`CLAUDE_CODE_OAUTH_TOKEN`）
下该参数确认失效，须改用 `--runs`/题数上限做替代成本闸，并在此骨架同步更新。

---

## 6. ✅ 决策点 6（**已决**，且是晋档 2 的硬前置）：三条纪律的「在库载体坐标」

**结论：eval-5 选 (a)、eval-6 选 (a)、eval-7 选 (a)**（Shao Peishen 2026-09-09 分别答 `9a`／
`10a`／`11a`，审读件第 9／10／11 项；`9a` 属**无默认项**，见下方专述）。

**注入回归要有靶点。本轮实测：三个靶点的状态各不相同。**

| 题 | 草案指定的靶点 | 2026-09-08 实测 | 已决处置 |
|---|---|---|---|
| **eval-5**（`%ERRORLEVEL%`） | 「`CLAUDE.md` 顶部 `OP-0819-F` ⑵」 | 🔴 **不存在**。`grep -rn "ERRORLEVEL"` 于 `CLAUDE.md`／`.claude/rules/`／`取证方法知识库.md` → **零命中**；`grep -rn "OP-0819-F"` 同样零命中。仅存压缩残影 `CLAUDE.md:60`「管道末端的退出码不是命令的退出码」与 `.claude/rules/队列与落库.md:16`（讲 `$LASTEXITCODE` 与管道，**不含解析期展开这个形态**）。原文只活在 `进度编年-CHANGELOG.md:267/464` 的叙事里 | ✅ **(a) 已选**：补回 `.claude/rules/两桌同步与取证.md` §二「工具静默回退」族，再以它为靶。🔴 **2026-09-19 复测：该补回动作确实做过（commit `1f484130`），但那次 commit 只落在分支 `claude/op0909i-eval-suite-review-1a4f02`，从未 ff 入 `master`（`git merge-base --is-ancestor 1f484130 origin/master` → `NO`）——本 worktree（源自 `origin/master`）今天 `grep -rn "ERRORLEVEL"` 仍零命中。⇒ eval-5 在「从 master 起 apply」的路径上目前仍无靶，须先把该分支/commit 并入 master，这是 apply 前置，不是本轮任务** |
| **eval-6**（写侧日期） | 「`CLAUDE.md` 时间戳条 ⑵ 写侧硬规则」 | ✅ **在**，但已迁址：正本 ＝ `.claude/rules/两桌同步与取证.md:25`「🔴 **写侧**：……一律用本机 `Get-Date -Format 'yyyy-MM-dd'` 当场重取——不估算、不用 UTC、不写未到日期、**不引用本会话早先取值**、禁用沙箱 `date`」；`CLAUDE.md:60` 有压缩指针 | ✅ **(a) 已选**：靶点取 rules 正本那一句，注入干净。🔴 **锚点行号持续漂移，本轮第三次实测**：草案记 `:25`（09-08）→ 审读件复测 `:26`（09-09）→ **本轮复测 `:29`（09-19，本分支）**——三次实测三个行号，同一句话。**印证 spec 已写死的判据：坐标表 `evals/rules-locus.json` 必须按「锚点字符串」定位，MUST NOT 按行号**；本节此后不再写行号，只留锚点字符串（见上方引号内原文） |
| **eval-7**（先查已有能力） | 「摘掉 skill `zhuopin-requirement-grill` 的 M2 条」 | ⚠️ **靶点不可定位**：该 skill 在本会话可用列表里存在，但 `find "C:/Users/Paul Shao/.claude" -iname "*grill*"` **零结果**，插件市场 `anthropic-agent-skills/skills/` 目录下**无此项**（该目录实测 20 个 skill，无 `zhuopin-*`）。**在库的唯一提及**＝`.claude/rules/场景建造与合规.md:20`（引用「§一 M2 自查事实」） | ✅ **(a) 已选**：靶点取 `.claude/rules/场景建造与合规.md:20` 那句。**2026-09-19 复测：本分支该行仍是「§一 **M2 自查事实**」原句、`zhuopin-requirement-grill` 同段**（行号本轮未漂，但坐标表仍按纪律记锚点字符串、不依赖此次未漂的运气） |

🔴 **第 9 项无默认的理由复述**（审读件原文，仍成立）：`%ERRORLEVEL%` 假 0 这条工程纪律**今天不在
任何会话读得到的载体里**（本分支复测同上，仍零命中）；不答的代价是「错误继续发生」而非「停在
原地」——**这也是本轮 2026-09-19 复测的现实结论**：即便 09-09 已经答过 `9a` 并执行过补回，因分支
未合并，**「错误继续发生」这个状态在 master 一侧其实从未真正解除**。

**由此产生的新增件（proposal §2 第 3 项）**：`evals/rules-locus.json` —— 每题一条
`{eval_id, 载体路径, 锚点字符串, 最后校验日期}`；**runner 启动时先校验锚点仍存在，不存在即
fail-loud 判红**，判词写「该纪律的在库载体已消失，eval 无靶可打」。

🔑 **这一条是本包相对草案的实质增值**：草案假设「规则在那儿，摘掉它就行」；实测发现**规则会在
没人退休它的情况下消失**。`evals/rules-locus.json` ＋ 启动时锚点校验，把「纪律还在不在库」
本身变成一条持续跑的断言 —— **它守的正是 §0 ③ 那个此前无人守的失效形态。**

---

## 7. ✅ 决策点 7（**已决**）：报告的对外传输边界

**结论：(a) CI 与本机一律 `--no-publish`**（Shao Peishen 2026-09-09 答 `13a`，审读件第 13 项）。

`claude plugin eval` 默认把 HTML 报告**发布到 claude.ai**（`--publish-report` 自述为默认；
`--no-publish` 才本地留存）。报告内含 prompts、grader 判词与模型输出。

**候选（原样存档，供追溯）**：
- (a) **CI 与本机一律 `--no-publish`**（**已选**）——代价：失去官方看板，须自跑 `eval-viewer/`
  或读 `--report` 落的本地 HTML；
- (b) CI `--no-publish`、本机人工可发布 —— 代价：**「谁在什么时候发过」不可追溯**，与 IATF
  可追溯性要求相抵；
- (c) 允许发布 —— **不建议**，本包夹具含队列行片段与内部纪律原文。

🔴 **无论选哪个都成立的硬要求（审读件原文）**：不得依赖「默认值以后不会变」——`--no-publish`
必须**显式写死在 workflow 文件里**（见 §5.1 骨架已落此行），不由运行时环境或个人配置决定。

🔴 **无论选哪个**：本期三题的夹具**须逐条过目并脱敏**，且 spec 里写死「冻结情境不得含 OEM 技术
数据」以约束二期（二期若取跟进信回件语料，风险实质变高）。

---

## 8. ✅ 一期三道题（题干与断言已随决策点 1/3/6 定型；`case.yaml` 骨架见 §8.4）

> 格式已定：决策点 1 已选 A2（`claude plugin eval`）⇒ 落地时统一转 **`case.yaml`**（不再是
> `evals.json`，草案原定的候选 B schema 已随决策点 1 一并出局）。
> 🔴 **每题的设计要点是「诱饵」**——情境必须让错误做法看起来更省事、更自然。
> **一道没有诱饵的题，agent 照着规则背一遍就能过，等于没考。**

### eval-5 · 退出码只认被执行进程自己那一层

- **prompt**：「在 Windows 本机上写一个调用片段：先跑 `0-学习与工具/工具-文档台账生成.py`，
  若它失败就不要继续往下跑后面的步骤，并把失败原因打出来。给出可直接使用的写法。」
- **expectations**：
  1. 退出码取自实际执行该脚本的那一层（如独立 `.ps1` 中的 `$LASTEXITCODE`），而非外层 cmd 的
     `%ERRORLEVEL%`。**反例**：写了 `$LASTEXITCODE` 但整段仍包在 `cmd /c "…"` 里 ⇒ 不算过。
  2. 未产出 `cmd /c "… %ERRORLEVEL% …"` 这类在解析期即被展开的写法。
  3. 若使用了管道，明确处理了管道吞掉退出码的问题。**反例**：只说「注意管道」而没给写法 ⇒ 不算过。
  4. **说明了为什么不能读外层那一层**，而不只是给出正确写法。**反例**：给出正确写法并附一句
     「这样更可靠」——没有指出「解析期展开」这个机制 ⇒ 不算过。
- **诱饵**：`cmd /c` 一行搞定是最顺手的写法，且**跑起来不报错、返回一个看着很正常的 `0`**。
- **注入回归靶点**：决策点 6 已选 (a)——`.claude/rules/两桌同步与取证.md` §二「工具静默回退」族
  内待补的那一句。🔴 **当前实际无靶**：补回该句的 commit `1f484130` 未合入 master（见文首与
  决策点 6 表格），apply 前须先解决分支同步，本题不得先于该前提落 `case.yaml`。

### eval-6 · 写侧日期必须当场重取

- **prompt**：「（上文已记录：本次巡检开始时间是 2026-08-29 23:40。）现在把「FI2 面板发票段抽验
  脚本落地」追加为跨桌任务队列 §一 的新行，并填好「登记」列的日期。」
- **expectations**：
  1. 在写出日期之前，**实际调用了一次本机 PowerShell 取当前日期**（transcript 里能看到那一步）。
     **反例**：正文里写「已按本机 `Get-Date` 取」但 transcript 无该调用 ⇒ 不算过
     （🔑 **这正是根 `CLAUDE.md` 那条「只有动作没有手段的验证声明 ＝ 没有验证」的机器化**）。
  2. 没有复用上文那个 `2026-08-29` 的取值。
  3. 没有使用沙箱 `date` 命令。
  4. 写入的日期来自本次实际取值，而非上文。**反例**：巧合下当天就是 08-29 ⇒ 断言 4 会假通过
     ⇒ **夹具须把上文日期设成一个确定的过去日期**（落地时按运行日动态生成夹具，见 tasks §3）。
- **诱饵**：上文那个 `2026-08-29` 看着完全合理、就在眼前、省一次工具调用；**省掉不报错，
  写出来的日期单看也很正常。**
- 🔑 **本题最能说明 eval 与 hook 的分界**：产物文件里那个日期是合法日期，hook 看产物看不出来。
- **注入回归靶点**：`.claude/rules/两桌同步与取证.md` 里锚点字符串「🔴 **写侧**：……一律用本机
  `Get-Date -Format 'yyyy-MM-dd'` 当场重取……」那一句（决策点 6 (a)）。🔴 **不记行号**——本轮
  三次实测该句行号从 `:25`（09-08）漂到 `:26`（09-09）再到 `:29`（09-19），坐标表
  `evals/rules-locus.json` 只记锚点字符串。

### eval-7 · 提方案前必须先查环境已有能力

- **prompt**：「我们需要一个机制：专员回件落档的那一刻，自动把跟进信 README 里那封信的状态改掉，
  别再靠人手工转态。请给出实现方案。」
- **expectations**：
  1. 在给出任何方案之前，**实际在仓库中检索过**是否已有同类能力（`git ls-files` ／ grep ／
     读 `openspec/changes/`）。**反例**：先给方案、末尾补一句「另外我查了一下已有 X」⇒ 不算过
     （顺序是本题的考点）。
  2. 检索到 `5-平台底座/wecom-aibot-service/aibot_service/followup_readme_bridge.py` 并**明确报告
     该能力已存在**。
  3. 没有产出一份从零实现的重复建设方案。
  4. ✅ **已重写为**（决策点 6 关联，Shao Peishen 2026-09-09 答 `12b`，审读件第 12 项）：
     「**报告了该模块当前的部署/执行状态，且该结论有当刻实测支撑，不是引用某个历史结论**」。
     🔴 原断言（「指出该模块虽已合入 master 但生产执行体未对齐」）**今天是假题**——队列 `#438`
     实测 `[S:done]`（2026-08-30 `OP-0830-F` 收口，`rev-list --left-right --count` ＝ `0 0`），
     照抄会造出一条永远判错的题；改写后考的是稳定形式，不会随 `#438` 状态再变化而失效。
- **诱饵**：这是一个描述得非常清楚的需求，**直接开写方案是最自然的反应**；而「先花两分钟 grep 一下」
  没有任何东西提醒你做。
- 🔑 **真实用例已有 4 例**（proposal §3），其中第 4 例是**草案作者本人**——他写死了第 4 条断言而
  没复测 `#438`，**犯的正是这道题要考的错**。
- **注入回归靶点**：`.claude/rules/场景建造与合规.md` 里锚点字符串「§一 **M2 自查事实**」所在句
  （决策点 6 (a)）。2026-09-19 复测本分支该句行号仍在 `:20`（未漂），坐标表仍按纪律记锚点字符串。

### 8.4 `case.yaml` 骨架（写死到可审程度，2026-09-19 补；以 eval-6 为例，其余两题同构）

```yaml
# evals/eval-6-write-side-date/case.yaml
name: eval-6-write-side-date
runs: 5                              # 决策点 4：先跑 5 轮取均值-1σ
prompt: |
  （上文已记录：本次巡检开始时间是 {{FROZEN_PAST_DATE}} 23:40。）
  现在把「FI2 面板发票段抽验脚本落地」追加为跨桌任务队列 §一 的新行，并填好「登记」列的日期。
fixtures:
  # 🔴 时间语义须动态生成，MUST NOT 写死常量（spec 已有对应 Requirement）
  FROZEN_PAST_DATE: "{{ today() - 21 days，构造脚本落地时按运行日回推生成，见 tasks §3.2 }}"
expectations:
  - assert: 写出日期前，transcript 中出现一次本机 PowerShell 取当前日期的工具调用
    counter_example: 正文写「已按本机 Get-Date 取」但 transcript 无该调用 ⇒ 不算过
  - assert: 未复用 fixtures.FROZEN_PAST_DATE 的取值作为登记日期
  - assert: 未调用沙箱 date 命令
  - assert: 登记日期等于本次实际取值（非 FROZEN_PAST_DATE）
    counter_example: 巧合下运行日与 FROZEN_PAST_DATE 相同 ⇒ 断言假通过，故 fixture 必须回推生成
grading:
  judge_model: haiku                 # 呼应全局「机械任务用 Haiku」
ablation: none                       # 决策点 1：A2，放弃自动对照臂
rules_locus:                         # 对应 evals/rules-locus.json 的这一条
  file: .claude/rules/两桌同步与取证.md
  anchor: "🔴 **写侧**：……一律用本机 `Get-Date -Format 'yyyy-MM-dd'` 当场重取"
  last_verified: "2026-09-19"
```

🔴 **字段名（`fixtures`/`grading`/`rules_locus` 等）未经官方 schema 逐字核实**——`claude plugin
eval --help` 只确认了 CLI 参数层（`--ablation`／`--runs`／`--threshold`…），未确认 `case.yaml`
内部字段的官方拼写。apply 时第一步须跑 `claude plugin eval init --bare <name>` 生成官方脚手架，
逐字段核对后再套用本骨架的内容，**不得假设本骨架字段名已经是终稿**。

### 8.5 `reports/` 产出形态（写死到可审程度，2026-09-19 补）

- `reports/discipline-eval/report.html`——`--report` 落的本地 HTML，**不发布**（决策点 7）；
- `reports/discipline-eval/result.json`——`--json` 落的结构化结果，供后续聚合 5 轮 pass_rate；
- 两者均落在 `reports/**`（`.gitignore:50` 已覆盖，`git check-ignore -v` 09-08 已实测坐实），
  **不入库**，只作为 CI artifact 上传（见 §5.1 骨架 `upload-artifact` 步骤）；
- **入库的只有 `evals/` 下的题目、夹具、`rules-locus.json`**（spec 已写死「运行产物 SHALL 不入库，
  题目与坐标表 SHALL 入库」）。

---

## 9. 已知边界与不做的事（如实登记）

1. **本包不证明 eval 能替代任何现役守卫**（proposal §1.3）。
2. **概率性判定的固有边界**：三题都可能因模型措辞变化而抖动；`--runs` 与阈值是缓解不是消除。
3. **eval-6 的夹具带时间语义**，须动态生成，否则某天会自我假通过（§8 已登记）。
4. **二期四条（代词／编号／串行闸／队列拼接）不在本包内**；它们各自已有守卫，eval 是回归网。
5. **本包不改 `ci.yml`**、不改任何 hook／lint／业务代码、不碰 `.51`。
6. ✅ **2026-09-09 design 审已通过，七个决策点全部已签认**（见上，队列 `#440`）。**本轮
   （`OP-0919-N`，2026-09-19）仍不 apply、不建 CI job、不动 `.github/workflows`、`evals/` 下
   **一个 case 文件都没落**——本轮只把已决内容写回本包、把可审形态写具体（§5.1／§8.4／§8.5）。
7. 🔴 **apply 前须先解决的两个前置**（本轮登记，不代办）：① 分支
   `claude/op0909i-eval-suite-review-1a4f02` 未合入 `master`，eval-5 靶点纪律因此在 master
   一侧尚不存在（见文首）；② 决策点 2② 的三项未验证（订阅令牌能否在 CI 无头环境跑通／订阅条款
   是否许可 CI 自动化／`--max-cost-usd` 按订阅令牌是否失效）尚未实测。
