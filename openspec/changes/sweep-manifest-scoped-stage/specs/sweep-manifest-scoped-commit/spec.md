## ADDED Requirements

### Requirement: sweep 自动提交的内容范围等于本步骤声明的路径集合
`工具-落库sweep.py` 的每一次自动 `git commit`，其产生的 commit 所含的路径集合 SHALL 等于该步骤自身通过 `git add -- <pathspec>` 声明的那个集合。

对批次落库主路径（`_process_normal_batch`），该集合 SHALL 为「本批次"文件清单"列解析出的 `resolved` 路径 ＋ 该批次所在的队列文件路径」——即与该函数两处 `git add` 的并集**逐字一致**，MUST NOT 另起一套计算。

未被本步骤声明、但当前已存在于 git index 中的任何路径（来自并发 session、人工暂存、中断在半路的流程、或被编辑锁「登记豁免」放行的脏文件），MUST NOT 出现在该 commit 中。

本 Requirement 对 sweep 的**全部**自动提交生效（批次落库、队列孤儿改动即时提交、遗留尾巴补销、台账重跑、定时任务镜像同步），MUST NOT 只对批次落库主路径生效——作用面由 design 决策点② 拍板；若拍板取窄，未覆盖的提交点 MUST 在代码注释中写明"本点尚未收紧"及其理由，MUST NOT 静默留白。

#### Scenario: 清单外的已暂存文件不得被带进批次提交
- **WHEN** git index 中存在一个不属于本批次文件清单的已暂存路径，且该批次照常落库
- **THEN** 新产生的 commit 的 `git show --name-only` 输出**不含**该路径，该路径的改动仍留在工作区／index

#### Scenario: 清单内的路径必须全部进入该批提交
- **WHEN** 本批次文件清单解析出的 `resolved` 路径均有实际改动
- **THEN** 新产生的 commit 含且仅含这些路径与该批次所在的队列文件路径

#### Scenario: 非恒真自证——关掉收紧逻辑后同一输入由"未带入"变回"带入"
- **WHEN** 把本 Requirement 的实现旁路掉（预期集合退化为"index 全部内容"），重放上面第一个 Scenario 的同一输入
- **THEN** 该清单外路径**重新出现**在 commit 中 —— 本 Scenario 用于证明拦截确实来自本变更包新增的实现，而非 `_manifest_coverage_gap`（#136）／`_partition_pending_rows_by_batch_isolation`（#238）／"非 clean 整轮跳过"等既有检查顺手挡下

#### Scenario: 声明路径当前无任何改动时不产生错误提交
- **WHEN** 本步骤声明的路径集合在 index 中无任何待提交改动
- **THEN** 工具 MUST NOT 产生一个空提交、MUST NOT 因此抛出未捕获异常；须沿用既有"本轮无内容可提交"的处置路径并留痕，MUST NOT 新造分支语义

### Requirement: 提交后须校验实际内容并对不一致出声
每次自动提交完成后，工具 SHALL 读取该 commit 实际包含的路径集合（`git show --name-only --format=`），与提交前的预期集合比对。

两者不一致时，工具 MUST 出声——写入本轮日志并按既有告警通道推送一次，提示中 MUST 点名 commit 的 sha、预期集合与实际集合的差集（两个方向都要点名：多出来的与缺失的）。

⚠️ 本项是**事后**校验，MUST NOT 被表述为拦截手段——真正的拦截来自上一条 Requirement 的实现。工具的回显与本变更包的任何汇报措辞 MUST 如实区分这两者。

不一致时是否阻断本轮后续步骤由 design 决策点④ 拍板；🔴 无论拍板取哪一项，**MUST NOT 试图"撤销"已产生的提交**（提交已发生，回滚属人工判断范围）。

#### Scenario: 提交内容与预期一致时静默
- **WHEN** 提交实际含的路径集合与预期集合相等
- **THEN** 不产生告警，只在本轮日志留一行常规记录（不制造 #147 式噪音）

#### Scenario: 提交内容与预期不一致时点名告警
- **WHEN** 提交实际含的路径集合与预期集合存在差集
- **THEN** 本轮日志与告警推送中出现该 commit 的 sha 与两个方向的差集路径

### Requirement: 被挡下的清单外内容须有承接方且措辞受限
收紧后留在工作区／index 中的清单外内容，其去向 SHALL 有明确承接方——既有孤儿脏文件告警（`_track_and_alert_orphan_paths`）为默认承接方。

本轮 sweep 主动未带走清单外内容时，是否额外点名由 design 决策点③ 拍板。

🔴 **覆盖边界须如实措辞**：工具的回显与本变更包的任何汇报 MUST 表述为「**本批提交内容已限定在清单声明范围内**」一类的受限断言，MUST NOT 表述为「sweep 提交从此不可能含意外文件」一类的全覆盖断言。

理由（判据，非说明）：编辑锁 release 守卫⑹ 有两条已成文的身份豁免（`SWEEP_LOCK_WHO` 与企微机器人，见 `工具-共享文档编辑锁.py` 常量 `SELF_COMMITTING_LOCK_HOLDERS`），这两个身份写队列时不受 ⑹ 约束 ⇒ 它们造出的清单外脏文件只剩孤儿**告警**一道兜底，而告警不是闸。

#### Scenario: 回显不作全覆盖断言
- **WHEN** 本轮批次全部按清单范围落库、无异常
- **THEN** 工具的回显只声称本批提交内容已限定在清单声明范围内，不声称 sweep 提交不可能含意外文件
