# tasks — open-pool-shared-criteria

> 执行环境：**CC**（`OP-0912-H`，worktree `312-openpool-align`，分支 `claude/op0912h-openpool-align-312`）。判据已裁定（2026-09-02，`#312`）；🟡 design D1／D2 待 Shao Peishen 追认，**代码已按推荐项实现、改判只动一处**。

## 1. 实现

- [x] 1.1 新增 `zhuopin_platform/shared_tools/open_pool.py`：`judge_open_pool_row`／`judge_section_one`／`compute_open_pool`／`snapshot_to_kanban_payload`，判据逐条写进 docstring
- [x] 1.2 `open_pool_reminder.py` 改 import 权威模块；本地 `_parse_status_domain_fields`／`_parse_table_rows` 退休；`OpenPoolRow`／`OpenPoolItem` 携带 `status`；文案对 partial 标 `[partial·尾巴待领]`
- [x] 1.3 新增 `0-学习与工具/工具-可Open池.py`（CLI 薄壳：`--json`／`--json-b64`／人读三种输出；文件缺失 exit 2）
- [x] 1.4 `工具-项目状态卡数据层.ps1`：删内联判据，改调 CLI 取 `@@POOL64@@`；fail-loud 连带标 `q1`；`op` 仍由 ps1 扫描器附上；`$qkSkip` 并入 CLI 的 skipped

## 2. 测试

- [x] 2.1 `zhuopin_platform/tests/test_open_pool.py`：判据逐分支 24 例（含 🛑 两列、partial 自陈在办、缺域 degraded、拼接反例、JSON 形状）
- [x] 2.2 `test_open_pool_reminder.py` 三条期望按裁定改判（partial 入池／缺 `[D:]` 归 degraded 并告警／🛑 两列），非放宽
- [x] 2.3 `test_open_pool_alignment.py` 三层对账：合成夹具（含变异验证）／生产真身 vs CLI／生产真身 vs 真跑 ps1（缺 pwsh 或仓库根即 skip 并说明）
- [x] 2.4 回归：服务 `834 passed／2 failed／1 skipped`，2 失败 ＝ `test_ps1_orphan_cr_guard.py` 两例，在纯 master `6b98aa3` 同命令复现（`2 failed, 11 passed`）⇒ 零回归；平台 `619 passed／1 skipped`

## 3. 真实验活

- [x] 3.1 生产队列真身实跑：改前推送器 48 / 看板 ps1 72；改后两侧同为 **70**（差 ＝ 看板原 72 减 `#382`／`#448` 任务列 🛑，即 D1）；`src.q1.ok=true`、`src.pool.ok=true`、`poolEx=0`、`poolDeg=0`
- [x] 3.2 fail-loud 实测：把 ps1 复制到无 `工具-可Open池.py` 的临时目录跑 ⇒ `pool=0`、`q1.ok=false`、`why=脚本不在位：…`
- [ ] 3.3 🟡 design D1／D2 追认（Shao Peishen）——追认前本包不归档；改判即改 `open_pool.py` 一行＋对应单测
- [ ] 3.4 ff 入 master 后，下一次 08:30 定时任务真跑：预期推送一条含 ~22 行 partial 的「新增」消息（裁定 ⑴ 的一次性后果），核 `reports/open_pool_reminder_state.json` 的 `known_open_ids` 由 48 → 70 一致
- [ ] 3.5 Cowork 侧打开看板一次，确认可 Open 池卡 N=70（或当日数）且分组正常——发布态 artifact 读不到源码之外的东西，只能眼看一次

## 4. 收口

- [x] 4.1 `open-pool-assigned-field-and-opener-env-filter` tasks 3.2「两处真跑比对」由本包 2.3 ⑶ 机器承接，已回写
- [x] 4.2 §二 批次 `B-0912_可Open池判据统一312` 已登记（⏳ 待 ff）；分支 `claude/op0912h-openpool-align-312` 已 push（commit `a798c87`，rebase 至 master `735bc74`）
- [x] 4.3 `#312` 已回写（2026-09-12 18:2x 本地，`edit-row`；K2 收窄：2026-09-02 裁定段留在 `队列行日志/#312.md` 末尾，行内首段＋指针＋末段 2,931 B）
- [ ] 4.4 🔴 **暂不归档**——理由＝ 3.3 追认未得 ＋ 3.4/3.5 发布态未验；**预期观察窗口：3 天**
