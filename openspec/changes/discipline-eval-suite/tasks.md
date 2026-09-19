# discipline-eval-suite Tasks

> ✅ **2026-09-09 design 审已通过**（`OP-0909-I`，队列 `#440`，Shao Peishen 答 `1a，2a，3a`）——
> §0 七项决策点**全部已签认**，见下。
> 🔴 **`OP-0919-N`（2026-09-19）复测发现：本包（`openspec/changes/discipline-eval-suite/`）十天
> 未同步这批决策**——决策只落在队列行与一份未合并分支（`claude/op0909i-eval-suite-review-1a4f02`）
> 上。本轮把决策写回本包（`design.md` 逐点已标「✅ 已决」）、把 evals/CI/reports 形态写到可审程度
> （`design.md` §5.1／§8.4／§8.5），**但仍止步于此——不 apply、不建 CI job**。
> 🔴 **apply 前两个硬前置未清**（本轮登记，不代办，详见 `design.md` 文首与 §6）：
> ① 分支 `claude/op0909i-eval-suite-review-1a4f02` 未 ff 入 `master`，eval-5 靶点纪律
> （commit `1f484130`）在 master 一侧不存在；② 决策点 2② 三项未验证（订阅令牌 CI 可用性／
> 订阅条款／`--max-cost-usd` 是否失效）未实测。

---

## 0. 已签认（七项，2026-09-09 队列 `#440` 定案；本包不得进 apply、不得归档——见上方两个硬前置）

- [x] 0.1 **决策点 1：eval 用什么跑 ＝ 候选 A2**（`claude plugin eval`，`--ablation none`）。
      Shao Peishen 答 `1a`。`case.yaml` 骨架见 `design.md` §8.4。
- [x] 0.2 **决策点 2：CI 凭据边界 ＝ repo secret `CLAUDE_CODE_OAUTH_TOKEN`**（订阅长效令牌，非
      API key；Shao Peishen 答 `2a` 并已建成，见 `design.md` §2 事实框）；额度闸 `--max-cost-usd`
      硬闸（`3a`）；轮换/回显照抄 `OP-0819-F`（`4a`）；不预改密钥扫描器、落包时实跑坐实（`5a`）。
      🔴 **三项未验证仍未清**（见文首）。
- [x] 0.3 **决策点 3：判分标准 ＝ 断言级 ＋ 反例**。Shao Peishen 答 `6b`。§8 三题已按此起草。
- [x] 0.4 **决策点 4：阈值与采样 ＝ 先跑 5 轮取均值−1σ，一期不设 1.0、不阻断合并**。Shao Peishen
      答 `7a`。
- [x] 0.5 **决策点 5：CI 落点 ＝ 新建独立 `discipline-eval.yml`，不并进 `ci.yml`，自带
      `PYTHONUTF8`**。Shao Peishen 答 `8a`。骨架见 `design.md` §5.1。
- [x] 0.6 **决策点 6：三条纪律的注入回归靶点 ＝ 均选 (a)**：eval-5 补回
      `.claude/rules/两桌同步与取证.md`（`9a`，🔴 **补回 commit 未合入 master，见文首**）；
      eval-6 靶点取 rules 正本锚点字符串（`10a`，不记行号——三次实测三个行号）；eval-7 靶点取
      `.claude/rules/场景建造与合规.md` 锚点字符串（`11a`）。
- [x] 0.7 **决策点 7：报告对外传输边界 ＝ CI 与本机一律 `--no-publish`**。Shao Peishen 答 `13a`。
- [x] 0.8 **eval-7 第 4 条断言重写**（决策点 6 关联）：改为不绑定 `#438` 状态的写法。
      Shao Peishen 答 `12b`。

> ⚠️ **另有两项不属本包、但由本包起草时的实测触发，须由值周巡检另行处置**（已登记回写件，
> 见 §7）：
> - 队列 `#284` 的同族违反计数由 **+3 追加为 +4**（新增第 4 例＝草案作者未复测 `#438` 状态即写死
>   eval-7 第 4 条断言）—— **已过退休制阈值（3 次）**。
> - `%ERRORLEVEL%` 那条纪律的**在库载体已消失**（非退休、系瘦身时蒸发）—— 是否补回，与 0.6 同源
>   但影响面更大（它是一条通用工程纪律，不只是 eval 的靶）。

---

## 1. 前置取证（本轮已完成，逐条附核实手段）

- [x] 1.1 队列 `#440` 全字段读取：`python 0-学习与工具/工具-队列查询.py --row 440 --field all`
      （🔴 未 Read／grep 队列真身）。
- [x] 1.2 **推翻草案断言 ①**：`skill-creator/scripts/run_eval.py` 实为 **description 触发率 eval**
      ——核实手段＝读该文件 docstring 与 `main()` 的 `add_argument` 全集（`--eval-set`／`--skill-path`／
      `--trigger-threshold`…，**无任何参数吃 `evals.json`**）＋ `SKILL.md:225` 原文「spawn a grader
      subagent … Save results to `grading.json`」。
- [x] 1.3 **推翻草案断言 ②**：`python 0-学习与工具/工具-队列查询.py --row 438 --field status` →
      `[S:done]`，2026-08-30 `OP-0830-F` 收口 ⇒ eval-7 第 4 条断言已成假题。
- [x] 1.4 **推翻草案断言 ③**：`grep -rn "ERRORLEVEL" CLAUDE.md .claude/rules/ 0-学习与工具/取证方法知识库.md`
      → **零命中**；`grep -rn "OP-0819-F" CLAUDE.md .claude/rules/` → **零命中**；
      `grep -rln "ERRORLEVEL" --include=*.md .` → 13 个文件，**全部是叙事件**（CHANGELOG／队列／
      草案／派单件），无一是纪律载体。
- [x] 1.5 CI 现状实测：`grep -c "secrets\." .github/workflows/ci.yml` → **0**（退出码 1）；
      `ls .github/workflows/` → **只有 `ci.yml`**；`grep -n "PYTHONUTF8"` → `ci.yml:50` workflow 级；
      `grep -n "runs-on"` → 11 处全 `windows-latest`；`"on":` 段 → 仅 `push:` ／ `pull_request:`，
      **无 path 过滤、无 schedule**。
- [x] 1.6 `.env.example` 实测 **第 36 行已有 `ANTHROPIC_API_KEY=`（空占位）** ⇒ 本机侧凭据落点已存在，
      缺的只是 CI 侧口径。
- [x] 1.7 **`.gitignore` 覆盖逐条实跑 `git check-ignore -v`**（6 条探针，输出与退出码全文见
      `proposal.md` §5）：`evals/evals.json` 与 `evals/files/*` **未被忽略**（退出码 1，符合预期）；
      `reports/**` 与 `evals/__pycache__/**` **已被覆盖**（退出码 0，命中 `.gitignore:50` `**/reports/`
      与 `.gitignore:18` `__pycache__/`）；🔴 **`.claude/commands/x.md` 未被忽略**（退出码 1）
      ⇒ 若选中的跑法会往该目录写临时命令文件，须同批补规则。
      配套核实：`git ls-files reports` → **零输出**（`reports/` 完全未跟踪）。
- [x] 1.8 **第三条路的发现与取证**：`claude --version` → **2.1.260**；
      `claude plugin eval --help` 全文已读，要点＝`--ablation with-without` 自带无插件基线臂／
      `--runs`／`--threshold`（低于即 exit 1）／`--max-cost-usd`（触顶 exit 2）／
      `--judge-model`（默认 haiku）／`--no-publish`（**默认会发布到 claude.ai**）／
      `eval init --bare` 脚手架。
- [x] 1.9 守卫盘点复测三项：`0-学习与工具/hooks/sentinel-pronoun.ps1` 实测在；
      `git ls-files | grep followup_readme_bridge` → 实现与测试各一，在库；
      `openspec/changes/editlock-write-side-date-guard/tasks.md` 实测 `[x]` **0** ／ `[ ]` **29**
      （未开工）⇒ eval-6 仍是唯一守卫。
- [x] 1.10 eval-7 靶点可定位性实测：`find "C:/Users/Paul Shao/.claude" -iname "*grill*"` → **零结果**；
      `ls .../marketplaces/anthropic-agent-skills/skills/` → 20 个 skill，**无 `zhuopin-*`**
      ⇒ 该 skill 的规则本体不可编辑，在库唯一提及＝`.claude/rules/场景建造与合规.md:20`。

## 2. propose ＋ design 起草（本轮已完成）

- [x] 2.1 `proposal.md`：含三条 MANDATORY 全节（知识资产三问 ／ 验收与晋档条件 ／ 伴生文件
      `.gitignore` 覆盖，后者附 6 条真实 `git check-ignore -v` 输出）＋ 机制类强制的「本次退休哪一个
      既有守卫」论证 ＋ §0「三处推翻草案」。
- [x] 2.2 `design.md`：七个决策点，**逐点只给候选与代价、不预定**，各标「须签认」。
- [x] 2.3 `specs/discipline-eval-suite/spec.md`：9 条 ADDED Requirements，**全部与决策点 1 的选型无关**
      （不预设 harness），每条带 scenario。
- [x] 2.4 `openspec validate discipline-eval-suite --strict` 通过（实测结果见 §8）。

---

## 3. 题目与夹具落地（**未开工，决策已全部签认；实际阻塞＝文首两个硬前置**）

- [ ] 3.1 按 A2 把三道题转成 `case.yaml`（骨架见 `design.md` §8.4；**先跑
      `claude plugin eval init --bare` 核对官方字段名，不假设骨架字段已是终稿**）。
- [ ] 3.2 `evals/files/` 三份冻结情境夹具；**eval-6 夹具按运行日回推动态生成**（spec 已写死）。
- [ ] 3.3 每条断言的反例已在 `design.md` §8 草稿中；落地时逐条核对完整性。
- [ ] 3.4 eval-7 第 4 条断言按 `12b` 落地为改写后的稳定形式（`design.md` §8 已给定文字）。
- [ ] 3.5 夹具脱敏并逐条过目；确认零 OEM 技术数据。

## 4. 坐标表与 runner（**未开工，阻塞于文首硬前置①——eval-5 靶点未合入 master**）

- [ ] 4.1 `evals/rules-locus.json`：三条题各一条 `{eval_id, 载体路径, 锚点字符串, 最后校验日期}`
      （字段示例见 `design.md` §8.4 `rules_locus`）。**MUST 按锚点字符串，MUST NOT 按行号**——
      本轮三次实测同一句话行号从 `:25`→`:26`→`:29`。
- [ ] 4.2 运行前锚点校验：任一锚点不存在即 **fail-loud 判红**，判词写「该纪律的在库载体已消失，
      eval 无靶可打」；🔴 **MUST NOT 跳过该题后报绿。**
- [ ] 4.3 编排层按 A2 落地（不涉候选 B/C 的 `.claude/commands/` 污染问题）。
- [ ] 4.4 记录并 pin 所用 `claude` CLI 版本（本轮实测基线 `2.1.260`），写进 `evals/` 元数据。

## 5. CI 集成（**未开工，阻塞于文首硬前置②——凭据三项未验证**）

- [ ] 5.1 新建 `.github/workflows/discipline-eval.yml`（**不改 `ci.yml`**）。
- [ ] 5.2 该文件自带 `env: PYTHONUTF8: "1"`。
- [ ] 5.3 触发面：仅 `CLAUDE.md` ／ `.claude/**` 变更时跑；定时触发一期不做，实测成本后再议。
- [ ] 5.4 成本上限写死；预算触顶（exit 2）与断言失败（exit 1）在报告中分成两种红。
- [ ] 5.5 `--no-publish` 写死在 workflow 里，不由运行时环境决定。
- [ ] 5.6 **实跑 `python 0-学习与工具/工具-密钥扫描lint.py` 坐实**：新 workflow 里的
      `${{ secrets.* }}` 引用不被自己的凭据扫描判成泄漏。🔴 **按代码推应放行，但推断不算实测。**
- [ ] 5.7 复核 `grep -c "secrets\." .github/workflows/ci.yml` 仍为 **0**。

## 6. 晋档 2 与退休义务（**未开工**）——🔴 §6.3 为晋档硬条件，不得放宽

- [ ] 6.1 CI 真实跑通一轮（含中文编码实测）。
- [ ] 6.2 凭据就位（已建）且三项未验证已实测清零（见文首硬前置②）。
- [ ] 6.3 🔴🔒 **晋档硬条件（协议〇.9 措施 B 同族，写死的可检验承诺）：三条 eval 各须捕获一次
      人为注入的回归**——逐题故意把对应纪律从其在库载体（`.claude/rules/两桌同步与取证.md` ／
      `.claude/rules/场景建造与合规.md`）摘掉，该题 **MUST 变红**；逐题记录「摘的哪一句、红的哪
      几条断言」。**未逐一做到三题全部变红前，本包 MUST NOT 声称任何一条人守规则可退休
      （spec「套件 SHALL 以注入回归而非跑绿作为可信性依据」已写死此约束）。**
      ⚠️ **eval-5 的这一项当前阻塞于文首硬前置①**（补回的纪律 commit `1f484130` 未合入
      master，注入回归无靶可打；eval-6／eval-7 靶点已在，不受此阻塞）。
- [ ] 6.4 连跑 5 轮记录方差，得出阈值经验值（不是拍一个）。
- [ ] 6.5 🔴 **退休义务（协议〇.9 措施 B，写死的可检验承诺）**：**上线后 4 周内，以 eval 覆盖为依据，
      对至少 3 条人守规则执行一次退休判定（机制化／降为一行指针／删除，三选一），逐条登记；
      判定为「不退」的须写明理由。**
- [ ] 6.6 价值指标基线由 Shao Peishen 在启动前确认存档（风险型：三条形态交付后复发 0 次；
      质量型：4 周内完成退休判定的人守规则条数 ≥3）。

## 7. 队列回写与登记（本轮部分完成）

- [x] 7.1 回写件落 `1-转型规划/0-全景路线图/队列回写待补/B-0908_B-440.json`，由看护者／sweep 统一回灌
      （🔴 本泳道不写队列真身）。
- [ ] 7.2 值周巡检据 7.1 把 `#284` 的同族违反计数由 +3 追加为 **+4**，并按退休制阈值判定处置。
- [ ] 7.3 知识资产台账登记（《跨场景前置数据与知识库任务总表》§一.2）：持有人 Shao Peishen ／
      backup 孙涛。

## 8. 本轮验证留痕

- [x] 8.1 `openspec validate discipline-eval-suite --strict` — 结果与退出码见收工报告。
- [x] 8.2 `openspec validate --all --strict` — 确认本包未打破全库既有 passed 计数。
- [x] 8.3（`OP-0919-N` 新增）`openspec validate discipline-eval-suite --strict` 复跑 → `Change
      'discipline-eval-suite' is valid`，退出码 `0`（2026-09-19 实测，本轮文字改动未破坏校验）。

> ⚠️ **不得 `/opsx:apply`、不得 `/opsx:archive`**：§0 七项决策虽已全部签认，但**文首两个硬前置
> 未清**（分支 `claude/op0909i-eval-suite-review-1a4f02` 未合入 master ⇒ eval-5 无靶；决策点 2②
> 三项未验证）——§3-§6 仍未开工。不归档理由写在机器认得的地方（本行 ＋ 文首硬前置段）。
