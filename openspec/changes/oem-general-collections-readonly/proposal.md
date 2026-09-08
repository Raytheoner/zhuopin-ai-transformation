# oem-general-collections-readonly Proposal

> **来源**：队列 §一 `#491`（2026-09-06 立行，`OP-0906-B` 业务总线）；由 `#466` 领取方 `OP-0906-C` 判 **D5「另包」** 派生 —— 判「另包」的那一刻就产生了一个无载体的裁决，`#491` 是该载体，本包是 `#491` 的交付物。
> **裁决来源（非本包再裁）**：**D5=(a)** 由 **Shao Peishen 本人** 2026-09-02 在 `oem-chroma-ownership-rejudge` design 审内裁定 —— 「采纳『校验入口未建成前通用库只读』——已有内容不受影响，仅禁新写入」。本包**只实现**，不改该口径、不扩大也不收窄。
> **依据件**：`openspec/changes/oem-chroma-ownership-rejudge/design.md` §D5（裁决原文）／同包 `specs/platform-oem-isolation/spec.md` L52-63（D5 的 spec 文本，已定稿）／`openspec/changes/oem-audit-fail-closed/design.md` 决策 4（判另包的理由原文）／`3-治理与合规/OEM数据隔离规范.md` §2.3、§3.2、§5 映射表 §2.3 行。
> **openspec 门槛核对（根 `CLAUDE.md` §5 三条）**：①改变全项目口径 ✅（「通用库当前不可写」成为平台强制行为，不再只是文档里的一句话）／②涉鉴权与数据可见性 ✅（写入侧准入判定）／③改变既有模块对外语义 ✅（`OEMRouter` 新增对外方法 `guard_write()` 与新异常类 `GeneralCollectionReadOnlyError`，并进 `data_isolation_layer.__all__`）——**三条全中**，故独立变更包。

## Why（为什么做）

`3-治理与合规/OEM数据隔离规范.md` §2.3 白纸黑字：通用知识库这一层「**写入侧控制是这一层的全部安全性所在**」，并列了三项写入前必过的校验（无 OEM 信息校验／脱敏＋质量 Champion 签字／写入写 audit）。而代码里这三项**一项都不存在**：`GENERAL_COLLECTIONS` 至今只在 `guard()` 的读取侧被引用，**没有任何写入侧函数**，`guard()` 又对通用库无条件放行、不校验 OEM 上下文。

⇒ 一条含 OEM 信息的 8D 若被写进 `kb_quality_cases`，**任何客户上下文都能检索到它，全程不报错、不留痕**。

Shao Peishen 本人已于 2026-09-02 就此裁决 **D5=(a)**：校验入口建成之前，通用库置为只读——已有内容不受影响，禁止新写入。裁决文本已在 `oem-chroma-ownership-rejudge` 包内落成 spec，但那一包明写「本包不落任何隔离层实现代码」；`oem-audit-fail-closed` 判 D5 为另包（`design.md` 决策 4：D5 是**新建入口**、与 D2「改一处已有分支」不对称，且属另一条独立 Requirement，不宜混进同一份 `compliance_redline_change` 的 diff）。⇒ 「只读」这条裁决自 2026-09-02 起在**代码里没有任何强制力**，本包是它的落地。

⚠️ **窗口期风险不是零，且正在变大**：`oem-audit-fail-closed` 决策 4 当时判「D5 延后不产生窗口期风险」，理由是「当前代码里没有任何写入通用库的函数存在」。该前提**至今仍成立**（本包重跑穷举核实，见 `tasks.md` §2），但 D1=(b) 之后 Q2 的**离线校准语料仍要落盘**，而 `kb_quality_cases` 正是「质量案例通用库」——「顺手把校准语料写进通用库」是 (b) 分支下最现实的一条越界路径（`oem-chroma-ownership-rejudge` design §D5 原话）。闸建在**第一个写入函数被写出来之前**，才是零成本的；建在之后就要回头改调用点。

### 本次退休哪一个既有守卫（协议〇.9 措施 B，机制类包强制回答）

**不能退，且必须写明为何不能。** 本包属"合规红线实现"类，其"守卫"是 `OEMRouter` 的读取侧 `guard()` —— 该守卫**不可退休**（`oem-chroma-ownership-rejudge` spec 已明写 L1 无到期日、约束为"不得下线"，理由＝QD-B 现行红线 ＋ 根 `CLAUDE.md` §4 质量域隔离边界，两者皆常设）。

本包**不新增任何独立守卫脚本／hook／CI job**，只在既有 `OEMRouter` 上补齐一个此前缺失的方法，因此不产生"规则只增不减"的净增量：新增的 `guard_write()` 与既有 `guard()` 是同一个守卫的读写两面，共用同一条 fail-closed 审计通道（`_record_denied`），未复制第二套判定逻辑。**本包自身设有退休条件**：写入侧「无 OEM 信息」校验入口建成之日，`guard_write()` 的 deny 分支即被改写为对该入口的调用（见 `design.md` 决策 5），届时本闸自动退场——它是一个**自带退休条件的临时闸**，不是永久新增的守卫。

### 伴生文件的 .gitignore 覆盖（队列 #328 子项②，强制回答）

**本变更不新增任何此前不存在的自动生成文件名形态。** 只读闸的拒绝留痕复用 `#466` 已建成的审计通道，落点是既有的 `reports/audit_log.jsonl`（未注入 `audit` 时的平台默认路径）——该形态在 `#466` 就已存在，非本次新造。

**核实方式（实测，非推断）**：`cd 5-平台底座/zhuopin_platform && git check-ignore -v reports/audit_log.jsonl` ⇒ 命中 `.gitignore:50:**/reports/`，退出码 `0`。本包新增文件仅四份 openspec 文档 ＋ 一份单测 ＋ 两处源码改动，全部是需要跟踪的仓库内容，不适用忽略规则。

## What Changes（改什么）

1. **新异常 `GeneralCollectionReadOnlyError(PermissionError)`**（`router.py`）——刻意**不**继承 `CrossOEMAccessError`：只读闸不是"跨客户访问"，且合并会让调用方 `except CrossOEMAccessError` 顺手吞掉本闸（理由见 `design.md` 决策 2）。同步进 `data_isolation_layer.__all__`。
2. **新审计动作常量 `ACTION_GENERAL_WRITE_DENIED = "general_collection_write_denied"`** —— 与 `cross_oem_access_denied` 分开计数，使 IATF 审计轨迹能区分"拿错客户上下文"与"整条写入通道未开放"两类违规企图。
3. **新方法 `OEMRouter.guard_write(oem, collection)`** —— 与只读的 `guard()` 分离的写入侧判定入口：通用库一律拒绝（拒绝前写 audit）；非通用 collection 委派给既有 `guard()`，不另立一套跨客户规则。
4. **`_record_denied` 泛化**：新增 `action` / `error_cls` 两个**带默认值**的参数（默认值＝ `#466` D2=(a) 的既有跨 OEM 语义，原有调用行为逐字不变），使只读闸复用同一条 fail-closed 通道而非复制一份。
5. **spec delta**（`platform-oem-isolation`）：ADDED 一条 Requirement「通用库只读闸 SHALL 在路由层以独立写入入口强制执行」（6 条 Scenario）。
6. **单测**：新增 `tests/test_general_collections_readonly.py`（13 用例），含一条**架构约束的机器守**——断言实现里不存在运行期开关或可注入 validator。

## Non-Goals（明确不做）

- 🔴 **不建 §2.3 的三项校验入口本身**（无 OEM 信息校验／脱敏＋质量 Champion 签字／写入写 audit）。本包只建"入口未建成期间的闸"，建入口是另一件事、另一个包、另一条队列行。
- 🔴 **不改读取侧语义**。`oem-chroma-ownership-rejudge` spec L55 那句「读取侧对通用 collection 的无条件放行 SHALL 仅在写入侧校验生效的前提下成立」若被读作"现在就该收紧读取侧"，那是一次新的口径变更（🟡 `change_criteria`），超出 D5 裁决文本（"已有内容不受影响"）。理由与边界见 `design.md` 决策 4。
- 🔴 **不改 `3-治理与合规/OEM数据隔离规范.md`**。§5 映射表 §2.3 行的改判文本已在 `tasks.md` §5 逐字备好，但该文件 L10 自定「维护：边界变更须经 Paul 批准并在本文修订记录登记」，且同表 §3.2 行的同类改判（V1.2）确由 Shao Peishen 2026-09-07 答 `2(a)` 后才落字——本包不自行落字、不代签批准人。
- 不建 `rag.retrieve()` 唯一入口（L2，到期日 2027-05，`#374` 已裁）。
- 不部署 `.51`、不触碰生产服务、不做任何 archive 动作。

## 知识资产三问（强制，全景规划 §1.4 第 2 条）

**⑴ 本流程哪些判断是人脑默会经验？**
- **「只读闸解闸的正确姿势」**——此前只在裁决人一句"校验入口建成前只读"里，代码零表达。本次显式化为：闸**不提供**任何运行期开关／环境变量／可注入 validator，解闸只能改写 `guard_write()` 的 deny 分支（必经 code review）。默会的部分是"为什么不给开关"：开关和可注入 validator 都会退化成"注入一个空校验器即放行"的绕过路径，而这条闸的全部价值就在于不可绕过。
- **「拒绝写入算不算违规企图」**——隔离规范 §3.2 只写了 `CrossOEMAccessError` 要留痕，没写"写入被闸拒"要不要留痕。本次按 §3.2 的**理由**（"违规企图本身就是审计事件"）判定：要，且用独立 action 名，使两类企图在审计轨迹里可分别计数。
- **「闸该建在哪一层」**——建在 `OEMRouter`（L1）而不是等 L2 `rag.retrieve()`：L2 到期日 2027-05，等它等于让裁决空转 8 个月；且 L1 是当前唯一存在的隔离判定点。

**⑵ 由谁显性化？（持有人 ＋ backup，实名）**
- 持有人：**Shao Peishen**（D5 裁决人，本包合规口径的唯一来源；解闸与读取侧收紧两项均须其本人拍板）
- backup：**孙涛**（可代 design 审查本包的**实现层**技术决策；🔴 **不可代改判 D5 本身**，亦不可代批准隔离规范 §5 映射表的改判——根 `CLAUDE.md` §5 决策代理条）

**⑶ 用什么方法提取？**
- **AI 起草·专家批改**：本包 `design.md` 五条实现层决策由 CC 起草并逐条写明"已否决方案 ＋ 否决理由"，交 design 审批改；其中决策 4（读取侧不动）与决策 5（不留开关）触及可绕过性，若审查方不同意即回到裁决人。
- **历史案例反推**：`#466` 的 fail-closed 通道（D2=(a)）是现成判例，本包逐条比对复用而非另立，"审计通道故障时仍以拒绝告终"的义务范围直接沿用其 design 决策 3 的边界（只覆盖拒绝路径，不覆盖允许路径）。

## 验收与晋档条件（强制，四档口径）

- **本变更包交付后场景所处档位**：**档1（mock 验证）**。理由：本包是平台底座的合规闸，全部验证为单测级（13 新增用例 ＋ 平台全量回归 ＋ 两个消费方场景回归），当前**无任何生产写入路径**可供档2 的"真实数据跑通"验证——因为"没有写入路径"正是本闸此刻的前提事实。
- **晋下一档的条件**（逐条）：
  1. §2.3 三项校验的**写入入口**建成（另包），届时本闸从"一律拒绝"改写为"经校验入口判定"；
  2. 至少一个真实写入方接线（当前候选：Q2 离线校准语料归集），跑通"含 OEM 信息内容被拦下 → 脱敏 → 质量 Champion 签字 → 写入并留痕"完整链路；
  3. 隔离规范 §5 映射表 §2.3 行改判落字（须 Shao Peishen 批准，见 `tasks.md` §5）；
  4. 主 spec `openspec/specs/platform-oem-isolation/spec.md` 已含本条 Requirement（即本包已 archive，且严格晚于 `oem-chroma-ownership-rejudge`）。
- **价值指标**（风险型）：**"含 OEM 信息内容进入跨客户可读通用库"的敞口数** —— 基线（2026-09-08，本包合入前）＝ **无上限敞口**：写入侧零校验、零闸、零留痕，任何一次写入都不会报错也不留痕，敞口大小完全取决于是否有人碰巧写了写入代码。目标（本包合入后）＝ **0 次新写入，且每一次企图必留痕**（`general_collection_write_denied` 计数可查）。基线由业务 Champion（质量域，经 Shao Peishen 指派）确认存档 —— 🔴 **本项基线尚未经 Champion 签字确认，本包不代签**。
- **LLM 判据黄金集**：**不适用**。本包无任何 LLM 运行时判断，判定全为集合成员判定与字符串规范化，无需黄金集。

## Impact（影响面）

- **spec**：`platform-oem-isolation`（ADDED 1 条 Requirement，6 条 Scenario）。**不与任何既有 Requirement 同名** ⇒ 本包**不进入** `oem-chroma-ownership-rejudge` → `oem-audit-fail-closed` 那条 archive 次序链（理由见 `design.md` 决策 3）。
- **代码**：`5-平台底座/zhuopin_platform/zhuopin_platform/data_isolation_layer/router.py`（＋异常类／常量／`guard_write()`／`_record_denied` 泛化）；同层 `__init__.py`（导出）；新增 `tests/test_general_collections_readonly.py`。
- **调用点核查**（全库穷举，非抽样，见 `tasks.md` §2）：`OEMRouter(` 全仓 30 处 ／ `GENERAL_COLLECTIONS` 与三个 `kb_*` 名全仓穷举 —— **无一处生产代码写入通用库**（FI10 `intake.py` 是本轮新出现的生产实例化点，只走 `resolve()`／`guard()` 读取侧，不碰通用库）。本包为纯新增 API，既有调用点行为**逐字不变**。
- **红线核对**：mock 先行 ✅（无真实数据）｜ audit 留痕 ✅（拒绝前必写，通道故障 fail-closed）｜ OEM 隔离 ✅（本包即隔离实现，收紧不放宽）｜ L2 门禁 ➖ 不适用（无 L2 自动执行动作）｜ ISO 26262 ➖ 不适用（非安全相关代码，无 ASIL 等级）。
- **不改**任何权威文档口径（隔离规范／全景规划／主 spec），只落代码与 spec delta。
