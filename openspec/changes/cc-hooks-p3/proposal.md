# cc-hooks-p3 Proposal

> **状态：propose ＋ design 同批出件；本包的建造授权已由 §四 `#155`（2026-09-04，Shao Peishen 答 (a)(a)）与 §一 `#381` 子项⑸原文给出，本 session（`P3hooks-OP0904A`，opener `OP-0904-A`）据此同批 apply，不再等待独立一轮 design 回合——但仍产出完整 propose/design 存证（协议〇.9 与 CLAUDE.md §5 openspec 门槛的强制要求不因"已授权建造"而减免）。**
> **来源**：队列 §一 `#381` 子项⑸ 全文（规格正本）；方案正本 `1-转型规划/0-全景路线图/根CLAUDE.md彻底瘦身-方案-2026-09-03.md` §二 H3／§五。
> **openspec 门槛核对（根 `CLAUDE.md` §5 场景建造与合规 §二「机制/工具类模块的 openspec 触发门槛」）**：命中 **①「改变全项目口径」**（`PreToolUse` 新增一道对队列/接力卡 `Edit`/`Write` 的全项目适用拦截；`sweep-claude-md-size-guard` 阈值口径变更）与 **③「改变既有模块对外语义」**（`Edit`/`Write` 在同一输入下由必然成功变为可能被拒；`工具-共享文档编辑锁.py acquire` 新增回显段）。⇒ **必须走 openspec 且必须含 design 记录**。
> **本 session 内两处澄清（已获 Shao Peishen 答复，见收工报告，本提案据此定稿）**：① ⓐ `SessionStart` **不与** `#398` 心跳钩子合并（#398 已实测在生产独立生效，合并已无「省一次注册」的原始收益）；② ⓓ `Stop` 钩子**仍建**，接受子项⑷评估 ⒞ 已指出的「半覆盖」已知风险（§四 `#155` 晚于⑷评估、视为对该风险的知情重新拍板）。
> **2026-09-04 00:48 追加 ⓖ（会话中途插入，先于 ⓐ-ⓓ 建造完成）**：Shao Peishen 原话「每天碰到几十次，必须就地解决且根治」——`工具-opener块lint.py` 扩形态③④⑤ ＋ `--file` 单文件自检模式，判据正本＝模板库 §〇.00。已建造并通过 41 条单测＋全库真实扫描验证，见下「新增：ⓖ」与 Capabilities。

---

## Why

**根 `CLAUDE.md` 彻底瘦身方案（H3）的前提是「先机制在生产真实验活，后把对应人守文本降为一行指针」——但截至本包之前，五类候选机制（会话开场信息、UserPromptSubmit 常驻提示、队列编辑锁拦截、编辑锁按触碰区路由提示、rules 目录尺寸巡检）一个都还没有对应的可执行钩子。** 本包把这五类＋一类附带增强（Stop 收口检查）从「方案文本」变成「可注册、可验活、留审计」的六枚产出物，是瘦身方案 P3 阶段（§四「执行顺序」）唯一的内容。

**本包不改变任何业务口径、不碰真实数据、不涉鉴权**——六枚钩子的作用对象全部是「本仓库的协作机制自身」（会话开场信息、队列写入拦截、rules 尺寸）。

---

## What Changes

### 新增：ⓐ `SessionStart` 会话开场上下文注入

`0-学习与工具/hooks/hooks-sessionstart-context.ps1`：会话开场时打印本机 `Get-Date` 双标（本地＋UTC）、`git fsck --connectivity-only` 结果摘要、`origin/master..master` 与 `master..origin/master` 双向计数、本线待领队列行摘要（§一 `[S:open]` 且未标 🛑 的前 N 行标题）。

### 新增：ⓒ `PreToolUse(Edit|Write)` 队列/接力卡编辑锁门禁

`0-学习与工具/hooks/hooks-pretooluse-editlock-guard.ps1`：目标文件命中两份队列真身或两张接力卡（见 spec 覆盖清单）且当前无**有效（非陈旧）**编辑锁时，`exit 2` 拒绝本次 `Edit`/`Write`，反馈提示先跑 `acquire`。

### 新增：ⓔ `acquire` 触碰区路由提示

修改 `0-学习与工具/工具-共享文档编辑锁.py::cmd_acquire`（含 `_acquire_locked`）：占锁成功回显后，按 `--file`（解析后的绝对路径）与 `--note` 文本对根 `CLAUDE.md` §4 路由表的触发关键词做子串匹配，命中即追加一行「命中根 §4 路由表 → 先读 `.claude/rules/<X>.md`」提示（可多条、去重）。

### 修改：ⓕ `sweep-claude-md-size-guard` 纳入 `.claude/rules/*.md`

修改 `0-学习与工具/工具-落库sweep.py`：`_claude_md_targets` 新增 `.claude/rules/*.md` 覆盖（单份阈值 8 KB）；新增「rules 目录合计 ≤30 KB」判据；`CLAUDE_MD_ROOT_BYTE_CAP` 由 48 KB 降至 **12 KB**（现网实测根文件 9,703 B，P2 瘦身已落地，降阈值不会当场告警）。

### 新增：ⓑ `UserPromptSubmit` 常驻五条

`0-学习与工具/hooks/hooks-userpromptsubmit-standing-five.ps1`：每轮从根 `CLAUDE.md` 正文按机器可读标记抓取「称呼纪律／禁推断性别／需你定夺格式／粘贴端标注／默认项两前提」五条的**当前正文**（不另存副本、不硬编码副本文本），拼成 ≤300 B 摘要注入 `additionalContext`。**为使抓取可机器核验**，根 `CLAUDE.md` 对应五处各增补一个行内标记 `<!-- UPS5:n -->`（零语义改动，纯锚点）。

### 新增：ⓓ `Stop` 需你定夺格式检查

`0-学习与工具/hooks/hooks-stop-decision-check.ps1`：读 `transcript_path` 指向的会话记录，取最后一条 `assistant` 文本；若其中出现「需你定夺」类小节标题但正文缺 `(a)`/`(b)` 选项标签，`exit 2` 回退提示补全；若完全未出现该小节，**不拦截**（因为「本次无需决策」是合法状态，见根 `CLAUDE.md` §5 原文），仅当小节存在但格式不全时拦。**已知限制（继承自 `#381`⑷评估⒞，本次知情接受）**：仅覆盖 CC 桌，Cowork 桌无对应机制，根文件正文常驻判据字面不降级为纯指针（见「本次退休哪一个既有守卫」）。

### 新增：ⓖ opener 块 lint 扩三形态＋单文件自检（✅ 已建造完成）

修改 `0-学习与工具/工具-opener块lint.py::check_block`：新增形态③（CC 侧标题值须匹配
`[Win]MMDDX-<短名>`）／④（`【设置】` 六字段齐且顺序对）／⑤（首行须匹配
`[OP-MMDD-X]【CC／Cowork】<短名≤12字>`）；新增 `--file <路径>` 单文件自检模式。
release 侧 `工具-共享文档编辑锁.py::_opener_guard_violations` **零改动**自动获得新判据
（既有实现逐字复用 `check_block`，不按形态代码过滤）。**不需要任何 `.claude/settings.json`
注册**——本项是既有 CLI 工具与既有 release 咽喉的扩展，不是新增 Claude Code hook 事件。

### 修改：项目 `.claude/settings.json`

新增 `SessionStart`／`PreToolUse`／`UserPromptSubmit`／`Stop` 四类挂接（详见 tasks §7 与各 hook 交付的注册片段）。
🔴 **该文件命中 `~/.claude/protected-paths.json` 的 `*/.claude/settings.json`（`mode: block`）⇒ 必须由 Shao Peishen 或 Cowork 瘦身线人工执行**，与 `project-hooks-write-time-sentinels` 包完全同形，**不绕**。本包按注册对象拆成四段独立片段（各 hook 事件一段），允许分批注册、分批验活，不要求一次性全部装上。

### BREAKING

**是，且仅限 ⓒ**：`Edit`/`Write` 在「目标命中两份队列或接力卡、且无有效编辑锁」这一输入组合下，由必然成功变为被拒（`exit 2`）。其余五枚钩子（ⓐⓑⓓ 为只读注入型，ⓔⓕ 为既有工具的回显/阈值增强）不改变任何调用在给定输入下的成功/失败结果。

---

## 本次退休哪一个既有守卫（强制，协议〇.9 措施 B）

**代码层面：本包不退休任何既有机器守卫。** 逐项核实：

- ⓐⓑⓓ 三枚填补的是**此前完全没有机器覆盖的空白**（会话开场信息此前唯一来源是模型记忆；UserPromptSubmit 持续注入此前不存在；Stop 端格式检查此前不存在）——没有前代可退。
- ⓒ 是**新增**的强制层，架在协议〇.7 既有的 `acquire`/`release` 协作机制**之上**，不替代它——`acquire`/`release` 仍是唯一能真正写锁文件、走预留取号的入口，ⓒ 只是让「忘记先 acquire 就直接编辑」这一类此前无信号的失误当场报错，两者共存，不构成替换关系。
- ⓔ 是既有 `cmd_acquire` 函数内**新增的一段回显**，不替换其任何既有分支。
- ⓕ 是**直接扩展**既有 `sweep-claude-md-size-guard`（同一份代码、同一套判据骨架），不是并行新建一套 rules 尺寸判据——不产生"退休"意义上的新旧交替，是收紧覆盖范围。

**净变化**：机制守卫 **+5**（ⓐⓑⓒⓓⓔ 各一枚新增判据/回显路径）；既有守卫 **1 处扩展**（ⓕ）。

**真正对应的"退休对象"不是代码，是等量的人守文本**（根 `CLAUDE.md` §5 时间戳/开工三查/编辑锁复述等条目、`.claude/rules/队列与落库.md` 里编辑锁复述段）——但按 `#381` 硬约束「先机制在生产真实验活、后降指针」，**文本降级是本包生产验活之后的独立后续步骤，不在本次 apply 范围内**（tasks §8，前置条件未满足前不得勾选）。本包 apply 完成 ＝ 六枚钩子达到"可注册、有单测、有审计"状态，**不等于**可以降指针。

---

## 伴生文件的 .gitignore 覆盖（强制）

本变更新增一种自动生成文件形态：`reports/hooks-audit.jsonl`（六枚钩子共用，一次触发追加一行，不覆盖写、不按日期分片——JSONL 天然只增不改，靠后续巡检按行数或日期做保留策略，本包不新造保留机制）。

实测：

```
git check-ignore -v reports/hooks-audit.jsonl
# ⇒ .gitignore:35:**/reports/    reports/hooks-audit.jsonl    退出码 0（已被覆盖）
```

与既有 `reports/hooks-heartbeat.json` 同一条 `.gitignore` 规则覆盖，不需要新增忽略规则。

---

## 知识资产三问（强制，全景规划 §1.4 第 2 条）

**⑴ 本流程哪些判断是人脑默会经验？**

- **ⓔ 路由提示的关键词→规则文件映射**：目前判断"这次改动该读哪份 rules"完全靠人记住根 `CLAUDE.md` §4 路由表；映射规则本身不复杂（5 行表），但"记得去查表"这件事此前 100% 靠人。
- **ⓓ「需你定夺」格式是否完整**：判断一段文字是否构成合格的决策清单（含字母标签、写清代价、标默认项）此前完全靠模型自觉执行根 `CLAUDE.md` §5 的文字规则。
- **ⓒ 何时才算"已尽到协议〇.7 的锁义务"**：此前完全是习惯与记忆，没有任何时刻会被检查。

**⑵ 由谁显性化？（持有人 ＋ backup 双人制，实名）**

- 持有人：**Shao Peishen**（队列协议〇与 CLAUDE.md §5/§4 路由表的唯一权威来源，本包六枚钩子的判据全部直接转录自其已拍板文本，不新增判断）。
- Backup：**环境总线（Cowork）**——本包由环境总线派出建造（【设置】行「派出线：环境总线」），后续 rules/协议〇文本的维护责任沿既有分工归它。

**⑶ 用什么方法提取？**

**历史案例反推 ＋ AI 起草·专家批改的组合**：六枚钩子的判据全部来自 `#381` 原文与瘦身方案 §二 H3 表格里已经写死的设计（非本包新拟），本包只是把已经文字化的规则翻译成可执行脚本；ⓒ 的"何时算违规"直接复用协议〇.7 记录的两起真实撞号/覆盖事故（07-23、07-27）作为判据来源与测试夹具。

---

## 验收与晋档条件（强制，四档口径）

**本变更包交付后所处档位：档 3（内部服务）。** 理由同 `project-hooks-write-time-sentinels`：六枚钩子服务于内部构建流程，真实运行在生产工作区（非 mock），不产出对客交付物、不涉真实业务数据。

**晋下一档（档 4 对客交付）的条件：不适用，且本包永不晋档 4。** 钩子是内部构建环境设施。

**本档验收条件（逐条，全部可机器核）**：

1. `openspec validate --strict` 绿；
2. 六枚判据各自的单测覆盖对应 spec 的全部 Scenario，含反例（fail-open、无法判定时不得判"合规"）；
3. **每枚在真实 session 里真实触发一次**，`reports/hooks-audit.jsonl` 有对应记录（贴审计行进收工报告）——「探针通了 ≠ 机制通了」（沿用 `#381`⑷⒞ 与 `project-hooks-write-time-sentinels` 已确立的判据）；
4. ⓔⓕ 两处修改后，既有回归测试套件（`test_工具-共享文档编辑锁.py`／`test_工具-落库sweep.py`）零漂移通过。

**价值指标（业务 Champion ＝ Shao Peishen 确认基线）**：

- **质量型（主）**：「中途丢规则」类违反（称呼/需你定夺格式/编辑锁遗忘）事件数——基线见协议〇.7 与 CLAUDE.md §5 历史记录的既有事故清单，目标是六枚钩子生效后同类事故 CC 侧复发数 ＝ 0。
- **不设工时型指标**：本包买的是"不必再靠模型记住"，用工时衡量会低估其价值（同 H3/H4 precedent 的论证方式）。

---

## Capabilities

### New Capabilities

- `hooks-sessionstart-context`（ⓐ）
- `editlock-pretooluse-guard`（ⓒ）
- `editlock-acquire-routing-hint`（ⓔ）
- `hooks-userpromptsubmit-standing-five`（ⓑ）
- `hooks-stop-decision-check`（ⓓ）
- `opener-block-lint-format-checks`（ⓖ，✅ 已建造：41 单测 + 全库真实扫描验证，F1/F2/F3/F4/F5 命中 75/57/81/221/247，规则生效日前存量按既有 H1-H3 三层判据全部归历史件、不阻断）

### Modified Capabilities

- `sweep-claude-md-size-guard`（ⓕ：纳入 `.claude/rules/*.md`，根阈值 48 KB→12 KB）

---

## 不在本包 scope（明写，免得被读成已做）

- **文本降指针**——本包只到"机制可注册、有单测"，降指针是后续独立步骤（见「本次退休哪一个既有守卫」）。
- **PreToolUse(Bash) 拦危险命令**——瘦身方案 H3 表格里提到但 `#381`⑸ 原文未列入本批范围，不在本包内。
- **Cowork 侧对应机制**——P0 实测已坐实 hooks 与带 `paths` 的 rules 只在 CC 生效（`根CLAUDE.md彻底瘦身-方案-2026-09-03.md` §五），本包 ⓐⓑⓒⓓ 不承诺 Cowork 侧，正文因此不能全部改写为"已双桌机制化"。
