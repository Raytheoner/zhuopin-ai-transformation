# queue-domain-strict-routing Tasks

> 🔴 **本次只做 1.x（propose＋design），2.x 起的 apply 任务列出方案供 Shao Peishen 审阅与后续 session 承接，本次不开工。**
> 派单指令：队列 `#341` 明示"止步于起草不代拍板"——design 停审等 Shao Peishen 批准后再 apply。

## 1. Propose ＋ Design（本次已完成）

- [x] 1.1 读取正本：队列 `#341`（`--row 341 --field all`）／`openspec/changes/archive/2026-08-17-queue-dual-file-split/tasks.md` §2.4／§3.7／design.md 决策点 3／7／两份主 spec 的「实现差异」标注
- [x] 1.2 白盒核实三处源码现状（非推测）：`工具-共享文档编辑锁.py`（`_resolve_append_target`／`QUEUE_LOCK_ANCHOR`／`_is_queue_system_target`）、`repo_paths.py::DEFAULT_QUEUE_RELATIVE_PATH`、`工具-队列结构lint.py`／`工具-落库sweep.py` 是否实现「跨文件一致性交叉校验」
- [x] 1.3 白盒核实推翻归档件一处自我表述——`editlock-dual-queue-routing` spec「锁粒度」Requirement 与其"📌 来源"标注称"独立锁已是既成实现"，实测代码为统一锚点锁（`QUEUE_LOCK_ANCHOR = QUEUE_MECHANISM_PATH_REL`）
- [x] 1.4 核实 `专线opener模板库.md` §〇.7（队列纪律格式唯一来源）现状——`--domain` 仍记为方括号可选参数，佐证"迁移期妥协"近一个月未附退出条件
- [x] 1.5 proposal.md（含知识资产三问／四档晋档条件／守卫退休问答／`.gitignore` 覆盖问答四个强制节）
- [x] 1.6 design.md 四个决策点，均带背景实证、推荐、被否候选与默认项
- [x] 1.7 两份 spec delta：`queue-dual-file-topology`（MODIFIED「§二 域路由」＋ MODIFIED「跨文件一致性交叉校验」）／`editlock-dual-queue-routing`（MODIFIED「acquire/append-row 按域路由」＋ REMOVED「锁粒度——独立锁」＋ ADDED「锁粒度——统一锚点锁」）
- [x] 1.8 `openspec validate queue-domain-strict-routing --strict` 通过
- [ ] 1.9 **Shao Peishen 审 design.md 四个决策点**——本次收工即停，pause 等待

## 2. Apply — 机器人默认值改动（决策点 1 第 1 条，无需观察期）

- [ ] 2.1 `repo_paths.py::DEFAULT_QUEUE_RELATIVE_PATH` 改指业务场景文件，恢复方案件 §6.5 建议 4 原始设计意图
- [ ] 2.2 配套单测：机器人默认写入目标为业务场景文件；既有依赖旧默认值的用例按改判处理（如有）
- [ ] 2.3 apply 前置核实：全仓 grep（或 `工具-仓库外载体扫描.py`）确认无下游消费者硬编码依赖"机器人行恒在机制环境文件"这一现状（design.md Risks 段已登记）

## 3. Apply — 编辑锁两阶段收紧（决策点 1 第 2 条）

- [ ] 3.1 阶段 (a)：软提示升级（`工具-共享文档编辑锁.py` 行 1924／2036 附近，比照"行长校验⑪ 首周告警"呈现范式）
- [ ] 3.2 阶段 (a)：`专线opener模板库.md` §〇.7 `[--domain 机|业]` 改为无方括号必需，登记阶段 (b) 确切生效日期（批准日 +7，本机 `Get-Date` 当场计算）
- [ ] 3.3 阶段 (a)：巡查现网 `append-row --section 一|二` 调用点（定时任务真身／opener 集／既有脚本），逐一补 `--domain`
- [ ] 3.4 观察满一个值周巡检节拍（约 7 天），确认现网无声明域调用已归零（`工具-队列查询.py --digest --grep`，不得整文件通读）
- [ ] 3.5 阶段 (b)：`_resolve_append_target()` 改 fail-loud；退休软提示分支（proposal.md「本次退休哪一个既有守卫」已登记）
- [ ] 3.6 阶段 (b) 落地后：移除两份 spec 中「§二 域路由」／「acquire/append-row 按域路由」的"实现差异"标注（该次 apply 变更包内完成）

## 4. Apply — 一致性交叉校验补齐（决策点 3）

- [ ] 4.1 `工具-队列结构lint.py` 新增：读取行的物理文件位置与 `[D:]` 字段值，不一致时输出数据完整性告警（不阻断、不自动迁移）
- [ ] 4.2 单测覆盖：一致／不一致两种情形；对现网两份队列真身跑一次全量核对，确认历史错位行（如 `#336`，若届时仍可查）被正确识别

## 5. Apply — 锁粒度 spec 更正的代码侧防回归（决策点 2）

- [ ] 5.1 新增单测钉住"队列系统模式下两个域（`--domain 机`／`--domain 业`）的锁路径逐字相同"，防止未来被误"修复"为独立锁
- [ ] 5.2 `工具-共享文档编辑锁.py` 相关注释同步核对，确保与 spec 新表述一致（本次移除的是 spec 层面的误述，代码本身注释已经写对，只需交叉确认无需改动）

## 6. 收尾

- [ ] 6.1 队列 `#341` 行回填：指向本变更包 `queue-domain-strict-routing`，状态按当时进度更新
- [ ] 6.2 全量回归零漂移：`0-学习与工具` 全套 ／ `5-平台底座/zhuopin_platform` ／ `openspec validate --all --strict`
- [ ] 6.3 `/opsx:archive queue-domain-strict-routing -y`（全部 tasks 勾完、决策点 1 阶段 (b) 已落地才可执行；若阶段 (b) 观察期未满，按"完工即归档"纪律的例外条款登记"预期观察窗口：N 天"，暂不归档）
