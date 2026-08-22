## Context

动机见 `proposal.md` §Why，不重述。本节只列**开工前取证查清、且改变了修法的现场事实**——派单件 §OP-0822-C（v2）明写「实现前先确认 `-AppFiles` 里是相对哪个根的路径、多份 sync 脚本如何枚举，这一步没查清之前不要动代码」，以下即该步的结论。

### 一、`-AppFiles` 的语义（正本 = `5-平台底座/deploy-tools/ZhuopinDeploy.psm1`）

- **根 = `-LocalAppDir`**，而 6 份脚本里它恒等于 `$PSScriptRoot` ⇒ **仓库相对路径 = 「sync 脚本自身所在目录」+ 「AppFiles 条目」**。
  ⚠️ **不能认变量名**：SC8 用的是 `$SC8` 而非 `$APP`（`sync-to-server.ps1:12`）。认 `$PSScriptRoot` 这个语义、不认变量拼写。
- **目录条目走 `scp -r` 递归、文件条目精确**（`ZhuopinDeploy.psm1:216-223`）⇒ 匹配语义须按「是目录则前缀匹配、是文件则精确匹配」区分，不能一律 `startswith`。
- **`-AppFiles` 是刻意的白名单**，模块 docstring 自陈「避免带上 reports/（含真实客户名/审计明细）、tests/、.venv」⇒ **它天然已排除 `tests/`、`*.md`、`sync-to-server.ps1` 自身**。这正是它比「按文件后缀猜」强的地方：排除项不必由我们枚举。

### 二、枚举方式（6 份脚本，但只有 5 份有 `-AppFiles`）

| sync 脚本 | 是否走 `Sync-ZhuopinPlatformAndApp` | 备注 |
|---|---|---|
| `5-平台底座/wecom-aibot-service/` | ✅ | **本次唯一在范围内的常驻服务** |
| `4-数字员工/财务部/FI2-三单匹配自动对账/` | ✅ | 另有额外 `scp data/mock` |
| `4-数字员工/质量部/QD-B-立项审核门禁/` | ✅ | 另有额外 `scp data/rules/registry.json` |
| `4-数字员工/采购部/SC2-采购周报自动生成/` | ✅ | |
| `4-数字员工/采购部/SC8-客户订单交期智能承诺/` | ✅ | |
| `1-转型规划/AI运营指挥中心/` | ❌ **无 `-AppFiles`** | 手写四行 `scp`，脚本内自陈「本脚本不走 `Sync-ZhuopinPlatformAndApp`」；页面还是 `框架原型-*.html` 通配取最新 |

⇒ **「读 `-AppFiles`」这条路对第 6 份不成立**，且两份脚本在模块调用之外另有 `scp` ⇒ **`-AppFiles` ≠ 「被部署集合」的全部**。本设计据此把范围收在一个服务上（见 §Decisions D1）。

### 三、🔴 现场取证推翻了「`-AppFiles` 可单独作判据」这一前提

本机 `Get-ScheduledTask` 直读四个 `Zhuopin*` 任务的 Action（只读取证，实测）：

| 任务 | State | Action 真身 |
|---|---|---|
| `ZhuopinAibotDevListener` | Running | `wscript.exe` → worktree `wecom-service-home` 下 `.../wecom-aibot-service/run-hidden.vbs` |
| `ZhuopinDecisionReminderDaily` | Ready | 同 worktree → `run-decision-reminder-hidden.vbs` |
| `ZhuopinFollowupDispatchDaily` | Ready | 同 worktree → `run-followup-dispatch-hidden.vbs` |
| `ZhuopinCommitSweep` | Ready | 主工作区 → `0-学习与工具/run-commit-sweep.ps1`（非本告警对象） |

**两条硬结论**：

1. **告警说的通道与 `-AppFiles` 描述的通道不是同一条。** 告警正文说「同步 `ops/wecom-service-home` 并重启 `ZhuopinAibotDevListener`」——那是**本机 worktree + 本机计划任务**；而 `-AppFiles` 描述的是 **scp 到 `.51`**，且 `wecom-aibot-service/sync-to-server.ps1` 文件头自陈「**本脚本目前不在常规使用**」。
2. **`run-*.vbs` 是计划任务 Action 的真身，却不在 `-AppFiles` 里。** ⇒ 若只读 `-AppFiles`，会把今天的「`.md` 误报」修掉，**同时新造一类「改 `run-*.vbs` 不报」的漏报**——正是派单件自己警告的「只修一面等于换一种不准」。

**顺带查清的边界（决定了范围可以收窄）**：三个 vbs 实际拉起的 `start-aibot-service-dev.ps1` / `run-decision-reminder-check.ps1` / `run-followup-dispatch-check.ps1` **均被 `.gitignore` 忽略、不在版本控制内**（`git check-ignore -v` 实测命中 `.gitignore:51`）⇒ 它们永远不会出现在 sweep 的 `touched_paths` 里，**判据不必也无法覆盖它们**，不是遗漏。

### 四、既有实现现状

`0-学习与工具/工具-落库sweep.py`：`RESIDENT_SERVICE_PATH_PREFIXES`（L484，单元素元组）→ `_touches_resident_service`（L1177-1178，一行 `startswith`）→ `_announce_resident_service_deployment_hint`（L1181-1200，固定文案）→ 调用点 L2723。既有单测在 `test_工具-落库sweep.py:1651` 断言文案含 `ZhuopinAibotDevListener`。

---

## Goals / Non-Goals

**Goals（本设计层面的边界，proposal 已述的范围不重复）**

- 判据的**每一项输入都可指回一处现场事实**（部署清单 / 计划任务 Action / gitignore 实测），不含「按后缀猜」「按目录名猜」这类推断。
- 判据**只有一条实现路径**：退休前缀常量后不留兜底分支，避免「两套判据各自为政」。
- **失败方向固定为多报**：任何解析不确定一律按命中处理并说明原因；漏报被视为比误报更严重的失败（漏报没有任何信号，误报至少会被人看见）。

**Non-Goals**

- **不扩到 6 个部署目标**（＝定夺 1(c) / 2(b)，已否）。本次「常驻服务」仍指**一个**：`wecom-aibot-service` 及其运行时依赖。
- **不合并 #229 部署留痕守卫**（理由见 proposal §退休哪一个守卫）。
- **不引入任何跨轮状态文件**（不做 24h 节流；理由见 proposal §伴生文件）。
- **不改 sweep 的阻断/退出码语义**，不自动同步、不自动重启。
- **不修 ⑴**（`#299` 硬编码，2026-08-21 已修复并销号）。
- **不处理** `wecom-aibot-service/sync-to-server.ps1` 缺 UTF-8 BOM 这一观察（实测无 BOM，与根 CLAUDE.md 坑 5 的部署惯例不一致；但该脚本不走 `.51` 常规部署，属另一件事，**只登记不动手**）。

---

## Decisions

### D1 · 判据范围收在「本机常驻通道」，不扩到 `.51` 六目标

**决定**：运行体集合 = `5-平台底座/wecom-aibot-service/` 的运行体 ∪ `5-平台底座/zhuopin_platform/`（除其 `tests/`）。事实来源只读**一份** sync 脚本（aibot 那份），不遍历 6 份。

**为什么**：告警正文点名的服务只有 `ZhuopinAibotDevListener`（＋同 worktree 的两个 Daily 任务），这就是「常驻」的实际所指。扩到 6 个目标会引出 6 套不同的处置文案与重启任务名，并与 #229 大面积重叠，属另一件事。

**替代方案**：(c) 两条通道都守 —— 工作量约翻倍且与 #229 重叠，**已否**。

**⚠️ 与派单件字面的一处差异，请在本次 design 审一并确认**：派单件 §要点写「改用 `sync-to-server.ps1` 的 `-AppFiles` 显式清单作判据」。本设计**采用该清单，但不把它当唯一真值**——因 §Context 三的取证证明它漏掉 `run-*.vbs`（Action 真身）。这正是定夺 1(a)「`-AppFiles` 只作输入之一」的落法。**若你要的是字面上的「只读 `-AppFiles`」（＝1(b)），本设计需回退，`run-*.vbs`/`register-*.ps1` 两类漏报将作为已知边界登记队列。**

### D2 · 运行体集合的三个来源与合并方式

| 来源 | 取到什么 | 匹配语义 |
|---|---|---|
| ① aibot `sync-to-server.ps1` 的 `-AppFiles` | `pyproject.toml` / `aibot_service` / `scripts` / `deploy-server.ps1` | 目录→前缀、文件→精确（按仓库内该路径实际是不是目录判定） |
| ② 同脚本的 `-LocalPlatformDir` | `5-平台底座/zhuopin_platform` | 前缀，**减去 `tests/`** |
| ③ 计划任务执行入口（取证所得，**声明在 sweep 侧常量里**） | `run-*.vbs`、`register-*.ps1` | glob，限该服务目录一层内 |

**为什么 ③ 要写成 sweep 侧常量而不是继续「读文件」**：它没有任何仓库内文件可读——计划任务的真实设置**不在仓库里**（#199 的核心教训）。写成常量并在注释里写明「本项取自 `Get-ScheduledTask` 直读，复核方式见 tasks 验收项」，比假装它是推导出来的诚实。

**排除项无需枚举**：`CLAUDE.md`/`CHANGELOG.md`/`*.md`/`tests/`/`sync-to-server.ps1` 本就不在①②③任一集合内 ⇒ **靠白名单自然排除，不写黑名单**（黑名单会漏，白名单只会多报）。

### D3 · ③ 内部按处置动作分两类，文案分开

- `run-*.vbs`（Action 真身）→「同步 worktree 后**下次触发即生效**」
- `register-*.ps1`（任务注册定义）→「须**重跑该注册脚本**，仅同步重启不生效」

**为什么**：#199 已实证「改注册脚本源码 ≠ 改了在跑的任务」。对这两类印同一句「同步并重启」，等于给出一个做了也没用的处置——**一条给错处置的告警，比不发更糟**。

### D4 · 解析契约（实现须逐条照做，避免踩已记录在案的坑）

1. **编码**：实测 6 份脚本 **BOM 不一致**（aibot 无 BOM、FI2 有 BOM）⇒ 一律 `encoding="utf-8-sig"` 读取，不得用 `utf-8`。
2. **路径分隔符**：脚本内写作 `5-平台底座\zhuopin_platform`（反斜杠）⇒ 解析后统一转正斜杠再与 `touched_paths` 比对。**实现时该常量必须用 r-string**（`feedback_bash_heredoc_backslash_mangling` 同族：`\z` 不是合法转义、但 `\a`/`\f` 是，静默变控制字符）。
3. **`-AppFiles @(...)` 可跨行**（FI2 那份就在续行符后）⇒ 正则须 `DOTALL` 到匹配的右括号，只取双引号内字面量。
4. **从低取值**：①解析不出条目、或 aibot sync 脚本不存在 ⇒ 该服务目录下**全部路径**视为命中，正文加一句「部署清单未解析出，已保守判定」。

### D5 · 告警正文改为回显命中明细

`_touches_resident_service` 由返回 `bool` 改为返回**命中明细**（路径 + 命中来源 + 对应处置类别），调用点 L2723 与渲染函数随之调整。

**为什么**：现文案是一句写死的话，收件人无法判断它这次说得对不对——**08-22 那次误报之所以要靠人去反查批次内容才发现，正是因为告警自己不说命中了什么**。回显命中项让判据本身可被现场证伪。

### D6 · 不新增变更包，不动 ⑴，不碰 `#229`

`⑴` 已于 2026-08-21 销号（实测 `工具-落库sweep.py` L2098/L2173 注释自陈已改为动态查，现存两处 `#299` 为合法历史注释）。本包只做 ⑶＋⑷。

---

## Risks / Trade-offs

- **[判据依赖 PowerShell 文本解析，脚本改写即可能解析失败]** → D4.4 从低取值（按命中处理并说明），且 tasks 中配「解析失败仍报」的反例单测；失败方向恒为多报，不会静默沉默。
- **[③ 是 sweep 侧常量，计划任务改了 Action 而常量没跟上 ⇒ 重新出现漏报]** → 这是本设计**明知而接受的残余风险**：计划任务设置不在仓库内，没有可读的真身。缓解＝常量处注释写明取证来源与复核方式，并列入月度环境体检（`#98`）的核对项。**不假装它是自动的。**
- **[范围收在一个服务 ⇒ 改 FI2/QD-B/SC2/SC8 代码仍不报]** → 这是 D1 的刻意取舍，不是遗漏：那四个是 `.51` 部署目标、由 #229 留痕守卫覆盖另一面。**须在队列 §四 #87 显式登记「本次未覆盖 `.51` 四目标」**，不让它成为下一次「以为已经覆盖了」。
- **[`deploy-server.ps1` 在 `-AppFiles` 内，但对本机常驻通道其实是惰性的]** → 保留为命中（多报方向），不做特例排除：为一个文件开特例会让白名单重新长出黑名单。
- **[改了对外语义，运维群收到的告警形态会变]** → 迁移计划见下；首次上线后须人工看一眼首条真实告警的正文（不只看单测绿）。

---

## Migration Plan

1. **不需要数据迁移**（无状态文件、无持久化）。
2. **上线即生效**：sweep 每轮现读现算，合入 master 后由 `ZhuopinCommitSweep` 下一轮自动采用。
3. **🔴 但生产载体可能不是 master**：`ZhuopinCommitSweep` 的 Action 指向**主工作区** `0-学习与工具/run-commit-sweep.ps1`（本次取证已确认），故 ff 入 master 即生效；**与 `ZhuopinAibotDevListener` 跑 worktree `wecom-service-home` 那条不同路径**，本次不涉及该 worktree 的同步。
4. **回滚**：`git revert` 单个 commit 即可（纯函数改动、无副作用、无状态残留）。
5. **上线后 7 天观察窗**：口径与晋档条件见 `proposal.md` §验收与晋档条件。

## Open Questions

- **告警首次真实命中的时间点不可预测**（取决于何时真有人改 `aibot_service/` 或底座）。这不影响 specs / approach / tasks，故列为可延后项：若 7 天观察窗内**零真实命中**，按 OP-0819-F 的教训**不得视为通过**，改为构造一次真实改动来验证——具体何时构造，留到观察窗结束时定。
