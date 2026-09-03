# 根 CLAUDE.md 彻底瘦身 — 方案与效果估计（2026-09-03，只读取证，未动任何文件）

> 目标：**开场读入从 ~48.6 KB 降到 ≤10 KB，同时让「会话中途忘规则」这件事不再依赖模型记忆。**
> 原则：不改任何纪律的语义，只改**载体、加载时机、执行方式**。每一条迁出都守 J1（先有承接载体再迁）＋ grep 零残差。

## 一、现状取证（本机沙箱只读实测）

| 项 | 实测值 |
|---|---|
| 根 `CLAUDE.md` | **48,599 B / 22,897 字 / 133 行**（≈ 17–20k tokens，中文按 1 字≈0.8–1 token 估） |
| 子 CLAUDE.md（已分层的部分） | 6-人才 10.5 KB · 5-底座 4.0 KB · 4-数字员工 3.2 KB · 0-全景 1.7 KB —— **这一层做得对，但只承接了 4 个目录** |
| `.claude/rules/` | **目录存在、内容为空** —— 路径作用域规则机制一条都没用上 |
| `.claude/settings.json` hooks | 只有 PostToolUse 两枚哨兵（乱码／代词）。**无 SessionStart、无 PreToolUse、无 Stop、无 UserPromptSubmit** |
| 文本特征 | 日期引用 **96 处**、🔴 **42 处**、加粗段 **390 处**、「⇒ 见 / 详见」指针 26 处 |
| 单条最长 | 「会话末显式罗列决策项」2.06 KB、「每个场景固定流程」2.04 KB、「跨桌任务队列纪律」1.86 KB、「CC 复命零粘贴」1.74 KB、「memory 层两桌不同命」1.69 KB |
| Cowork 侧隐性负担 | 本会话系统提示里挂着 **约 140 条 skill 描述**（legal / sales / small-business / finance / HR / marketing / data / design / customer-support…），保守估 **8–12k tokens／每次 Cowork 开场**，与本项目无关但每次都吃 |

**三句诊断**：
1. 体积不是来自规则数量，而是来自**每条规则都随身带「谁定／何时定／改过几版／成因实证／为什么是硬规则」**。粗估这类 provenance 占 35–45%。
2. 所有规则**不分场景全量常驻**：跟进信、`.51` 部署、全景重排、场景建造、时间戳取证……一个只改 `.md` 的规划 session 也把它们全读一遍。
3. 「中途丢规则」的根因是**靠模型记 48 KB 文本**。已机器守的（J6、进度段 lint、sweep 尺寸告警）从不丢；丢的全是「人守」条目。⇒ 瘦身的核心不是删字，是**把「人守」改成「机制守」，然后文本才有资格降成一行**。

## 二、七类手段（按「省多少 × 风险多低」排序）

### H1 · 去 provenance：每条规则只留「判据一句 + 落点一句」
- 做法：谁定／何时定／改版史／成因实证／「为什么是硬规则」全部搬进 `进度编年-CHANGELOG.md` 对应附录（**这个通道已存在**，附录 A–G 就是干这个的，只是没做完）。正文每条压成固定三段：**触发条件 → 必做动作 → 机器判据／指针**。
- 96 处日期 → 目标 ≤ 10 处（只留仍在倒计时的：外部评审 11 月中旬等）。
- 估计：**−16 ~ −20 KB**。风险最低，语义零变。

### H2 · 路径作用域规则 `.claude/rules/*.md`（按「碰到什么文件才加载」拆）
Claude Code 支持 `.claude/rules/` 下带 `paths:` frontmatter 的规则文件——只在会话触碰匹配路径时注入。拟拆 6 份：

| 规则文件 | `paths` | 从根迁走的条目 |
|---|---|---|
| `跟进信.md` | `6-人才与组织/**` | 专员跟进纪律、串行原则、README 发送状态唯一权威、第 8 步全文、人的属性/禁推断 |
| `场景建造.md` | `4-数字员工/**`, `5-平台底座/**` | 场景固定流程、发布即收口四关、新场景不新起端口、openspec 触发门槛、完工即归档 |
| `队列与落库.md` | `**/跨桌任务队列*.md`, `**/session接力*.md` | 跨桌队列纪律、机制优先、建议未答复重提、环境保障线派单边界 |
| `全景与文档治理.md` | `1-转型规划/0-全景路线图/**` | 排期同步、docx 重转、重组循环、文档治理六规则、接力卡定长 |
| `取证与时间戳.md` | `0-学习与工具/**`, `reports/**` | UTC vs 本地、工具静默回退、乱码哨兵、重启判据指针 |
| `合规红线.md` | `4-数字员工/**`, `5-平台底座/**`, `3-治理与合规/**` | §7 五条 + OEM 隔离 + ASIL 禁区 |

- 根里只留一张**路由表**：「做 X 之前读 Y」（≈ 12 行）。
- 估计：**再 −12 ~ −15 KB**；被迁走的规则在相关 session 里**原样加载**，不相关 session 零成本。
- 🔴 风险：**Cowork 是否加载 `.claude/rules` 未经实测**（本会话能证明 Cowork 读根 CLAUDE.md，不能证明它读 rules）。⇒ P0 先放一枚探针（见 §四）。若 Cowork 不读，退路＝用 CLAUDE.md 的 `@路径` 导入语法把同一份文件按需引用，或让根路由表指向文件、由 session 自己 Read。

### H3 · 用 hooks 把「人守」改「机制守」，文本随之降为一行
| hook | 做什么 | 顶掉哪些文本 |
|---|---|---|
| **SessionStart** | 跑一个 `.ps1`，stdout 注入开场：`Get-Date`（本地＋UTC 双标）、`git fsck --connectivity-only` 结果、`rev-list origin/master..master`、LAN 探针、本线待领队列行摘要、跟进闸状态 | 「时间戳必判 UTC」写侧规则、「开工先 fsck 再 pull」、「开工必读队列」——**变成开场就摆在眼前的事实，不需要记** |
| **UserPromptSubmit** | 每轮追加 ≤300 B 的「常驻五条」（称呼纪律／禁推断性别／需你定夺格式／粘贴端标注／默认项两前提） | 这是对「中途丢规则」最直接的解——**每轮重注 300 B，胜过开场读一次 48 KB** |
| **PreToolUse (Edit\|Write)** | 目标是队列／接力卡 ⇒ 检查编辑锁已 `acquire`，否则 block | 协议〇编辑锁的文字复述 |
| **PreToolUse (Bash)** | 拦 `rd`/`Remove-Item -Recurse`/`git push --force`/`openspec update`（Cowork 侧） | 「Cowork 不改工具链」「状态页只许 Get-Content 级 cmdlet」 |
| **Stop** | 读 transcript 最后一条 assistant 文本，缺「需你定夺」小节或缺 (a)(b) 选项即回退提示 | 「会话末显式罗列决策项」2 KB 的格式四条 |
- 估计：直接省字 **−4 ~ −6 KB**；但真正价值是**丢规则率**——已机器守的条目至今零违反。
- 与「规则退休制」完全同向：违反 3 次即机制化——这次是一次性把候选全机制化。

### H4 · 已有指针的条目，指针替代正文
26 处「⇒ 见 …」后面仍跟着完整正文（例：决策路由、输出规范三条、CC 复命零粘贴），属「既指又抄」。指针成立即删正文。
- 估计：**−3 ~ −4 KB**。

### H5 · 「当前进度」段清零
OP-0819-F／OP-0819-A 两条判据（1.9 KB）已过承接期，按 J1 迁 CHANGELOG（承接载体＝§四 #73 与 CHANGELOG 同节，已具备）。本段只留「最近一批＝空，指针 CHANGELOG」一行。
- 估计：**−2 KB**。

### H6 · Cowork 侧：关掉与本项目无关的插件
legal / sales / small-business / finance / human-resources / marketing / customer-support / data / design / product-management / operations / engineering 十二个套件对本项目零调用，却每次注入 ~140 条描述。保留 zhuopin-*、md-to-word、docx、xlsx、pdf、skill-creator、superpowers。
- 估计：**每次 Cowork 开场 −8 ~ −12k tokens**（与根文件瘦身同量级，且零改文档）。
- 风险：无——插件随时可重启用。

### H7 · memory 层定位不变、补一个「不入 memory」的机械判据
维持 2026-08-29 判决（CC 侧只记技巧；纪律不入）。唯一补充：把「违反会让人做错事 ⇒ 不入 memory」这一句写成 `MEMORY.md` 顶部固定 header，并让 sweep 第 4 类告警顺带扫 memory 目录是否出现队列编号 `#\d{2,3}`（纪律漏进 memory 的指纹）。
- 不省字，防回流。

## 三、效果估计（叠加）

| 阶段 | 根 CLAUDE.md | 每次开场实际读入 | 说明 |
|---|---|---|---|
| 现状 | 48.6 KB | 48.6 KB ＋ 4 个子 CLAUDE.md 按需 | ≈ 18k tokens |
| H1 去 provenance | ~30 KB | 30 KB | 语义零变 |
| H4＋H5 指针化＋进度清零 | ~24 KB | 24 KB | |
| H2 路径规则拆分 | **~9 KB** | 9 KB ＋ 命中的 1–2 份规则（3–6 KB） | 典型 session 12–15 KB |
| H3 hooks 机制化 | **~7 KB** | ≈ 同上，另每轮 +300 B 常驻 | 目标态 |
| H6 插件清理（Cowork） | — | 另省 8–12k tokens | 与上独立叠加 |

**目标态：根 ≤ 8 KB（≈ 3k tokens），典型 session 总开场纪律读入 ≤ 15 KB，比现状省 70%；Cowork 侧再省一个根文件的量。** 「丢规则」指标改为：机器守条目数 从 3（J6／进度段 lint／sweep 尺寸）→ ≥ 9。

## 四、执行顺序（串行，四阶段，每阶段一个 PR、可独立回滚）

**P0 探针（半天，只读＋两个 1 KB 文件）**
1. `.claude/rules/探针.md`（`paths: 6-人才与组织/**`）写一句暗号；分别在 CC 与 Cowork 新开 session 触碰该目录，看暗号是否出现。⇒ 决定 H2 的 Cowork 退路。
2. CC 里跑 `/context` 记录开场 token 基线（真值，不用估）。
3. 试挂一个只打印日期的 SessionStart hook，确认 Cowork 是否执行 hooks（本会话已证明 PostToolUse 在 CC 侧可用）。

**P1 无语义改动（H1＋H4＋H5）**：一个 PR；验收＝ CHANGELOG 附录逐条能对上、`grep` 每个被删的日期/成因句在 CHANGELOG 命中 ≥1。这一步单独就能到 ~24 KB。

**P2 拆规则（H2）**：按 P0 结论走 rules 或 @导入；验收＝ 6 份规则文件字节和 ≈ 迁出量，根路由表 12 行。同批更新 `工具-落库sweep.py::_check_claude_md_carrier_size` 阈值（新上限建议 10 KB，只降不升）＋ 新增「rules 目录总量 ≤ 30 KB」告警。

**P3 机制化（H3）**：五枚 hook 按上表顺序，一枚一个批次，每枚挂上后对应文本才降为一行（先机制、后删字，不倒序）。

**P4 Cowork 插件（H6）＋ memory header（H7）**：他本人在 Cowork 设置里操作，10 分钟。

**不做的事**：不合并两份队列、不动协议〇、不改任何 skill 正文、不动子目录 CLAUDE.md（它们已是目标形态）。

## 五、P0 探针结论（2026-09-03 22:16–22:33 本地，两桌各一 session，取件方式＝CC jsonl 直读 ＋ Cowork `read_transcript`）

| 加载机制 | CC（Claude Code Desktop） | Cowork |
|---|---|---|
| 根 `CLAUDE.md` | ✅ | ✅ |
| `.claude/rules/*.md` **无 paths** | ✅ 开场无条件注入 | ✅ 开场无条件注入（随 claudeMd 块） |
| `.claude/rules/*.md` **带 paths** | ✅ **Read 命中路径的文件那一刻注入**（`PROBE-PATH-6RC` 在读 6-人才 README 后出现） | ❌ 读了同一文件仍不注入（H 会话与本会话各证一次） |
| 子目录 `CLAUDE.md` 自动加载 | ✅ 随首次触碰目录注入（6-人才/CLAUDE.md 全文） | ❌ 不自动加载（本会话 Read 6-人才文件后无注入） |
| `SessionStart` hook | ✅ 执行且 stdout 进上下文（`PROBE-HOOK-Z3M` ＋ 本地/UTC 双标日期） | ❌ 未观察到 |
| `/context` | ❌ 桌面 App 内不可用，开场 token 无法直测 | — |
| skill 描述条数 | — | **155 条**（实数） |

**对方案的三处修正**：
1. **H2 双轨落地**：规则文件仍放 `.claude/rules/` 带 `paths`——CC 自动按路径加载；**Cowork 靠根里的路由表显式 Read 同一份文件**（与今天「动 6-人才前先读 6-人才/CLAUDE.md」是同一机制，实测 Cowork 一直就是这样工作的）。一份文件、两种加载方式，零复制。⚠️ 反过来说：**Cowork 侧任何「按需」都只能靠路由表**，所以路由表不是可选项，是 Cowork 的唯一开关。
2. **H3 hooks 只覆盖 CC**：编辑锁门禁、Stop 检「需你定夺」、UserPromptSubmit 常驻五条——**只在 CC 生效**。Cowork 侧机制化仍只有事后工具（sweep／lint／对账审计），**故「常驻五条」必须留在根文件正文**（≈300 B），不能只靠 hook。
3. **H6 有实数**：155 条 skill 描述，按每条 60–90 tokens 估 **9–14k tokens／每次 Cowork 开场**——与根文件同量级，且本项目真正用到的不到 20 条。

**顺带发现（非本线动作，登记即可）**：`mcp__ccd_session_mgmt__set_session_title` 返回值**不带旧标题**——与 `zhuopin-kickoff-prompt` v1.23 所记「返回值带出旧标题、自带回读校验」不符，该句待更正（一次观测，未复测）。

**效果估计修正**：目标态不变（根 ≤8 KB）；Cowork 典型 session 开场读入 ＝ 根 8 KB ＋ 常驻五条 ＋ 显式 Read 的 1–2 份规则（3–6 KB）≈ 12–15 KB，与原估一致。

## 六、下一步 P1（无语义改动）交付形态
不直接覆盖根 `CLAUDE.md`。产出三件供他过目后再换：① `CLAUDE.md` 新版草稿；② **逐条映射表**（原条目 → 新版落点 → CHANGELOG 附录落点），每行可 grep；③ 尺寸对比。换版那一步走 §二 批次由 sweep 落库。
