# editlock-credential-shape-guard Tasks

> 🛑 **design 审未过，本包不得 apply。** 下方 1.x 之后全部为**未执行**，不得预先勾选。
> 执行环境：**CC**（写生产码、跑测试、自行 commit+push，一任务一 worktree）。
> 来源：队列 §一 `#480`（派生自 §四 `#118` ⑶）；本次 propose 由看护批 `B-0906_G` 泳道 `480-credential-guard`（波三）产出。

## 0. 前置闸（design 审后、动手前）

- [ ] 0.1 design 审五个决策点已全部拍板，结论回填 `design.md` 文首结论表 ＋ 队列 §一 `#480` 行
- [ ] 0.2 触碰区核对 —— `git for-each-ref` 遍历本地分支跑 `git log master..<branch> -- 0-学习与工具/工具-共享文档编辑锁.py`，再用三点比对确认无在途分支领先于 master 地改动 `cmd_edit_row`／`cmd_append_row`。🔴 **本轮已知同碰者**：`claude/op0906k-status-triage-454`（同批 A4 泳道）——apply 前须确认它已到终态并合入或明确不冲突
- [ ] 0.3 `pip show zhuopin_platform` 的 `Editable project location` 核实（#98 的静默漂移陷阱）：确认单测取到的 `queue_table` 是本 worktree 的那一份

## 1. 取证与口径（🔴 必须先于实现）

- [x] 1.1 白盒读 `工具-密钥扫描lint.py` 全文，两族判据的边界与 lint 自陈的排除理由已抄录进 `design.md` 决策点①
- [x] 1.2 🔴 **现网全量实测（propose 期已跑）** —— 手段：一次性只读脚本，对 `git -c core.quotepath=false ls-files` 列出的**全部 1465 个已跟踪 `.md`** 各跑两遍判据。结果：**结构化 `CREDENTIAL_PATTERNS` 四条命中 0 处；`GENERIC_ASSIGNMENT_RE` 通用启发式（含 lint 同款占位符/纯大写标识符/长度<8 三重过滤）命中 0 处**。⇒ 决策点① 的两个选项在现网内容上的误伤面**实测均为零**
- [x] 1.3 锁文件的 git 落地性实测（决策点④ 依据）—— 手段：`git check-ignore -v .editlock.json` 与 `git check-ignore -v <队列文件>.editlock.json`，两者均命中 `.gitignore:69:*.editlock*` ⇒ `--note` 内容不进 git
- [x] 1.4 挂载点定位 —— `cmd_edit_row` L2129（`changed_values` 归一之后）、`cmd_append_row` L2306-2307（`_resolve_append_cells` 之后），落点表见 `design.md` 末
- [ ] 1.5 🔴 **apply 期重跑 1.2**，确认结论未漂移（不得直接引用 propose 期数字）
- [ ] 1.6 🔴 **下游消费者核实（重跑，不得引用 `#455` tasks 1.4 的旧结论）** —— grep `工具-队列结构lint.py`／`工具-落库sweep.py`／`工具-队列查询.py` 是否消费 `edit-row`／`append-row` 的返回码或 stdout 格式

## 2. 实现

- [ ] 2.1 `_CREDENTIAL_LINT_SCRIPT` ＋ `_load_credential_lint_module()`，**逐字仿照** `_load_opener_lint_module()` 的动态加载与 fail-loud 惯例；🔴 **不复制任何正则字面量进编辑锁**，判据正本恒在 lint 本体
- [ ] 2.2 `_credential_shape_violations(named_values)` —— 按 design 决策点① 的拍板结论决定取哪一族/哪两族规则；返回文案含**列名 ＋ 规则名 ＋ 按决策点③ 截断的命中前缀**
- [ ] 2.3 `cmd_edit_row` 挂载（L2129 之后）：对 `changed_values` 逐项跑，命中即 `print` ＋ `return 1`，**不修改目标文件**
- [ ] 2.4 `cmd_append_row` 挂载（L2306-2307 之后）：对各内容格逐项跑，同上
- [ ] 2.5 拒绝文案定稿：必含「**凭据请落 `.env`，队列只写指针**」＋ 一个可照抄的替代写法示例；按决策点② 的结论决定是否提供逃生阀
- [ ] 2.6 fail-loud 分支的文案须点名「判据正本文件路径 ＋ 该怎么修」，不得只抛 traceback（proposal 残余风险 3）
- [ ] 2.7 模块文件头新增 `#480` 段：成因（载体属性冲突）、判据来源（复用不重写）、**覆盖边界**（只覆盖走正门的写入，不得写成"队列已不可能进凭据"）、与 lint 回显位数刻意不同的理由
- [ ] 2.8 🔴 **`工具-密钥扫描lint.py` 本体一行不改** —— 实现完成后 `git diff --stat` 实测该文件零改动

## 3. 测试（新增测试类 `CredentialShapeGuardTests`，`0-学习与工具/test_工具-共享文档编辑锁.py`）

- [ ] 3.1 **反例·`edit-row`**：`--set` 一条**形状合规的固定假串**（非任何真实凭据，如 `qyapi.weixin.qq.com/cgi-bin/webhook/send?key=` ＋ 一串固定假 hex）⇒ 返回 1、文案点名规则、**目标文件字节不变**
- [ ] 3.2 **反例·`append-row`**：同一假串放进某个内容格 ⇒ 同上（证明判据装在**两个**入口，不是只装一半）
- [ ] 3.3 **反例·其余三条结构化规则各一条**（AWS／私钥头／`sk-ant-`），各自点名到**正确的那条规则名**（不是笼统"命中凭据"）
- [ ] 3.4 **正例**：正常队列文本（含中文叙述、反引号包路径、`[S:open][D:机]` 状态串、`.env` 指针写法如「见 `.env` 的 `WECOM_WEBHOOK_URL_OPS`」）⇒ 返回 0、正常落盘
- [ ] 3.5 **正例·占位符不误伤**：`XKY_APP_KEY=<value>` 这类叙述写法 ⇒ 放行（钉住 lint 的占位符过滤确实在起作用）
- [ ] 3.6 **拒绝文案含出路**：断言文案里出现「`.env`」与「指针」，不是只有一句"拒绝"
- [ ] 3.7 **回显不泄露**：断言拒绝文案中**不包含**假串的完整值（按决策点③ 的位数上限）
- [ ] 3.8 🔴 **非恒真自证**：把 `_load_credential_lint_module` mock 成返回"零条规则"的桩（＝本包实现前的状态）⇒ 3.1 的同一输入由**拒绝变放行并真的落盘** ⇒ 证明拒绝确实来自本包新增判据，而非别处早已存在的某道检查顺手拦下
- [ ] 3.9 **fail-loud 用例**：判据正本不可加载时 ⇒ 报错退出且文案点名文件路径，**不静默放行**
- [ ] 3.10 `0-学习与工具` 全量回归绿、零漂移

## 4. 现网验证（不落盘）

- [ ] 4.1 用**已实现**的判据对现网两份队列 ＋ 跟进信 README 做只读全量跑，命中集须与 1.2/1.5 一致
- [ ] 4.2 若出现任何非零命中，**先停下报出**，不得自行判定为"可忽略"

## 5. 收口

- [ ] 5.1 队列 §一 `#480` 行回填（走编辑锁协议 `acquire` → `edit-row` → `release`）
- [ ] 5.2 §四 `#118` 行内追加一句「⑶ 的人守面已由机器接管」指针 —— **只追加、不改历史正文**；⚠️ `#118` 属他人触碰区，按「决策路由」不就地改，随 5.1 一并登记待总线派发
- [ ] 5.3 §二 批次登记，触发 sweep，核 `reports/sweep-commit.log`
- [ ] 5.4 `/opsx:archive editlock-credential-shape-guard -y` —— 合入 master 之前不归档
