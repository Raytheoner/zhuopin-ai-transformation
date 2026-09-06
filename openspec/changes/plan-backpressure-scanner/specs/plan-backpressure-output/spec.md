## Purpose

定义扫描结果的输出形态与落点：只读清单、sweep 常驻轮次接入（第 13 类）、陈化抑制，以及"产出队列行"这一动作的自动化边界——使扫描结果既不消亡于一份没人看的报告，也不越过并入审核、环境保障线与域级暂缓这三条现行边界。

> 🛑 **写侧条款（最后一节）依赖 design D5 的拍板，未审前不得实现。** 本 spec 的只读侧条款不受该拍板影响。

## ADDED Requirements

### Requirement: 清单分档输出
扫描输出 SHALL 至少分为三档并分别列示：⑴「三处皆无」；⑵「疑似已承接·待人确认」（别名命中但被 `excludes` 降级）；⑶「已承接」（附命中证据）。三档 MUST NOT 合并为单一列表。

#### Scenario: 分档可分别消费
- **WHEN** 生成一次输出
- **THEN** 三档 SHALL 各自可被独立读取与计数，且每档的场景数量 SHALL 出现在输出头部

### Requirement: 输出件落点
只读清单与运行状态文件 SHALL 落在 `reports/` 目录下（已被 `.gitignore` 覆盖，不入库）；扫描器 MUST NOT 向版本控制中写入清单类产出。

#### Scenario: 清单不入库
- **WHEN** 扫描器写出清单与状态文件后执行 `git status`
- **THEN** 工作区 SHALL 无新增的未跟踪文件

### Requirement: 输出文案界定本包的回答范围
输出 SHALL 含一句固定说明，声明本清单只回答"该场景对现役机制是否可见"，不构成排期建议或开工授权。

#### Scenario: 不被误当排期建议
- **WHEN** 任一档中出现场景
- **THEN** 输出中 SHALL 同时出现该范围声明，并指向负责排期与优先级的队列行

### Requirement: 接入 sweep 常驻轮次
扫描 SHALL 以 `工具-落库sweep.py` 的**第 13 类**常驻状态告警形式接入每小时轮次，并 SHALL 走子进程调用而非进程内 import。

#### Scenario: 类号不与既有类冲突
- **WHEN** 本能力落地
- **THEN** 其类号 SHALL 为第 13 类，MUST NOT 复用第 1 至第 12 类中任一已被占用的类号

#### Scenario: 子进程隔离
- **WHEN** 扫描子进程异常退出
- **THEN** sweep 本轮的其余各类 SHALL 不受影响，且该异常 SHALL 被记录

### Requirement: 本轮是否真的执行过必须可区分
第 13 类 SHALL 在每轮结束时留下一条可区分「本轮已巡检且无告警」与「本轮根本没跑到」的痕迹；两种情形的痕迹 MUST NOT 相同。

#### Scenario: 整轮早退留痕
- **WHEN** sweep 因早退未执行到第 13 类
- **THEN** 状态文件中 SHALL 留下"本轮未巡检"的痕迹，且连续未巡检达到阈值 SHALL 产生一条告警

#### Scenario: 巡检恢复通知
- **WHEN** 此前已因连续未巡检告警，本轮真正执行到第 13 类
- **THEN** SHALL 发出一条巡检已恢复的解除通知

### Requirement: 陈化抑制与陈化催办
推送 SHALL 以「当前未承接场景码集合」为指纹，集合未出现新场景码时保持静默；同时 SHALL 在集合非空且持续超过阈值天数时发出一次陈化催办。

#### Scenario: 集合不变即静默
- **WHEN** 连续两轮的未承接场景码集合完全一致
- **THEN** 第二轮 SHALL 不推送

#### Scenario: 新增场景码即推送
- **WHEN** 某轮的未承接集合中出现了上一轮没有的场景码
- **THEN** SHALL 推送一次，并在推送中点名新增的场景码

#### Scenario: 同一批不在 24 小时内重复推送
- **WHEN** 同一批未承接场景在 24 小时内被再次判定
- **THEN** MUST NOT 产生第二次推送

### Requirement: 域级暂缓场景移出推送但保留在清单
`suspended` 非空的场景 SHALL 保留在清单的对应档中并标注暂缓来源与日期，但 SHALL 被排除出常规推送；对该类场景 SHALL 另按更长周期发出一次"该暂缓已持续 N 天，是否仍成立"的复核提醒。

#### Scenario: 暂缓场景不制造每轮噪音
- **WHEN** 某未承接场景带 `suspended` 标记
- **THEN** 常规推送中 MUST NOT 出现该场景，而清单中 SHALL 出现并标注其暂缓来源与日期

#### Scenario: 暂缓本身会被复核
- **WHEN** 某场景的 `suspended` 生效日期距今超过复核周期
- **THEN** SHALL 发出一次复核提醒，指出该暂缓已持续的天数

### Requirement: 误报与负例分开计数
输出与状态记录 SHALL 把「报了未承接、而实际三处之一有真实承接」（误报）与「报了未承接、而人决定不立行」（负例）分开计数，MUST NOT 合并为单一计数。

#### Scenario: 负例不驱动判据收紧
- **WHEN** 某场景因域级暂缓而被人判定不立行
- **THEN** 该事件 SHALL 记为负例，MUST NOT 计入误报，也 MUST NOT 触发任何自动的判据收紧

---

## 写侧（🛑 依赖 design D5 拍板，未审前不得实现）

### Requirement: 队列行产出的自动化边界
在 design D5 拍板之前，扫描器 MUST NOT 向任何一份跨桌任务队列写入任何内容；拍板之后的写入行为 SHALL 严格限于所批准的档位。

#### Scenario: 未拍板前纯只读
- **WHEN** design D5 尚未拍板而扫描器被执行
- **THEN** 两份队列文件的内容 SHALL 逐字节不变

#### Scenario: 域级暂缓场景永不自动立行
- **WHEN** 某场景带 `suspended` 标记
- **THEN** 无论 D5 拍板为哪一档，扫描器 MUST NOT 为该场景自动写入业务场景队列行

#### Scenario: 写入动作走既有咽喉并留审计
- **WHEN** 拍板后的档位允许扫描器写入队列
- **THEN** 写入 SHALL 经由共享文档编辑锁的既有命令完成（不得裸手改文件），且该动作 SHALL 写入 append-only 审计
