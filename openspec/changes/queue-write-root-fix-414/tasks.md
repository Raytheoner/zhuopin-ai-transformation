## 1. Design 审核（阻塞后续所有任务）

- [x] 1.1 五个决策点均记录在 design.md，其中决策点 2（字样判据否决）与决策点 3（更正派单件 A3 的"13 列"判断）为**实测推翻纸面方案**，非纸面推演
- [x] 1.2 授权来源：Shao Peishen 2026-08-26 答「a」（#414 与 #416 合派），派单件 OP-0826-N A 组

## 2. 修复面 A · 正文不进 argv

- [x] 2.1 `工具-共享文档编辑锁.py`：`append-row` 新增 `--cells-json <文件>` 与 `--stdin-json`；新增 `_load_cells_json`／`_resolve_append_cells`，JSON 顶层支持数组（按列序）与对象（列名→值）
- [x] 2.2 四类入口（`--cell`／`--set`／`--cells-json`／`--stdin-json`）四选一，多给 fail-loud，不做静默取舍

## 3. 修复面 B · 守卫覆盖所有入口

- [x] 3.1 `queue_table.py`：新增 `validate_row_cells(section, cells, *, source="write"|"parsed")`，收拢为全写盘路径共用的单一校验函数
- [x] 3.2 新增关键格哨兵：编号格非纯数字（行头断裂）／§一 状态格不以 `[S:` 开头／`✅` 落进期望产出格（#412 形态）／格内含换行
- [x] 3.3 🔴 **字样判据（`Is a directory`／`command not found` 等）实测否决、刻意不实现**——照 #414 行内建议 ⑶ 实现后对生产队列 5 行全部误报，成因与判据写成长注释留在代码里，防止后人照字面重做（见 design.md 决策点 2）
- [x] 3.4 `_build_append_row_line` 与 `cmd_edit_row` 写盘前一律调用该函数；既有 arity／裸竖线诊断文案（#351 打磨过）保留不动，新校验只补它们看不见的第三种外形

## 4. 修复面 C · 按列名写入

- [x] 4.1 `queue_table.py`：新增 `SECTION_COLUMN_NAMES`／`_COLUMN_ALIASES`／`resolve_column_index`／`build_row_cells`／`header_mismatch`；缺列 fail-loud 不补空串
- [x] 4.2 `append-row --set 列名=值`（可重复）；编号列只经 `--number`，在 `--set`/JSON 中重复提供即拒绝
- [x] 4.3 新增子命令 `edit-row --section --number --set/--append 列名=值 [--append-sep]`，含锁归属校验、按编号定位（找不到/命中多行均 fail-loud）
- [x] 4.4 🔴 **`edit-row --changes-json` / `--stdin-json`（回写 #414 时实测补齐）**——`--append` 只能加尾巴，**翻转「状态」格的 `[S:blocked]` → `[S:done]` 前缀必须整格重写**，而真实队列行的状态格数千字且密集使用反引号 ⇒ 不走 JSON 入口就只能把整格正文经 argv 传一遍，正是本行要根治的那件事。缺口在**实际使用自己的工具回写真实队列**那一刻才暴露

## 5. A3-1 · lint 行头断裂盲区

- [x] 5.1 `工具-队列结构lint.py`：新增 `_broken_row_head_violations`，接入 `_lint_one_file` 每个分区的扫描前置
- [x] 5.2 🔴 **更正派单件 A3 的"13 列而 lint 报通过"**——该形态复现不出来（真 13 列的行现有校验当场就报），原报告成因是 `awk -F'|'` 不认反引号保护；已配对照单测锁死该事实（见 design.md 决策点 3）
- [x] 5.3 判据对当前生产队列实测 0 误报，并配回归护栏单测

## 6. A3-2 · release 对自愈的出口

- [x] 6.1 `_head_row_numbers`（读 git HEAD 同分区编号基线，取不到返回 `None` 而非空集合）＋ `RESERVE_WAIVER_MARKER`（`预留豁免：`）＋ `_HEAD_NUMBERS_UNSET` 哨兵
- [x] 6.2 ③预留归属校验接入两条豁免；仅豁免本项，组内重复/归档号重复不受影响
- [x] 6.3 配套**反例**单测：HEAD 中不存在且未预留的新行仍被拒绝——没有它，"豁免生效"与"整项校验被改废"无法区分

## 7. 验收（派单件 A4）

- [x] 7.1 三条修复面各有反例测试，能对旧实现变红——新增 13 项 `QueueWriteRootFixTests` ＋ 4 项 release 自愈用例 ＋ 7 项 lint 盲区用例
- [x] 7.2 **不得边改边用**：先在一次性玩具队列文件上跑通 **19 项**验收（含 §一/§二/§四 与向后兼容），再用于真实队列
- [x] 7.3 `工具-队列结构lint.py` 对 13 列行能报出——**本就能报**，见 5.2 更正
- [x] 7.4 全量回归：`test_工具-共享文档编辑锁.py`／`test_工具-队列结构lint.py`／`test_工具-共享文档编辑锁-补件选表.py`／`test_工具-落库sweep.py`／`test_工具-队列查询.py`／`test_queue_table.py` 合计 **592 passed、35 subtests passed、0 failed**
- [x] 7.5 存量夹具更正：5 处 `#308` 之前写法的测试夹具（状态格为"待领"、无 `[S:` 前缀）同步更新——生产队列 75 条 §一 活行存量合规数为 0 违规，lint 早已硬门禁该格式

## 8. 收尾

- [x] 8.1 队列 §一 #414 行回写（状态、产出路径、两条更正、晋档结果）——**用本变更包新增的 `edit-row --changes-json` 写的真实队列，一次写对、lint 通过、release 一次放行**，晋**档3**达成
- [x] 8.1a 🔴 **回写过程本身又验证了一次守卫**：首次提交被自己的写侧竖线校验当场拒绝（追加正文里写了 `awk -F` 加半角竖线的命令示例）——**又一次「在解释这个 bug 的那一行正文里再犯一次」**，与 #414 第 5 次事故同形，只是这次**被机制拦住了**，没有落库
- [x] 8.2 §二 批次登记——`B-0826_12_414A组队列写入根治收工回写`
- [ ] 8.3 `/opsx:archive` 归档本变更包
