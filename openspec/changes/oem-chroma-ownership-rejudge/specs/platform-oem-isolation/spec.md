## ADDED Requirements

### Requirement: 隔离层 SHALL 按三层分别表述，不得作为单一整体挂靠
「OEM 隔离层」在任何权威载体中 MUST 按三层分别表述：**L1 路由 guard**（`OEMRouter`）／**L2 唯一入口**（`rag.retrieve()`）／**L3 向量库本体**（Chroma 实例与部署）。三层的依赖方、就绪度与到期日 MUST 各自独立记录。载体 MUST NOT 使用「隔离层就绪」「Chroma 归属」这类不指明层次的表述作为排期前提或门禁判据。

#### Scenario: 场景把「隔离层就绪」写成前置
- **WHEN** 某场景在前置表或排期表中写「待 OEM 隔离层就绪」
- **THEN** 该表述不合规，MUST 改写为指明所需层次（如「待 L2 唯一入口就绪」）

#### Scenario: QD-B 类只需路由 guard 的场景
- **WHEN** 场景红线只要求「走 `data_isolation_layer.OEMRouter` 按客户路由」
- **THEN** 该场景依赖 L1，L1 已就绪 ⇒ 该场景 MUST NOT 被记为「等待 Chroma」

### Requirement: L2/L3 的到期日 SHALL 由消费方机械重算，不得写成孤立常量
L2 与 L3 的到期日 MUST 由规则推出：**取所有「需跨客户检索 OEM 数据」的已排期场景中，最早的前置开工日**；若该场景另有更早的数据落盘门禁（如历史库归集须「归集时即分库」），MUST 取更早者。任一场景的排期、范围或检索需求变更时，MUST 在同一次重排内重算该日期；该重算 MUST 是 `zhuopin-rebaseline` 重组循环的固定步骤，MUST NOT 依赖任何人回头记起。载体 MUST NOT 只保留一个无算法留痕的日期常量（D3 =(a)，Shao Peishen 2026-09-02）。

L1 MUST NOT 设到期日；其约束为「不得下线」，理由 ＝ 现行已上线场景的 OEM 红线 ＋ 根 `CLAUDE.md` §4 质量域隔离边界（两者皆常设）。

#### Scenario: 某消费方的检索需求被业务方删除
- **WHEN** 一个原本需要跨客户检索的场景被收敛为不需检索（如 Q4 由 18 项文件包收敛为三文件内部比对）
- **THEN** 该场景退出到期日推算集合（仅保留存储侧隔离要求），并 MUST 在同批重算 L2/L3 到期日

#### Scenario: 只需存储侧隔离的消费方
- **WHEN** 某场景的 OEM 数据只需按客户分库存储、不做跨客户检索
- **THEN** 该场景 MUST NOT 计入 L2/L3 到期日推算，但其分库存储与脱敏门禁 MUST 照常适用

#### Scenario: 语料只作离线校准、不进生产检索路径
- **WHEN** 某场景以规则库逐条判定为生产路径，历史语料仅用于离线校准/评测，不被生产链路检索
- **THEN** 该场景 MUST NOT 计入 L2/L3 到期日推算；但其语料归集 MUST 照常按客户分库落盘并执行脱敏 SOP——「不进检索路径」MUST NOT 被读作「可以混库存放」

#### Scenario: 到期日未答定期间
- **WHEN** 推算所需的输入（某场景是否需检索）尚未裁决
- **THEN** 现行日期沿用为「不得放宽的下限」，且 MUST NOT 据此自行收紧——两个方向都属改口径，须经裁决

#### Scenario: 推算输入已裁决后重算得出的新日期
- **WHEN** 推算所需的输入已由裁决人答定，按本规则重算得出与现行常量不同的日期
- **THEN** 新日期 SHALL 直接生效并替换旧常量，MUST NOT 再被「不得放宽」的原约束挡住——该约束的解除条件即「重判出结论」；重算须同批留下算法、输入与裁决人留痕

### Requirement: 检索侧唯一入口 SHALL 不可绕过，未建成前禁止场景自接向量库
所有对 OEM 数据的检索 MUST 经平台提供的唯一入口 `rag.retrieve()`，guard MUST 内嵌于入口内部且不可绕过。场景代码 MUST NOT 直接持有向量库 client。该入口未建成前，任何场景 MUST NOT 自行接入向量库——包括以「先跑通、上线前再收口」为由的临时接入。

单实例多 collection 的部署形态 SHALL 被允许（依据：客户 NDA 无「物理隔离／独立实例／独立存储介质」条款——D0 =(b)，Shao Peishen 2026-09-02；🔴 若日后新签或改签的 NDA 出现该类条款，本许可 MUST 回炉重判），但其合规性 MUST 同时满足三条件：① 本入口不可绕过；② 违规企图必留痕；③ 备份/导出/日志面同受控。任一条件不成立时，MUST NOT 以「已按客户分 collection」作为满足隔离要求的依据。

#### Scenario: 场景在入口未就绪时想先接
- **WHEN** 某场景排期临近而 `rag.retrieve()` 未建成
- **THEN** MUST 顺延该场景或先建入口，MUST NOT 自持 client 绕过

#### Scenario: 以实例数替代入口控制
- **WHEN** 有人主张「已改为每 OEM 一个独立实例，故无需唯一入口」
- **THEN** 该主张不成立——实例数控制的是爆炸半径，入口唯一性控制的是是否会发生；两者 MUST NOT 互相替代

### Requirement: 通用知识库 SHALL 由写入侧校验把关，校验入口未建成前只读
通用（跨客户可读）collection 的**写入** MUST 经校验入口，该入口 MUST 执行三项：① 无 OEM 信息校验（不含客户名称/车型/项目代号/客户零件号/可反推客户身份的组合信息）；② 含 OEM 信息的内容须完成实体脱敏并由质量 Champion 签字确认；③ 写入操作写平台 audit（操作人、内容摘要、脱敏确认人）。

该校验入口建成前，通用 collection MUST 置为只读——既有内容不受影响，禁止任何新写入（D5 =(a)，Shao Peishen 2026-09-02）。**离线校准/评测语料 MUST NOT 以「不进生产检索路径」为由绕过本闸写入通用 collection。**读取侧对通用 collection 的无条件放行 SHALL 仅在写入侧校验生效的前提下成立。

#### Scenario: 校验入口未建成时写入通用库
- **WHEN** 某场景尝试把一份质量案例写入 `kb_quality_cases` 而校验入口尚未建成
- **THEN** 写入 MUST 被拒绝

#### Scenario: 含 OEM 信息的 8D 进入通用案例库
- **WHEN** 一份含客户名称与车型的 8D 报告被提交至通用案例库
- **THEN** MUST 被无 OEM 信息校验拦下；经脱敏并由质量 Champion 签字后方可写入，且写 audit

### Requirement: 运维面 SHALL 同受隔离约束
备份、快照、导出、日志与监控采样 MUST 同受 OEM 隔离约束：任何一次操作 MUST NOT 在无控制的情况下同时导出多家 OEM 的数据；导出与备份操作 MUST 写平台 audit。单实例部署形态下，本条 SHALL 被视为爆炸半径的唯一控制手段，MUST NOT 缺省。

#### Scenario: 全库快照
- **WHEN** 对承载多 OEM collection 的实例做整体快照或备份
- **THEN** MUST 记录该操作（操作人、范围、去向）并按 OEM 数据的同等保密级别管控存放介质

#### Scenario: 调试日志含检索内容
- **WHEN** 检索链路的调试日志会落盘检索命中的文档片段
- **THEN** MUST 脱敏或按 OEM 分域落盘，MUST NOT 汇入跨客户共享的日志流

## MODIFIED Requirements

### Requirement: 跨 OEM 访问拒绝前写审计
`OEMRouter` SHALL 在抛出 `CrossOEMAccessError`（未注册 OEM 上下文 / 跨客户专属库访问）**之前**写一条 `AuditEvent`（`action="cross_oem_access_denied"`，含 oem/collection/reason），使违规企图留痕。

✅ **D2 已裁决 =(a) 收紧（Shao Peishen 本人，2026-09-02）——以下文本已定稿生效：**

审计 MUST NOT 是可选的。未显式注入 `audit` 时，`OEMRouter` MUST 使用平台默认 `AuditLogger`；默认 logger 亦不可用时，`resolve()`/`guard()` MUST 直接拒绝访问（fail-closed），MUST NOT 在无留痕的情况下放行或静默抛错。

> **变更理由**：原文「无 audit 注入时仅抛错（向后兼容）」与 `3-治理与合规/OEM数据隔离规范.md` §3.2「**每次**触发**必须**写平台 audit……违规**企图**本身就是审计事件」直接冲突。默认构造 `OEMRouter()` 不注入 audit ⇒ 任何遗漏注入的调用点，其违规拦截都不产生证据；在 IATF 可追溯性审核下，「拦截到了却没有证据」与「没拦截」是同一个结论。
> **本条属合规红线口径变更**（根 `CLAUDE.md` §5 决策代理条：孙涛不可代，须 Shao Peishen 本人）——**已由 Shao Peishen 本人于 2026-09-02 裁决 =(a) 收紧，代理条已满足。**
> ⚠️ **实现另立行**：本条改 `OEMRouter` 构造签名与 `_record_denied` 行为，命中 openspec 门槛③ ⇒ 由独立变更包承接（含单测回归与调用点核查），本包只落 spec 文本。

#### Scenario: 跨 OEM 拒绝前写审计
- **WHEN** 在 OEM-A 上下文中访问属于 OEM-B 的专属集合
- **THEN** 写 `cross_oem_access_denied` 审计事件（含 oem/collection/reason）后抛 `CrossOEMAccessError`

#### Scenario: 未注入 audit 时使用默认 logger
- **WHEN** `OEMRouter` 以默认构造创建，发生跨 OEM 访问
- **THEN** 经平台默认 `AuditLogger` 写留痕后抛 `CrossOEMAccessError`

#### Scenario: 审计通道完全不可用
- **WHEN** 默认 `AuditLogger` 亦不可用（如落盘失败）
- **THEN** `resolve()`/`guard()` 直接拒绝访问，MUST NOT 无留痕放行
