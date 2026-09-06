## ADDED Requirements

### Requirement: append 的 `决策点:` 前置校验
`append` 子命令 SHALL 要求调用方给出本次待登记信件的 `.md` 路径（`--letter-path`，仓库根相对路径或绝对路径），并在**读 README 主表之前**读取该文件的 frontmatter：`决策点:` 字段缺失、取值为空、或取值形态不合判据者 MUST 被拒绝（非零退出码），且 MUST NOT 获取编辑锁、MUST NOT 改动 README 主表。

`--letter-path` MUST 为必填参数，MUST NOT 设计成「给了才查」的可选参数——可省略即可绕过的闸，等于把该字段当初静默消亡的病因（漏写不产生任何信号）原样重造一遍。

取值形态判据 MUST 复用 `工具-跟进信frontmatter校验.py` 的 `parse_frontmatter` 与 `RE_DECISION`（前缀锚定 `^\d+\s*项`），CLI MUST NOT 自持一份独立的 frontmatter 解析器或 `决策点:` 正则，以免两处判据漂移。**只做前缀锚定、不校验括号内容**：全串锚定会把真实合法语料（`IT部#5` 的 `2 项（FO…／PO…），或告知已有的替代查询方式`）判成违规，而一条误杀真实语料的判据第一次跑就会被加豁免绕开。

`0 项`（B 类纯通报信的真实形态）MUST 放行——把「没有需其定夺的点」逼成编一个出来，比字段缺失更坏。

拒绝文案 MUST 给出路：指向 skill `zhuopin-followup-letter` v3.8 §5 步骤 1bis 的写法（`决策点: N 项（a / b / c）`，按 P1 判别式拆点）与 B 类通报信的 `0 项（…无需其决策）` 形态。

本要求 MUST NOT 校验点数是否拆对——拆点是起草侧按 P1（「专员只答这一条、完全不答其他条，这一条能否成立？」）做的专家判断，机器守不了。本要求亦 MUST NOT 改变 `set-status` 的行为，MUST NOT 回溯已登记的历史行。

成功路径 SHALL 在 `[PLAN]` 回显中打印读到的 `决策点:` 取值——只在失败时说话的闸，自身即是下一个「不产生任何信号」的机制。

#### Scenario: 信件缺 `决策点:` 字段时 append 被拒绝
- **WHEN** `--letter-path` 指向的信件 frontmatter 中不存在 `决策点:` 字段
- **THEN** CLI 以非零退出码拒绝、不获取编辑锁、不改动 README，并输出指向 skill v3.8 §5 步骤 1bis 的出路文案

#### Scenario: `决策点:` 取值为空时 append 被拒绝
- **WHEN** `--letter-path` 指向的信件 frontmatter 中 `决策点:` 存在但取值为空白
- **THEN** CLI 以非零退出码拒绝、不获取编辑锁、不改动 README

#### Scenario: `决策点: 0 项（…）` 的通报类信正常登记
- **WHEN** `--letter-path` 指向的信件 frontmatter 为 `决策点: 0 项（结果通报＋请验收，无需其决策）`
- **THEN** CLI 继续后续校验与写入流程，正常完成登记

#### Scenario: `决策点: 3 项（a / b / c）` 正常登记且回显取值
- **WHEN** `--letter-path` 指向的信件 frontmatter 为 `决策点: 3 项（关闭触发 / 关闭权限 / 部分关闭审计）`
- **THEN** CLI 正常完成登记，且计划行回显读到的 `决策点:` 取值

#### Scenario: 括号外带后缀的真实取值不被误杀
- **WHEN** `决策点:` 取值以「数字＋项」开头但括号之后另有自由文本（如 `2 项（FO…／PO…），或告知已有的替代查询方式`）
- **THEN** CLI 放行，不因括号外后缀判违规

#### Scenario: 取值形态不合判据时 append 被拒绝
- **WHEN** `决策点:` 取值不以「数字＋项」开头（如 `唯一 1 项`）
- **THEN** CLI 以非零退出码拒绝、不获取编辑锁、不改动 README，并说明形态要求

#### Scenario: 信件路径读不到时 append 被拒绝
- **WHEN** `--letter-path` 指向的文件不存在或读取失败
- **THEN** CLI 以非零退出码拒绝、不获取编辑锁、不改动 README，并提示该参数应指向本次要登记的那封信的 `.md`

#### Scenario: 信件无 frontmatter 时 append 被拒绝且正文中的同名文字不算数
- **WHEN** `--letter-path` 指向的文件不以 `---` 开头（即便正文中出现「决策点」字样）
- **THEN** CLI 以非零退出码拒绝，不把正文里的文字当作字段取值

#### Scenario: 缺 `--letter-path` 参数时命令行直接报错
- **WHEN** 调用 `append` 时未提供 `--letter-path`
- **THEN** 命令行解析即失败并以非零退出码结束，不进入任何校验或写入流程

#### Scenario: dry-run 同样过闸
- **WHEN** 以 `--dry-run` 调用 `append` 且信件缺 `决策点:`
- **THEN** CLI 以非零退出码拒绝，不因 dry-run 而跳过本校验
