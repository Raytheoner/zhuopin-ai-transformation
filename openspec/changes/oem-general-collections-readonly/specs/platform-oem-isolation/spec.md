## ADDED Requirements

### Requirement: 通用库只读闸 SHALL 在路由层以独立写入入口强制执行

本条是「通用知识库 SHALL 由写入侧校验把关，校验入口未建成前只读」（D5=(a)，Shao Peishen 2026-09-02）这条**政策**的**强制点**：规定该政策在代码中由谁、以什么 API、以什么错误、以什么留痕来执行。两条分工不同，MUST NOT 互相替代。

平台 SHALL 提供与读取分离的写入侧准入入口 `OEMRouter.guard_write(oem, collection)`。对通用（跨客户可读）collection 的写入 MUST 被拒绝并抛 `GeneralCollectionReadOnlyError`；拒绝**之前** MUST 写一条 `AuditEvent`（`action="general_collection_write_denied"`，含 oem/collection/reason）。该拒绝 MUST NOT 因 OEM 上下文而豁免——未建成校验入口时任何上下文（含已注册的合法客户）一律被拒。

审计通道不可用时（默认 `AuditLogger` 构造失败或写入失败），`guard_write()` MUST 仍以拒绝告终（fail-closed），MUST NOT 无留痕放行、MUST NOT 无留痕静默抛错。本条的 fail-closed 义务范围仅限**拒绝路径**，与「跨 OEM 访问拒绝前写审计」一条的既有边界一致，本条不扩大。

`GeneralCollectionReadOnlyError` MUST NOT 是 `CrossOEMAccessError` 的子类：两者语义与处置动作不同，且继承会使既有 `except CrossOEMAccessError` 顺手吞掉本闸，构成隐性绕过路径。

只读闸 MUST NOT 提供运行期开关、环境变量或可注入的 validator 钩子——任一形式都会退化为"注入空校验器即放行"的绕过路径。解除本闸 MUST 通过改写实现（把拒绝分支换成对真实校验入口的调用）并经独立变更包评审。

只读闸 MUST NOT 改变读取侧语义，MUST NOT 影响通用 collection 的既有内容——D5 裁决文本明写"已有内容不受影响，仅禁新写入"。

写入目标不是通用 collection 时，`guard_write()` MUST 沿用既有的跨 OEM 判定与留痕（本客户专属库放行、其它客户专属库拒绝并写 `cross_oem_access_denied`），MUST NOT 另立一套跨客户规则。

#### Scenario: 场景尝试写入通用库
- **WHEN** 某场景以任一 OEM 上下文调用 `guard_write()` 写入 `kb_supplier` / `kb_quality_cases` / `kb_finance_rules`
- **THEN** 写 `general_collection_write_denied` 审计事件后抛 `GeneralCollectionReadOnlyError`，写入被拒绝

#### Scenario: 离线校准语料想绕过只读闸
- **WHEN** 某场景主张其语料"仅作离线校准、不进生产检索路径"，据此写入通用 collection
- **THEN** 该主张 MUST NOT 构成豁免，写入照样被只读闸拒绝并留痕

#### Scenario: 审计通道不可用时的写入企图
- **WHEN** 默认 `AuditLogger` 亦不可用（构造失败或落盘失败）且发生通用库写入企图
- **THEN** `guard_write()` MUST 仍拒绝写入，MUST NOT 无留痕放行

#### Scenario: 写入本客户专属库
- **WHEN** 已注册 OEM 上下文对自身专属 collection 调用 `guard_write()`
- **THEN** 放行，且 MUST NOT 写违规审计（审计故障不改变允许路径的结果）

#### Scenario: 写入其它客户专属库
- **WHEN** OEM-A 上下文对属于 OEM-B 的专属 collection 调用 `guard_write()`
- **THEN** 按既有跨 OEM 判定拒绝，写 `cross_oem_access_denied` 审计后抛 `CrossOEMAccessError`

#### Scenario: 有人主张加开关临时放开写入
- **WHEN** 有人以"先跑通、上线前再收口"为由要求加运行期开关或注入一个空 validator 放开通用库写入
- **THEN** 该主张不成立——解闸的唯一路径是建成 §2.3 三项校验入口并改写实现，MUST NOT 以配置或注入的方式放开
