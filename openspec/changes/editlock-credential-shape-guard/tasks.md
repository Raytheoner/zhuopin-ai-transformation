# editlock-credential-shape-guard Tasks

> ✅ **design 审已过**（Shao Peishen 2026-09-06 于看护批 `B-0906_G` 当场拍板五点，
> 结论表见 `design.md` 文首）。apply ＝ `OP-0906-O`【CC】，分支
> `claude/op0906o-credential-guard-apply-480`（从 master 起，cherry-pick 起草期
> commit `a778c19` 带入本包）。
> 执行环境：**CC**（写生产码、跑测试、自行 commit+push，一任务一 worktree）。
> 来源：队列 §一 `#480`（派生自 §四 `#118` ⑶）；起草由看护批 `B-0906_G` 泳道
> `480-credential-guard`（波三）产出。

## 0. 前置闸（design 审后、动手前）

- [x] 0.1 design 审五个决策点已全部拍板（①=(b) ②=(a) ③=(b) ④=(a) ⑤=(a)），结论已回填
  `design.md` 文首结论表；队列 §一 `#480` 行的回填见 5.1
- [x] 0.2 触碰区核对 —— 手段：只读脚本遍历 `git for-each-ref refs/heads/` 全部 **279 个本地
  分支**，对每个跑 `git log master..<branch> -- 0-学习与工具/工具-共享文档编辑锁.py`。
  **结果：3 个分支有提交（`claude/op0905n-editrow-guard-455`／`claude/queue-315-apply-9f2c1a`／
  `claude/unified-portal-design-8a2ce3`），但三者 `git diff --stat master <branch> -- <该文件>`
  全部是「相对 master 大量删除」（-397／-3505／-4655 行）⇒ 它们都落后于 master，无一领先。**
  🔴 派单件点名的同碰者 `claude/op0906k-status-triage-454`：**已合入 master**（master head
  `e472016` ＝「merge(队列#454/OP-0906-N)」），不在上述三者之列，无冲突
- [x] 0.3 `pip show zhuopin_platform` ⇒ `Editable project location: C:\Dev\zhuopin-ai\5-平台底座\
  zhuopin_platform`（**指向主 checkout，不是本 worktree** —— 这正是 `#98` 的静默漂移形态）。
  ⚠️ **如实写明并给出核实手段**：本包不改 `queue_table`，且实测两份文件 **SHA-256 前 16 位
  同为 `82eb1ab361b4c1ae`**（主 checkout 与本 worktree 逐字节一致）⇒ 单测取到的 `queue_table`
  与本 worktree 那一份等价，本轮无漂移。**不是"因此可以不管"**：改 `queue_table` 的包仍须先
  处理这条

## 1. 取证与口径（🔴 必须先于实现）

- [x] 1.1 白盒读 `工具-密钥扫描lint.py` 全文，两族判据的边界与 lint 自陈的排除理由已抄录进 `design.md` 决策点①
- [x] 1.2 🔴 **现网全量实测（propose 期已跑）** —— 手段：一次性只读脚本，对 `git -c core.quotepath=false ls-files` 列出的**全部 1465 个已跟踪 `.md`** 各跑两遍判据。结果：**结构化 `CREDENTIAL_PATTERNS` 四条命中 0 处；`GENERIC_ASSIGNMENT_RE` 通用启发式（含 lint 同款占位符/纯大写标识符/长度<8 三重过滤）命中 0 处**。⇒ 决策点① 的两个选项在现网内容上的误伤面**实测均为零**
- [x] 1.3 锁文件的 git 落地性实测（决策点④ 依据）—— 手段：`git check-ignore -v .editlock.json` 与 `git check-ignore -v <队列文件>.editlock.json`，两者均命中 `.gitignore:69:*.editlock*` ⇒ `--note` 内容不进 git
- [x] 1.4 挂载点定位 —— `cmd_edit_row` L2129（`changed_values` 归一之后）、`cmd_append_row` L2306-2307（`_resolve_append_cells` 之后），落点表见 `design.md` 末
- [x] 1.5 🔴 **apply 期重跑 1.2**（未引用 propose 期数字）—— 手段：同款一次性只读脚本，
  对 `git -c core.quotepath=false ls-files` 列出的 **1473 个已跟踪 `.md`**（比 propose 期多 8 份，
  期间新增）各跑两遍判据。**结果：结构化四条命中 0，通用启发式命中 0 —— 与 1.2 同结论，
  未漂移。** ⚠️ 边界照旧：只覆盖当前 checkout 的已跟踪 `.md`，不覆盖 git 历史，「今天零命中」
  只支持「今天不误伤」
- [x] 1.6 🔴 **下游消费者核实（本次重跑，未引用 `#455` tasks 1.4 的旧结论）** —— 手段：对三个
  文件逐一 grep `edit-row|append-row|edit_row|append_row|共享文档编辑锁`，再逐个命中点读上下文。
  **结论：三者均不消费 `edit-row`／`append-row` 的返回码或 stdout。**
  ⑴ `工具-队列结构lint.py` —— 只 `importlib` **加载编辑锁模块**取三个常量
  （`QUEUE_MECHANISM_PATH_REL`／`QUEUE_BUSINESS_PATH_REL`／`REPO_ROOT`），**从不调用这两个子命令**；
  ⑵ `工具-落库sweep.py` —— `_edit_lock()` 的全部 4 处调用点实测只传 `status`／`acquire`／`release`
  （L4868／L4986／L5002），`_run_triage_candidates_json()` 只传 `triage-candidates --json`；
  L5847 出现的 `append-row` 只是**打印给人看的建议命令行字符串**，不执行、不读返回码；
  ⑶ `工具-队列查询.py` —— 仅两处**注释**提及编辑锁，无调用。
  另跑一次全仓补充 grep（`--include=*.py/*.ps1/*.sh`，排除测试与编辑锁本体）⇒ 无新增消费者

## 2. 实现

- [x] 2.1 `_CREDENTIAL_LINT_SCRIPT` ＋ `_load_credential_lint_module()`，逐字仿照
  `_load_opener_lint_module()` 的动态加载与 fail-loud 惯例；**零正则字面量进编辑锁**
- [x] 2.2 `_credential_shape_violations(named_values)` —— 按 ①=(b) 取**两族**规则
  （`CREDENTIAL_PATTERNS` ＋ `GENERIC_ASSIGNMENT_RE`，后者复用 lint 的 `_looks_like_real_secret`
  三重过滤）；返回「**列名 ＋ 规则名 ＋ 前 8 字符截断前缀**」三元文案。
  配套 `_named_append_values(section, cells)` 把 `append-row` 的内容格配上列名（有编号列的分区
  跳过列名表首项；格数多于列名时按 `第N格` 兜底，**不静默丢格**）
- [x] 2.3 `cmd_edit_row` 挂载：`changed_values = {**sets, **appends}` **之后**、`--repair` 留痕
  检查之前，命中即 `print` ＋ `return 1`，不修改目标文件
- [x] 2.4 `cmd_append_row` 挂载：`_resolve_append_cells` ／ `_build_append_row_line` 的 try 块
  之后、回读列数校验之前——挂在四种入口归一之后，故 `--cell`／`--set`／`--cells-json`／
  `--stdin-json` 一次覆盖
- [x] 2.5 拒绝文案定稿（`_print_credential_rejection`）：含「**凭据请落 `.env`，队列只写指针**」
  ＋ 可照抄替代写法（`` 见 `.env` 的 `WECOM_WEBHOOK_URL_OPS` ``／`<REDACTED-见§四#118>` ＋ 行号指针）
  ＋ 明写**不提供豁免开关**及其理由（②=(a)）
- [x] 2.6 fail-loud 分支（`_print_credential_lint_unavailable`）点名判据正本**文件路径**、失败原因
  与**修复方向**，不抛裸 traceback
- [x] 2.7 模块文件头新增 `#480` 段：成因（载体属性冲突）／判据来源（复用不重写）／五点拍板
  结论／🔴 **覆盖边界如实措辞**（只覆盖走正门的写入，不写成"队列已不可能进凭据"）／与 lint
  回显位数刻意不同的理由（另在 `CREDENTIAL_HIT_PREFIX_LEN` 处再写一遍，防后人"顺手对齐"）
- [x] 2.8 🔴 **`工具-密钥扫描lint.py` 本体一行不改** —— 实测
  `git diff --stat -- 0-学习与工具/工具-密钥扫描lint.py` **输出为空**；
  `git status --porcelain` 全程只有两个 `M`（编辑锁本体 ＋ 其单测），**零新增文件**
  （proposal §伴生文件 那条"不出现任何新文件名形态"的实跑核实）

## 3. 测试（新增测试类 `CredentialShapeGuardTests`，`0-学习与工具/test_工具-共享文档编辑锁.py`）

> ⚠️ **本类的假凭据一律拼接构造、不写字面量**：lint 的四条结构化规则对**测试文件同样生效**
> （只有通用启发式那一族跳过测试文件），写成字面量会让 CI `凭据扫描` 当场变红。

- [x] 3.1 **反例·`edit-row`**（`test_31_...`）：形状合规的固定假企微 webhook ⇒ 返回 1、文案点名
  规则名与「状态」格、**目标文件字节不变**（`read_bytes()` 前后比对）
- [x] 3.2 **反例·`append-row`**（`test_32_...`）：同一假串放进「任务」格 ⇒ 同上（证明判据装在
  **两个**入口）
- [x] 3.3 **反例·其余三条结构化规则各一条**（`test_33_...`，AWS／私钥头／`sk-ant-`，subTest 逐条）
  各自点名到**正确的那条规则名**；另加 `test_33b_...` 钉住 ①=(b) 的通用启发式那一族——
  **若有人把范围偷改回 (a)，该用例立刻变红**
- [x] 3.4 **正例**（`test_34_...`）：中文叙述 ＋ 反引号包路径 ＋ `[S:done][D:机]` 状态串 ＋
  `` 见 `.env` 的 `WECOM_WEBHOOK_URL_OPS` `` 指针写法 ⇒ 返回 0、正常落盘、仍是合法 8 列
- [x] 3.5 **正例·占位符不误伤**（`test_35_...`）：`` 环境变量 `XKY_APP_KEY=<value>` ``／
  `API_TOKEN = "TODO"`／`_GATE_ENV_VAR = "ZP_GATE_PASSWORD"` 三例 ⇒ 全放行
- [x] 3.6 **拒绝文案含出路**（`test_36_...`）：断言文案含 `.env`、「指针」与可照抄的替代写法
- [x] 3.7 **回显不泄露**（`test_37_...`）：断言文案**不含**假串完整值、不含 key 主体、含「已截断」，
  并钉住 `CREDENTIAL_HIT_PREFIX_LEN == 8`（含"不得为了与 lint 对齐而改"的失败提示）
- [x] 3.8 🔴 **非恒真自证**（`test_38_...`）：把 `_load_credential_lint_module` mock 成返回
  **零条规则**的桩 ⇒ 3.1 的同一输入由**拒绝变放行并真的落盘**（断言落盘后该格确实含
  `qyapi.weixin.qq.com`）⇒ 同时证明拒绝来自本包新增判据、且编辑锁内**不存在第二份复制的判据**
- [x] 3.9 **fail-loud 用例**（`test_39_...`）：加载器抛异常 ⇒ 返回 1、文案含判据正本路径与
  「修复方向」、目标文件字节不变，**不静默放行**
- [x] 3.10 回归绿、零漂移 —— `test_工具-共享文档编辑锁.py` 全量 **406 passed, 19 subtests
  passed**（229 秒，含本类 15 例／11 subtests），即派单件 ⑦ 要求的那一项。
  另跑两道 CI 门禁做旁证：`python 0-学习与工具/工具-队列结构lint.py` ⇒ **exit=0**，
  且回写后的 `#480` 行**零告警**；`python 0-学习与工具/工具-密钥扫描lint.py` 的结果见 4.3。
  ⚠️ **如实标注**：`0-学习与工具` **目录级**全量 pytest 本泳道内未跑完（耗时远超本泳道窗口），
  **未收敛即未声称**——本包只改这一个模块 ＋ 其单测，其余目录内测试与本包无 import 关系
- [x] 3.11（追加）**边界四例**：`test_boundary_04_...`（④ ＝ `acquire --note` 通道**不被拦**，
  实测 note 原样落进 `*.editlock`）／`test_boundary_05_...`（⑤ ＝ 历史行某格已含凭据形状时，
  改**其它列**不被误拒）／`test_boundary_05b_...`（⑤ 的要害 ＝ 把那一格**改写成 `<REDACTED>`**
  必须放行，否则重犯 `#324`／`#454`）／`test_no_credential_regex_literal_is_copied_into_editlock`
  （spec「判据正本唯一」的机器守：拿 lint 本体的 `.pattern` 去编辑锁源码里反查，**一个都不许有**）

## 4. 现网验证（不落盘）

- [x] 4.1 用**已实现**的 `_credential_shape_violations` 对现网两份队列 ＋ 跟进信 README 做只读
  全量跑（按读侧 `split_row_cells` 逐格喂）：机制队列 **1492 格**、业务队列 **652 格**、
  `6-人才与组织/部门AI专员跟进/README-跟进机制与命名约定.md` **441 格**，合计 **2585 格
  ⇒ 命中 0 处**，与 1.2／1.5 一致
- [x] 4.2 无非零命中，本项不触发
- [x] 4.3（追加·如实报出）跑 `python 0-学习与工具/工具-密钥扫描lint.py` 实测 **exit=1，5 处
  疑似**：`工具-未闭合产出扫描.py` 的 `EXPECTED_SERVER_TOKEN`、`工具-落库sweep.py` 的
  `LOCAL_ONLY_DIVERGED_KEY`／`LOCAL_ONLY_AHEAD_KEY`／`LOCAL_ONLY_UNSCANNED_KEY`／
  `CLAUDE_MD_RULES_TOTAL_KEY`。**五处全部是本包未触碰的既有文件**（`git status --porcelain`
  只有编辑锁本体与其单测两个 `M`）⇒ **既有假阳性，非本包引入**，且它们都是"变量名像凭据、
  右值其实是普通字符串常量"的通用启发式误报。🔴 **不在本包范围内处置、也不得顺手改 lint**
  （派单件「不做什么」第一条），另立行报给总线

## 5. 收口

- [x] 5.1 队列 §一 `#480` 行回填 —— 走协议 `acquire`（`--who CC-OP-0906-O-480`）→ `edit-row
  --changes-json` → `release`，全程未 Read／Edit 队列真身。状态转 **`[S:partial][D:机]`**
  （🔴 **未销号**：留步三项见 5.2／5.4 与「ff 进 master」）。
  **K2 行长口径**：外置前状态格 **7778 字节**（近上限两倍），已按 `#454`（`OP-0906-N`）先例
  整体外置至 `1-转型规划/0-全景路线图/队列行日志/#480.md`（原文一字未改，md5 `1a9252e1`；
  同文件另附本次 apply 收工回写全文），行内只留首段＋指针＋末段 ⇒ **7.8 KB → 3.5 KB**，
  行内写明 `行长豁免：`。`release` 全部结构门禁通过（opener 守卫已校验本次触碰的 3 个 `.md`）
- [ ] 5.2 §四 `#118` 行内追加一句「⑶ 的人守面已由机器接管」指针 —— **只追加、不改历史正文**；⚠️ `#118` 属他人触碰区，按「决策路由」不就地改，随 5.1 一并登记待总线派发
- [x] 5.3 §二 批次登记 —— 已 `append-row --section 二` 写入
  `B-0906_O_OP0906O_凭据形状即拒闸apply回写`（文件清单＝机制队列 ＋ `队列行日志/#480.md`，
  状态「待处理」，由 `ZhuopinCommitSweep` 自动取活）。⚠️ **sweep 落库与 `reports/sweep-commit.log`
  核对不由本泳道当场完成**（sweep 是定时任务，本次未触发、也不该由建造泳道手动催）
- [ ] 5.4 `/opsx:archive editlock-credential-shape-guard -y` —— 合入 master 之前不归档
