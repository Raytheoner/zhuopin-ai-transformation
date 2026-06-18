---
title: "VP 实战练习册 — 照着敲就能跑，跑完能自己对答案"
created: 2026-06-10
audience: Paul（分管供应链与质量 VP，CS + 供应链背景）
定位: 《VP实战补强》的"可执行版"。三个练习全是真命令 + 真预期 + 文末自检答案；外加 claude-howto → 卓品实战的桥接表。
沙盒: claude-howto（本地 git 练手，纯可丢弃，碰不坏任何真项目）。
不影响主线: 全程不碰 §1 加固 / SC1 / 收割；练习①②在沙盒里跑，练习③只读不改。
---

> 《VP实战补强》讲"为什么、怎么想"；这份讲"现在就敲哪几行、该看到什么、做对了没"。挑当下用得上的一节，干活间隙花 15 分钟跑一个。

**两个路径先记住（Windows 终端里用）：**
- 沙盒（claude-howto）：`C:\Users\Paul Shao\OneDrive\Projects\claude-howto`
- SC8 测试：`C:\Users\Paul Shao\OneDrive\Projects\企业AI转型\4-数字员工\采购部\SC8-客户订单交期智能承诺\tests`

> ⚠️ 一个坑先说清：claude-howto 的远端是**别人的仓库**（github.com/luongnv89/...），你**没有 push 权限**。所以本练习册里的 git 练手**全在本地玩、不 push**——真正的 push→PR 这一环，你本来就在 `企业AI转型` 的真分支上每天做，不用在沙盒里造假。

---

## 练习① — Git 手感（claude-howto 本地沙盒，全程可丢弃）

**目标**：把"工作区 → 暂存 → 提交 → 看 diff → 分支"这条链跑出手感。

> claude-howto 现在本来就带几个它自己的未提交小改动。练习全程**只 add 你自己建的 `PRACTICE_SCRATCH.md`**，别动它自带的，就互不影响。

照下面一行行敲，右边是**你该看到什么**：

```bash
cd "C:\Users\Paul Shao\OneDrive\Projects\claude-howto"

git checkout -b practice/git-warmup     # → Switched to a new branch（开了个可丢弃分支）
git branch --show-current               # → practice/git-warmup（确认我在练习分支，不在 main）

echo "# 我的第一次 commit 练习" > PRACTICE_SCRATCH.md
git status                              # → Untracked files: PRACTICE_SCRATCH.md（红色，还没进暂存）

git add PRACTICE_SCRATCH.md
git status                              # → Changes to be committed: new file（绿色，进暂存了）

git commit -m "practice: 我的第一个练习提交"
git log --oneline -3                    # → 最上面一行就是你刚才那条提交

echo "再加一行看看 diff" >> PRACTICE_SCRATCH.md
git diff                                # → 绿色 +再加一行看看 diff（工作区比已提交多了这行）
```

**清理（练完痕迹清零）：**

```bash
git checkout main                       # 先切回 main
git branch -D practice/git-warmup       # 删掉练习分支
del PRACTICE_SCRATCH.md                 # 删掉练习文件（PowerShell 用 Remove-Item）
git status                              # → 应回到练习前的样子
```

**自检**：你能不看右边注释，说出每条命令"为什么这一步"吗？尤其 `add` 和 `commit` 的区别（暂存 = 挑要提交的；提交 = 存档点）。说得出 → 这条链你有手感了。

---

## 练习② — 环境意识（真机为准 + OneDrive 反面教材）

**目标**：体会"凡 git，以真机为准"，并认出"代码不该住云盘"的活例子。

```bash
cd "C:\Users\Paul Shao\OneDrive\Projects\企业AI转型"
git status                              # 真机上当前真实状态
git branch --show-current               # 真机上你真在哪个分支
```

**两个观察 + 自检：**
1. 回想之前 Cowork 沙箱报过"假 68 改动"——真机 `git status` 才是真相。**凡 git 操作，永远以你终端（Claude Code）的输出为准，别信 Cowork 沙箱的镜像。**
2. 注意到了吗：claude-howto 和 企业AI转型 **都住在 `OneDrive\Projects\` 下**。这正是我们说的反面教材——云同步会动 `.git`。学习库（claude-howto）无所谓；但你的**卓品真代码**理想是放 `C:\dev\`，靠 GitHub 备份。你现在的折中是"开发时暂停 OneDrive 同步"——可用，但记住这是折中，不是最佳。

---

## 练习③ — 审 AI 产出（SC8 二十个测试 → 六条门禁）⭐最值钱

**目标**：练"审测试报告"的真功夫——核心不是看"全绿",是看**"该测的场景测全了没"**。

**第一步，把 20 个测试名列出来：**

```bash
cd "C:\Users\Paul Shao\OneDrive\Projects\企业AI转型\4-数字员工\采购部\SC8-客户订单交期智能承诺\tests"
findstr /n "def test_" test_*.py        # Windows；列出全部测试函数名
```

**第二步，自己判一遍（先别看下面答案）：**
打开《SC8 上线前置门禁》§3 那 6 条检查表，对照这 20 个测试，逐条问自己——
- 这条门禁，有没有对应的测试用例？
- 有没有哪条门禁**一个测试都对不上**？（这才是重点）
- 有没有测试覆盖不了、只能靠流程/文档的门禁？

判完，再翻下面对答案。

<details>
<summary><b>📋 点开对答案（自己判完再看）</b></summary>

**门禁 1（黄金基准：确定性偏差=0、置信度标注、关键路径）→ ✅ 测得很全**
- `test_golden_zero_deviation` —— 确定性偏差 = 0 的总闸
- `test_critical_path_is_latest_material` —— 关键路径取最晚物料（黄金基准核心算法）
- `test_high_confidence_all_feedback` / `test_low_confidence_no_feedback_applies_30` / `test_low_confidence_outsourced_applies_10` / `test_confidence_orthogonal_to_risk` / `test_heuristic_driven_by_config` / `test_unschedulable_when_no_lead_time` —— 置信度标注 + 启发式假设全套

**门禁 3（置信度阈值 + L2 人工确认，未确认不外发）→ ✅ 测得最扎实**
- `test_first_commitment_blocked` / `test_low_confidence_blocked` / `test_late_forecast_blocked` / `test_missing_requires_confirmation_field_blocked` —— 四种"必须拦下"触发
- `test_low_risk_auto_sends` / `test_blocked_then_approved_sends` —— 该放行的放行、拦下经确认后能发
- `test_approve_without_confirmer_is_blocked` / `test_approve_unknown_id_returns_false` —— 无确认人 / 未知 ID 一律拦（fail-closed）
- `test_enqueue_persists_pending` —— 待确认队列持久化（支撑人工确认流程）

**门禁 5（审计全链留痕、可追溯原记录、幂等）→ ✅ 覆盖到位**
- `test_forecast_audit_carries_full_decision` —— 预测决策全量入审计
- `test_correction_links_original_and_keeps_append_only` —— 更正关联原记录 + append-only
- `test_approve_sends_once_then_idempotent` —— 幂等，不重复外发

**门禁 2（错误/回滚 SOP 文档化 + Paul 确认）→ ⬜ 测试覆盖不了，本就该靠流程**
"文档化 + 人工确认"不是代码逻辑，测试测不了。没有对应测试是**正常**的——靠你签字门禁。

**门禁 6（先推内部/测试通道，再切真实客户）→ ⬜ 测试覆盖不了，靠部署流程**
环境切换/灰度，也不是单元测试范畴。正常。

**门禁 4（偏差监控 / 重算触发就位）→ ⚠️ 二十个测试里一个都没有！**
这就是你该抓出来的那条。它**是**代码逻辑（预测 vs 实际偏差超阈值告警），本该可测，却没测。
- 它不是"漏测忘了写"——是 MVP 阶段**没有真实进展数据**，偏差监控无从触发，所以合理推后到 `sc8-real-data-cutover`（切真实库）阶段再补测。
- **关键能力**：你要能说清"这条为什么现在没有"——是合理推后，不是偷工。这句话说得出，你就从"看全绿点头"升级成"能独立守门禁"了。

**一句话总结**：20 个测试把门禁 1/3/5 测透了；2/6 是流程门禁、测不了很正常；**4 暂缺、但有正当理由（推后到切库阶段）**。这就是"审测试 = 看该测的测全没"的完整一遍。

</details>

---

## 桥接表 — claude-howto 学什么，对应你卓品的哪个真活

claude-howto 教的是 Claude Code 功能的"抽象用法"。下面把它接到你的真项目上：每读一个模块，就知道"我已经在用的实例"和"接着在沙盒/真项目练什么"。

| howto 模块 | 学什么 | 你卓品里已经在用的实例 | 接着练什么 |
|-----------|--------|----------------------|-----------|
| 01 slash-commands | 自定义快捷命令 | OpenSpec 的 `/opsx:propose` `/opsx:apply` | 给 SC1/SC8 常用动作配一两条自己的命令 |
| 02 memory | CLAUDE.md 项目记忆 | 你三个仓库的 `CLAUDE.md`（L1 记忆） | 读它，对照你的 CLAUDE.md 还缺哪些"红线/节奏" |
| 03 skills | 可复用能力包 | 你装的 `md-to-word` Skill | 看它怎么写 SKILL.md，理解你那个 Skill 的结构 |
| 04 subagents | 专职子代理 | 你让 Antigravity 做"只读评审"就是这思路 | 理解"评审用子代理、绝不让它改关键文件"为何安全 |
| 05 mcp | 接外部系统 | 7/1 要申请的 U9C ERP MCP | 读它，把"U9C MCP 申请"在脑子里走通一遍 |
| 06 hooks | 事件触发自动化 | （暂未用） | 了解即可；Phase 2 做质量门禁时再回来 |
| 07 plugins | 打包分发 | （暂未用） | 了解即可 |
| 08 checkpoints | 会话快照/回退 | 你"先 push 保险"的习惯就是手动版 | 学它的快照机制，少手动 push 几次 |
| 09 advanced | planning / thinking | 你审 design 前让它"先出方案停下"就是 planning 门禁 | 巩固"先方案后实现"的节奏 |
| 10 cli | `claude -p` 脚本化 | （暂未用） | 了解即可；将来批量任务用得上 |

> 读法建议：你现在是 **Level 2~3**（已会 CLAUDE.md、Skill、子代理评审、MCP 申请）。重点扫 **05 MCP（对口 U9C）** 和 **09 advanced（巩固审 design 节奏）**，其余按需。别从头读到尾——你早过了 Level 1。

---

## 用法
- 三个练习都是真命令、真路径、真答案。挑一个，干活间隙跑一遍，比看十篇教程强。
- 练习③ 最该做——它把你从"批准者"练成"能独立守门禁的把关人"，这是带 AI 团队最核心的本事。
- 判不准的，随时拿来跟我对。

---
*配套：《VP实战补强-git环境与审AI产出》（讲为什么）｜《Claude_Code自学路径与转型技术方案》（技术全景）。本文是"照着敲"的执行版。*
