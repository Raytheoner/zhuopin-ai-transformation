# tasks · lane-watch-heartbeat-wiring

> 队列 §一 `#565`。**§1–§4 是本轮（`OP-0912-B`，调查＋「调用侧」最小修复，已获派单件明示豁免、不越过 openspec apply 边界）的全部范围；§5 起方案 B 一律 MUST NOT 在 design 审过之前动手。**
> 🔴 档位说明：**起草 ＝ 🟢，调用侧最小修复 ＝ 🟢（派单件明示豁免）＝已随本轮落地，design 审 ＝ 🟡（针对方案 B 与整体裁定），方案 B 落地 ＝ 🟡**。

## 1. 诊断（本轮，🟢，已完成）

- [x] 1.1 读队列 §一 `#565` 全行（`工具-队列查询.py --row 565 --field all`），不 Read/grep 队列真身
- [x] 1.2 心跳命令真实完整形态取证：`工具-泳道看护状态机.py heartbeat --help` 现取 ⇒ `--lane`／`--text`／`--done`／`--batch`／`--json`
- [x] 1.3 子任务泳道 opener 正文是否含心跳指令——取证：现读 `看护件-泳道看护批B-0911_机制收口-2026-09-11.md` §三 全部 5 条 `### A<N>` 代码块正文，逐字比对 `工具-opener生成.py::generate_opener(variant="subtask_lane")` 输出，确认三者一致且**均无心跳提及**；心跳约定仅存在于该看护件 §一「硬边界继承」段与 SKILL.md 步骤 4
- [x] 1.4 心跳工具在 worktree 隔离环境下是否可用——隔离 worktree 内现取 `git rev-parse --git-common-dir` ＝ 主 checkout；调用 `heartbeat --lane test-op0912b-verify-565 --text "..."` 与 `--done --batch <测试批次>`，回显确认写入落在主 checkout；`summary --batch <测试批次>` 现取确认终态计数正确；验证后清理测试心跳文件与状态文件条目
- [x] 1.5 复核 `summary` 时意外发现第二个坑：8 条历史泳道因 `heartbeat --done` 未带 `--batch` 而"批次归属未知"（`419-ops-webhook`／`459-sweep-pth`／`519-scanner-test`／`530-evidence-guard`／`532-bot-domain`／`533-editlock-deadlock`／`535-fixture-date`／`537-anchor-count`）

## 2. propose ＋ design 起草（本轮，🟢，已完成）

- [x] 2.1 `proposal.md`（含两条 MANDATORY 节、退休问答、`.gitignore` 覆盖问答）
- [x] 2.2 `design.md`（决策点 1–4 已落地取值 ＋ 决策点 5 方案 B 只设计不落地 ＋ Non-Goals ＋ 与既有变更包关系）
- [x] 2.3 `specs/lane-watch-heartbeat-wiring/spec.md`（ADDED，5 个 Scenario）
- [x] 2.4 `openspec validate --strict` 本包自身

## 3. 「调用侧」最小修复（本轮，🟢，派单件明示豁免——已落地，非待审后才做）

- [x] 3.1 `0-学习与工具/工具-opener生成.py`：新增 `SUBTASK_HEARTBEAT_NOTE` 常量（含 `--lane`／`--text`／`--done --batch <批次>`／`--repo-root`／`--heartbeat-file` 不存在提醒／长等待补写规则）
- [x] 3.2 `subtask_lane` 分支强制注入列表由三条扩为四条：`[PARALLEL, HEARTBEAT, PUSH, SENTINEL]`
- [x] 3.3 `1-转型规划/0-全景路线图/opener骨架.md`【CC · 子任务泳道】骨架节：三条改四条，心跳段落"有意扩入"说明，示例代码块同步
- [x] 3.4 `0-学习与工具/工具-opener块lint.py`：新增形态⑩（`HEARTBEAT_LINE_RE`、`check_block` 分支、`RULE_EFFECTIVE_FORM10`、`FORM_TITLE["F10"]`、模块 docstring 表格行、九→十形态计数更新）
- [x] 3.5 单测：
  - [x] 3.5.1 `test_工具-opener生成.py`：`子任务泳道占位段::test_未传时正文恰为三行加四条机器口径`（原三条测试改名并更新断言）
  - [x] 3.5.2 `test_工具-opener生成.py`：`骨架与生成器契约::test_四条机器口径逐字取自正本`（原三条测试改名）＋ 新增 `test_正本写明心跳行是有意扩入`
  - [x] 3.5.3 `test_工具-opener生成.py`：`收工哨兵强制注入::test_传了do_dont仍在最末` 更新为四行断言
  - [x] 3.5.4 `test_工具-opener生成.py`：新增 `心跳强制注入` 类（5 个用例：含行、含 `--batch`、排序、其它变体不注入、变异检验）
  - [x] 3.5.5 `test_工具-opener块lint.py`：既有涉 `SENTINEL_LINE` 的"干净样本"共享夹具补 `HEARTBEAT_LINE`（`_WATCHER_FILE_CLEAN`／`_LANE_THREE_LINE`／`_LANE_WITH_SENTINEL`）
  - [x] 3.5.6 `test_工具-opener块lint.py`：新增 `形态十_子任务泳道块缺心跳约定` 类（7 个用例，镜像既有形态九类）
  - [x] 3.5.7 全量回归：`test_工具-opener块lint.py`（220 例含 subtests）＋ `test_工具-opener生成.py`＋ `test_工具-opener批处理执行v2.py` 零回归
- [x] 3.6 `0-学习与工具/skills源码/zhuopin-lane-watch/SKILL.md`：
  - [x] 3.6.1 步骤 4 示例命令补 `--batch <批次>` ＋ 一句"不能漏"提醒
  - [x] 3.6.2 「已知缺陷与其状态」新增缺陷四（成因、已修状态、指向本变更包、注明方案 B 未落地）
  - [x] 3.6.3 版本历史追加 v2.3 条目
- [x] 3.7 🔴 未改动确认：`工具-opener批处理执行v2.ps1`（只读引用，零改动）；`工具-泳道看护状态机.py`（零改动）；历史看护件（零改动，历史记录不追改）

## 4. 收口（本轮，🟢 部分／🟡 部分）

- [ ] 4.1 🟡 合入 master —— 本泳道 MUST NOT 自行合入，只 push 本泳道分支
- [x] 4.2 队列 §一 `#565` 状态回写（走编辑锁 `acquire`／`edit-row`／`release`）
- [ ] 4.3 §二 批次登记（新批次名，避开 `B-0911_W` 撞号）

## 5. apply · 方案 B（design 审过后，🟡，本轮不做）

- [ ] 5.1 🔴 **design 审 —— 待 Shao Peishen 裁定**是否值得推进方案 B 的可行性核实
- [ ] 5.2 若推进：核实子任务收工报告是否落在看护状态机可读的文件里（决策点 5 待厘清前提①）
- [ ] 5.3 若前提成立：设计并实现读取入口（决策点 5 待厘清前提②），新增单测，`summary` 现取报出
- [ ] 5.4 若前提不成立：如实登记「方案 B 在当前架构下不可行」，关闭该分支，不强行绕过
