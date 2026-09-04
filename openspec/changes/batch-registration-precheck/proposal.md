# batch-registration-precheck Proposal

> **状态：propose 出件，实现与单测已随本包同批完成（补件式 propose）。**
> **来源**：队列 §一 **#381** 子项 ⑸ⓘ（B1，2026-09-04 追加，Shao Peishen 答「都按建议推进」）；设计与判据正本＝`1-转型规划/0-全景路线图/构建环境瘦身第二轮-方案-2026-09-04.md` §一 B1。建造 opener＝`OP-0904-G`。
> **openspec 门槛核对**（`.claude/rules/场景建造与合规.md` §二）：命中 ①「改变全项目口径」——§二 批次登记的文件清单格式从人守变机器守（方案原文「口径变更」）；命中 ③「改变既有模块对外语义」——`append-row --section 二`／`edit-row` 在同一输入下由放行变为拒绝，`_reconcile_with_origin_and_push` 新增 autostash 行为。⇒ **必须走 openspec。**
> **与 `editlock-write-side-date-guard` 的差异（如实说明）**：该包的六个决策点在 propose 期尚待 Shao Peishen 拍板；**本包的设计已在方案 B1 里由他一次性拍板批准**（「都按建议推进」），故本 propose 是**补件式**——记录已落地的实现与判据，供归档与未来复核，不再等待逐点 design 审。

## Why

sweep（`ZhuopinCommitSweep`）每轮约有 13 个 §二 批次被跳过：登记方在"文件清单"里写非路径文本（自然语言描述）、偷懒速记（"同名 docx"／"同上"）、或路径写错，sweep 校验不过就静默跳过，登记方长期零反馈。2026-09-04 当天，编辑锁 acquire/release 自身对两份队列文件的改动未被任何批次清单覆盖，叠加主仓与 origin 分叉（需人工 `git stash --autostash` 补救），构成一次真实事故。方案 B1 判定：**批次清单格式必须从人守升级为机器守**，且落库流程要堵住"队列文件自身改动裸露在批次之外"的窗口。

## What Changes

### ⓘ1 · §二 批次登记文件清单预检（`工具-共享文档编辑锁.py`）
`append-row --section 二` 与 `edit-row`（针对 §二 行）写入前，对"文件清单"字段里每一个反引号 `` `...` `` 串做双重校验：
1. **形态校验**（复用既有 `_file_list_path_violations` 的路径/通配符/目录前缀/CLI 参数豁免口径，不重造）＋ 新增对「同上」「同名」类速记的关键字级拒绝；
2. **git 归属校验**（新函数 `_file_list_git_state_violations`）：该路径须在**主仓**（复用 acquire/release 已有的仓库根定位逻辑，不新造）的 git 脏集 ∨ 未跟踪新文件 ∨ 最近 3 个 commit 内被触碰，三者之一。
任一项不过 ⇒ 拒绝整次写入（fail-loud，打印具体是哪个反引号串、因何原因不合格）；git 状态完全不可得时（非 git 目录、git 调用失败）形态/速记校验仍生效，只豁免 git 归属这一半（fail-open 仅限该子项）。

### ⓘ2 · 队列文件改动即刻落库（`工具-落库sweep.py`）
`main()` 处理 §二 批次前，先检查两份队列文件中是否存在"当前无任何待处理 §二 行"却仍脏的文件——即编辑锁 acquire/release 等锁流程自身写入、且不会被后续任何批次覆盖的改动。若存在，先单独 commit（固定 message `docs(队列): 锁流程自带改动即刻落库`），再继续处理批次。

**判据取舍（与最初字面方案的偏差，需如实记录）**：方案原文写"未被任何待取活批次覆盖"，字面实现（按批次清单路径匹配）在回归测试中暴露问题——一个仍在途、因自身歧义而暂缓（blocked）的批次，其对应队列行不应被当作"已覆盖"从而被提前 commit 冲掉暂缓状态。改为按**物理队列文件当前是否还有任何待处理 §二 行**判断"是否可即刻落库"，语义更贴近"这份文件此刻没有等待中的批次在盯着它"。

### ⓘ3 · `_reconcile_with_origin_and_push` autostash（`工具-落库sweep.py`）
仅当需要 rebase（`behind > 0`）时启动：把当前脏文件分两组——**批次清单内**（即将被 commit 的对象，不 stash，只发告警）／**批次清单外**（`git stash push -u -m ... -- <files>` 按路径 stash）；rebase／ff-only 完成或 push 成功后 pop 回来；pop 冲突时保留 stash 现场、`abort` 当次 reconcile 并沿既有告警通道报错，不静默吞掉。

### ⓘ4 · 日志周轮转（`工具-落库sweep.py`）
`reports/sweep-commit.log` 按"一轮 sweep 运行"块（`=== sweep 运行 ... ===` 边界）轮转、`reports/hooks-audit.jsonl` 按其 `ts` 字段逐行轮转，均保留最近 4 周；解析不出的块/行一律保守保留、不猜测丢弃。

## 存量与不做的事

**存量 13 个被跳过批次**（B-0902_47/48/49/62/64、B-0903_12/13/21/33/51/80/82/99、B-0904_H）由业务总线自行订正清单格式，本包不代改。本包不改任何存量批次行的内容，不改队列文件正文（除 sweep 运行时按 ⓘ2 产生的自动 commit）。

## Capabilities

### New Capabilities
- `batch-registration-precheck`：§二 批次登记文件清单的机器校验（形态＋git 归属）；sweep 落库流程的队列文件即刻兜底 commit、reconcile 阶段的按清单归属 autostash、日志周轮转。

### Modified Capabilities
（无——`_file_list_path_violations`、`_reconcile_with_origin_and_push` 的既有校验语义保留，本包是叠加，不改变既有校验①～⑩ 或既有 git 状态判断的既有通过路径。）

## Impact

- **受影响代码**：`0-学习与工具/工具-共享文档编辑锁.py`（`cmd_append_row`／`cmd_edit_row` §二 分支）；`0-学习与工具/工具-落库sweep.py`（`main()`、`_reconcile_with_origin_and_push`）。
- **受影响测试**：`0-学习与工具/test_工具-共享文档编辑锁.py` 新增 `FileListGitStateViolationTests`（20 例，白盒）；`0-学习与工具/test_工具-落库sweep.py` 新增 `ImmediateQueueChangeCommitTests`／`ReconcileAutostashTests`／`LogRotationTests`（合计 15 例）。两份测试文件全量回归绿（前者 340 passed/8 subtests；后者 382 passed/51 subtests）。
- **受影响文档**：队列 §一 #381 子项 ⑸ⓘ 回填；§二 登记本批次；不改根 `CLAUDE.md`／`.claude/rules/`（本包不构成"降指针"前置条件——降指针须等机制在生产真实验活一次，见「已知残余风险」）。
- **红线核对**：mock 先行——不适用（纯 git/文件操作，无外部数据）；audit 留痕——不适用（编辑锁与 sweep 均不写 `zhuopin_platform.audit`）；OEM 隔离——不适用；L2 门禁——不适用；ISO 26262——不适用。

## 已知残余风险（如实写明）

1. **ⓘ1 的 git 归属校验只覆盖主仓**：若登记方在其它 worktree 里改动了文件、尚未同步回主仓，会被误判为"不在脏集/未跟踪/最近 3 commit 内"而拒绝——这是刻意取舍（批次清单描述的本就是"主仓视角下这批要 commit 什么"），但需要登记方知晓。
2. **ⓘ2 的"零待处理行"判据不是"未被批次覆盖"的严格子集**：一份队列文件可能同时有一个已在处理中、即将被 commit 的批次（清单外的改动理应保留）和另一处锁流程自身写入的改动；当前实现按"文件当前无待处理行"这一整体判据放行，暂未实现"同一文件内分段判断"。如后续观察到误伤，需回来收紧。
3. **本包未走"先机制在生产真实验活、后降指针"的降指针环节**（不适用——本包不承诺任何降指针，B1 方案本身也未要求）。
