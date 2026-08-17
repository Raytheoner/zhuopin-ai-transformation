# editlock-hold-scope-and-wip-block Tasks

> 🔴 **1.x 全部完成、且 Shao Peishen 已批准 design.md 六个决策点之后，才可开工 2.x 起的实现项。**
> 派单指令：design 停审等批准后再 apply。

## 1. Propose ＋ Design（本次已完成）

- [x] 1.1 现网全量取证：对两份队列文件 §一/§四 全 170 行只读跑现判据与三个候选判据，产出命中集对照表（design 决策点 1）
- [x] 1.2 §四 #52 误报复现：内存内补回被去掉的反引号，确认现判据命中、首段判据不命中（未落盘、未改生产文件）
- [x] 1.3 回答 #324 的前置问题「⑥ 自 #258 落地以来是否真拦下过一次真实的暂缓不一致」——查得真阳性 0 次，且曾被记错的那次归属（#285 行 2026-08-07）当时即已更正为校验①
- [x] 1.4 ⑨ 的白盒核实：确认提示只在 `new_mechanism_row_added` 为真时触发（＝6 次都响了、6 次都被越过）
- [x] 1.5 proposal.md（含知识资产三问／四档晋档条件／守卫退休问答／`.gitignore` 覆盖问答四个强制节）
- [x] 1.6 design.md 六个决策点，均带推荐与默认项
- [x] 1.7 两份 spec delta（`editlock-followup-hold-consistency-guard` MODIFIED+REMOVED／`editlock-mechanism-wip-guard` MODIFIED+ADDED）
- [x] 1.8 `openspec validate editlock-hold-scope-and-wip-block --strict` 通过
- [ ] 1.9 **Shao Peishen 审 design.md 六个决策点**（不答按各自默认项执行）

## 2. Apply — ⑥ 收窄（决策点 1/2/3）

- [ ] 2.1 先写测试后实现：新增 `_leading_conclusion_segment()`（按 `━━━` 取首段，无分隔符时返回整格）
- [ ] 2.2 `_row_hold_language_status()` 改用首段做关键词扫描；§四 文件名提取同步取首段，§一 文件名来源保持 `cells[3]`/`cells[6]`
- [ ] 2.3 删除 `_validate_followup_hold_consistency()` 的反向告警分支（退休项）及其对 `FOLLOWUP_NON_TERMINAL_STATUSES` 的引用（若该常量再无其它消费者则一并删，否则保留并注明现有消费者）
- [ ] 2.4 单测（⑥ 此前 **0 覆盖**，本项须一次补齐）：
  - [ ] 2.4.1 **真阳性**——首段含"暂不发"＋点名 README 中状态为 `🆕 待发` 的信 ⇒ 拒绝 release（这是 ⑥ 存在的全部理由，必须钉住）
  - [ ] 2.4.2 **#52 误报回归**——关键词只在历史段、文件名在另一历史段 ⇒ 放行
  - [ ] 2.4.3 无 `━━━` 的单元格行为与收窄前逐字一致
  - [ ] 2.4.4 仅关键词无文件名 ⇒ 不触发
  - [ ] 2.4.5 反向情形（README 已终态、队列仍称暂缓）⇒ **既不拒绝也不再打印告警**（退休后的断言）
- [ ] 2.5 现网全量回归复核：apply 后重跑 1.1 的对照脚本，确认真实命中集与 design 决策点 1 表中 (甲) 列一致（若不一致，说明期间队列内容已变，须重新取证而非直接采信旧表）

## 3. Apply — ⑨ 阻断化（决策点 4/5/6）

- [ ] 3.1 `cmd_release` 新增逃生阀开关参数（不携带理由文本）
- [ ] 3.2 新增 `WIP豁免：` 标记常量，复用 `FOLLOWUP_SERIAL_WAIVER_MARKER` 既有范式
- [ ] 3.3 `_validate_release_structure` ⑨ 段：超限改为进 `violations`；触发条件保持"仅新增 `[D:机]` §一 行时"不变
- [ ] 3.4 逃生阀双条件判定（开关 ＋ 行内标记），缺任一时的提示分别指出缺哪个
- [ ] 3.5 拒绝提示文案含当前计数／上限、新增行编号、两条出路确切写法
- [ ] 3.6 单测：超限拒绝／未超限放行／业务类行不触发／**存量超限但本次未新增机制行仍放行**（决策点 4 的关键回归，防"把自己锁在门外"）／逃生阀齐备放行／只给开关拒绝／只写标记拒绝
- [ ] 3.7 `--mechanism-wip-cap` 默认值与 help 文案核对（16，不上调）

## 4. 收尾

- [ ] 4.1 `工具-共享文档编辑锁.py` 头部说明段与 `_validate_release_structure` docstring ⑥／⑨ 两段同步改写
- [ ] 4.2 队列协议〇.9 措施 C 正文由"提示不阻断"改为"阻断＋逃生阀"，并写明逃生阀理由须落行内
- [ ] 4.3 全量回归：`0-学习与工具` 全套 ＋ `工具-队列结构lint.py` ＋ sweep ＋ `工具-队列查询.py`，零漂移
- [ ] 4.4 **真实 dogfooding**：本包 apply 自身的 `release` 即会撞上 ⑨（存量 24／16）——如实记录当次是走了关行还是走了逃生阀，作为晋档条件①②的第一份真实样本
- [ ] 4.5 队列 #324 与 §四 #58 第⑶条回填实现结果
- [ ] 4.6 值周巡检 prompt／派单件模板知悉：apply 当天起新建机制行会被真的挡住（`1-转型规划/0-全景路线图/专线opener模板库.md`）
- [ ] 4.7 `/opsx:archive editlock-hold-scope-and-wip-block -y`（全部 tasks 勾完才做）
