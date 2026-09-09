# editable-pth-blindspot-guard Proposal

> **状态：propose 出件，等 design 审。** 本包**不得** apply，直到 Shao Peishen 完成 design 审。
> **来源**：队列 §一 **#459**（来源 `#410`，2026-09-02 立行的硬条件——他当日答 `#410` (a) 时原话「**盲区必须当场另立队列行，不得只记在包里**」）。
> **openspec 门槛核对**（`.claude/rules/场景建造与合规.md` §二「机制/工具类模块的 openspec 门槛」）：命中 **①「改变全项目口径」**——新增一类巡检判据（`.pth` 纯路径形态），改变的是 `工具-落库sweep.py` 第 6 类常驻告警「editable 安装指向巡检」的判据覆盖范围，全项目共用这一套判据。⇒ **必须走 openspec 且必须含 design 审**（#459 行内原话同此判定）。

## Why

### 缺陷是什么

`工具-落库sweep.py` 第 6 类常驻告警（`_check_editable_install_targets`，队列 `#410`，2026-08-25 立行）巡检 `pip install -e` 在 site-packages 留下的指向，防的是「装的时候指错了、import 却照常成功、测试照常绿」这一类静默漂移（`#406` 实证：藏了至少数周，靠一次人工普查才发现）。

**现行判据只认一种产物形态**：`__editable___<dist>_<ver>_finder.py`（下称 finder 形态）——`pip install -e` 默认产出的、把「包名 → 磁盘目录」字面量写死的 import-hook 模块，判据用 `EDITABLE_FINDER_GLOB = "__editable___*_finder.py"` 扫它。

**setuptools 还有第二种产物形态**：`--config-settings editable_mode=compat`（下称 compat 形态）只产出一份 `__editable__.<dist>-<ver>.pth`，**内容是包目录的一行纯磁盘路径，site-packages 里不会有任何 `*_finder.py`**。现行判据对这种形态**完全不可见**——不是报错、不是判「判据不可用」，而是**照常打出「editable 分发 0 个／模块映射 0 条／指向异常 0 条」**，与「本机压根没有 editable 安装」外观完全相同。这正是本判据自己在文件头注释里反复强调的那句话（`#410` ③）栽在了自己身上：**「没扫到」不等于「没问题」**。

### 现状实测（只读取证，非推断）——这是未来风险，不是现存缺陷

本机当前 site-packages 3 处、editable 分发 9 个，**9 个全是 finder 形态，compat 形态零实例**。这正是 Shao Peishen 2026-09-02 答 `#410` (a) 时「本批不改判据、另立新行」的依据——**不是现在有多严重，是装法一换就会照样发现不了**。

### 🔴 关键发现：这个盲区已经被补过一次，且已经消亡过一次

本包起草前核查了 `#410` 相关分支的完整 git 历史，发现：

- **2026-08-31**，分支 `claude/queue-410-editable-probe` 提交 `330218c`（"feat(sweep): #410 editable 判据补 `.pth` 纯路径形态盲区 ＋ 真实产物真机验活"）**已经完整实现了本包要做的事**：新增 `EDITABLE_PTH_GLOB`、`_parse_editable_pth`（纯分类取值、零执行）、`_editable_pth_key`（切版本号，同 key 纪律）、`_merge_editable_detail`（同 key 合并而非覆盖），并补了「hook 形态 `.pth` 引用的 finder 不存在」判 `判据不可用` 的衍生发现；配 14 条新单测（`test_工具-落库sweep.py`，该组 16 → 30 条全绿，19.64s），含 4 条真跑 `pip install -e --prefix <临时目录>` 的真实产物用例（真机验活：阳性——setuptools 81.0.0/pip 26.1.2 真实产物经 `site.addsitedir` 后判据报「幽灵import」；阴性——同一包装到无 worktree 段路径则 0 告警）。
- **这个分支从未被合入 `master`**。2026-09-02，`#410` 通过另一条不同的执行路径（Cowork `OP-0902-A` 泳道看护首跑批 泳道 C）以**不同的收口口径**（「端到端单测 5 条 ＋ 只读取证」，聚焦的是发送链路从未走通那个问题，**不含 `.pth` 盲区**）销号，并把 compat 形态盲区**明确排除、另立新行**——这条新行就是 `#459`。
- **结果**：`330218c` 里已经写好、测过、真机验活过的代码，因为没有被那条销号路径承接，**连同它一起在分支里躺到了现在，成为「只记在包里就会消亡」的又一个真实样本**——与 `#459` 行内点名的同族病例 `#447`（"判据早已实践过、风险已写下，两次都只落文档没有承接载体，于是都消亡了"）性质完全一致，只是这次消亡的不是文档而是已验活的代码。

**⇒ 本包的 design 决策点 1（见 design.md）就是：以 `330218c` 为蓝本 rebase/cherry-pick，而不是重新实现一遍**——重新实现既浪费已经真机验活过的工作量，也有再引入偏差的风险。

## What Changes

- 新增 `EDITABLE_PTH_GLOB = "__editable__*.pth"`，在 `_check_editable_install_targets` 里与既有 `EDITABLE_FINDER_GLOB` 并列扫描。
- 新增 `_parse_editable_pth(path)`：逐字按 CPython `site.py` 的 `.pth` 语义解析（空行/`#` 开头行忽略；`import ` 开头行只取模块名、不执行；其余非空行是纯路径），**零执行、零导入**——与 finder 那一路「判据不得与被检对象共享失败模式」同一条纪律。
- 新增 `_editable_pth_key(path)`：从 `__editable__.<dist>-<ver>.pth` 切出告警 key，**切掉版本号**（同既有 finder key「不含路径与版本」纪律，防止每次升版本都被判成新问题、旧 key 被误判「已解除」）。
- 新增 `_merge_editable_detail(details, key, detail)`：同 key 合并而非覆盖——finder 那一路的 key 是模块名、`.pth` 那一路的 key 是分发名，两者可能撞（分发名与顶层模块同名是常态），直接赋值会让后写的一条吃掉先写的一条、丢掉一条真异常。
- 补「hook 形态 `.pth`（内容是 `import` 行、无纯路径）引用的 finder 模块文件不存在」的衍生判定，归入既有 `EDITABLE_FORM_UNREADABLE`（判据不可用）——`finder` 被删掉时，若只扫 finder glob 会「零分发、零异常」，与「零风险」外观相同，而 import 早已在报 `ModuleNotFoundError`。
- 回显文案补三个数（`.pth` 直挂条数、其中异常条数、判据不可用项数），解析失败数由原来的减法推算改成显式计数器（`330218c` 已发现原写法 `len(details) - module_anomalies` 在两路径合流后会算错，见 design 决策点 4）。
- **不新增告警类别**：仍挂在既有「第 6 类常驻告警」（`_track_and_alert_standing_state` 同一次调用、同一个状态文件 `reports/sweep-editable-install-state.json`）之下——语义上都是「editable 安装指向异常」这同一件事，只是新增一种扫描形态，不是新一类问题。

## 本次退休哪一个既有守卫（强制，协议〇.9 措施 B）

**不退休任何既有守卫，理由**：one-in-one-out 约束的是「新增一条人守规则时必须退休一条」——本变更**不向根 `CLAUDE.md` 或 `.claude/rules/` 新增任何人守条目**，它做的是对一个**已经机制化**的既有机器判据（`#410` 第 6 类常驻告警）补一种此前未覆盖的扫描形态，判据本身此前已经是机器守、此后仍是机器守，覆盖面变大不改变"谁来守"这件事。不适用 one-in-one-out。

## 伴生文件的 .gitignore 覆盖（强制）

**不适用——本变更不新增任何自动生成的文件名形态。** `.pth` 文件本身是 `pip install -e` 的既有产物（判据只读不写）；状态落盘沿用既有 `reports/sweep-editable-install-state.json`，`git check-ignore -v reports/sweep-editable-install-state.json` 实测命中 `.gitignore:35:**/reports/`，早已被覆盖，本包不改动这条路径。

## Capabilities

### New Capabilities

- `editable-pth-blindspot-guard`：`工具-落库sweep.py` 第 6 类常驻告警对 setuptools `.pth` 纯路径形态（compat 模式）的判据覆盖，与既有 finder 形态判据同挂一个告警通道、同一状态文件、key 空间可合并。

### Modified Capabilities

（无——不改动既有 finder 形态判据的语义，`.pth` 判据是并列新增，互不覆盖。）

## 知识资产三问（强制，全景规划 §1.4 第 2 条）

1. **本流程哪些判断是人脑默会经验？** 两处：① 「`pip install -e` 有不止一种产物形态、装法一换判据就会失明」——此前只在写过 `330218c` 的那次会话与队列 `#459` 行文本里，尚未落进代码本身的判据覆盖面；② 「零告警」与「没装 editable」两种真实状态在 compat 形态下外观完全相同，如何靠上下文（`.pth` 文件是否存在、其内容是路径还是 `import` 行）区分——此前靠人读日志推断，本包把它显性化为 `_parse_editable_pth` 的分类返回值。
2. **由谁显性化？** 持有人 Shao Peishen（design 审拍板：是否以 `330218c` 为蓝本 rebase、`#454` 触碰区串行顺序）；backup ＝ 下一位领取本包 apply 任务的 CC session，可凭本 proposal＋design.md＋`330218c` 的完整 diff（本文件已附引用）独立复核，不依赖上一位的记忆。
3. **用什么方法提取？** 历史真实产物反推（`330218c` 提交信息里的真机验活记录：setuptools 81.0.0/pip 26.1.2 两种形态的真实产出对比）＋ 现网只读实测（本机 9 个 editable 分发全形态普查）。不涉及 LLM 判断。

## 验收与晋档条件（强制，四档口径）

- **本变更包交付后场景所处档位**：本变更为跨项目机制/工具类模块，非独立业务场景，套用最接近的描述 ＝ **档 2（真实数据跑通）**——`330218c` 已完成过一轮真机验活（真跑 `pip install -e --prefix <临时目录>` 产出真实 compat 形态并验证判据能抓到），本包只需在当前 `master` 基线上重新核实该结论仍然成立，不需要从零开始验证。
- **晋下一档（档 3 内部服务，即真正挂在本机每小时常驻轮次里持续生效）的条件**，逐条：
  1. apply 后的 `_check_editable_install_targets` 在本机一次真实常驻轮次里跑过，日志逐项回显 `.pth` 直挂条数（即便当前 0 命中也要显式打出「0 条」，不得省略——同既有第 6 类告警"零告警不省略回显"的纪律，`OP-0819-F` 教训）。
  2. 全量单测绿（既有 `EditableInstallTargetTests` 组 ＋ 本包新增用例），且新增用例里至少保留 `330218c` 原有的两条真实产物用例（真跑 pip，非全 mock）。
  3. 与 `#454`（同触碰 `工具-落库sweep.py`，队列已注明"触碰区重叠、必须串行"）完成一次串行顺序核对，确认 apply 时不与其冲突（哪条先动交值周定，本包不预先假定）。
- **价值指标**（风险型）：compat 形态盲区的可检出性——基线 ＝ 不可见（0 分发/0 异常，与"没装"外观相同）；目标 ＝ 与 finder 形态同等可检出（分发数、异常数、判据不可用数三个数字均显式回显）。本机当前 0 实例，`330218c` 已用真机产物证明判据抓得到，不是恒绿摆设。
- **LLM 判据黄金集**：不适用（纯文件解析与路径分类，无 LLM 运行时判断）。

## Impact

- **受影响代码**：`0-学习与工具/工具-落库sweep.py`（`_check_editable_install_targets` 内新增 `.pth` 扫描分支 ＋ 三个新私有函数 ＋ 文件头 `#410` 说明段补一段"第二种形态"注释，参照 `330218c` 原文）。
- **受影响测试**：`0-学习与工具/test_工具-落库sweep.py`（`EditableInstallTargetTests` 组新增用例，覆盖点清单见 design.md）。
- **受影响文档**：队列 `#459` 行回填（结论、apply 状态）；本包完工后按纪律 `/opsx:archive editable-pth-blindspot-guard -y`。
- **受影响的其它消费者（须在 apply 期核实）**：`330218c` 提交信息记录"全文件另有 2 条失败（sweep 与自己的编辑锁互撞），已在未改动的 master 主工作树同口径复跑复现 ⇒ 预存缺陷、非本次引入" —— apply 期须在当前 `master` 基线上重新确认这两条预存失败是否仍存在、是否仍与本包触碰区无关，不得直接沿用一周前的结论。
- **红线核对**：mock 先行——不适用（判据本身不写业务数据，读的是本机 site-packages 只读文件）；audit 留痕——不适用（本判据不写 `zhuopin_platform.audit`，沿用既有第 6 类告警未接 audit 的现状）；OEM 隔离——不适用；L2 人工确认门禁——不适用；ISO 26262——不适用（非车规安全相关代码，是内部工具链判据）。

## 已知残余风险（如实写明，不粉饰）

1. **仍不覆盖"装对了但代码内容漂了"**——本判据（含 `.pth` 分支）只发现"装的时候指错了"，不做目录内容哈希比对，这是 `#410` ③ 原有边界，本包不扩大也不缩小。
2. **仍是"全机单例、只能挂本机常驻任务"**——`.pth` 分支复用与 finder 分支相同的 `_site_packages_dirs()`，CI 容器里跑永远是绿的，与既有边界一致。
3. **`330218c` 的真机验活结论有一周窗口未复核**——该分支验活于 2026-08-31，本机 setuptools/pip 版本、9 个 editable 分发的现状均可能已漂移，apply 期 tasks 1.x 要求重新做一次现网只读全量核对，不得直接沿用旧结论（同已知残余风险第 4 条：知识资产三问回答里点名的"现网只读实测"必须重新跑一遍，不是复述一遍）。
