# open-pool-shared-criteria Proposal

> **状态：判据已由 Shao Peishen 2026-09-02 裁定（队列 §一 `#312`「以看板判据为准 ＝ 35 条」，答 (a)），本包＝该裁定的实现件；design 只剩两处**裁定原文未逐字覆盖、本班按既有裁定推导**的实现细节（D1／D2）待追认。**
> **承载队列行**：§一 `#312`（可 Open 池），**不另立行、不占 WIP**。执行环境：**CC**（`OP-0912-H`，worktree `312-openpool-align`，分支 `claude/op0912h-openpool-align-312`）。
> **openspec 门槛核对**：命中第 ①条「改变全项目口径（判据）」——推送器的入池判据由「只取 `[S:open]`」改为看板判据（`partial` 入池、🛑 起首排除）；第 ③条「改变既有模块对外语义」——推送集合变大（本班实测 48 → 70 条）。⇒ 走 openspec；判据本身已裁定，design 审只覆盖 D1／D2。

## Why

同一个「可 Open 池」概念此前有**两套独立实现**：企微推送器 `5-平台底座/wecom-aibot-service/aibot_service/open_pool_reminder.py`（Python）与看板 artifact `zhuopin-project-status` 的数据层 `0-学习与工具/工具-项目状态卡数据层.ps1`（PowerShell）。两者各持一份判据、无人对账：

- 2026-09-02 Cowork `OP-0902-A` 对两份队列真身实跑：**推送器 25 条 vs 看板 35 条**，差异双向（看板独有 11 条全是 `[S:partial]`；推送器独有 `#439`／`#440` 以 🛑 起首）。
- 2026-09-12 本班再跑：**48 vs 72**，差 ＝ partial 29 行 ＋ 🛑 起首 5 行——**漂移随时间放大**。

裁定（Shao Peishen 2026-09-02）：⑴ `[S:partial]` 入池（尾巴本身就是可开工的活，推送器少报的即「该提醒他的活没提醒」）；⑵ 正文以 🛑 起首者排除（🛑 ＝ 明示的「结构性不可动」）；🔴 **不取「各保留、只加对账告警」**——两套数长期并存正是本项目反复吃亏的「第二份真身」形态；🔴 **对齐不是抄一遍判据，是让两侧共用同一个判定函数，否则今天修完明天照样漂。**

## What Changes

**A. 新增权威判定模块** `5-平台底座/zhuopin_platform/zhuopin_platform/shared_tools/open_pool.py`：`judge_open_pool_row(cells)` 单行判据只写这一处；`compute_open_pool(repo_root)` 遍历两份物理队列文件逐份判定后合并；`snapshot_to_kanban_payload()` 出看板 ps1 消费的 JSON 形状（键名与 ps1 原 `$pool`／`$poolEx`／`$poolDeg` 逐字一致）。

**B. 推送器改 import 权威模块**：`open_pool_reminder.parse_open_pool_rows` 只做组装与非静默告警，本地 `_parse_status_domain_fields`／`_parse_table_rows` 退休；`OpenPoolRow`／`OpenPoolItem` 随行携带 `status`，提醒文案对 partial 行标 `[partial·尾巴待领]`。

**C. 看板数据层改调同一函数**：新增 CLI 薄壳 `0-学习与工具/工具-可Open池.py`（判据不在其中），ps1 经子进程 `--json-b64` 取一行 base64(UTF-8 JSON)（stdout 纯 ASCII，绕开无控制台宿主的 `[Console]::OutputEncoding` 不可控）；ps1 内联判据整段删除，只保留 `op`（opener 出处）扫描与桶／WIP 计数。**fail-loud**：python／脚本不在位、未输出契约行、任一队列文件读取失败 ⇒ `src.pool.ok=false` 且连带 `src.q1.ok=false`（JS 的池卡与徽标只认 `q1`；宁可任务看板一并「无法核验」，也不让池渲染成绿色 0）。

**D. 断言测试锁死两侧逐行相同**：`wecom-aibot-service/tests/test_open_pool_alignment.py` 三层——合成夹具（每判据分支一行）推送器 vs CLI；生产真身推送器 vs CLI；生产真身推送器 vs **真跑 ps1**（缺 pwsh／仓库根即 skip 并说明，不假装验过）。另 `zhuopin_platform/tests/test_open_pool.py` 逐判据分支 24 例。

## Non-Goals

- 不动 `工具-共享文档编辑锁.py::_mechanism_wip_row_counts`（WIP 计数与池判据同源但不是同一件事：计 hold、不看 `[A:`）；两者对 🛑 的认列口径须一致（见 design D1），但收拢为一份留待另一行。
- 不改看板 artifact 的 JS（`index.html` 在仓库外，Cowork 侧载体）；JS 若日后改 `srcBad(d,['q1','pool'])`，ps1 里「连带标 q1」那一句可收窄。
- 不改 opener 出处扫描（ps1 的 `$op` 与推送器的 `find_opener_path` 仍各自一份——那是「opener 在哪」不是「谁可开工」，本包只收拢后者）。
- 不动 `#312` 另一未闭合项「完整 7 天周期轨迹未验」。

## Impact

`shared_tools/open_pool.py`（新）／`工具-可Open池.py`（新）／`open_pool_reminder.py`／`工具-项目状态卡数据层.ps1`／`test_open_pool_reminder.py`（三条期望随裁定改判：partial 入池、缺 `[D:]` 归 degraded）／`test_open_pool.py`（新）／`test_open_pool_alignment.py`（新）。
生产影响：每日 08:30 `ZhuopinDecisionReminderDaily` 下一次运行时，`known_open_ids` 会一次性新增约 22 条 partial 行 ⇒ **推送一条含 ~22 行的「新增」消息**（指纹抑制按行号集合，此后静默）。这是裁定 ⑴ 的直接后果，不是缺陷；如实预告。
