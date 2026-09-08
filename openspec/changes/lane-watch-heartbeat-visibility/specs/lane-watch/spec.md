> **基线依赖（design 决策点 6(a)）**：本 delta 的 MODIFIED 块以 `openspec/changes/lane-watch-mode/specs/lane-watch/spec.md` 的同名 requirement 为基线——`lane-watch` capability 目前尚未归档进 `openspec/specs/`。🔴 **本包 MUST 在 `lane-watch-mode` 之后归档**，否则会得到一份「修改了不存在的 requirement」的 spec。

## MODIFIED Requirements

### Requirement: 波间 SHALL 监测心跳，超时 MUST 暂停并等待人工判断

系统 MUST 周期性检查活跃泳道的心跳信号；若某泳道心跳超过 30 分钟未更新，MUST 暂停该泳道的后续波次、发出告警并等待人工判断，MUST NOT 自行判定该泳道是失败还是仍在执行长任务。已处于等待人工答复状态的泳道 MUST NOT 被心跳检查重复触发。

**🆕 读写同锚**：心跳信号的**写入位置与读取位置 MUST 由同一个仓库根锚解析**，且该锚 MUST 恒定指向主工作区——泳道在 linked worktree 内写下的心跳，看护者从主工作区 MUST 能读到同一份。系统 MUST 提供心跳的**写入入口**，由该入口负责路径解析；心跳路径 MUST NOT 以「由调用方按自身工作目录解析的相对路径」形态出现在任何执行指引中。系统 MUST NOT 以「读不到就换个位置再找一遍」的方式弥补锚不一致，MUST NOT 跨工作区搜索同名心跳文件取其最新者。

**🆕 终态豁免**：已进入终态的泳道 MUST NOT 被判为失联。终态的判定 SHALL 以泳道状态记录为权威来源；仅当状态记录未标终态时，SHALL 回落读取心跳文件末行的收工哨兵作为只读推断，且该推断 MUST NOT 回写状态记录。豁免生效时系统 MUST NOT 暂停该泳道、MUST NOT 发出告警，并 MUST 在返回结果中给出**可与「健康运行中」相区分**的原因标识。

30 分钟阈值 SHALL 保持不变——本条改的是「什么算失联」的覆盖范围，不是「多久算超时」的数值。

#### Scenario: 心跳超过 30 分钟未更新
- **WHEN** 某活跃泳道的心跳信号连续 30 分钟未更新
- **THEN** 该泳道后续波次暂停，系统发出告警并等待人工确认，而非自行判定为失败

#### Scenario: 已暂停泳道不重复触发看门狗
- **WHEN** 某泳道已处于等待人工答复 D1 决策点的暂停状态
- **THEN** 心跳检查 MUST NOT 对该泳道重复发出告警或改写其等待原因

#### Scenario: 泳道在隔离工作区内写心跳，看护者从主工作区读
- **WHEN** 某泳道运行于 linked worktree，经系统提供的写入入口写下一行心跳
- **THEN** 看护者从主工作区执行心跳检查 MUST 读到该行，MUST NOT 因位置不一致而判其失联

#### Scenario: 写入入口与读取侧解析出同一路径
- **WHEN** 分别在主工作区与任一 linked worktree 内解析同一泳道的心跳路径
- **THEN** 两次解析结果 MUST 为同一个绝对路径，且该路径位于主工作区

#### Scenario: 已完工泳道收工后自然静默
- **WHEN** 某泳道已标记完工，其后超过 30 分钟无新心跳
- **THEN** 系统 MUST NOT 暂停该泳道、MUST NOT 发出告警，并在结果中标明其为终态豁免而非健康运行中

#### Scenario: 存量泳道仅在心跳文件末行写下收工哨兵
- **WHEN** 某泳道未调用写入入口标记状态，但其心跳文件末行为收工哨兵，且其后超过 30 分钟无更新
- **THEN** 系统 SHALL 据该哨兵豁免该泳道，且 MUST NOT 据此回写其状态记录

#### Scenario: 终态豁免与健康运行必须可区分
- **WHEN** 调用方对一条已终态泳道与一条心跳新鲜的运行中泳道分别执行心跳检查
- **THEN** 两次返回 MUST 在原因标识上不同，MUST NOT 输出无法区分的同一结果
