## MODIFIED Requirements

### Requirement: ⏭️ 转出档 SHALL 记录去向并继续，MUST NOT 进入决策问答

命中 ⏭️ 档（`.51` 部署及任何触碰生产服务的动作）的动作 MUST NOT 由本能力**自作主张**执行；系统 MUST 记录该动作已转出、须交由 `zhuopin-lan-closeout` 处理，并推送一次性 FYI 通知，MUST NOT 将其纳入等待人工答复的决策问答队列。泳道自身 MUST 继续执行其余不依赖该动作的任务；若后续任务确实依赖被转出的这一项，MUST 按依赖阻塞处理（同失败依赖链例外）。

该动作的档位分类 SHALL 保持为 ⏭️，MUST NOT 因下述放行路径的存在而改判为其他档位——四档的判据轴是可逆性，而放行路径解的是执行时序，两者不同轴。

**新增的唯一放行路径**：在转出记录已存在的前提下，若 Shao Peishen 就该项给出一次明确授权、且当次 LAN 探针实测为 on，则该项 MAY 在同一 session 内继续执行；此路径 SHALL 受能力 `lane-watch-deploy-authorization` 的全部约束（前置三查、逐项粒度、留痕、以及纪律 MUST 取自 `zhuopin-lan-closeout` 正本而 MUST NOT 在本能力侧复制）。缺少上述任一前提时，该项 SHALL 停留在已转出状态。

#### Scenario: `.51` 部署动作被转出

- **WHEN** 泳道的下一步是部署到 `.51`
- **THEN** 系统记录该项转出并注明去向为 `zhuopin-lan-closeout`，不询问任何问题，泳道继续执行其余独立任务

#### Scenario: 转出项被下游依赖

- **WHEN** 泳道的后续任务需要读取刚被转出、尚未执行的 `.51` 部署结果
- **THEN** 该后续任务 MUST 视同依赖阻塞，不得假定转出项已完成而盲目继续

#### Scenario: 无授权时转出状态不变

- **WHEN** 某项已被转出，但无当次授权记录（或 LAN 探针实测非 on）
- **THEN** 该项 SHALL 保持已转出状态，本能力 MUST NOT 执行它；档位判定结果仍为 ⏭️

#### Scenario: 授权存在时档位判定结果不变

- **WHEN** 某项已被转出且已获授权，系统再次对该动作做档位判定
- **THEN** 判定结果仍为 ⏭️，MUST NOT 返回其他档位——授权改变的是该项能否被执行，不是它属于哪一档

### Requirement: 本能力 MUST NOT 自动执行对外发送与生产部署类动作

无论决策点判据如何演进，本能力 MUST NOT 自动发送任何对外内容（跟进信、企微群消息、专员触达）、MUST NOT 自动完成 L2 人工门禁签字、MUST NOT 自动变更合规红线、MUST NOT 参与 ASIL C/D 相关自动修改——这些永远停在"已准备好、等人确认"状态。

`.51` 部署及任何触碰生产服务的动作，本能力 MUST NOT **自行**执行；其唯一例外 SHALL 是能力 `lane-watch-deploy-authorization` 定义的授权放行路径，且该路径本身以「Shao Peishen 就该项的一次明确授权」为不可省略的前提——**没有他的授权就没有例外**。放宽仅及于 `.51` 部署这一项，MUST NOT 被援引为放宽对外发送、L2 门禁签字、合规红线变更或 ASIL C/D 相关动作的依据。

#### Scenario: 对外发送类动作止步于可发送态

- **WHEN** 某任务的完成需要向专员发送一封跟进信
- **THEN** 系统只将其准备到可发送状态即停，MUST NOT 自动执行发送

#### Scenario: 授权路径 MUST NOT 被援引到其他红线动作上

- **WHEN** 某任务命中 🔴 档（对外发送／L2 门禁签字／合规红线变更／ASIL C-D 相关），且 Shao Peishen 在场并已就某个 `.51` 部署项给过授权
- **THEN** 该 🔴 档任务 SHALL 仍然停在"可发送态/等人确认"，MUST NOT 因存在部署授权而被一并放行
