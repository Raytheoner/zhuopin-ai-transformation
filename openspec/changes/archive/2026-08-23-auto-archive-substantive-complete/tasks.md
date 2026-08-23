## 1. 判定内核（已完成于 commit 8323852）

- [x] 1.1 新建 `0-学习与工具/工具-变更包自动归档.py`：四态判据 `classify_tasks()` ＋ `is_archive_action_line()`
- [x] 1.2 形态判别 `carries_human_note()`：剥复选框/编号/反引号代码段/命令词后按实词字符数判定；另认缩进子项
- [x] 1.3 `scan_changes()` 扫 `openspec/changes/*/tasks.md`，跳过 `archive/`，空目录判 `no-tasks` 并记名
- [x] 1.4 `assert_main_workspace()` 复用 sweep 的 `MAIN_WORKSPACE` 与 `_assert_not_a_linked_worktree`，转 `RefuseToRun`
- [x] 1.5 `--dry-run` 清单渲染，逐条回显未勾项原文
- [x] 1.6 单测 18 passed ＋ 12 subtests，三条生产真身反例逐条钉死

## 2. 文件头与命名的诚实性（范围定为 (b) 后必做）

- [x] 2.1 改写 `工具-变更包自动归档.py` 文件头：删去「等定夺 4」「执行路径尚未实现」等过渡措辞，明写**本工具不执行归档、只做判定**
- [x] 2.2 `main()` 去掉「非 --dry-run 即报错退出 2」的过渡分支，改为默认即判定输出（不再有「另一半功能待建」的暗示）
- [x] 2.3 文件名保留不改，但在文件头显式说明为何不改名（已被 commit／队列行／派单件引用，改名即让指针失效）

## 3. sweep 告警分三类措辞

- [x] 3.1 `_announce_stale_in_flight_changes` 引入判定器，对每个 escalate 项取四态与 `unchecked_carry_notes`
- [x] 3.2 第 1 类（实质完工 ＋ 无人留话）⇒ 措辞「只差归档这一步」，按原路径升级推送
- [x] 3.3 第 2 类（实质完工 ＋ 有人留话）⇒ 措辞「作者已写明理由，但未用机器认得的入口」，**正文列出三条入口**
- [x] 3.4 第 3 类（尚有真未完项）⇒ 措辞「已 X 天无改动，尚有 N 条真未完项」，**不含「遗忘归档」字样**
- [x] 3.5 三类均逐条回显包名、判定结论与判定理由（判据须可现场证伪）
- [x] 3.6 `observing`（观察窗口内）分支逻辑不动
- [x] 3.7 判定器导入失败时**从低取值**：退回现有单一措辞并在日志记明原因，不静默、不中断 sweep

## 4. 单测

- [x] 4.1 三类措辞各一条断言，用 2026-08-23 那 4 个被报的包做端到端夹具
- [x] 4.2 断言旧措辞「疑似遗忘归档」对那 4 个包**全部不成立**（复现 4 报 3 误已消除）
- [x] 4.3 断言第 2 类告警正文含 `暂不归档`／`预期观察窗口`／`--ack-stale-change` 三个字样
- [x] 4.4 断言判定器导入失败时 sweep 不中断且日志有记
- [x] 4.5 sweep 既有单测零回归

## 5. 收工纪律落点（队列 §四 #87 ⑶）

- [x] 5.1 `1-转型规划/0-全景路线图/专线opener模板库.md` §〇 收工段写入三条降噪入口及各自适用场景
- [x] 5.2 根 `CLAUDE.md` §5 加**一行指针**（🔴 该文件今日已由 71.7K 瘦到 56.0K，**不得展开**）
- [x] 5.3 不改 tasks 写法约定（派单件 §四 撤销，理由已写进 design ④）

## 8. 🔴 §3.1ter 自洽性补丁（Shao Peishen 2026-08-23 追问后补，优先级等同 §3.3bis）

- [x] 8.1 `is_substantively_complete()`：两条任一命中 —— ⑴ 未勾数＝0（N/N）⑵ 未勾项 ≥1 且全为 archive 动作
- [x] 8.2 `alert_class()` 把 `COMPLETE`（N/N）映射到 `ALERT_FORGOTTEN`，措辞「只差归档这一步（N/N，除归档外无事可做）」
- [x] 8.3 `NO_TASKS` 从 incomplete 分支拆出为独立类 `ALERT_UNJUDGEABLE`——它此前同样会印「尚有 0 条真未完项」
- [x] 8.4 `--dry-run` 渲染把 N/N 归入「实质完工」组并置顶，不再叫「已无欠账」
- [x] 8.5 §3.1ter 要求的三条单测各一：`N/N 判实质完工`（本次新增）／`未勾项全为 archive 判实质完工`／`含一条非 archive 不判中`
- [x] 8.6 补告警侧对照单测：N/N 包端到端走「只差归档这一步」，断言不含「尚有 0 条」「它没完工」
- [x] 8.7 spec 增 Requirement「实质完工须同时覆盖 N/N 与未勾项全为 archive 两条」＋3 条 Scenario
- [x] 8.8 design 增 ③bis，并写明它与 ④（治本撤销）的耦合已解开

## 6. 验收与回归

- [x] 6.1 对生产真身跑 `--dry-run`，核对三个包判为实质完工＋有人留话、`queue-status-machine-field` 与 `open-pool` 判为未完工、`sc2-weekly-report-mvp` 判为 no-tasks 且在清单内
- [x] 6.2 `0-学习与工具` 全量回归绿（**652 passed ＋ 51 subtests，零失败**；§3.1ter 修复前为 646，+6 即新增单测）
- [x] 6.3 `openspec validate --all --strict`：101 passed / 1 failed，唯一失败是 master 既有的 `sc2-weekly-report-mvp` —— 零新增
- [x] 6.4 ff 合入 master 并 push

## 7. 收工回写

- [x] 7.1 队列 §四 `#87` 追记：**「判据死锁」这个发现本身被实测推翻的经过**（比脚本更值得留），以及 ⑶ 已落地
- [x] 7.2 派单件 `status:` 改 `已执行归档`；§二 批次登记
- [x] 7.3 `/opsx:archive auto-archive-substantive-complete -y`
