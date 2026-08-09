# Design: queue-table-shared-parser-consolidation

> **本设计不重开审议**——范围缩窄（P2→P3，仅剩②转义与④列数校验）已由 Shao Peishen 2026-08-08 拍板措施 A 定案，相关决策记录在 `openspec/changes/queue-status-machine-field/design.md` 决策点 4（"#306 原定的独立 design 审——决策点 4 已把其缩窄为『读一份定长字段＋队列文件路径解析收拢』，并入本 design 一次性定案"）。本文档记录**如何落地**，供后续 session 追溯。

## 决策点 1：模块承载哪两件事，不承载什么

**已定案**：只承载 `SECTION_COLUMN_COUNTS`（列数常量）与转义/裸竖线检测（`has_bare_pipe`/`escape_bare_pipe`）/`column_count_ok`。**不承载**表格切分（`_split_live_sections`/`_table_data_rows` 等价物）或开头片段提取（`_leading_status_segment` 等价物）——这两件事本可随 #308 状态机器字段落地而大部分作废，各消费者继续按需本地实现极简的展示层逻辑（如状态列索引），不属于本次权威化范围。

## 决策点 2："队列文件路径解析收拢"是否一并做

**已定案：不做，如实登记留给 #306 自身后续范围**。`queue-status-machine-field` design.md 决策点 4 的标题虽然把"队列文件路径解析收拢"与"七处消费者切换顺序"并列讨论（因为发现这是消费者切换的一个隐藏前置），但其 tasks.md 4.3 明确写明"队列文件路径解析收拢……未做，留 #306 自身后续范围"——即该项从未在 #308 的 apply 阶段被交付，只是被"发现并记录"。

本变更的授权范围来自 2026-08-09 环境总线派单件（`派单件-环境侧F1F2-2026-08-09.md`），其原文对 #306 的范围复述为"仅剩②转义与④列数校验两件"，**未提及路径解析收拢**——与该派单件写作时刻 #306 行文本身的措辞一致（该行文本身也未提及路径解析收拢这一项，可能是 08-08 拍板与 08-09 决策点4 补充记录之间的时间差所致，见根 CLAUDE.md §5"前提变更后依赖它的载体无人复检"同类形态）。**处置**：不在本变更内静默扩大范围，如实在本变更完工回写与队列 #306 行内注明"路径解析收拢（5 处 Python 各自硬编码 `_resolve_repo_root`/`DEFAULT_TARGET` 等价物）未做，如需处理另评估"，留给后续 session 或另立行处理，不因本次顺手做了另外两件事就默认这件也该顺手做——路径解析收拢涉及修改全部五处消费者的仓库根解析逻辑，风险与范围都比"新增一个纯函数模块+替换几个整数常量"大得多，不适合在未经明确授权时顺带扩大。

## 决策点 3：consumer 切换的技术手法——sys.path 引导 vs 直接 import

**已定案**：`0-学习与工具/*.py` 系列脚本（非包，文件名含中文/连字符）采用"检测本地 `5-平台底座/zhuopin_platform` 目录是否存在→存在则插入 sys.path 并 import→不存在则本地兜底桩"的引导模式，与队列 #300 conftest.py 的 worktree 隔离引导同一原则（import 结果与全局 editable 安装当前指向谁无关）。`wecom-aibot-service/aibot_service/*.py`（已是标准 Python 包 `aibot_service`）沿用其既有惯例——直接 `from zhuopin_platform... import ...`，不新增引导代码（该文件既有的 `from zhuopin_platform.audit import AuditEvent` 已是此惯例，本变更只是多加一行同风格 import）。

**兜底桩的必要性（apply 阶段实测发现）**：`test_工具-共享文档编辑锁.py::EditLockCrossWorktreeTests` 把脚本文本单独复制到不含 `zhuopin_platform` 包的隔离临时目录子进程运行（测试 `_resolve_repo_root()` 的跨 worktree 行为，与本变更无关）。若 import 语句无条件执行且目标目录不存在，Python 会转而在全局 `sys.path`（可能残留其它 worktree的 stale editable install，见 #300 已知风险）里找到一个不含 `queue_table` 的旧版 `zhuopin_platform.shared_tools`，报 `ImportError`——这正是 apply 阶段两个测试失败的真实根因。修法：仅当本地目录确认存在时才 `sys.path.insert`+import；目录缺失时用一个内容与 `queue_table` 模块完全一致的本地类兜底，不改变脚本在隔离环境下的可运行性；若目录存在但 import 本身失败（真实错误，如包损坏），仍如实抛出，不静默吞掉。

## 决策点 4：两种"竖线不能直接进单元格"的处理惯例是否统一

**已定案：不统一，如实并存记录**。`escape_bare_pipe`（本模块，#164 口径：事后转义为全角 `／`）与既有 `append-row`/`_cell_has_bare_pipe`（#258 口径：写入时直接拒绝，提示改用全角 `｜`）服务不同场景——前者面向"批量修复已落库的历史正文"，后者面向"新写入路径的即时拒绝"。统一为一种会削弱 `append-row` 刻意设计的"拒绝而非静默改写"语义（design.md `editlock-section-append-and-followup-consistency-guard` 已有完整论证），本变更不重新挑战该决策，只是如实记录两种惯例并存的事实，供后续消费者选用正确的一种。

## Non-Goals

- 不重建"权威表格解析器"（原 #306 大工程），不承载列语义/开头片段提取。
- 不做队列文件路径解析收拢（决策点 2）。
- 不改变 Cowork artifact `zhuopin-project-status`（JS，不可消除的第二实现，接受并登记）。
